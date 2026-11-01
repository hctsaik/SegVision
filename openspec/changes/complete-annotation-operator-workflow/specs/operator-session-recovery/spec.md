## ADDED Requirements

### Requirement: [REC-R001] Completed mutations shall autosave an isolated editable draft
After every completed authoritative mutation, the system SHALL atomically publish or update a loader-verifiable draft for the current dataset item. Pointer movement and an unfinished pointer stroke MUST NOT be persisted as a completed checkpoint. Draft artifacts MUST remain isolated from Accepted and Needs Review outputs and MUST NOT be enumerated by any training loader.

#### Scenario: [REC-R001-S01] A brush stroke completes
- **WHEN** the operator releases the pointer after a valid brush or erase stroke
- **THEN** exactly one new session checkpoint SHALL become current
- **AND** a draft representing that checkpoint SHALL be atomically published without blocking later canvas input

#### Scenario: [REC-R001-S02] The process stops during a stroke
- **WHEN** the App or sidecar stops after pointer-down but before pointer-up
- **THEN** recovery SHALL restore the last completed checkpoint
- **AND** SHALL NOT claim that the incomplete stroke was saved

### Requirement: [REC-R002] Recovery shall validate identity and integrity before mutation
A draft restore SHALL require a valid schema, content hashes, source-image fingerprint, dataset/item identity, class identity, and compatible protocol version. Invalid or incompatible drafts MUST be quarantined or presented read-only and MUST NOT mutate a new session.

#### Scenario: [REC-R002-S01] Valid draft is found after restart
- **WHEN** the Native App restarts and finds a draft whose schema, hashes, source image, class, and protocol are valid
- **THEN** it SHALL offer `繼續上次標註`, `檢視草稿資訊`, and `捨棄草稿`
- **AND** continuing SHALL restore the exact mask, ROI, locked regions, prompts, history, and revision represented by the checkpoint

#### Scenario: [REC-R002-S02] Source image changed
- **WHEN** a draft fingerprint does not match the currently granted source image
- **THEN** the system SHALL refuse automatic restoration
- **AND** SHALL preserve the draft for explicit inspection or quarantine

### Requirement: [REC-R003] Destructive navigation shall require an explicit dirty-state decision
Image switch, dataset switch, window close, engine restart, and update installation SHALL be blocked while a dirty draft decision is pending. The UI MUST offer semantically explicit save-draft, discard, and cancel choices. Discard MUST target only the current editable draft and MUST NOT remove Accepted or Needs Review records.

#### Scenario: [REC-R003-S01] Operator closes a dirty Native App
- **WHEN** a window close is requested while the current item has unsaved completed mutations
- **THEN** Tauri SHALL prevent close until the operator chooses `先儲存草稿`, `捨棄並關閉`, or `取消`

#### Scenario: [REC-R003-S02] Operator cancels image switch
- **WHEN** the operator requests another image and then chooses `取消`
- **THEN** the original session, image, draft, viewport, and authoritative revision SHALL remain active

### Requirement: [REC-R004] Model work shall be cancellable, retryable, and recoverable
The Native App SHALL expose elapsed time and a job-scoped cancel action while MobileSAM work is pending or running. Cancellation MUST preserve the latest completed authoritative checkpoint. Retry MUST create a new request and job from that checkpoint and MUST NOT install a late result from the cancelled job.

#### Scenario: [REC-R004-S01] Operator cancels MobileSAM
- **WHEN** the operator clicks `取消計算` for a running job
- **THEN** the job SHALL become observably cancelled
- **AND** the previously completed mask and draft SHALL remain available

#### Scenario: [REC-R004-S02] Operator retries the same ROI
- **WHEN** a cancelled or failed job is retried
- **THEN** a new job identity SHALL be created against the current authoritative revision
- **AND** any later result from the old job SHALL be discarded as stale

### Requirement: [REC-R005] Sidecar recovery and diagnostics shall be host supervised and redacted
On sidecar exit, the host SHALL freeze mutations, mark painted pixels non-authoritative, and require a new random port and launch secret before recovery. Only a loader-verified draft or published pair may restore authoritative state. Diagnostic export MUST use an allowlist and MUST NOT contain launch secrets, raw filesystem paths, source images, masks, or automatic network upload.

#### Scenario: [REC-R005-S01] Sidecar crashes with a valid draft
- **WHEN** the host detects sidecar exit and successfully starts a new healthy sidecar
- **THEN** the new sidecar SHALL validate and restore the last completed draft before enabling mutations
- **AND** React canvas pixels SHALL NOT be used as recovery input

#### Scenario: [REC-R005-S02] Operator exports diagnostics
- **WHEN** the operator chooses `匯出診斷資料`
- **THEN** the output SHALL include only allowlisted versions, checksums, job states, stable error details, and timings
- **AND** SHALL contain no secret, raw path, or image content
