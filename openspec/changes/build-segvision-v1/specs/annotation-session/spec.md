## ADDED Requirements

### Requirement: [SES-R001] In-memory session creation

The system SHALL expose `SegVisionEngine.start(...)` as the only public operation that creates an annotation session. The operation SHALL accept an in-memory `uint8[H,W,3]` RGB image, a non-empty `image_id`, a non-empty `class_id`, a valid full-image ROI, and an optional already-parsed class recipe. The core API SHALL NOT accept annotation output paths, download models, perform annotation file I/O, import GUI types, or mutate caller-owned inputs.

#### Scenario: [SES-R001-S01] Start a valid session

- **GIVEN** a contiguous or non-contiguous `uint8[H,W,3]` RGB image, a non-empty image ID and class ID, and a valid ROI
- **WHEN** the caller invokes `SegVisionEngine.start(...)`
- **THEN** the system SHALL create a unique session at revision `1`
- **AND** the session SHALL retain an immutable image identity and an internal read-only view or copy of the pixels
- **AND** the caller's image, ROI, and recipe objects SHALL remain byte-for-byte or value-for-value unchanged

#### Scenario: [SES-R001-S02] Reject an invalid image contract

- **GIVEN** an image with a non-`uint8` dtype, fewer or more than three channels, zero height or width, or an unsupported array rank
- **WHEN** the caller invokes `SegVisionEngine.start(...)`
- **THEN** the system SHALL raise a typed input error
- **AND** the system SHALL NOT create a session or call a model backend

#### Scenario: [SES-R001-S03] Keep the core headless and side-effect free

- **GIVEN** a fake backend and in-memory inputs
- **WHEN** a caller completes start, propose, select, refine, local edit, commit, and Needs Review test workflows
- **THEN** the core SHALL complete without opening an annotation output path, writing a file, downloading an artifact, or importing a GUI module

### Requirement: [SES-R002] Frozen default annotation policy

Every session SHALL bind an immutable annotation-policy identifier. Unless a repository-owned policy explicitly overrides it through a future OpenSpec change, v1 SHALL use `segvision-visible-pixels-default-v1`: annotate visible pixels only, do not hallucinate occluded regions, include visible disconnected pieces of the selected object, exclude cast shadows and reflections, retain visible holes, and clip at the source-image boundary while recording truncation.

#### Scenario: [SES-R002-S01] Bind the default policy

- **GIVEN** no alternate repository-owned annotation policy
- **WHEN** a session starts
- **THEN** the session SHALL bind policy ID `segvision-visible-pixels-default-v1`
- **AND** every `CommitResult` and `ReviewResult` SHALL record that policy ID

#### Scenario: [SES-R002-S02] Prevent runtime policy drift

- **GIVEN** an active session bound to `segvision-visible-pixels-default-v1`
- **WHEN** a caller attempts to change hole, occlusion, shadow, reflection, or disconnected-component semantics for one image
- **THEN** the core SHALL reject the mutation as unsupported
- **AND** the session policy SHALL remain unchanged

### Requirement: [SES-R003] Session-owned opaque inference state

The session SHALL exclusively own encoded crop state, provider-specific previous mask state, candidate graph, prompt history, undo checkpoints, and timing events. Public callers SHALL refer to candidates by opaque IDs and SHALL NOT pass embedding tensors, low-resolution logits, tensor names, normalization values, or model input dimensions through the public API.

#### Scenario: [SES-R003-S01] Refine through a candidate ID

- **GIVEN** a current refinable candidate with an internally stored previous mask state
- **WHEN** the caller invokes `refine(candidate_id, new_points)`
- **THEN** the session SHALL resolve the matching encoded crop and previous mask state internally
- **AND** the caller SHALL NOT be required or permitted to provide raw logits or an embedding ID

#### Scenario: [SES-R003-S02] Reject a foreign candidate ID

- **GIVEN** a candidate ID created by another session
- **WHEN** the caller passes that ID to select, refine, edit, or commit
- **THEN** the session SHALL raise a typed candidate/session mismatch error
- **AND** the system SHALL NOT call the backend

### Requirement: [SES-R004] Monotonic revision ownership

The session SHALL maintain a monotonically increasing revision. A successful ROI change SHALL increment the revision exactly once, invalidate all prior candidates and local edits, cancel in-flight jobs when supported, and make any remaining old results ineligible for presentation or selection. Redrawing or expanding the ROI SHALL NOT reset the first-ROI-lock timestamp.

#### Scenario: [SES-R004-S01] Update the ROI

- **GIVEN** an active session at revision `r` with candidates or edits
- **WHEN** `update_roi(new_roi_full)` succeeds
- **THEN** the session revision SHALL become `r + 1`
- **AND** the old encoded state, candidates, prompt history, fusion result, and local edits SHALL become invalid
- **AND** the first-ROI-lock timestamp SHALL remain unchanged

#### Scenario: [SES-R004-S02] Discard a late result

- **GIVEN** a worker result tagged with revision `r` after the session advanced to revision `r + 1`
- **WHEN** the worker attempts to publish the result
- **THEN** the session SHALL discard the result
- **AND** the result SHALL NOT become visible, selectable, refinable, editable, or committable

#### Scenario: [SES-R004-S03] Reuse the same ROI on a different image

- **GIVEN** two images with identical dimensions and ROI coordinates
- **WHEN** a new session starts for the second image
- **THEN** the second session SHALL NOT reuse the first image's encoded crop state or candidates

### Requirement: [SES-R005] Candidate selection and capability enforcement

The session SHALL allow selection only of a current-revision candidate returned by the current proposal. Each candidate SHALL expose immutable `can_refine`, `can_local_edit`, and `can_commit` capabilities according to its source.

| Candidate source | `can_refine` | `can_local_edit` | `can_commit` |
|---|---:|---:|---:|
| `sam_box`, `sam_safe_grid`, `sam_cv` | true | true | true |
| `cv_direct` | false | true | true |
| `manual_empty` | false | true | false |
| non-empty `manual_edit` | false | true | true |

#### Scenario: [SES-R005-S01] Select a current candidate

- **GIVEN** a proposal with one to three current-revision candidates
- **WHEN** the caller selects one of those candidate IDs
- **THEN** the session SHALL mark exactly that candidate as current
- **AND** SHALL expose the capabilities defined by its source

#### Scenario: [SES-R005-S02] Reject an unsupported operation

- **GIVEN** a candidate whose relevant capability is false
- **WHEN** the caller requests that operation
- **THEN** the session SHALL raise `UnsupportedOperation`
- **AND** SHALL NOT perform a lazy encode, decode, or implicit candidate conversion

### Requirement: [SES-R006] Previous-state point refinement

Point refinement SHALL be available only for current SAM-generated candidates. Every refinement SHALL preserve the original user box prompt, append the new human points to the complete ordered human point history, use the selected candidate's previous mask state, request exactly one output mask, and add zero encoder calls.

#### Scenario: [SES-R006-S01] First human point refinement

- **GIVEN** a selected current SAM candidate and no prior human points
- **WHEN** the caller adds one valid foreground or background point
- **THEN** the decoder request SHALL contain the original user box, that human point, and the selected candidate's previous mask state
- **AND** `multimask_count` SHALL equal `1`
- **AND** encoder call count SHALL remain unchanged

#### Scenario: [SES-R006-S02] Multi-round refinement

- **GIVEN** a refined candidate produced from one prior human point
- **WHEN** the caller adds a second human point
- **THEN** the next decoder request SHALL contain both human points in insertion order
- **AND** SHALL use the immediately preceding refined candidate's mask state
- **AND** encoder call count SHALL remain unchanged

#### Scenario: [SES-R006-S03] Reject a point outside the current work crop

- **GIVEN** a full-image point that is outside `crop_rect_full`
- **WHEN** the caller requests refinement with that point
- **THEN** the session SHALL reject the point with a typed validation error
- **AND** SHALL NOT call the decoder

### Requirement: [SES-R007] Human prompts override automatic proposal state

The first valid human point in a revision SHALL invalidate any active fusion result and SHALL remove all automatic safe-grid points from subsequent refinement prompt bundles. Human foreground and background points SHALL be hard constraints for candidate validation and commit validation.

#### Scenario: [SES-R007-S01] Replace automatic prompts with human evidence

- **GIVEN** a selected `sam_safe_grid` candidate or an active opt-in fusion result
- **WHEN** the first valid human point is accepted
- **THEN** the fusion result SHALL become stale
- **AND** automatic safe-grid points SHALL NOT be included as hard prompts in the refinement request
- **AND** the original user box, human point history, and selected previous mask state SHALL remain

### Requirement: [SES-R008] Terminal local-edit model lock

The first brush, erase, grow, shrink, or fill-holes operation SHALL create a `manual_edit` candidate linked to its parent and SHALL lock out all further model calls until undo restores a SAM-ready checkpoint. Local mask operations SHALL act on a copy and SHALL NOT mutate their input mask.

#### Scenario: [SES-R008-S01] Begin local editing from a model candidate

- **GIVEN** a selected SAM candidate
- **WHEN** the caller applies the first local edit
- **THEN** the session SHALL create a `manual_edit` candidate with the SAM candidate as `parent_candidate_id`
- **AND** the new candidate SHALL retain the parent's generator provenance
- **AND** no encode or decode call SHALL occur
- **AND** point refinement SHALL become unsupported

#### Scenario: [SES-R008-S02] One-pixel grow and shrink

- **GIVEN** a crop-resolution boolean mask
- **WHEN** one grow or shrink operation is applied
- **THEN** the system SHALL use exactly one source-crop pixel with a frozen 8-connected `3x3` structuring element
- **AND** the input mask SHALL remain unchanged

#### Scenario: [SES-R008-S03] Fill visible holes

- **GIVEN** a crop-resolution boolean mask with background components
- **WHEN** fill holes is invoked
- **THEN** only background components not connected to the crop boundary SHALL become foreground
- **AND** boundary-connected background SHALL remain background

### Requirement: [SES-R009] Session-owned undo checkpoints

The session SHALL own undo history. Undo SHALL restore the exact prior candidate, mask, prompt history, capabilities, revision, and model-ready state without automatically invoking the backend.

#### Scenario: [SES-R009-S01] Undo a local edit to a SAM candidate

- **GIVEN** a `manual_edit` candidate whose previous checkpoint is a SAM candidate
- **WHEN** the caller invokes `undo()`
- **THEN** the session SHALL restore the exact SAM candidate and its previous mask state
- **AND** `can_refine` SHALL become true
- **AND** backend call count SHALL remain unchanged

#### Scenario: [SES-R009-S02] Undo with no checkpoint

- **GIVEN** a session with no earlier checkpoint
- **WHEN** the caller invokes `undo()`
- **THEN** the system SHALL return a typed no-undo result or error
- **AND** SHALL leave current state unchanged

### Requirement: [SES-R010] Manual fallback from an empty mask

The session SHALL support `begin_manual_empty()` after a recoverable proposal failure or zero-candidate result. The operation SHALL create a crop-resolution all-background `manual_empty` candidate without calling CV or the backend. An unchanged empty candidate MUST NOT be accepted.

#### Scenario: [SES-R010-S01] Begin drawing after a backend failure

- **GIVEN** a current revision with no usable candidate
- **WHEN** the caller invokes `begin_manual_empty()`
- **THEN** the session SHALL create a boolean all-false mask with the exact crop dimensions
- **AND** backend and CV call counts SHALL remain unchanged
- **AND** local editing SHALL be enabled

#### Scenario: [SES-R010-S02] Reject an unchanged empty manual mask

- **GIVEN** a `manual_empty` candidate with no foreground pixels
- **WHEN** the caller invokes `commit()`
- **THEN** commit validation SHALL fail
- **AND** the session SHALL remain editable or reviewable

### Requirement: [SES-R011] Explicit human Accept and hard commit validation

Only an explicit human-triggered `commit(candidate_id, acceptance)` call SHALL produce a `CommitResult`. The core SHALL NOT auto-accept based on score, time, CV gate, candidate rank, or absence of warnings. Before commit, the system SHALL verify that the candidate is current, non-empty, boolean, crop-sized, satisfies every human point, and has all mandatory warning acknowledgements.

#### Scenario: [SES-R011-S01] Commit a valid candidate

- **GIVEN** a current non-empty candidate satisfying all human points and required acknowledgements
- **WHEN** an explicit commit action invokes commit with `explicit_confirmation=true` and `acceptance_actor` equal to `interactive_user` or `scripted_test`
- **THEN** the system SHALL return a full-image mask and JSON-serializable sidecar data in memory
- **AND** SHALL record the selected candidate, revision, annotation policy, prompts, operations, warnings, and acceptance event
- **AND** SHALL NOT write files

#### Scenario: [SES-R011-S05] Scripted acceptance cannot prove human acceptance

- **GIVEN** an isolated automated E2E run that injects the explicit Accept control
- **WHEN** commit succeeds with `acceptance_actor="scripted_test"`
- **THEN** the result MAY prove commit mechanics for Tier A or Tier B
- **AND** it SHALL NOT count as an interactive-user Accept, real annotator outcome, or Tier C human evidence

#### Scenario: [SES-R011-S02] Reject automatic acceptance

- **GIVEN** a rank-1 candidate with a high provider-local score and no warning
- **WHEN** no human commit action occurs
- **THEN** the system SHALL NOT produce an accepted result or training-eligible annotation

#### Scenario: [SES-R011-S03] Reject point-inconsistent commit

- **GIVEN** a candidate that excludes a human foreground point or includes a human background point
- **WHEN** commit is requested
- **THEN** validation SHALL fail
- **AND** no `CommitResult` SHALL be produced

#### Scenario: [SES-R011-S04] Require crop-edge acknowledgement

- **GIVEN** a candidate carrying `TOUCHES_WORK_CROP_EDGE`
- **WHEN** commit is requested without that warning in `acknowledged_warning_codes`
- **THEN** validation SHALL fail
- **AND** the caller SHALL be able to expand the ROI, continue editing, or explicitly acknowledge the warning

### Requirement: [SES-R012] Explicit Needs Review outcome

Every active annotation session with a valid current ROI/revision SHALL permit an explicit `mark_needs_review(reason)` action while it is not inside an Accept or review publication transaction. A `ReviewResult` SHALL declare `training_eligible=false`, SHALL NOT masquerade as Accept, SHALL carry `user_roi_full` and `crop_rect_full`, and MAY include a draft crop mask only under review-specific metadata. A pre-ROI image is not an annotation session outcome in v1 and SHALL NOT be persisted as Needs Review.

#### Scenario: [SES-R012-S01] Mark an unresolved annotation for review

- **GIVEN** an active session that cannot reach training quality within the operator's budget
- **WHEN** a human invokes `mark_needs_review("boundary_unresolved_within_budget")`
- **THEN** the system SHALL return `ReviewResult`
- **AND** its status SHALL equal `needs_review`
- **AND** it SHALL NOT contain an accepted training annotation

#### Scenario: [SES-R012-S02] Thirty seconds elapse

- **GIVEN** an active session at or beyond 30 seconds from the first ROI lock
- **WHEN** no human disposition has been chosen
- **THEN** the core SHALL NOT auto-accept or auto-review the session
- **AND** the session SHALL remain available for an explicit Accept or Needs Review action

### Requirement: [SES-R013] Typed recoverable errors and proposal warnings

The public API SHALL distinguish typed misuse/failure from recoverable proposal quality warnings. At minimum it SHALL define `InvalidRoi`, `RecipeSchemaError`, `RecipeClassMismatch`, `EmbeddingExpired`, `StaleRevision`, `BackendUnavailable`, and `UnsupportedOperation`. Empty masks, crop-edge contact, low provider-local score, tiny components, low target occupancy, and invalid runtime recipe results SHALL be represented as warnings or diagnostics when manual fallback remains possible.

#### Scenario: [SES-R013-S01] Recoverable zero-candidate proposal

- **GIVEN** all generated candidates are filtered as unusable
- **WHEN** proposal completes
- **THEN** the system SHALL return a zero-candidate `ProposalSet` with explanatory warnings and diagnostics
- **AND** SHALL NOT fabricate a candidate or raise an unrecoverable exception
- **AND** manual fallback and Needs Review SHALL remain available
