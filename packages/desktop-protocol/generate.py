"""Generate TypeScript and Rust protocol bindings from protocol.json."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))


def ts() -> str:
    ops = ",\n  ".join(json.dumps(op["name"]) for op in DATA["operations"])
    codes = ",\n  ".join(json.dumps(c) for c in DATA["error_codes"])
    kinds = ",\n  ".join(json.dumps(k) for k in DATA["event_kinds"])
    assets = ",\n  ".join(json.dumps(k) for k in DATA["asset_kinds"])
    routes = ",\n  ".join(
        f'{json.dumps(op["name"])}: {{ method: {json.dumps(op["method"])}, path: {json.dumps(op["path"])} }}'
        for op in DATA["operations"]
    )
    return f"""/* generated from protocol.json — do not hand-edit */
export const PROTOCOL_VERSION = {json.dumps(DATA["protocol_version"])} as const;
export const OPERATIONS = [
  {ops}
] as const;
export type OperationName = (typeof OPERATIONS)[number];
export const ERROR_CODES = [
  {codes}
] as const;
export type ErrorCode = (typeof ERROR_CODES)[number];
export const EVENT_KINDS = [
  {kinds}
] as const;
export type EventKind = (typeof EVENT_KINDS)[number];
export const ASSET_KINDS = [
  {assets}
] as const;
export type AssetKind = (typeof ASSET_KINDS)[number];
export const ROUTES: Record<OperationName, {{ method: string; path: string }}> = {{
  {routes}
}};
"""


def rs() -> str:
    ops = ",\n    ".join(f'"{op["name"]}"' for op in DATA["operations"])
    codes = ",\n    ".join(f'"{c}"' for c in DATA["error_codes"])
    kinds = ",\n    ".join(f'"{k}"' for k in DATA["event_kinds"])
    return f"""// generated from protocol.json — do not hand-edit
pub const PROTOCOL_VERSION: &str = "{DATA["protocol_version"]}";
pub const OPERATIONS: &[&str] = &[
    {ops}
];
pub const ERROR_CODES: &[&str] = &[
    {codes}
];
pub const EVENT_KINDS: &[&str] = &[
    {kinds}
];
"""


def main() -> None:
    generated = ROOT / "generated"
    generated.mkdir(exist_ok=True)
    (generated / "protocol.ts").write_text(ts(), encoding="utf-8", newline="\n")
    (generated / "protocol.rs").write_text(rs(), encoding="utf-8", newline="\n")
    (ROOT / "index.ts").write_text(
        'export * from "./generated/protocol";\n', encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
