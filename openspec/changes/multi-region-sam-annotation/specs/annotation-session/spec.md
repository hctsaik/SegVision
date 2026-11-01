## MODIFIED Requirements

### Requirement: [SES-R005] Candidate selection and capability enforcement
The session SHALL expose candidate capabilities for the active pass and SHALL additionally expose `can_lock_region`, `can_next_region`, and `can_unlock_region`. A pixel edit disables refinement only for that active pass; starting a new pass creates a SAM-capable state without modifying locked regions.

#### Scenario: [SES-R005-S01] Select a current candidate
- **GIVEN** a proposal with one to three current-revision candidates
- **WHEN** the caller selects one of those candidate IDs
- **THEN** the session SHALL mark exactly that candidate as current and expose its capabilities

#### Scenario: [SES-R005-S02] New pass restores SAM capability
- **GIVEN** a session with a manual active pass and at least one locked region
- **WHEN** the caller starts the next region
- **THEN** the new active pass SHALL permit SAM refinement after a valid ROI lock
- **AND** locked masks SHALL remain immutable

### Requirement: [SES-R006] Previous-state point refinement
Point refinement SHALL be available for a SAM-generated active candidate. Every refinement SHALL preserve the original box prompt, append active prompt IDs to the ordered history, use the selected candidate's previous mask state, request exactly one output mask, and add zero encoder calls. Deleted prompts SHALL be excluded by deterministic replay from the original SAM state.

#### Scenario: [SES-R006-S01] First human point refinement
- **GIVEN** a selected current SAM candidate and no prior active prompts
- **WHEN** the caller adds one valid point
- **THEN** the decoder SHALL receive the original box, that point, and the previous mask state with `multimask_count=1`
- **AND** encoder call count SHALL remain unchanged

#### Scenario: [SES-R006-S02] Delete an earlier prompt
- **GIVEN** an active prompt history containing three prompts
- **WHEN** the caller deletes the first prompt
- **THEN** the session SHALL replay the remaining two prompts from the original SAM state
- **AND** encoder call count SHALL remain unchanged

### Requirement: [SES-R008] Active-pass local editing and protected regions
Brush, erase, grow, shrink, or fill SHALL create an active manual delta without modifying locked masks. These operations SHALL prevent additional SAM refinement for the current pass until `回到 SAM 結果` or `新增下一區塊` is invoked; a new pass MAY call the model.

#### Scenario: [SES-R008-S01] Local edit clips locked pixels
- **GIVEN** a locked foreground mask and an active candidate
- **WHEN** the caller erases across both masks
- **THEN** only unlocked active pixels SHALL change
- **AND** the locked mask hash SHALL remain unchanged

#### Scenario: [SES-R008-S02] Start next pass after a local edit
- **WHEN** the caller locks the edited component and starts the next region
- **THEN** the active manual state SHALL be archived in provenance
- **AND** the new pass SHALL allow a fresh SAM encode/decode

### Requirement: [SES-R009] Session-owned undo checkpoints
Undo SHALL restore exact active-pass, locked-region, prompt, capability, revision, and model-ready state without invoking the backend. Lock and unlock operations SHALL be checkpoints.

#### Scenario: [SES-R009-S01] Undo a lock
- **WHEN** the caller invokes undo immediately after a lock
- **THEN** the locked region SHALL be removed and the prior active state restored exactly
- **AND** backend call count SHALL remain unchanged

#### Scenario: [SES-R009-S02] Undo with no checkpoint
- **WHEN** the caller invokes undo with no earlier checkpoint
- **THEN** state SHALL remain unchanged and a typed no-op result SHALL be returned
