## ADDED Requirements

### Requirement: [AOB-R001] Annotation sessions shall emit ordered structured events
Every annotation session SHALL emit ordered machine-readable events for `image_visible`, `roi_drag_started`, `first_roi_locked`, `roi_relocked`, `proposal_started`, `encode_started`, `encode_finished`, `first_candidate_ready`, `all_candidates_ready`, `candidate_selected`, `refine_started`, `refine_finished`, `first_local_edit`, `job_cancel_requested`, `job_cancelled`, `stale_result_rejected`, `required_operation_timeout`, `accept_attempted`, `accept_validation_passed`, `accept_validation_failed`, `needs_review_requested`, `review_save_started`, `review_save_finished`, `review_save_failed`, `commit_started`, `commit_finished`, `save_started`, `save_finished`, `save_failed`, and `next_image`. Events MUST contain session ID, revision, monotonic timestamp, event sequence number, and relevant candidate/job IDs without exposing opaque model tensors. A timeout event MUST identify the timed operation and timeout budget in `details`; it is diagnostic and MUST NOT itself create a final disposition.

#### Scenario: [AOB-R001-S01] Happy-path event sequence
- **WHEN** a user completes a normal ROI-to-Accept annotation
- **THEN** the event stream SHALL contain a strictly ordered sequence sufficient to reconstruct proposal, selection, optional edits, validation, commit, save, and navigation

#### Scenario: [AOB-R001-S02] Revision changes during an active job
- **WHEN** the ROI changes while proposal or refinement is pending
- **THEN** the event stream SHALL identify the old and new revisions and SHALL record cancellation or stale-result rejection for the old job

#### Scenario: [AOB-R001-S03] Failed Accept is observable
- **WHEN** Accept validation fails
- **THEN** the stream SHALL record `accept_attempted` and its validation reason and SHALL NOT record `accept_validation_passed`

### Requirement: [AOB-R002] Time metrics shall use monotonic and non-resettable definitions
The system SHALL calculate `first_valid_accept_time_ms` and `annotation_time` as the first `accept_validation_passed - first_roi_locked` whenever validation has ever passed, SHALL calculate `decision_time` as the earliest of the first valid Accept validation or explicit Needs Review request minus `first_roi_locked`, and SHALL calculate `within_30_accept` as a final durable accepted disposition with `annotation_time < 30000 ms`. If accepted publication later fails and the user durably chooses Needs Review, the outcome remains non-accepted and `within_30_accept=false`, but the prior validation timing SHALL remain as diagnostic evidence. ROI redraw, Expand ROI, candidate selection, refinement, local editing, invalid Accept attempts, save retry, and review-save retry MUST NOT reset or shorten these durations.

#### Scenario: [AOB-R002-S01] Strict 30-second boundary
- **WHEN** valid Accept occurs at 29,999 ms, 30,000 ms, and 30,001 ms in controlled-clock runs
- **THEN** only the 29,999 ms run SHALL have `within_30_accept=true`

#### Scenario: [AOB-R002-S02] Invalid early Accept does not game time
- **WHEN** an invalid Accept is attempted at 20 seconds and a valid Accept passes at 31 seconds
- **THEN** annotation time SHALL be 31 seconds and the outcome SHALL be recorded as a time-SLO failure

#### Scenario: [AOB-R002-S03] ROI redraw preserves timer origin
- **WHEN** the ROI is redrawn after the first valid lock and the annotation later completes
- **THEN** both annotation and decision time SHALL use the original `first_roi_locked` timestamp

#### Scenario: [AOB-R002-S04] Save completes after the annotation limit
- **WHEN** Accept validation passes before 30 seconds and pair publication finishes after 30 seconds
- **THEN** annotation time SHALL end at validation, save latency SHALL be reported separately, and navigation SHALL remain disabled until publication succeeds

#### Scenario: [AOB-R002-S05] Needs Review is not a successful Accept
- **WHEN** Needs Review is selected within 30 seconds
- **THEN** decision time SHALL be populated and `within_30_accept` SHALL be false
- **AND** annotation time SHALL remain absent only when no prior valid Accept validation occurred

#### Scenario: [AOB-R002-S06] Save failure is changed to Needs Review
- **WHEN** Accept validation passes, accepted-pair publication fails, and the user subsequently publishes Needs Review
- **THEN** the final disposition SHALL be Needs Review and `within_30_accept` SHALL be false
- **AND** the prior `first_valid_accept_time_ms` and annotation time SHALL remain present as diagnostic evidence

### Requirement: [AOB-R003] Aggregate reports shall expose success and failure denominators
The reporting system MUST publish total presented images, final accepted count, final Needs Review count, unresolved-at-run-cutoff count, valid Accept count, accepted-under-30 count, accepted-over-30 count, sessions-with-timeout count, backend failure count, save failure count, invalid Accept attempts, and wrong-Accept count. Timeout is a diagnostic event flag, not a terminal disposition, so timeout and accepted/review/unresolved counts MAY overlap. `timeout_rate` SHALL equal sessions with any required-operation timeout divided by total presented images. It SHALL publish both accepted-conditional latency distributions and all-image accepted-under-30 rate so Needs Review, timeout, unresolved, or dropped failures cannot improve the apparent success rate.

#### Scenario: [AOB-R003-S01] Mixed outcome aggregation
- **WHEN** a fixture contains one 20-second Accept, one 31-second Accept, one Needs Review, and one timeout followed by Needs Review
- **THEN** the report SHALL calculate total presented images as four, accepted as two, accepted under 30 as one, Needs Review as two, sessions with timeout as one, and SHALL retain both all-image and accepted-conditional denominators

#### Scenario: [AOB-R003-S02] Timed-out session remains unresolved at cutoff
- **WHEN** a required operation times out and no human disposition is durably published before the declared run cutoff
- **THEN** the session SHALL count as timeout and unresolved, SHALL remain in the total-presented denominator, and SHALL have no decision time

#### Scenario: [AOB-R003-S03] Failed cases remain in reports
- **WHEN** an image reaches timeout, save failure, or Needs Review
- **THEN** the outcome SHALL remain in aggregate denominators and MUST NOT be filtered as an incomplete successful sample

### Requirement: [AOB-R004] Deterministic E2E tests shall use controlled dependencies and machine oracles
Tier A E2E acceptance SHALL use a scripted backend, scripted CV gates, controlled monotonic clock, deterministic job barriers, fault-injecting persistence adapter, versioned image/mask fixtures, and actual GUI input injection. Pass/fail MUST be determined from state, call ledgers, event order, candidate and mask hashes, schema validation, and loader results; screenshots alone MUST NOT be the oracle.

#### Scenario: [AOB-R004-S01] Race test uses a barrier
- **WHEN** a stale-job scenario is executed
- **THEN** the test SHALL control job completion with a deterministic barrier rather than an arbitrary sleep and SHALL prove the stale result was not exposed

#### Scenario: [AOB-R004-S02] GUI test sends real input events
- **WHEN** a keyboard or mouse workflow is tested
- **THEN** the test SHALL send events through the GUI framework and SHALL verify controller/session effects rather than calling the target action directly

#### Scenario: [AOB-R004-S03] Fixture result is reproducible
- **WHEN** the same deterministic scenario is repeated with the same source revision, fixture manifest, and seed
- **THEN** candidate ordering, masks, event semantics, and output hashes SHALL be identical

### Requirement: [AOB-R005] Candidate-cardinality E2E coverage shall include zero through three
The mandatory functional suite MUST exercise displayed candidate cardinalities zero, one, two, and three, plus an internal pool larger than three, and SHALL prove that no fake or duplicate display slot is manufactured.

#### Scenario: [AOB-R005-S01] Zero-candidate oracle
- **WHEN** the scripted proposal returns or filters down to zero valid candidates
- **THEN** the oracle SHALL require an empty candidate list, proposal-level diagnostics, and access to manual-empty or Needs Review

#### Scenario: [AOB-R005-S02] One-candidate oracle
- **WHEN** exactly one valid candidate remains
- **THEN** the oracle SHALL require one selectable card and no effect from candidate keys 2 or 3

#### Scenario: [AOB-R005-S03] Two-candidate oracle
- **WHEN** exactly two valid candidates remain
- **THEN** the oracle SHALL require two selectable cards and no third card

#### Scenario: [AOB-R005-S04] Three-candidate oracle
- **WHEN** three valid candidates remain
- **THEN** the oracle SHALL require distinct candidate IDs for cards 1, 2, and 3 and exact selection-key mapping

#### Scenario: [AOB-R005-S05] Oversized internal pool oracle
- **WHEN** native masks, safe-grid variants, or `sam_cv` create more than three internal variants
- **THEN** the oracle SHALL require deterministic deduplication, ranking, and a maximum of three displayed candidates

### Requirement: [AOB-R006] Refinement and manual-fallback E2E coverage shall verify backend call semantics
The mandatory suite SHALL verify that SAM refinement preserves the selected previous state, box, and accumulated points, requests a single output, and adds zero encoder calls. It SHALL also verify that CV-direct and manual candidates reject point refinement, manual-empty starts without a backend call, local editing locks out model mutation, and Undo restores an exact session checkpoint without decoding.

#### Scenario: [AOB-R006-S01] Multi-round refinement oracle
- **WHEN** a foreground point and then a background point are applied to a selected SAM candidate
- **THEN** the backend ledger SHALL show one proposal encode, two chained single-output refinement decodes, accumulated human points, and the selected previous-state lineage

#### Scenario: [AOB-R006-S02] First human point clears automatic guidance
- **WHEN** refinement begins from a candidate produced with safe-grid or fusion context
- **THEN** the oracle SHALL show auto prompts and fusion invalidated before the human-guided decode

#### Scenario: [AOB-R006-S03] Manual-empty acceptance oracle
- **WHEN** zero candidates lead to an empty manual mask, an invalid Accept attempt, a brush stroke, and a valid Accept
- **THEN** the oracle SHALL show no hidden backend call, no validation-pass event for the empty attempt, manual provenance after the stroke, and a valid final full-image mask

#### Scenario: [AOB-R006-S04] Local-edit lock and Undo oracle
- **WHEN** a local operation is applied and then undone to a SAM checkpoint
- **THEN** the oracle SHALL show no model call during edit or Undo, exact mask restoration, and point refinement enabled only after the SAM checkpoint is restored

### Requirement: [AOB-R007] CV E2E coverage shall verify direct, coarse, invalid, and disabled paths
The mandatory suite MUST exercise class recipes returning `direct`, `coarse`, and `invalid`, as well as a disabled recipe. It SHALL prove that direct proposals encode zero times, coarse masks enter the backend only as mask prompts and become `sam_cv`, invalid recipes fall back to SAM, disabled recipes are not called, and no path displays more than three candidates.

#### Scenario: [AOB-R007-S01] CV-direct oracle
- **WHEN** the scripted recipe passes its direct gate
- **THEN** the oracle SHALL require a `cv_direct` candidate with CV generator provenance, zero encoder and decoder calls, disabled point tools, explicit human Accept, and no auto-accept

#### Scenario: [AOB-R007-S02] CV-coarse oracle
- **WHEN** the scripted recipe returns a known coarse mask
- **THEN** the oracle SHALL require one proposal encode, an exact coarse-mask hash at the mask-prompt bridge, a displayed `sam_cv` rather than raw coarse candidate, and at most three cards

#### Scenario: [AOB-R007-S03] Invalid recipe oracle
- **WHEN** the recipe result is invalid
- **THEN** diagnostics SHALL be recorded and normal SAM proposal behavior SHALL proceed with one encode

#### Scenario: [AOB-R007-S04] Disabled recipe oracle
- **WHEN** the class recipe is disabled
- **THEN** the CV call count SHALL be zero and the normal SAM proposal path SHALL execute

### Requirement: [AOB-R008] Revision and stale-job E2E coverage shall be deterministic
The mandatory suite MUST exercise ROI redraw and Expand ROI during pending proposal and refinement work. It SHALL prove that the first timer origin is retained, the revision increments, old candidate handles are invalid, cancelled or late jobs cannot change the GUI, and only the current revision can be selected, edited, committed, or persisted.

#### Scenario: [AOB-R008-S01] Proposal completes after ROI redraw
- **WHEN** revision-one proposal completion is delayed until revision-two proposal has started
- **THEN** the oracle SHALL show revision one cancelled or discarded, its cards absent, its handles stale, and only revision-two candidates selectable

#### Scenario: [AOB-R008-S02] Refinement completes after ROI redraw
- **WHEN** a refinement result from the old crop arrives after ROI change
- **THEN** the canvas and current candidate hash SHALL remain owned by the new revision

#### Scenario: [AOB-R008-S03] Expand ROI follows a CV-direct result
- **WHEN** Expand ROI produces a new crop whose recipe again passes direct
- **THEN** the new revision SHALL re-run the recipe and SHALL retain an encoder count of zero

### Requirement: [AOB-R009] Persistence E2E coverage shall prove pair consistency and recovery
The mandatory suite MUST inject failure at temporary PNG write, temporary sidecar write, validation, PNG publication, and sidecar publication; MUST simulate orphan and corrupt pairs; and MUST prove that the accepted loader rejects every incomplete, mismatched, review-only, or unsupported artifact while a retained session can retry successfully.

#### Scenario: [AOB-R009-S01] Every save stage is fault injected
- **WHEN** the persistence failure matrix runs
- **THEN** every injected failure SHALL leave next-image disabled, preserve the pending result, expose `SAVE_FAILED`, and yield zero newly loadable accepted pair until retry succeeds

#### Scenario: [AOB-R009-S02] Crash leaves a published PNG without a matching sidecar
- **WHEN** execution stops after PNG publication and before sidecar publication
- **THEN** the loader SHALL reject the orphan or hash mismatch and the evidence SHALL show that no partial pair entered training enumeration

#### Scenario: [AOB-R009-S03] Retry publishes a complete pair
- **WHEN** a storage fault is removed and save is retried
- **THEN** the loader SHALL return one matching accepted mask and sidecar with the expected hashes

#### Scenario: [AOB-R009-S04] Review artifacts are isolated
- **WHEN** accepted and Needs Review artifacts coexist
- **THEN** the accepted loader SHALL enumerate only accepted, training-eligible, integrity-valid pairs

### Requirement: [AOB-R010] GUI E2E coverage shall verify every frozen interaction
The mandatory GUI suite MUST verify candidate keys `1`/`2`/`3`, left/right point inputs, `B`, `[`, `]`, `F`, `X`, `Z`, `Space`, and `N`, plus the visible Erase and Needs Review controls. It SHALL verify capability-based disabled states, save gating, and absence of out-of-scope v1 controls.

#### Scenario: [AOB-R010-S01] Candidate and point inputs
- **WHEN** actual candidate keys and left/right canvas clicks are injected
- **THEN** candidate IDs and foreground/background prompt records SHALL match the input sequence and coordinate transform oracle

#### Scenario: [AOB-R010-S02] Local-edit inputs
- **WHEN** brush, Erase, shrink, grow, fill holes, and Undo are invoked through GUI controls
- **THEN** the resulting mask hashes SHALL match golden operations and backend call counts SHALL remain unchanged

#### Scenario: [AOB-R010-S03] Accept and next-image gating
- **WHEN** `Space` is followed by `N` before save completion and again after save completion
- **THEN** navigation SHALL be rejected before `ACCEPTED` and allowed afterward

#### Scenario: [AOB-R010-S04] Non-refinable candidate controls
- **WHEN** `cv_direct` or a manual candidate is selected
- **THEN** foreground/background controls SHALL be disabled with an accessible reason and local tools SHALL remain enabled

#### Scenario: [AOB-R010-S05] Frozen-scope control inventory
- **WHEN** the GUI starts with default settings
- **THEN** its accessibility tree SHALL omit text/VLM, DINO, per-image color sliders, multi-instance tabs, and default fusion, and SHALL contain no automatic Accept action

### Requirement: [AOB-R011] UI responsiveness shall have a hard overlay and brush gate
On the fingerprinted reference Windows CPU, the acceptance runner SHALL measure input-to-frame latency for overlay and brush interaction with inference isolated in the configured background process. The p95 latency MUST be less than 100 ms, and the evidence SHALL include p50, p90, p95, maximum, sample count, thread policy, and active backend workload.

#### Scenario: [AOB-R011-S01] Overlay and brush benchmark passes
- **WHEN** the prescribed reference-machine interaction workload is executed
- **THEN** measured p95 input-to-frame latency SHALL be below 100 ms and all required distribution and hardware fields SHALL be present

#### Scenario: [AOB-R011-S02] Encoder is busy during GUI interaction
- **WHEN** the same workload runs while a proposal encoder job is pending
- **THEN** the GUI SHALL continue processing events and SHALL still be evaluated against the frozen responsiveness gate

### Requirement: [AOB-R012] Backend performance shall be measured only on fingerprinted hardware
The acceptance runner SHALL record cold model load, warm encoder, initial decoder, cached refinement, peak RAM, cache behavior, ROI/crop sizes, and target occupancy on a recorded reference CPU with fixed runtime and thread policy. Cached refine p95 SHALL be compared with the PRD target of at most one second as a best-effort SLO unless the acceptance profile promotes it to a hard threshold. Shared or unfingerprinted CI MUST NOT be used to claim performance acceptance.

#### Scenario: [AOB-R012-S01] Reference-CPU benchmark evidence is complete
- **WHEN** Tier B performance tests finish
- **THEN** the evidence SHALL include machine fingerprint, dependency/model hashes, thread settings, p50/p90/p95/max latency, peak RAM, and pass/report-only classification for each threshold

#### Scenario: [AOB-R012-S02] Shared CI produces timing data
- **WHEN** functional CI runs on hardware that is not the recorded reference machine
- **THEN** its timing MAY be retained diagnostically but MUST NOT satisfy the Tier B performance gate

### Requirement: [AOB-R013] Quality acceptance shall combine objective boundary and human outcomes
Before domain validation, an approved acceptance profile MUST identify the representative image manifest, annotation policy, independent gold subset, boundary metric and tolerance, minimum valid Accept rate, maximum Needs Review and timeout rates, and maximum wrong-Accept rate. `domain-validated` SHALL require both the objective boundary gate and independent human judgement that accepted masks are training-usable; IoU alone MUST NOT satisfy the requirement.

#### Scenario: [AOB-R013-S01] Domain quality passes
- **WHEN** the approved representative dataset is annotated and independently reviewed
- **THEN** the evaluation SHALL calculate the frozen boundary metric and workflow outcome rates and SHALL pass only if every configured objective and human threshold passes

#### Scenario: [AOB-R013-S02] Boundary passes but human review fails
- **WHEN** objective metrics meet their thresholds but independent reviewers reject too many accepted masks as training-unusable
- **THEN** domain validation SHALL fail

#### Scenario: [AOB-R013-S03] Human review passes but boundary fails
- **WHEN** reviewer outcomes pass but the frozen boundary metric fails
- **THEN** domain validation SHALL fail

#### Scenario: [AOB-R013-S04] Required domain inputs are absent
- **WHEN** representative approved data, gold masks, annotation policy, or independent reviewer evidence is unavailable
- **THEN** the release SHALL report `domain-validated=false` or `BLOCKED` for Tier C and MUST NOT fabricate or substitute synthetic evidence

### Requirement: [AOB-R014] Feature retention shall be evidence based
After the frozen v1 engineering baseline has been implemented and verified, an optional model/provider, recipe enhancement, prompt strategy, or GUI feature proposed beyond that baseline SHALL remain enabled by default only when controlled comparison shows reduced annotation time or user actions without degrading the frozen boundary-quality gate. This retention gate SHALL NOT be a prerequisite for, recursively gate, or disable the frozen MobileSAM correctness backend or frozen safe-grid engineering baseline. If Tier C comparison inputs are unavailable, the optional post-baseline feature SHALL remain disabled and that absence MUST NOT block M0 through M4, `PASS_ENGINEERING`, or the v1 engineering baseline. The evaluation MUST report candidate-selection, Undo, prompt, stroke, and Needs Review outcomes rather than treating feature count as success.

#### Scenario: [AOB-R014-S01] Feature reduces actions without harming quality
- **WHEN** an optional post-baseline feature has an A/B evaluation showing fewer clicks or strokes and no boundary regression under the frozen tolerance
- **THEN** the feature MAY pass its retention gate with the comparison evidence attached without changing the already frozen baseline gates

#### Scenario: [AOB-R014-S02] Feature adds complexity without measured benefit
- **WHEN** an optional post-baseline feature does not reduce time/actions, does not improve required quality, or lacks the Tier C inputs required for its comparison
- **THEN** its retention gate SHALL fail or remain blocked and it MUST NOT become a default v1 hot-path dependency
- **AND** the frozen MobileSAM and safe-grid engineering baseline SHALL remain eligible for M4 and `PASS_ENGINEERING`

### Requirement: [AOB-R015] Every acceptance run shall produce a self-describing evidence bundle
Each release-gate run MUST create `evidence/<run-id>/` containing a manifest with source revision and dirty-state fingerprint, executed commands and exit codes, OS/CPU/RAM, Python and dependency-lock hashes, model/checkpoint and recipe hashes, scenario-to-requirement mapping, structured events, backend and filesystem ledgers, test results, performance and quality metrics, output artifact hashes, and failure screenshots or traces. Before any task checkbox or release verdict, the repository-owned `validate-contracts`, `validate-evidence`, and `validate-state` commands MUST pass for the applicable task or complete run bundle and MUST bind to the same source, task graph, contracts, profile, state, and evidence hashes. Release-gate validation SHALL evaluate only milestones, scenarios, thresholds, and external inputs applicable to the declared `target_release_class`. The bundle SHALL be sufficient for an independent runner to identify exactly what was tested.

#### Scenario: [AOB-R015-S01] Passing evidence bundle is audited
- **WHEN** all required scenarios report pass
- **THEN** `validate-contracts`, `validate-evidence`, and `validate-state` SHALL each exit zero and the evidence validator SHALL verify every required file, field, hash, test ID, requirement ID, command exit code, and release-threshold result before issuing a passing verdict

#### Scenario: [AOB-R015-S02] Evidence is missing or inconsistent
- **WHEN** a required scenario, manifest field, output hash, command result, threshold record, or mandatory validator result is absent, stale, non-zero, or inconsistent
- **THEN** the evidence validator SHALL fail the corresponding gate and SHALL forbid the task checkbox or release verdict rather than inferring success

#### Scenario: [AOB-R015-S03] Dirty source tree is tested
- **WHEN** a run is performed from uncommitted or otherwise dirty source state
- **THEN** the manifest SHALL record a reproducible dirty-state fingerprint and the release process MUST NOT attribute the evidence solely to the clean source revision

### Requirement: [AOB-R016] Offline clean-machine acceptance shall be part of Tier B
Tier B SHALL install and run the release on a clean Windows x64 machine with outbound networking disabled, empty dependency and model caches, no CUDA requirement, and no account or service login. The test MUST import the common package, launch the GUI, run a real packaged-backend annotation through save and reload, and verify dependency, model, checksum, SBOM, notice, and license manifests.

#### Scenario: [AOB-R016-S01] Offline install and import
- **WHEN** the offline bundle is installed on the clean machine with `--no-index` or equivalent network isolation
- **THEN** installation and `import segvision` SHALL succeed without a download, login, CUDA provider, or remote service

#### Scenario: [AOB-R016-S02] Offline GUI annotation and reload
- **WHEN** the packaged GUI completes ROI, proposal, explicit Accept, save, close, reopen, and reload on the clean machine
- **THEN** the accepted mask and sidecar SHALL reload with matching hashes and no network dependency

#### Scenario: [AOB-R016-S03] Runtime has no hidden GPU or network dependency
- **WHEN** process module and socket activity are audited during cold launch and inference
- **THEN** the release SHALL require no CUDA DLL/provider and SHALL make no required outbound connection

#### Scenario: [AOB-R016-S04] License or manifest entry is missing
- **WHEN** a bundled runtime, model code, checkpoint, conversion artifact, or GUI dependency lacks the required source, hash, license, or redistribution record
- **THEN** Tier B release acceptance SHALL fail

### Requirement: [AOB-R017] Release classification shall be explicit and machine-verifiable
Every release run SHALL declare `target_release_class` as `engineering` or `domain`; absent an explicit repository-owned target, it SHALL use `engineering`. The release system SHALL issue `engineering-accepted` only when M0 through M4 and all deterministic Tier A scenarios, fingerprinted Tier B performance gates, persistence integrity, clean-machine offline execution, packaging, security, and license-manifest checks pass. It SHALL issue `domain-validated` only when M0 through M5 pass and the same build or a traceable successor is engineering-accepted and all Tier C data, independent review, boundary, time, and workflow thresholds also pass. Missing Tier C inputs MUST NOT prevent an otherwise compliant engineering-target candidate from being labeled `engineering-accepted`.

#### Scenario: [AOB-R017-S01] Engineering acceptance succeeds without domain data
- **WHEN** all Tier A and Tier B gates pass but approved Tier C data is unavailable
- **THEN** an engineering-target run SHALL emit `PASS_ENGINEERING` with `engineering_accepted=true` and `domain_validated=false`
- **AND** a domain-target run SHALL retain `engineering_accepted=true`, emit `BLOCKED_EXTERNAL_INPUT`, and use `project_state=implementation_complete_release_blocked` until its required Tier C inputs exist

#### Scenario: [AOB-R017-S02] Domain validation succeeds
- **WHEN** Tier A and Tier B pass and every approved Tier C threshold and evidence requirement also passes
- **THEN** the verdict SHALL be `PASS_DOMAIN_VALIDATED` and set both `engineering_accepted=true` and `domain_validated=true`

#### Scenario: [AOB-R017-S03] Deterministic or reference-machine gate fails
- **WHEN** every independent runnable task has been exhausted and a mandatory non-external Tier A or Tier B gate remains finally failed, or its owning task is `rejected`, after the allowed materially different attempts
- **THEN** an engineering-target verdict SHALL be `FAIL` with `project_state=failed` and both classifications SHALL be false
- **AND** a missing external input, license authority, or designated reference machine SHALL instead use the applicable `BLOCKED_*` verdict and `project_state=implementation_complete_release_blocked`

#### Scenario: [AOB-R017-S04] Domain gate fails after engineering acceptance
- **WHEN** Tier A and Tier B pass, every independent runnable task has been exhausted, and an available-input Tier C metric or independent review threshold remains finally failed after its allowed attempts
- **THEN** the domain-target verdict SHALL be `FAIL` with `project_state=failed`, `engineering_accepted` MAY remain true when all Tier A/B gates still pass, and `domain_validated` SHALL be false with the failing gate IDs recorded

### Requirement: [AOB-R018] The final verdict shall be machine readable and non-gameable
The acceptance runner MUST emit a final structured verdict conforming to `acceptance/release-verdict.schema.json` and containing the target release class, project state, required/passed/failed functional scenarios, flaky retry count, partial-pair and corruption acceptance counts, performance distributions, accepted-under-30 and review/timeout rates, boundary and reviewer metrics, offline/network/CUDA results, release classifications, blockers, and evidence hashes. Its verdict MUST be exactly one of `PASS_ENGINEERING`, `PASS_DOMAIN_VALIDATED`, `FAIL`, `BLOCKED_EXTERNAL_INPUT`, `BLOCKED_LICENSE`, or `BLOCKED_REFERENCE_HARDWARE`. It MUST NOT emit or change that verdict until `validate-contracts`, `validate-evidence` for the complete run bundle, and `validate-state` all pass against matching hashes. `FAIL` SHALL be emitted only after independent runnable work is exhausted and a mandatory non-external gate remains finally failed or rejected after the allowed attempts. Mandatory failures, missing frozen thresholds, or unapproved threshold changes MUST NOT produce a passing verdict.

#### Scenario: [AOB-R018-S01] All configured gates pass
- **WHEN** every mandatory scenario applicable to `target_release_class` passes and every profile threshold and evidence field required for that target is present
- **THEN** the verdict SHALL be `PASS_ENGINEERING` or `PASS_DOMAIN_VALIDATED` according to `target_release_class`, with zero failed mandatory scenarios and the applicable cumulative classification

#### Scenario: [AOB-R018-S02] Acceptance profile is incomplete
- **WHEN** a gate requires target hardware, boundary, Accept, Needs Review, timeout, or wrong-Accept thresholds that have not been frozen
- **THEN** the verdict SHALL be the applicable `BLOCKED_EXTERNAL_INPUT`, `BLOCKED_LICENSE`, or `BLOCKED_REFERENCE_HARDWARE` value for the affected release tier and SHALL list the exact missing profile fields
- **AND** a Tier C-only field that is not applicable to an engineering target SHALL NOT block or fail `PASS_ENGINEERING`

#### Scenario: [AOB-R018-S03] Test passes only after an automatic retry
- **WHEN** a mandatory deterministic scenario fails and then passes only through an unreported retry
- **THEN** the evidence validator SHALL reject the run; any authorized rerun MUST remain visible with its reason and SHALL NOT erase the original failure

#### Scenario: [AOB-R018-S04] Threshold is weakened during a run
- **WHEN** a threshold or required scenario is changed after the run begins to make a failure pass
- **THEN** the verdict SHALL fail evidence consistency and SHALL require a new versioned acceptance profile and a complete rerun
