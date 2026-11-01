## ADDED Requirements

### Requirement: [PM-R001] SAM prompts shall be individually addressable
Every foreground or background prompt SHALL have a stable ID, label, full-image coordinate, insertion order, and active/deleted status. The GUI SHALL render markers and a prompt list in Chinese.

#### Scenario: [PM-R001-S01] Select a prompt marker
- **WHEN** the user clicks a rendered prompt marker
- **THEN** that prompt SHALL become selected and expose `刪除此提示點`

#### Scenario: [PM-R001-S02] Delete a prompt and replay
- **WHEN** the user confirms deletion of any active prompt
- **THEN** the session SHALL rebuild from the original SAM state using remaining prompts in order
- **AND** encoder calls SHALL remain zero
- **AND** the operation SHALL commit only after the decode succeeds

#### Scenario: [PM-R001-S03] Replay failure is atomic
- **WHEN** replay decode fails
- **THEN** the deleted prompt and prior mask SHALL be restored
- **AND** a recoverable Chinese error SHALL be shown
