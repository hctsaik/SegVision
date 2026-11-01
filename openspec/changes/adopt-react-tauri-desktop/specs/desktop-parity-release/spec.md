## ADDED Requirements

### Requirement: [DPR-R001] PySide6 remains the default GUI until parity evidence exists
The shipped default GUI entry point SHALL remain the existing PySide6 annotation application until every mandatory desktop-parity scenario in this capability has passing, hash-bound evidence. The React + Tauri desktop shell MUST NOT be advertised, launched as the documented default, or selected by an unmarked installer option before that evidence exists. PySide6 MUST remain buildable, launchable, and covered by its existing GUI acceptance cases while it is the default.

#### Scenario: [DPR-R001-S01] Default entry point before parity
- **WHEN** the React + Tauri shell exists but one or more mandatory desktop-parity scenarios lack passing evidence
- **THEN** the documented launch command, installer default, and release notes SHALL start PySide6
- **AND** selecting the Tauri shell SHALL require an explicit non-default development or experimental path that cannot satisfy a default-GUI release claim

#### Scenario: [DPR-R001-S02] PySide6 remains operable
- **WHEN** a parity candidate is under test and PySide6 is still the default
- **THEN** the PySide6 GUI SHALL still launch, execute the frozen annotation workflow, and pass its existing GUI acceptance cases

### Requirement: [DPR-R002] React/Tauri MUST satisfy equivalent or stronger gates before becoming default
The React + Tauri desktop application SHALL become the default GUI only after it satisfies every existing annotation-workflow, persistence, offline-release, and acceptance contract that the PySide6 GUI currently must satisfy, plus every new protocol, sidecar, React, real-window desktop E2E, and offline-installer gate defined by this change. The new shell MUST NOT replace a passing PySide6 gate with a weaker substitute, a skipped case, or a screenshot-only check.

#### Scenario: [DPR-R002-S01] Cutover is authorized
- **WHEN** every mandatory existing Python unit, integration, E2E, GUI, packaging, and acceptance case still passes, and every mandatory desktop-parity scenario in this capability also passes with hash-bound evidence
- **THEN** the default GUI entry point MAY switch to the Tauri application
- **AND** the evidence bundle SHALL record that the new shell met equivalent or stronger gates than the PySide6 default it replaces

#### Scenario: [DPR-R002-S02] Partial new-shell coverage cannot cut over
- **WHEN** the Tauri shell passes a subset of desktop E2E paths but any existing mandatory case or any mandatory desktop-parity scenario fails, is skipped, or lacks evidence
- **THEN** the default GUI MUST remain PySide6
- **AND** the candidate MUST NOT receive a release label that names React/Tauri as the default GUI

### Requirement: [DPR-R003] PySide6 remains deprecated-in-place after the default switch
Completing this change SHALL mean, at most, that React/Tauri is the default GUI and PySide6 is marked deprecated in place. Removal of PySide6 source, tests, packaging, or launch paths is OUT OF SCOPE for this change and MUST NOT be treated as a completion condition. After a valid default switch, PySide6 MUST remain in-tree, launchable for rollback, and excluded from the default entry point without deleting its evidence or user-facing recovery path.

#### Scenario: [DPR-R003-S01] Default switch deprecates rather than deletes
- **WHEN** React/Tauri becomes the default GUI under DPR-R002
- **THEN** PySide6 SHALL remain in the repository and documented as deprecated
- **AND** the deprecated path SHALL still launch for rollback without requiring a new OpenSpec change to restore it

#### Scenario: [DPR-R003-S02] Removal cannot complete this change
- **WHEN** an implementation deletes PySide6, its tests, or its launch path in order to mark this change complete
- **THEN** the desktop-parity-release gate MUST fail
- **AND** this change MUST remain incomplete until PySide6 is restored as deprecated-in-place

### Requirement: [DPR-R004] Existing Python contracts remain mandatory and unmodified for green status
Existing Python unit, integration, E2E, GUI, packaging, governance, and acceptance contracts SHALL remain mandatory throughout this change. Implementers MUST NOT skip, xfail, delete, weaken, rewrite, or retarget a required test, threshold, oracle, pytest node, or acceptance case to obtain a green result for the React/Tauri shell. New desktop tests are additive. Shared CI timing MUST NOT substitute for existing reference-CPU gates.

#### Scenario: [DPR-R004-S01] Existing suites still run
- **WHEN** a desktop-parity candidate is evaluated
- **THEN** the existing Python unit, integration, E2E, GUI, packaging, and governance suites SHALL execute and MUST pass at their current thresholds
- **AND** `validate-contracts`, `validate-evidence`, and `validate-state` SHALL still bind the current OpenSpec sources, task graph, profile, and evidence hashes

#### Scenario: [DPR-R004-S02] Weakening a required case is a gate failure
- **WHEN** a required existing test is skipped, xfailed, deleted, rewritten to a weaker oracle, or given a changed threshold to make React/Tauri appear green
- **THEN** the desktop-parity-release and existing acceptance gates MUST fail
- **AND** the original failure SHALL remain visible in evidence

### Requirement: [DPR-R005] New test layers are mandatory for cutover
Before React/Tauri may become the default GUI, the repository SHALL add and pass all of the following additive layers: protocol contract tests; sidecar integration tests covering health, session, cancel, stale rejection, binary asset transfer, and crash recovery; React unit and component tests; real-window desktop E2E tests; and an offline installer test on a clean Windows machine with outbound network blocked. A passing PySide6 suite alone MUST NOT authorize cutover.

#### Scenario: [DPR-R005-S01] All new layers are present
- **WHEN** cutover evidence is assembled
- **THEN** the evidence bundle SHALL contain passing results for protocol contract, sidecar integration, React unit/component, real-window desktop E2E, and clean-machine offline installer layers
- **AND** each layer SHALL name its commands, exit codes, and artifact hashes

#### Scenario: [DPR-R005-S02] Missing layer blocks default switch
- **WHEN** any required new layer is absent, non-zero, skipped, or lacks hash-bound artifacts
- **THEN** the default GUI MUST remain PySide6
- **AND** the missing layer SHALL be recorded as a failed or blocked desktop-parity gate rather than inferred from screenshots or prose

### Requirement: [DPR-R006] Protocol contract tests SHALL lock request, response, event, and error schemas
Protocol contract tests SHALL validate the versioned desktop control, event, and error schemas against a single OpenAPI/JSON Schema source of truth. They MUST fail on undocumented fields that change public behavior, missing required identifiers (`session_id`, `revision`, `request_id` where specified by the protocol capability), incompatible version negotiation, and error-code drift between TypeScript, Rust, and Python bindings.

#### Scenario: [DPR-R006-S01] Compatible schema round-trip
- **WHEN** a generated or fixture request, response, and event are validated against the frozen schema
- **THEN** the contract suite SHALL accept only schema-valid payloads
- **AND** Python server validation, TypeScript client types, and Rust host types SHALL agree on the same identifiers and error codes

#### Scenario: [DPR-R006-S02] Schema drift is rejected
- **WHEN** a binding emits an undeclared error code, drops a required revision field, or disagrees with the schema source of truth
- **THEN** the protocol contract suite MUST fail
- **AND** cutover MUST remain unauthorized

### Requirement: [DPR-R007] Sidecar integration tests SHALL exercise a real localhost process
Sidecar integration tests SHALL start a real Python desktop sidecar on localhost and MUST verify health/readiness, session create/open, job cancel, stale-result rejection, binary asset retrieval, and crash recovery. Tests that stub the sidecar process, skip crash recovery, or transfer full images and masks as JSON/base64 MUST NOT satisfy this requirement.

#### Scenario: [DPR-R007-S01] Health and session succeed
- **WHEN** the host starts a real sidecar and waits for readiness
- **THEN** health SHALL become ready within the documented timeout and SHALL include `protocol_version`, sidecar readiness, and approved-backend presence/capability or diagnostic setup state
- **AND** `sessions.create` SHALL return an authoritative snapshot with `protocol_session_id`, `workflow_state` `IMAGE_OPEN`, and `revision` `0`

#### Scenario: [DPR-R007-S02] Cancel and stale rejection
- **WHEN** a proposal or refine job is in flight and the test cancels it or advances the session revision
- **THEN** the sidecar SHALL acknowledge cancel or emit a stale rejection
- **AND** `jobs.cancel` MUST still be attempted after the session revision advances and MUST NOT return `revision_conflict` solely because `base_revision` is old
- **AND** the late result MUST NOT become the current candidate or mutate the current mask hash

#### Scenario: [DPR-R007-S03] Binary asset channel
- **WHEN** the UI or host requests an image or mask asset for the current session
- **THEN** the sidecar SHALL serve it through the binary asset path
- **AND** the integration test MUST NOT accept a JSON/base64 full-image or full-mask body as a passing oracle

#### Scenario: [DPR-R007-S04] Crash recovery handshake
- **WHEN** the sidecar process exits abnormally during an open session
- **THEN** the host SHALL detect the crash, put the UI in `engine_unavailable/recovering`, freeze mutations, keep displayed pixels as non-authoritative, MAY auto-restart the sidecar with a new port and secret, and re-handshake
- **AND** restore SHALL occur if and only if persistence verifies a draft or published pair for the current image identity; otherwise `sessions.create` is required
- **AND** “unconditional restart” means respawn and assume in-memory session survived, which is forbidden; auto-respawn of the process is allowed
- **AND** recovery MUST NOT invent a new accepted annotation

### Requirement: [DPR-R008] React unit and component tests SHALL cover tools, candidates, recovery, and coordinates
React unit and component tests SHALL cover tool state, candidate-card rendering for zero through three real candidates, error and recovery presentation, and canvas coordinate mapping including device-pixel-ratio, zoom, and pan. Contract tests plus React component tests SHALL cover those behaviors. Component tests MUST project authoritative Python snapshots rather than owning masks, jobs, or persistence.

#### Scenario: [DPR-R008-S01] Candidate cardinality rendering
- **WHEN** a snapshot contains zero, one, two, or three valid candidates
- **THEN** the component suite SHALL render exactly that many distinct cards
- **AND** it MUST NOT fabricate, duplicate, or pad missing candidates

#### Scenario: [DPR-R008-S02] Coordinate mapping
- **WHEN** a fixture pointer event is applied at a known canvas location under non-1.0 DPR, zoom, or pan
- **THEN** the mapped full-image coordinate SHALL match the frozen half-open `XYXY` contract
- **AND** a mismatch MUST fail the component suite

#### Scenario: [DPR-R008-S03] Error and recovery presentation
- **WHEN** a snapshot reports a typed sidecar, validation, persistence, or recovery error
- **THEN** the component SHALL expose the machine-readable reason and recovery action
- **AND** it MUST NOT hide the error behind an invented successful mask

### Requirement: [DPR-R009] Desktop E2E SHALL drive a real Tauri window
Desktop E2E SHALL operate a real Tauri window with automated mouse, keyboard, file-picker grant, canvas, and sidecar-lifecycle input. Direct controller, React store, or Python session method calls MUST NOT substitute for a desktop E2E oracle. The existing Qt `GuiDriver` contract remains mandatory for PySide6 and MUST NOT be weakened by the new driver.

#### Scenario: [DPR-R009-S01] Real-window input
- **WHEN** a desktop E2E case draws an ROI, selects a candidate, or presses a frozen shortcut
- **THEN** the driver SHALL inject real window input
- **AND** the oracle SHALL read session state, revision, event trace, and hashes rather than a mocked store

#### Scenario: [DPR-R009-S02] Direct API calls cannot pass desktop E2E
- **WHEN** a purported desktop E2E case calls the application service or React store without a real window event
- **THEN** that case MUST NOT be counted as a passed desktop E2E gate

### Requirement: [DPR-R010] Desktop E2E SHALL cover the frozen minimum annotation paths
Real-window desktop E2E SHALL cover at least the following paths before default cutover: open a local dataset and display image plus overlay; lock a Tier-1 small ROI and obtain at most three candidates; select a candidate, add positive and negative points, and observe a new revision; apply a local brush edit after which a later model result cannot overwrite the mask; publish distinct Accept and Needs Review outputs; reject stale results after rapid ROI, cancel, or image switch; recover from sidecar crash or restart; reject a missing or checksum-invalid model with a diagnostic setup state; fail closed on a read-only output directory; and complete the workflow with outbound network blocked. Dataset-scale MVTec execution MAY use a locally authorized tree and MUST NOT require the installer to contain MVTec content.

#### Scenario: [DPR-R010-S01] Open local dataset and viewer gold overlay
- **WHEN** the operator grants a local dataset folder that contains images and dataset gold or source overlay masks and the session is still in viewer/`IMAGE_OPEN` with no locked ROI
- **THEN** the desktop app SHALL display the selected image and the dataset gold/source overlay
- **AND** the oracle SHALL confirm the loaded image identity and the viewer gold/source overlay mask hash rather than a screenshot alone
- **AND** that hash MUST NOT be compared against an annotation session-mask overlay

#### Scenario: [DPR-R010-S11] Annotation session-mask overlay
- **WHEN** an annotation session has a current revision with session mask assets after `sessions.lock_roi`
- **THEN** the desktop app SHALL compose the annotation overlay from those session mask assets
- **AND** the oracle SHALL confirm the annotation session-mask overlay hash
- **AND** that hash MUST NOT be compared against the dataset gold/source viewer overlay

#### Scenario: [DPR-R010-S02] Tier-1 small ROI yields at most three candidates
- **WHEN** the user locks a valid small rectangular ROI on a Tier-1 fixture or authorized local image via `sessions.lock_roi` with `class_id` from dataset metadata
- **THEN** `sessions.lock_roi` SHALL be the call that invokes `SegVisionEngine.start` and mints core revision `1`
- **AND** the session SHALL enter the proposal path and display zero through three real candidates
- **AND** the displayed count MUST equal the session candidate count and MUST NOT exceed three

#### Scenario: [DPR-R010-S03] Selection, points, and new revision
- **WHEN** the user selects a refinable candidate via `sessions.select` and adds a foreground point and a background point
- **THEN** the session revision SHALL increase for the ROI or refine path defined by the existing workflow
- **AND** the refined candidate SHALL use the selected previous state and MUST NOT trigger a new encoder call
- **AND** selection MUST NOT be owned only in React

#### Scenario: [DPR-R010-S04] Local brush locks out model overwrite
- **WHEN** the user applies a brush, erase, grow, shrink, or fill-holes edit and a prior model job later completes
- **THEN** the current mask hash SHALL remain the local-edit result byte-for-byte
- **AND** encode and decode counts SHALL be unchanged by the local operation

#### Scenario: [DPR-R010-S05] Accept and Needs Review output paths
- **WHEN** the user explicitly Accepts a valid candidate in one run and chooses Needs Review in another
- **THEN** Accept SHALL publish a pair-consistent full-image PNG and accepted sidecar only after validation, commit, and durable save
- **AND** Needs Review SHALL publish review metadata with `training_eligible=false` and MUST NOT expose an accepted training pair

#### Scenario: [DPR-R010-S06] Rapid ROI, cancel, and image-switch stale rejection
- **WHEN** the user rapidly redraws the ROI, cancels in-flight work, or switches images via `sessions.close` then `sessions.create` while a job is pending
- **THEN** late results SHALL be cancelled or rejected as stale
- **AND** the canvas and current candidate hash MUST belong only to the current session and revision

#### Scenario: [DPR-R010-S07] Sidecar crash or restart
- **WHEN** the sidecar crashes or is restarted during an open annotation
- **THEN** the UI SHALL enter `engine_unavailable/recovering`, freeze mutations, keep displayed pixels as non-authoritative, re-handshake after allowed auto-respawn with a new port and secret, and restore if and only if persistence verifies a draft or published pair for the current image identity; otherwise it SHALL require `sessions.create`
- **AND** it MUST NOT auto-accept, invent candidates, treat auto-respawn as unconditional restart of live session memory, or silently resume with a mismatched `session_id` or `revision`

#### Scenario: [DPR-R010-S08] Missing or checksum-invalid model
- **WHEN** the approved model file is absent or its SHA-256 disagrees with the approved manifest
- **THEN** the app SHALL show a diagnostic setup state, refuse deserialization of the bad artifact, and MUST NOT download a replacement
- **AND** annotation that requires the model SHALL remain blocked until a verified local component is supplied

#### Scenario: [DPR-R010-S09] Read-only output directory
- **WHEN** the configured output directory is read-only and the user Accepts or requests Needs Review
- **THEN** persistence SHALL fail into `SAVE_FAILED` or `REVIEW_SAVE_FAILED`
- **AND** next-image navigation MUST stay disabled, the live mask or review result MUST be retained, and retry SHALL succeed only after the directory is writable, without a new model call

#### Scenario: [DPR-R010-S10] Offline no outbound network
- **WHEN** desktop E2E runs with outbound network blocked
- **THEN** open, propose or replay, edit, Accept or Needs Review, and save SHALL complete without a required remote connection
- **AND** any required outbound attempt MUST fail the case

### Requirement: [DPR-R011] Screenshots MUST NOT be the sole correctness oracle
Screenshots MAY be stored as forensic evidence. Correctness oracles for desktop parity SHALL be session state, revision, event trace, mask hash, PNG sidecar contents, and acceptance evidence. A case whose only passing check is a screenshot, visual diff, or prose description MUST fail.

#### Scenario: [DPR-R011-S01] Structured oracles pass
- **WHEN** a desktop-parity case succeeds
- **THEN** its `oracle-results.json` SHALL bind session state, revision, event-trace sequence, and at least one of mask hash, PNG sidecar schema/hash, or acceptance evidence
- **AND** a screenshot, if present, SHALL be hashed as auxiliary evidence only

#### Scenario: [DPR-R011-S02] Screenshot-only case is rejected
- **WHEN** a case reports pass based only on a screenshot or visual comparison
- **THEN** evidence validation MUST fail that case
- **AND** the case MUST NOT authorize cutover

### Requirement: [DPR-R012] Offline installer composition is frozen
The offline desktop installer SHALL contain the Tauri executable and WebView assets, a versioned Python sidecar directory, licenses and third-party notices, and configuration templates. It MUST remain a Windows x64 CPU-only package. Importing the Python `segvision` package MUST NOT initialize the GUI, and the GUI launch path MUST remain independent of `import segvision`.

#### Scenario: [DPR-R012-S01] Required payload is present
- **WHEN** packaging verification inspects a release candidate installer
- **THEN** it SHALL find the Tauri executable, WebView assets, versioned sidecar directory, notices, and configuration templates
- **AND** each included component SHALL have a recorded cryptographic hash

#### Scenario: [DPR-R012-S02] Python import stays GUI-free
- **WHEN** a clean environment installs the importable `segvision` distribution and executes `import segvision`
- **THEN** the import SHALL succeed without opening a Tauri window, starting the sidecar, downloading models, or creating a hidden process-global model session

### Requirement: [DPR-R013] The PyTorch sidecar SHALL be a versioned directory, not a one-file bundle
The Python sidecar that carries CPU-only PyTorch and MobileSAM dependencies SHALL be packaged as a versioned one-folder directory with a component manifest and hashes. The release MUST NOT ship that sidecar as a one-file PyInstaller executable. The directory layout SHALL expose the engine entry point, CPython/runtime libraries, CPU-only dependencies, and notices so that DLL, model, and component hashes can be inspected without extracting a self-unpacking archive at every launch.

#### Scenario: [DPR-R013-S01] One-folder sidecar is inspectable
- **WHEN** the installed sidecar directory is audited
- **THEN** the verifier SHALL find a versioned directory, component manifest, hashes, and CPU-only runtime files
- **AND** launching the sidecar MUST NOT require unpacking a one-file archive into a temporary directory

#### Scenario: [DPR-R013-S02] One-file PyTorch sidecar is rejected
- **WHEN** a candidate packages the PyTorch sidecar as a one-file PyInstaller binary
- **THEN** the packaging gate MUST fail
- **AND** the candidate MUST NOT become the default GUI package

### Requirement: [DPR-R014] Model weights are a separate verified component with no silent download
Approved model weights SHALL be a separate, versioned, checksum-verified offline component. The installer MUST NOT silently download weights at build, install, or first launch. If an approved local model is missing, the application SHALL enter a diagnostic setup state and MUST NOT fall back to an unrecorded mirror or execute an untrusted checkpoint.

#### Scenario: [DPR-R014-S01] Verified local model loads
- **WHEN** the approved checkpoint is present and its SHA-256 matches the manifest
- **THEN** the sidecar MAY load that local file
- **AND** the load evidence SHALL record the checkpoint hash and approval status

#### Scenario: [DPR-R014-S02] Missing model is diagnostic, not a download
- **WHEN** first launch cannot find the approved local model
- **THEN** the UI SHALL show a diagnostic setup state identifying the missing component
- **AND** no download, login, or remote model request SHALL be attempted

#### Scenario: [DPR-R014-S03] Checksum mismatch is quarantined
- **WHEN** a local checkpoint hash differs from the approved manifest
- **THEN** loading MUST be refused, the artifact MUST be quarantined, and no unrecorded mirror fallback SHALL occur

### Requirement: [DPR-R015] Packaging allowlist MUST exclude MVTec and unauthorized weights
Packaging SHALL use an allowlist plus a manifest scan. MVTec dataset files, MVTec gold masks, and unauthorized or unapproved model weights MUST NOT be bundled in the installer, sidecar directory, WebView assets, or notices payload. Local dataset E2E MAY read an operator-supplied authorized MVTec tree that remains outside the package.

#### Scenario: [DPR-R015-S01] Allowlist scan passes
- **WHEN** packaging scans the installer payload against the allowlist and artifact manifest
- **THEN** every included file SHALL match an approved allowlist entry and recorded hash
- **AND** MVTec content and unauthorized weights SHALL be absent

#### Scenario: [DPR-R015-S02] Prohibited content is detected
- **WHEN** the scan finds MVTec images, MVTec gold masks, EdgeSAM weights, or any model lacking approved manifest fields
- **THEN** the packaging gate MUST fail
- **AND** the artifact MUST be removed before any default-GUI or engineering package label is applied

#### Scenario: [DPR-R015-S03] Local MVTec is not redistributed
- **WHEN** desktop or dataset E2E opens a locally authorized MVTec tree
- **THEN** that tree MUST remain outside the installer
- **AND** packaging evidence SHALL show it was not copied into the release payload

### Requirement: [DPR-R016] Tauri updater, telemetry, and runtime network default OFF
The Tauri updater, telemetry, analytics, crash-upload, and any other runtime network feature SHALL default OFF in v1. A required annotation, model-load, Accept, Needs Review, save, or recovery path MUST complete with outbound network disabled and MUST NOT require an account login. Enabling updater or telemetry SHALL require an explicit later configuration change and MUST NOT be the packaged default.

#### Scenario: [DPR-R016-S01] Defaults are disabled
- **WHEN** a clean install is inspected and launched with default configuration
- **THEN** the Tauri updater, telemetry, and runtime network features SHALL be off
- **AND** configuration templates SHALL not enable them

#### Scenario: [DPR-R016-S02] Required path attempts network
- **WHEN** install, launch, model load, annotation, Accept, Needs Review, save, or recovery attempts a required outbound connection or login
- **THEN** the offline network gate MUST fail
- **AND** the candidate MUST NOT become the default GUI package

### Requirement: [DPR-R017] Engineering verdict MUST NOT claim the new GUI is default until parity passes
An engineering or domain release verdict SHALL NOT state that React/Tauri is the default GUI, and `release-verdict.json` MUST NOT record a default-GUI switch, until every mandatory desktop-parity scenario has passing evidence. Existing `PASS_ENGINEERING` semantics remain; this change MUST NOT invent a partial-pass verdict. Missing desktop-parity evidence MUST keep PySide6 as default without fabricating success.

#### Scenario: [DPR-R017-S01] Verdict without parity keeps PySide6 default
- **WHEN** Tier A/B engineering gates pass for the existing product but desktop-parity scenarios are incomplete
- **THEN** any engineering verdict SHALL keep PySide6 as the default GUI
- **AND** it MUST NOT claim React/Tauri cutover

#### Scenario: [DPR-R017-S02] Forbidden verdict labels
- **WHEN** a candidate uses `PARTIAL_PASS`, `PASS_WITH_SKIPS`, `MOSTLY_PASS`, or a rerun-until-green procedure to hide a failed parity case
- **THEN** verdict validation MUST fail
- **AND** the original failed case SHALL remain in evidence

### Requirement: [DPR-R018] Human Accept, gold masks, and signoff MUST NOT be fabricated
Desktop-parity tests, packaging checks, and release evidence MUST NOT fabricate a human Accept, independent gold mask, user study, legal approval, or release signoff. Scripted desktop E2E Accept SHALL record `acceptance_actor=scripted_test` and MUST NOT count as Tier C human evidence. Synthetic or replayed masks MUST NOT be labeled as independent gold.

#### Scenario: [DPR-R018-S01] Scripted Accept is labeled
- **WHEN** a desktop E2E case performs Accept through scripted window input
- **THEN** the sidecar and evidence SHALL record scripted actor provenance
- **AND** the case MUST NOT be counted as real-annotator or independent-reviewer evidence

#### Scenario: [DPR-R018-S02] Fabricated gold or signoff is rejected
- **WHEN** evidence presents a self-generated mask as independent gold or an agent-written statement as legal or release signoff
- **THEN** evidence validation MUST fail
- **AND** no domain or default-GUI claim SHALL be inferred

### Requirement: [DPR-R019] Migration is staged, independently verifiable, and reversible
Adoption SHALL proceed through independently verifiable stages in this order: protocol and host skeleton; read-only dataset viewer; full annotation loop; persistence and recovery; MobileSAM and MVTec E2E against authorized local data; offline installer and security gates; default GUI switch. Each stage MUST have its own commands, pass criteria, evidence, and rollback. A later stage MUST NOT be marked passed if an earlier required stage lacks evidence. Completing an earlier stage MUST NOT delete PySide6 or change the default GUI.

#### Scenario: [DPR-R019-S01] Stage order is enforced
- **WHEN** execution state records desktop-parity stages
- **THEN** a stage SHALL become passed only after its own evidence passes and every preceding required stage has passed
- **AND** default switch SHALL be last among the stages in this requirement

#### Scenario: [DPR-R019-S02] Each stage can be verified alone
- **WHEN** a single stage is re-run
- **THEN** its tests SHALL produce stage-scoped evidence that can pass or fail without requiring undocumented work from a later stage
- **AND** failure SHALL leave the default GUI unchanged

#### Scenario: [DPR-R019-S03] Rollback is reversible
- **WHEN** a later stage fails after an earlier stage passed
- **THEN** rollback SHALL restore the prior verified host, UI, sidecar, or installer artifact without deleting its evidence
- **AND** PySide6 SHALL remain available as the default or deprecated-in-place path according to whether cutover had already been authorized

### Requirement: [DPR-R020] nativeApp host/sidecar patterns MAY be reused; portal production patterns MUST NOT
Implementers MAY reuse nativeApp engineering patterns for a React/Vite workspace, Tauri 2 host, Python sidecar packaging, random localhost port, health checks, readiness timeout, hidden child process, stdout/stderr logs, graceful shutdown, crash detection, file-picker grants, shared protocol, Vitest, and real desktop E2E. The SegVision desktop app MUST NOT copy nativeApp portal, tool-registry, iframe, Streamlit, or microfrontend production structure, MUST NOT use wildcard origin or mock authentication in production, and MUST NOT let React know the sidecar port, secret, or local absolute paths.

#### Scenario: [DPR-R020-S01] Dedicated app structure
- **WHEN** the desktop host and UI are inspected
- **THEN** the product SHALL be a dedicated annotation application
- **AND** it MUST NOT embed a portal, iframe tool host, wildcard CORS origin, or production mock-auth module

#### Scenario: [DPR-R020-S02] React cannot reach the sidecar directly
- **WHEN** a production React bundle is audited
- **THEN** it MUST NOT contain the sidecar port, per-launch secret, or filesystem absolute paths
- **AND** all control and binary asset access SHALL go through the Tauri host

### Requirement: [DPR-R021] License notices MUST cover the new desktop stack and retain existing prohibitions
Every desktop release candidate SHALL include SBOM and `THIRD_PARTY_NOTICES` covering Tauri, WebView2, React, Vite, Rust crates, and the Python sidecar stack in addition to the existing common package, inference runtime, CV runtime, model code, model weights, and packaged assets. GPL-licensed X-AnyLabeling source or assets MUST NOT be copied. EdgeSAM MUST remain excluded unless written commercial authorization is recorded in the model manifest. Missing notice text for a redistributable desktop component SHALL fail the license gate.

#### Scenario: [DPR-R021-S01] Desktop stack notices are complete
- **WHEN** the license verifier compares the installed desktop inventory with SBOM and notices
- **THEN** Tauri, WebView2, React, Vite, Rust crates, and Python sidecar components SHALL be represented with required attribution
- **AND** the inventory SHALL match the clean installed environment

#### Scenario: [DPR-R021-S02] X-AnyLabeling GPL copy is detected
- **WHEN** provenance identifies copied X-AnyLabeling GPL material in the desktop host, UI, sidecar, or installer
- **THEN** the license gate MUST fail
- **AND** the material MUST be removed or the distribution license decision MUST be explicitly escalated before any package label

#### Scenario: [DPR-R021-S03] EdgeSAM lacks written permission
- **WHEN** the model manifest has no written commercial approval for EdgeSAM
- **THEN** EdgeSAM MUST be excluded from build, test-selection, and desktop packaging
- **AND** including it SHALL fail the license gate

### Requirement: [DPR-R022] This engineering GUI-shell change MUST NOT require domain or Tier C input
Completing desktop-parity-release as an engineering GUI-shell change SHALL require M0–M4-class engineering evidence plus the additive desktop-parity gates in this capability. Missing representative domain images, independent gold masks, real annotator sessions, or other Tier C inputs MUST NOT block this change, MUST NOT force a `FAIL` verdict, and MUST NOT be fabricated to obtain cutover. A domain-target promotion remains a separate gate and MUST stay `domain_validated=false` until real Tier C evidence exists.

#### Scenario: [DPR-R022-S01] Engineering cutover without Tier C
- **WHEN** all engineering desktop-parity and existing Tier A/B gates that do not require domain input have passing evidence and Tier C input is absent
- **THEN** this change MAY complete as an engineering GUI-shell change if PySide6 default-switch rules are also satisfied
- **AND** `domain_validated` SHALL remain false

#### Scenario: [DPR-R022-S02] Missing Tier C is not a desktop-parity failure
- **WHEN** independent gold or real-annotator evidence is unavailable
- **THEN** desktop-parity-release MUST NOT treat that absence as a failed GUI-shell gate
- **AND** the classifier MUST NOT invent `PASS_DOMAIN_VALIDATED`

### Requirement: [DPR-R023] Existing performance thresholds SHALL remain unmodified
This change MUST NOT invent new performance numbers and MUST NOT relax existing hard gates. Overlay and brush input-to-frame p95 SHALL remain strictly below 100 milliseconds on the designated reference machine. Cached refine remains a best-effort target that MUST report a miss. Shared CI timing MUST NOT satisfy reference-CPU evidence. A Tauri candidate that lacks reference-machine overlay/brush evidence MUST NOT claim performance parity by anecdote.

#### Scenario: [DPR-R023-S01] Existing hard UI gate still applies
- **WHEN** reference-CPU UI responsiveness is measured for the default GUI after an authorized cutover
- **THEN** overlay and brush input-to-frame p95 SHALL be strictly below 100 milliseconds on the designated machine
- **AND** the report SHALL fingerprint OS, CPU, RAM, runtime, and artifact hashes

#### Scenario: [DPR-R023-S02] New numbers cannot replace the profile
- **WHEN** a candidate introduces a new latency claim or a looser threshold without a versioned acceptance-profile change
- **THEN** the performance and desktop-parity gates MUST fail
- **AND** the existing profile hash SHALL remain the sole threshold source

### Requirement: [DPR-R024] React/Tauri SHALL implement the existing annotation workflow contract
The React + Tauri GUI SHALL implement the frozen annotation workflow in `annotation-workflow` without changing ROI geometry, candidate policy, point refinement, local-edit lockout, undo, shortcuts, Accept, Needs Review, timer origin, or out-of-scope control prohibitions. Python session state remains authoritative. The UI MUST NOT auto-accept, default to pixel-OR fusion, display more than three candidates, or allow a model result to overwrite a local edit.

#### Scenario: [DPR-R024-S01] Workflow states remain the source of truth
- **WHEN** a user completes a valid model-assisted Accept through the Tauri GUI
- **THEN** the session SHALL traverse the existing ready, editing, `VALIDATING`, `COMMITTING`, `SAVING`, and `ACCEPTED` states
- **AND** the UI MUST NOT show accepted status before pair-consistent publication

#### Scenario: [DPR-R024-S02] Frozen shortcuts remain mapped
- **WHEN** the Tauri window receives `1`/`2`/`3`, left/right clicks, `B`, `[`, `]`, `F`, `X`, `Z`, `Space`, or `N`
- **THEN** those inputs SHALL map to `sessions.select`, point, local-edit, `sessions.expand_roi`, `sessions.undo`, Accept-attempt, and next-image contracts
- **AND** `N` MUST remain disabled until durable `ACCEPTED` or durable `NEEDS_REVIEW`

#### Scenario: [DPR-R024-S03] Out-of-scope controls stay absent
- **WHEN** the Tauri GUI launches with default configuration
- **THEN** its control tree SHALL omit text/VLM prompting, DINO points, per-image color sliders, multi-instance tabs, automatic Accept, and default fusion

### Requirement: [DPR-R025] Clean-machine offline installer verification is mandatory for the Tauri package
The Tauri installer SHALL be verified on a clean supported Windows x64 machine with outbound network disabled. Installation, GUI launch, sidecar readiness, verified local model load when the separate component is present, scripted annotation, Accept, Needs Review, save, reload, and uninstall or removal smoke SHALL succeed without login, CUDA, GPU runtime, or a hosted service. Unicode and space-containing paths SHALL be included in the packaging evidence.

#### Scenario: [DPR-R025-S01] Clean offline install and workflow
- **WHEN** an operator installs the Tauri bundle on a clean Windows machine with outbound network disabled and empty caches
- **THEN** the GUI SHALL launch and a scripted Accept-save-reload path and a Needs Review path SHALL complete
- **AND** accepted reload hashes SHALL match while review output remains `training_eligible=false`

#### Scenario: [DPR-R025-S02] CPU-only and path audit
- **WHEN** the installed process tree and payload are audited on that machine
- **THEN** the verifier SHALL find no required CUDA or GPU runtime and no required outbound socket
- **AND** model lookup and pair save SHALL succeed on a writable Unicode data path
