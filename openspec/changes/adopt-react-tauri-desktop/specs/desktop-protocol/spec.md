## ADDED Requirements

### Requirement: [DTP-R001] Protocol version negotiation

The desktop transport SHALL identify itself with `protocol_version` equal to the string `1.0`. Every control-plane request, including health/handshake, GET-equivalent reads, list, and asset-get, SHALL carry `protocol_version` in the typed envelope or header defined by the protocol schema. The sidecar and host MUST compare the declared version to `1.0` before applying any operation, opening a session, emitting a job event, or issuing an asset token. A missing, empty, unknown, or otherwise incompatible `protocol_version` MUST fail closed: the receiver SHALL NOT apply the request, SHALL NOT mutate session state, and SHALL return the typed error code `protocol_version_mismatch`. Compatible `1.0` peers SHALL complete handshake and proceed. The transport MUST NOT coerce, truncate, or silently reinterpret an unrecognized version as `1.0`. Reads MUST NOT increment revision.

#### Scenario: [DTP-R001-S01] Compatible 1.0 handshake succeeds

- **WHEN** a control-plane health or handshake request declares `protocol_version` `"1.0"`
- **THEN** the sidecar SHALL accept the request as version-compatible
- **AND** SHALL return a health payload that also declares `protocol_version` `"1.0"`
- **AND** SHALL remain available for subsequent `1.0` control, event, and data-plane traffic

#### Scenario: [DTP-R001-S02] Unknown version fails closed

- **WHEN** a request declares `protocol_version` as a value other than `"1.0"`, including a future major version or a non-semver token
- **THEN** the receiver SHALL reject the request with error code `protocol_version_mismatch`
- **AND** SHALL NOT create a session, start a job, write persistence, or issue an asset token

#### Scenario: [DTP-R001-S03] Missing version fails closed

- **WHEN** a control-plane request omits `protocol_version` or sends it empty or null
- **THEN** the receiver SHALL reject the request with error code `protocol_version_mismatch`
- **AND** SHALL leave all session, job, and asset state unchanged

#### Scenario: [DTP-R001-S04] Incompatible version cannot be coerced

- **WHEN** a request declares a version that shares a prefix with `1.0` but is not exactly `"1.0"`, such as `"1"`, `"1.0.0"`, `"1.1"`, or `"v1.0"`
- **THEN** the receiver SHALL treat it as incompatible and fail closed with `protocol_version_mismatch`
- **AND** MUST NOT normalize the value to `"1.0"`

#### Scenario: [DTP-R001-S05] Reads carry protocol_version and do not increment revision

- **WHEN** `health`, `sessions.get`, `datasets.list_items`, or `assets.get` is issued with `protocol_version` `"1.0"` against a live session at revision `r`
- **THEN** the receiver SHALL require `protocol_version` in the typed envelope or header
- **AND** a successful response SHALL leave revision equal to `r`

### Requirement: [DTP-R002] Control plane is small JSON over a frozen operation set

The control plane SHALL carry only small JSON documents for desktop operations. The frozen conceptual operations are `health`, `datasets.open`, `datasets.list_items`, `sessions.create`, `sessions.get`, `sessions.lock_roi`, `sessions.propose`, `sessions.select`, `sessions.refine`, `sessions.edit`, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.expand_roi`, `sessions.acknowledge_warning`, `sessions.accept`, `sessions.needs_review`, `sessions.close`, `jobs.cancel`, and `assets.get`. These names describe transport shape. The desktop protocol MUST map each operation onto the existing application and core methods without changing candidate ranking, ROI geometry, MobileSAM behavior, Accept validation, Needs Review semantics, or persistence schemas. Select, undo, manual-empty, Expand ROI, warning acknowledgement, ROI lock, and session close MUST be addressed by these frozen operations; the protocol MUST NOT leave those mutations to React-owned session state. The control plane MUST NOT carry images, binary masks, embeddings, logits, or giant integer arrays. Production control traffic MUST travel React typed client to Tauri host to the Python sidecar; the protocol MUST NOT treat a React-direct sidecar URL, cloud inference endpoint, GPU worker, or portal/iframe RPC as an allowed production path.

#### Scenario: [DTP-R002-S01] Frozen operations are addressable as small JSON

- **WHEN** a compatible client issues `health`, dataset open or list, session create, get, lock-roi, propose, select, refine, edit, undo, begin-manual-empty, expand-roi, acknowledge-warning, accept, needs-review, close, job cancel, or asset get
- **THEN** the control plane SHALL accept each as a small JSON request or a tokenized asset fetch
- **AND** SHALL NOT require a different public operation set to complete the annotation loop

#### Scenario: [DTP-R002-S02] Binary payloads are rejected on the control plane

- **WHEN** a caller embeds a base64 image, a base64 mask, or a dense pixel/integer array in a control-plane JSON body
- **THEN** the receiver SHALL reject the request with `validation_failed`
- **AND** SHALL NOT decode the payload as an annotation mask or image

#### Scenario: [DTP-R002-S03] Transport mapping preserves core semantics

- **WHEN** `sessions.lock_roi`, `sessions.propose`, `sessions.select`, `sessions.refine`, `sessions.edit`, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.expand_roi`, `sessions.acknowledge_warning`, `sessions.accept`, or `sessions.needs_review` succeeds on the desktop protocol
- **THEN** the sidecar SHALL invoke the existing session operations with unchanged ROI, candidate, Accept, and review rules
- **AND** SHALL NOT introduce a second ranking, geometry, selection, undo, or validation implementation in the transport layer or in React

#### Scenario: [DTP-R002-S04] Unknown operations fail typed

- **WHEN** a client requests an operation outside the frozen set, including portal, plugin, GPU, or cloud inference operations
- **THEN** the receiver SHALL reject it with `unsupported_operation`
- **AND** SHALL NOT forward it to core, a remote service, or a GPU backend

### Requirement: [DTP-R003] Mutation envelope and authoritative revision

Every control-plane request, including GET-equivalent reads, SHALL include `protocol_version` in the typed envelope or header defined by the protocol schema. Every mutation request SHALL also include a unique `request_id`, `session_id` when a desktop protocol session already exists, and `base_revision` when the mutation is snapshot-mutating. Session-creating mutations have no prior session and SHALL omit `session_id`; they SHALL send `base_revision` `0`. Non-session mutations such as `datasets.open` SHALL include `protocol_version` and `request_id` and MUST NOT invent a `session_id`. A successful snapshot-mutating operation MUST return the new authoritative `revision` owned by the Python session (protocol `revision` `0` while the public workflow state is `IMAGE_OPEN`). Read operations `health`, `sessions.get`, `datasets.list_items`, and `assets.get` MUST NOT increment `revision`. No read, list, or asset-get increments revision. The protocol MUST NOT allow the UI or host to assign or rewrite the authoritative revision. `jobs.cancel` is job-scoped and is not a snapshot-mutating operation under this requirement.

#### Scenario: [DTP-R003-S01] Successful session mutation returns the new revision

- **WHEN** a current snapshot-mutating request includes `protocol_version` `"1.0"`, a unique `request_id`, the existing `session_id`, and a `base_revision` equal to the session's current revision
- **THEN** the sidecar SHALL apply the mutation through existing session ownership
- **AND** SHALL return the new authoritative `revision` in the success response
- **AND** that `revision` SHALL match the Python session's current revision (`0` if still `IMAGE_OPEN`)

#### Scenario: [DTP-R003-S02] Incomplete mutation envelope is rejected

- **WHEN** a snapshot-mutating session operation omits `request_id`, omits `session_id` after a desktop protocol session exists, or omits `base_revision`
- **THEN** the sidecar SHALL reject the request with `validation_failed`
- **AND** SHALL NOT change session state or start a job

#### Scenario: [DTP-R003-S03] Session create opens IMAGE_OPEN at protocol revision zero

- **WHEN** `sessions.create` is issued with `protocol_version` `"1.0"`, a unique `request_id`, no `session_id`, and `base_revision` `0`
- **THEN** a successful create SHALL return a new `protocol_session_id` usable as `session_id` and authoritative protocol `revision` `0`
- **AND** SHALL NOT call `SegVisionEngine.start`, SHALL NOT mint core revision `1`, and SHALL NOT reuse another image's session identity or encoded state

#### Scenario: [DTP-R003-S04] Reads, lists, and asset-get do not mint a new revision

- **WHEN** `health`, `sessions.get`, `datasets.list_items`, or `assets.get` succeeds against a session at revision `r`
- **THEN** the response SHALL report revision `r` unchanged
- **AND** SHALL NOT create a job or candidate as a side effect of the read

### Requirement: [DTP-R004] Stale base revision cannot overwrite

A snapshot-mutating session operation whose `base_revision` is not exactly the session's current revision MUST fail with typed error code `revision_conflict`. On `revision_conflict` the sidecar MUST NOT apply the mutation, MUST NOT overwrite masks, candidates, prompts, local edits, Accept results, or review results, and MUST NOT treat the request as success. The client MUST re-fetch the authoritative `sessions.get` snapshot and MUST NOT retry the same body against a newer revision without reconciling. Silent overwrite is forbidden. Snapshot-mutating operations include `sessions.lock_roi`, `sessions.propose`, `sessions.select`, `sessions.refine`, `sessions.edit`, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.expand_roi`, `sessions.acknowledge_warning`, `sessions.accept`, `sessions.needs_review`, and `sessions.close`. `jobs.cancel` remains job-scoped: it MUST carry `session_id` and `job_id`, MUST still be attempted for a job that belongs to the given `session_id` even if the session revision has advanced, MUST NOT return `revision_conflict` solely because `base_revision` is old, and MUST NOT write a new snapshot or candidates.

#### Scenario: [DTP-R004-S01] Current base revision is applied once

- **WHEN** two otherwise valid snapshot-mutating edits are sent in sequence and the second uses the `revision` returned by the first
- **THEN** both SHALL succeed in order
- **AND** the second success revision SHALL be strictly greater than the first

#### Scenario: [DTP-R004-S02] Stale mutation is conflicted

- **WHEN** a lock-roi, propose, select, refine, edit, undo, begin-manual-empty, expand-roi, acknowledge-warning, accept, needs-review, or close request carries `base_revision` older than the current session revision
- **THEN** the sidecar SHALL return `revision_conflict`
- **AND** the current mask, candidate selection, and revision SHALL remain byte-for-byte unchanged

#### Scenario: [DTP-R004-S03] Conflict requires a snapshot refetch

- **WHEN** a client receives `revision_conflict`
- **THEN** the client MUST obtain a fresh `sessions.get` snapshot before issuing another snapshot-mutating session operation
- **AND** MUST NOT apply the rejected payload as if the server had accepted it

#### Scenario: [DTP-R004-S04] Concurrent stale writers cannot clobber

- **WHEN** two snapshot-mutating operations share the same stale `base_revision` after the session has already advanced
- **THEN** both SHALL fail with `revision_conflict`
- **AND** neither SHALL become the authoritative mask or Accept result

#### Scenario: [DTP-R004-S05] Cancel is not revision_conflict solely because the session advanced

- **WHEN** `jobs.cancel` carries `session_id` and `job_id` for a still-known job after the session revision has advanced, even if `base_revision` is older than the current snapshot
- **THEN** the sidecar MUST still attempt cancellation
- **AND** MUST NOT return `revision_conflict` solely because `base_revision` is old
- **AND** MUST NOT write a new snapshot or candidates

### Requirement: [DTP-R005] Event plane envelope, kinds, and host-owned transport

Job and background events SHALL travel on a distinct event plane from control JSON. Every event MUST include `event_id`, `request_id`, `job_id`, `session_id`, `revision`, `kind`, and `timestamp`. `kind` MUST be one of `progress`, `completed`, `cancelled`, `stale`, or `failed` in protocol version `1.0`. Additional payload fields MAY describe displayable progress or a typed error, but they MUST NOT carry embeddings, logits, raw Python tracebacks, or binary masks. Events MUST be correlatable to the originating `request_id` and to the Python-owned `job_id`, `session_id`, and `revision`. Duplicate `event_id` values MUST be treated as the same event. The production event plane SHALL be sidecar emission on loopback using host-owned SSE or an equivalent host-only HTTP channel, authenticated with the per-launch secret. Tauri SHALL forward typed events to React. React MUST NOT subscribe to sidecar event URLs directly. Shared memory remains out of protocol `1.0`.

#### Scenario: [DTP-R005-S01] Completed event carries the required envelope

- **WHEN** a proposal or refinement job finishes successfully for the current revision
- **THEN** the event plane SHALL emit a `completed` event that includes `event_id`, `request_id`, `job_id`, `session_id`, `revision`, `kind`, and `timestamp`
- **AND** the `revision` SHALL equal the session revision that owned the job

#### Scenario: [DTP-R005-S02] Required kinds are representable

- **WHEN** a job reports in-flight work, success, user or system cancel, supersession by a newer revision, or terminal failure
- **THEN** the sidecar SHALL emit `progress`, `completed`, `cancelled`, `stale`, or `failed` respectively
- **AND** SHALL NOT substitute an untyped string or a Python exception name for `kind`

#### Scenario: [DTP-R005-S03] Malformed events are not delivered as valid

- **WHEN** an event omits `event_id`, `request_id`, `job_id`, `session_id`, `revision`, `kind`, or `timestamp`, or uses a `kind` outside the frozen set
- **THEN** contract validation SHALL fail that event
- **AND** UI receivers MUST discard it and MUST NOT treat it as `completed`

#### Scenario: [DTP-R005-S04] Events correlate without leaking engine tensors

- **WHEN** a `failed` or `progress` event is emitted
- **THEN** it SHALL include the originating `request_id` and `job_id`
- **AND** its payload SHALL NOT include embeddings, logits, tensor names, or a Python stack trace as the UI contract

#### Scenario: [DTP-R005-S05] Production events are host-owned loopback, not React-direct

- **WHEN** the sidecar emits a job or session event in production
- **THEN** it SHALL emit on loopback over host-owned SSE or an equivalent host-only HTTP channel authenticated with the current per-launch secret
- **AND** the Tauri host SHALL forward a typed event to React
- **AND** React MUST NOT open or subscribe to a sidecar event URL

### Requirement: [DTP-R006] Dual stale rejection of events and masks

Stale rejection is mandatory on both the Python runtime and every desktop event receiver. A job result or event whose `session_id` does not match the current session, or whose `revision` is older than the current session revision, MUST be discarded. Receivers MUST NOT paint, select, refine, edit, or Accept a mask from a stale `completed` event. The Python session remains the only source of truth; a UI cache MUST yield to the authoritative snapshot after discard. A current-revision `completed` event MAY update the projection only after the receiver confirms `session_id` and `revision` still match.

#### Scenario: [DTP-R006-S01] Receiver discards an older completed event

- **WHEN** the current session revision is `r + 1` and a `completed` event arrives tagged with revision `r`
- **THEN** the React/Tauri receiver MUST discard the event
- **AND** MUST NOT draw that event's mask onto the canvas

#### Scenario: [DTP-R006-S02] Python rejects the stale job first

- **WHEN** a worker finishes a job for revision `r` after the session has advanced to `r + 1`
- **THEN** the Python runtime MUST mark or emit the result as stale
- **AND** MUST NOT install the result as the current candidate set

#### Scenario: [DTP-R006-S03] Stale completed cannot become Acceptable

- **WHEN** a discarded or `stale` job is the only completed inference for a prior revision
- **THEN** the protocol SHALL expose no current candidates from that job
- **AND** `sessions.accept` MUST NOT succeed against that job's masks

#### Scenario: [DTP-R006-S04] Current-revision completion remains eligible

- **WHEN** a `completed` event matches the current `session_id` and current `revision`
- **THEN** the receiver MAY project the authoritative snapshot or asset tokens from that revision
- **AND** MUST still refuse any later event for an older revision

### Requirement: [DTP-R007] Binary data plane uses opaque assets

Images and binary masks MUST move on a data plane of opaque, short-lived asset tokens or URIs. The control and event planes MUST NOT encode images or masks as JSON base64, data URLs, or giant integer arrays. Overlay composition SHALL occur in the UI from source image plus binary mask; the protocol MUST NOT require a precomposited full-frame overlay asset. Embeddings, low-resolution logits, and other model tensors MUST NOT leave the Python process on any plane. `assets.get` is the only protocol operation that returns image or mask bytes, and it MUST do so as binary content identified by token, not as JSON. Mask bytes on the data plane for display and commit previews SHALL be PNG with pixel values `{0,255}`. Source images SHALL remain PNG, JPEG, or WebP as stored. Media type on asset responses MUST be explicit.

#### Scenario: [DTP-R007-S01] Image bytes are fetched by token

- **WHEN** a session snapshot refers to a source image or thumbnail
- **THEN** the snapshot SHALL include an opaque asset token or URI rather than pixel arrays
- **AND** `assets.get` SHALL return the image bytes for a valid token
- **AND** the response media type SHALL be explicit (`image/png`, `image/jpeg`, or `image/webp` as stored)

#### Scenario: [DTP-R007-S02] Mask bytes are fetched by token

- **WHEN** a current candidate mask must be displayed
- **THEN** the control response SHALL provide an opaque mask asset token
- **AND** SHALL NOT include the mask as base64, a boolean JSON array, or packed integer rows
- **AND** `assets.get` SHALL return PNG bytes with pixel values `{0,255}` and media type `image/png`

#### Scenario: [DTP-R007-S03] Tensor leakage is forbidden

- **WHEN** any control response, event, or asset document is inspected
- **THEN** it MUST NOT contain embeddings, logits, tensor names, normalization weights, or model input dimensions
- **AND** callers SHALL continue to address candidates only by opaque candidate IDs as the session contract already requires

#### Scenario: [DTP-R007-S04] Overlay is composed locally

- **WHEN** the UI needs an image-plus-mask overlay
- **THEN** it MUST compose from the image asset and the mask asset
- **AND** the sidecar MUST NOT be required to transmit a precomposited full-image overlay to satisfy v1 display

### Requirement: [DTP-R008] Asset tokens are bound, short-lived, and path-safe

An asset token MUST bind `session_id`, `revision`, asset kind, and an expiry. Asset kind SHALL distinguish at least source image, thumbnail, and binary mask. `assets.get` MUST redeem a token only when the binding still matches a live session revision and the token has not expired. Tokens MUST be unguessable and MUST NOT embed a filesystem path. Requests that include `..`, absolute drive paths, UNC paths, or any other caller-supplied filesystem path in place of or inside a token MUST be rejected. A valid token MUST NOT authorize arbitrary file reads outside the bound asset.

#### Scenario: [DTP-R008-S01] Bound token returns the matching asset

- **WHEN** `assets.get` receives an unexpired token issued for the current session, revision, and declared kind
- **THEN** the data plane SHALL return only that asset's bytes
- **AND** SHALL NOT return a different revision's mask or another session's image

#### Scenario: [DTP-R008-S02] Expired or rebound token is rejected

- **WHEN** a token is expired, or its bound `session_id` or `revision` no longer matches, or its kind does not match the requested kind
- **THEN** `assets.get` SHALL fail with `not_found` or `unauthorized`
- **AND** SHALL NOT stream file bytes

#### Scenario: [DTP-R008-S03] Path traversal is rejected

- **WHEN** a caller supplies `..`, an absolute path, a UNC path, or a relative filesystem path as the asset identifier
- **THEN** the host and sidecar MUST reject the request
- **AND** MUST NOT read that path

#### Scenario: [DTP-R008-S04] Token does not unlock arbitrary files

- **WHEN** a valid mask token is presented together with a query or header that names an unrelated local file
- **THEN** the data plane SHALL ignore the extra path
- **AND** SHALL return only the bound asset or a typed error, never the unrelated file

### Requirement: [DTP-R009] Single OpenAPI and event-schema source of truth

Protocol types SHALL have one source of truth: an OpenAPI 3.1 document for control-plane requests, responses, and error objects, plus a JSON Schema union for event-plane kinds. TypeScript, Rust, and Python MUST consume that source; they MUST NOT each hand-write a divergent set of operation names, event kinds, or error codes. Contract tests MUST load the published schemas and the language bindings and MUST fail when an enum, required field, or error code is missing, extra, or renamed on one side. A green contract suite is required before a protocol change is treated as complete.

#### Scenario: [DTP-R009-S01] Published schemas define the wire types

- **WHEN** a new client or sidecar build is produced
- **THEN** its request, response, event, and error types SHALL be generated from or validated against the OpenAPI 3.1 document and the event JSON Schema union
- **AND** those documents SHALL be the only normative type catalog for protocol version `1.0`

#### Scenario: [DTP-R009-S02] Hand-written divergence fails contract tests

- **WHEN** TypeScript, Rust, or Python adds, removes, or renames an operation, event `kind`, or error code that is not identical in the published schemas
- **THEN** the protocol contract tests MUST fail
- **AND** the change MUST NOT be reported as schema-compatible

#### Scenario: [DTP-R009-S03] Event union mismatch is detectable

- **WHEN** a sidecar emits a `kind` that is absent from the JSON Schema event union, or a client enumerates a `kind` the sidecar cannot emit
- **THEN** contract tests MUST fail
- **AND** the extra kind MUST NOT be treated as an informal extension of version `1.0`

#### Scenario: [DTP-R009-S04] Required envelope fields are schema-enforced

- **WHEN** a fixture omits a mutation field required by DTP-R003 or an event field required by DTP-R005
- **THEN** schema validation SHALL reject the fixture
- **AND** contract tests MUST fail

### Requirement: [DTP-R010] Typed error codes are the UI contract

Control-plane failures SHALL return a typed error object with a stable `code` from the frozen set of eight sidecar JSON UI codes: `protocol_version_mismatch`, `revision_conflict`, `unauthorized`, `engine_unavailable`, `validation_failed`, `unsupported_operation`, `not_found`, and `stale_job`. The UI contract is that code plus an operator-safe message. Python stack traces, exception class names, and sidecar internals MUST NOT be the UI error contract and MUST NOT be required to render recovery. `unauthorized` SHALL cover missing or invalid per-launch credentials. `engine_unavailable` SHALL cover a sidecar or engine that cannot serve. `validation_failed` SHALL cover schema and input violations. `unsupported_operation` SHALL preserve existing core unsupported-operation meaning. `not_found` SHALL cover unknown session, job, dataset, or asset identity. `stale_job` SHALL cover attempts to fetch or apply a job that is no longer current. Core and application failures SHALL map many-to-one onto those eight codes as specified by DTP-R016. Windows path and IO failures surfaced through host commands use host-stable codes `grant_invalid` and `filesystem_error`; the host MAY wrap those before the React client; they are not extra sidecar JSON codes.

#### Scenario: [DTP-R010-S01] Frozen codes cover the desktop failure modes

- **WHEN** a client performs version mismatch, stale mutation, missing secret, down engine, bad JSON, unsupported candidate operation, unknown id, or stale job fetch
- **THEN** the response `code` SHALL be the matching frozen value listed in this requirement
- **AND** SHALL be one of the eight codes, not an ad-hoc string

#### Scenario: [DTP-R010-S02] Tracebacks are not the UI contract

- **WHEN** the sidecar raises an internal Python exception while handling a control request
- **THEN** the transport SHALL still return a typed `code` from the frozen set of eight
- **AND** the payload consumed by the UI MUST NOT require a Python traceback to decide retry, refetch, or freeze-mutation behavior

#### Scenario: [DTP-R010-S03] Unauthorized rejects unauthenticated control access

- **WHEN** a control or asset request lacks the current launch credential or presents an invalid credential
- **THEN** the sidecar SHALL return `unauthorized`
- **AND** SHALL NOT apply the mutation or stream the asset

#### Scenario: [DTP-R010-S04] Engine unavailability is explicit

- **WHEN** the engine process is not ready, has crashed, or cannot load an approved backend
- **THEN** control mutations SHALL fail with `engine_unavailable`
- **AND** the protocol MUST NOT report those requests as `completed` jobs or successful Accept

### Requirement: [DTP-R011] Cancel is an observable non-success state

`jobs.cancel` SHALL request cancellation of a not-yet-terminal job and SHALL yield an observable `cancelled` state on the event plane when cancellation takes effect. Cancel is not success: a cancelled job MUST NOT be reported as `completed`, MUST NOT install candidates, MUST NOT paint a mask, and MUST NOT produce an Accept or training-eligible result. Cancel of an already `completed`, `failed`, `cancelled`, or `stale` job SHALL be idempotent and MUST still not create candidates or Accept. A late worker result after cancel MUST be rejected as `stale` or discarded and MUST NOT outrank the cancelled state. The request MUST include `session_id` and `job_id`. Cancellation MUST still be attempted after the session revision advances and MUST NOT return `revision_conflict` solely because `base_revision` is old.

#### Scenario: [DTP-R011-S01] Cancel emits cancelled rather than completed

- **WHEN** the client cancels an in-flight proposal or refinement job that has not yet produced a current-revision result
- **THEN** the event plane SHALL expose `kind` `cancelled` for that `job_id`
- **AND** SHALL NOT emit a succeeding `completed` event that installs candidates for the cancelled job

#### Scenario: [DTP-R011-S02] Cancelled jobs produce no candidates

- **WHEN** cancellation of a proposal job is observed
- **THEN** `sessions.get` SHALL NOT present candidates originating from that job
- **AND** the UI MUST NOT render a mask from that job

#### Scenario: [DTP-R011-S03] Cancel cannot Accept

- **WHEN** the only inference work for a revision was cancelled
- **THEN** `sessions.accept` MUST NOT succeed against that job
- **AND** the protocol MUST NOT record an accepted training annotation from the cancelled work

#### Scenario: [DTP-R011-S04] Late completion after cancel is discarded

- **WHEN** a worker returns a mask after `jobs.cancel` for the same `job_id`
- **THEN** the result SHALL be marked `stale` or discarded
- **AND** SHALL NOT replace the cancelled observation with a successful candidate set

#### Scenario: [DTP-R011-S05] Cancel remains job-scoped after a revision bump

- **WHEN** the session revision advances while a job for that `session_id` is still cancellable
- **THEN** `jobs.cancel` with that `session_id` and `job_id` MUST still be attempted
- **AND** MUST NOT fail solely as `revision_conflict`

### Requirement: [DTP-R012] Shared memory is out of scope for protocol 1.0

Protocol version `1.0` MUST be implementable and correct using the JSON control plane, the typed event plane, and the opaque binary asset plane alone. Shared memory, memory-mapped files, and GPU IPC MUST NOT be required to open a dataset, run a session, display an image or mask, cancel a job, or Accept. Shared-memory transport remains out of scope until a measured bottleneck on real images demonstrates that the binary asset proxy is insufficient. Adding shared memory MUST be a new protocol version or OpenSpec change; it MUST NOT silently become a `1.0` dependency.

#### Scenario: [DTP-R012-S01] Annotation loop works without shared memory

- **WHEN** a desktop client performs health, dataset open, session create, lock-roi, propose, select, refine, edit, undo, asset fetch, cancel, accept, needs-review, and close using only JSON, events, and asset tokens
- **THEN** the protocol SHALL complete those operations without a shared-memory channel
- **AND** contract tests MUST NOT require a shared-memory fixture for version `1.0`

#### Scenario: [DTP-R012-S02] Missing shared memory is not an error

- **WHEN** the host and sidecar are started with no shared-memory region configured
- **THEN** they MUST still handshake at `protocol_version` `"1.0"`
- **AND** MUST NOT fail health with `unsupported_operation` merely because shared memory is absent

#### Scenario: [DTP-R012-S03] Shared memory cannot be smuggled as 1.0

- **WHEN** a build requires a memory-mapped file or shared-memory handle to fetch a mask or image
- **THEN** that build SHALL be treated as outside protocol `1.0`
- **AND** protocol contract tests for this change MUST fail rather than relax the data-plane rules

### Requirement: [DTP-R013] Two-phase desktop session create then lock_roi

`sessions.create` SHALL open a desktop protocol session for an image. The public workflow state SHALL be `IMAGE_OPEN`. `sessions.create` MUST NOT call `SegVisionEngine.start` and MUST NOT mint core revision `1`. The protocol MAY use `base_revision` `0`, and a successful create snapshot SHALL report `revision` `0`. That snapshot MUST show no `user_roi_full` yet and MUST NOT claim Accept or Needs Review eligibility. `sessions.lock_roi` is the only desktop protocol operation that invokes `SegVisionEngine.start`. `sessions.lock_roi` MUST supply `class_id` and, when a recipe is present, recipe identity sourced from dataset metadata, not React-invented tensors, together with a valid full-image ROI. A successful lock SHALL mint core revision `1` and transition public workflow state to `ROI_LOCKED`, after which proposal work MAY proceed. React MUST NOT invent a second IMAGE_OPEN or ROI-lock owner.

#### Scenario: [DTP-R013-S01] Create does not start the engine

- **WHEN** `sessions.create` succeeds for a current image identity
- **THEN** the snapshot SHALL report public workflow state `IMAGE_OPEN` and `revision` `0`
- **AND** SHALL omit `user_roi_full`
- **AND** SHALL NOT report Accept or Needs Review as eligible
- **AND** the sidecar MUST NOT have called `SegVisionEngine.start`

#### Scenario: [DTP-R013-S02] lock_roi is the only start call

- **WHEN** `sessions.lock_roi` is issued against an `IMAGE_OPEN` session with `class_id` from dataset metadata and a valid full-image ROI
- **THEN** the sidecar SHALL call `SegVisionEngine.start` with that `class_id` and ROI
- **AND** a successful lock SHALL mint core revision `1` and public workflow state `ROI_LOCKED`

#### Scenario: [DTP-R013-S03] lock_roi requires class_id from dataset metadata

- **WHEN** `sessions.lock_roi` omits `class_id` or supplies a class or recipe tensor invented by React rather than dataset metadata
- **THEN** the sidecar SHALL reject the request with `validation_failed`
- **AND** SHALL NOT call `SegVisionEngine.start`

#### Scenario: [DTP-R013-S04] No other operation starts the engine

- **WHEN** `sessions.create`, `sessions.propose`, `sessions.select`, or `sessions.get` is issued
- **THEN** none of those operations SHALL invoke `SegVisionEngine.start`
- **AND** core revision `1` SHALL exist only after a successful `sessions.lock_roi`

### Requirement: [DTP-R014] sessions.get snapshot 1.0 field contract

A successful `sessions.get` snapshot in protocol `1.0` MUST include `protocol_session_id`, `workflow_state`, and `revision` (`0` if `IMAGE_OPEN`). It MUST include `user_roi_full` and `crop_rect_full` when they exist, the selected candidate id, candidate summaries with capability flags, the warning list, the job summary, image and mask asset tokens, `class_id` when bound, and the annotation timer origin when the first ROI has been locked. Reads MUST NOT increment revision. The snapshot MUST NOT claim Accept or Needs Review eligibility while `workflow_state` is `IMAGE_OPEN` or while `user_roi_full` is absent.

#### Scenario: [DTP-R014-S01] IMAGE_OPEN snapshot fields

- **WHEN** `sessions.get` succeeds for a protocol session that has not locked an ROI
- **THEN** the snapshot SHALL include `protocol_session_id`, `workflow_state` `IMAGE_OPEN`, `revision` `0`, image asset tokens, and job summary
- **AND** SHALL NOT include `user_roi_full`
- **AND** SHALL NOT claim Accept or Needs Review eligibility

#### Scenario: [DTP-R014-S02] ROI_LOCKED and later snapshot fields

- **WHEN** `sessions.get` succeeds after a successful `sessions.lock_roi`
- **THEN** the snapshot SHALL include `protocol_session_id`, `workflow_state`, `revision` at least `1`, `user_roi_full`, `crop_rect_full`, `class_id`, selected candidate id when a selection exists, candidate summaries with capability flags, warning list, job summary, image and mask asset tokens, and annotation timer origin `first_roi_locked`

#### Scenario: [DTP-R014-S03] Snapshot get does not advance revision

- **WHEN** `sessions.get` is issued twice without an intervening snapshot-mutating operation
- **THEN** both responses SHALL report the same `revision`
- **AND** SHALL NOT create jobs or candidates

### Requirement: [DTP-R015] Health success payload

A successful `health` response MUST include `protocol_version`, sidecar readiness, and an approved-backend presence and capability summary. When the approved checkpoint is missing or invalid, the payload MUST include a diagnostic setup state and MUST NOT download a replacement. `health` MUST NOT increment revision.

#### Scenario: [DTP-R015-S01] Ready health reports backend capability

- **WHEN** `health` succeeds and an approved checksum-valid backend is present
- **THEN** the payload SHALL include `protocol_version` `"1.0"`, sidecar readiness ready, and an approved-backend presence/capability summary
- **AND** SHALL NOT include the listen port or per-launch secret

#### Scenario: [DTP-R015-S02] Missing or invalid checkpoint is diagnostic

- **WHEN** `health` succeeds but the approved checkpoint is missing or checksum-invalid
- **THEN** the payload SHALL include `protocol_version` `"1.0"`, sidecar readiness, approved-backend absence, and a diagnostic setup state
- **AND** the sidecar MUST NOT download weights

### Requirement: [DTP-R016] Many-to-one core exception map onto eight protocol codes

The eight sidecar JSON UI `code` values remain exhaustive. The adapter SHALL map existing typed failures onto those codes as follows: `StaleRevision` for a late job maps to `stale_job`; a client `base_revision` behind the current snapshot maps to `revision_conflict`; `InvalidRoi`, `RecipeSchemaError`, `RecipeClassMismatch`, and crop-candidate validation failure map to `validation_failed`; `EmbeddingExpired` maps to `stale_job`; `BackendUnavailable` and a missing, unapproved, or checksum-invalid model map to `engine_unavailable`; `UnsupportedOperation` maps to `unsupported_operation`; unknown or expired grant identity maps to `unauthorized` or `not_found` as appropriate. Untyped exceptions MUST still use one of the eight codes and MUST NOT leak a traceback. This map is many-to-one: those core types MUST NOT become extra protocol codes.

#### Scenario: [DTP-R016-S01] Validation-class core errors share validation_failed

- **WHEN** core or application raises `InvalidRoi`, `RecipeSchemaError`, `RecipeClassMismatch`, or a crop-candidate validation failure
- **THEN** the sidecar JSON `code` SHALL be `validation_failed`

#### Scenario: [DTP-R016-S02] Late job StaleRevision maps to stale_job

- **WHEN** a late job surfaces `StaleRevision`
- **THEN** the sidecar JSON `code` SHALL be `stale_job`

#### Scenario: [DTP-R016-S03] Client base_revision behind snapshot is revision_conflict

- **WHEN** the client's `base_revision` is behind the current snapshot
- **THEN** the sidecar JSON `code` SHALL be `revision_conflict`

#### Scenario: [DTP-R016-S04] EmbeddingExpired maps to stale_job

- **WHEN** the failure is `EmbeddingExpired`
- **THEN** the sidecar JSON `code` SHALL be `stale_job`

#### Scenario: [DTP-R016-S05] Backend and model failures map to engine_unavailable

- **WHEN** the failure is `BackendUnavailable` or a missing, unapproved, or checksum-invalid model
- **THEN** the sidecar JSON `code` SHALL be `engine_unavailable`

#### Scenario: [DTP-R016-S06] UnsupportedOperation maps to unsupported_operation

- **WHEN** core raises `UnsupportedOperation`
- **THEN** the sidecar JSON `code` SHALL be `unsupported_operation`

#### Scenario: [DTP-R016-S07] Unknown or expired grant maps to unauthorized or not_found

- **WHEN** the grant is unknown or expired
- **THEN** the `code` SHALL be `unauthorized` or `not_found` as appropriate

#### Scenario: [DTP-R016-S08] Host IO uses host-stable codes

- **WHEN** a Windows path or IO failure is surfaced through a host command
- **THEN** the host MAY use `grant_invalid` or `filesystem_error` and MAY wrap before the React client
- **AND** those host codes MUST NOT be added as sidecar JSON protocol codes

### Requirement: [DTP-R017] Grant identifiers on the control plane

React SHALL send `grant_id` only. `datasets.open` SHALL take a dataset `grant_id`. An output folder SHALL be a host grant passed into persistence commands and MUST never be a raw path from the WebView. An optional `checkpoint` grant is non-approving: Python still checksums. The host resolves the canonical path; the sidecar receives that path from the host process, never from the WebView.

#### Scenario: [DTP-R017-S01] Dataset open uses grant_id

- **WHEN** `datasets.open` is issued
- **THEN** the control JSON SHALL include a dataset `grant_id` and MUST NOT include a WebView-supplied filesystem path

#### Scenario: [DTP-R017-S02] Output path is a host grant

- **WHEN** Accept or Needs Review persistence is requested
- **THEN** the output location SHALL be identified to the host as an output `grant_id`
- **AND** the WebView MUST NOT supply a raw output path

#### Scenario: [DTP-R017-S03] Checkpoint grant does not approve

- **WHEN** an optional checkpoint grant is presented
- **THEN** Python SHALL still perform approval-status and SHA-256 verification
- **AND** the grant MUST NOT be treated as model approval
