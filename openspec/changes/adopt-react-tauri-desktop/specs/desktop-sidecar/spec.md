## ADDED Requirements

### Requirement: [DSS-R001] Desktop sidecar is a transport adapter, not a second core

The Python desktop sidecar SHALL be a localhost transport adapter plus a thin application service over the existing SegVision core, providers, runtime, adapters, and acceptance packages. It MUST map versioned desktop-protocol messages onto existing public operations and MUST NOT own authoritative masks, candidate ranking, ROI geometry, recipe evaluation, or a second mask store. Sidecar work SHALL be an application plus transport adapter, not a core fork. It MUST NOT copy or fork the existing core package.

#### Scenario: [DSS-R001-S01] Adapter delegates a valid mutation

- **WHEN** the sidecar receives a schema-valid refinement request for a current session and revision
- **THEN** it SHALL map the request to the existing application/core refinement operation
- **AND** the resulting candidate, mask, capabilities, and revision SHALL be those produced by the existing session, not a sidecar-local reconstruction

#### Scenario: [DSS-R001-S02] Adapter does not become a second engine

- **WHEN** a protocol client asks the sidecar to rank candidates, merge masks, evaluate a class recipe, or store a mask independently of the core session
- **THEN** the sidecar MUST reject the request as unsupported or MUST perform it only by calling the existing authoritative module
- **AND** it MUST NOT keep a parallel candidate graph or mask buffer as the source of truth

### Requirement: [DSS-R002] Adapter SHALL validate protocol version, schema, session, revision, and request id

Every control-plane request SHALL be validated before any session mutation. The adapter MUST require a supported `protocol_version` in the typed envelope or header, a schema-valid payload, a well-formed unique `request_id` on mutations, and, for snapshot-mutating session operations, a known `session_id` plus a `base_revision` that matches the current authoritative revision. A mismatch MUST fail closed. Successful snapshot-mutating operations MUST return the new authoritative `revision`. A stale `base_revision` on a snapshot-mutating operation MUST produce `revision_conflict` and MUST NOT silently overwrite session state. Snapshot-mutating operations are `sessions.lock_roi`, `sessions.propose`, `sessions.select`, `sessions.refine`, `sessions.edit`, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.expand_roi`, `sessions.acknowledge_warning`, `sessions.accept`, `sessions.needs_review`, and `sessions.close`. `jobs.cancel` is job-scoped: it MUST carry `session_id` and `job_id`, MUST still be attempted after the session revision advances, and MUST NOT return `revision_conflict` solely because `base_revision` is old. Reads, lists, and asset-get MUST NOT increment revision.

#### Scenario: [DSS-R002-S01] Current-revision mutation is accepted

- **WHEN** a schema-valid mutation carries a supported protocol version, a unique request id, an active session id, and a `base_revision` equal to the session revision
- **THEN** the adapter SHALL invoke the corresponding application operation
- **AND** the response SHALL include the resulting authoritative `revision`

#### Scenario: [DSS-R002-S02] Unsupported protocol or invalid schema is rejected

- **WHEN** a request uses an unsupported `protocol_version`, omits a required field, or fails the published request schema
- **THEN** the adapter MUST reject it with a stable validation error code
- **AND** it MUST NOT create a session, increment a revision, submit a job, or persist an annotation

#### Scenario: [DSS-R002-S03] Unknown session is rejected

- **WHEN** a mutation or snapshot request names a `session_id` that is not active in this sidecar process
- **THEN** the adapter MUST reject it with a stable session-not-found error
- **AND** it MUST NOT create an implicit session or reuse another session's state

#### Scenario: [DSS-R002-S04] Stale base revision produces revision_conflict on snapshot-mutating operations

- **WHEN** a snapshot-mutating operation carries `base_revision` less than the current session revision
- **THEN** the adapter MUST return `revision_conflict`
- **AND** it MUST leave the current session, candidates, local edits, and jobs unchanged
- **AND** it MUST NOT apply the mutation after the fact
- **AND** this scenario SHALL NOT apply to `jobs.cancel`

#### Scenario: [DSS-R002-S05] Missing or duplicate request identity is rejected

- **WHEN** a mutation omits `request_id`, supplies a malformed id, or replays a completed mutating `request_id` for the same session
- **THEN** the adapter MUST reject the new mutation or return the original idempotent result without a second side effect
- **AND** it MUST NOT submit a second inference job for a replayed completed mutation

#### Scenario: [DSS-R002-S06] Cancel is not subject to revision_conflict

- **WHEN** `jobs.cancel` carries `session_id` and `job_id` after the session revision has advanced
- **THEN** the adapter MUST still attempt cancellation
- **AND** MUST NOT return `revision_conflict` solely because `base_revision` is old

### Requirement: [DSS-R003] Transport DTOs SHALL map to existing core and application types

The adapter SHALL convert protocol DTOs into the existing in-memory core and application types, including full-image half-open `XYXY` rectangles, full-image points, opaque candidate ids, class ids, warning acknowledgements, and job ids. Callers MUST NOT be required to supply embeddings, logits, tensor names, normalization values, model input shapes, or provider mask-state arrays. The adapter MUST NOT invent candidate ids, masks, or provenance that the session did not produce. The `sessions.lock_roi` DTO MUST include `class_id` and, when present, recipe identity sourced from dataset metadata, not React-invented tensors.

#### Scenario: [DSS-R003-S01] ROI and point DTOs use existing geometry contracts

- **WHEN** a proposal or refinement DTO contains a user ROI or human points
- **THEN** the adapter SHALL convert them to the existing full-image geometry types and pass those values to the application/core API
- **AND** it MUST preserve half-open `XYXY` semantics and MUST NOT convert the prompt into model-space tensors for the client

#### Scenario: [DSS-R003-S02] Opaque candidate identifiers are preserved

- **WHEN** `sessions.select`, `sessions.refine`, `sessions.edit`, or `sessions.accept` names a candidate id
- **THEN** the adapter SHALL pass that opaque id to the existing session API
- **AND** a foreign or stale candidate id SHALL surface as the existing typed candidate/session mismatch mapped to `validation_failed` or `unsupported_operation` per DTP-R016

#### Scenario: [DSS-R003-S03] Raw model state is rejected at the boundary

- **WHEN** a request payload includes embeddings, logits, tensor names, or provider previous-mask arrays
- **THEN** the adapter MUST reject the payload as schema-invalid or unsupported
- **AND** those values MUST NOT be forwarded into core

#### Scenario: [DSS-R003-S04] lock_roi carries dataset class_id

- **WHEN** `sessions.lock_roi` is mapped to `SegVisionEngine.start`
- **THEN** the adapter SHALL pass `class_id` and any recipe identity from dataset metadata together with a valid full-image ROI
- **AND** it MUST NOT accept React-invented class tensors or omit `class_id`

### Requirement: [DSS-R004] Exceptions SHALL map to stable error codes, not Python stack traces

The adapter SHALL translate core, application, runtime, persistence, and validation failures into the versioned desktop-protocol error contract of eight sidecar JSON UI codes: `protocol_version_mismatch`, `revision_conflict`, `unauthorized`, `engine_unavailable`, `validation_failed`, `unsupported_operation`, `not_found`, and `stale_job`. The UI protocol MUST expose those machine-readable codes, a safe operator message, and optional structured details. Python stack traces, traceback strings, and interpreter internals MUST NOT be the UI protocol. “Corresponding” means the many-to-one map in DTP-R016, not one extra protocol code per core exception type: `StaleRevision` for a late job maps to `stale_job`; a client `base_revision` behind the current snapshot maps to `revision_conflict`; `InvalidRoi`, `RecipeSchemaError`, `RecipeClassMismatch`, and crop-candidate validation failure map to `validation_failed`; `EmbeddingExpired` maps to `stale_job`; `BackendUnavailable` and a missing, unapproved, or checksum-invalid model map to `engine_unavailable`; `UnsupportedOperation` maps to `unsupported_operation`; unknown or expired grant identity maps to `unauthorized` or `not_found` as appropriate. Windows path and IO failures surfaced through host commands use host-stable `grant_invalid` and `filesystem_error`; they are not extra sidecar JSON codes.

#### Scenario: [DSS-R004-S01] Typed core errors keep the mapped eight codes

- **WHEN** the application/core raises `InvalidRoi`, `StaleRevision`, `UnsupportedOperation`, or another existing typed public error
- **THEN** the adapter SHALL return the DTP-R016 mapped protocol `code` from the frozen eight
- **AND** the response body MUST be schema-valid without a Python traceback field as a required or displayed protocol member
- **AND** the adapter MUST NOT invent a ninth sidecar JSON code

#### Scenario: [DSS-R004-S02] Unexpected exceptions are sanitized

- **WHEN** an untyped or unexpected exception occurs while handling a request
- **THEN** the adapter MUST return one of the eight frozen codes (`engine_unavailable` when the sidecar cannot serve) and a recoverable operator message
- **AND** it MUST NOT serialize a Python stack trace, hidden frame, or exception repr as the UI protocol payload
- **AND** it MUST NOT use an `internal-failure` code outside the frozen eight

#### Scenario: [DSS-R004-S03] Diagnostics remain host-local

- **WHEN** a failure is recorded for support diagnostics
- **THEN** the sidecar MAY write a redacted log on the local host
- **AND** that log MUST NOT be required by React as the error schema
- **AND** secrets, per-launch credentials, and raw image bytes MUST NOT appear in the protocol error

### Requirement: [DSS-R005] Production sidecar SHALL bind loopback only and MUST NOT enable CORS

A production desktop sidecar MUST listen on `127.0.0.1` only. It MUST NOT bind `0.0.0.0`, `::`, a LAN interface, or a routable hostname. Production MUST NOT enable CORS. The sidecar MUST reject control and asset requests that lack the current per-launch shared secret. React MUST NOT be given a production configuration that treats the sidecar as a cross-origin website.

#### Scenario: [DSS-R005-S01] Production process binds loopback

- **WHEN** the sidecar starts in production configuration
- **THEN** it SHALL bind `127.0.0.1` on the host-selected port
- **AND** a bind or listen target other than IPv4 loopback MUST fail startup

#### Scenario: [DSS-R005-S02] LAN or wildcard bind is refused

- **WHEN** configuration asks the production sidecar to listen on `0.0.0.0`, `::`, or a non-loopback address
- **THEN** startup MUST fail
- **AND** no production HTTP server SHALL accept connections

#### Scenario: [DSS-R005-S03] Production CORS is disabled

- **WHEN** a browser or test client sends a CORS preflight or a cross-origin request to a production sidecar
- **THEN** the sidecar MUST NOT return an Access-Control-Allow-Origin policy that permits that origin
- **AND** the request MUST NOT succeed as an unauthenticated public website call

#### Scenario: [DSS-R005-S04] Missing launch secret is rejected

- **WHEN** a production control or asset request omits or mismatches the current per-launch secret
- **THEN** the sidecar MUST reject the request
- **AND** it MUST NOT mutate session state or stream a binary asset

### Requirement: [DSS-R006] Localhost HTTP MAY implement transport, but MUST NOT be a public website

A localhost HTTP adapter MAY implement the transport when it provides schema validation and testability. That implementation remains a private desktop transport. Production MUST NOT serve an interactive public website, unauthenticated OpenAPI explorer, wildcard origin, or browser-direct annotation UI. React MUST access sidecar operations only through the Tauri host bridge and MUST NOT treat the adapter as a hosted web product. The production event plane SHALL be loopback host-owned SSE or an equivalent host-only HTTP channel authenticated with the per-launch secret; React MUST NOT subscribe to sidecar event URLs directly.

#### Scenario: [DSS-R006-S01] Localhost adapter is allowed behind the host

- **WHEN** the production sidecar is implemented with a localhost HTTP adapter
- **THEN** it MAY expose the versioned localhost control, event, and asset endpoints
- **AND** those endpoints MUST still require the per-launch secret and loopback bind defined by this capability
- **AND** event emission MUST be host-owned on loopback; React MUST NOT subscribe to the sidecar event URL

#### Scenario: [DSS-R006-S02] Production does not serve a public web app

- **WHEN** the production sidecar is running
- **THEN** it MUST NOT serve a public HTML application, docs website, or unauthenticated OpenAPI explorer as a user-facing product
- **AND** a direct React-to-sidecar browser session MUST NOT be a supported production path

#### Scenario: [DSS-R006-S03] Development CORS cannot leak into production

- **WHEN** a development-only exact-origin CORS exception exists
- **THEN** production configuration MUST disable it
- **AND** a production startup with wildcard or browser-public CORS MUST fail

### Requirement: [DSS-R007] Thin application service SHALL coordinate desktop use cases

The application service SHALL coordinate existing modules for dataset open, cursor paging, current-image flow, desktop protocol session create and close, ROI lock via `sessions.lock_roi`, revisioned proposals, candidate selection via `sessions.select`, undo via `sessions.undo`, manual-empty via `sessions.begin_manual_empty`, Expand ROI via `sessions.expand_roi`, warning acknowledgement via `sessions.acknowledge_warning`, point refinement, local-edit commit, job submit/cancel/observe, persistence, evidence recording, and recoverable drafts. It MUST return authoritative snapshots from the session and persistence adapters. It MUST NOT infer job completion, fabricate candidates, or auto-Accept. React MUST NOT own select, undo, or manual-empty state.

#### Scenario: [DSS-R007-S01] Dataset-to-session flow is orchestrated

- **WHEN** the host supplies a valid dataset grant and the UI requests open, page, current image, and `sessions.create`
- **THEN** the application service SHALL open the dataset, return page summaries, and open a desktop protocol session in public workflow state `IMAGE_OPEN` at protocol `revision` `0`
- **AND** it MUST NOT call `SegVisionEngine.start` and MUST NOT return core revision `1` from create
- **AND** the snapshot MUST show no `user_roi_full` and MUST NOT claim Accept or Needs Review eligibility

#### Scenario: [DSS-R007-S02] Annotation mutations stay session-owned

- **WHEN** the UI requests `sessions.lock_roi`, proposal, `sessions.select`, refinement, local edit, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.expand_roi`, `sessions.acknowledge_warning`, explicit Accept, or Needs Review
- **THEN** the application service SHALL call the existing session operations in that order of authority
- **AND** Accept MUST remain an explicit human or scripted-test commit and MUST NOT be emitted because a job completed
- **AND** `sessions.lock_roi` is the only operation that invokes `SegVisionEngine.start` with `class_id` plus a valid full-image ROI and mints core revision `1`

#### Scenario: [DSS-R007-S03] Jobs, persistence, evidence, and drafts are coordinated

- **WHEN** a long-running proposal is submitted, later cancelled or completed, and a later Accept or Needs Review is persisted
- **THEN** the application service SHALL submit and observe the job through the existing runtime, persist through existing adapters, record evidence through existing acceptance contracts, and write recoverable drafts only through those adapters
- **AND** it MUST close session-owned runtime state when `sessions.close` succeeds

#### Scenario: [DSS-R007-S04] Snapshot is authoritative

- **WHEN** a client requests `sessions.get` of the current session after a successful mutation
- **THEN** the returned snapshot SHALL include `protocol_session_id`, `workflow_state`, `revision` (`0` if `IMAGE_OPEN`), `user_roi_full` / `crop_rect_full` when they exist, selected candidate id, candidate summaries with capability flags, warning list, job summary, image and mask asset tokens, `class_id` when bound, and annotation timer origin when the first ROI has been locked
- **AND** the sidecar MUST NOT return a React- or host-supplied mask as authoritative state

### Requirement: [DSS-R008] Application service MUST NOT duplicate core ranking, geometry, mask, or recipe rules

The application service MUST NOT reimplement candidate validation, ranking, duplicate filtering, ROI padding, crop geometry, morphology, hole fill, fusion, or class-recipe execution. Those rules remain in the existing core and CV/provider modules. The service MAY sequence calls and translate errors, but a conflict with core behavior is a sidecar defect.

#### Scenario: [DSS-R008-S01] Ranking remains core-owned

- **WHEN** a proposal completes with more internally generated masks than the public slot limit
- **THEN** the displayed candidate set SHALL be the existing core policy result of at most three real candidates
- **AND** the application service MUST NOT pad, clone, or re-rank slots

#### Scenario: [DSS-R008-S02] Geometry and recipes remain core-owned

- **WHEN** a user ROI is accepted or a class recipe is bound
- **THEN** crop padding, half-open rectangles, and recipe execution SHALL be performed by the existing core/CV path
- **AND** the application service MUST NOT compute a second crop or a second recipe mask

#### Scenario: [DSS-R008-S03] Local mask edits remain core-owned

- **WHEN** a brush, erase, grow, shrink, or fill-holes delta is committed
- **THEN** the session SHALL apply the existing mask operations and terminal local-edit lock
- **AND** the sidecar MUST NOT merge model pixels over a local edit

### Requirement: [DSS-R009] Existing core, providers, runtime, adapters, and acceptance remain authoritative

Existing core, providers, runtime, adapters, and acceptance remain the authoritative implementations. Sidecar work MUST add application and transport layers only; it is not a core fork. Core MUST remain headless and in-memory: it MUST NOT import GUI or Tauri types, open annotation output paths, write files, download models, or hold a hidden process-global session. Lower layers MUST NOT depend on React, Tauri, or browser objects.

#### Scenario: [DSS-R009-S01] New code is confined to application and transport

- **WHEN** the desktop sidecar is added to the repository
- **THEN** desktop HTTP and use-case orchestration SHALL live in application and transport adapter layers
- **AND** the existing core package MUST NOT gain HTTP handlers, filesystem path parameters, or GUI imports

#### Scenario: [DSS-R009-S02] Core remains headless under sidecar use

- **WHEN** a fake-backend annotation flows through the application service without persistence
- **THEN** core SHALL complete start, propose, select, refine, local edit, commit, and Needs Review in memory
- **AND** it MUST NOT open an output path, write a file, or import a GUI or transport module

#### Scenario: [DSS-R009-S03] Lower layers do not depend on the shell

- **WHEN** import graphs of core, providers, runtime, adapters, and acceptance are inspected
- **THEN** they MUST NOT import React, Tauri, WebView, or the desktop transport adapter
- **AND** transport MAY depend downward on application, which MAY depend downward on core/runtime/adapters

### Requirement: [DSS-R010] Heavy inference MUST run on the existing runtime worker, not the ASGI event loop

Proposal encoding, decoding, refinement, and other heavy inference MUST execute on the existing CPU runtime/worker with bounded threads. The ASGI or HTTP event-loop thread MUST NOT run encoder or decoder work. Health, cancel, snapshot, and validation endpoints MUST remain schedulable while inference is in flight. The Tauri UI thread is outside this capability, but the sidecar MUST NOT require that thread to wait on MobileSAM.

#### Scenario: [DSS-R010-S01] Proposal work is queued on the runtime

- **WHEN** a proposal request is accepted
- **THEN** the application service SHALL submit a runtime job carrying session id and revision
- **AND** the ASGI worker that accepted the HTTP request MUST return without executing the encoder

#### Scenario: [DSS-R010-S02] Event loop stays responsive during a blocked encoder

- **WHEN** a deterministic test barrier blocks the runtime encoder after a proposal is submitted
- **THEN** health, cancel, and session-snapshot requests SHALL still complete
- **AND** the blocked work MUST remain on the runtime worker

#### Scenario: [DSS-R010-S03] Sidecar does not add a second inference loop

- **WHEN** two concurrent protocol requests require model work for the same approved backend
- **THEN** both SHALL be scheduled through the existing runtime job mechanism
- **AND** the adapter MUST NOT start a parallel FastAPI-thread model call

### Requirement: [DSS-R011] A single approved model instance and bounded embedding cache SHALL remain

The sidecar process SHALL continue to use one approved model instance and the existing bounded in-memory embedding cache. It MUST NOT deserialize an additional production model per request, per session, or per HTTP worker, and MUST NOT unbounded-cache encodings. Cache entries remain bound to session, revision, backend fingerprint, preprocessing version, crop fingerprint, and `crop_rect_full`. The adapter MUST NOT transmit embeddings or logits to the host or UI.

#### Scenario: [DSS-R011-S01] One approved instance is shared

- **WHEN** two annotation sessions in one sidecar process require the approved MobileSAM CPU backend
- **THEN** the process SHALL use the single approved deserialized model instance
- **AND** a second production model object MUST NOT be loaded as a per-request or per-ASGI-worker instance

#### Scenario: [DSS-R011-S02] Embedding cache stays bounded and session-scoped

- **WHEN** encodings are produced across revisions or sessions beyond the existing cache bound
- **THEN** the existing bounded cache SHALL evict according to its contract
- **AND** a closed session's encoded state SHALL be released
- **AND** the sidecar MUST NOT create a second unbounded cache

#### Scenario: [DSS-R011-S03] Model state does not leave the Python process

- **WHEN** a snapshot, event, or asset is returned to the host
- **THEN** the payload MUST NOT include embeddings, logits, or provider mask-state tensors
- **AND** clients SHALL refer to crops and candidates by opaque ids and binary asset tokens only

### Requirement: [DSS-R012] New ROI or refinement SHALL increment revision and MUST NOT apply stale jobs

A successful new ROI or accepted refinement SHALL increment the session revision exactly as the existing session contract specifies. In-flight jobs from the previous revision SHALL be cancelled when supported. A later completion from an old revision SHALL be marked stale and MUST NOT be applied to the snapshot, candidate set, canvas assets, or persistence. The adapter MUST also ignore late events whose revision is older than the current session revision.

#### Scenario: [DSS-R012-S01] ROI change advances revision and invalidates old work

- **WHEN** an active session at revision `r` accepts a new ROI while a proposal job is in flight
- **THEN** the session revision SHALL become `r + 1`
- **AND** prior candidates, encoded crop state, prompt history, fusion, and local edits SHALL become invalid
- **AND** the old job SHALL be cancelled when supported or marked stale on completion

#### Scenario: [DSS-R012-S02] Completed old jobs do not apply

- **WHEN** a worker completes a result tagged with revision `r` after the session has advanced to `r + 1`
- **THEN** the application service SHALL mark that result stale
- **AND** the result MUST NOT become visible, selectable, refinable, editable, committable, or persisted
- **AND** the adapter MUST NOT emit it as a current `completed` candidate set

#### Scenario: [DSS-R012-S03] Refinement is revision-safe

- **WHEN** a current-revision refinement is accepted
- **THEN** the session SHALL increment revision according to the existing session rules and bind the new result only to that revision
- **AND** a later completion for the pre-refinement revision MUST be discarded

### Requirement: [DSS-R013] Cancel SHALL be observable and MUST NOT mean success

Job cancellation SHALL be an observable state transition, not an implicit success. `jobs.cancel` MUST carry `session_id` and `job_id`, MUST still be attempted after the session revision advances, and MUST NOT return `revision_conflict` solely because `base_revision` is old. A cancel request MUST be recorded, and a cancelled or stale job MUST NOT emit candidates, an Accept result, or a training-eligible annotation. Cancel MUST NOT auto-Accept, invent a fallback candidate, or clear an existing local edit by claiming success.

#### Scenario: [DSS-R013-S01] Cancel is visible without succeeding

- **WHEN** a client cancels an in-flight proposal or refinement job
- **THEN** the sidecar SHALL emit a job event with kind `cancelled` or the equivalent protocol cancelled state, including `event_id`, `request_id`, `job_id`, `session_id`, `revision`, and timestamp
- **AND** the job MUST NOT be reported as `completed` success

#### Scenario: [DSS-R013-S02] Cancelled work cannot produce candidates or Accept

- **WHEN** a cancelled or stale job later produces a backend mask
- **THEN** the sidecar MUST NOT publish candidates from that job
- **AND** it MUST NOT create a `CommitResult`, accepted pair, or Accept event

#### Scenario: [DSS-R013-S03] Cancel does not fabricate recovery success

- **WHEN** cancel occurs before any usable candidate exists
- **THEN** the session SHALL remain recoverable through manual-empty or Needs Review as existing session rules allow
- **AND** the adapter MUST NOT emit a synthetic candidate to make cancel look successful

### Requirement: [DSS-R014] Sidecar SHALL issue short-lived unguessable binary asset tokens

Large images and masks SHALL be offered through the data plane as short-lived unguessable binary asset tokens, not as JSON, base64, or integer arrays in the control plane. Each token MUST bind `session_id`, `revision`, asset kind, and expiry. The sidecar MUST reject expired, unbound, wrong-kind, wrong-revision, and path-like tokens, including any value containing `..` or an absolute filesystem path. Tokens MUST NOT authorize arbitrary local file read. Mask bytes for display and commit previews SHALL be PNG `{0,255}` with explicit `image/png` media type. Source images SHALL remain PNG, JPEG, or WebP as stored with an explicit media type.

#### Scenario: [DSS-R014-S01] Current-revision asset token streams bytes

- **WHEN** a snapshot includes an image or mask asset for the current session and revision
- **THEN** the sidecar SHALL issue an unguessable token bound to that session, revision, kind, and expiry
- **AND** a later authorized fetch of that token SHALL return the binary bytes without placing the full raster in the control-plane JSON

#### Scenario: [DSS-R014-S02] Expired or unbound tokens are rejected

- **WHEN** a client presents an expired token, a token for another session or revision, a token of the wrong kind, or a guessable identifier
- **THEN** the sidecar MUST deny the asset
- **AND** it MUST NOT stream another image, mask, or file

#### Scenario: [DSS-R014-S03] Filesystem paths cannot be used as tokens

- **WHEN** a client requests an asset with `..`, an absolute path, a host grant path, or any non-issued token string
- **THEN** the sidecar MUST reject the request
- **AND** it MUST NOT read arbitrary disk content

### Requirement: [DSS-R015] Crash recovery SHALL restore only verifiable persisted drafts after re-handshake

Sidecar process death SHALL discard in-memory annotation sessions. Recovery SHALL follow this sequence: detect crash; UI `engine_unavailable/recovering`; freeze mutations; keep displayed pixels as non-authoritative; the host MAY auto-restart the sidecar process with a new port and secret; re-handshake; restore if and only if persistence verifies a draft or published pair for the current image identity; otherwise require `sessions.create`. “Unconditional restart” means respawn and assume the in-memory session survived; that assumption is forbidden. Auto-respawn of the process is allowed. The sidecar MUST NOT rebuild ROI, candidates, jobs, undo history, or masks from React memory.

#### Scenario: [DSS-R015-S01] In-memory session does not survive restart

- **WHEN** the sidecar process exits while an unsaved in-memory session exists and a new sidecar process then completes health/handshake
- **THEN** the previous `session_id` MUST NOT be active
- **AND** the new process MUST NOT claim that candidates, jobs, or masks from the dead process are current
- **AND** auto-respawn MUST NOT be treated as unconditional restart of live session memory

#### Scenario: [DSS-R015-S02] Verifiable persisted draft can be restored

- **WHEN** re-handshake succeeds and an existing persistence adapter verifies a schema-valid recoverable draft or published pair for the current image identity
- **THEN** the application service SHALL restore that draft or published pair into a new session only after loader validation
- **AND** unverifiable or mismatched files MUST NOT be restored

#### Scenario: [DSS-R015-S03] Missing draft requires a new session

- **WHEN** re-handshake succeeds and no verifiable persisted draft or published pair exists for the current image identity
- **THEN** the sidecar MUST require `sessions.create`
- **AND** it MUST NOT synthesize annotation state from UI snapshots or prior events

### Requirement: [DSS-R016] Model checkpoint approval and checksum SHALL remain a Python gate

Approval-status and SHA-256 verification of a model checkpoint SHALL occur in Python before the checkpoint is deserialized. The sidecar MUST use the existing fail-closed manifest/checksum path. Tauri, React, and the transport adapter MUST NOT load weights, skip checksum comparison, or treat a host file picker grant as model approval.

#### Scenario: [DSS-R016-S01] Approved matching checkpoint may deserialize

- **WHEN** the sidecar is asked to make the approved CPU backend ready and the checkpoint hash matches the approved manifest
- **THEN** Python SHALL verify approval and checksum first
- **AND** only then MAY the existing provider deserialize the model

#### Scenario: [DSS-R016-S02] Checksum or approval failure blocks load

- **WHEN** the checkpoint is unapproved, missing from the manifest, or has a mismatched SHA-256
- **THEN** Python MUST prevent deserialization
- **AND** the sidecar SHALL return `engine_unavailable` without loading the file as a model

#### Scenario: [DSS-R016-S03] Tauri cannot replace the gate

- **WHEN** the host supplies a user-selected weight path or claims the file is trusted
- **THEN** the sidecar MUST still run the Python approval and checksum gate
- **AND** it MUST NOT deserialize because the host already read or hashed the file

### Requirement: [DSS-R017] Importing `segvision` MUST NOT start GUI, sidecar HTTP, or a hidden model session

The importable `segvision` package MUST remain side-effect free. `import segvision` MUST NOT start a GUI, bind a sidecar HTTP port, spawn a hidden ASGI server, open datasets, or create a process-global model or annotation session. Sidecar HTTP listening SHALL occur only through an explicit desktop entrypoint invoked by the Tauri host.

#### Scenario: [DSS-R017-S01] Package import stays inert

- **WHEN** a clean environment executes `import segvision`
- **THEN** the import SHALL succeed without starting a GUI, binding `127.0.0.1` for the desktop API, downloading a model, opening files, or creating a hidden model session

#### Scenario: [DSS-R017-S02] Sidecar listen requires an explicit entrypoint

- **WHEN** the desktop sidecar HTTP adapter is not explicitly started
- **THEN** no production desktop-api server SHALL be listening
- **AND** importing application or core modules MUST NOT bind the port as an import side effect

### Requirement: [DSS-R018] Dataset open from a host grant SHALL reuse existing verification contracts

Opening a dataset SHALL consume a host-authorized grant path, not an arbitrary React-supplied filesystem capability. React sends `grant_id` only; host resolves canonical path; sidecar receives the path from the host process, never from the WebView, then existence/manifest/hash checks. `datasets.open` takes a dataset `grant_id` that the host has already resolved. The application service MUST verify existence, supported format, dataset manifest, and required hashes using existing contracts before paging images. MVTec and other licensed evaluation corpora MUST remain outside the software package, installer, source archive, and CI fixture bundle. Missing, unreadable, unlocked, or hash-mismatched datasets MUST fail with `validation_failed` or `not_found` as appropriate.

#### Scenario: [DSS-R018-S01] Valid granted dataset opens

- **WHEN** the host presents a grant for a local dataset whose files exist, match the supported format, and satisfy the existing manifest and required hashes
- **THEN** the application service SHALL open it and allow cursor paging of item summaries
- **AND** React MUST NOT need a raw filesystem path to complete the open
- **AND** the sidecar MUST have received the canonical path from the host process, never from the WebView

#### Scenario: [DSS-R018-S02] Missing or invalid dataset is rejected

- **WHEN** the granted path does not exist, is not a supported dataset layout, fails manifest validation, or disagrees with a required hash
- **THEN** the sidecar MUST return `validation_failed` or `not_found` as appropriate
- **AND** it MUST NOT create an annotation session or copy the dataset into the package

#### Scenario: [DSS-R018-S03] MVTec remains outside the package

- **WHEN** a developer or E2E profile points at a local MVTec tree through explicit environment or grant configuration
- **THEN** the sidecar MAY read that local tree after the same existence, format, manifest, and hash checks
- **AND** the software package, installer, source archive, and default CI fixtures MUST NOT contain the MVTec corpus

### Requirement: [DSS-R019] Persistence SHALL remain pair-consistent PNG plus JSON through existing adapters

Accept and Needs Review persistence SHALL continue to use the existing persistence adapters and pair-consistent publication protocol. An accepted outcome MUST publish a full-image PNG plus JSON sidecar through that adapter; a Needs Review outcome MUST remain isolated from training enumeration. The desktop sidecar MUST NOT add a second mask store, write masks through ad-hoc files, or treat a UI asset cache as durable storage. The output folder is a host grant: React sends `grant_id` only; host resolves canonical path; sidecar receives the path from the host process, never from the WebView, then existence/manifest/hash checks.

#### Scenario: [DSS-R019-S01] Accept uses the existing pair protocol

- **WHEN** an explicit Accept commit succeeds and the application service requests persistence
- **THEN** the existing adapter SHALL write PNG and JSON through the pair-consistent temporary-file protocol to the host-resolved output path
- **AND** a loader SHALL observe an accepted pair only after the sidecar pointer is published
- **AND** the output path MUST have come from the host process, never from the WebView

#### Scenario: [DSS-R019-S02] Needs Review stays out of training data

- **WHEN** an explicit Needs Review outcome is persisted
- **THEN** the existing review adapter path SHALL record `training_eligible=false`
- **AND** the accepted loader MUST NOT enumerate it as training data

#### Scenario: [DSS-R019-S03] Sidecar does not add a second mask store

- **WHEN** a mask is shown in the UI or recovered after save
- **THEN** the bytes SHALL originate from the session snapshot, a short-lived asset token, or a loader-validated persisted pair
- **AND** the transport layer MUST NOT keep an authoritative duplicate mask database

### Requirement: [DSS-R020] Sidecar MUST NOT add GPU, remote services, runtime model download, or a second core store

The desktop sidecar remains an offline CPU transport. It MUST NOT enable GPU inference, cloud inference, remote model or VLM services, runtime model download, a second mask store, or a hidden multi-provider hot path. Missing models MUST surface as a diagnostic setup/backend-unavailable state instead of a background network fetch.

#### Scenario: [DSS-R020-S01] Offline CPU path does not call remote services

- **WHEN** the sidecar handles health, dataset open, proposal, refinement, persistence, or asset fetch on a network-blocked machine
- **THEN** it MUST complete or fail locally
- **AND** it MUST NOT download a model, call a hosted inference API, or require an account login

#### Scenario: [DSS-R020-S02] Missing approved model does not download

- **WHEN** no approved checksum-verified checkpoint is available at startup or first backend use
- **THEN** the sidecar SHALL report `engine_unavailable` and a diagnostic setup state
- **AND** it MUST NOT fetch weights from the network

#### Scenario: [DSS-R020-S03] GPU and second stores remain prohibited

- **WHEN** configuration or code paths are inspected for the production sidecar
- **THEN** they MUST NOT require CUDA, a GPU runtime, or a remote provider
- **AND** they MUST NOT introduce a sidecar-owned authoritative mask store separate from core and existing persistence adapters
