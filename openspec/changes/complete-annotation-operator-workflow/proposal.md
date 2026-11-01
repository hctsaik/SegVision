## Why

SegVision can already create and refine a MobileSAM mask, but an operator can still lose work on a crash or accidental image switch, cannot cancel or recover a stalled inference from the UI, and must leave the native app to complete LabelMe delivery. The next change should make daily annotation safe, resumable, batch-oriented, quality-checked, and deliverable without weakening the existing CPU-only MobileSAM and lossless persistence contracts.

## What Changes

- Add crash-safe editable draft autosave, startup resume, unsaved-change guards, and explicit discard semantics.
- Add visible MobileSAM cancel, retry, sidecar restart, recovery status, and redacted diagnostic export controls.
- Add native LabelMe export and import, including a preview of the cleaned closed polygons and a deterministic `Defect` fallback label.
- Add redo plus an operation-history panel covering SAM prompts, brush/erase strokes, lock/unlock, merge, ROI, and local edit-area changes.
- Allow an existing SAM point to be moved or relabeled as foreground/background with deterministic replay and rollback on failure.
- Add a dataset work queue with per-image status, filters, progress counts, reopen/resume, and next-unfinished navigation.
- Add pre-save mask quality checks for holes, isolated components, boundary contact, tiny regions, and empty or near-full masks, with issue navigation and explicit acknowledgement.
- Add project-level label management while keeping `Defect` as the no-configuration default.
- Add application version information plus signed manual and offline update-package workflows; automatic network update and telemetry remain disabled by default.
- Close the remaining native evidence gap for the independent two-click edit area, including radius-aware clipping and no `sessions.lock_roi` call.
- **BREAKING** Version the desktop control protocol from exact-match `1.0` to exact-match `1.1` for redo, prompt update, draft recovery, work-queue, interchange, diagnostics, and engine-restart operations; no `1.0` client may silently call the new contract.

## Capabilities

### New Capabilities

- `operator-session-recovery`: Editable draft autosave, dirty-state guards, crash resume, inference cancellation, engine recovery, and diagnostics.
- `annotation-interchange`: Native LabelMe export/import, cleaned polygon preview, validation, and deterministic label mapping.
- `dataset-work-queue`: Per-image annotation status, filters, progress, resume, and next-unfinished navigation.
- `annotation-quality-assurance`: Pre-save mask analysis, issue navigation, acknowledgement, and quality summaries.
- `project-label-management`: Project-level category definitions, stable default category, and output label provenance.
- `desktop-update-delivery`: Version presentation and signed manual/offline update workflows with network features disabled by default.

### Modified Capabilities

- `annotation-session`: Add redo and deterministic move/relabel replay for existing SAM prompts.
- `annotation-workflow`: Expose recovery, history, prompt adjustment, QA, work-queue, and edit-area completion behavior in the native UI.
- `annotation-persistence`: Persist and restore non-terminal editable drafts without publishing them as accepted training data.
- `acceptance-observability`: Add machine-verifiable E2E coverage for recovery, interchange, work queues, QA, prompt adjustment, and update safety.
- `offline-release`: Bind installers and update packages to signed, checksum-verified, offline-capable release artifacts.

## Impact

The change affects the Python session history and persistence adapters, desktop application service and protocol, Tauri sidecar lifecycle and diagnostics, React store/canvas/rails, dataset indexing, LabelMe adapters, installer/update packaging, and native Playwright acceptance coverage. It adds no new model provider, cloud service, GPU path, automatic Accept, or remote telemetry dependency.
