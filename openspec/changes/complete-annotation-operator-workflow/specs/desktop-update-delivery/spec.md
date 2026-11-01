## ADDED Requirements

### Requirement: [UPD-R001] The Native App shall expose verifiable component versions
The version view SHALL display the App version, build identity, desktop protocol version, Python sidecar version, model identity and checkpoint checksum, and installer/update channel. Secrets, raw paths, and unverified human-readable labels MUST NOT replace these identities.

#### Scenario: [UPD-R001-S01] Operator opens version information
- **WHEN** the operator opens the About or version view
- **THEN** the displayed identities SHALL match the running host, sidecar health response, and approved model manifest

### Requirement: [UPD-R002] Manual offline updates shall be signed and checksum verified
The first supported update workflow SHALL use an operator-selected local update package. The host MUST verify package signature, component manifest, every required checksum, compatibility, license/release authority, and rollback metadata before modifying the installation. Failure of any verification SHALL leave the running installation unchanged.

#### Scenario: [UPD-R002-S01] Update checksum is invalid
- **WHEN** any staged component checksum differs from the signed manifest
- **THEN** installation SHALL stop before switch-over
- **AND** the current verified App SHALL remain launchable

### Requirement: [UPD-R003] Update shall resolve dirty work and support rollback
Before update switch-over, the App SHALL resolve dirty drafts through the explicit guard, flush verified drafts, close sessions, and stop the sidecar. The prior verified version SHALL remain available until the new version passes launch, health, protocol, draft-load, Accepted-load, and save smoke. Failed smoke SHALL roll back without rewriting user annotation artifacts.

#### Scenario: [UPD-R003-S01] Update requested with dirty work
- **WHEN** the operator starts an update while the current session is dirty
- **THEN** installation SHALL wait for save-draft, discard, or cancel
- **AND** choosing cancel SHALL leave the App and session unchanged

#### Scenario: [UPD-R003-S02] New sidecar fails health
- **WHEN** the staged version cannot complete the required sidecar health handshake
- **THEN** the updater SHALL restore the prior verified version
- **AND** preserved drafts and Accepted data SHALL remain loader-verifiable

### Requirement: [UPD-R004] Runtime networking and telemetry shall remain disabled by default
Automatic network update, telemetry, analytics, crash upload, and remote inference SHALL be disabled in the shipped configuration. All required annotation, recovery, LabelMe, and manual-update paths MUST operate with outbound networking blocked and without login.

#### Scenario: [UPD-R004-S01] Clean machine has no network
- **WHEN** outbound networking is disabled on a supported clean Windows machine
- **THEN** the App SHALL launch, annotate, autosave, recover, export/import LabelMe, apply a valid local update, and reload results without a network request
