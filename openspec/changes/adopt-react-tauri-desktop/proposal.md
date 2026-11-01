## Why

SegVision v1 currently freezes PySide6 as the desktop GUI, but the annotation surface (dataset browsing, canvas zoom/pan, ROI, point refinement, candidate comparison, brush edits, long-job progress, recoverable errors, and recovery) is better served by a dedicated React + Tauri native shell. The Python core, MobileSAM CPU backend, and existing behavioral contracts must remain the source of truth. This change freezes the desktop transport, host, UI, sidecar, and cutover contracts so the GUI can be replaced without silently changing product semantics.

## What Changes

- Add a versioned localhost desktop protocol with separate control, event, and binary data planes.
- Add a Tauri 2 host that owns windowing, capability grants, sidecar lifecycle, and asset proxying.
- Add a React + Vite annotation UI that implements the existing GUI workflow contract without owning masks, jobs, or persistence.
- Add a Python desktop sidecar adapter and thin application service over the existing core/runtime/adapters.
- Add GUI functional-parity, security, and offline-installer gates; PySide6 remains until those gates pass.
- Do **not** change ROI geometry, candidate policy, MobileSAM behavior, Accept/Needs Review rules, or core headless in-memory constraints.
- **BREAKING** only after documented parity: the default shipped GUI entry point may switch from PySide6 to the Tauri desktop app. The importable `segvision` Python package remains GUI-free.

## Capabilities

### New Capabilities

- `desktop-protocol`: Versioned control/event/data-plane contracts, revision concurrency, stale rejection, typed errors, and a single OpenAPI/JSON Schema source of truth.
- `desktop-host`: Tauri 2 host responsibilities: sidecar lifecycle, localhost secret, file/folder grants, command allowlist, CSP, and binary asset proxy.
- `desktop-ui`: React annotation UI ownership, canvas/coordinate mapping, shortcut parity, and projection of Python authoritative snapshots.
- `desktop-sidecar`: Python localhost adapter, application-service orchestration, schema validation, job events, and crash/recovery handshake.
- `desktop-parity-release`: Functional parity with the existing GUI workflow, phased cutover, offline Tauri packaging, and license/network gates.

### Modified Capabilities

<!-- Main specs are not yet archived. Existing v1 capabilities are preserved by reference; this change adds desktop-shell requirements instead of rewriting UIW/OFR text in-place. -->

## Impact

- Adds `apps/desktop-ui` (React + Vite), `apps/desktop-host` (Tauri 2 / Rust), and `packages/desktop-protocol` (OpenAPI 3.1 + event schemas).
- Adds `src/segvision/application/` and `src/segvision/transport/desktop_api/` without modifying `src/segvision/core`.
- Introduces React, Vite, Tauri 2, WebView2, Rust host, and a versioned Python sidecar bundle; CPU-only PyTorch/MobileSAM remain in the sidecar.
- Existing pytest core/E2E/acceptance gates remain mandatory. New contract, sidecar integration, Vitest, and desktop E2E gates are added.
- Does not authorize GPU, cloud inference, portal/iframe/plugin runtime, React-direct sidecar access, or packing MVTec/model weights without existing approval rules.
- PySide6 remains in-tree until desktop-parity-release scenarios pass; removal is a later change.
