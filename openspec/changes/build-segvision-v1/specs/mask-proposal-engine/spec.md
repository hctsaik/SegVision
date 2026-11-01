## ADDED Requirements

### Requirement: [MPE-R001] Narrow interactive-mask backend protocol

Every mask backend SHALL expose immutable identity and capabilities plus `encode`, `decode`, `mask_prompt_from_binary`, and `release` operations. Capabilities SHALL declare the model input contract, box support, point support, previous-mask support, maximum multimask count, and provider score kind. GUI code MUST NOT depend on backend tensor names, normalization, model input size, embedding shape, or mask-state shape.

#### Scenario: [MPE-R001-S01] Discover backend capabilities

- **GIVEN** a configured backend implementation
- **WHEN** `SegVisionEngine` initializes it
- **THEN** the engine SHALL obtain a complete `ModelIdentity` and `BackendCapabilities`
- **AND** SHALL reject a backend that does not support box prompts, point prompts, previous mask state, and at least three initial masks

#### Scenario: [MPE-R001-S02] Keep backend details opaque

- **GIVEN** a successful encode and decode
- **WHEN** candidates are returned through the public session API
- **THEN** callers SHALL receive crop-resolution masks, IDs, metrics, warnings, and provenance
- **AND** SHALL NOT receive raw embeddings, tensor names, or provider-specific mask-state arrays

### Requirement: [MPE-R002] MobileSAM CPU correctness baseline

The first real backend SHALL be MobileSAM TinyViT with PyTorch on CPU using a caller-configured, checksum-verified, locally available artifact. It SHALL NOT require CUDA, a hosted service, an account, or a runtime download. EdgeSAM MUST NOT be a company shipping backend without separately recorded written commercial permission. A complete MobileSAM ONNX encoder deployment MUST NOT be claimed unless a future validated backend explicitly supplies it.

#### Scenario: [MPE-R002-S01] Initialize the approved baseline offline

- **GIVEN** an approved MobileSAM checkpoint whose SHA-256 matches the configured identity
- **WHEN** the backend initializes on a network-disabled Windows CPU host without CUDA
- **THEN** initialization SHALL succeed using CPU
- **AND** SHALL NOT attempt a network request or artifact download

#### Scenario: [MPE-R002-S02] Reject an unapproved or mismatched artifact

- **GIVEN** a missing approval record or a checkpoint whose SHA-256 differs from configuration
- **WHEN** backend initialization is attempted
- **THEN** initialization SHALL fail before model deserialization
- **AND** no proposal SHALL run

### Requirement: [MPE-R003] Immutable backend inputs

Backend operations SHALL NOT mutate crop pixels, prompt objects, binary CV masks, previous mask state objects, or caller-owned arrays. Backend results SHALL own their returned memory or clearly expose immutable views.

#### Scenario: [MPE-R003-S01] Encode and decode preserve inputs

- **GIVEN** copies or hashes of a crop, prompt bundle, and previous mask state
- **WHEN** encode and decode complete
- **THEN** all input copies or hashes SHALL remain unchanged

### Requirement: [MPE-R004] Encode-once proposal invariant

Every non-`cv_direct` crop revision SHALL invoke backend `encode` exactly once before proposal decoding. Native box masks, safe-grid probes, `sam_cv`, candidate validation, ranking, selection, and all point refinements SHALL reuse that encoded state. A `cv_direct` revision SHALL invoke the backend zero times.

#### Scenario: [MPE-R004-S01] Box-only proposal

- **GIVEN** a current revision with CV disabled or invalid
- **WHEN** the engine produces native box candidates
- **THEN** encode call count SHALL equal `1`
- **AND** initial box decode call count SHALL equal `1`

#### Scenario: [MPE-R004-S02] Proposal with safe grid and coarse CV

- **GIVEN** a current revision with a usable safe-grid probe and a `coarse` CV result
- **WHEN** all proposal variants are generated
- **THEN** encode call count SHALL still equal `1`
- **AND** safe-grid and `sam_cv` SHALL add decoder calls only

#### Scenario: [MPE-R004-S03] CV-direct proposal

- **GIVEN** an enabled fixed recipe whose gate returns `direct`
- **WHEN** the engine builds the proposal
- **THEN** encode and decode call counts SHALL both equal `0`

### Requirement: [MPE-R005] Encoded-state identity and release

Encoded crop state SHALL be bound to session ID, revision, backend/checkpoint fingerprint, preprocessing version, crop pixel fingerprint, and `crop_rect_full`. It SHALL be kept only in bounded memory and SHALL support explicit release. State from a different identity MUST NOT be decoded.

#### Scenario: [MPE-R005-S01] Reject mismatched encoded state

- **GIVEN** encoded state from another revision, crop, checkpoint, preprocessing version, or session
- **WHEN** decode is requested
- **THEN** the backend or session SHALL raise `EmbeddingExpired` or `StaleRevision`
- **AND** SHALL NOT produce a candidate

#### Scenario: [MPE-R005-S02] Release state after ROI change

- **GIVEN** an encoded crop for the current ROI
- **WHEN** ROI changes or the session closes
- **THEN** the encoded state SHALL be released or evicted from the bounded in-memory cache
- **AND** SHALL NOT be persisted to disk

### Requirement: [MPE-R006] Initial box-first multimask behavior

For a non-direct proposal, the first decoder request SHALL use the mapped `user_roi_full` as the box prompt, no human points, no automatic points, and no previous mask state. It SHALL request exactly three native masks through `multimask_count=3`.

#### Scenario: [MPE-R006-S01] Generate native box candidates

- **GIVEN** a valid encoded crop and mapped user box
- **WHEN** initial proposal decode runs
- **THEN** the request SHALL contain the user box only
- **AND** `multimask_count` SHALL equal `3`
- **AND** the backend SHALL return at most three native masks with provider-local metrics and opaque mask states

#### Scenario: [MPE-R006-S02] Backend returns fewer masks

- **GIVEN** a valid initial decode that returns fewer than three masks
- **WHEN** the proposal is assembled
- **THEN** the engine SHALL use only the returned masks
- **AND** SHALL NOT repeat or synthesize masks to fill three slots

### Requirement: [MPE-R007] Frozen candidate-policy defaults

The v1 candidate policy SHALL use these defaults unless changed by a future OpenSpec change: `max_candidates=3`, `duplicate_iou_threshold=0.995`, `near_full_reject_fraction=0.995`, `safe_grid_max_points=2`, `safe_grid_margin_fraction=0.01`, `safe_grid_margin_min_px=2`, and `fusion_enabled_by_default=false`. Missing required policy values MUST fail engine construction rather than acquire hidden defaults.

#### Scenario: [MPE-R007-S01] Enforce the maximum

- **GIVEN** more than three internally generated valid candidate variants
- **WHEN** candidate slot allocation completes
- **THEN** the public proposal SHALL contain at most three candidates

#### Scenario: [MPE-R007-S02] Reject incomplete policy configuration

- **GIVEN** an explicitly supplied candidate-policy object missing a required v1 field
- **WHEN** the engine is constructed
- **THEN** construction SHALL fail with a typed configuration error
- **AND** SHALL NOT invent a threshold

### Requirement: [MPE-R008] Hard candidate validation

Before ranking, the engine SHALL reject masks that are empty, have foreground area fraction greater than or equal to `0.995`, have the wrong shape or dtype, or violate any current human foreground/background point. Crop-edge contact and low provider-local score SHALL be warnings rather than implicit geometry edits or automatic Accept decisions.

#### Scenario: [MPE-R008-S01] Reject an empty candidate

- **GIVEN** a candidate with zero foreground pixels
- **WHEN** validation runs
- **THEN** the candidate SHALL be removed
- **AND** proposal diagnostics SHALL record `EMPTY_MASK`

#### Scenario: [MPE-R008-S02] Reject a near-full candidate

- **GIVEN** a crop mask whose foreground fraction is at least `0.995`
- **WHEN** validation runs
- **THEN** the candidate SHALL be removed
- **AND** the configured threshold SHALL be recorded in diagnostics

#### Scenario: [MPE-R008-S03] Reject a point-violating candidate

- **GIVEN** a candidate that excludes any human foreground point or includes any human background point
- **WHEN** validation runs
- **THEN** the candidate SHALL be removed regardless of provider score

#### Scenario: [MPE-R008-S04] Preserve a crop-edge candidate for human decision

- **GIVEN** an otherwise valid candidate touching the work-crop edge
- **WHEN** validation runs
- **THEN** the candidate SHALL remain eligible
- **AND** SHALL carry `TOUCHES_WORK_CROP_EDGE`
- **AND** SHALL NOT be eroded, cropped, or auto-accepted

### Requirement: [MPE-R009] Deterministic candidate deduplication

Candidates with pairwise binary IoU greater than or equal to `0.995` SHALL be treated as duplicates. The candidate with higher provider-local quality SHALL remain; a quality tie SHALL prefer higher stability, then lower native output index, then lexicographically smaller candidate ID.

#### Scenario: [MPE-R009-S01] Deduplicate native masks

- **GIVEN** two valid native masks with IoU `>= 0.995`
- **WHEN** deduplication runs
- **THEN** exactly one SHALL remain
- **AND** the survivor SHALL be chosen by the frozen tie-break order

#### Scenario: [MPE-R009-S02] Preserve meaningfully different masks

- **GIVEN** two valid candidates with IoU below `0.995`
- **WHEN** deduplication runs
- **THEN** neither SHALL be removed as a duplicate

### Requirement: [MPE-R010] Provider-local deterministic ranking

Raw scores SHALL be interpreted only according to `BackendCapabilities.score_kind` and SHALL NOT be presented as calibrated cross-provider confidence. Native candidates SHALL rank by descending provider-local quality, descending stability, ascending native output index, and ascending candidate ID. Candidate warnings SHALL be displayed and recorded but MUST NOT be converted into an undocumented numeric confidence penalty.

#### Scenario: [MPE-R010-S01] Rank equal-quality candidates

- **GIVEN** native candidates with equal provider-local quality but different stability
- **WHEN** ranking runs
- **THEN** the candidate with higher stability SHALL rank first

#### Scenario: [MPE-R010-S02] Reject cross-provider score voting

- **GIVEN** a SAM score and a CV diagnostic value
- **WHEN** candidate allocation runs
- **THEN** the engine SHALL NOT add, average, normalize, or vote those numbers as a unified confidence

### Requirement: [MPE-R011] Bounded safe-grid prompt probe

Automatic positive probes SHALL run only after at least two valid native box masks exist. The engine SHALL intersect all valid native box masks, compute a safe interior margin of `max(2, ceil(0.01 * min(crop_height, crop_width)))` pixels, and evaluate the normalized `3x3` user-ROI grid at coordinates `{0.25,0.50,0.75} x {0.25,0.50,0.75}`. It SHALL deterministically choose at most two surviving, spatially separated points and perform at most one additional decode using the original box plus those points, `multimask_count=1`, and no additional encode.

#### Scenario: [MPE-R011-S01] Generate one safe-grid variant

- **GIVEN** at least two valid native box masks and one or more normalized grid positions inside their safe interior
- **WHEN** safe-grid probing runs
- **THEN** it SHALL choose no more than two points
- **AND** SHALL perform at most one extra decoder call
- **AND** encode call count SHALL remain unchanged
- **AND** any returned candidate SHALL use source `sam_safe_grid`

#### Scenario: [MPE-R011-S02] Skip unsafe probes

- **GIVEN** fewer than two valid native masks or no normalized grid point inside the safe interior
- **WHEN** safe-grid probing is evaluated
- **THEN** no automatic point SHALL be created
- **AND** no safe-grid decoder call SHALL occur

#### Scenario: [MPE-R011-S03] Thin stable intersection

- **GIVEN** a non-empty stable intersection that disappears under the frozen safe margin
- **WHEN** safe-grid probing is evaluated
- **THEN** the engine SHALL skip the probe rather than reduce the margin or place an unsafe point

### Requirement: [MPE-R012] Coarse-CV mask-prompt candidate

A `coarse` CV result SHALL be converted by the backend into provider-specific mask state and decoded as `sam_cv`. The raw CV mask SHALL NOT become a public candidate, SHALL NOT be converted into positive/negative points, and SHALL NOT replace the RGB crop.

#### Scenario: [MPE-R012-S01] Decode a coarse mask prompt

- **GIVEN** a valid encoded crop and a `coarse` binary CV mask
- **WHEN** the engine generates the CV-assisted proposal
- **THEN** it SHALL call `mask_prompt_from_binary` exactly once
- **AND** SHALL perform decoder-only inference with the original box and converted mask state
- **AND** any surviving result SHALL use source `sam_cv`

#### Scenario: [MPE-R012-S02] Reject backend without mask-prompt support

- **GIVEN** a configured backend that cannot convert or decode a binary mask prompt
- **WHEN** engine capability validation runs
- **THEN** the backend SHALL be rejected for v1
- **AND** the engine SHALL NOT approximate the CV mask with automatic points

### Requirement: [MPE-R013] Deterministic public slot allocation

The public candidate list SHALL contain at most three masks and SHALL always be compacted into contiguous cards `1..N` with no empty placeholder. Allocation SHALL first append the highest-ranked valid `sam_box` when present, then append the geometrically most distinct valid `sam_box` or `sam_safe_grid` alternative when present, reserve capacity for and append a valid `sam_cv`, and finally fill any remaining capacity with the next valid non-duplicate ranked alternatives. Ties SHALL use the frozen ranking key. Consequently `sam_cv` is card 3 only when two earlier candidates exist, card 2 after one, and card 1 when it is the sole valid result. A `cv_direct` proposal SHALL contain only that one candidate.

#### Scenario: [MPE-R013-S01] Allocate box and CV candidates

- **GIVEN** at least two valid box/grid candidates and one valid `sam_cv`
- **WHEN** public slot allocation runs
- **THEN** slot 1 SHALL be the best `sam_box`
- **AND** slot 2 SHALL be the alternative with the lowest IoU to slot 1, subject to deterministic ties
- **AND** slot 3 SHALL be `sam_cv`

#### Scenario: [MPE-R013-S02] Allocate no CV candidate

- **GIVEN** no valid `sam_cv` and two valid non-duplicate native candidates
- **WHEN** public slot allocation runs
- **THEN** the proposal SHALL contain exactly those two candidates
- **AND** SHALL NOT fabricate a third candidate

#### Scenario: [MPE-R013-S03] Allocate a sole CV-assisted candidate

- **GIVEN** every box and grid candidate is invalid or duplicate and one valid `sam_cv` remains
- **WHEN** public slot allocation runs
- **THEN** the proposal SHALL contain exactly one contiguous card and card 1 SHALL be `sam_cv`

#### Scenario: [MPE-R013-S04] Allocate one box and one CV-assisted candidate

- **GIVEN** one valid `sam_box` and one valid `sam_cv` remain
- **WHEN** public slot allocation runs
- **THEN** card 1 SHALL be the box candidate and card 2 SHALL be `sam_cv` with no empty card

#### Scenario: [MPE-R013-S05] Direct CV proposal

- **GIVEN** a fixed recipe result with gate `direct`
- **WHEN** public candidates are assembled
- **THEN** the proposal SHALL contain exactly one `cv_direct` candidate

### Requirement: [MPE-R014] Structured uncertainty layers

The proposal engine SHALL return separate crop-resolution boolean masks for candidate disagreement and crop-edge risk. For two or three shown candidates, disagreement SHALL equal the union of shown masks minus their intersection. With zero or one shown candidate, disagreement SHALL be all false. Crop-edge risk SHALL identify shown foreground pixels on the one-pixel work-crop boundary and SHALL remain distinct from disagreement.

#### Scenario: [MPE-R014-S01] Compute disagreement for three candidates

- **GIVEN** three shown crop masks
- **WHEN** uncertainty is computed
- **THEN** `disagreement_mask_roi` SHALL equal `shown_union & ~shown_intersection`

#### Scenario: [MPE-R014-S02] Compute uncertainty for one candidate

- **GIVEN** one shown candidate
- **WHEN** uncertainty is computed
- **THEN** `disagreement_mask_roi` SHALL contain no true pixels
- **AND** crop-edge risk SHALL still be computed independently

### Requirement: [MPE-R015] Previous-state single-mask refinement

Refinement decode SHALL use the original user box, complete human point history, selected candidate previous mask state, and `multimask_count=1`. It SHALL produce at most one new `Candidate`, SHALL add one decoder call per successful request, and SHALL add zero encoder calls.

#### Scenario: [MPE-R015-S01] Successful refinement call counts

- **GIVEN** a current refinable SAM candidate and a valid new human point
- **WHEN** refinement completes successfully
- **THEN** decoder call count SHALL increase by exactly one
- **AND** encoder call count SHALL increase by zero
- **AND** at most one current refined candidate SHALL be produced

#### Scenario: [MPE-R015-S02] Decoder failure during refinement

- **GIVEN** a current SAM candidate and a backend decoder exception or timeout
- **WHEN** refinement fails
- **THEN** the previous selected candidate SHALL remain available
- **AND** the engine SHALL expose a typed failure or recoverable diagnostic
- **AND** SHALL NOT fabricate or partially publish a new candidate

### Requirement: [MPE-R016] Candidate provenance and capabilities

Every candidate SHALL record candidate ID, session revision, source, generator identity, optional parent candidate ID, prompt provenance, provider-local metrics, warnings, and immutable operation capabilities. Model generator identity SHALL include backend name, model version, checkpoint SHA-256, runtime version, and preprocessing version. CV and manual candidates MUST NOT fabricate a model identity.

#### Scenario: [MPE-R016-S01] Model candidate provenance

- **GIVEN** a `sam_box`, `sam_safe_grid`, or `sam_cv` result
- **WHEN** the candidate is created
- **THEN** generator kind SHALL equal `model`
- **AND** complete model identity SHALL be present
- **AND** `can_refine` and `can_local_edit` SHALL both be true

#### Scenario: [MPE-R016-S02] CV-direct provenance

- **GIVEN** a `cv_direct` candidate
- **WHEN** the candidate is created
- **THEN** generator kind SHALL equal `cv_recipe`
- **AND** recipe ID and canonical recipe hash SHALL be present
- **AND** `can_refine` SHALL be false
- **AND** `can_local_edit` and `can_commit` SHALL be true

### Requirement: [MPE-R017] Opt-in 2-of-3 majority fusion

The core SHALL provide a pure `fuse_majority` operation for exactly three same-revision, same-crop, same-shape binary candidates. Foreground SHALL be `vote_count >= 2`, background SHALL be `vote_count == 0`, and fusion uncertainty SHALL be `vote_count == 1`. Fusion SHALL be disabled by default in the GUI and MUST NOT fall back to union, score voting, or a two-mask interpretation.

#### Scenario: [MPE-R017-S01] Fuse three compatible candidates

- **GIVEN** exactly three compatible binary candidates
- **WHEN** opt-in majority fusion is invoked
- **THEN** each output foreground pixel SHALL have at least two foreground votes
- **AND** every one-vote pixel SHALL be marked uncertain rather than foreground

#### Scenario: [MPE-R017-S02] Reject incompatible fusion inputs

- **GIVEN** fewer or more than three candidates, different revisions, different crop contexts, or different shapes
- **WHEN** fusion is invoked
- **THEN** validation SHALL fail
- **AND** no union or partial fusion SHALL be returned

#### Scenario: [MPE-R017-S03] Invalidate fusion on human input

- **GIVEN** an active fusion result
- **WHEN** the first human foreground or background point is accepted
- **THEN** the fusion result SHALL become stale
- **AND** refinement SHALL continue from a selected SAM candidate, not the fused mask

### Requirement: [MPE-R018] Honest zero-candidate failure

If all candidates fail generation, validation, or deduplication, the engine SHALL return a zero-candidate `ProposalSet` with proposal-level warnings, diagnostics, call counts, and timings. It MUST NOT label a bad or empty mask as recommended.

#### Scenario: [MPE-R018-S01] All model outputs are unusable

- **GIVEN** an encode succeeds but every decoded mask is empty, near-full, malformed, duplicate-only, or prompt-violating
- **WHEN** proposal assembly completes
- **THEN** `candidates` SHALL be empty
- **AND** diagnostics SHALL explain each removal reason
- **AND** manual-empty fallback and Needs Review SHALL remain possible
