# Tasks

Implement the React + Vite + Tauri 2 desktop shell over the existing Python core. Existing pytest core, E2E, GUI, packaging, and acceptance gates remain mandatory; never skip, xfail, delete, weaken, or rewrite a required test or threshold to go green. PySide6 stays the shipped default until stage 8. This checklist is not wired to the autonomous execution controller.

Honor the frozen protocol `1.0` operation set in `desktop-protocol` (including `sessions.lock_roi`, `sessions.select`, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.expand_roi`, `sessions.acknowledge_warning`, and `sessions.close`). Keep the eight sidecar JSON error codes exhaustive; use host-consumed SSE; replay of a completed mutating `request_id` on the same session returns the original result. Do not invent extra public operations, GPU/cloud paths, or a default-GUI switch without hash-bound parity evidence.

## 1. Governance and scaffold

- [ ] 1.1 Create `apps/desktop-ui`, `apps/desktop-host/src-tauri`, `packages/desktop-protocol`, `src/segvision/application/`, `src/segvision/transport/desktop_api/`, `tests/contract/`, sidecar `tests/integration/`, and `tests/desktop-e2e/` without copying `src/segvision/core` or mixing WebView assets into the Python package
  - Requirement refs: DSS-R001, DSS-R009, DSS-R017, DTH-R014, DPR-R020

- [ ] 1.2 Encode the frozen protocol `1.0` operations (`health`, dataset open/list, session create/get/`lock_roi`/propose/select/refine/edit/undo/`begin_manual_empty`/`expand_roi`/`acknowledge_warning`/accept/needs-review/close, job cancel, asset get) and the eight error codes in the protocol package; stop rather than adding a ninth public code or a React-owned session
  - Requirement refs: DTP-R002, DTP-R010, DTP-R013, DSS-R007, DUI-R001, DUI-R010

- [ ] 1.3 Author `packages/desktop-protocol/openapi.yaml` (OpenAPI 3.1) for the frozen control-plane operations, mutation envelope, snapshot, health/readiness, eight error codes, and HTTP mapping
  - Requirement refs: DTP-R001, DTP-R002, DTP-R003, DTP-R009, DTP-R010

- [ ] 1.4 Author `packages/desktop-protocol/events.schema.json` for the event-plane union (`progress`, `completed`, `cancelled`, `stale`, `failed`) with `event_id`, `request_id`, `job_id`, `session_id`, `revision`, `kind`, and `timestamp`
  - Requirement refs: DTP-R005, DTP-R006, DTP-R011, DTH-R018

- [ ] 1.5 Specify binary asset token, media type, and PNG `{0,255}` mask encoding rules in the protocol package so control JSON cannot carry images, masks, embeddings, or logits
  - Requirement refs: DTP-R007, DTP-R008, DTP-R012, DSS-R014

- [ ] 1.6 Generate the TypeScript client and types from the published OpenAPI into `packages/desktop-protocol` and consume that generated client from `apps/desktop-ui` (no hand-written divergent operation names)
  - Requirement refs: DTP-R009, DTH-R017, DUI-R003

- [ ] 1.7 Add Python schema loaders that validate the published OpenAPI and event schemas at sidecar startup and reject schema-invalid requests before mutation
  - Requirement refs: DTP-R009, DSS-R002, DSS-R006

- [ ] 1.8 Add Rust serde types whose enums and required fields are checked by the same contract tests against the published schemas
  - Requirement refs: DTP-R009, DTH-R017, DPR-R006

- [ ] 1.9 Add `tests/contract/` protocol tests that fail on extra, missing, or renamed operations, event `kind` values, or error codes across TypeScript, Rust, and Python
  - Requirement refs: DPR-R006, DTP-R002, DTP-R010

- [ ] 1.10 Scaffold `apps/desktop-ui` with React 19, TypeScript strict, Vite, Vitest, and Testing Library; keep the UI a dedicated annotation app with no portal, iframe host, or plugin runtime
  - Requirement refs: DUI-R002, DPR-R008, DPR-R020

- [ ] 1.11 Scaffold the Tauri 2 host crate with the frozen command allowlist stubs, production CSP denying remote scripts/frames/wildcard origins, and no generic `read_file` / `write_file` / `run_command`
  - Requirement refs: DTH-R007, DTH-R008, DTH-R014, DTH-R019

- [ ] 1.12 Scaffold `segvision.application` and `segvision.transport.desktop_api` so `import segvision` stays inert, prove existing pytest node IDs are still collected, and do not skip or xfail any required Python test
  - Requirement refs: DSS-R017, DSS-R020, DPR-R001, DPR-R004

## 2. Protocol and host skeleton

- [ ] 2.1 Implement sidecar `GET /v1/health` with exact `protocol_version` `"1.0"` matching; reject `"1"`, `"1.0.0"`, `"1.1"`, `"v1.0"`, missing, and empty versions as `protocol_version_mismatch` with no session, job, persist, or asset side effects
  - Requirement refs: DTP-R001, DSS-R002, DSS-R006

- [ ] 2.2 Bind the sidecar to `127.0.0.1` on an OS-assigned random port, authenticate with `X-SegVision-Launch-Secret`, disable production CORS, and refuse unauthenticated OpenAPI explorers
  - Requirement refs: DTP-R002, DSS-R005, DTH-R002

- [ ] 2.3 Return only the eight frozen UI error codes (`protocol_version_mismatch`, `revision_conflict`, `unauthorized`, `engine_unavailable`, `validation_failed`, `unsupported_operation`, `not_found`, `stale_job`) with operator-safe messages and no Python tracebacks
  - Requirement refs: DTP-R010, DSS-R004, DTH-R013

- [ ] 2.4 Reject unknown operations as `unsupported_operation` without forwarding to core, GPU, or a remote service
  - Requirement refs: DTP-R002, DSS-R001, DSS-R020

- [ ] 2.5 Have the Tauri host spawn a hidden Windows sidecar, wait for health before exposing a redacted engine-ready summary, and never return port or secret to the WebView
  - Requirement refs: DTH-R001, DTH-R003, DTH-R016

- [ ] 2.6 Inject the per-launch secret only on the host-to-sidecar proxy; audit that the production React bundle contains no sidecar port, secret, or base URL
  - Requirement refs: DTH-R001, DTH-R015, DPR-R020

- [ ] 2.7 Subscribe the host (not production React) to authenticated loopback SSE and forward typed Tauri events without synthesizing `completed`, `accepted`, or save-success from process liveness
  - Requirement refs: DTP-R005, DTH-R018, DUI-R003

- [ ] 2.8 Implement graceful sidecar shutdown on app close with a default 5-second timeout then terminate; capture stdout/stderr and redact secrets from diagnostic export
  - Requirement refs: DTH-R005, DTH-R011

- [ ] 2.9 Launch the sidecar CPU-only with no CUDA/GPU device flags and no hosted inference; fail host commands outside the SegVision allowlist
  - Requirement refs: DTH-R007, DTH-R016, DSS-R020

- [ ] 2.10 Add sidecar integration tests that start a real localhost process and cover health/handshake, missing secret (`unauthorized`), and version mismatch
  - Requirement refs: DPR-R007, DTP-R001, DSS-R005

- [ ] 2.11 Detect sidecar crash, report `engine_unavailable` / `recovering`, freeze mutations, keep currently painted pixels, and require a new port/secret handshake after restart
  - Requirement refs: DTH-R004, DSS-R015, DUI-R012

## 3. Read-only dataset viewer

- [ ] 3.1 Implement native folder/file pickers that store canonical paths in a host-private grant table and return only opaque `grant_id` plus display name
  - Requirement refs: DTH-R006, DUI-R013, DSS-R018

- [ ] 3.2 Implement `datasets.open` and cursor-paged `datasets.list_items` so the host resolves the grant and the sidecar verifies existence, format, manifest, and required hashes with existing contracts
  - Requirement refs: DTP-R002, DSS-R007, DSS-R018

- [ ] 3.3 Implement `assets.get` with unguessable tokens bound to `session_id`, `revision`, kind (`source_image` | `thumbnail` | `mask`), and expiry; reject `..`, `file:`, drive letters, and UNC paths
  - Requirement refs: DTP-R007, DTP-R008, DSS-R014

- [ ] 3.4 Proxy binary assets through `segvision-asset://<opaque-token>` (or equivalent host-owned scheme) so React never receives a filesystem path and images/masks never travel as Tauri JSON, base64, or integer arrays
  - Requirement refs: DTH-R009, DTH-R017, DUI-R004

- [ ] 3.5 Build the React dataset list and image viewer against host commands and opaque asset URIs only
  - Requirement refs: DUI-R003, DUI-R013, DTH-R001

- [ ] 3.6 Implement one coordinate-mapping module (CSS pixel ↔ DPR ↔ viewport zoom/pan ↔ full-image integer) with Vitest coverage for non-1.0 DPR, zoom, pan, and half-open `XYXY` round-trip
  - Requirement refs: DUI-R007, DPR-R008

- [ ] 3.7 Render Canvas2D source image plus overlay composed in the UI from binary image and mask bytes; overlay color/alpha stay application-fixed with no per-image sliders
  - Requirement refs: DUI-R006, DUI-R014, DPR-R010

- [ ] 3.8 Add sidecar integration tests that page dataset items and retrieve image, thumbnail, and mask bytes as binary (fail if JSON/base64 full payloads are accepted)
  - Requirement refs: DPR-R007, DTP-R007

- [ ] 3.9 Add Vitest/Testing Library cases for grant opacity (no raw paths in the store) and overlay composition from fixtures
  - Requirement refs: DPR-R008, DUI-R004, DUI-R014

- [ ] 3.10 Add the first real-window desktop E2E path: grant a local folder, open an image, display overlay, and assert image identity plus overlay mask hash (screenshots forensic only)
  - Requirement refs: DPR-R009, DPR-R010, DPR-R011

## 4. Full annotation loop

- [ ] 4.1 Implement application-service `sessions.create` as a desktop session that can project `IMAGE_OPEN` without calling `SegVisionEngine.start`; ROI lock is the only path that starts the engine and mints core revision `1`
  - Requirement refs: DTP-R003, DSS-R007, DUI-R001

- [ ] 4.2 Implement `sessions.propose` for a user-drawn half-open full-image ROI against the fake backend, returning at most three real candidates with no cloned filler cards
  - Requirement refs: DTP-R002, DSS-R008, DUI-R015, DPR-R024

- [ ] 4.3 Project zero through three candidate cards from the Python snapshot; map `1`/`2`/`3` to selection through the frozen 1.0 mapping; fill the overlay only for the selected candidate
  - Requirement refs: DUI-R009, DUI-R010, DUI-R015, DSS-R003

- [ ] 4.4 Implement `sessions.refine` for positive and negative points on the selected previous state; refinement must not trigger a new encoder call
  - Requirement refs: DTP-R002, DSS-R008, DSS-R012, DPR-R010

- [ ] 4.5 Implement `sessions.edit` as pointer-up or throttled stroke/delta batches (never a full-canvas upload per move) and lock out later model overwrite of the local-edit mask
  - Requirement refs: DUI-R008, DUI-R011, DSS-R012, DPR-R010

- [ ] 4.6 Wire frozen shortcuts `1`/`2`/`3`, left/right clicks, `B`, `[`/`]`, `F`, `X`, `Z`, `Space`, and `N` (erase remains an explicit control); keep `N` disabled until durable `ACCEPTED` or durable `NEEDS_REVIEW`
  - Requirement refs: DUI-R010, DPR-R024

- [ ] 4.7 Implement `jobs.cancel` as job-scoped, observable `cancelled` (never success), still attempted after revision advance, and never failing solely as `revision_conflict`
  - Requirement refs: DTP-R004, DTP-R011, DSS-R013

- [ ] 4.8 Implement dual stale rejection: Python must not install late worker results; React/host must discard events with mismatched `session_id` or older `revision`, treating duplicate `event_id` as the same event
  - Requirement refs: DTP-R006, DSS-R012, DUI-R009

- [ ] 4.9 Add a small typed Zustand (or equivalent) store for JSON view models only; keep decoded bitmaps in an asset cache and uncommitted strokes in local interaction state
  - Requirement refs: DUI-R003, DUI-R005, DUI-R011

- [ ] 4.10 Keep fusion off by default, never pixel-OR, invalidated by the first human point; omit text/VLM, DINO, per-image color sliders, multi-instance tabs, and automatic Accept
  - Requirement refs: DUI-R016, DUI-R017, DPR-R024

- [ ] 4.11 Add Vitest + Testing Library coverage for tools, candidate cards 0–3, typed recovery errors, and coordinate mapping; components must project snapshots rather than own masks or jobs
  - Requirement refs: DPR-R008, DUI-R009, DUI-R012

- [ ] 4.12 Add sidecar integration tests for propose, refine, edit, `revision_conflict`, cancel, and stale-result rejection against a real localhost process
  - Requirement refs: DPR-R007, DSS-R002, DSS-R013

- [ ] 4.13 Add real-window E2E for Tier-1 small ROI (≤3 candidates), points plus new revision, local-edit lockout, and rapid ROI/cancel/image-switch stale rejection; oracles are session/revision/event/hash, not store mocks
  - Requirement refs: DPR-R009, DPR-R010, DPR-R011

## 5. Persistence and recovery

- [ ] 5.1 Implement `sessions.accept` through existing adapters so a valid explicit Accept publishes a pair-consistent full-image PNG plus JSON sidecar only after validation, commit, and durable save; scripted E2E Accept records `acceptance_actor=scripted_test`
  - Requirement refs: DSS-R019, DUI-R016, DPR-R010, DPR-R018

- [ ] 5.2 Implement `sessions.needs_review` as a distinct path that publishes review metadata with `training_eligible=false` and never exposes an accepted training pair
  - Requirement refs: DSS-R019, DUI-R001, DPR-R010

- [ ] 5.3 Persist drafts through existing Python adapters; bind output location to a host output-folder grant rather than a React-supplied filesystem path
  - Requirement refs: DTH-R006, DUI-R004, DSS-R015, DSS-R019

- [ ] 5.4 Map read-only, locked, Unicode, long-path, and disconnected-drive output failures to stable codes (`SAVE_FAILED` / `REVIEW_SAVE_FAILED`) without hanging the UI thread; keep next-image disabled and retry without a new model call after the directory is writable
  - Requirement refs: DTH-R013, DPR-R010, DSS-R004

- [ ] 5.5 On sidecar death, freeze mutations, keep display pixels as non-authoritative, re-handshake with a new port and secret, restore only loader-verified drafts or published pairs, and otherwise require `sessions.create`
  - Requirement refs: DTH-R004, DSS-R015, DUI-R012, DPR-R007

- [ ] 5.6 Invoke public `sessions.close` on image switch and sidecar shutdown, and require a new `sessions.create` after unverified crash recovery
  - Requirement refs: DSS-R007, DTP-R002, DPR-R010

- [ ] 5.7 Add sidecar integration tests for crash handshake and verified-draft restore (no invented Accept, no rebuild from React pixels)
  - Requirement refs: DPR-R007, DSS-R015

- [ ] 5.8 Add real-window E2E for distinct Accept versus Needs Review outputs, crash/reopen, and hash oracles including `training_eligible=false` on review
  - Requirement refs: DPR-R009, DPR-R010, DPR-R011

## 6. Real MobileSAM and existing Python gates

- [ ] 6.1 Wire the approved MobileSAM TinyViT CPU backend through the existing runtime worker so the ASGI loop never runs encoder/decoder work and health/cancel/snapshot stay schedulable
  - Requirement refs: DSS-R010, DSS-R011, DSS-R020, DTH-R010

- [ ] 6.2 Keep checkpoint approval and SHA-256 verification as a Python gate; missing or mismatched weights yield diagnostic `engine_unavailable` / setup state, quarantine the artifact, and never download a replacement
  - Requirement refs: DSS-R016, DTH-R020, DPR-R014, DPR-R010

- [ ] 6.3 Run focused real-model desktop E2E first, then the broader DPR-R010 paths against operator-granted local data; keep MVTec trees outside the package
  - Requirement refs: DPR-R010, DPR-R015, DPR-R019

- [ ] 6.4 Re-run existing Python unit, integration, E2E, GUI (PySide6), packaging, and governance suites at current thresholds; fail this change if any required case is skipped, xfailed, deleted, or weakened
  - Requirement refs: DPR-R004, DPR-R001, DPR-R023

- [ ] 6.5 Confirm `validate-contracts`, `validate-evidence`, and `validate-state` still bind current OpenSpec sources, task graph, profile, and evidence hashes
  - Requirement refs: DPR-R004, DPR-R017

- [ ] 6.6 Reject GPU, cloud inference, VLM, DINO, SAM 2/3, HQ-SAM, and runtime model-download flags in sidecar launch, host commands, and the React control tree
  - Requirement refs: DSS-R020, DTH-R016, DUI-R017, DPR-R024

## 7. Offline installer and security gates

- [ ] 7.1 Package the sidecar as a versioned one-folder directory (entrypoint, CPython/runtime, CPU-only torch/MobileSAM, component manifest, hashes, notices), not a one-file PyInstaller binary
  - Requirement refs: DPR-R012, DPR-R013, DSS-R009

- [ ] 7.2 Compose the Windows x64 CPU installer from the Tauri executable, WebView assets, sidecar directory, licenses/notices, and configuration templates, each with recorded hashes
  - Requirement refs: DPR-R012, DTH-R019

- [ ] 7.3 Keep model weights as a separate checksum-verified offline component; the installer must not pack, fetch, or silently download them at build, install, or first launch
  - Requirement refs: DPR-R014, DTH-R020, DSS-R016

- [ ] 7.4 Add an allowlist plus manifest scan that fails if MVTec images/gold, unapproved weights, EdgeSAM without written commercial approval, or GPL X-AnyLabeling copies appear in the payload
  - Requirement refs: DPR-R015, DPR-R021

- [ ] 7.5 Ship Tauri updater, telemetry, analytics, crash-upload, and other runtime network features default OFF; required annotation paths must work with outbound network disabled and without login
  - Requirement refs: DPR-R016, DTH-R012

- [ ] 7.6 Extend `THIRD_PARTY_NOTICES` and SBOM to cover Tauri, WebView2, React, Vite, Rust crates, and the Python sidecar stack in addition to existing package notices
  - Requirement refs: DPR-R021

- [ ] 7.7 Fail the production profile if CORS, WebView devtools, wildcard `connect-src`, or React-direct sidecar connect is enabled in the shipped bundle
  - Requirement refs: DTH-R008, DTH-R015, DSS-R005, DPR-R020

- [ ] 7.8 Add clean-machine Windows x64 smoke with outbound network blocked: install, launch, sidecar ready, local model when present, scripted Accept and Needs Review, save/reload, Unicode and space-containing paths, uninstall/removal
  - Requirement refs: DPR-R025, DPR-R010, DTH-R013

- [ ] 7.9 Prove the installed importable `segvision` package still imports without opening a window, binding a port, loading models, or creating a hidden global session, and that the process tree requires no CUDA/GPU runtime
  - Requirement refs: DPR-R012, DSS-R017, DTH-R016

## 8. Parity evidence and default-GUI switch

- [ ] 8.1 Assemble hash-bound evidence for protocol contract, sidecar integration, Vitest/Testing Library, real-window desktop E2E, and clean-machine offline layers; reject screenshot-only oracles
  - Requirement refs: DPR-R005, DPR-R011, DPR-R019

- [ ] 8.2 Confirm PySide6 still launches, passes its existing GUI cases, and remains the documented default until every mandatory parity scenario in this change has passing evidence
  - Requirement refs: DPR-R001, DPR-R004

- [ ] 8.3 Switch the documented launch command and installer default to the Tauri app only after existing Python gates plus every additive desktop-parity scenario pass at current thresholds
  - Requirement refs: DPR-R002, DPR-R017, DPR-R019

- [ ] 8.4 Mark PySide6 deprecated-in-place: keep `src/segvision/gui/` and `segvision-gui` launchable for rollback; do not delete PySide6 source, tests, or packaging
  - Requirement refs: DPR-R003

- [ ] 8.5 Keep engineering/domain verdicts from claiming React/Tauri is the default GUI until 8.3; forbid `PARTIAL_PASS`, skip-to-green, and fabricated human Accept, gold masks, or legal signoff
  - Requirement refs: DPR-R017, DPR-R018, DPR-R022

- [ ] 8.6 Re-run existing Python suites together with the new contract, sidecar, Vitest, real-window E2E, and offline-installer layers; leave overlay/brush p95 strictly below 100 ms on the designated reference machine and invent no new latency numbers
  - Requirement refs: DPR-R004, DPR-R023, DPR-R024
