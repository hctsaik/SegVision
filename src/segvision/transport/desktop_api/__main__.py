"""Sidecar entrypoint: python -m segvision.transport.desktop_api"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys

from .app import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="segvision-desktop-engine")
    parser.add_argument("--secret", default=None, help="launch secret (prefer SEGVISION_SECRET for managed launches)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--actor", default="interactive_user")
    parser.add_argument("--prefer-real", action="store_true")
    parser.add_argument("--lazy-real", action="store_true")
    parser.add_argument("--dev-origin", default=os.environ.get("SEGVISION_DEV_ORIGIN"))
    args = parser.parse_args(argv)
    secret = args.secret or os.environ.get("SEGVISION_SECRET", "")
    if not secret:
        parser.error("--secret or SEGVISION_SECRET is required")
    if args.host != "127.0.0.1":
        print("sidecar must bind 127.0.0.1", file=sys.stderr)
        return 2
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    port = args.port or _free_port()
    ready = {"port": port, "pid": os.getpid(), "host": "127.0.0.1"}
    sys.stdout.write(json.dumps(ready) + "\n")
    sys.stdout.flush()
    import uvicorn

    app = create_app(
        secret=secret,
        actor=args.actor,
        prefer_real=args.prefer_real,
        lazy_real=args.lazy_real,
        dev_origin=args.dev_origin,
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
