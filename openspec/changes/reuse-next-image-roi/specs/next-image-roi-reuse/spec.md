## ADDED Requirements

### Requirement: [NIR-R001] Next-image ROI reuse is opt-in and off by default
The desktop UI SHALL expose a visible opt-in control to reuse the last locked `user_roi_full` on sequential next-image navigation. The control SHALL default to off for a cold UI. Enabling it MUST NOT lock an ROI by itself, MUST NOT Accept, and MUST NOT copy encoded crop state.

#### Scenario: [NIR-R001-S01] Cold launch leaves reuse off
- **WHEN** the desktop UI starts with default configuration
- **THEN** the reuse-last-ROI control SHALL be visible and unchecked
- **AND** Next SHALL create the next session without calling `sessions.lock_roi`

#### Scenario: [NIR-R001-S02] Enabling reuse does not mutate the current session
- **WHEN** the user checks reuse-last-ROI while a session is open
- **THEN** the current snapshot, revision, and candidates SHALL remain unchanged

### Requirement: [NIR-R002] Sequential Next may lock the previous user ROI on a new session
When reuse is enabled and Next/`N` is allowed, the UI SHALL close the current session, create a session for the next dataset item, then submit the captured previous `user_roi_full` through `sessions.lock_roi` on that new session. The new image MUST encode under the new session identity. Candidates, points, previous-mask state, and local edits from the previous session MUST NOT be applied.

#### Scenario: [NIR-R002-S01] Next with reuse on locks the carried rectangle
- **GIVEN** reuse-last-ROI is enabled
- **AND** the current snapshot has a four-integer `user_roi_full` and Next is enabled
- **WHEN** the user activates Next
- **THEN** the UI SHALL call `sessions.close` on the current session, then `sessions.create` for the next item, then `sessions.lock_roi` on the new session with that same rectangle
- **AND** MUST NOT pass the previous `protocol_session_id` into `sessions.lock_roi`

#### Scenario: [NIR-R002-S02] Next with reuse off does not lock
- **GIVEN** reuse-last-ROI is off
- **AND** the current snapshot has `user_roi_full` and Next is enabled
- **WHEN** the user activates Next
- **THEN** the UI SHALL create the next session and MUST NOT call `sessions.lock_roi`

### Requirement: [NIR-R003] Dataset list open does not carry ROI
Opening a dataset item from the item list SHALL create a new session without submitting a carried ROI, even when reuse-last-ROI is enabled.

#### Scenario: [NIR-R003-S01] List click ignores reuse
- **GIVEN** reuse-last-ROI is enabled and the current snapshot has `user_roi_full`
- **WHEN** the user opens another item from the dataset list
- **THEN** the UI SHALL create that item's session and MUST NOT call `sessions.lock_roi` as part of that open

### Requirement: [NIR-R004] Invalid carried ROI fails closed
If the carried rectangle is missing, not four integers, or `sessions.lock_roi` rejects it, the UI SHALL keep the newly created session in `IMAGE_OPEN` without a locked ROI, SHALL expose an operator-visible error, and MUST NOT clip, pad, or otherwise invent a replacement rectangle.

#### Scenario: [NIR-R004-S01] Lock rejection leaves IMAGE_OPEN
- **GIVEN** reuse-last-ROI is enabled and Next is activated with a captured rectangle
- **WHEN** `sessions.lock_roi` fails
- **THEN** the displayed session SHALL be the newly created session
- **AND** `workflow_state` SHALL remain `IMAGE_OPEN` unless a later successful lock occurs
- **AND** the UI SHALL show an operator-visible error
- **AND** MUST NOT call `sessions.lock_roi` a second time with a modified rectangle
