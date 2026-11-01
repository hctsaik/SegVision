# Tasks

Track A only: opt-in next-image `user_roi_full` reuse in the desktop UI. Do not implement ConstraintSet, prototype matching, or offline LAB fitting.

- [x] 1. Add the `next-image-roi-reuse` spec and keep Next gated on durable outcome
- [x] 2. Add a default-off reuse-last-ROI control in `apps/desktop-ui`
- [x] 3. On Next/`N` with reuse on, close → create → `sessions.lock_roi` with the captured rectangle
- [x] 4. Leave list-item open on create-only; fail closed when lock_roi rejects
- [x] 5. Cover NIR-R001–R004 with Vitest in `apps/desktop-ui/src/App.test.tsx`
