# SegVision Project Context

## Purpose

SegVision is a CPU-only Windows desktop tool and Python package for rapidly annotating one binary foreground object in a static image. A user draws an ROI, selects from no more than three candidates, refines a SAM-generated candidate with points, completes local pixel edits, and explicitly Accepts or sends the item to Needs Review.

## Current state

The repository is greenfield: product code has not yet been implemented. The active change is `build-segvision-v1`.

## Technology baseline

- CPython 3.11 x64 development baseline.
- NumPy boolean crop masks and uint8 RGB images.
- MobileSAM TinyViT + PyTorch CPU correctness backend.
- PySide6 thin GUI.
- Pytest-based unit, integration, E2E, GUI, model, and packaging gates.
- Full-image 0/255 PNG plus versioned JSON sidecar.

Exact patch versions are pinned and recorded during implementation.

## Non-negotiable constraints

- No local GPU requirement, hosted runtime, login, or network dependency.
- One selected foreground object per image in v1.
- ROI and padded crop are distinct.
- Non-direct SAM proposal encodes once per ROI revision; refinement is decoder-only.
- CV direct encodes zero times and does not support point refine.
- Candidate count is 0–3; no duplicate padding.
- Local edit prevents model calls until undo restores a model checkpoint.
- Accepted data and Needs Review are separate namespaces and eligibility states.
- Release evidence is required; synthetic evidence cannot satisfy domain validation.

## OpenSpec workflow

```text
proposal → specs + design → tasks → implementation → evidence → archive
```

Validate with:

```powershell
openspec validate build-segvision-v1 --strict --no-interactive
```

Archive only after every task checkbox, mandatory E2E case, evidence gate, and intended release classification is complete.
