## Why

SegVision currently has a frozen PRD and an implementation-ready architecture recommendation, but no executable behavioral contract that an AI coding agent can follow from a greenfield repository through a verified CPU-only release. This change converts those decisions into OpenSpec capabilities, deterministic acceptance gates, evidence requirements, and safe failure behavior so implementation can proceed autonomously without silently changing product scope.

## What Changes

- Add a typed annotation-session contract that owns revision, cached model state, candidates, undo, commit, and Needs Review outcomes.
- Add an exact full-image / user-ROI / padded-crop / model coordinate contract and full-image mask reconstruction behavior.
- Add the CPU interactive segmentation behavior: MobileSAM correctness baseline, encode-once SAM proposals, at most three candidates, previous-state refinement, safe prompt probes, warnings, and opt-in 2-of-3 fusion.
- Add immutable per-class CV recipe behavior with `invalid`, `coarse`, and `direct` gates.
- Add the desktop annotation state machine, local-edit fallback, keyboard workflow, stale-job rejection, validated Accept, and Needs Review separation.
- Add pair-consistent PNG + JSON sidecar persistence and reload validation.
- Add machine-verifiable functional, E2E, performance, quality, provenance, licensing, and offline-delivery gates.
- Add autonomous-delivery governance: ordered task execution, required evidence, retries, rollback rules, prohibited shortcuts, and explicit escalation conditions.
- Establish two release labels:
  - `engineering-accepted`: all deterministic and reference-machine gates pass;
  - `domain-validated`: representative real-scene data and independent annotation-quality gates also pass.
- Preserve VLM, DINO, SAM 2/3, HQ-SAM, multi-provider streaming, multi-class instances, video, and learned fusion as out-of-scope follow-up work.

## Capabilities

### New Capabilities

- `annotation-session`: Public in-memory engine/session behavior, candidate capabilities, revision safety, cache ownership, typed outcomes, and errors.
- `roi-geometry`: ROI padding, coordinate spaces, transform invariants, crop-resolution masks, and full-image commit geometry.
- `mask-proposal-engine`: CPU backend behavior, candidate generation/ranking, safe probes, previous-state refinement, uncertainty, and opt-in majority fusion.
- `fixed-cv-recipes`: Versioned class-bound CV recipes, deterministic processing, quality gates, direct candidates, and mask-prompt handoff.
- `annotation-workflow`: Desktop GUI behavior, state transitions, shortcuts, local editing, undo, validated Accept, failure fallback, and Needs Review.
- `annotation-persistence`: Accepted/review output schemas, pair-consistent publication, reload, integrity, and provenance.
- `acceptance-observability`: Event telemetry, deterministic E2E cases, performance and boundary-quality metrics, evidence bundles, and release classification.
- `offline-release`: CPU-only packaging, model/dependency manifests, license gates, clean-machine installation, and offline execution.
- `autonomous-delivery`: AI-agent task governance, checkpointing, test-first gates, retry/fallback policy, evidence recording, and bounded escalation.

### Modified Capabilities

<!-- Greenfield project: no deployed OpenSpec capabilities are modified. -->

## Impact

- Creates the initial behavioral source of truth under `openspec/changes/build-segvision-v1/specs/`.
- Governs the planned `src/segvision/`, `tests/`, `benchmarks/`, `models/`, `docs/`, and GUI implementation.
- Introduces Python, NumPy, OpenCV, PyTorch/MobileSAM, PySide6, test, benchmark, packaging, and license-manifest responsibilities, with versions pinned during implementation.
- Requires no GPU, hosted service, user account, or online runtime dependency.
- Does not authorize commercial use of a model or dependency whose license is not recorded as compatible.
- Does not allow an AI agent to claim domain validation without representative approved data and independently checkable ground truth.
