# Spec review: `adopt-react-tauri-desktop`

Reviewer role: OpenSpec review only. Specs were subsequently patched to address the issues below; heading/`WHEN`/`THEN`/`SHALL` format is preserved.

Sources: `proposal.md`; `specs/desktop-protocol/spec.md`, `desktop-host/spec.md`, `desktop-ui/spec.md`, `desktop-sidecar/spec.md`, `desktop-parity-release/spec.md`; `docs/react-tauri-architecture-recommendation.md`; conformance targets `build-segvision-v1/specs/annotation-workflow/spec.md`, `annotation-session/spec.md`, `offline-release/spec.md`.

## Overall

The change correctly adds shell capabilities instead of rewriting UIW/OFR in place. Product-boundary prohibitions are repeated and aligned: no GPU/cloud/VLM, no auto-Accept, no more than three real candidates, no React-direct production sidecar, no packing MVTec, core stays headless, PySide6 stays default until hash-bound parity. Mask ownership is consistent where stated (Python session is authority; React/host/sidecar must not keep a second mask store).

The gaps that mattered were an unfinished protocol freeze: the frozen operation set could not carry the annotation-workflow loop, `sessions.create` collided with `IMAGE_OPEN` / `SegVisionEngine.start`, and error/recovery language was not one contract. Those gaps are addressed in the capability specs.

No OpenSpec format defects were found (every spec uses `## ADDED Requirements`, `### Requirement:`, `#### Scenario:`, `WHEN`/`THEN`, and `SHALL`/`MUST`).

## Issues

### Issue 1
- Severity: critical
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-protocol/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-ui/spec.md`; `openspec/changes/build-segvision-v1/specs/annotation-workflow/spec.md`; `openspec/changes/build-segvision-v1/specs/annotation-session/spec.md`
- Description:
  DTP-R002 freezes control operations as `health`, `datasets.open`, `datasets.list_items`, `sessions.create`, `sessions.get`, `sessions.propose`, `sessions.refine`, `sessions.edit`, `sessions.accept`, `sessions.needs_review`, `jobs.cancel`, and `assets.get`. Unknown operations MUST fail as `unsupported_operation`. That set cannot express the workflow the other specs already require:
  - Candidate **select** is a session mutation in SES-R005 and is named as a protocol request in DSS-R003-S02 and DSS-R007-S02. DUI-R009 says the displayed selected candidate MUST come from the Python snapshot; DUI-R010 maps `1`/`2`/`3` to selection. There is no `sessions.select`.
  - Session **undo** is required by UIW-R008 / DUI-R010 (`Z`). There is no `sessions.undo`.
  - **Manual-empty** fallback is required by UIW-R006 / SES-R010 / DUI-R015-S01. There is no `sessions.begin_manual_empty` (or equivalent).
  - Application-service **close** is required by DSS-R007; DPR-R010-S06 requires image-switch stale rejection. There is no `sessions.close`.
  - Expand ROI (`X`, UIW-R002) and crop-edge **warning acknowledgement** (SES-R011 / UIW-R010) have no frozen operation or accept-payload fields.
  Implementers must either invent operations (forbidden by DTP-R002-S04) or keep selection/undo/manual state in React (forbidden by DUI-R004/R009 and SES ownership).
- Suggestion:
  Extend the frozen 1.0 operation set (or explicitly map each missing call onto an existing operation plus required DTO fields) so select, undo, manual-empty, session close/image-switch, Expand ROI, and Accept acknowledgements are addressable without a second state owner.
- Status: addressed
- Response: DTP-R002 now freezes `sessions.select`, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.close`, `sessions.lock_roi`, `sessions.expand_roi`, and `sessions.acknowledge_warning`; sidecar/UI specs invoke those operations instead of React-owned select/undo/manual state.

### Issue 2
- Severity: critical
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-protocol/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-ui/spec.md`; `openspec/changes/build-segvision-v1/specs/annotation-session/spec.md`; `openspec/changes/build-segvision-v1/specs/annotation-workflow/spec.md`
- Description:
  Three session-creation stories cannot all be true:
  1. DUI-R001 / UIW-R001 require public state `IMAGE_OPEN` before ROI lock; UIW-R013 forbids Needs Review there because no ROI/revision geometry exists.
  2. SES-R001 says `SegVisionEngine.start(...)` is the only public session factory, requires a valid full-image ROI, and creates revision `1`.
  3. DTP-R003-S03 / DSS-R007-S01 say `sessions.create` has no `session_id`, sends `base_revision` `0`, loads the image through the existing engine API, and returns revision `1` when start succeeds.
  If `sessions.create` is `engine.start`, `IMAGE_OPEN` never exists on the authoritative snapshot. If `sessions.create` is an image-open desktop session without ROI, it must not call `start` or return core revision `1`, and a later ROI lock needs a distinct mutation that actually starts the engine. The specs currently conflate protocol session identity with core session identity.
- Suggestion:
  Freeze a two-phase mapping: protocol session MAY exist in `IMAGE_OPEN` without core `start`; ROI lock is the only call that invokes `SegVisionEngine.start` and mints revision `1`. Or drop `IMAGE_OPEN` from desktop snapshots (not allowed while DUI-R001 claims UIW conformance). Do not return core revision `1` from create unless ROI+`start` actually ran.
- Status: addressed
- Response: DTP-R013/DTP-R003-S03/DSS-R007-S01 freeze `sessions.create` as `IMAGE_OPEN` at protocol revision `0` with no `SegVisionEngine.start`; `sessions.lock_roi` is the only `start` call and mints core revision `1`.

### Issue 3
- Severity: major
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-protocol/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-host/spec.md`
- Description:
  DTP-R010 freezes exactly eight UI error codes and says the response `code` SHALL be one of those eight, not an ad-hoc string. DSS-R004 requires mapping `InvalidRoi`, `RecipeSchemaError`, `RecipeClassMismatch`, `EmbeddingExpired`, `StaleRevision`, `BackendUnavailable`, and `UnsupportedOperation` to stable codes **and** distinguishing those from `revision_conflict` and request-schema failures. `StaleRevision` has no frozen protocol code; collapsing it into `revision_conflict` violates DSS-R004, while inventing a ninth code violates DTP-R010. DTH-R013 / DTH-R006 add further “stable” host filesystem and grant codes that are also outside the eight. Integrity/license/dataset-open failures in DSS-R016/R018 are similarly unnamed in the frozen set.
- Suggestion:
  Publish one error catalog (protocol + host) with an explicit map from core exception types to `code` values. If the eight codes stay exhaustive, document the many-to-one mapping (`StaleRevision` → `stale_job`, `InvalidRoi` → `validation_failed`, checksum/missing model → `engine_unavailable`, unknown grant → `not_found`/`unauthorized`, etc.) so DSS-R004 “corresponding” is not read as 1:1.
- Status: addressed
- Response: DTP-R016 and DSS-R004 keep the eight sidecar JSON codes and define the many-to-one map; host `grant_invalid`/`filesystem_error` stay host-stable wrappers, not extra sidecar codes.

### Issue 4
- Severity: major
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-protocol/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`
- Description:
  DTP-R003 requires `base_revision` on mutations that target session **or job** state. DTP-R004 exempts `jobs.cancel`: cancellation MUST still be attempted for a job of that `session_id` even after the session revision has advanced. DSS-R002-S04 is unqualified: any mutation whose `base_revision` is less than the current session revision MUST return `revision_conflict` and MUST NOT apply. A cancel sent with the job’s original revision after an ROI bump is therefore both required to proceed (DTP-R004) and required to fail closed (DSS-R002).
- Suggestion:
  State that `jobs.cancel` is job-scoped, MUST carry `session_id` + `job_id`, MUST NOT be subject to `revision_conflict`, and that DSS-R002-S04 applies only to snapshot-mutating operations (propose/refine/edit/accept/review/select/undo/ROI).
- Status: addressed
- Response: DTP-R004/R011 and DSS-R002-S04/S06 make `jobs.cancel` job-scoped (`session_id`+`job_id`), still attempted after revision advance, and not `revision_conflict` solely because `base_revision` is old.

### Issue 5
- Severity: major
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-host/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-ui/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-parity-release/spec.md`
- Description:
  Crash recovery is not one behavior:
  - DTH-R004 / DSS-R015 / DUI-R012: process restart discards in-memory sessions; host MAY auto-restart and re-handshake; restore is **MAY** and only for loader-verified persisted drafts; otherwise **MUST** require a new session; do not rebuild from React pixels.
  - DPR-R007-S04: host SHALL “refuse silent unconditional restart without recovery state” **and** recovered state SHALL restore the last durable draft or published result.
  - DPR-R010-S07: UI SHALL re-handshake **and restore** durable draft or published output (no “else new session” branch).
  “Refuse unconditional restart” can be read as forbidding the auto-restart DTH-R004 describes. “SHALL restore” conflicts with DSS/DTH/DUI “MAY restore, else new session.”
- Suggestion:
  Freeze the sequence: detect crash → `engine_unavailable/recovering` → freeze mutations → keep display pixels as non-authoritative → auto-restart process with new port/secret → handshake → restore iff persistence verifies a draft/published pair for the current image identity → else require `sessions.create`. Replace DPR SHALL-restore with that conditional. Define “unconditional restart” as “restart and assume live session memory,” not “do not respawn the process.”
- Status: addressed
- Response: DTH-R004, DSS-R015, DUI-R012, DPR-R007-S04, and DPR-R010-S07 now share that crash→recovering→freeze→non-authoritative pixels→optional auto-respawn→handshake→conditional restore sequence, and define unconditional restart as assuming in-memory session survival.

### Issue 6
- Severity: major
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-protocol/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`; `docs/react-tauri-architecture-recommendation.md`
- Description:
  Architecture §7 and §17 said the protocol envelope, snapshot, health/capability payload, and binary plane must be frozen before implementation. Current freeze is partial:
  - Mutation envelope fields are named, but `health` / `sessions.get` / `assets.get` still have no required carriage for `protocol_version` (header vs body vs query). GET-with-JSON is unspecified.
  - `sessions.get` snapshot is not a field contract. DSS-R007-S04 lists revision, selected candidate id, capabilities, warnings, and job summary; it does not require workflow state (`IMAGE_OPEN`…), asset tokens, `user_roi_full` / `crop_rect_full`, timer origin, `class_id`, or candidate capability flags that DUI-R001/R009 must project.
  - Data-plane bytes are “binary” only. Architecture §7.3 required display masks as PNG `{0,255}` (RLE/bit-pack later). Without that, React, host, and sidecar can disagree on raster interpretation while still passing “not JSON/base64.”
  - `health` success is only required to echo `protocol_version` `"1.0"`. Readiness, approved-backend presence, and diagnostic setup (DPR-R010-S08 / DTH-R020) have no health DTO.
- Suggestion:
  Add a 1.0 snapshot schema (including UIW state and asset tokens), a health/readiness schema, an explicit version-carriage rule for every plane, and a mask/image media type (`image/png` with `{0,255}` masks unless a later version). Leave HTTP paths and library versions out of SHALL text.
- Status: addressed
- Response: DTP-R001/R003/R007/R014/R015 freeze version carriage on every control request including reads, the `sessions.get` 1.0 snapshot fields, health/readiness/diagnostic payload, and explicit PNG `{0,255}` mask plus stored image media types.

### Issue 7
- Severity: major
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-protocol/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-host/spec.md`; `docs/react-tauri-architecture-recommendation.md`
- Description:
  Control-plane hop is frozen (React typed command → Tauri → Rust HTTP → localhost sidecar). Event-plane hop is not. DTP-R005 freezes envelope and kinds; DTH-R018 says the host “receives sidecar job and session events” and forwards typed Tauri events. Architecture §7.2 required Python → Tauri → React, but 1.0 does not say whether that is sidecar-push (SSE/WebSocket), host-pull, or a localhost callback. Shared memory is correctly out of scope (DTP-R012); the non-shared-memory event channel still needs a fail-closed choice so contract tests have an oracle.
- Suggestion:
  Freeze one production event transport (for example host-owned HTTP callback or SSE on loopback with the per-launch secret) and forbid React-direct event URLs. Keep the mechanism name in the protocol spec; keep frame layout in OpenAPI/JSON Schema.
- Status: addressed
- Response: DTP-R005 and DTH-R018 freeze production events as host-owned loopback SSE or equivalent host-only HTTP with the per-launch secret; Tauri forwards typed events and React MUST NOT subscribe to sidecar event URLs.

### Issue 8
- Severity: major
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-host/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-ui/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-protocol/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`; `openspec/changes/build-segvision-v1/specs/annotation-session/spec.md`
- Description:
  Grant flow for **dataset open** is consistent (picker → opaque `grant_id` + display name → host resolves canonical path → sidecar). Two related contracts are missing:
  - DUI-R004 says output location uses host grants, and DPR-R010-S09 / DTH-R013 require read-only output failures, but no frozen operation or grant type binds an output folder. Persistence can only work if the sidecar already knows a path from config, which React is forbidden to supply as a raw path.
  - SES-R001 requires `class_id` (and optional recipe) at `start`. No desktop operation or snapshot field binds class/recipe from a dataset item to session create/ROI lock (DSS-R008-S02 mentions recipe bind without a wire operation).
- Suggestion:
  Add host grant kinds `dataset` and `output` (and optionally `checkpoint` as non-approving), plus protocol fields that pass `grant_id` only. Require `class_id` / recipe identity on session start/ROI lock DTOs, sourced from dataset metadata rather than React-invented tensors.
- Status: addressed
- Response: DTH-R006/DTP-R017 freeze grant kinds `dataset`, `output`, and optional non-approving `checkpoint` with `grant_id` only; `sessions.lock_roi` MUST carry `class_id` (and recipe identity if present) from dataset metadata.

### Issue 9
- Severity: minor
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-parity-release/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-host/spec.md`
- Description:
  Behavioral SHALLs include repository layout and library/tool names that `openspec/AGENTS.md` says belong in `design.md`/`tasks.md`: sidecar code MUST live under `src/segvision/application/` and `src/segvision/transport/desktop_api/` (DSS-R001/R009); FastAPI/Starlette is named as an allowed ASGI stack (DSS-R006); DPR-R008 requires Vitest and Testing Library by name. Tauri 2 as host is an architecture ADR and is acceptable; directory dumps and test-runner brands are over-implementation.
- Suggestion:
  Keep “application + transport adapter, not a core fork” and “contract tests plus React component tests” as behavior; move exact paths and framework names to design/tasks.
- Status: addressed
- Response: DSS-R001/R006/R009 and DPR-R008 keep adapter-not-core-fork and contract-plus-component-test behavior and no longer MUST-require exact repo paths or Vitest as the only runner.

### Issue 10
- Severity: minor
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-sidecar/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-host/spec.md`
- Description:
  DSS-R018 says the sidecar consumes a “host-authorized grant path” and scenarios mix “grant” with filesystem existence checks. DTH-R006 says only the host stores the canonical path and React never sees it; the sidecar receives the resolved path from the host, not a `grant_id`. Readers can implement a React-supplied path or a sidecar grant table and still claim compliance.
- Suggestion:
  One sentence in both specs: React sends `grant_id` only; host resolves to a canonical path; sidecar receives that path from the host process, never from the WebView, and then applies existence/manifest/hash checks.
- Status: addressed
- Response: DTH-R006 and DSS-R018 now use the same sentence: React sends `grant_id` only; host resolves canonical path; sidecar receives the path from the host process, never from the WebView, then existence/manifest/hash checks.

### Issue 11
- Severity: minor
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-parity-release/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-ui/spec.md`; `docs/react-tauri-architecture-recommendation.md`
- Description:
  DPR-R010-S01 requires opening a local dataset and displaying “the overlay” with an overlay mask hash, matching architecture’s read-only viewer (gold/source overlay). Annotation overlay in DUI-R014 is composed from session mask assets after a revision exists. The E2E case does not say whether the first overlay is dataset gold, empty annotation, or either. That can pass a viewer-stage hash against the wrong plane.
- Suggestion:
  Split or label the case: dataset gold overlay (viewer stage) vs authoritative session-mask overlay (annotation stage), each with its own hash oracle.
- Status: addressed
- Response: DPR-R010-S01 is the viewer gold/source overlay hash; DPR-R010-S11 is the annotation session-mask overlay hash, each with its own oracle.

### Issue 12
- Severity: nit
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-ui/spec.md`; `openspec/changes/build-segvision-v1/specs/annotation-workflow/spec.md`
- Description:
  DUI-R001 incorporates UIW by reference, which covers timer origin (`first_roi_locked`) and distinguishing `user_roi_full` from `crop_rect_full`. DUI never restates those as desktop-canvas requirements, while it does restate shortcuts, candidate cardinality, and overlay composition. Easy to implement a timer that resets on ROI redraw or a single rectangle that is both user ROI and work crop.
- Suggestion:
  Add one UI scenario each: timer continues across ROI redraw/Expand; displayed user box vs padded crop use the same half-open full-image values the session reports.
- Status: addressed
- Response: DUI-R001-S04 freezes timer origin `first_roi_locked` across ROI redraw/Expand; DUI-R007-S04 displays `user_roi_full` vs `crop_rect_full` as session-reported half-open full-image XYXY.

### Issue 13
- Severity: nit
- Specs: `openspec/changes/adopt-react-tauri-desktop/specs/desktop-protocol/spec.md`; `openspec/changes/adopt-react-tauri-desktop/specs/desktop-host/spec.md`
- Description:
  DTP-R003-S04 says only `health` and `sessions.get` MUST NOT increment revision. `datasets.list_items` and `assets.get` are also reads and are omitted. DTH-R017 typed allowlist is not explicitly the DTP-R002 frozen set, so extra host commands could appear without a protocol change.
- Suggestion:
  State that no read/list/asset-get increments revision, and that the production Tauri command allowlist is exactly the frozen operation set plus host-only window/grant/log/export commands named in desktop-host.
- Status: addressed
- Response: DTP-R003-S04 states that `health`, `sessions.get`, `datasets.list_items`, and `assets.get` do not increment revision; DTH-R008/R017 freeze the production allowlist as those protocol operations plus named host-only window/grant/log/export commands.

## Product-boundary check

No spec authorizes GPU, cloud inference, auto-Accept, more than three candidates, cloned filler cards, React-direct production sidecar access, packing MVTec, or a core rewrite. Those bans are present in protocol, host, UI, sidecar, and parity-release. The practical boundary risk in Issues 1–2 (a React- or adapter-owned session filling missing operations) is closed by the extended frozen operation set and two-phase `sessions.create` / `sessions.lock_roi` mapping.

## Architecture freeze coverage

| Intended freeze (architecture §7 / §17) | Status in this change |
| --- | --- |
| ADR-001 React/Vite + Tauri 2 + Python sidecar | Present (proposal, host, UI, sidecar) |
| ADR-002 React does not talk to sidecar in production | Present (DTH-R001/R015, DSS-R005/R006, DPR-R020) |
| ADR-003 Python session + revision concurrency | Present (two-phase create/`lock_roi`; select/undo/close/expand/ack in DTP-R002) |
| ADR-004 binary asset plane, no base64 JSON | Present; PNG `{0,255}` masks and explicit media types frozen (Issue 6 addressed) |
| ADR-005 one-folder sidecar; models separate verified component | Present (DPR-R013/R014) |
| ADR-006 Canvas2D default; shared memory out of 1.0 | Present (DUI-R006, DTP-R012) |
| ADR-007 PySide6 remains until parity; no removal in this change | Present (DPR-R001–R003, R019) |
| ADR-008 dedicated app, no portal/iframe/plugin | Present (DUI-R002, DTH-R014, DPR-R020) |
| CORS off in production; exact-origin dev only | Present |
| Grant flow | Dataset, output, and optional non-approving checkpoint grants; `class_id` on `lock_roi` (Issue 8 addressed) |
| Control-plane hop | Present |
| Event-plane hop | Host-owned loopback SSE or equivalent host-only HTTP; React MUST NOT subscribe directly (Issue 7 addressed) |

## Counts

| Severity | Count |
| --- | --- |
| critical | 0 open / 2 addressed |
| major | 0 open / 6 addressed |
| minor | 0 open / 3 addressed |
| nit | 0 open / 2 addressed |
| **total open** | **0** |
| **total addressed** | **13** |

Validate-breaking format defects: 0.
