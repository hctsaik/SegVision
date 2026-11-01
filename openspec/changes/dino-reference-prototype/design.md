## Context

Human decision 2026-08-29 (supersedes Track A as the product goal): learn DINO patch FG/BG from the previous accepted mask, match on the next image, SAM for boundaries. Do not assume the defect stays at the same box.

Authoritative inputs: `PRD.md` (DINO is Later, not v1 In), `docs/one-shot-class-transfer-recommendation.md` Track D, frozen candidate cap 3, no auto-Accept, no default pixel OR.

Local eval artifacts already on the machine: `timm` DINOv2-small (`vit_small_patch14_dinov2.lvd142m`) in the Hugging Face cache; official MobileSAM vit_t for the SAM stage. Organizational redistribution of DINO/MobileSAM remains unapproved.

## Goals / Non-Goals

**Goals**

- Observational CPU spike: teacher mask → sure-FG/sure-BG patch prototypes → target margin map → abstain or one coarse box → MobileSAM multimask.
- Compare against gold on MVTec capsule scratch `000 → 002/003` (position shift, similar appearance).
- Fail closed if DINO weights are missing (no download in the spike when `HF_HUB_OFFLINE=1`).

**Non-Goals**

- Copying `user_roi_full` as the transfer mechanism.
- Putting DINO in `build-segvision-v1` GUI/session hot path.
- Auto-Accept, union of masks, filler candidates.
- Learning “edge pixels” as a class.
- Shipping DINO weights in the offline bundle.

## Decisions

1. **Spike before GUI.** Same rule as the one-shot memo. This change’s first executable is `benchmarks/capsule_scratch_dino_prototype.py`.
2. **DINOv2-small patch-14, CPU, 518 input.** Cached locally; CLS token dropped; L2-normalized patch tokens.
3. **Prototypes are mean sure-FG and mean sure-BG** for the first spike. Medoids are a later comparison, not the default.
4. **SAM still owns the edge.** DINO only proposes a box (crop + box prompt with 10% pad, same as v1 geometry intent).
5. **Abstain** if two large connected components have similar mass, or FG/BG token counts are too small.
6. **Provenance later:** `sam_prototype` must not masquerade as `sam_cv`. Not wired until spike go.

## Risks

- Thin scratches may still be a poor SAM box target even with a correct DINO region.
- Teacher gold is a proxy for Accept; scripted Accept must not become a production teacher.
- DINO license/package is a later gate; spike is local-only.
