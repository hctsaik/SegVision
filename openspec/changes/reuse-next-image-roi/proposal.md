## Why

PRD stage 0 already allows a stable batch to reuse the previous `user_roi`. The desktop UI currently opens a new session on Next with an empty ROI, so every image forces a redraw. That cost must be measurable before any later prototype path can claim it reduced annotation time.

## What Changes

- Add an opt-in desktop control to reuse the last locked `user_roi_full` when advancing to the next dataset item.
- After `sessions.create` on the new item, submit that rectangle through the existing `sessions.lock_roi` path so the new image still encodes once.
- If the rectangle is missing or invalid on the new image, leave `IMAGE_OPEN`, show an operator error, and do not invent a clipped ROI.
- Do not reuse embeddings, candidates, points, edits, or previous-mask state. Do not auto-Accept. Do not apply reuse when the user opens an arbitrary list item.

## Capabilities

### New Capabilities

- `next-image-roi-reuse`: opt-in carry of `user_roi_full` across sequential Next navigation only.

### Modified Capabilities

- `desktop-ui`: Next/`N` may follow create with one `sessions.lock_roi` when reuse is enabled.

## Impact

- Desktop React UI and Vitest only. No core backend protocol operations, no MobileSAM changes, no Track B/C/D artifacts.
- Existing Accept/Needs Review gating for Next remains unchanged.
