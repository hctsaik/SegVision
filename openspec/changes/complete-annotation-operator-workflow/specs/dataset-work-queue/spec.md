## ADDED Requirements

### Requirement: [QUE-R001] Every dataset item shall have a verified workflow status
The sidecar SHALL derive item status from loader-verified Accepted, Needs Review, Draft, and failure artifacts. Supported statuses SHALL include unstarted, draft, accepted, needs-review, save-failed, and conflict-or-corrupt. Status MUST NOT be inferred solely from React memory or filename presence.

#### Scenario: [QUE-R001-S01] Draft and accepted artifacts both exist
- **WHEN** an item has a valid immutable Accepted pair and a newer valid editable draft
- **THEN** the work queue SHALL report that Accepted exists and that resumable changes are pending
- **AND** SHALL NOT silently collapse the item to only accepted or only draft

#### Scenario: [QUE-R001-S02] Sidecar hash is invalid
- **WHEN** an item's artifact fails schema, pair, source, or content-hash validation
- **THEN** the item SHALL be marked conflict-or-corrupt
- **AND** SHALL not be opened as a normal mutable session without an explicit recovery path

### Requirement: [QUE-R002] The Native App shall expose filters, search, and progress
The dataset rail SHALL display item status and provide status filters, filename search, total count, completed count, draft count, Needs Review count, and unresolved failure count. Filtering MUST preserve a deterministic stable item order.

#### Scenario: [QUE-R002-S01] Operator filters to drafts
- **WHEN** the operator selects the draft filter
- **THEN** the rail SHALL show only items with a valid resumable draft or accepted-plus-newer-draft state
- **AND** progress counts SHALL continue to describe the complete dataset

### Requirement: [QUE-R003] Next navigation shall prioritize unfinished work and preserve safety
`下一張未完成` SHALL navigate to the next item in the current stable filtered order that is not durably complete. It MUST run the dirty-state guard before closing the current session. Accepted and Needs Review items SHALL be reopenable in read-only mode, while valid drafts SHALL offer resume.

#### Scenario: [QUE-R003-S01] Current item is accepted
- **WHEN** the operator invokes `下一張未完成`
- **THEN** the App SHALL skip later Accepted items and open the next eligible unfinished item

#### Scenario: [QUE-R003-S02] Current item has dirty work
- **WHEN** the operator invokes next-unfinished while the current draft has unflushed completed mutations
- **THEN** navigation SHALL wait for an explicit save, discard, or cancel decision
