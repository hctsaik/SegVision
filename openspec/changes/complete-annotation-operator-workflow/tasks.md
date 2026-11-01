## 1. Baseline and protocol 1.1

- [ ] 1.1 Freeze the current protocol `1.0` contract and complete the outstanding native edit-area E2E for two-click creation, nearest-corner replacement, radius-aware half-open clipping, zoom/pan/DPR mapping, and zero `sessions.lock_roi` calls.
- [ ] 1.2 Define protocol `1.1` operations, snapshots, asset kinds, and event payloads for redo, prompt update, draft flush/load/discard, dataset work status, QA, LabelMe preview/export/import, engine restart, diagnostics, labels, and updates.
- [ ] 1.3 Update OpenAPI/event schemas and generate matching TypeScript, Rust, and Python protocol types without adding a ninth public error-code family.
- [ ] 1.4 Add contract tests proving exact `1.1` matching, mixed `1.0`/`1.1` rejection before mutation, command allowlists, binary asset-token use, and no raw path/secret exposure.
- [ ] 1.5 Add repository-owned schemas and defaults for draft retention, history depth, QA thresholds, LabelMe area-delta tolerance, project labels, and update manifests.

## 2. Session history and prompt adjustment

- [ ] 2.1 Refactor session history into bounded `past/current/future` checkpoints that preserve active pass, locked masks, prompts, candidate state, capabilities, ancestry, and revision.
- [ ] 2.2 Implement Redo with zero encoder/decoder calls, exact state restoration, and future-stack invalidation after a new mutation.
- [ ] 2.3 Implement atomic prompt move and foreground/background relabel by stable prompt ID using ordered decoder-only replay from the original active-pass SAM state.
- [ ] 2.4 Project typed operation-history records for ROI, candidate selection, prompts, local edits, lock/unlock, Merge, Undo, Redo, import, and reclassification.
- [ ] 2.5 Add focused core tests for redo branches, history bounds, prompt move/relabel success, invalid coordinates, decode rollback, locked-region preservation, and zero extra encoder calls.

## 3. Editable draft persistence

- [ ] 3.1 Add a versioned editable-draft schema and isolated DraftStore that AcceptedStore and training loaders never enumerate.
- [ ] 3.2 Serialize and reload source fingerprint, dataset/item/class identity, protocol, revision, ROI/crop, active mask, locked masks, prompts, history, redo state, model identity, ancestry, and payload hashes.
- [ ] 3.3 Implement pair-consistent sidecar-last publication, one-active-write coalescing, superseded-draft compaction, quarantine, and exact-item discard.
- [ ] 3.4 Trigger autosave only after completed authoritative mutations and expose authoritative dirty, flushing, saved, failed, and resumable draft states.
- [ ] 3.5 Add sidecar operations for draft flush, inspect, load, and discard through host-resolved opaque grants.
- [ ] 3.6 Add persistence fault tests for interruption at every temporary write/flush/publish stage, corrupt hashes, changed source images, protocol/schema mismatch, and Accepted/Needs Review isolation.

## 4. Tauri process recovery and dirty-close enforcement

- [ ] 4.1 Add sidecar lifecycle monitoring that detects exit, freezes mutations, marks displayed pixels non-authoritative, and exposes typed recovering state.
- [ ] 4.2 Implement sidecar restart with a new random port/secret handshake and loader-verified draft/published-result recovery only.
- [ ] 4.3 Intercept native window close and block image switch, dataset switch, engine restart, and update while a save-draft/discard/cancel decision is pending.
- [ ] 4.4 Add a redacted diagnostic exporter that drains/captures bounded child stdout/stderr and excludes secrets, paths, images, masks, and automatic upload.
- [ ] 4.5 Add Rust/sidecar integration tests for process death, new handshake identity, stale-event rejection, close cancellation, flush-before-close, and redaction.

## 5. Native work-safety, history, and prompt UI

- [ ] 5.1 Extend Zustand snapshot projection with draft, dirty, autosave, recovery, redo, operation-history, QA, work-status, and prompt-update state while keeping masks out of the store.
- [ ] 5.2 Add Chinese resume-draft and dirty-state dialogs with explicit `繼續上次標註`, `先儲存草稿`, `捨棄`, and `取消` outcomes.
- [ ] 5.3 Add running-job elapsed time plus `取消計算`, `重試`, `重新啟動 MobileSAM 引擎`, and `匯出診斷資料` controls with disabled explanations.
- [ ] 5.4 Add Redo keyboard/control behavior and an operation-history panel that identifies current, undone, and unavailable checkpoints.
- [ ] 5.5 Add canvas and inspector interactions for selecting, moving, relabeling, and deleting a stable SAM prompt while replay progress is visible.
- [ ] 5.6 Add React tests for every work-safety decision, engine state, retry/cancel/stale result, Redo branch, history projection, prompt rollback, and Chinese error state.

## 6. Native LabelMe preview, export, and import

- [ ] 6.1 Extend the LabelMe adapter to produce preview metrics, cleaned polygon assets, changed-pixel assets, deterministic cleanup identities, and bounded area-delta results without mutating Accepted data.
- [ ] 6.2 Add grant-scoped single/batch preview and export operations with stable `Defect` fallback, project label mapping, imagePath validation, and atomic JSON publication.
- [ ] 6.3 Add Native App mask/boundary/polygon/difference preview modes and require acknowledgement or blocking when cleanup exceeds the frozen threshold.
- [ ] 6.4 Implement strict LabelMe polygon import validation, supported-shape reporting, deterministic rasterization, image/size/label checks, and provenance-bound draft creation.
- [ ] 6.5 Add Native App import conflict handling that never overwrites Accepted data or a dirty draft without an explicit decision.
- [ ] 6.6 Add unit/integration/UI tests for closed polygons, thin defects, holes, one-pixel gaps, Unicode/space paths, batch export, unsupported shapes, unknown labels, and exact/toleranced round-trip masks.

## 7. Dataset work queue

- [ ] 7.1 Build an incremental per-item status index from loader-verified Accepted, Needs Review, Draft, save-failure, and conflict/corruption artifacts.
- [ ] 7.2 Add paged work-status summaries and deterministic status precedence to dataset list protocol `1.1`.
- [ ] 7.3 Add rail status badges, filters, filename search, and total/accepted/draft/review/failure progress counters.
- [ ] 7.4 Implement `下一張未完成`, valid-draft resume, and Accepted/Needs Review read-only reopen with dirty-state guard integration.
- [ ] 7.5 Add dataset/integration/React/native E2E tests for mixed statuses, newer draft over Accepted, corruption, stable filtering order, and next-unfinished navigation.

## 8. Annotation quality assurance

- [ ] 8.1 Freeze machine-readable QA thresholds and issue schema for empty/near-full masks, image/crop boundaries, tiny components, holes, one-pixel bridges, component counts, and LabelMe area delta.
- [ ] 8.2 Implement deterministic full-image mask and polygon-preview checks with stable codes, severities, bboxes, measurements, and threshold identities.
- [ ] 8.3 Project deduplicated Chinese QA issues, blocking reasons, and revision-bound acknowledgements through the session snapshot and Accepted provenance.
- [ ] 8.4 Add inspector issue navigation that frames the full-image bbox without changing pixels, ROI, or revision.
- [ ] 8.5 Add unit, integration, React, and native E2E coverage for each issue, duplicate collapse, navigation, blocking empty masks, advisory acknowledgement, and Needs Review fallback.

## 9. Project label management

- [ ] 9.1 Define and validate bounded project label metadata with stable IDs, display names, shortcuts, LabelMe names, uniqueness, and exact `Defect` no-configuration behavior.
- [ ] 9.2 Unify dataset, session, Accepted sidecar fallback, draft, QA, and LabelMe fallback on the shared case-sensitive `Defect` default.
- [ ] 9.3 Add project label selection and explicit session reclassification with old/new label, actor, timestamp, revision, and dirty-draft integration.
- [ ] 9.4 Add explicit import mapping for unknown LabelMe labels; reject silent conversion to `Defect` and record reject/map/extend-project decisions.
- [ ] 9.5 Add schema, service, persistence, UI, shortcut, reclassification, and LabelMe mapping regression tests.

## 10. Version and signed offline update delivery

- [ ] 10.1 Add an About/version projection that binds App/build, protocol, Python sidecar, model/checkpoint, and update-channel identities to running verified components.
- [ ] 10.2 Define signed local update-package and component-manifest formats with checksums, compatibility ranges, dependencies, model/license references, release authority, and rollback metadata.
- [ ] 10.3 Implement fail-closed local package verification and side-by-side staging without modifying the current verified installation before all pre-switch checks pass.
- [ ] 10.4 Integrate dirty-draft resolution, session close, sidecar stop, staged switch-over, post-update launch/health/load/save smoke, and automatic executable rollback.
- [ ] 10.5 Add Native App controls for selecting a local update, viewing verification results, cancelling, applying, reporting rollback, and confirming the running version.
- [ ] 10.6 Prove shipped automatic network update, telemetry, analytics, crash upload, remote inference, and login dependencies remain disabled by default.

## 11. Verification and documentation

- [ ] 11.1 Run focused core, persistence, sidecar, protocol, Rust, React, LabelMe, QA, work-queue, label, and updater tests after each owning task.
- [ ] 11.2 Run the complete existing Python, GUI, desktop UI, contract, integration, E2E, packaging, and governance suites without deleting, skipping, xfail-ing, or weakening required coverage.
- [ ] 11.3 Add native real-MobileSAM `014.png` E2E for autosave, incomplete-stroke exclusion, cancel/retry/stale rejection, crash/restart/resume, Redo, prompt move/relabel, and edit-area clipping.
- [ ] 11.4 Add native batch E2E for work-status filters, next-unfinished, QA navigation/acknowledgement, LabelMe preview/export/import, project label mapping, and artifact/hash oracles.
- [ ] 11.5 Update operator help, keyboard legend, LabelMe guide, recovery troubleshooting, project manifest reference, update guide, architecture diagrams, and native app status documentation.
- [ ] 11.6 Run OpenSpec strict validation plus repository `validate-contracts`, task evidence validation, and execution-state validation against matching source/spec/task/profile hashes.

## 12. Phased release gates

- [ ] 12.1 `R1-WORK-SAFETY` — Prove draft autosave, dirty guards, cancel/retry, sidecar restart, diagnostics, crash recovery, and no fabricated Accept with machine-verifiable native evidence.
- [ ] 12.2 `R2-LABELME-CLOSURE` — Prove Native App preview, single/batch export, import, conflict safety, and exact/toleranced round-trip on thin real defects.
- [ ] 12.3 `R3-PRODUCTIVITY` — Prove Redo/history, prompt adjustment, dataset statuses, filters, progress, resume, and next-unfinished workflows.
- [ ] 12.4 `R4-QA-LABELS` — Prove deterministic QA, navigation, acknowledgements, `Defect` default, project labels, reclassification, and LabelMe mapping provenance.
- [ ] 12.5 `X-UPDATE-AUTH` — Obtain attributable signing keys, release authority, dependency/model/asset authorization, and approved update-channel ownership; do not fabricate or infer these inputs.
- [ ] 12.6 `X-UPDATE-REFERENCE` — Obtain the designated supported clean Windows x64 offline update/rollback target and fingerprint its OS, CPU, RAM, storage, WebView, and network-block state.
- [ ] 12.7 `R5-UPDATE-DELIVERY` — On the approved reference target, prove invalid-signature rejection, valid offline update, dirty-draft preservation, post-update annotation/save/reload, forced-failure rollback, artifact integrity, and network-disabled operation.
