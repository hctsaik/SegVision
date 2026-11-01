## Why

The human goal is not to copy the previous `user_roi` coordinates. It is to learn what the accepted foreground looks like in DINO patch space, search the next image for a similar region even if it moved, then let SAM propose edges. Track A (Reuse last ROI) remains an optional coordinate shortcut and is the wrong product for class-like transfer.

## What Changes

- Add a later, default-off **reference-mask prototype** path: teacher = human Accept (or gold in observational spikes), features = DINOv2 patch tokens of sure-FG vs sure-BG, target matching = `sim_fg - sim_bg`, output = at most one coarse prompt into existing SAM decode.
- Keep DINO off the frozen v1 hot path and out of `build-segvision-v1`.
- First delivery is a CPU observational spike plus this change’s specs; GUI wiring waits on the spike go/no-go.

## Capabilities

### New Capabilities

- `dino-reference-prototype`: teacher trimap, DINOv2 patch prototypes, match/abstain, coarse prompt into SAM, provenance `sam_prototype` (later), never auto-Accept.

### Modified Capabilities

- None in v1. Desktop “Reuse last ROI” is unchanged and default-off.

## Impact

- New later change only. No DINO import in `src/segvision` until a follow-up task after spike evidence.
- Spike code lives under `benchmarks/` and writes an observational HTML report.
- Non-goals: ROI coordinate copy as the transfer mechanism, automatic Accept, cloned filler candidates, GUI tensor leak, v1 hot-path DINO, treating edge pixels as an appearance class.
