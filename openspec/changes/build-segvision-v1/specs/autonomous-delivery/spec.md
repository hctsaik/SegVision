## ADDED Requirements

### Requirement: [AUT-R001] Authoritative inputs and scope precedence
The autonomous delivery agent SHALL treat the frozen `PRD.md` as the highest product authority, this OpenSpec change as the implementation behavior authority, and the final development recommendation as subordinate guidance. The agent MUST NOT resolve a conflict by silently changing a higher-priority requirement.

#### Scenario: [AUT-R001-S01] Guidance conflicts with the frozen product contract
- **WHEN** a task discovers that implementation guidance contradicts the PRD or an OpenSpec requirement
- **THEN** the agent MUST stop the affected behavior change and record the exact conflict
- **AND** it MUST continue only work that is independent of that conflict

### Requirement: [AUT-R002] Dependency-driven task graph
Delivery SHALL be represented as a directed acyclic graph whose nodes declare dependencies and milestone membership. The agent MUST execute a node only after every required dependency has passed and every applicable authority gate has been approved.

#### Scenario: [AUT-R002-S01] Task dependencies have passed
- **WHEN** a pending task has passing dependency checkpoints and no unresolved required gate
- **THEN** the controller SHALL mark it `runnable`

#### Scenario: [AUT-R002-S02] Dependency has not passed
- **WHEN** any required predecessor is pending, failed, rejected, or blocked
- **THEN** the dependent task MUST remain non-runnable
- **AND** the agent MUST NOT manufacture or assume the missing predecessor output

### Requirement: [AUT-R003] Complete task definition
Every executable task SHALL declare a stable task ID, objective, dependencies, owned files, required inputs, expected outputs, commands, required evidence, pass criteria, retry policy, fallback, rollback boundary, and escalation conditions. A task missing any field required for safe execution MUST NOT become runnable.

#### Scenario: [AUT-R003-S01] Task definition is complete
- **WHEN** the controller evaluates a task containing all required execution fields
- **THEN** it SHALL validate the task and make it eligible for dependency evaluation

#### Scenario: [AUT-R003-S02] Task lacks evidence or rollback instructions
- **WHEN** a task definition omits required evidence or a safe rollback boundary
- **THEN** the controller MUST reject the task definition
- **AND** no repository mutation SHALL begin for that task

### Requirement: [AUT-R004] Explicit task state machine
The task controller SHALL use the states `pending`, `runnable`, `running`, `passed`, `failed_retryable`, `blocked_external_input`, `blocked_license`, `blocked_reference_hardware`, and `rejected`. Every transition MUST include a timestamp, reason, and evidence reference, and a task MUST NOT transition directly from `running` to `passed` without completing its declared validation.

#### Scenario: [AUT-R004-S01] Validation succeeds
- **WHEN** a running task produces all outputs and every required command exits successfully
- **THEN** the controller SHALL record its evidence and transition it to `passed`

#### Scenario: [AUT-R004-S02] External authority is missing
- **WHEN** a running or pending task requires an external human/data input, a license decision, or designated reference hardware that the agent cannot supply
- **THEN** the controller SHALL transition it to `blocked_external_input`, `blocked_license`, or `blocked_reference_hardware` as applicable
- **AND** it MUST preserve all prior passing checkpoints

### Requirement: [AUT-R005] Read-only preflight before mutation
Before the first repository mutation in a run, the agent SHALL inspect project instructions, authoritative specifications, repository files, current source revision, dirty worktree paths, available Python runtimes, and relevant host hardware. It MUST record this baseline and MUST NOT overwrite or hide pre-existing changes.

#### Scenario: [AUT-R005-S01] Worktree is clean or non-overlapping
- **WHEN** preflight finds no user modification in the task-owned files
- **THEN** the agent SHALL record the baseline and may begin the task

#### Scenario: [AUT-R005-S02] User change overlaps task ownership
- **WHEN** preflight finds an existing user change in a file the task must edit and the changes cannot be safely composed
- **THEN** the task MUST stop before writing that file
- **AND** the overlap MUST be escalated with the observed diff summary

### Requirement: [AUT-R006] File ownership and safe parallelism
Each running task SHALL own an explicit, minimal file set. The controller MAY run independent tasks concurrently only when their owned files and mutable external resources do not overlap, and it MUST serialize tasks that share a file, cache mutation, environment, package artifact, or benchmark machine.

#### Scenario: [AUT-R006-S01] Independent tasks are available
- **WHEN** two runnable tasks have disjoint owned files and no shared mutable execution resource
- **THEN** the controller MAY execute them concurrently

#### Scenario: [AUT-R006-S02] Tasks share a mutable file
- **WHEN** two runnable tasks both declare ownership of the same file or generated artifact
- **THEN** the controller MUST serialize them in dependency order

### Requirement: [AUT-R007] Test-first bounded execution loop
For each task, the agent SHALL inspect the referenced requirement and existing implementation, add or update focused tests, implement the smallest compliant change, run the focused gate, run every affected regression gate, record evidence, update directly affected documentation, and only then checkpoint the task. The agent MUST NOT broaden scope merely because adjacent work is convenient.

#### Scenario: [AUT-R007-S01] Focused implementation succeeds
- **WHEN** focused tests and all affected regressions pass for the smallest compliant change
- **THEN** the agent SHALL record the outputs and proceed to checkpoint

#### Scenario: [AUT-R007-S02] Adjacent refactor is unnecessary
- **WHEN** an unrelated cleanup is not required to satisfy the current requirement
- **THEN** the agent MUST leave that cleanup outside the task-owned change

### Requirement: [AUT-R008] Focused and regression validation
Every task SHALL declare at least one focused validation command, and every task that changes a shared contract, public API, data schema, state machine, persistence behavior, packaging behavior, or runtime dependency MUST run the applicable milestone regression suite. A skipped required test MUST be treated as a failed or blocked gate, not as a pass.

#### Scenario: [AUT-R008-S01] Shared contract changes
- **WHEN** a task modifies a public type or common session behavior
- **THEN** it SHALL run its focused contract tests and the complete affected core and integration regression suites

#### Scenario: [AUT-R008-S02] Required test cannot execute
- **WHEN** a required test cannot run because an environment, artifact, or authority is unavailable
- **THEN** the task MUST record the missing prerequisite and remain blocked or failed
- **AND** it MUST NOT mark the skipped test as successful

### Requirement: [AUT-R009] Structured and reproducible task evidence
Every task SHALL emit an evidence record containing task ID, dependency checkpoint IDs, source revision and dirty-state hash, input hashes, owned-file output hashes, exact commands, exit codes, test results, benchmark results when applicable, tool versions, warnings, retry history, and timestamps. Evidence MUST be sufficient for another agent to determine why the task passed, failed, or blocked.

#### Scenario: [AUT-R009-S01] Passing task is audited
- **WHEN** another agent reads the task evidence
- **THEN** it SHALL be able to identify the exact inputs, commands, outputs, and validations that justified `passed`

#### Scenario: [AUT-R009-S02] Command output contains a secret
- **WHEN** evidence collection encounters a credential, token, private URL, or other secret
- **THEN** the evidence writer MUST redact the secret while preserving the command outcome and diagnostic meaning

### Requirement: [AUT-R010] Strict task completion
A task SHALL transition to `passed` only when all dependencies remain passed, all declared outputs exist and validate, every required command exits successfully, focused and regression gates pass, required evidence is stored, no prohibited action occurred, and changes remain within the owned-file boundary.

#### Scenario: [AUT-R010-S01] Output exists but regression fails
- **WHEN** a task creates its expected files but an affected regression gate fails
- **THEN** the task MUST NOT transition to `passed`

#### Scenario: [AUT-R010-S02] All completion conditions hold
- **WHEN** outputs, validation, evidence, ownership, and policy checks all pass
- **THEN** the task SHALL transition to `passed` and publish a checkpoint ID

### Requirement: [AUT-R011] Materially different bounded retries
The agent MAY attempt a deterministic failed task no more than three times in total. Every retry MUST record a new root-cause hypothesis or materially different corrective action; the agent MUST NOT repeatedly run an unchanged command solely to obtain a passing result.

#### Scenario: [AUT-R011-S01] Retry uses a new hypothesis
- **WHEN** an initial implementation fails and the agent identifies a different, evidence-based correction
- **THEN** the controller SHALL record the hypothesis and permit the next attempt within the limit

#### Scenario: [AUT-R011-S02] Third materially different attempt fails
- **WHEN** three attempts fail to satisfy the task gate
- **THEN** the controller MUST stop automatic retries
- **AND** it SHALL apply the declared safe fallback or record a blocker

### Requirement: [AUT-R012] Failure-specific safe fallback
Each task SHALL use the fallback declared for its failure class. Dependency conflicts MUST fall back to a clean isolated environment and reviewed pins; unavailable approved models MUST fall back to the fake backend while blocking real-model gates; a failing CPU backend MUST be rejected or replaced only by another authorized CPU backend; a slow GUI MUST fall back to a different local rendering implementation; and an ineffective class recipe MUST remain disabled.

#### Scenario: [AUT-R012-S01] Approved checkpoint is temporarily unavailable
- **WHEN** verified official-source retries fail to obtain the approved checkpoint
- **THEN** core and fake-backend work SHALL remain usable
- **AND** real-model and release tasks MUST become blocked rather than selecting an unapproved mirror

#### Scenario: [AUT-R012-S02] CV recipe does not improve evidence
- **WHEN** a class recipe fails its time, action-count, or boundary-quality admission gate
- **THEN** the recipe SHALL remain `enabled=false`
- **AND** the agent MUST NOT tune per-image controls to force a pass

### Requirement: [AUT-R013] Integrity and license failures cannot be bypassed
A missing license approval, incompatible redistribution term, or checksum mismatch MUST stop the affected acquisition, packaging, or release task immediately. The agent MUST NOT spend retries searching for unofficial artifacts, relabel an artifact, omit a manifest field, or substitute inferred permission.

#### Scenario: [AUT-R013-S01] Checkpoint hash is wrong
- **WHEN** an acquired model artifact does not match the approved hash
- **THEN** the agent MUST quarantine it and mark the task blocked or failed
- **AND** it MUST NOT load or package the artifact

#### Scenario: [AUT-R013-S02] Commercial authority is unknown
- **WHEN** the intended distribution requires authority not present in the manifest
- **THEN** the task SHALL become `blocked_license`
- **AND** the agent MUST request the exact missing approval once

### Requirement: [AUT-R014] Passing-task checkpoints
After a task passes, the agent SHALL create an immutable checkpoint that identifies its dependency checkpoints, source revision, task-owned file hashes, test evidence, and generated artifacts. If repository policy authorizes agent commits, the checkpoint MUST use one atomic task commit; otherwise it MUST use a recorded patch and hashes without modifying unrelated work.

#### Scenario: [AUT-R014-S01] Task passes with commit authority
- **WHEN** repository policy permits commits and the task gate passes
- **THEN** the agent SHALL create one task-scoped commit and record its commit ID in the evidence

#### Scenario: [AUT-R014-S02] Commit authority is absent
- **WHEN** repository policy does not authorize commits
- **THEN** the agent SHALL preserve an auditable patch and output hashes
- **AND** lack of a commit MUST NOT justify touching unrelated files

### Requirement: [AUT-R015] Non-destructive rollback
Rollback SHALL affect only the failed task's owned changes and artifacts. The agent MUST use an inverse patch, task-scoped revert, or selection of a prior verified artifact, and MUST NOT use destructive worktree reset, broad checkout, broad recursive deletion, or history rewriting.

#### Scenario: [AUT-R015-S01] Latest task must be rolled back
- **WHEN** a newly completed task causes a later mandatory gate to fail
- **THEN** the agent SHALL revert only that task checkpoint or apply its recorded inverse patch
- **AND** all earlier passing checkpoints and user changes SHALL remain intact

#### Scenario: [AUT-R015-S02] Release artifact rollback is required
- **WHEN** a new release candidate fails after an earlier candidate passed
- **THEN** the controller SHALL restore or republish the prior verified artifact by hash
- **AND** it MUST retain the failed candidate's evidence for audit

### Requirement: [AUT-R016] Protected user data and accepted annotations
Autonomous execution MUST preserve pre-existing user work, source data, gold data, accepted annotations, and prior release evidence. Tests MUST write only to isolated generated directories, and schema or recipe changes MUST be versioned instead of destructively rewriting accepted data in place.

#### Scenario: [AUT-R016-S01] Persistence test needs output files
- **WHEN** an automated test writes PNG, sidecar, draft, or temporary data
- **THEN** it SHALL use an isolated task-owned test directory
- **AND** cleanup MUST target only the verified generated directory

#### Scenario: [AUT-R016-S02] Existing accepted annotation is present
- **WHEN** a test or migration encounters an accepted annotation from an earlier version
- **THEN** it MUST leave the original pair unchanged
- **AND** any converted output SHALL use a new versioned location or filename

### Requirement: [AUT-R017] Product-scope prohibitions
The autonomous agent MUST NOT introduce GPU or cloud inference, VLM, DINO, SAM 2 or SAM 3, HQ-SAM, multi-provider racing, automatic Accept, default fusion, global pixel OR, per-image threshold sliders, multi-class or video behavior, custom-model training, or an additional production inference runtime into v1. It MUST NOT weaken the three-candidate cap, previous-state refinement, local-edit model lock, explicit Accept, Needs Review separation, or CPU/offline requirements.

#### Scenario: [AUT-R017-S01] Failing latency tempts a GPU fallback
- **WHEN** the selected CPU backend misses a measured target
- **THEN** the agent MUST optimize within the approved CPU contract or reject the backend
- **AND** it MUST NOT add GPU or remote inference without a new approved OpenSpec change

#### Scenario: [AUT-R017-S02] Later feature appears convenient
- **WHEN** an implementation task could be simplified by adding a prohibited Later capability
- **THEN** the agent MUST keep that capability out of the task and record it only as follow-up work

### Requirement: [AUT-R018] Test and evidence integrity
The agent MUST NOT weaken thresholds, delete or skip required tests, alter fixtures solely to hide a regression, relabel Needs Review as Accept, fabricate command output, synthesize human approval, generate fake gold truth for domain claims, or report shared-CI timing as reference-machine evidence.

#### Scenario: [AUT-R018-S01] Required performance threshold fails
- **WHEN** measured performance misses a frozen threshold
- **THEN** the evidence SHALL report the failure unchanged
- **AND** the agent MUST NOT lower the threshold or discard slow samples to create a pass

#### Scenario: [AUT-R018-S02] Domain data is unavailable
- **WHEN** only synthetic or agent-generated fixtures exist
- **THEN** the agent MAY complete deterministic engineering tests
- **AND** it MUST NOT claim domain validation

### Requirement: [AUT-R019] Bounded escalation eligibility
The agent SHALL escalate only when safe in-scope alternatives are exhausted and the remaining blocker is one of: overlapping externally owned changes, destructive or irreversible authority, missing commercial-use or redistribution permission, unavailable required official checkpoint, unavailable representative domain data or independent gold truth, a frozen PRD/OpenSpec contradiction, target hardware failure after measured optimization, or a security or privacy restriction on required data.

#### Scenario: [AUT-R019-S01] Ordinary implementation choice remains
- **WHEN** the agent can choose a compliant module name, internal algorithm, test structure, local GUI implementation, or compatible pinned dependency using repository evidence
- **THEN** it SHALL make the choice and continue without escalation

#### Scenario: [AUT-R019-S02] Required legal authority is missing
- **WHEN** no safe authorized artifact or distribution path remains
- **THEN** the agent SHALL escalate the exact authority gap
- **AND** it MUST stop only tasks that depend on that authority

### Requirement: [AUT-R020] Machine-readable escalation record
Every escalation SHALL identify the blocked task and gate, observed evidence, materially different attempts, safe alternatives tried, exact missing authority or input, two or three mutually exclusive options when a decision is required, the recommended option, the safe no-response state, and the earliest milestone affected.

#### Scenario: [AUT-R020-S01] Escalation is emitted
- **WHEN** a blocker satisfies an allowed escalation condition
- **THEN** the agent SHALL write a machine-readable blocker artifact with every required field
- **AND** the user-facing request SHALL be a concise projection of that artifact

#### Scenario: [AUT-R020-S02] Escalation lacks attempted alternatives
- **WHEN** the blocker record does not show that safe in-scope alternatives were considered
- **THEN** the controller MUST reject the escalation as incomplete

### Requirement: [AUT-R021] Independent work continues around blockers
When a task becomes blocked, the controller SHALL continue every runnable task that does not consume the missing authority, data, artifact, hardware, or conflicted file. A blocked human or license gate MUST NOT freeze pure core, fake-backend, test, documentation, or other independent work.

#### Scenario: [AUT-R021-S01] Model license gate is blocked
- **WHEN** model authorization is unavailable but core tasks depend only on the fake backend
- **THEN** the controller SHALL continue and complete the eligible core tasks
- **AND** only real-model, packaging, and dependent release tasks SHALL remain blocked

### Requirement: [AUT-R022] Resumable autonomous execution
The controller SHALL reconstruct execution state from authoritative task definitions, passed checkpoints, blocker artifacts, and evidence after interruption or agent replacement. It MUST revalidate the current source and input hashes before reusing a prior task result.

#### Scenario: [AUT-R022-S01] Agent resumes after interruption
- **WHEN** a new agent loads a run with passing checkpoints
- **THEN** it SHALL verify the checkpoint inputs and outputs
- **AND** it SHALL resume from the earliest runnable task without repeating valid completed work

#### Scenario: [AUT-R022-S02] Input changed after checkpoint
- **WHEN** a required input hash differs from the checkpoint record
- **THEN** the controller MUST invalidate the affected checkpoint and its dependents
- **AND** it SHALL rerun them in dependency order

### Requirement: [AUT-R023] Milestone and release completion
A milestone SHALL be complete only when every required node and exit gate in that milestone has passed. Release completion SHALL evaluate only milestones and external gates applicable to the declared `target_release_class`: engineering requires M0 through M4, while domain requires M0 through M5 and all Tier C inputs. An implementation with complete source and tests but missing human data, hardware evidence, license authorization, or release signoff required by its declared target MUST use project state `implementation_complete_release_blocked`, not a passing verdict. Missing Tier C inputs MUST NOT block an engineering-target completion.

#### Scenario: [AUT-R023-S01] Engineering implementation is complete but external gate is missing
- **WHEN** all autonomous engineering tasks pass but a required external release input remains unavailable
- **THEN** the controller SHALL report `implementation_complete_release_blocked`
- **AND** it MUST identify the exact promotion input still required

#### Scenario: [AUT-R023-S02] Engineering milestone gates pass
- **WHEN** M0 through M4 and every engineering-target hardware, artifact, and license gate pass
- **THEN** the controller SHALL permit `PASS_ENGINEERING` classification without requiring M5

#### Scenario: [AUT-R023-S03] Domain milestone gates pass
- **WHEN** M0 through M5 and every applicable data, human, hardware, and license gate pass
- **THEN** the controller SHALL permit `PASS_DOMAIN_VALIDATED` classification according to the offline-release specification

### Requirement: [AUT-R024] Release-label authority
The autonomous controller SHALL assign `engineering-accepted` only when the offline-release Tier A and Tier B gates pass, and SHALL assign `domain-validated` only when the additional approved real-domain and human evidence passes. It MUST bind each label to exact source, dependency-lock, model, recipe, package, and evidence hashes.

#### Scenario: [AUT-R024-S01] Deterministic and reference gates pass without domain evidence
- **WHEN** the candidate satisfies all engineering gates but lacks approved representative-domain evidence
- **THEN** the controller MAY assign `engineering-accepted`
- **AND** it MUST leave `domain-validated` false

#### Scenario: [AUT-R024-S02] Candidate changes after label assignment
- **WHEN** source, dependency lock, model, recipe, or packaged artifact hash changes
- **THEN** the prior label MUST NOT transfer to the changed candidate
- **AND** all affected gates SHALL run again before classification
