from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="segvision")
    parser.add_argument("--version", action="version", version="segvision 0.1.0")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("gui", help="Launch the default Native App (Tauri + React + sidecar)")
    sub.add_parser("pyside6", help="Launch the deprecated PySide6 shell")
    export = sub.add_parser(
        "export-labelme",
        help="Convert accepted PNG + JSON sidecars to LabelMe polygon JSON",
    )
    export.add_argument("input", help="SegVision accepted-output directory")
    export.add_argument("output", help="Directory for LabelMe JSON files")
    export.add_argument(
        "--image-root",
        help="Optional dataset root; matching source images are referenced by relative path",
    )
    export.add_argument("--label", help="Override the LabelMe shape label")
    args = parser.parse_args(argv)
    if args.cmd == "gui":
        from segvision.desktop import main as desktop_main

        return desktop_main()
    if args.cmd == "pyside6":
        from segvision.gui.app import main as pyside_main

        return pyside_main()
    if args.cmd == "export-labelme":
        from pathlib import Path

        from segvision.adapters.labelme import export_directory

        exported = export_directory(
            Path(args.input),
            Path(args.output),
            image_root=Path(args.image_root) if args.image_root else None,
            label=args.label,
        )
        print(f"Exported {len(exported)} LabelMe JSON file(s) to {Path(args.output)}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
