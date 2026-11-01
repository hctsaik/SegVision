## Context

Human decision 2026-08-29: adopt Track A only from `docs/one-shot-class-transfer-recommendation.md`. Track B/C/D product changes stay closed. Track D OpenSpec remains blocked until this control arm exists.

Authoritative inputs: `PRD.md` (reuse previous ROI when composition is stable), `annotation-session` (new image must not reuse encoded crop), `desktop-ui` (Next after durable outcome), this change.

## Goals / Non-Goals

**Goals:**

- Opt-in sequential Next can lock the previous `user_roi_full` on the new item.
- New session still encodes; timer origin is that image's `first_roi_locked`.
- Invalid/out-of-bounds ROI fails closed: `IMAGE_OPEN`, operator error, no silent clip.

**Non-Goals:**

- Sticky-on-by-default reuse.
- Carrying ROI when clicking an arbitrary dataset list item.
- ConstraintSet, prototype matching, offline LAB fitting, Focus Crop.
- Reusing embeddings, candidates, points, or local edits.
- Changing `sessions.create` to accept an initial ROI (keep the frozen operation set).
- Python PySide6 `next_image` actually switching files (it only records `next_image` today).

## Decisions

1. **Opt-in checkbox, default off.** Matches the research memo and avoids silent lock on the next image.
2. **Reuse is UI-owned carry, then existing `lock_roi`.** No new protocol operation.
3. **Capture ROI before `sessions.close`.** Closing the previous session must not lose the rectangle.
4. **List navigation does not carry.** Only Next button and `N`.
5. **Failure does not roll back to the previous item.** The new session stays open so the user can draw a fresh ROI.
6. **After a successful lock (drawn or reused), the canvas frames that `user_roi_full`.** Coordinate reuse is useless if the next 1000px image still shows the top-left corner. List navigation does not frame a missing ROI.
7. **A short status line reports reuse.** It must not appear when reuse is off or when the user opens an item from the list.

## Risks

- A too-large previous ROI may encode slowly on a larger next image; existing ROI-size warnings still apply after lock.
- Class id comes from the previous snapshot or the next item metadata, never a model.
