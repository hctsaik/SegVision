## ADDED Requirements

### Requirement: [PST-R012] Editable drafts shall have a separate pair-consistent publication contract
Persistence SHALL store non-terminal editable drafts in a namespace that AcceptedStore and the training loader never enumerate. A draft publication SHALL use temporary payloads, durable flush, content hashes, and a sidecar-last commit marker. An interrupted or partial draft MUST NOT replace the last valid draft.

#### Scenario: [PST-R012-S01] Crash occurs before draft sidecar publication
- **WHEN** the process stops after writing a temporary draft mask but before publishing its sidecar commit marker
- **THEN** the loader SHALL ignore the partial artifact
- **AND** SHALL expose the prior valid draft if one exists

### Requirement: [PST-R013] Draft sidecars shall preserve complete resumable semantics
A draft sidecar SHALL version and bind source fingerprint, dataset/item identity, class, protocol, revision, ROI/crop geometry, active mask, locked foreground/background regions, prompt IDs/order, operation-history identities, model identity, generator ancestry, and every referenced payload hash. Reload SHALL preserve those semantics exactly or reject the draft.

#### Scenario: [PST-R013-S01] Reload a multi-region draft
- **WHEN** a valid draft contains two locked regions, an active SAM pass, prompt history, and an undone stroke in redo history
- **THEN** reload SHALL restore exact locked hashes, active state, prompts, undo/redo availability, capabilities, and composed-mask hash

### Requirement: [PST-R014] Draft lifecycle shall not mutate immutable outcomes
Flushing, superseding, discarding, or quarantining a draft MUST NOT delete or rewrite Accepted or Needs Review artifacts. Accept MAY mark a matching draft complete or remove it only after the Accepted pair is durably published and verified. Draft cleanup SHALL be scoped by opaque grant, dataset, and item identity.

#### Scenario: [PST-R014-S01] Accept publication fails
- **WHEN** an operator accepts a valid draft but Accepted publication fails before the sidecar commit marker
- **THEN** the valid draft SHALL remain resumable
- **AND** no Accepted pair SHALL be exposed
