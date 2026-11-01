## ADDED Requirements

### Requirement: [QAC-R001] Pre-save mask checks shall be deterministic and local
The system SHALL analyze the composed full-image binary mask and LabelMe preview using repository-owned deterministic thresholds. Checks SHALL include empty mask, near-full mask, source-image boundary contact, work-crop boundary contact, tiny isolated components, enclosed holes, one-pixel bridges, component-count policy, and mask-to-polygon area delta. QA MUST NOT invoke a model or modify pixels.

#### Scenario: [QAC-R001-S01] Mask contains an isolated tiny component
- **WHEN** the component area falls below the active repository-owned threshold
- **THEN** QA SHALL emit one stable issue containing code, severity, bbox, measured area, threshold identity, and Chinese message

### Requirement: [QAC-R002] QA issues shall be deduplicated and navigable
Repeated equivalent issues SHALL be deduplicated for display while retaining measured provenance. Selecting an issue SHALL frame its full-image bbox without changing the mask, ROI, or revision.

#### Scenario: [QAC-R002-S01] Operator selects a hole issue
- **WHEN** the operator clicks the hole issue in the inspector
- **THEN** the viewer SHALL zoom or pan to the issue bbox
- **AND** the current annotation state SHALL remain unchanged

### Requirement: [QAC-R003] Blocking failures and acknowledgements shall be explicit
Invalid empty output and other frozen safety-critical issues MUST block Accept. Advisory issues MAY allow Accept only after explicit acknowledgement. The Accepted sidecar SHALL record acknowledged issue code, measured values, threshold identity, actor, and revision. Needs Review SHALL remain available where permitted.

#### Scenario: [QAC-R003-S01] Advisory boundary issue is acknowledged
- **WHEN** an operator reviews and acknowledges an advisory boundary-contact issue
- **THEN** Accept MAY proceed if every blocking validation passes
- **AND** the acknowledgement details SHALL be persisted in provenance

#### Scenario: [QAC-R003-S02] Empty mask remains blocking
- **WHEN** the composed mask is empty
- **THEN** Accept SHALL remain disabled regardless of acknowledgement
- **AND** the operator SHALL be offered local repair or Needs Review where workflow state permits
