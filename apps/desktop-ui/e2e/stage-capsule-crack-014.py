"""Stage MVTec capsule crack 014.png plus its gold mask for GUI E2E."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

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
    image = source / "test" / "crack" / "014.png"
    gold = source / "ground_truth" / "crack" / "014_mask.png"
    dest = args.dest
    dest.mkdir(parents=True, exist_ok=True)
    if not image.is_file() or not gold.is_file():
        print(f"missing {image} or {gold}", file=sys.stderr)
        return 3
    shutil.copy2(image, dest / "014.png")
    shutil.copy2(gold, dest / "014_gold.png")
    rgb = Image.open(dest / "014.png")
    (dest / "manifest.json").write_text(
        json.dumps({"class_id": "capsule", "items": ["014.png"]}),
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps(
            {
                "root": str(dest),
                "source": str(image),
                "gold": str(gold),
                "items": [
                    {
                        "name": "014.png",
                        "width": int(rgb.size[0]),
                        "height": int(rgb.size[1]),
                        "gold_bbox": bbox(dest / "014_gold.png"),
                    }
                ],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
