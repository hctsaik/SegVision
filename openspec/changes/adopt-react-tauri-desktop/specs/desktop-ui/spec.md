## ADDED Requirements

### Requirement: [DUI-R001] Annotation-workflow capability conformance
The desktop UI SHALL implement the `annotation-workflow` capability as a projection of Python authoritative session state. It MUST honor that capability's state machine (`IMAGE_OPEN`, `ROI_LOCKED`, `PROPOSING`, `PROPOSAL_READY`, `MANUAL_EMPTY`, `REFINE_PENDING`, `REFINED_READY`, `LOCAL_EDITING`, `VALIDATING`, `COMMITTING`, `SAVING`, `SAVE_FAILED`, `REVIEW_SAVING`, `REVIEW_SAVE_FAILED`, `ACCEPTED`, and `NEEDS_REVIEW`), zero-to-three real candidates, frozen shortcuts, local-edit lockout of model mutation, undo-via-session rather than a GUI mask history, explicit Accept versus Needs Review outcomes, and stale-completion rejection. The UI MUST NOT rewrite those core rules, invent additional public states, or present an annotation as accepted before validation, commit, and pair-consistent publication have completed.

#### Scenario: [DUI-R001-S01] Workflow states are projected, not invented
- **WHEN** the Python session reports a legal `annotation-workflow` state
- **THEN** the desktop UI SHALL display that same state and SHALL enable or disable controls according to the current candidate capabilities and that state's allowed operations

#### Scenario: [DUI-R001-S02] Invalid UI action is rejected without hidden work
- **WHEN** a control, shortcut, or pointer gesture requests an operation that is not valid in the current authoritative state
- **THEN** the UI SHALL leave the current mask and state unchanged, SHALL expose a machine-readable reason, and MUST NOT invoke hidden model, commit, or persistence work

#### Scenario: [DUI-R001-S03] Accept and Needs Review remain distinct
- **WHEN** the user requests Accept or Needs Review from the desktop UI
- **THEN** the UI SHALL send the corresponding explicit command and MUST NOT convert one outcome into the other, auto-finalize, or treat a pending save as a durable terminal state

#### Scenario: [DUI-R001-S04] Timer origin is first_roi_locked and continues across redraw
- **WHEN** the session reports annotation timer origin `first_roi_locked` after `sessions.lock_roi` and the user later redraws the ROI or issues `sessions.expand_roi`
- **THEN** the UI SHALL continue the same timer from that origin
- **AND** MUST NOT reset the timer solely because the ROI was redrawn or expanded

#### Scenario: [DUI-R001-S05] IMAGE_OPEN is projected from sessions.create
- **WHEN** `sessions.create` returns a snapshot with `workflow_state` `IMAGE_OPEN` and `revision` `0`
- **THEN** the UI SHALL display `IMAGE_OPEN` with no `user_roi_full`
- **AND** MUST NOT claim Accept or Needs Review eligibility
- **AND** MUST NOT treat that snapshot as a completed `SegVisionEngine.start`

### Requirement: [DUI-R002] Dedicated annotation application shell
The desktop UI MUST be a dedicated SegVision annotation application. It MUST NOT be a portal, iframe host, microfrontend container, tool registry, or plugin runtime that loads unrelated web applications.

#### Scenario: [DUI-R002-S01] Cold launch presents the annotation app
- **WHEN** the desktop UI starts with default configuration
- **THEN** the visible shell SHALL be the SegVision annotation workspace and MUST NOT host third-party frames, portal navigation, or a generic tool registry

#### Scenario: [DUI-R002-S02] External document embedding is rejected
- **WHEN** a configuration or runtime request attempts to load an arbitrary remote or local document as an iframe, microfrontend, or plugin surface
- **THEN** the UI MUST refuse that embedding and MUST keep the annotation workspace as the only primary surface

### Requirement: [DUI-R003] React owns presentation and local interaction
React SHALL own layout, toolbars, dataset list, candidate cards, status, zoom, pan, hover, the current tool, uncommitted strokes, Canvas preview, and retry or recovery display. React SHALL call typed host commands and subscribe to typed events to project authoritative snapshots. React MUST remain responsive to pan, zoom, redraw, cancellation, manual fallback, and Needs Review while model work is pending.

#### Scenario: [DUI-R003-S01] Local viewport interaction does not wait for Python
- **WHEN** the user pans, zooms, or hovers while a proposal or refinement job is pending
- **THEN** React SHALL update the viewport immediately and MUST NOT block the UI thread on inference

#### Scenario: [DUI-R003-S02] Tool and status are UI-owned
- **WHEN** the user selects brush, point, ROI, or another allowed tool and a job later reports progress or a recoverable error
- **THEN** React SHALL keep the current tool locally, SHALL render the job or recovery status from typed events, and MUST NOT infer job completion from elapsed time or UI inactivity

#### Scenario: [DUI-R003-S03] Dataset list and candidate cards are projected
- **WHEN** an authoritative snapshot contains dataset items and zero to three candidates
- **THEN** React SHALL render the dataset list and only the returned candidate cards, including diagnostics when no card exists

### Requirement: [DUI-R004] React must not own engine or persistence truth
React MUST NOT own embeddings, logits, model objects, checkpoints, authoritative masks, candidate provenance, Accept results, persistence truth, job-completion inference, raw filesystem paths, or shell execution. Those values MUST remain owned by Python, the Tauri host, or persistence adapters as specified by the desktop architecture.

#### Scenario: [DUI-R004-S01] Mask truth is displayed, not stored as the authority
- **WHEN** the UI renders a mask overlay
- **THEN** the pixels SHALL be a projection of a Python-issued asset or snapshot for the current session and revision, and React MUST NOT treat a locally mutated pixel buffer as the durable mask

#### Scenario: [DUI-R004-S02] Filesystem and shell capabilities are absent
- **WHEN** the UI needs to open a dataset, image, or output location
- **THEN** it MUST use host grants (`dataset` or `output`) and typed commands, sending `grant_id` only, and MUST NOT read raw filesystem paths, construct shell commands, or execute a process

#### Scenario: [DUI-R004-S03] Job completion is not inferred
- **WHEN** a job has been pending longer than a progress interval or the last event is delayed
- **THEN** the UI MUST continue showing the last verified job status and MUST NOT mark the job completed, cancelled, stale, or failed unless a typed event or snapshot says so

#### Scenario: [DUI-R004-S04] Select undo and manual-empty are protocol mutations
- **WHEN** the user selects a candidate, undoes, or begins manual-empty
- **THEN** the UI SHALL invoke `sessions.select`, `sessions.undo`, or `sessions.begin_manual_empty` respectively
- **AND** MUST NOT keep a React-owned selected-candidate, undo, or manual-empty mask store as authority

### Requirement: [DUI-R005] Global store holds only small serializable view models
The global React store MUST contain only small, serializable UI and view-model state such as session identifiers, revision, selected candidate id, current tool, viewport transform, panel visibility, and recovery status. Images and masks MUST be decoded in the browser and supplied to Canvas through an asset cache. The store MUST NOT hold every pixel, brush point, embedding, or large mask buffer.

#### Scenario: [DUI-R005-S01] Snapshot fields are serializable
- **WHEN** the UI hydrates its global store from an authoritative snapshot
- **THEN** the stored records SHALL be JSON-serializable view models and MUST omit raw image and mask pixel arrays

#### Scenario: [DUI-R005-S02] Decoded assets live in the cache
- **WHEN** the UI displays a source image and an authoritative mask
- **THEN** decoded bitmaps SHALL be obtained from the asset cache for Canvas use and MUST NOT be duplicated into the global store as the pixel source of truth

#### Scenario: [DUI-R005-S03] Uncommitted stroke points stay local
- **WHEN** the user is drawing an uncommitted brush stroke
- **THEN** stroke samples SHALL remain in local interaction state or a bounded preview buffer until submit, and the global store MUST NOT accumulate every pointer sample as durable state

### Requirement: [DUI-R006] Canvas2D layered annotation rendering
The first version of the annotation canvas MUST use Canvas2D. The canvas SHALL compose distinct layers: the source image; the authoritative mask overlay with a fixed alpha and color; the interaction layer for ROI, points, brush cursor, and uncommitted strokes; and selection or provenance hints for the current candidate. The UI MUST NOT represent each point or pixel as a DOM element. WebGL MUST NOT be the default renderer and MAY be considered only after a measured Canvas2D failure on target hardware; that upgrade is outside this change's allowed default.

#### Scenario: [DUI-R006-S01] Default renderer is Canvas2D
- **WHEN** the annotation canvas is created for a session image
- **THEN** the renderer SHALL be Canvas2D and MUST draw the image, mask overlay, interaction, and selection layers without requiring WebGL

#### Scenario: [DUI-R006-S02] Overlay style is frozen
- **WHEN** an authoritative binary mask is displayed
- **THEN** the overlay SHALL use the application's fixed color and alpha and MUST NOT expose per-image color sliders

#### Scenario: [DUI-R006-S03] Selected candidate is the only filled mask
- **WHEN** more than one candidate card is visible
- **THEN** only the selected candidate SHALL be rendered as the active filled mask, and disagreement or provenance hints MUST NOT composite every candidate as a filled mask

### Requirement: [DUI-R007] Single tested coordinate mapping module
Coordinate conversion MUST be concentrated in a single tested module that maps CSS pixels to device-pixel ratio, viewport transform (zoom and pan), and full-image integer coordinates. ROI display and submit MUST use the existing half-open `XYXY` contract in full-image coordinates. Pointer and ROI values shown to the user MUST round-trip through that module without introducing a second ad-hoc mapping.

#### Scenario: [DUI-R007-S01] Pointer maps to full-image integer coordinates
- **WHEN** the user clicks the canvas at a CSS pixel under a non-identity zoom, pan, and device-pixel ratio
- **THEN** the coordinate module SHALL emit the corresponding full-image integer point used for refinement or local-edit submission

#### Scenario: [DUI-R007-S02] ROI uses half-open XYXY
- **WHEN** the user completes a rectangular ROI drag
- **THEN** the displayed and submitted ROI SHALL be the same half-open full-image `XYXY` box, and a later display of that box MUST occupy the same image pixels

#### Scenario: [DUI-R007-S03] Unmapped ad-hoc conversion is prohibited
- **WHEN** a toolbar, overlay, or test helper needs image coordinates
- **THEN** it MUST call the shared coordinate module and MUST NOT implement a separate CSS-to-image conversion

#### Scenario: [DUI-R007-S04] User ROI and padded crop are distinct session rectangles
- **WHEN** the snapshot reports both `user_roi_full` and `crop_rect_full`
- **THEN** the UI SHALL display the user ROI and the padded work crop as those session-reported half-open full-image `XYXY` values
- **AND** MUST NOT treat a single rectangle as both user ROI and work crop when the session reports two values

### Requirement: [DUI-R008] Pointer preview versus committed stroke traffic
Pointer-move events MUST update local preview only. Strokes and other pointer-driven edits MUST be submitted on pointer-up or in throttled batches. The UI MUST NOT upload a full mask on every mouse move.

#### Scenario: [DUI-R008-S01] Move updates preview only
- **WHEN** the pointer moves while drawing an ROI, point hover, or uncommitted brush stroke
- **THEN** React SHALL update the local interaction layer and MUST NOT send a full-mask payload or an unthrottled mutation for each move

#### Scenario: [DUI-R008-S02] Pointer-up submits a delta
- **WHEN** the pointer is released after a valid brush or erase stroke
- **THEN** the UI SHALL submit a stroke or edit delta for the current session and `base_revision` rather than a complete mask bitmap of the image

#### Scenario: [DUI-R008-S03] Throttled batches remain deltas
- **WHEN** a long stroke is configured for throttled batch submit before pointer-up
- **THEN** each batch SHALL contain stroke or delta samples and MUST NOT replace the authoritative mask by uploading the entire current canvas

### Requirement: [DUI-R009] Authoritative snapshot projection and stale rejection
Session identity, revision, selected candidate, candidate summaries, capabilities, and durable outcomes MUST come from the Python authoritative snapshot. The displayed selected candidate MUST come from that snapshot after `sessions.select` or default rank-one selection performed by the session, not from React-owned selection state. The UI MUST display that snapshot and MUST NOT rewrite session history, invent candidate provenance, or apply a completed event whose session or revision is older than the current snapshot. Stale completed events MUST be discarded and MUST NOT be drawn. Production React MUST subscribe only to typed Tauri events and MUST NOT subscribe to sidecar event URLs.

#### Scenario: [DUI-R009-S01] Snapshot is the displayed authority
- **WHEN** a mutation response or snapshot fetch returns a new `revision` and selected candidate
- **THEN** the UI SHALL replace its projected session view with that snapshot and MUST NOT keep superseded candidate ids, masks, or history entries as current

#### Scenario: [DUI-R009-S02] Stale completion is discarded
- **WHEN** a `completed` event arrives with a `revision` older than the current session revision
- **THEN** the UI MUST discard the event, MUST NOT draw its mask or candidates, and MUST keep the current snapshot unchanged

#### Scenario: [DUI-R009-S03] History rewrite is rejected
- **WHEN** a local reducer, cache, or retry buffer contains a prior candidate or mask for the same session
- **THEN** the UI MUST NOT reapply that prior record over a newer authoritative revision

### Requirement: [DUI-R010] Frozen shortcut and erase-control contract
The desktop UI MUST implement the frozen shortcut contract from `annotation-workflow` UIW-R009: `1`, `2`, and `3` select candidates via `sessions.select`; left and right canvas clicks add foreground and background points; `B` activates brush; `[` and `]` shrink and grow; `F` fills holes; `X` expands ROI via `sessions.expand_roi`; `Z` undoes via `sessions.undo`; `Space` attempts Accept; and `N` advances to the next image only after the current outcome has been durably finalized. Manual-empty SHALL be requested via `sessions.begin_manual_empty`. Crop-edge warning acknowledgement SHALL be requested via `sessions.acknowledge_warning`. Erase MUST remain available as an explicit GUI control even when no keyboard shortcut is assigned. Shortcuts MUST have no effect when the corresponding candidate, capability, or state does not allow the action.

#### Scenario: [DUI-R010-S01] Candidate number keys select existing cards only
- **WHEN** the user presses `1`, `2`, or `3`
- **THEN** the UI SHALL invoke `sessions.select` for the corresponding existing candidate card without inference, and a number with no card MUST have no effect
- **AND** the displayed selection MUST come from the returned snapshot, not from React-owned selection state

#### Scenario: [DUI-R010-S02] Local-edit and workflow shortcuts match visible controls
- **WHEN** the user presses `B`, `[`, `]`, `F`, `X`, or `Z` in a state that supports the action
- **THEN** the UI SHALL activate or apply the same brush, shrink, grow, fill-holes, `sessions.expand_roi`, or `sessions.undo` operation as the visible controls

#### Scenario: [DUI-R010-S03] Accept, next-image, and erase remain distinct
- **WHEN** the user presses `Space` then `N` before durable publication, and later uses the erase control
- **THEN** `Space` SHALL start an Accept attempt, `N` SHALL remain disabled until durable `ACCEPTED` or durable `NEEDS_REVIEW`, and erase SHALL be available from an explicit control even without a shortcut

### Requirement: [DUI-R011] Uncommitted interaction stays local until submit
Uncommitted ROI, points, and brush strokes are React-owned local previews until the UI submits them with the current `session_id` and `base_revision`. Completing an ROI lock SHALL invoke `sessions.lock_roi` with `class_id` (and recipe identity if present) sourced from dataset metadata, not React-invented tensors. After a successful submit the UI MUST wait for the new authoritative revision and MUST NOT treat the local preview as committed. After submit, a conflicting or older snapshot MUST win over the preview.

#### Scenario: [DUI-R011-S01] ROI preview is not a locked session
- **WHEN** the user is dragging an ROI and has not completed the drag
- **THEN** the interaction layer MAY show the rectangle and the session MUST remain in its last authoritative state until the completed ROI is submitted

#### Scenario: [DUI-R011-S02] Submit waits for the new revision
- **WHEN** the UI submits points, `sessions.lock_roi`, or a local-edit delta
- **THEN** it SHALL wait for the returned snapshot or a matching revision event before replacing the committed overlay, and MUST NOT mark the operation durable from the local preview alone
- **AND** `sessions.lock_roi` SHALL include `class_id` from dataset metadata

#### Scenario: [DUI-R011-S03] Preview yields to authority
- **WHEN** a new snapshot arrives while an uncommitted stroke is visible
- **THEN** the UI SHALL keep the uncommitted stroke on the interaction layer until pointer-up or cancel, and MUST draw the authoritative mask from the snapshot rather than from the uncommitted pixels

### Requirement: [DUI-R012] Sidecar crash freezes mutations and preserves pixels
When the sidecar is crashed, unreachable, or restarting, recovery SHALL follow this sequence: detect crash; UI `engine_unavailable/recovering`; freeze mutations; keep displayed pixels as non-authoritative; the host MAY auto-restart the sidecar with a new port and secret; re-handshake; restore if and only if persistence verifies a draft or published pair for the current image identity; otherwise require `sessions.create`. The UI MUST NOT fake job completion, Accept, Needs Review, or candidate generation. “Unconditional restart” means respawn and assume the in-memory session survived; that assumption is forbidden. Auto-respawn of the process is allowed.

#### Scenario: [DUI-R012-S01] Crash shows recovering and freezes input
- **WHEN** the host reports that the sidecar has crashed or the engine is unavailable
- **THEN** the UI SHALL display `engine_unavailable` or `recovering`, SHALL reject new mutation commands, and SHALL keep the last painted image and overlay visible as non-authoritative

#### Scenario: [DUI-R012-S02] Crash does not complete work
- **WHEN** a proposal, refinement, Accept, or save was pending at crash time
- **THEN** the UI MUST NOT present those jobs as completed and MUST NOT invent candidates, accepted pairs, or review records

#### Scenario: [DUI-R012-S03] Recovery does not assume live session memory
- **WHEN** the sidecar later completes handshake without a verifiable persisted draft or published pair for the current image identity
- **THEN** the UI MUST require `sessions.create` and MUST NOT resume editing against an unverified in-memory guess

#### Scenario: [DUI-R012-S04] Verified draft or published pair is restored
- **WHEN** re-handshake succeeds and persistence verifies a draft or published pair for the current image identity
- **THEN** the UI SHALL project that restored snapshot
- **AND** MUST NOT treat auto-respawn as unconditional restart of live session memory

### Requirement: [DUI-R013] Dataset open uses host grant identifiers only
Opening a dataset from the desktop UI MUST use a Tauri-issued opaque `grant_id` and display name. React sends `grant_id` only; host resolves canonical path; sidecar receives the path from the host process, never from the WebView, then existence/manifest/hash checks. The UI MUST NOT send, store as a capability, or concatenate raw filesystem paths for dataset open, output folder, or optional checkpoint grants.

#### Scenario: [DUI-R013-S01] Folder picker returns a grant
- **WHEN** the user chooses a dataset folder through the host picker
- **THEN** the UI SHALL receive an opaque `grant_id` and display name and SHALL pass that `grant_id` to `datasets.open`

#### Scenario: [DUI-R013-S02] Raw path open is rejected
- **WHEN** a caller supplies a filesystem path string instead of a `grant_id`
- **THEN** the UI MUST refuse to open the dataset through that path and MUST NOT construct a grant by string concatenation

#### Scenario: [DUI-R013-S03] Output folder is a host grant
- **WHEN** the UI requests persistence
- **THEN** it SHALL pass an output `grant_id` into the host persistence command
- **AND** MUST NOT send a raw output path from the WebView

### Requirement: [DUI-R014] Overlay composition is performed in the UI
The UI MUST compose the displayed overlay from the source image plus the authoritative mask (and interaction layers). A precomposed full overlay image MUST NOT be accepted as the source of truth for the canvas.

#### Scenario: [DUI-R014-S01] Image and mask are composed locally
- **WHEN** image and mask assets are available for the current revision
- **THEN** the canvas SHALL composite them in the UI with the frozen overlay style and MUST NOT require a precomposed overlay bitmap as the authoritative frame

#### Scenario: [DUI-R014-S02] Precomposed overlay is not authoritative
- **WHEN** a transport payload includes a precomposed overlay image in addition to image and mask assets
- **THEN** the UI MUST ignore that overlay as the source of truth and SHALL continue composing from image plus mask

### Requirement: [DUI-R015] Candidate cards remain honest and uncapped by padding
The UI SHALL display only the actual number of valid candidates returned for the current revision, from zero through three. It MUST NOT fabricate, duplicate, clone, or visually pad missing candidates. Rank one SHALL be selected by default when at least one candidate exists. Inputs for absent cards MUST have no effect.

#### Scenario: [DUI-R015-S01] Zero candidates show no card
- **WHEN** proposal generation returns no valid candidates
- **THEN** the UI SHALL display no candidate card, SHALL expose proposal diagnostics, and SHALL offer `sessions.begin_manual_empty` and Needs Review actions without inventing a filler mask or keeping a React-owned empty mask as authority

#### Scenario: [DUI-R015-S02] Partial pools are not padded
- **WHEN** the snapshot contains one or two valid candidates
- **THEN** the UI SHALL render only those cards, SHALL select rank one by default, and MUST NOT clone or pad additional cards to reach three

#### Scenario: [DUI-R015-S03] Three real cards map to shortcuts
- **WHEN** the snapshot contains three distinct valid candidates
- **THEN** the UI SHALL display three real cards and SHALL map `1`, `2`, and `3` to those candidate ids without substituting a fused or duplicated mask

### Requirement: [DUI-R016] Accept is explicit and never automatic
The UI MUST create a training-eligible Accept only after an explicit user Accept command. No score, recipe, timeout, timer, model event, or idle condition MAY auto-accept. An invalid Accept attempt MUST keep the session editable, display the validation reason, and MUST NOT stop the annotation timer.

#### Scenario: [DUI-R016-S01] Only Space or the Accept control commits an attempt
- **WHEN** a valid current candidate is visible and the user has not pressed `Space` or the Accept control
- **THEN** the UI MUST NOT send Accept and MUST NOT present the session as `ACCEPTED`

#### Scenario: [DUI-R016-S02] High score and timer do not accept
- **WHEN** a candidate has the highest provider-local score or the annotation timer reaches 30 seconds
- **THEN** the UI SHALL still wait for explicit Accept, SHALL keep editing and Needs Review available, and MUST NOT auto-accept

#### Scenario: [DUI-R016-S03] Invalid Accept remains editable
- **WHEN** the user presses `Space` and crop or full-image validation fails
- **THEN** the UI SHALL show the validation reason, SHALL remain in the exact editable state reported by the snapshot, and MUST NOT record a successful Accept

### Requirement: [DUI-R017] Frozen-scope controls and prohibited fusion defaults
The v1 desktop UI MUST expose the frozen ROI, candidate, point, local-edit, timer, Accept, and Needs Review controls. It MUST NOT expose text or VLM prompting, DINO points, per-image HSV or Lab color sliders, multi-instance tabs, automatic Accept, default-on fusion, or a pixel-OR fusion control. If opt-in 2-of-3 fusion is exposed at all, it SHALL default off, SHALL never use pixel OR, and SHALL be invalidated by the first human point.

#### Scenario: [DUI-R017-S01] Cold launch control tree is frozen
- **WHEN** the annotation UI starts with default configuration
- **THEN** its visible and accessibility control tree SHALL contain the frozen annotation controls and SHALL omit VLM, DINO, per-image color sliders, multi-instance tabs, and auto-Accept

#### Scenario: [DUI-R017-S02] Fusion remains off until explicit enablement
- **WHEN** three candidates are available and the user has not explicitly enabled fusion
- **THEN** the UI SHALL display the selected candidate unchanged and MUST NOT silently replace it with a fused or OR-combined mask
