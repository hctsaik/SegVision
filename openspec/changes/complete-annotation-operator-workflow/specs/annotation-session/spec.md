## ADDED Requirements

### Requirement: [SES-R014] Session-owned redo checkpoints
The annotation session SHALL own a redo stack complementary to its undo checkpoints. Undo SHALL move the exact current state into redo history; Redo SHALL restore the exact mask, candidate, active pass, locked regions, ordered prompts, operation ancestry, capabilities, and revision represented by the next redo checkpoint without invoking the backend. Any new mutation after Undo SHALL clear redo history.

#### Scenario: [SES-R014-S01] Redo a brush stroke
- **WHEN** the operator undoes a completed brush stroke and then requests Redo without an intervening mutation
- **THEN** the exact post-stroke mask, history, capability set, and revision SHALL be restored
- **AND** encoder and decoder call counts SHALL remain unchanged

#### Scenario: [SES-R014-S02] New action invalidates redo
- **WHEN** the operator undoes an action and then completes a different mutation
- **THEN** the prior redo branch SHALL be discarded
- **AND** a later Redo request SHALL make no state change

### Requirement: [SES-R015] Existing SAM prompts shall support atomic move and relabel replay
A session with a SAM-generated active candidate SHALL allow an existing prompt ID to be moved to a valid full-image coordinate or relabeled between foreground and background. The session SHALL rebuild from the original active-pass SAM state using the complete remaining ordered prompt history, SHALL make zero encoder calls, and SHALL commit one checkpoint only after successful decode and validation. Failure SHALL atomically preserve the prior prompt and mask state.

#### Scenario: [SES-R015-S01] Move a foreground prompt
- **WHEN** a valid foreground prompt is moved within the active work crop
- **THEN** the decoder SHALL replay the ordered prompt history with the new coordinate and exactly one active decode result
- **AND** the prompt ID and ordering SHALL remain stable

#### Scenario: [SES-R015-S02] Relabel replay fails
- **WHEN** relabeling a prompt produces a backend or constraint failure
- **THEN** the prior prompt label, coordinate, mask, logits state, capabilities, and history SHALL remain exact
- **AND** a recoverable Chinese error SHALL be projected
