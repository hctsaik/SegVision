## Context

SegVision is a greenfield Windows desktop annotation tool for static images. The frozen v1 product contract is CPU-only, one binary foreground per image, a user-defined ROI, no more than three machine candidates, previous-state point refinement, local pixel editing, explicit Accept or Needs Review, and full-image PNG plus JSON provenance.

The repository currently contains requirements and strategy documents but no product source code, test harness, representative dataset, approved model artifact, or release package. The implementation must therefore begin with contracts and deterministic fakes, then add a real model without allowing model availability to block core development.

The user wants an AI coding agent to execute the project end to end. This design makes every engineering gate machine-verifiable and supplies deterministic defaults. It also distinguishes engineering completion from claims that require evidence an AI cannot fabricate, such as independent domain annotation quality or commercial-license approval.

Authoritative inputs, in descending priority, are:

1. `PRD.md` frozen decisions;
2. this OpenSpec change and its capability specs;
3. `docs/final-development-recommendation.md`;
4. research material in `docs/SAM-assisted-annotation-strategy.md`.

## Goals / Non-Goals

**Goals:**

- Deliver an importable Python common package and a thin Windows desktop GUI.
- Make core behavior deterministic, typed, headless-testable, and independent of filesystem and GUI code.
- Implement a MobileSAM TinyViT + PyTorch CPU correctness backend behind a narrow protocol.
- Guarantee geometry, revision, cache, candidate, refinement, local-edit, persistence, and provenance invariants with automated tests.
- Make E2E functional acceptance runnable without a human by using fake, synthetic, replay, and fixed real-model fixtures.
- Produce a reference-CPU benchmark and a signed-off evidence bundle for every release candidate.
- Allow an AI agent to progress without asking preference questions when a documented default or safe fallback exists.
- Stop honestly, with a machine-readable blocker, when a required external asset or authority is absent.

**Non-Goals:**

- VLM/text prompts, DINO/TokenCut, SAM 2/3, HQ-SAM, FocalClick, multi-provider races, video, or multi-instance annotation.
- Automatic acceptance of any mask.
- Per-image color-threshold tuning.
- GPU, cloud inference, account login, or online runtime dependencies.
- Treating synthetic fixtures as proof of real-domain annotation quality.
- Bypassing model, checkpoint, dependency, or redistribution licenses.
- Maintaining both PyTorch and ONNX as required production runtimes in v1.

## Decisions

### 1. Two explicit release classifications

The repository uses two cumulative completion labels:

- `engineering-accepted`: deterministic functional, integration, scripted E2E, reference-CPU, persistence, clean-machine, security, and license-manifest gates pass.
- `domain-validated`: `engineering-accepted` plus representative approved images, independent gold masks, boundary-quality gates, and real annotator workflow evidence pass.

An agent may complete and publish an `engineering-accepted` release candidate autonomously. It MUST NOT call that candidate `domain-validated` when representative data, gold truth, annotator evidence, or required legal approval is missing.

Labels, a run verdict, and project state are separate axes. `domain-validated` implies `engineering-accepted`. Each run declares `target_release_class=engineering|domain`. Missing Tier C input does not block an engineering-target run; for a domain-target run whose engineering gates already pass, the candidate retains `engineering_accepted=true`, receives `BLOCKED_EXTERNAL_INPUT`, and uses project state `implementation_complete_release_blocked` until the promotion input exists.

Alternative considered: one release flag. Rejected because it would encourage synthetic tests to be misrepresented as product validation.

### 2. Deterministic defaults replace preference questions

Unless repository-owned configuration overrides them, the agent uses these defaults:

- OS/runtime target: Windows x64, CPU-only.
- Development Python: CPython 3.11 x64; exact patch and dependency versions are locked in the repository.
- Common package layout: `src/segvision`.
- Unit/integration runner: `python -m pytest`.
- GUI: PySide6, isolated from core.
- Correctness model: MobileSAM TinyViT + PyTorch CPU from an official, pinned source and checksum-verified checkpoint.
- ROI padding: `0.10` on each dimension before clamping.
- Public rectangles: full-image half-open XYXY.
- Candidate mask: crop-resolution `numpy.bool_`.
- Initial candidate maximum: three; no duplicate padding.
- Local morphology default: zero-radius/no-op until explicitly invoked.
- Fusion: pure vote-count `>=2`, GUI default off, uncertainty at vote count `==1`.
- Annotation policy: visible pixels only; do not hallucinate occluded regions; include visible disconnected pieces of the selected object; exclude cast shadows and reflections; retain visible holes; clip at image boundary and record truncation.

Changing a default that alters public behavior requires a new OpenSpec change. Runtime measurements and exact dependency patch versions may be updated as evidence without changing behavioral requirements.

### 3. Layered package architecture

```text
GUI/controller ───────┐
                      ├──> core engine/session ──> backend protocol
storage adapter ──────┘              │
                                     └──> pure CV/mask/geometry functions
```

Planned layout:

```text
src/segvision/
  core/
    api.py
    types.py
    geometry.py
    candidate_policy.py
    mask_ops.py
    recipe.py
  runtime/
    embedding_cache.py
    jobs.py
  providers/
    base.py
    fake.py
    mobile_sam_torch_cpu.py
  cv/
    fixed_recipe.py
  adapters/
    png_sidecar.py
  gui/
    controller.py
    canvas.py
    panels.py
tests/
benchmarks/
models/
evidence/
```

Core accepts in-memory values only. It never opens paths, writes files, downloads models, imports GUI modules, or uses a hidden process-global model/session singleton.

Alternative considered: put model state and save behavior directly in the GUI. Rejected because it prevents headless testing and makes stale-result safety unverifiable.

### 4. Session-owned opaque model state

`SegVisionEngine.start(...)` creates an `AnnotationSession`. The session owns:

- immutable image identity and pixels;
- current ROI/crop context and monotonically increasing revision;
- encoded crop state;
- candidate graph and generator provenance;
- prompt history and provider-specific previous mask state;
- undo checkpoints;
- timing events and final outcome.

GUI code passes candidate IDs and full-image prompts, never embedding tensors, low-resolution logits, ONNX names, normalization details, or model input shapes.

Candidate capabilities are explicit:

```text
SAM candidate      can_refine=true,  can_local_edit=true
CV direct candidate can_refine=false, can_local_edit=true
manual candidate   can_refine=false, can_local_edit=true
```

v1 does not lazy-encode a CV-direct candidate. To obtain SAM point refinement, a new revision must run a SAM proposal path.

### 5. Geometry is a first-class contract

The system distinguishes:

- `user_roi_full`: user box and SAM box prompt;
- `crop_rect_full`: 10% padded, clamped work crop;
- crop coordinates;
- backend-owned model coordinates.

All public points are full-image XY. Rectangles are half-open. The backend owns resize, normalization, pad, prompt transforms, and mask-state conversion. Candidate masks remain at source crop resolution. Only commit creates a full-image mask.

Touching the padded crop boundary is a truncation warning. Touching the user ROI is not inherently erroneous.

### 6. CPU backend strategy

MobileSAM TinyViT + PyTorch CPU is implemented first as the correctness backend. This choice is based on its compatible interactive SAM API and permissive repository license, not an unverified performance claim.

The model adapter supports:

- crop encode;
- box and point prompts;
- native multimask output;
- provider-specific score and stability metadata;
- previous mask-state refinement;
- binary coarse mask to provider mask input;
- explicit release.

Standard MobileSAM preprocessing remains fixed around its expected encoder input; ROI improves target occupancy and isolation but is not assumed to reduce encoder FLOPs linearly. The benchmark records observed latency instead of deriving it from ROI area.

EdgeSAM is excluded from commercial shipping until written permission exists. Full MobileSAM ONNX is not a v1 promise because the official export path does not establish a complete validated TinyViT encoder deployment.

### 7. Proposal and refinement policy

For non-direct proposals, one crop/revision performs one encoder call. Box-only native multimask candidates are the baseline. Empty, nearly full, prompt-violating, or effectively duplicate candidates are removed; missing slots are not fabricated.

An optional safe-grid probe may run only after box candidates exist. It takes at most two points from an eroded stable intersection. It adds decoder calls, never encoder calls. It is omitted when no stable interior exists and is discarded after the first human point.

Point refinement is allowed only for SAM-generated candidates. It preserves the original box, accumulated human points, and selected candidate previous state, requests a single result, and adds zero encoder calls.

The candidate ranking layer uses validation filters, provider-local metrics, stability, duplicate distance, and warnings. It does not expose a fabricated cross-provider confidence.

### 8. Fixed CV recipes run before optional model encoding

An enabled, immutable class recipe runs immediately after crop creation:

```text
invalid/off → normal SAM box proposal
coarse     → encode once, then coarse mask as provider mask prompt → sam_cv
direct     → cv_direct candidate, zero encoder calls
```

The raw coarse mask never occupies a displayed candidate slot. `sam_cv` may replace one slot, so the GUI still displays no more than three candidates. A direct candidate still requires explicit human Accept.

### 9. Local edit is a terminal model lock

The first brush, erase, grow, shrink, or fill operation creates a manual candidate and disables model calls. Undo restores the exact prior checkpoint; only after undo to a SAM checkpoint can point refinement resume. No model/manual pixel merge algorithm is implemented in v1.

### 10. GUI uses a cancellable state machine

Inference executes in one background process with bounded threads. Jobs carry session and revision IDs. ROI change or session close cancels work when possible; otherwise a completed stale result is discarded before entering GUI state.

The GUI exposes one selected mask, no more than three cards, disagreement/crop-edge uncertainty, recipe status, timer, ROI, points, local-edit tools, Accept, and Needs Review. It disables point tools for non-refinable candidates.

Accept follows `attempt → validate crop candidate → commit full mask → validate full result → save pair → accepted`. Validation or save failure keeps the session open. Needs Review is available from every non-accepted annotation state.

### 11. Pair-consistent persistence

The adapter writes PNG and sidecar to unique temporary files, flushes and validates them, publishes a new versioned or content-addressed PNG without replacing any PNG referenced by an existing sidecar, and atomically replaces only the sidecar pointer last as the commit marker. A loader accepts an annotation only when the sidecar is accepted, the referenced PNG exists, and filename/hash/schema/shape agree.

This is not a claim that two filesystem renames are a single atomic operation. It is a reader-visible transaction protocol that prevents partial pairs from being interpreted as accepted data.

Needs Review metadata and optional drafts live outside the accepted training namespace and always declare `training_eligible=false`.

### 12. Acceptance is evidence-driven

Acceptance uses three tiers:

- Tier A, deterministic CI: contracts, geometry, fake backend, candidate policy, CV, state machine, persistence, CLI, and scripted GUI tests.
- Tier B, reference CPU: real model fixtures, latency distributions, peak RAM, UI responsiveness, clean-machine offline launch, and scripted end-to-end time.
- Tier C, domain validation: approved representative new scenes, independent gold masks, boundary metrics, and real annotator outcomes.

Every gate produces structured evidence under `evidence/<run-id>/`. The run manifest records source revision, dirty-state hash, OS, CPU, RAM, Python, dependency lock hash, model/checkpoint hash, recipe hashes, commands, exit codes, timings, metric results, logs, and artifact hashes.

### 13. Autonomous agent control loop

The implementation agent follows this loop for each task:

```text
read pending task and referenced requirements
→ inspect existing files and tests
→ create/update focused tests
→ implement smallest compliant change
→ run focused gate
→ run affected regression gate
→ record evidence
→ update docs and mark task complete only when evidence passes
→ checkpoint
```

The agent may retry a deterministic failure up to three materially different attempts. After that it records a blocker. It may not weaken a threshold, skip a required test, relabel failure, switch to GPU/cloud, introduce an excluded model, or fabricate external approval to make a gate pass.

### 14. Escalation is bounded and machine-readable

Engineering work does not pause for preferences already covered by defaults. An agent stops only when all safe in-scope alternatives are exhausted and one of these applies:

- destructive or irreversible action outside generated build/test artifacts;
- missing commercial-use or redistribution authority;
- unavailable required external checkpoint after verified official-source retries;
- representative domain data or gold truth required to claim `domain-validated`;
- a frozen PRD/OpenSpec contradiction that changes public behavior;
- physical target hardware cannot meet a hard release threshold after measured optimization attempts;
- security/privacy constraints forbid using the available data.

The blocker artifact contains `task_id`, `gate_id`, observed evidence, attempts, safe alternatives tried, exact missing authority/input, and the earliest task that can continue once resolved.

## Risks / Trade-offs

- **[Fixed 1024 preprocessing may be slower than expected]** → Benchmark on the recorded target CPU; keep one backend; preserve manual fallback; do not claim ROI-area speedups.
- **[Model checkpoint availability or license differs from repository code]** → Treat code and weights as separate manifest entries; verify checksum and redistribution terms before packaging.
- **[Synthetic E2E fixtures overstate real-scene quality]** → Separate engineering acceptance from domain validation; never substitute synthetic masks for Tier C evidence.
- **[GUI tests are flaky]** → Use deterministic fake backend, off-screen rendering where supported, event-loop condition waits instead of sleeps, screenshots on failure, and fixed input fixtures.
- **[Wall-clock CI is noisy]** → Keep functional tests in shared CI and run hard performance gates only on a fingerprinted reference machine.
- **[CPU thread oversubscription freezes UI]** → Run inference in one process, pin configurable Torch/OpenCV/BLAS thread limits, and measure input-to-frame latency.
- **[Candidate score semantics differ]** → Keep metrics provider-local and record score kind; rank with explicit policy instead of a false unified confidence.
- **[Save interruption leaves orphan files]** → Publish sidecar last, validate hashes on load, quarantine or clean temporary/orphan artifacts, and keep the live session on failure.
- **[Agent optimizes for passing tests rather than behavior]** → Require traceability from spec scenario to test ID and evidence; mutation/negative cases cover prohibited shortcuts.
- **[Long specification becomes inconsistent]** → `openspec validate --strict`, requirement-ID mapping, generated acceptance manifest validation, and multi-agent review are mandatory gates.

## Migration Plan

1. Establish project scaffold, contracts, fake backend, tests, and evidence tooling without downloading a model.
2. Implement and benchmark the MobileSAM CPU backend using a pinned official source and verified checkpoint.
3. Add candidate/refinement/local-edit/session behavior and pass headless integration gates.
4. Add background runtime, thin GUI, scripted E2E workflow, persistence, and reload.
5. Add fixed CV recipes and class-specific gates.
6. Produce the reference-machine evidence bundle and clean-machine offline package.
7. Complete M4 and tag an `engineering-accepted` release candidate after all Tier A/B gates pass.
8. For a domain-target run, execute optional M5 when approved representative data and independent review are available and promote the same or a newer traceable candidate to `domain-validated`.

Rollback is source-level and artifact-level: revert only the failing task checkpoint, retain prior evidence bundles, invalidate newer manifests, and never overwrite accepted annotation data during tests.

## Open Questions

No unresolved preference blocks M1–M4 engineering work; the defaults above are normative for this change.

The following are external promotion inputs rather than implementation questions:

- Which approved real-scene dataset and independent gold masks will be used for Tier C?
- Which organization/person supplies final commercial redistribution approval for model weights and GUI/runtime dependencies?
- Which physical machine is designated as the release reference CPU if it differs from the autonomous agent host?

If these inputs are absent, the agent completes and reports `engineering-accepted` when eligible, and leaves `domain-validated=false` without asking to weaken the gate.
