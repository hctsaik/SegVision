## MODIFIED Requirements

### Requirement: [PST-R003] Accepted sidecars shall carry versioned integrity and provenance
Every accepted annotation SHALL carry sidecar version `2` (or a backward-compatible v1 record) with the existing integrity fields plus `locked_regions`, `active_pass`, stable prompt IDs, operation ancestry, composed-mask hash, and lock/unlock events. Required fields MUST validate against the committed full-image mask.

#### Scenario: [PST-R003-S01] Multi-region accepted annotation
- **WHEN** an annotation with locked and active regions is accepted
- **THEN** the sidecar SHALL record every region mask hash, parent candidate, prompt history, operation, and final composed hash

#### Scenario: [PST-R003-S02] Sidecar mismatch
- **WHEN** a locked-region hash or composed mask hash differs from the committed result
- **THEN** publication SHALL fail and no accepted sidecar SHALL be published

### Requirement: [PST-R008] Persistence shall retain manual and multi-region ancestry without rewriting generator history
Persistence SHALL record each pass, lock/unlock event, prompt deletion/replay, and manual operation while preserving the original generator identity and parent candidate for every region.

#### Scenario: [PST-R008-S01] Reload multi-region ancestry
- **WHEN** a composed annotation is saved
- **THEN** the sidecar SHALL preserve pass order, locked-region IDs, prompt IDs, and manual ancestry without relabeling model output

### Requirement: [PST-R009] Reload shall preserve mask and metadata semantics
Reloading an accepted pair SHALL reconstruct the exact committed full-image mask and all locked-region, active-pass, prompt, operation, ROI, revision, and provenance metadata in the recorded full-image coordinate system.

#### Scenario: [PST-R009-S01] Save and reload multi-region mask
- **WHEN** an accepted multi-region pair is reloaded
- **THEN** its boolean mask and composed hash SHALL equal the committed result pixel-for-pixel

#### Scenario: [PST-R009-S02] Coordinates remain full-image based
- **WHEN** a locked region originated in a padded crop
- **THEN** its stored component and prompt coordinates SHALL remain full-image coordinates after reload
