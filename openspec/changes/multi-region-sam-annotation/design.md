## Context

The current session has one selected candidate. A local brush/erase operation creates a terminal `manual_edit` candidate and disables all model calls. The React toolbar hides disabled point tools, so users cannot tell why SAM refinement disappeared or how to work on another disconnected object. MobileSAM state is opaque and may change any unlocked pixel on every decode; it cannot provide an immutable-region guarantee by itself.

## Goals / Non-Goals

**Goals:**

- Keep model prompts, pixel edits, and protected regions as separate layers.
- Support repeated passes over disconnected regions while preserving locked pixels exactly.
- Provide deterministic prompt deletion/replay, undo, unlock, persistence, and stale-job safety.
- Keep the existing local MobileSAM CPU backend and encode-once/decode-only refinement contract.

**Non-Goals:**

- Multi-class or multi-instance training outputs; the committed result remains one binary mask.
- A second inference provider, cloud inference, automatic Accept, or pixel-OR fusion of ordinary candidates.
- Editing a locked region without an explicit unlock operation.

## Decisions

1. **Layered session state.** Store full-image `locked_foreground` and `locked_background` masks plus one active pass (`user_roi`, SAM candidate/logits, ordered prompts, and manual delta). The display/commit mask is `locked_foreground OR (active_mask AND NOT locked_background)`. Frozen masks are copied, never passed as a lock guarantee through `mask_input`.

2. **Component lock semantics.** `鎖定此區塊` selects the 8-connected foreground component containing the clicked pixel. The UI previews the component before confirmation. The region record stores an ID, full-image mask hash, click coordinate, parent candidate, prompt IDs, and sequence. A one-pixel background guard is recorded when exact outer contour protection is requested; otherwise a later pass may add adjacent foreground pixels but cannot erase the locked component.

3. **Pass boundaries.** After locking, `新增下一區塊` clears only active ROI/SAM/manual state, releases the old embedding, increments the session revision, and starts a fresh ROI. Locked regions survive ROI changes and stale jobs. SAM jobs are scoped to the active pass and their result is composited only over unlocked pixels.

4. **Prompt history.** Every prompt has a stable ID and full-image coordinate. Deleting any prompt rebuilds from the pass's original SAM candidate using the remaining ordered prompts, with zero encoder calls; the operation is atomic and rolls back on decode failure. Undo remains the cheapest way to remove the latest action.

5. **Pixel tools.** Brush/erase operate on the active mask/manual delta only, with an explicit 1 px pencil. Strokes clip locked pixels and create one undo checkpoint on pointer-up. Entering pixel mode disables (but does not hide) SAM buttons and offers `回到 SAM 結果`; starting another pass re-enables SAM.

6. **Persistence and compatibility.** Sidecar version increments to `2`; v1 sidecars load as one unlocked pass. New records include locked regions, active pass, prompt IDs, operation ancestry, and composed-mask hash. Accepted PNG remains `{0,255}` full-image binary output.

## Risks / Trade-offs

- [Risk] Connected components can join through a one-pixel bridge → show a preview and permit undo/unlock; use the background guard for exact contour protection.
- [Risk] Replaying many prompts costs decoder time → keep the original embedding and replay decode only, expose progress, and commit atomically.
- [Risk] A new pass can touch a locked boundary → clip writes to unlocked pixels and preserve locked hashes in every commit test.
- [Risk] Existing clients expect terminal manual lock → version the sidecar/API snapshot and keep disabled-tool explanations plus `回到 SAM 結果` for the old path.

## Migration Plan

Implement core state and APIs first, then controller/sidecar, then React controls and overlays. Read v1 sidecars as a single pass with no locked regions. On failure, the active pass can be discarded without changing locked regions; the previous v1 behavior remains available for sessions that never call `新增下一區塊`.

## Open Questions

- Whether the background guard should be on by default or only when the user selects `鎖定輪廓` (default recommendation: on for component lock).
- Whether to expose a separate locked-background tool in the first UI release (default recommendation: store it internally, expose only foreground component lock initially).
