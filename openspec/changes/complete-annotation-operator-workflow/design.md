## Context

SegVision currently keeps authoritative annotation state in the Python session, projects it through the desktop sidecar, and renders JSON snapshots plus opaque image assets in React. Accepted and Needs Review outcomes are durable, but ordinary editable work is not a resumable artifact. React exposes Undo but not Redo, the host has a job-cancel API without an operator control, LabelMe conversion is CLI-only, and dataset items do not carry persisted workflow status.

This change crosses core session history, persistence, sidecar protocol, Tauri process supervision, React interaction state, dataset indexing, interchange, packaging, and native E2E. The existing constraints remain: CPU-only MobileSAM, exact protocol matching, no raw paths or launch secrets in React, no full-mask JSON transfer, no automatic Accept, no network dependency, and accepted PNG + sidecar as the lossless source of truth.

The change is sequenced after the current v1 engineering baseline. It introduces exact-match desktop protocol `1.1`; protocol `1.0` remains frozen and is not silently extended.

## Goals / Non-Goals

**Goals:**

- Preserve every completed operator action in a loader-verified editable draft and recover it after App or sidecar failure.
- Prevent accidental loss on image switch, dataset switch, close, engine restart, or update.
- Give the operator explicit cancel, retry, recovery, and redacted diagnostic controls.
- Make Undo, Redo, prompt adjustment, and operation history session-authoritative and deterministic.
- Complete LabelMe export/import inside the Native App with a visible polygon-cleanup preview.
- Provide dataset statuses, next-unfinished navigation, deterministic QA, project labels, and signed offline update handling.
- Keep every new workflow machine-verifiable through native E2E and persistence/hash oracles.

**Non-Goals:**

- GPU, cloud inference, a second model provider, SAM 2/3, HQ-SAM, VLM, or automatic Accept.
- Replacing accepted binary PNG + JSON sidecar with polygons.
- Multi-user collaboration, cloud sync, accounts, or automatic diagnostic upload.
- Treating draft, imported LabelMe, or QA acknowledgement as an Accepted annotation.
- Supporting arbitrary LabelMe shape types in the first round-trip release.

## Decisions

### 1. Python owns a bounded checkpoint journal

Every completed mutation produces one immutable session checkpoint and one operation record. The session owns `past`, `current`, and `future` stacks; Undo moves current to future, Redo moves future to past, and any new mutation clears future. A checkpoint stores references or compact deltas where safe, but its externally persisted representation is a complete logical snapshot with hashes.

React never owns mask history. Undo and Redo make no encoder or decoder calls. Prompt move/relabel is the exception to no model work during history creation: it atomically replays the ordered prompt set through the existing cached embedding with zero encoder calls and records one checkpoint only after success.

Alternatives considered:

- React-local history was rejected because it diverges from sidecar revision and cannot survive a crash.
- Persisting only stroke deltas was rejected as the recovery source because replay across protocol/model versions is fragile; deltas remain provenance, while a validated logical snapshot is the restore source.

### 2. Drafts use an isolated, atomic namespace

Editable drafts are written by the Python persistence adapter under a dedicated draft namespace. They never appear in AcceptedStore or the training loader. Each draft contains source-image fingerprint, project/dataset/item identity, protocol version, class ID, ROI/crop geometry, active mask token or PNG, locked foreground/background regions, ordered prompts, operation history, revision, model identity, and content hashes.

Autosave occurs after pointer-up or another completed mutation and is coalesced so at most one write is active per session. A sidecar-last atomic publication marks a valid checkpoint. Interrupted temporary files are ignored. Startup restore requires schema, checksum, source-image fingerprint, protocol compatibility, and class identity to pass.

Alternatives considered:

- Browser storage was rejected because it would expose authoritative state to the WebView and cannot provide pair consistency.
- Reusing Needs Review was rejected because review is a terminal human outcome, while a draft is resumable non-terminal work.

### 3. Dirty-state decisions are explicit and host-enforced

The snapshot exposes draft/dirty status but no filesystem path. Image switch, dataset switch, window close, sidecar restart, and update request enter a pending navigation state. React presents `save draft`, `discard`, and `cancel`; for native window close, Tauri prevents close until the sidecar confirms flush/discard or the operator cancels.

Discard removes only the exact draft artifact for the current dataset/item after resolving the opaque grant in the host. Accepted and review artifacts are never deleted by discard.

### 4. Protocol 1.1 is additive but exact-match

Protocol `1.1` adds typed operations for redo, prompt update, draft flush/load/discard, dataset work status, QA issue projection, LabelMe preview/export/import, engine restart, and redacted diagnostics. The existing eight public error-code families remain; new failure details use structured reason fields under the applicable stable code instead of adding ad-hoc codes.

The host and sidecar must both advertise exact `1.1`. A mixed `1.0`/`1.1` pair fails before creating a session. Binary masks and previews continue through opaque asset tokens, never JSON/base64 control payloads.

### 5. Tauri supervises recovery; Python validates restored state

The host detects sidecar exit, freezes mutations, keeps the last painted pixels explicitly marked non-authoritative, and exposes recovering status. Restart always creates a new child, random port, and secret. The new sidecar validates and loads only a verified draft or published pair; React pixels are never used to reconstruct state.

`jobs.cancel` remains job-scoped. Retry creates a new request/job against the same authoritative checkpoint. Diagnostics are assembled by the host from allowlisted, redacted fields and never upload automatically.

### 6. LabelMe preview and commit are separate phases

Export is a two-phase operation:

1. Python derives cleaned, closed polygons from the accepted mask and returns metrics plus opaque preview assets.
2. After operator confirmation, the host writes standard LabelMe JSON into an output grant.

The preview reports component count, polygon count, mask/polygon area delta, filled holes, closed gaps, simplification tolerance, label, and imagePath resolution. Export never modifies the accepted pair.

Import validates JSON, image identity, dimensions, labels, polygon bounds, and supported `shape_type="polygon"`, then rasterizes into a new draft. It never overwrites an Accepted pair. Unsupported shapes and invalid polygons are reported explicitly, not skipped.

### 7. Dataset status is derived from verified artifacts

The sidecar builds a per-item work index from verified Accepted, Needs Review, and Draft namespaces. Status precedence is corruption/conflict, save failure, dirty draft, accepted, needs review, then unstarted. The index stores hashes and compact metadata, not decoded masks.

Next-unfinished navigation uses the current filtered stable item ordering and skips Accepted items by default. A separate action can open Accepted or Needs Review in read-only mode.

### 8. QA is deterministic and advisory unless safety-critical

QA runs locally on the composed full-image binary mask and LabelMe preview. Checks include empty/near-full mask, source/crop boundary contact, tiny components, holes, one-pixel bridges, component-count policy, and export area delta. Each issue has a stable code, severity, bbox, measured values, threshold identity, and Chinese message.

Errors such as empty masks remain blocking. Advisory issues require explicit acknowledgement recorded in sidecar provenance. QA never changes pixels automatically.

### 9. Project labels are stable metadata

Without project metadata, the class is exactly `Defect`. An optional project manifest declares a bounded label list, display names, shortcuts, and export labels. A session snapshots the active label identity; changing it later does not silently relabel open work. Reclassification is a recorded mutation with old/new label, actor, revision, and timestamp.

### 10. Updates are signed, local-first, and rollback-capable

The first update workflow accepts an operator-selected local update package. Tauri verifies package signature, component manifest, checksums, compatibility, and release authority before installation. It flushes or resolves dirty drafts, closes the sidecar, stages the update, and keeps the prior verified version for rollback until post-update launch/health/load smoke passes.

Automatic network update, telemetry, analytics, and crash upload remain disabled in shipped configuration. A future network checker must be a separately approved change.

### 11. The two-click edit area is closed by evidence, not UI presence

The current independent edit-area implementation is considered complete only after native tests prove first/opposite click creation, nearest-corner replacement, half-open XYXY semantics, radius-aware brush/erase clipping at zoom/pan/non-1.0 DPR, and zero `sessions.lock_roi` calls.

## Risks / Trade-offs

- [Risk] Frequent draft writes reduce responsiveness or storage lifetime. → Coalesce completed checkpoints, keep one write active per session, benchmark pointer-up p95, and compact superseded drafts safely.
- [Risk] A draft created by another version restores incorrectly. → Require exact schema/protocol compatibility or an explicit tested migration; otherwise quarantine read-only.
- [Risk] Redo history consumes substantial memory for large masks. → Use bounded history, compressed mask snapshots/deltas, and expose the retained depth in diagnostics without weakening exact restoration.
- [Risk] LabelMe cleanup changes meaningful thin defects. → Show the difference preview and area delta; block above a frozen threshold unless explicitly acknowledged.
- [Risk] Dataset status scanning becomes slow for large folders. → Index verified sidecar metadata incrementally and invalidate by directory/file fingerprints.
- [Risk] Restarting the engine while work is dirty loses in-flight state. → Flush the last completed checkpoint first; never claim the unfinished pointer stroke or pending model job was saved.
- [Risk] Update failure leaves the App unlaunchable. → Stage side-by-side, verify before switch, retain prior version, and test rollback offline on clean Windows.
- [Risk] Broad scope delays value. → Deliver in five gated releases: work safety, LabelMe closure, productivity, QA/labels, then update delivery.

## Migration Plan

1. Freeze and validate the current protocol `1.0` baseline and complete the outstanding edit-area native evidence.
2. Add protocol `1.1` schemas/types and dual-version fixture tests; do not run mixed-version production components.
3. Implement session checkpoint/redo/prompt-update semantics and isolated draft persistence with loader tests.
4. Add host dirty-close and sidecar-recovery supervision, then React recovery controls and crash E2E.
5. Add LabelMe preview/export/import and round-trip E2E without changing accepted pair schemas.
6. Add dataset index, history UI, prompt adjustment, QA, and project label manifest support.
7. Add signed local update packaging only after installer, license, clean-machine, and rollback evidence is available.

Rollback is phase-scoped. Protocol `1.0` binaries and data remain readable; `1.1` drafts are ignored or quarantined by `1.0`, never destructively downgraded. Accepted PNG + sidecars remain the durable compatibility boundary.

## Open Questions

- Final maximum undo/redo depth and draft-retention count must be selected from reference-machine memory and disk measurements.
- QA thresholds for tiny components, near-full masks, bridge width, and polygon area delta need repository-owned defaults before implementation.
- Whether imported LabelMe labels outside the project manifest are rejected or offered as an explicit project-manifest migration requires a product decision.
- Signed update authority and reference clean-Windows hardware remain external release inputs; update implementation may proceed, but release claims cannot.
