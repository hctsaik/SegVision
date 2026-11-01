"""Stage three similar-composition MVTec capsule scratch images.

Uses test/scratch 000, 002, 003: defects sit in the same band of the capsule,
so carrying one tight ROI is a fair trial of Track A. Different crack instances
are not used.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

DEFECT = "scratch"
NAMES = ("000.png", "002.png", "003.png")


def bbox(mask_path: Path) -> list[int]:
    arr = np.asarray(Image.open(mask_path).convert("L")) > 0
    ys, xs = np.where(arr)
    if xs.size == 0:
        raise SystemExit(f"empty gold mask: {mask_path}")
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("dest", type=Path)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(os.environ["SEGVISION_MVTEC_CAPSULE_ROOT"])
        if os.environ.get("SEGVISION_MVTEC_CAPSULE_ROOT")
        else None,
        help="MVTec capsule dataset root (or set SEGVISION_MVTEC_CAPSULE_ROOT)",
    )
    args = parser.parse_args()
    if args.source is None:
        parser.error("provide --source or set SEGVISION_MVTEC_CAPSULE_ROOT")
    source = args.source
    dest = args.dest
    dest.mkdir(parents=True, exist_ok=True)
    test_dir = source / "test" / DEFECT
    gold_dir = source / "ground_truth" / DEFECT
    if not test_dir.is_dir() or not gold_dir.is_dir():
        print(f"MVTec capsule {DEFECT} not found under {source}", file=sys.stderr)
        return 3
    items: list[dict[str, object]] = []
    for name in NAMES:
        src = test_dir / name
        mask = gold_dir / f"{Path(name).stem}_mask.png"
        if not src.is_file() or not mask.is_file():
            print(f"missing {src} or {mask}", file=sys.stderr)
            return 3
        shutil.copy2(src, dest / name)
        shutil.copy2(mask, dest / f"{Path(name).stem}_gold.png")
        rgb = Image.open(dest / name)
        items.append(
            {
                "name": name,
                "width": int(rgb.size[0]),
                "height": int(rgb.size[1]),
                "gold_bbox": bbox(dest / f"{Path(name).stem}_gold.png"),
            }
        )
    (dest / "manifest.json").write_text(
        json.dumps({"class_id": "capsule", "items": list(NAMES)}),
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps({"root": str(dest), "source": str(source), "defect": DEFECT, "items": items})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
