## ADDED Requirements

### Requirement: [DTH-R001] Tauri is the only production React-to-engine bridge
The production desktop application SHALL route every React control request, event subscription, and binary asset fetch to the Python sidecar exclusively through the Tauri 2 Rust host. The React UI MUST NOT discover, store, display, or persist the sidecar listen port or per-launch secret. The host MUST inject sidecar authentication on the proxy and MUST NOT return that credential to the WebView.

#### Scenario: [DTH-R001-S01] Production UI has no sidecar endpoint
- **WHEN** the production React bundle and its runtime configuration are inspected after a successful sidecar launch
- **THEN** they MUST NOT contain the sidecar port, per-launch secret, or a reachable sidecar base URL
- **AND** React MUST be able to invoke only typed host commands and load only host-issued opaque asset URIs

#### Scenario: [DTH-R001-S02] Host injects authentication on proxy
- **WHEN** React issues an allowed control command that the host forwards to the sidecar
- **THEN** the Rust host MUST add the current per-launch secret to the sidecar request
- **AND** the command response, event payload, and frontend store MUST NOT include that secret

#### Scenario: [DTH-R001-S03] Production direct sidecar access is forbidden
- **WHEN** production React or WebView code attempts to open a TCP or HTTP connection to `127.0.0.1` on the sidecar port
- **THEN** production CSP and host policy MUST prevent the connection
- **AND** the host MUST NOT expose a production API that returns the sidecar port or secret

### Requirement: [DTH-R002] Loopback random port and ephemeral secret
On each launch the host SHALL start the Python sidecar bound only to `127.0.0.1` on an OS-assigned random port. The host SHALL generate a per-launch secret for sidecar authentication. That secret MUST NOT be written to logs, settings, disk caches, crash reports, or other persisted files. A subsequent launch MUST use a new port and a new secret.

#### Scenario: [DTH-R002-S01] Sidecar binds loopback on a random port
- **WHEN** the host starts a sidecar process
- **THEN** the sidecar MUST listen on `127.0.0.1` and MUST NOT listen on `0.0.0.0` or any non-loopback interface
- **AND** the listen port MUST be chosen per launch rather than a fixed published port

#### Scenario: [DTH-R002-S02] Secret is not logged or persisted
- **WHEN** the host generates and uses a per-launch sidecar secret
- **THEN** host logs, sidecar stdout, sidecar stderr, configuration files, and diagnostic exports MUST NOT contain the secret value
- **AND** restarting the application MUST produce a different secret than the previous launch

#### Scenario: [DTH-R002-S03] LAN callers cannot use the sidecar
- **WHEN** a process on another host or a non-loopback local interface attempts to call the sidecar HTTP API
- **THEN** the attempt MUST fail because the sidecar is not bound for that address
- **AND** possession of a previous launch secret MUST NOT authenticate a later launch

### Requirement: [DTH-R003] Sidecar lifecycle without blocking the UI thread
The Tauri host SHALL start, health-check, watch, restart, and gracefully shut down the Python sidecar. Sidecar MobileSAM inference MUST run in the sidecar process. The host UI thread MUST NOT block waiting for MobileSAM inference, encoder work, or decoder work to finish.

#### Scenario: [DTH-R003-S01] Host starts and health-checks the sidecar
- **WHEN** the desktop application launches with a packaged sidecar present
- **THEN** the host SHALL spawn the sidecar, wait for a successful health check, and expose an engine-ready health summary to the UI
- **AND** that summary MUST include `protocol_version`, sidecar readiness, approved-backend presence/capability, and a diagnostic setup state when the approved checkpoint is missing or invalid
- **AND** that summary MUST NOT include the sidecar port, secret, or raw process credentials

#### Scenario: [DTH-R003-S02] Host watches a live sidecar
- **WHEN** the sidecar is running after a successful health check
- **THEN** the host MUST observe process exit, unready health, and unexpected termination
- **AND** it MUST keep a diagnostic record of the last observed sidecar state

#### Scenario: [DTH-R003-S03] UI thread stays responsive during inference
- **WHEN** React submits a proposal, refinement, or other long sidecar job that requires MobileSAM inference
- **THEN** the host MUST return from the invoking command without waiting for inference completion
- **AND** the native window MUST remain able to accept user input while the sidecar job is in progress

#### Scenario: [DTH-R003-S04] Hidden sidecar process
- **WHEN** the host starts the sidecar on Windows
- **THEN** it MUST NOT present a sidecar console window as part of the normal operator workflow
- **AND** sidecar stdout and stderr MUST still be collected for diagnostics

### Requirement: [DTH-R004] Sidecar crash recovery and verifiable draft restore
If the sidecar crashes or becomes unready, recovery SHALL follow this sequence: detect crash; UI `engine_unavailable/recovering`; freeze mutations; keep displayed pixels as non-authoritative; the host MAY auto-restart the sidecar with a new port and secret; re-handshake; restore if and only if persistence verifies a draft or published pair for the current image identity; otherwise require `sessions.create`. The host MUST NOT mark in-flight jobs completed, accepted, or persisted. “Unconditional restart” means respawn and assume the in-memory session survived; that assumption is forbidden. Auto-respawn of the process is allowed.

#### Scenario: [DTH-R004-S01] Crash freezes mutations and preserves pixels
- **WHEN** the sidecar process exits or fails health while an image and overlay are displayed
- **THEN** the host SHALL report `engine_unavailable/recovering` to React
- **AND** mutation commands MUST be rejected
- **AND** the currently displayed image and overlay pixels MUST remain visible and MUST be treated as non-authoritative
- **AND** the host MUST NOT emit a job-completed, accepted, or saved result for work that did not finish

#### Scenario: [DTH-R004-S02] Restart requires a new handshake
- **WHEN** the host auto-restarts the sidecar after a crash
- **THEN** it MUST obtain a fresh loopback port and per-launch secret, complete health check, and re-establish protocol handshake
- **AND** it MUST NOT reuse the crashed process port, secret, or in-memory session as if they were still valid
- **AND** auto-respawn MUST NOT be treated as unconditional restart of live session memory

#### Scenario: [DTH-R004-S03] Only verifiable persisted drafts are restored
- **WHEN** handshake after restart and persistence verify a draft or published pair for the current image identity
- **THEN** the host SHALL present that draft or published pair through sidecar-authored snapshot data
- **AND** in-memory, unpersisted edits from the crashed process MUST NOT be reconstructed by the host

#### Scenario: [DTH-R004-S04] Missing draft requires a new session
- **WHEN** handshake after restart finds no verifiable persisted draft or published pair for the current image identity
- **THEN** the host MUST require `sessions.create`
- **AND** it MUST NOT claim that prior candidates, jobs, or masks are still authoritative solely because the process restarted

### Requirement: [DTH-R005] Application close shuts the sidecar down
On application close the host SHALL request graceful sidecar shutdown first. If the sidecar does not exit within the configured timeout, the host MUST terminate the process. The host MUST retain the last diagnostic logs after shutdown or termination.

#### Scenario: [DTH-R005-S01] Graceful shutdown on close
- **WHEN** the operator closes the native window and the sidecar exits within the shutdown timeout
- **THEN** the host MUST send a graceful shutdown request before any forced kill
- **AND** the process MUST not remain running after the application has closed

#### Scenario: [DTH-R005-S02] Timeout then terminate
- **WHEN** the sidecar does not exit within the shutdown timeout
- **THEN** the host MUST terminate the sidecar
- **AND** the application close sequence MUST still complete

#### Scenario: [DTH-R005-S03] Diagnostic logs survive close
- **WHEN** close finishes by graceful shutdown or forced termination
- **THEN** the last host and sidecar diagnostic logs MUST remain available for later export or inspection
- **AND** those retained logs MUST still omit the per-launch secret

### Requirement: [DTH-R006] Opaque file and folder grants
React SHALL request local file or folder access only through host-owned pickers. Host grant kinds SHALL include at least `dataset`, `output`, and optional `checkpoint` (non-approving; Python still checksums). The host MUST record the user-authorized canonical path internally and MUST return only an opaque `grant_id` and a display name. React MUST NOT receive the canonical filesystem path, a path-construction API, or arbitrary filesystem access. React sends `grant_id` only; host resolves canonical path; sidecar receives the path from the host process, never from the WebView, then existence/manifest/hash checks. `datasets.open` takes a dataset `grant_id`. An output folder is a host grant passed into persistence commands, never a raw path from the WebView.

#### Scenario: [DTH-R006-S01] Picker returns grant identity only
- **WHEN** the operator selects a file or folder in the host picker
- **THEN** the host MUST store the canonical path in host memory or a host-private grant table with kind `dataset`, `output`, or optional `checkpoint`
- **AND** React MUST receive `grant_id` and display name only
- **AND** the React payload MUST NOT include the absolute path

#### Scenario: [DTH-R006-S02] Dataset open uses grant_id
- **WHEN** React asks the host to open a dataset with a valid `grant_id`
- **THEN** the host MUST resolve the recorded canonical path and pass that path only to the sidecar
- **AND** React MUST still not learn the canonical path from the command result
- **AND** React sends `grant_id` only; host resolves canonical path; sidecar receives the path from the host process, never from the WebView, then existence/manifest/hash checks

#### Scenario: [DTH-R006-S03] Unknown or revoked grant is rejected
- **WHEN** React submits a missing, expired, or revoked `grant_id`
- **THEN** the host MUST reject the command with `grant_invalid` or `not_found`/`unauthorized` as appropriate
- **AND** the sidecar MUST NOT receive an operator-supplied raw path from React

#### Scenario: [DTH-R006-S04] Picker cancellation creates no grant
- **WHEN** the operator cancels the file or folder picker
- **THEN** the host MUST NOT create a `grant_id`
- **AND** no dataset-open side effect SHALL occur

#### Scenario: [DTH-R006-S05] Output and checkpoint grants
- **WHEN** persistence needs an output folder or the operator optionally grants a checkpoint file
- **THEN** React SHALL send the output or checkpoint `grant_id` only
- **AND** the host SHALL resolve the canonical path and pass that path to the sidecar
- **AND** a checkpoint grant MUST NOT be treated as model approval

### Requirement: [DTH-R007] No generic filesystem or shell commands
The host MUST NOT expose generic `read_file`, `write_file`, or `run_command` commands to React. It MUST NOT expose a generic shell, process-spawn, or unrestricted path-read/write API. Allowed commands MUST be SegVision-specific and MUST operate only through grants, snapshots, jobs, and host-mediated assets.

#### Scenario: [DTH-R007-S01] Generic file commands are absent
- **WHEN** the production command allowlist is inspected
- **THEN** it MUST NOT contain generic `read_file`, `write_file`, or equivalent unrestricted file APIs
- **AND** a React invoke of those names MUST fail

#### Scenario: [DTH-R007-S02] Generic command execution is absent
- **WHEN** React attempts to invoke `run_command`, a shell, or an arbitrary process spawn through the host
- **THEN** the host MUST reject the invoke
- **AND** no operator-supplied executable MUST be launched

### Requirement: [DTH-R008] SegVision command allowlist, CSP, and navigation lock
The production host SHALL expose only a SegVision-specific command allowlist. The production Tauri command allowlist SHALL be exactly the frozen desktop-protocol operations in DTP-R002 plus the host-only window, grant, log, and export commands named in this capability (`window.close`, `grants.pick_folder`, `grants.pick_file`, `diagnostics.export`, and redacted `engine.health_summary`). Production CSP MUST forbid remote scripts, frames, wildcard origins, and arbitrary connect sources. Production MUST disable devtools and MUST forbid external navigation of the WebView.

#### Scenario: [DTH-R008-S01] Allowlist contains only SegVision commands
- **WHEN** a production build is inspected or a non-allowlisted invoke is attempted
- **THEN** only the frozen protocol operations plus the named host-only window, grant, log, and export commands SHALL be callable
- **AND** unknown commands MUST be rejected

#### Scenario: [DTH-R008-S02] Production CSP blocks remote and framed content
- **WHEN** production WebView policy is evaluated
- **THEN** CSP MUST deny remote script sources, frame or iframe embedding, wildcard origins, and arbitrary `connect-src` targets
- **AND** the UI MUST load only packaged local application assets except for host-controlled asset protocol responses

#### Scenario: [DTH-R008-S03] Production forbids devtools and external navigation
- **WHEN** an operator or page script requests production devtools or navigates to an external HTTP(S) origin
- **THEN** the host MUST prevent the action
- **AND** the WebView MUST remain on the packaged SegVision UI

### Requirement: [DTH-R009] Restricted binary asset protocol
The host SHALL serve images and masks through a restricted custom protocol such as `segvision-asset://` or an equivalent host-owned scheme. React MUST use an opaque tokenized URI. The host MUST validate the token, then stream the sidecar binary response. The protocol MUST reject path traversal, including `..`, and MUST reject raw local filesystem paths.

#### Scenario: [DTH-R009-S01] Valid token streams sidecar bytes
- **WHEN** React requests a host-issued asset URI whose token is unexpired and bound to the current session, revision, and asset kind
- **THEN** the host MUST validate the token and stream the sidecar binary body to the WebView
- **AND** the URI MUST NOT embed a filesystem path

#### Scenario: [DTH-R009-S02] Invalid token is rejected
- **WHEN** an asset URI has a missing, expired, unbound, or guessable token
- **THEN** the host MUST refuse to stream bytes
- **AND** it MUST NOT fall back to reading an arbitrary local file

#### Scenario: [DTH-R009-S03] Traversal and raw paths are rejected
- **WHEN** an asset request contains `..`, a `file:` URL, or a raw local path such as `C:\` or UNC path
- **THEN** the host MUST reject the request
- **AND** no file outside the sidecar-issued asset MUST be returned

#### Scenario: [DTH-R009-S04] Large binaries stay off command JSON
- **WHEN** React needs an original image or binary mask
- **THEN** the host MUST use the restricted asset protocol rather than Tauri command JSON, base64 fields, or integer pixel arrays
- **AND** embeddings and model tensors MUST NOT be transferred to React or the host

### Requirement: [DTH-R010] Host must not implement the annotation engine
The Tauri host MUST NOT implement segmentation, candidate ranking, ROI geometry rules, mask merge, Accept rules, or tensor parsing. Those behaviors MUST remain in the Python sidecar and existing core. The host MAY only window, grant, proxy, stream, log, and manage sidecar lifecycle.

#### Scenario: [DTH-R010-S01] Host does not rank or segment
- **WHEN** a proposal or refinement command is issued
- **THEN** the host MUST forward the request to the sidecar without computing masks, ranking candidates, or parsing tensors
- **AND** the authoritative candidate list MUST come from the sidecar snapshot or event

#### Scenario: [DTH-R010-S02] Host does not apply ROI or Accept rules
- **WHEN** React submits `sessions.lock_roi`, local edit, Accept, Needs Review, `sessions.select`, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.expand_roi`, or `sessions.acknowledge_warning`
- **THEN** the host MUST NOT validate crop geometry, local-edit policy, or Accept eligibility itself
- **AND** it MUST relay the sidecar result or typed error unchanged in meaning
- **AND** it MUST NOT keep a React-owned select, undo, or manual-empty store as authority

### Requirement: [DTH-R011] Host and sidecar diagnostic logs with redaction
The host SHALL collect host logs and sidecar stdout and stderr. Log storage and export MUST redact the per-launch secret, sensitive user filesystem paths, and image content. The host SHALL provide a diagnostic export entry point that preserves those redactions.

#### Scenario: [DTH-R011-S01] Sidecar output is collected
- **WHEN** the sidecar writes stdout or stderr while running
- **THEN** the host MUST capture that output in the diagnostic log set
- **AND** an operator MUST be able to export those logs through a host command or documented export path

#### Scenario: [DTH-R011-S02] Secrets, paths, and pixels are redacted
- **WHEN** logs would otherwise include the per-launch secret, a full user dataset path, or image or mask bytes
- **THEN** the stored and exported logs MUST omit or replace those values with redacted placeholders
- **AND** image content MUST NOT be dumped as raw pixels, base64, or encoded raster data in logs

### Requirement: [DTH-R012] Production updater, telemetry, and runtime network stay off
Production Tauri updater, telemetry, crash-reporting upload, and other runtime network features SHALL default OFF. The host MUST NOT download models, UI assets, or updates at runtime. The packaged desktop application MUST be able to launch and operate with outbound network access disabled.

#### Scenario: [DTH-R012-S01] Network features are disabled by default
- **WHEN** a production build starts on a machine with outbound network disabled
- **THEN** updater, telemetry, and other runtime network features MUST remain off
- **AND** launch MUST NOT require an account, remote service, or download

#### Scenario: [DTH-R012-S02] Runtime does not fetch models or scripts
- **WHEN** an approved model is missing or the UI needs an asset
- **THEN** the host MUST NOT download a checkpoint, script, or remote iframe
- **AND** it MUST surface a local diagnostic setup state instead of contacting a network origin

### Requirement: [DTH-R013] Windows filesystem failures have stable errors
Host file and folder operations SHALL map Windows Unicode paths, paths with spaces, long paths, read-only directories, disconnected network drives, and locked files to host-stable machine-readable error codes `grant_invalid` and `filesystem_error` plus actionable operator messages. The host MAY wrap those codes before the React client. They are not extra sidecar JSON protocol codes. The host MUST NOT crash the UI process solely because one of those filesystem conditions occurred.

#### Scenario: [DTH-R013-S01] Unicode, spaces, and long paths succeed when valid
- **WHEN** the operator grants a valid existing folder whose path contains Unicode, spaces, or a long path
- **THEN** the host MUST record the canonical grant and MUST be able to resolve it for sidecar open
- **AND** the display name returned to React MUST remain human-readable

#### Scenario: [DTH-R013-S02] Read-only directory is a stable error
- **WHEN** a required write target is a read-only directory
- **THEN** the host or proxied sidecar error MUST use `filesystem_error` (host-stable; not an extra sidecar JSON code)
- **AND** the operator message MUST state that the location is not writable

#### Scenario: [DTH-R013-S03] Disconnected network drive is a stable error
- **WHEN** a previously granted path refers to a disconnected network drive
- **THEN** the host MUST fail the resolve or open command with `grant_invalid` or `filesystem_error`
- **AND** it MUST NOT hang the UI thread indefinitely

#### Scenario: [DTH-R013-S04] Locked file is a stable error
- **WHEN** a required file is locked by another process
- **THEN** the host MUST return `filesystem_error` and an actionable message
- **AND** currently displayed pixels MUST remain on screen

### Requirement: [DTH-R014] Dedicated SegVision application
The desktop host SHALL be a dedicated SegVision annotation application. It MUST NOT be a portal, iframe container, tool registry, plugin runtime, or microfrontend host. It MUST NOT load third-party tools, Streamlit apps, or arbitrary remote pages into the window.

#### Scenario: [DTH-R014-S01] No portal or plugin surface
- **WHEN** the production UI and host command surface are inspected
- **THEN** they MUST NOT provide a tool registry, plugin loader, or iframe container for foreign applications
- **AND** only the packaged SegVision annotation UI SHALL occupy the native window

#### Scenario: [DTH-R014-S02] Foreign runtime content is rejected
- **WHEN** configuration or a command asks the host to embed an external tool origin or plugin bundle
- **THEN** the host MUST refuse
- **AND** the refusal MUST be testable as a policy failure rather than a loaded foreign document

### Requirement: [DTH-R015] Development-only direct sidecar connect must not ship
A development-only React-direct sidecar connection, if present at all, MUST allow only an exact local development origin and MUST NOT be included in a production installer or production WebView policy. Production MUST keep sidecar CORS disabled for browser callers.

#### Scenario: [DTH-R015-S01] Production bundle has no direct-connect path
- **WHEN** a production installer or packaged WebView configuration is inspected
- **THEN** it MUST NOT enable React-direct sidecar access, wildcard CORS, or a development origin allowlist
- **AND** production React MUST continue to use only the Tauri host bridge

#### Scenario: [DTH-R015-S02] Dev-only origin is exact when enabled
- **WHEN** a non-production development profile enables a direct sidecar connection
- **THEN** it MUST allow only one exact development origin
- **AND** that profile MUST NOT be the shipped production default

### Requirement: [DTH-R016] CPU-only offline sidecar launch
The host SHALL launch the packaged CPU-only Python sidecar and MUST NOT enable GPU, CUDA, cloud inference, or remote model services. The host MUST NOT change Python core behavior and MUST NOT pack MVTec datasets into the desktop installer.

#### Scenario: [DTH-R016-S01] Sidecar launch is CPU-only and local
- **WHEN** the host starts the engine sidecar
- **THEN** the launch environment MUST select the CPU-only runtime path
- **AND** it MUST NOT set GPU device flags or contact a hosted inference service

#### Scenario: [DTH-R016-S02] Host does not redistribute MVTec
- **WHEN** a production desktop package is inspected
- **THEN** it MUST NOT include MVTec dataset files
- **AND** dataset access MUST occur only through operator grants to local folders

#### Scenario: [DTH-R016-S03] Host does not replace Python core
- **WHEN** the host proxies annotation operations
- **THEN** it MUST call the sidecar application/transport API
- **AND** it MUST NOT reimplement or patch `segvision.core` rules in Rust

### Requirement: [DTH-R017] Typed control-plane proxy
The host SHALL accept typed Tauri commands from React for small control-plane JSON and SHALL forward those requests with the current protocol version, request identity, and injected authentication to the sidecar HTTP API. Every forwarded control request, including GET-equivalent reads, SHALL carry `protocol_version` in the typed envelope or header. The production Tauri command allowlist SHALL be exactly the frozen protocol operations plus the host-only window, grant, log, and export commands named in this capability. The host MUST NOT provide an untyped generic HTTP-forward command that accepts an arbitrary URL, method, or header set from React. Reads, lists, and asset-get MUST NOT increment revision.

#### Scenario: [DTH-R017-S01] Allowed command is forwarded to localhost sidecar
- **WHEN** React invokes a frozen protocol operation or named host-only command with a well-formed control payload
- **THEN** the host MUST send the corresponding sidecar request, when the command is a protocol operation, to the current `127.0.0.1` sidecar port
- **AND** React MUST NOT supply the destination URL
- **AND** the forwarded request MUST include `protocol_version`

#### Scenario: [DTH-R017-S02] Generic HTTP bridge is absent
- **WHEN** React attempts to pass an arbitrary URL, header map, or raw HTTP request through the host
- **THEN** the host MUST reject the invoke
- **AND** no request MUST be sent to a non-sidecar origin

### Requirement: [DTH-R018] Typed event-plane forwarding
The production event plane SHALL be sidecar emission on loopback using host-owned SSE or an equivalent host-only HTTP channel authenticated with the per-launch secret. The host SHALL receive those sidecar job and session events and SHALL emit typed Tauri events to React. React MUST NOT subscribe to sidecar event URLs directly. Event payloads MUST preserve sidecar identity fields needed for stale rejection. The host MUST NOT synthesize `completed`, `accepted`, or persistence-success events from process liveness alone. Shared memory remains out of protocol `1.0`.

#### Scenario: [DTH-R018-S01] Sidecar events reach React with identity fields
- **WHEN** the sidecar emits a job progress, completed, cancelled, stale, or failed event
- **THEN** the host MUST consume it on loopback over host-owned SSE or equivalent host-only HTTP authenticated with the per-launch secret
- **AND** the host MUST forward a typed event that includes the sidecar-provided `event_id`, `request_id`, `job_id`, `session_id`, `revision`, `kind`, and timestamp
- **AND** React MUST be able to discard an event whose revision is older than the displayed snapshot
- **AND** React MUST NOT subscribe to the sidecar event URL

#### Scenario: [DTH-R018-S02] Host does not invent completion
- **WHEN** the sidecar process is alive but a job has not completed
- **THEN** the host MUST NOT emit a completed or accepted event
- **AND** a sidecar crash MUST produce unavailability or failure signaling rather than success

### Requirement: [DTH-R019] Native window owns the packaged UI
The Tauri 2 host SHALL own the native application window and SHALL load the packaged React UI as the only production document. Window creation, close handling, and WebView capability grants are host responsibilities. The host MUST keep core headless constraints intact by remaining outside Python core.

#### Scenario: [DTH-R019-S01] Production window loads packaged UI
- **WHEN** the operator launches the production desktop application
- **THEN** a native window MUST open and MUST load the packaged SegVision React UI
- **AND** it MUST NOT load a remote site as the initial document

#### Scenario: [DTH-R019-S02] Close is owned by the host
- **WHEN** the operator requests window close
- **THEN** the host MUST run the sidecar shutdown sequence specified by [DTH-R005]
- **AND** React MUST NOT be required to know sidecar process handles in order for close to complete

### Requirement: [DTH-R020] Model approval remains a Python gate
The host MUST NOT deserialize, checksum-bypass, or substitute a MobileSAM checkpoint. Checkpoint approval and checksum verification MUST remain in Python. If the sidecar reports a missing, unapproved, or checksum-invalid model, the host MUST show a recoverable engine setup or error state and MUST NOT download a replacement.

#### Scenario: [DTH-R020-S01] Host does not load tensors
- **WHEN** a model file exists on disk
- **THEN** the host MUST NOT parse or load it as a tensor or checkpoint
- **AND** only a sidecar-reported health or error state SHALL determine whether the engine is ready

#### Scenario: [DTH-R020-S02] Missing or invalid model stays offline
- **WHEN** the sidecar reports that the approved checkpoint is missing or fails checksum verification
- **THEN** the host MUST keep updater and network download disabled
- **AND** it MUST present a diagnostic setup or error state without claiming inference is available
