## Why

SegVision currently hides SAM point refinement after the first brush or erase operation, leaving users unable to correct another prompt or finish a second disconnected region without discarding work. Users need a predictable workflow that distinguishes model prompts from pixel edits, preserves completed regions, and lets MobileSAM operate on a new region without overwriting approved pixels.

## What Changes

- Keep `＋ 加入目標` and `－ 排除背景` visible with a Chinese disabled explanation whenever the current pass is in pixel-edit mode.
- Add selectable SAM prompt markers and deterministic deletion/replay of an individual prompt.
- Add an explicit 1 px pencil plus brush/erase editing that is clipped away from locked pixels.
- Add multi-pass annotation: lock one foreground component, start a new ROI/pass, and compose all locked regions with the active result.
- Add lock, unlock, undo, next-region, save/reload, and provenance semantics for frozen regions.
- **BREAKING** Change the session contract from a single terminal manual-edit candidate to separate locked-region, active-SAM, and active-manual layers; MobileSAM may run only on the active pass and can never overwrite locked pixels.

## Capabilities

### New Capabilities

- `multi-region-annotation`: Protected foreground components, next-region passes, composition, and lock/unlock operations.
- `prompt-management`: Prompt marker selection, deletion, replay, and point history.

### Modified Capabilities

- `annotation-session`: Allow multiple active passes and preserve immutable locked masks while maintaining revision-safe undo.
- `annotation-workflow`: Expose disabled SAM tools, pixel-edit mode, lock/unlock/next-region controls, and multi-pass state transitions.
- `annotation-persistence`: Persist locked regions, prompt history, operation ancestry, and the composed final mask.

## Impact

The Python core session API, MobileSAM adapter job routing, controller/state machine, React canvas toolbar and overlays, sidecar schema/loader, and acceptance tests are affected. No new inference provider is required; the existing local MobileSAM CPU backend remains the only model path.
