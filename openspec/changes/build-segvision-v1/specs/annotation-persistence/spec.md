## ADDED Requirements

### Requirement: [PST-R001] Core commit shall remain in-memory and persistence shall be adapter-owned
The core annotation session SHALL accept and return in-memory values only. A successful explicit Accept SHALL allow core commit to return a `CommitResult` containing the full-image mask and JSON-serializable sidecar data, while a storage adapter SHALL own all path selection, file creation, publication, reload, cleanup, and retry behavior. Core code MUST NOT open a path, download a model, or mutate caller-owned image or mask buffers.

#### Scenario: [PST-R001-S01] Headless commit
- **WHEN** a valid crop candidate is committed without a storage adapter
- **THEN** core SHALL return a full-image mask and sidecar value without creating or modifying any filesystem entry

#### Scenario: [PST-R001-S02] Adapter saves a commit result
- **WHEN** a caller passes a valid `CommitResult` and destination policy to the persistence adapter
- **THEN** only the adapter SHALL perform filesystem operations and the committed in-memory values SHALL remain unchanged

### Requirement: [PST-R002] Accepted masks shall use a deterministic full-image PNG contract
An accepted mask SHALL be persisted as a single-channel 8-bit PNG with the exact original image height and width, background encoded as `0`, foreground encoded as `255`, and no foreground outside `crop_rect_full`. The adapter MUST reject masks with a different shape, unsupported value, stale revision, or non-binary content before publishing an accepted pair.

#### Scenario: [PST-R002-S01] Valid full-image mask is encoded
- **WHEN** a committed boolean full-image mask passes post-commit validation
- **THEN** the adapter SHALL encode a PNG of identical height and width whose unique pixel values are a subset of `{0, 255}`

#### Scenario: [PST-R002-S02] Crop content is placed in full coordinates
- **WHEN** a crop-resolution mask is committed for a crop that does not cover the full source image
- **THEN** the persisted full-image PNG SHALL contain the crop mask at the exact crop offset and SHALL contain only background outside the crop

#### Scenario: [PST-R002-S03] Invalid mask is rejected before publication
- **WHEN** a committed result has the wrong shape, non-binary pixels, foreground outside the crop, or a stale candidate revision
- **THEN** the adapter SHALL reject publication with a machine-readable validation error and SHALL NOT publish an accepted sidecar

### Requirement: [PST-R003] Accepted sidecars shall carry versioned integrity and provenance
Every accepted annotation SHALL have a versioned JSON sidecar with `status="accepted"`, `training_eligible=true`, `acceptance_actor` equal to `interactive_user` or `scripted_test`, source image identity and shape, mask filename and SHA-256, `user_roi_full`, `crop_rect_full`, padding, class, selected candidate, generator identity, parent provenance, model or recipe identity as applicable, prompts, manual operations, warnings and acknowledgements, revision, timing events, and recorded hardware/runtime identity. Required fields MUST be validated against the committed result before publication. A `scripted_test` record MAY prove isolated Tier A/B mechanics but MUST NOT be counted as Tier C human evidence.

#### Scenario: [PST-R003-S01] Model-generated annotation sidecar
- **WHEN** an accepted annotation descends from a SAM candidate
- **THEN** the sidecar SHALL identify the model backend, model version, checkpoint hash, candidate source and parent chain, prompts, and any later manual operations

#### Scenario: [PST-R003-S02] Direct-CV annotation sidecar
- **WHEN** an accepted annotation descends from `cv_direct`
- **THEN** the sidecar SHALL use a `cv_recipe` generator identity and SHALL record the recipe ID and recipe hash without fabricating a model identity

#### Scenario: [PST-R003-S03] Fully manual annotation sidecar
- **WHEN** an accepted mask was drawn from `manual_empty`
- **THEN** the sidecar SHALL use a manual generator identity and SHALL preserve the sequence of local operations without fabricating model or recipe provenance

#### Scenario: [PST-R003-S04] Sidecar does not match the commit result
- **WHEN** sidecar shape, mask filename, hash, revision, status, or selected candidate is inconsistent with the committed result
- **THEN** validation SHALL fail and no accepted sidecar SHALL be published

### Requirement: [PST-R004] Accepted PNG and sidecar shall use a pair-consistent publication protocol
The persistence adapter MUST write the PNG and sidecar to unique temporary names in the destination filesystem, flush and close both files, and validate their schema, dimensions, and hashes. Every published PNG SHALL use a new versioned or content-addressed final filename and MUST NOT replace the PNG referenced by an existing accepted sidecar. The adapter SHALL publish that new PNG first and atomically replace only the destination sidecar pointer last as the reader-visible commit marker. The implementation MUST NOT claim that the two publications are one filesystem transaction; consistency SHALL be established by loader validation of the final sidecar and referenced mask. An unused new PNG from a failed sidecar publication MAY be removed or quarantined only after the previous sidecar/PNG pair has been revalidated.

#### Scenario: [PST-R004-S01] Successful new annotation publication
- **WHEN** both temporary files are valid and all publication operations succeed
- **THEN** the final PNG SHALL be published before the final sidecar and a loader SHALL observe exactly one valid accepted pair

#### Scenario: [PST-R004-S02] Existing annotation is replaced
- **WHEN** a valid newer accepted pair replaces a pair for the same destination key
- **THEN** the new PNG SHALL use a different versioned or content-addressed filename and the final sidecar SHALL identify its new filename and hash
- **AND** the supersession metadata SHALL preserve the prior record identity

#### Scenario: [PST-R004-S04] Replacement sidecar publication fails
- **WHEN** a new versioned PNG is published but atomic replacement of an existing valid sidecar fails
- **THEN** the prior sidecar and its prior PNG SHALL remain a loader-valid current pair
- **AND** retry SHALL either publish the new sidecar pointer or safely quarantine the unused new PNG without changing the prior pair

#### Scenario: [PST-R004-S03] Sidecar publication is the commit marker
- **WHEN** a new versioned PNG exists but its new final sidecar has not been published
- **THEN** a loader SHALL NOT infer acceptance from the PNG alone

### Requirement: [PST-R005] Publication failure shall preserve retryability and reject partial pairs
Failure during temporary writing, flushing, validation, PNG publication, or sidecar publication SHALL leave the live session and validated `CommitResult` available for retry, SHALL keep next-image navigation disabled, and SHALL ensure the accepted loader rejects any partial or mismatched pair. Temporary and orphan artifacts MUST be removed or moved to a non-training quarantine without overwriting the user's in-memory annotation.

#### Scenario: [PST-R005-S01] Temporary PNG write fails
- **WHEN** the adapter fails while writing the temporary PNG
- **THEN** no final sidecar SHALL be published, the session SHALL remain retryable, and training enumeration SHALL find no new accepted annotation

#### Scenario: [PST-R005-S02] Temporary sidecar write or validation fails
- **WHEN** the sidecar cannot be written, parsed, or validated
- **THEN** the final sidecar SHALL remain unpublished and any temporary artifacts SHALL be cleaned or quarantined

#### Scenario: [PST-R005-S03] PNG publication succeeds but sidecar publication fails
- **WHEN** a new versioned PNG is published and atomic replacement of the sidecar pointer then fails
- **THEN** a previously accepted sidecar/PNG pair SHALL remain valid when present, the new PNG SHALL not be treated as accepted, the session SHALL retain the result, and retry SHALL be possible without model inference

#### Scenario: [PST-R005-S04] Retry succeeds
- **WHEN** the storage fault is removed and publication is retried for the retained result
- **THEN** the adapter SHALL publish one matching accepted pair and the workflow MAY transition to `ACCEPTED`

### Requirement: [PST-R006] The accepted loader shall validate every pair before exposing training data
The accepted-annotation loader SHALL enumerate an annotation only when a supported sidecar exists, has `status="accepted"` and `training_eligible=true`, references an existing PNG, and the PNG filename, SHA-256, dimensions, binary value contract, source shape, and schema agree. The loader MUST reject and report orphan, corrupt, unsupported, review-only, or mismatched artifacts.

#### Scenario: [PST-R006-S01] Complete pair reloads
- **WHEN** a valid accepted PNG and matching supported sidecar are loaded
- **THEN** the loader SHALL return the exact full-image boolean mask and provenance represented by the pair

#### Scenario: [PST-R006-S02] Orphan PNG is ignored
- **WHEN** a PNG exists without an accepted sidecar commit marker
- **THEN** the accepted loader SHALL exclude it from training enumeration and SHALL report or quarantine it as an orphan

#### Scenario: [PST-R006-S03] Referenced PNG is missing
- **WHEN** an accepted-looking sidecar references a mask file that does not exist
- **THEN** the loader SHALL reject the annotation with a missing-mask integrity error

#### Scenario: [PST-R006-S04] Mask hash is incorrect
- **WHEN** the persisted PNG bytes do not match `mask_sha256`
- **THEN** the loader SHALL reject the pair and MUST NOT expose its mask to the training caller

#### Scenario: [PST-R006-S05] Schema version is unsupported
- **WHEN** the sidecar schema major version is not supported
- **THEN** the loader SHALL reject it with a typed schema error rather than guessing field semantics

### Requirement: [PST-R007] Needs Review persistence shall be isolated from accepted training data
A Needs Review outcome SHALL persist review metadata with `status="needs_review"`, `training_eligible=false`, current `user_roi_full`, current `crop_rect_full`, revision, reason, timing diagnostics, and actor provenance. An optional draft mask MUST be stored only in a review namespace that the accepted training loader never enumerates. Marking Needs Review MUST NOT require a non-empty mask and MUST NOT publish an accepted PNG/sidecar pair. The review writer SHALL use a unique temporary file and atomically publish the review sidecar as its commit marker; failure SHALL retain a retryable `ReviewResult` and MUST NOT produce terminal `NEEDS_REVIEW`.

#### Scenario: [PST-R007-S01] Review without a draft
- **WHEN** a user selects Needs Review before any usable mask exists
- **THEN** the adapter SHALL persist review metadata and the accepted loader SHALL return no training annotation for that image outcome

#### Scenario: [PST-R007-S02] Review with a draft
- **WHEN** a user selects Needs Review after partial refinement or local editing and chooses to retain a draft
- **THEN** the draft and review sidecar SHALL be stored in the review namespace with `training_eligible=false`

#### Scenario: [PST-R007-S03] Review publication fails
- **WHEN** the temporary review sidecar write, validation, or atomic publication fails
- **THEN** no durable Needs Review outcome SHALL be reported, next-image navigation SHALL remain disabled, and the exact review result SHALL remain available for persistence-only retry

#### Scenario: [PST-R007-S04] Training loader scans review storage
- **WHEN** accepted and review artifacts are present under their configured roots
- **THEN** the accepted loader SHALL enumerate only complete accepted pairs and SHALL exclude every Needs Review artifact

### Requirement: [PST-R008] Persistence shall retain manual ancestry without rewriting generator history
When local edits derive from a model or CV candidate, persistence SHALL record a manual-edit node with `parent_candidate_id` and operation history while preserving the original generator identity and prompts in the ancestry. It MUST NOT relabel a manually modified mask as untouched model output or discard the evidence needed to replay the edit sequence.

#### Scenario: [PST-R008-S01] Model candidate is brushed before Accept
- **WHEN** a user applies brush or erase to a SAM-generated candidate and accepts the result
- **THEN** the sidecar SHALL identify manual edit as the current source, retain the SAM candidate as parent, and record the ordered operations

#### Scenario: [PST-R008-S02] CV-direct candidate is locally corrected
- **WHEN** a user locally edits a `cv_direct` candidate before Accept
- **THEN** the sidecar SHALL retain the CV recipe generator as parent provenance and SHALL record manual operations separately

### Requirement: [PST-R009] Reload shall preserve mask and metadata semantics
Reloading an accepted pair SHALL reconstruct a boolean full-image mask equal to the committed mask and SHALL preserve the source image ID, class, ROI and crop rectangles, selected source, revision, generator ancestry, recipe/model hashes, prompts, manual operations, warnings, and timing metadata without coordinate reinterpretation.

#### Scenario: [PST-R009-S01] Save and reload round trip
- **WHEN** an accepted annotation is saved and immediately reloaded
- **THEN** the reloaded boolean mask SHALL be pixel-identical to `CommitResult.full_image_mask` and all required sidecar fields SHALL compare equal after canonical JSON parsing

#### Scenario: [PST-R009-S02] Coordinates remain full-image based
- **WHEN** a sidecar produced from a padded crop is reloaded
- **THEN** its public ROI, crop, and point coordinates SHALL remain in the recorded full-image coordinate system

### Requirement: [PST-R010] Accepted and review outcomes shall be immutable release records
After publication, an accepted or Needs Review record MUST NOT be silently mutated in place without producing a new complete sidecar revision and preserving or invalidating the older record according to the destination policy. Tests and retries MUST NOT overwrite unrelated accepted annotation data.

#### Scenario: [PST-R010-S01] Retry targets the same pending outcome
- **WHEN** a failed save is retried before the session is finalized
- **THEN** retry SHALL operate on the retained pending result and SHALL NOT modify any unrelated image annotation

#### Scenario: [PST-R010-S02] A later annotation supersedes an earlier one
- **WHEN** a new explicit annotation outcome is published for an image that already has an accepted record
- **THEN** the adapter SHALL follow a deterministic version or replacement policy and SHALL leave enough metadata to identify which complete revision is current

### Requirement: [PST-R011] Persistence tests shall exercise crash and corruption boundaries
The persistence capability MUST provide deterministic fault-injection coverage for every publication stage and MUST prove that the accepted loader never treats a half-written, orphaned, hash-mismatched, wrong-shape, or review-only artifact as training data.

#### Scenario: [PST-R011-S01] Failure matrix is executed
- **WHEN** the persistence E2E suite runs
- **THEN** it SHALL inject failures at temporary PNG write/flush/close, temporary sidecar write/flush/close, validation, new versioned PNG publication, and atomic sidecar-pointer replacement and SHALL assert retryability, prior-pair preservation, and loader exclusion for every case

#### Scenario: [PST-R011-S02] Corruption matrix is executed
- **WHEN** the reload E2E suite runs
- **THEN** it SHALL test missing files, altered PNG bytes, incorrect hashes, unsupported schema, wrong shape, non-binary pixels, and review-only records with machine-verifiable rejection oracles
