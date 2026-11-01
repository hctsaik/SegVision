## ADDED Requirements

### Requirement: [UIW-R001] The GUI shall implement the annotation session state machine
The desktop GUI SHALL expose a single current annotation session and SHALL transition it only through `IMAGE_OPEN`, `ROI_LOCKED`, `PROPOSING`, `PROPOSAL_READY`, `MANUAL_EMPTY`, `REFINE_PENDING`, `REFINED_READY`, `LOCAL_EDITING`, `VALIDATING`, `COMMITTING`, `SAVING`, `SAVE_FAILED`, `REVIEW_SAVING`, `REVIEW_SAVE_FAILED`, `ACCEPTED`, and `NEEDS_REVIEW` according to the current candidate capabilities and operation result. `ACCEPTED` and `NEEDS_REVIEW` are terminal only after their respective durable publication succeeds. The GUI MUST NOT represent an annotation as accepted before validation, commit, and pair-consistent publication have completed.

#### Scenario: [UIW-R001-S01] Successful model-assisted annotation
- **WHEN** a user locks an ROI, selects a generated candidate, optionally refines or locally edits it, explicitly accepts it, and persistence succeeds
- **THEN** the session SHALL traverse the applicable ready and editing states, then `VALIDATING`, `COMMITTING`, `SAVING`, and `ACCEPTED` in order

#### Scenario: [UIW-R001-S02] Invalid transition is rejected
- **WHEN** an input requests an operation that is not valid in the current state
- **THEN** the GUI SHALL leave the current mask and state unchanged and SHALL expose a machine-readable reason instead of invoking hidden model or persistence work

#### Scenario: [UIW-R001-S03] Validation failure returns to editing
- **WHEN** an Accept attempt fails crop-candidate validation
- **THEN** the session SHALL return to the exact editable state from which validation started and SHALL preserve the current candidate and undo history

### Requirement: [UIW-R002] The workflow shall distinguish the user ROI from the work crop
The GUI and controller MUST preserve `user_roi_full` as the user box and model box prompt, MUST derive a separately padded and clamped `crop_rect_full`, and MUST display enough context to distinguish the two. The GUI SHALL define a rectangular user ROI with two primary corner clicks; dragging SHALL NOT be required. Changing or expanding the ROI SHALL create a new session revision and SHALL invalidate candidate and edit handles from the prior revision.

#### Scenario: [UIW-R002-S01] Initial ROI lock
- **WHEN** the user clicks two opposite corners to define the first valid rectangular ROI
- **THEN** the workflow SHALL enter `ROI_LOCKED`, record `first_roi_locked`, derive the padded crop, and start proposal work for the new revision

#### Scenario: [UIW-R002-S02] ROI redraw invalidates old state
- **WHEN** the user redraws the ROI after candidates, prompts, or edits exist
- **THEN** the workflow SHALL increment the revision, discard the old selected state and edits, and re-run the recipe/proposal path for the new crop

#### Scenario: [UIW-R002-S03] Expand ROI follows the current recipe path
- **WHEN** the user invokes Expand ROI for a crop-edge risk
- **THEN** the workflow SHALL expand and clamp the work region, create a new revision, re-run the configured recipe, and encode only when the new proposal path is not `cv_direct`

### Requirement: [UIW-R003] The GUI shall present zero to three real candidates
The GUI SHALL display the actual number of valid candidates returned by the session, from zero through three, SHALL select rank one by default when at least one candidate exists, and MUST NOT fabricate, duplicate, or visually pad missing candidates. Only the selected candidate SHALL be rendered as the active filled mask.

#### Scenario: [UIW-R003-S01] Zero candidates
- **WHEN** proposal generation returns no valid candidates
- **THEN** the GUI SHALL display no candidate card, SHALL expose proposal diagnostics, and SHALL offer manual-empty and Needs Review actions

#### Scenario: [UIW-R003-S02] One candidate
- **WHEN** proposal generation returns one valid candidate
- **THEN** the GUI SHALL display and select only card 1, and inputs for cards 2 and 3 SHALL have no effect

#### Scenario: [UIW-R003-S03] Two candidates
- **WHEN** proposal generation returns two valid candidates
- **THEN** the GUI SHALL display only cards 1 and 2, SHALL allow both to be selected, and input for card 3 SHALL have no effect

#### Scenario: [UIW-R003-S04] Three candidates
- **WHEN** proposal generation returns three valid candidates
- **THEN** the GUI SHALL display three distinct cards and SHALL map selection inputs 1, 2, and 3 to their corresponding candidate IDs

#### Scenario: [UIW-R003-S05] Candidate pool exceeds the display cap
- **WHEN** internal box, safe-grid, or `sam_cv` generation produces more than three candidate variants
- **THEN** candidate policy SHALL deterministically validate, deduplicate, rank, and cap the displayed result at three without modifying source masks to merge them

### Requirement: [UIW-R004] Candidate controls shall respect candidate capabilities
The GUI SHALL enable point refinement only when the selected candidate declares `can_refine=true`, SHALL enable local editing only when `can_local_edit=true`, and SHALL allow Accept only when `can_commit=true` and validation succeeds. Direct-CV and manual candidates MUST NOT trigger lazy model encoding.

#### Scenario: [UIW-R004-S01] SAM candidate permits point refinement
- **WHEN** the selected source is `sam_box`, `sam_safe_grid`, or `sam_cv`
- **THEN** foreground and background point controls SHALL be enabled and a point input SHALL enter `REFINE_PENDING`

#### Scenario: [UIW-R004-S02] CV-direct candidate rejects point refinement
- **WHEN** the selected source is `cv_direct`
- **THEN** foreground and background point controls SHALL be disabled with an explanatory status, local editing SHALL remain available, and no encoder call SHALL be made

#### Scenario: [UIW-R004-S03] Manual candidate rejects point refinement
- **WHEN** the current source is `manual_empty` or `manual_edit`
- **THEN** point controls SHALL be disabled, local editing SHALL remain available, and direct API refinement SHALL return `UnsupportedOperation`

### Requirement: [UIW-R005] Point refinement shall be previous-state and revision safe
For a refinable candidate, the workflow SHALL send full-image foreground or background points to the session, SHALL retain the original box and accumulated human points, SHALL refine from the selected candidate's opaque previous state, and MUST NOT cause another encoder call. The first human point MUST invalidate auto-grid prompts and any current fusion result.

#### Scenario: [UIW-R005-S01] Foreground point refinement
- **WHEN** the user left-clicks a missing foreground area on a refinable candidate
- **THEN** the workflow SHALL record a foreground point, request one decoder result from the selected previous state, and show the returned refined candidate only if its session and revision remain current

#### Scenario: [UIW-R005-S02] Background point refinement
- **WHEN** the user right-clicks an over-segmented area on a refinable candidate
- **THEN** the workflow SHALL record a background point, preserve all prior human points, and request one decoder result without re-encoding

#### Scenario: [UIW-R005-S03] Candidate is switched before refinement
- **WHEN** the user selects a different candidate and then supplies a point
- **THEN** the refinement request SHALL use the newly selected candidate's previous state rather than the former or default candidate state

#### Scenario: [UIW-R005-S04] First human point supersedes automatic prompts
- **WHEN** the first valid human point is accepted
- **THEN** the workflow SHALL remove all auto-grid prompts and invalidate the current fusion result before producing the human-guided refinement

### Requirement: [UIW-R006] Manual-empty fallback shall be usable without a model result
When proposal generation returns no candidate or a recoverable backend failure occurs, the workflow SHALL allow the user to create a crop-resolution all-background manual candidate without invoking the backend. The empty candidate MUST fail Accept validation until a local operation creates a non-empty foreground or the user chooses Needs Review.

#### Scenario: [UIW-R006-S01] Draw from an empty mask
- **WHEN** the user chooses manual fallback after a zero-candidate proposal and draws foreground with the brush
- **THEN** the workflow SHALL enter `LOCAL_EDITING`, create a `manual_edit` candidate with manual generator provenance, and SHALL make no additional backend call

#### Scenario: [UIW-R006-S02] Empty manual mask cannot be accepted
- **WHEN** the user attempts Accept before adding any foreground to `manual_empty`
- **THEN** validation SHALL fail, the annotation timer SHALL continue, and no commit or accepted output SHALL start

#### Scenario: [UIW-R006-S03] Backend failure falls back safely
- **WHEN** proposal work times out or raises a recoverable backend failure
- **THEN** the GUI SHALL remain responsive and SHALL offer both manual-empty and Needs Review without displaying a stale or invented candidate

### Requirement: [UIW-R007] Local editing shall lock out model mutation
The first brush, erase, grow, shrink, or fill-holes operation SHALL create a manual checkpoint and SHALL prevent new model calls or late model results from modifying the mask. The workflow MUST NOT merge model output into manual pixels in v1.

#### Scenario: [UIW-R007-S01] Local operation changes only the current mask
- **WHEN** the user applies brush, erase, grow, shrink, or fill holes
- **THEN** the session SHALL record the operation and resulting manual candidate while backend encode and decode counts remain unchanged

#### Scenario: [UIW-R007-S02] Late model result arrives after local edit
- **WHEN** an older model job completes after local editing has begun
- **THEN** the result SHALL be discarded and the manual mask SHALL remain byte-for-byte unchanged

#### Scenario: [UIW-R007-S03] Erase returns a manual mask to empty
- **WHEN** local erase removes every foreground pixel
- **THEN** the current candidate SHALL remain editable but SHALL fail Accept validation until foreground is restored or Needs Review is selected

### Requirement: [UIW-R008] Undo shall restore session-owned checkpoints
Undo SHALL be implemented by the annotation session rather than a separate GUI mask history, SHALL restore the exact preceding candidate and operation state, and MUST NOT invoke the backend. Point refinement MAY become available again only after undo has restored a refinable model checkpoint.

#### Scenario: [UIW-R008-S01] Undo a local operation
- **WHEN** the user presses Undo after a local edit
- **THEN** the prior mask, source, provenance, capability set, and operation history SHALL be restored exactly without a decoder call

#### Scenario: [UIW-R008-S02] Undo returns to a SAM checkpoint
- **WHEN** repeated Undo reaches the most recent SAM-generated checkpoint
- **THEN** point tools SHALL become enabled again and a later point SHALL refine from that restored previous state

#### Scenario: [UIW-R008-S03] Undo has no earlier checkpoint
- **WHEN** Undo is invoked at the first retained checkpoint
- **THEN** the session SHALL remain unchanged and SHALL return a non-destructive no-op result

### Requirement: [UIW-R009] The GUI shall implement the frozen shortcut contract
The GUI MUST map `1`, `2`, and `3` to candidate selection; left and right canvas clicks to foreground and background points; `B` to brush; `[` and `]` to shrink and grow; `F` to fill holes; `X` to Expand ROI; `Z` to Undo; `Space` to Accept attempt; and `N` to next image only after the current outcome has been durably finalized. Erase SHALL be available as an explicit GUI control even when no keyboard shortcut is assigned.

#### Scenario: [UIW-R009-S01] Candidate keyboard selection
- **WHEN** the user presses a candidate number for an existing card
- **THEN** that card and its exact mask SHALL become selected without invoking model inference

#### Scenario: [UIW-R009-S02] Local-edit keyboard operations
- **WHEN** the user presses `B`, `[`, `]`, or `F` in an editable annotation state
- **THEN** the matching brush, shrink, grow, or fill operation SHALL be activated or applied to the current candidate

#### Scenario: [UIW-R009-S03] Expand and undo shortcuts
- **WHEN** the user presses `X` or `Z` in a state that supports the corresponding action
- **THEN** the workflow SHALL perform Expand ROI or session Undo using the same core APIs as the visible controls

#### Scenario: [UIW-R009-S04] Accept and next-image shortcuts are separate
- **WHEN** the user presses `Space` and then presses `N` before pair publication succeeds
- **THEN** `Space` SHALL start an Accept attempt and `N` SHALL remain disabled until the session reaches durable `ACCEPTED` or durable `NEEDS_REVIEW`

### Requirement: [UIW-R010] Uncertainty and crop-edge risk shall be visible and actionable
The GUI SHALL render candidate disagreement and work-crop edge contact as distinguishable uncertainty reasons, MUST test edge contact against `crop_rect_full` rather than `user_roi_full`, and SHALL offer Expand ROI when work-crop truncation is possible.

#### Scenario: [UIW-R010-S01] Candidate disagreement is shown
- **WHEN** displayed candidates disagree on pixels
- **THEN** the GUI SHALL show their union-minus-intersection disagreement layer without compositing all candidates as filled masks

#### Scenario: [UIW-R010-S02] Mask touches only the user ROI
- **WHEN** a candidate touches `user_roi_full` but does not touch `crop_rect_full`
- **THEN** the GUI MUST NOT report a work-crop edge warning solely for that contact

#### Scenario: [UIW-R010-S03] Mask touches the work crop
- **WHEN** a candidate touches `crop_rect_full`
- **THEN** the GUI SHALL show a crop-edge warning and SHALL require Expand ROI or an explicit recorded acknowledgement before Accept validation can pass

### Requirement: [UIW-R011] Accept shall be explicit, validated, and non-automatic
The workflow MUST create a training annotation only after an explicit user Accept. An Accept attempt SHALL validate the non-empty crop mask, binary shape, human-point constraints, current revision, and crop-edge acknowledgement before commit; it SHALL then validate the full-image result before persistence. No model, recipe, score, timeout, or timer condition MAY auto-accept a mask.

#### Scenario: [UIW-R011-S01] Valid Accept
- **WHEN** the user presses `Space` with a valid current candidate
- **THEN** the workflow SHALL record `accept_attempted`, pass crop validation, record `accept_validation_passed`, commit and validate the full result, and proceed to saving

#### Scenario: [UIW-R011-S02] Invalid Accept does not stop the timer
- **WHEN** the user presses `Space` with an empty, stale, shape-invalid, point-violating, or unacknowledged crop-edge candidate
- **THEN** the workflow SHALL record the failed attempt, remain editable, display the validation reason, and MUST NOT record `accept_validation_passed`

#### Scenario: [UIW-R011-S03] High model score does not auto-accept
- **WHEN** a candidate has the highest possible provider-local score
- **THEN** the workflow SHALL still wait for explicit user Accept

### Requirement: [UIW-R012] Save failure shall preserve the live workflow
The workflow SHALL remain in `SAVE_FAILED` when accepted-pair persistence fails, SHALL retain the exact validated result and session evidence for retry, and MUST keep next-image navigation disabled until publication succeeds. Retrying MUST NOT require another model inference or destroy the user's mask.

#### Scenario: [UIW-R012-S01] Save fails and succeeds on retry
- **WHEN** persistence fails after validation and the user retries after the storage condition is corrected
- **THEN** the session SHALL move from `SAVING` to `SAVE_FAILED`, retain the validated result, retry the same pair, and enter `ACCEPTED` only after success

#### Scenario: [UIW-R012-S02] Next is attempted after save failure
- **WHEN** the user presses `N` while the session is `SAVE_FAILED`
- **THEN** the current image and session SHALL remain active and no accepted annotation SHALL be inferred from the failed save

### Requirement: [UIW-R013] Needs Review shall be a first-class non-training outcome
The states `ROI_LOCKED`, `PROPOSING`, `PROPOSAL_READY`, `MANUAL_EMPTY`, `REFINE_PENDING`, `REFINED_READY`, `LOCAL_EDITING`, and `SAVE_FAILED` SHALL permit an explicit Needs Review request. `IMAGE_OPEN` has no review action because no valid ROI/revision geometry exists. `VALIDATING`, `COMMITTING`, `SAVING`, `REVIEW_SAVING`, `ACCEPTED`, and terminal `NEEDS_REVIEW` SHALL reject a new review request, preventing an accepted publication race. A valid request MUST terminate or cancel active model work, transition to `REVIEW_SAVING`, MUST NOT produce a training-eligible accepted annotation, and SHALL preserve a structured reason and optional review-only draft. It SHALL become terminal `NEEDS_REVIEW` only after durable review metadata publication; a failure SHALL enter `REVIEW_SAVE_FAILED` and retain an exact retryable review result.

#### Scenario: [UIW-R013-S01] User selects Needs Review from an active state
- **WHEN** the user chooses Needs Review from ROI-locked, proposing, candidate-ready, refine-pending, refined, manual-empty, local-editing, or save-failed state
- **THEN** active work SHALL be cancelled or made stale, the workflow SHALL enter `REVIEW_SAVING`, and no accepted training output SHALL be exposed
- **AND** successful review publication SHALL enter `NEEDS_REVIEW` and enable next-image navigation

#### Scenario: [UIW-R013-S02] Review publication fails and retries
- **WHEN** review metadata publication fails from `REVIEW_SAVING`
- **THEN** the workflow SHALL enter `REVIEW_SAVE_FAILED`, retain the exact review result, keep next-image navigation disabled, and permit a persistence-only retry
- **AND** a successful retry SHALL enter `NEEDS_REVIEW` without a model call or accepted-pair publication

#### Scenario: [UIW-R013-S03] Timeout is sent to review
- **WHEN** model work times out and the user chooses Needs Review
- **THEN** the outcome SHALL record both the timeout and review reason and MUST NOT increment successful Accept counts

#### Scenario: [UIW-R013-S04] Durable Needs Review is terminal
- **WHEN** a session has reached `NEEDS_REVIEW`
- **THEN** later model results or Accept inputs SHALL NOT convert that same session into an accepted annotation, and next-image navigation SHALL be enabled

### Requirement: [UIW-R014] The GUI timer shall use the first valid ROI lock
The GUI SHALL display elapsed annotation time from `first_roi_locked`, SHALL preserve that origin across ROI redraw, Expand ROI, candidate selection, refinement, and local editing, and MUST NOT stop the annotation timer for an invalid Accept attempt. Reaching 30 seconds SHALL NOT auto-accept a mask; the GUI SHALL continue to permit safe editing or Needs Review while telemetry records the SLO outcome.

#### Scenario: [UIW-R014-S01] ROI redraw does not reset time
- **WHEN** the user redraws or expands the ROI after the annotation timer has started
- **THEN** the displayed and recorded duration SHALL continue from the first valid ROI lock

#### Scenario: [UIW-R014-S02] Invalid Accept does not reset or stop time
- **WHEN** Accept validation fails and the user continues editing
- **THEN** the timer SHALL continue from its original start until a later validation passes or Needs Review is chosen

#### Scenario: [UIW-R014-S03] Thirty seconds elapse without a valid mask
- **WHEN** the timer reaches 30 seconds before a valid Accept
- **THEN** the GUI SHALL NOT auto-accept, SHALL keep manual and Needs Review controls available, and SHALL mark any later Accept as a time-SLO failure

### Requirement: [UIW-R015] Model work shall not block the annotation UI
Proposal and refinement jobs SHALL execute outside the GUI event loop with bounded CPU threads. The GUI MUST remain responsive to redraw, cancellation, pan/zoom, manual fallback, and Needs Review while model work is pending, and stale completions MUST be rejected before presentation.

#### Scenario: [UIW-R015-S01] ROI changes during proposal
- **WHEN** a proposal job is pending and the user redraws the ROI
- **THEN** the old job SHALL be cancelled when possible or rejected on completion, and only candidates from the new revision SHALL become selectable

#### Scenario: [UIW-R015-S02] ROI changes during refinement
- **WHEN** a decoder job is pending and the user changes the ROI
- **THEN** the pending result SHALL NOT update the canvas and the new revision SHALL own all subsequent state

#### Scenario: [UIW-R015-S03] GUI remains responsive during encoding
- **WHEN** the backend encoder is deliberately blocked by a deterministic test barrier
- **THEN** the GUI SHALL continue processing paint, pan/zoom, ROI-redraw, and Needs Review events

### Requirement: [UIW-R016] The v1 GUI shall expose only frozen-scope annotation controls
The v1 GUI MUST NOT expose text/VLM prompting, DINO points, per-image HSV or Lab sliders, multi-instance tabs, automatic Accept, or default fusion. If opt-in 2-of-3 fusion is exposed, it SHALL default off, SHALL never use pixel OR, and SHALL be invalidated by the first human point.

#### Scenario: [UIW-R016-S01] Cold GUI launch
- **WHEN** the annotation GUI starts with default configuration
- **THEN** its visible and accessibility control tree SHALL contain the frozen ROI, candidate, point, local-edit, timer, Accept, and Needs Review controls and SHALL omit out-of-scope controls

#### Scenario: [UIW-R016-S02] Fusion remains opt-in
- **WHEN** three candidates are available and the user has not explicitly enabled fusion
- **THEN** the GUI SHALL display the selected candidate unchanged and MUST NOT silently replace it with a fused mask
