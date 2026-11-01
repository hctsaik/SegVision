## ADDED Requirements

### Requirement: [LBL-R001] The no-configuration label shall be exactly Defect
When no valid project label metadata is present, the dataset, session fallback, Accepted sidecar fallback, and LabelMe export fallback SHALL use the exact case-sensitive label `Defect`.

#### Scenario: [LBL-R001-S01] Open a folder without a manifest
- **WHEN** an operator opens a supported image folder with no project or dataset class configuration
- **THEN** new annotation sessions and their saved outputs SHALL use class `Defect`

### Requirement: [LBL-R002] Project labels shall be bounded, validated metadata
An optional project manifest SHALL define a bounded list of stable label IDs, display names, keyboard shortcuts, and LabelMe export names. IDs and export names MUST be non-empty and unique. Invalid metadata MUST fail before a mutable session is created.

#### Scenario: [LBL-R002-S01] Project declares multiple labels
- **WHEN** a valid project manifest declares a small label list
- **THEN** the Native App SHALL present only those labels and their documented shortcuts
- **AND** SHALL retain `Defect` only when it is explicitly included or no valid configuration exists

### Requirement: [LBL-R003] Open sessions shall not be silently relabeled
A session SHALL snapshot its label identity at creation or explicit reclassification. Later manifest changes MUST NOT silently alter the open session, draft, Accepted record, or export. Reclassification SHALL be an explicit revisioned operation recording old/new labels, actor, and timestamp.

#### Scenario: [LBL-R003-S01] Manifest changes during an open session
- **WHEN** project label metadata changes after the session was created
- **THEN** the open session SHALL retain its original label until the operator performs an explicit reclassification

### Requirement: [LBL-R004] LabelMe mapping shall be visible and reversible
Export and import SHALL display the active project-to-LabelMe label mapping. Unknown imported labels MUST be rejected or resolved by an explicit recorded mapping decision; they MUST NOT be silently converted to `Defect`.

#### Scenario: [LBL-R004-S01] Import contains an unknown label
- **WHEN** imported LabelMe JSON uses a label absent from the project manifest
- **THEN** import SHALL pause before rasterization and require reject, map, or explicitly extend-project behavior
- **AND** the chosen mapping action SHALL be recorded
