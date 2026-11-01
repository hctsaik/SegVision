## ADDED Requirements

### Requirement: [DRP-R001] Reference transfer shall not copy ROI coordinates
A later reference-mask prototype SHALL search the new image by appearance in patch-feature space. It MUST NOT treat the previous `user_roi_full` as the next image’s search box.

#### Scenario: [DRP-R001-S01] Moved defect is still eligible
- **GIVEN** a teacher Accept mask whose foreground lies in one region of image A
- **AND** image B shows a similar-looking foreground in a different region
- **WHEN** prototype matching runs
- **THEN** a match MAY be proposed at B’s location
- **AND** MUST NOT be constrained to A’s previous box coordinates

### Requirement: [DRP-R002] DINO is default-off and off the v1 hot path
DINOv2 matching SHALL NOT run during ordinary v1 annotation unless a later change enables an explicit, default-off capability. Frozen v1 GUI inventory MUST continue to omit DINO controls.

#### Scenario: [DRP-R002-S01] Cold v1 GUI has no DINO control
- **WHEN** the v1 annotation GUI starts with default configuration
- **THEN** it SHALL NOT expose a DINO or prototype-fit control as part of the frozen v1 inventory

### Requirement: [DRP-R003] Prototype may only propose and must be able to abstain
Matching SHALL emit zero or one coarse prompt into the existing SAM path. It MUST NOT auto-Accept, MUST NOT write a public heatmap as a candidate mask, and MUST NOT clone filler candidates.

#### Scenario: [DRP-R003-S01] Low-margin match returns no prototype candidate
- **WHEN** FG/BG margin is below the frozen spike policy or more than one large component survives
- **THEN** the prototype path SHALL return zero prototype candidates and leave the ordinary SAM/manual path available

### Requirement: [DRP-R004] Teacher must be an accepted mask
A prototype SHALL be fit only from a human-accepted mask in product form. Observational spikes MAY use gold as a stand-in and MUST label `claim_scope.quality_gate=false`.

#### Scenario: [DRP-R004-S01] Unconfirmed SAM card cannot be a teacher
- **WHEN** only an unaccepted candidate mask is available
- **THEN** fitting SHALL refuse to produce a reusable prototype artifact

### Requirement: [DRP-R005] Desktop DINO prototype is opt-in and does not copy ROI
When enabled, Accept SHALL fit prototypes from the accepted full-image mask, and opening a new item SHALL appearance-match then lock a proposed ROI. It MUST NOT copy the previous `user_roi_full`. When disabled, v1 create/accept behaviour is unchanged.

#### Scenario: [DRP-R005-S01] Cold desktop leaves DINO prototype off
- **WHEN** the desktop UI starts
- **THEN** the DINO prototype control SHALL be visible and unchecked
- **AND** Next SHALL NOT send `prototype_match`

#### Scenario: [DRP-R005-S02] Enabled Next matches by appearance
- **GIVEN** DINO prototype is enabled and a teacher was fitted on Accept
- **WHEN** the user opens the next item
- **THEN** the UI SHALL create the session with `prototype_match=true`
- **AND** MUST NOT submit the previous rectangle as `sessions.lock_roi` coordinates
- **AND** a successful match SHALL lock a DINO-proposed ROI and show an operator note
