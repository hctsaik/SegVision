## ADDED Requirements

### Requirement: [INT-R001] LabelMe export shall have a non-mutating preview phase
Before writing LabelMe JSON, the system SHALL derive cleaned closed polygons from an Accepted mask and present an operator preview. Preview generation MUST NOT modify the Accepted PNG, Accepted sidecar, or source image.

#### Scenario: [INT-R001-S01] Preview a brush-edited mask
- **WHEN** the operator requests LabelMe export for an Accepted brush-edited mask
- **THEN** the preview SHALL report label, component count, polygon count, simplification identity, filled holes, closed gaps, and mask-to-polygon area delta
- **AND** SHALL provide opaque assets for cleaned polygons and changed pixels

### Requirement: [INT-R002] Native LabelMe export shall be deterministic and grant scoped
The Native App SHALL export one item or a verified batch to standard LabelMe polygon JSON through an output-folder grant. Every shape SHALL use `shape_type="polygon"`, closed valid coordinates, a deterministic label, and an imagePath that resolves according to the selected export layout. Accepted data MUST remain unchanged.

#### Scenario: [INT-R002-S01] Export with no project label configuration
- **WHEN** a valid Accepted item is exported without explicit project label metadata
- **THEN** every exported shape label SHALL be exactly `Defect`

#### Scenario: [INT-R002-S02] Export cleanup exceeds threshold
- **WHEN** polygon cleanup changes mask area beyond the frozen allowed threshold
- **THEN** export SHALL block or require an explicit recorded acknowledgement
- **AND** the preview SHALL identify the affected region

### Requirement: [INT-R003] LabelMe import shall create a validated draft and never overwrite Accepted data
The system SHALL validate LabelMe version-independent required fields, imagePath identity, image dimensions, label mapping, polygon bounds, point count, and supported shape types before rasterization. A valid import SHALL create a new editable draft. It MUST NOT overwrite or relabel an Accepted record.

#### Scenario: [INT-R003-S01] Import valid polygons
- **WHEN** the operator imports valid LabelMe polygons that match the granted image
- **THEN** the system SHALL rasterize them deterministically into a new draft
- **AND** SHALL record the imported JSON hash, label mapping, and rasterization identity

#### Scenario: [INT-R003-S02] Import contains an unsupported shape
- **WHEN** LabelMe JSON contains an unsupported shape type or invalid polygon
- **THEN** the import SHALL fail without creating or changing a draft
- **AND** the UI SHALL list each unsupported or invalid shape in Chinese rather than silently ignoring it

### Requirement: [INT-R004] LabelMe round-trip shall be measurable and bounded
Export followed by import using the same image and label configuration SHALL preserve the rasterized mask within a frozen pixel and area tolerance. The system SHALL report any round-trip difference and MUST NOT claim exactness when cleanup intentionally changed pixels.

#### Scenario: [INT-R004-S01] Round-trip a clean polygon mask
- **WHEN** an Accepted mask needs no cleanup and is exported then imported
- **THEN** the imported draft SHALL equal the source mask under the exact-mask oracle

#### Scenario: [INT-R004-S02] Round-trip includes cleanup
- **WHEN** export closes a gap, fills a hole, or simplifies a boundary
- **THEN** the round-trip report SHALL identify the changed pixels and cleanup operations
- **AND** SHALL remain within the configured accepted tolerance
