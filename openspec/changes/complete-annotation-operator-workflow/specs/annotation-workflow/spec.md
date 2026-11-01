## ADDED Requirements

### Requirement: [UIW-R020] The Native App shall expose work-safety and engine-recovery controls
The UI SHALL display draft state, dirty state, autosave progress, recovery state, running-job elapsed time, cancel, retry, engine restart, and diagnostic export where applicable. Controls MUST project authoritative host/sidecar state and MUST NOT infer saved or recovered status from React liveness.

#### Scenario: [UIW-R020-S01] MobileSAM appears stalled
- **WHEN** a model job remains running beyond the normal immediate-feedback interval
- **THEN** the compute banner SHALL continue showing elapsed time and expose `取消計算`
- **AND** the rest of the non-mutating UI SHALL remain responsive

#### Scenario: [UIW-R020-S02] Engine is recovering
- **WHEN** the host reports sidecar restart or recovery
- **THEN** mutation controls SHALL be disabled with a Chinese explanation
- **AND** the App SHALL distinguish non-authoritative painted pixels from restored authoritative state

### Requirement: [UIW-R021] The GUI shall expose Redo and operation history
The Native App SHALL expose Undo, Redo, and a readable ordered operation-history panel. Each item SHALL identify operation kind, affected region or prompt, revision, and whether it is current, undone, or unavailable. The UI MUST call session operations rather than restoring a React-owned mask.

#### Scenario: [UIW-R021-S01] Operator inspects recent edits
- **WHEN** the operation-history panel is opened after SAM points, a stroke, and a region lock
- **THEN** those operations SHALL appear in authoritative order with stable identities
- **AND** the current checkpoint SHALL be visibly identified

### Requirement: [UIW-R022] Existing prompt markers shall be adjustable from the canvas and inspector
Selecting a prompt marker SHALL expose move, foreground/background relabel, and delete actions. Canvas dragging or point replacement MUST use full-image integer coordinates, preserve prompt identity, and show progress while deterministic replay runs.

#### Scenario: [UIW-R022-S01] Operator changes an exclusion to inclusion
- **WHEN** the operator selects a background prompt and chooses foreground
- **THEN** the UI SHALL keep the same prompt selected while the sidecar replays the prompt set
- **AND** it SHALL display either the committed new result or the exact prior result with a recoverable error

### Requirement: [UIW-R023] The independent edit area shall be native-tested and model-independent
The `編輯範圍` tool SHALL use first-corner/opposite-corner clicks, replace the nearest corner on later clicks, and clip the complete brush or erase radius to a half-open full-image `XYXY` rectangle. It MUST remain available independently of SAM candidate selection where manual-empty editing is permitted and MUST NOT invoke `sessions.lock_roi`, propose, encode, or decode.

#### Scenario: [UIW-R023-S01] Radius touches the edit-area boundary
- **WHEN** a 5 px brush or erase stroke is centered near the edit-area boundary
- **THEN** every changed pixel SHALL remain inside the half-open edit rectangle
- **AND** no model or ROI-lock operation SHALL be observed

#### Scenario: [UIW-R023-S02] Operator adjusts a completed corner
- **WHEN** the operator clicks closer to corner 1 than corner 2 after completing the edit area
- **THEN** corner 1 SHALL move to the new full-image point and corner 2 SHALL remain exact
- **AND** the behavior SHALL be invariant under supported zoom, pan, and DPR values
