# SegVision

SegVision is a CPU-first image annotation tool under active development. Its UI is built with React and Vite, the desktop host uses Tauri 2, and segmentation and persistence remain in the Python application and sidecar.

## Project layout

- `apps/desktop-ui/` — React interface and browser-based UI tests
- `apps/desktop-host/` — Tauri desktop host
- `src/segvision/` — Python application, transport, and core
- `packages/desktop-protocol/` — UI-to-sidecar protocol contracts
- `openspec/changes/` — product behavior and implementation acceptance criteria

## Development

Use the Python 3.11 environment described in the project setup, then follow the launch and test commands in [`apps/README.md`](apps/README.md). The current implementation and release gaps are documented in [`docs/native-app-status.md`](docs/native-app-status.md).

Install the React UI dependencies and run its checks from the repository root:

```powershell
npm --prefix apps/desktop-ui ci
npm --prefix apps/desktop-ui test
npm --prefix apps/desktop-ui run build
```

SegVision is not yet a release-ready application. See [`PRD.md`](PRD.md) and the active OpenSpec change for scope and acceptance requirements.
