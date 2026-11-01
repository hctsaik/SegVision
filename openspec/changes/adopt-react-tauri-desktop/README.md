# adopt-react-tauri-desktop

Replace the v1 PySide6 GUI shell with a dedicated React + Vite + Tauri 2 desktop host while keeping the existing Python core, MobileSAM CPU backend, and OpenSpec behavioral contracts.

Status: OpenSpec artifacts complete (`proposal`, `design`, `specs`, `tasks`). This is an implementation contract, not a completed GUI replacement. PySide6 remains the shipped default until parity evidence exists.

## Implementation handoff

Read in this order:

1. `proposal.md` — why the shell changes and which capabilities are added.
2. `design.md` — ADRs, layout, control/event/data planes, migration stages.
3. `specs/*/spec.md` — normative desktop requirements:
   - `desktop-protocol` (`DTP-*`)
   - `desktop-host` (`DTH-*`)
   - `desktop-ui` (`DUI-*`)
   - `desktop-sidecar` (`DSS-*`)
   - `desktop-parity-release` (`DPR-*`)
4. `tasks.md` — 75-task staged checklist (scaffold → host → viewer → annotation loop → persistence → MobileSAM/E2E → installer → default switch).
5. Existing v1 contracts remain in force: `openspec/changes/build-segvision-v1/specs/` especially `annotation-session`, `annotation-workflow`, and `offline-release`.
6. Background: `docs/react-tauri-architecture-recommendation.md`.

`spec-review.md` is a working review log of the spec-authoring round; it is not a capability spec.

## Frozen shape (do not silently change)

- React = presentation and uncommitted preview.
- Tauri = window, grants, sidecar lifecycle, the only production bridge.
- Python session = authoritative mask, revision, candidates, Accept, persistence.
- `sessions.create` = `IMAGE_OPEN` at protocol revision `0` (no `SegVisionEngine.start`).
- `sessions.lock_roi` = only `start` call; mints core revision `1`.
- Images/masks travel as opaque binary assets (display masks PNG `{0,255}`), not JSON/base64.
- Eight sidecar error codes only; host has separate grant/filesystem codes.

## Authoring validation

```powershell
openspec validate adopt-react-tauri-desktop --strict --no-interactive
openspec status --change adopt-react-tauri-desktop
```

Do not archive while required tasks are unchecked. Do not treat this change as the active v1 product change; `build-segvision-v1` remains the engineering-release contract until this shell reaches documented parity.
