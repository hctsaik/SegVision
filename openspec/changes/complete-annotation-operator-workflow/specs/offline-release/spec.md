## ADDED Requirements

### Requirement: [OFR-R016] Update packages shall be immutable signed release artifacts
Every distributable update package SHALL have an immutable version/build identity, signed component manifest, per-component checksums, dependency/model/license references, compatible protocol and data-schema ranges, rollback metadata, and attributable release authority. Missing or invalid fields, signatures, checksums, or authority MUST fail closed before installation.

#### Scenario: [OFR-R016-S01] Package lacks release authority
- **WHEN** an otherwise valid update package has no attributable approval for a bundled dependency, model artifact, or asset
- **THEN** the updater SHALL reject the package
- **AND** the current verified installation SHALL remain unchanged

### Requirement: [OFR-R017] Installed updates shall preserve offline operation and rollback
The update mechanism SHALL stage components side-by-side, preserve the prior verified installation until post-update smoke passes, and function with outbound networking disabled. Rollback MUST restore executable components without downgrading, deleting, or rewriting user datasets, drafts, Accepted pairs, review records, or LabelMe exports.

#### Scenario: [OFR-R017-S01] Update is applied offline
- **WHEN** a clean supported Windows target selects a valid local update package while outbound networking is blocked
- **THEN** signature verification, installation, sidecar health, draft/Accepted reload, annotation, and save smoke SHALL complete without login or network access

#### Scenario: [OFR-R017-S02] Rollback follows failed save smoke
- **WHEN** the staged version launches but fails the mandatory post-update save/reload smoke
- **THEN** the prior verified version SHALL be restored
- **AND** the release evidence SHALL record the failed stage and retained user artifact hashes
