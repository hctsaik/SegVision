## ADDED Requirements

### Requirement: [MRA-R001] Locked components shall be immutable across passes
The session SHALL lock the 8-connected foreground component containing a user click into a full-image mask with a stable region ID and hash. Later SAM, brush, erase, ROI, and stale-job operations MUST NOT clear or alter locked pixels.

#### Scenario: [MRA-R001-S01] Lock one component
- **WHEN** the user previews and confirms a foreground component
- **THEN** the component SHALL be removed from the active editable layer and stored as a locked region
- **AND** the composed preview SHALL still contain that component

#### Scenario: [MRA-R001-S02] Later pass cannot overwrite a lock
- **WHEN** a later SAM result or erase stroke overlaps a locked region
- **THEN** locked pixels SHALL remain byte-identical
- **AND** the operation SHALL clip or exclude the overlap

### Requirement: [MRA-R002] The workflow shall support a next-region pass
The GUI SHALL provide `新增下一區塊` that starts a new ROI/SAM pass while preserving all locked regions and incrementing the session revision.

#### Scenario: [MRA-R002-S01] Start another disconnected region
- **WHEN** the user confirms a locked component and chooses `新增下一區塊`
- **THEN** the active ROI, prompts, candidate, and embedding SHALL be reset for the new pass
- **AND** the locked-region masks SHALL remain visible and selected in the composed preview

#### Scenario: [MRA-R002-S02] Stale result from an earlier pass
- **WHEN** an old SAM job completes after a new pass starts
- **THEN** the result SHALL be rejected as stale
- **AND** no locked or active mask SHALL change

### Requirement: [MRA-R003] Composed output shall be deterministic
The final preview and accepted full-image mask SHALL equal locked foreground union active foreground minus locked background, with no implicit candidate OR fusion.

#### Scenario: [MRA-R003-S01] Accept multiple regions
- **WHEN** two locked components and one active component are accepted
- **THEN** the committed binary mask SHALL contain their deterministic composition
- **AND** the PNG SHALL use the existing full-image `{0,255}` contract

### Requirement: [MRA-R004] Lock lifecycle shall be reversible and auditable
Lock, unlock, confirm, cancel, and undo SHALL be atomic session operations. Unlocking SHALL create an event and return the region to the active editable layer without rewriting its ancestry.

#### Scenario: [MRA-R004-S01] Undo a lock
- **WHEN** the user invokes Undo immediately after locking a component
- **THEN** the exact prior active mask and unlocked state SHALL be restored without a model call

#### Scenario: [MRA-R004-S02] Unlock a region
- **WHEN** the user selects a locked region and confirms `解除鎖定`
- **THEN** the region SHALL become editable in the active pass
- **AND** its historical lock record SHALL remain in provenance

### Requirement: [MRA-R005] Foreground regions shall be mergeable into the active layer
The GUI SHALL provide `合併區塊` when at least one foreground region is locked. The operation SHALL union the active mask with all locked foreground regions, remove those foreground locks so the union is editable, preserve every locked background region, and create an undo checkpoint. It MUST NOT invoke SAM or increment the session revision.

#### Scenario: [MRA-R005-S01] Merge locked foreground without changing exclusions
- **WHEN** the user chooses `合併區塊` with one or more locked foreground regions and an active candidate
- **THEN** the displayed candidate SHALL be a locally editable union of the active mask and locked foreground masks
- **AND** locked background pixels SHALL remain excluded and immutable
- **AND** no model encode/decode call SHALL occur

#### Scenario: [MRA-R005-S02] Undo a merge
- **WHEN** the user invokes Undo immediately after merging
- **THEN** the prior locked foreground records and active candidate SHALL be restored exactly
