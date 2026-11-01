## 1. Core session and mask layers

- [x] 1.1 Add stable prompt IDs and prompt deletion/replay from the original encoded SAM state with zero encoder calls.
- [x] 1.2 Add full-image locked foreground/background masks, connected-component preview/lock/unlock, and immutable hash checks.
- [x] 1.3 Add next-region pass lifecycle that preserves locked regions, resets only active state, and composes the final mask deterministically.
- [x] 1.4 Clip all local mask operations to unlocked pixels and expose an explicit 1 px pencil radius.
- [x] 1.5 Extend session undo checkpoints and core tests for prompt deletion, lock/unlock, stale jobs, overlap, and exact composition.

## 2. Desktop service and persistence

- [x] 2.1 Add protocol operations for lock preview/confirm, unlock, next region, prompt deletion, and active snapshot fields.
- [x] 2.2 Route new operations through controller/service with revision and stale-job guards; synchronize Undo state.
- [x] 2.3 Persist sidecar v2 locked regions, active pass, prompt IDs, operation ancestry, and composed-mask integrity; migrate v1 loads.
- [x] 2.4 Add Python integration tests for multi-pass save/reload, lock immutability, and failure rollback.

## 3. React/Tauri workflow

- [x] 3.1 Keep SAM point tools visible with Chinese disabled explanations and a `回到 SAM 結果` action.
- [x] 3.2 Add prompt marker selection/deletion list and Chinese status for SAM versus pixel-edit mode.
- [x] 3.3 Add lock/unlock/next-region controls, frozen overlays, clipping feedback, and keyboard shortcuts.
- [x] 3.4 Add selectable 1 px, 3 px, and 5 px pencil/brush sizes (1 px default) and update canvas interaction, store, styles, and UI tests.
- [x] 3.5 Make brush/erase pointer capture and full-image-to-crop coordinate mapping resilient in the native WebView, and expose a selectable Frozen-region Dropbox for unlocking any saved region.
- [x] 3.6 Add export-only contour cleanup and LabelMe polygon interoperability while preserving the lossless PNG + sidecar source.
- [x] 3.7 Add a reversible `合併區塊` action that flattens locked foreground regions into the active editable mask, preserves locked exclusions, and documents small-gap repair guidance.
- [x] 3.8 Add a real MobileSAM CPU Playwright E2E for `014.png` covering ROI lock, point-tool enablement, coordinate delivery, and prompt-history update.
- [ ] 3.9 Add an independently available `編輯範圍` tool that mirrors PhoneCV's first-corner/opposite-corner click flow, supports nearby-corner adjustment after completion, preserves the `框選` two-click ROI/SAM tool, clips brush and erase strokes (including radius) to the half-open `XYXY` boundary, and adds UI/core regression coverage without invoking `sessions.lock_roi`.

## 4. Verification and release

- [x] 4.1 Run focused Python and React tests, then full regression suites.
- [x] 4.2 Run OpenSpec strict validation and acceptance contract/state/evidence validators for this change.
- [x] 4.3 Restart the Tauri native app and verify the multi-region workflow with the real local MobileSAM CPU backend.
