"""Build benchmarks/dataset-manifest.jsonl from an extracted MVTec AD 2 test_public gold set.

Reads paired defect images and pixel ground-truth masks, measures the mask
properties that decide whether a record fits the v1 "one binary foreground blob
per image" contract, and emits one JSON object per image/mask pair.

Dependencies stay inside the declared project set (numpy, Pillow); connected
components come from a run-length union-find rather than scipy or cv2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

SCHEMA_VERSION = 1
DATASET_ID = "MVTec AD 2"
LICENSE = "CC BY-NC-SA 4.0"
LICENSE_ACK = "I_ACKNOWLEDGE_MVTEC_AD_2_CC_BY_NC_SA_4_0_NONCOMMERCIAL_RESEARCH_ONLY"

# A record whose largest component holds at least this share of the foreground
# is one blob plus specks, not a genuine multi-object scene.
DOMINANT_SHARE = 0.95
TINY_AREA_FRACTION = 0.001


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class _UnionFind:
    def __init__(self) -> None:
        self.parent: list[int] = []

    def add(self) -> int:
        self.parent.append(len(self.parent))
        return len(self.parent) - 1

    def find(self, a: int) -> int:
        root = a
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[a] != root:
            self.parent[a], a = root, self.parent[a]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _row_runs(row: np.ndarray) -> list[tuple[int, int]]:
    """Half-open [start, end) runs of True in a 1-D boolean row."""
    padded = np.concatenate(([False], row, [False]))
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    return list(zip(edges[0::2].tolist(), edges[1::2].tolist(), strict=True))


def connected_components(mask: np.ndarray) -> tuple[int, list[int]]:
    """8-connected component count and pixel counts, via run-length union-find.

    Defect masks are sparse, so the run count stays far below the pixel count
    and the Python-level loop stays cheap.
    """
    uf = _UnionFind()
    prev: list[tuple[int, int, int]] = []  # (start, end, label)
    sizes: list[int] = []
    for y in range(mask.shape[0]):
        current: list[tuple[int, int, int]] = []
        for start, end in _row_runs(mask[y]):
            label = uf.add()
            sizes.append(end - start)
            # 8-connectivity: diagonally touching runs overlap once widened by 1.
            for p_start, p_end, p_label in prev:
                if p_start < end + 1 and start < p_end + 1:
                    uf.union(label, p_label)
            current.append((start, end, label))
        prev = current

    totals: dict[int, int] = {}
    for label, size in enumerate(sizes):
        root = uf.find(label)
        totals[root] = totals.get(root, 0) + size
    return len(totals), sorted(totals.values(), reverse=True)


def _stratum(components: int, largest_share: float, area_fraction: float) -> dict[str, Any]:
    if components == 1:
        shape = "single_blob"
    elif largest_share >= DOMINANT_SHARE:
        shape = "dominant_blob"
    else:
        shape = "multi_blob"
    if area_fraction < TINY_AREA_FRACTION:
        size = "tiny"
    elif area_fraction < 0.01:
        size = "small"
    elif area_fraction < 0.1:
        size = "medium"
    else:
        size = "large"
    return {
        "shape": shape,
        "size": size,
        "v1_single_foreground_compatible": shape in {"single_blob", "dominant_blob"},
    }


def _pairs(root: Path) -> Iterator[tuple[str, Path, Path]]:
    for category_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        gt_dir = category_dir / "test_public" / "ground_truth" / "bad"
        bad_dir = category_dir / "test_public" / "bad"
        if not gt_dir.is_dir():
            continue
        for mask_path in sorted(gt_dir.glob("*_mask.png")):
            image_path = bad_dir / f"{mask_path.stem.removesuffix('_mask')}.png"
            if not image_path.is_file():
                raise FileNotFoundError(f"mask without image: {mask_path}")
            yield category_dir.name, image_path, mask_path


def build_record(category: str, image_path: Path, mask_path: Path, root: Path) -> dict[str, Any]:
    with Image.open(image_path) as img:
        image_size, image_mode = img.size, img.mode
    with Image.open(mask_path) as m:
        mask_size, mask_mode = m.size, m.mode
        mask_arr = np.asarray(m.convert("L"))
    if image_size != mask_size:
        raise ValueError(f"size mismatch: {image_path} {image_size} vs {mask_path} {mask_size}")

    binary = mask_arr > 0
    height, width = binary.shape
    total = height * width
    foreground = int(binary.sum())
    components, sizes = connected_components(binary)
    largest = sizes[0] if sizes else 0
    area_fraction = foreground / total
    largest_share = (largest / foreground) if foreground else 0.0

    ys, xs = np.nonzero(binary)
    if foreground:
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
        bbox = [x0, y0, x1 - x0 + 1, y1 - y0 + 1]
        touches_border = bool(x0 == 0 or y0 == 0 or x1 == width - 1 or y1 == height - 1)
    else:
        bbox = [0, 0, 0, 0]
        touches_border = False

    stem = image_path.stem
    scene_id, _, variant = stem.partition("_")
    return {
        "schema_version": SCHEMA_VERSION,
        "record_id": f"mvtec_ad_2/{category}/{stem}",
        "dataset_id": DATASET_ID,
        "license": LICENSE,
        "license_acknowledgement": LICENSE_ACK,
        "commercial_use_authorized": False,
        "category": category,
        "scene_id": scene_id,
        "variant": variant,
        # One capture per scene at nominal exposure/position; the other variants
        # are the robustness axis, not extra scenes.
        "gold_subset": variant == "regular",
        "stratum": _stratum(components, largest_share, area_fraction),
        "image": {
            "path": image_path.relative_to(root).as_posix(),
            "sha256": _sha(image_path),
            "width": image_size[0],
            "height": image_size[1],
            "mode": image_mode,
        },
        "mask": {
            "path": mask_path.relative_to(root).as_posix(),
            "sha256": _sha(mask_path),
            "width": mask_size[0],
            "height": mask_size[1],
            "mode": mask_mode,
            "values": sorted(int(v) for v in np.unique(mask_arr)),
        },
        "mask_stats": {
            "foreground_pixels": foreground,
            "area_fraction": round(area_fraction, 8),
            "components_8conn": components,
            "largest_component_pixels": largest,
            "largest_component_share": round(largest_share, 6),
            "component_sizes_top5": sizes[:5],
            "bbox_full": bbox,
            "bbox_area_fraction": round(bbox[2] * bbox[3] / total, 8),
            "touches_image_border": touches_border,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="extracted mvtec_ad_2 directory")
    parser.add_argument("--out", type=Path, required=True, help="output .jsonl path")
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.out.open("w", encoding="utf-8", newline="\n") as f:
        for category, image_path, mask_path in _pairs(args.root):
            record = build_record(category, image_path, mask_path, args.root)
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
            if count % 50 == 0:
                print(f"  {count} records...", flush=True)
    print(f"wrote {count} records to {args.out}")


if __name__ == "__main__":
    main()
