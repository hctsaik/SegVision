## ADDED Requirements

### Requirement: [AOB-R019] Operator workflow E2E shall prove recovery and productivity semantics
Mandatory native E2E SHALL cover completed-checkpoint autosave, incomplete-stroke exclusion, dirty navigation guards, App and sidecar crash recovery, job cancellation/retry/stale rejection, Redo, prompt move/relabel rollback, dataset status/filter/next-unfinished, QA navigation, LabelMe preview/export/import round-trip, project-label mapping, and the independent edit area. Oracles SHALL use session/revision/job IDs, artifact hashes, masks, operation histories, and process state rather than screenshots alone.

#### Scenario: [AOB-R019-S01] Crash and resume a real annotation
- **WHEN** the native E2E annotates the local `014.png` fixture, completes a point and stroke, terminates the sidecar, and restarts it
- **THEN** the last completed checkpoint SHALL be restored with matching source, draft, mask, prompt, locked-region, history, and revision evidence
- **AND** no incomplete action or fabricated Accept SHALL appear

#### Scenario: [AOB-R019-S02] LabelMe batch round-trip
- **WHEN** accepted items are previewed, exported, and imported through Native App grants
- **THEN** every JSON, image identity, label mapping, polygon metric, rasterized mask hash, and allowed difference SHALL be recorded and validated

### Requirement: [AOB-R020] Update acceptance shall be offline, rollback-tested, and artifact-bound
A release claiming update support SHALL run on a supported clean Windows x64 target with outbound network blocked. The suite SHALL verify version identities, signature/checksum rejection, dirty-draft guard, valid local update, post-update health and reload, forced failure rollback, and annotation artifact integrity. Evidence SHALL bind the before/after installers, update package, manifests, signatures, commands, and hashes.

#### Scenario: [AOB-R020-S01] Forced post-update health failure
- **WHEN** a staged update is made to fail the required health smoke on the designated clean target
- **THEN** rollback SHALL restore the prior verified version
- **AND** pre-update drafts, Accepted pairs, and review records SHALL retain verified hashes
