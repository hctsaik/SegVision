# SegVision v1 Autonomous Implementation Tasks

> This file is the human-readable projection of `acceptance/task-graph.json`.
> Every checkbox intentionally starts unchecked. A task may be checked only after every declared output, command, pass criterion, and evidence requirement in the corresponding graph node passes.
> Canonical milestones are M0–M5. M5 is optional domain promotion and never blocks the engineering target.
> External-gate tasks are fail-closed: an AI agent may validate supplied evidence but must never fabricate approval, hardware, representative data, gold truth, human review, or release signoff.

## Execution rules

- Select the lowest checklist ID whose dependencies are all `passed` and whose applicable external gates are satisfied.
- Run focused tests first, then affected regression, static/type/schema checks, `validate-evidence`, and `validate-state` as declared.
- A prose summary is not evidence. Each task writes `evidence/<run-id>/<task-id>/evidence.json` and records exact hashes and command outcomes.
- Never skip/xfail a mandatory test, weaken a threshold, hide a retry, overwrite accepted data, or edit outside `owned_paths`.
- After any graph/checklist change, run `validate-contracts`, checklist/graph parity, dependency existence, and DAG cycle checks.
- P00 creates one `sv-<UTC-YYYYMMDDTHHMMSSZ>-<8 lowercase hex>` run ID, persists it in `evidence/execution-state.json`, and exports the identical value as `SEG_RUN_ID`; resumed runs reload it instead of generating another ID.
- For each post-bootstrap task, the controller exports its exact graph ID as `SEG_TASK_ID` and runs listed commands in order. Immediately before the first repository validator it writes provisional task evidence and proposed state/checkpoint; after listed commands it refreshes those artifacts and runs the inherited `validate-contracts`, task `validate-evidence`, and `validate-state` commands. All must exit zero before `passed`.
- `owned_paths` governs implementation writes. Only the controller may additionally update `openspec/changes/build-segvision-v1/tasks.md` and `evidence/execution-state.json`, atomically and solely for checkbox/state bookkeeping; these two paths are the frozen `execution_contract.controller_managed_paths` exception and do not grant implementation code broader write scope.
- The canonical source fingerprint excludes `.venv/`, `evidence/`, `dist/`, `build/`, and tool caches, normalizes only `tasks.md` checkbox markers to unchecked, and binds model/release artifacts through their own manifests. A checkpoint is reused from unchanged contract, dependency-checkpoint, declared required-input, and owned-output hashes; disjoint later outputs and controller bookkeeping alone do not invalidate it.
- A `verdict` command is legal only when contract validation, full-run evidence validation, and state validation appear earlier in that same task's command list and all exited zero.
- `P00`, `SCAFFOLD`, `VALIDATE-CONTRACTS`, `VALIDATE-EVIDENCE`, and `VALIDATE-STATE` are the only bootstrap exceptions because they create those validators in dependency order. `VALIDATE-STATE` must prove all three validators together; every later task has it as a transitive dependency.
- After `SCAFFOLD`, each run prepends repository `.venv\Scripts` to `PATH` and verifies `sys.executable`, CPython 3.11, and 64-bit pointer width before interpreting any listed bare `python` command.

## M0 — Governance and project scaffold

- [x] 0.1 `P00` — Record read-only repository, toolchain, hardware, and dirty-worktree preflight before mutation
  - **External gate:** `false`
  - **Dependencies:** none
  - **Requirement refs:** `AUT-R001`, `AUT-R005`, `AUT-R006`, `AUT-R016`
  - **E2E refs:** none
  - **Owned paths:** `evidence/preflight/`, `evidence/execution-state.json`, `evidence/<run-id>/P00/`
  - **Required inputs:** `AGENTS.md`, `PRD.md`, `docs/final-development-recommendation.md`, `openspec/changes/build-segvision-v1/`
  - **Expected outputs:** `Preflight inventory with source/file-tree hash, dirty paths, Python, OS, CPU, RAM, and tool versions`, `Initial execution-state document with immutable canonical run_id also exported as SEG_RUN_ID`
  - **Exact commands:**
    1. `openspec validate build-segvision-v1 --strict --no-interactive`
    2. `python --version`
    3. `openspec --version`
  - **Required evidence:** `Schema-valid evidence/<run-id>/P00/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Preflight is captured before any implementation write and identifies every pre-existing path without hiding, resetting, or overwriting it
    - run_id matches sv-<UTC-YYYYMMDDTHHMMSSZ>-<8 lowercase hex>, is persisted once, and equals SEG_RUN_ID
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Leave the repository unchanged and emit a blocker only for an overlapping externally owned change that cannot be composed.
  - **Rollback boundary:** Revert only P00 owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 0.2 `SCAFFOLD` — Create the locked CPython 3.11 package, test, benchmark, model, and evidence scaffold
  - **External gate:** `false`
  - **Dependencies:** `P00`
  - **Requirement refs:** `OFR-R001`, `OFR-R003`, `OFR-R004`, `PST-R001`
  - **E2E refs:** `PKG-INSTALL`
  - **Owned paths:** `pyproject.toml`, `requirements/`, `src/segvision/`, `tests/`, `benchmarks/`, `models/`, `.venv/`, `evidence/.gitkeep`, `.gitignore`, `evidence/<run-id>/SCAFFOLD/`
  - **Required inputs:** `P00 checkpoint`, `CPython 3.11 x64`, `design.md package layout`
  - **Expected outputs:** `Importable src/segvision package skeleton`, `Exact development and runtime lock inputs`, `Unit/integration/e2e/gui test directories`
  - **Exact commands:**
    1. `py -3.11 -m venv .venv`
    2. `.venv\Scripts\python.exe -c "import struct, sys; assert sys.version_info[:2] == (3, 11) and struct.calcsize('P') == 8"`
    3. `.venv\Scripts\python.exe -m pip install --require-hashes -r requirements/dev.lock`
    4. `.venv\Scripts\python.exe -m pytest tests/unit/test_import_contract.py -q`
  - **Required evidence:** `Schema-valid evidence/<run-id>/SCAFFOLD/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Importing segvision performs no GUI initialization, model load, filesystem write, download, or hidden global-session creation
    - The locked dependency plan is exact and CPU-only
    - Every later bare python command resolves to the locked .venv\Scripts\python.exe and records sys.executable
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Use a clean isolated virtual environment and reviewed compatible pins; do not globally unpin dependencies.
  - **Rollback boundary:** Revert only SCAFFOLD owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 0.3 `VALIDATE-CONTRACTS` — Implement validate-contracts for every normative JSON instance, schema, stable requirement ID, E2E ID, and traceability edge
  - **External gate:** `false`
  - **Dependencies:** `SCAFFOLD`
  - **Requirement refs:** `AUT-R003`, `AUT-R008`, `AUT-R018`, `AOB-R004`, `AOB-R015`, `AOB-R018`
  - **E2E refs:** `GOV-INCOMPLETE`, `GOV-OWNERSHIP`
  - **Owned paths:** `src/segvision/acceptance/__init__.py`, `src/segvision/acceptance/__main__.py`, `src/segvision/acceptance/contracts.py`, `tests/unit/test_validate_contracts.py`, `evidence/<run-id>/VALIDATE-CONTRACTS/`
  - **Required inputs:** `All acceptance/*.schema.json`, `All normative acceptance JSON instances`, `All specs/*/spec.md`, `acceptance/traceability.json`, `acceptance/e2e-cases.json`
  - **Expected outputs:** `validate-contracts CLI`, `Contract-discovery and cross-reference validator`, `Positive and mutation-negative contract tests`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_validate_contracts.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
  - **Required evidence:** `Schema-valid evidence/<run-id>/VALIDATE-CONTRACTS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Every normative instance validates against its schema
    - Requirement IDs, scenario IDs, planned tests, and existing E2E IDs are unique and resolve bidirectionally
    - Every E2E case exact test_target file is owned by a task that references that case, and a declared task command runs that exact node or its file
    - Unknown, duplicate, missing, stale, or malformed references produce non-zero exit
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep invalid contracts rejected and report exact JSON pointer/Markdown source; never relax a schema to obtain green status.
  - **Rollback boundary:** Revert only VALIDATE-CONTRACTS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 0.4 `VALIDATE-EVIDENCE` — Implement validate-evidence with hash, command, artifact, retry, redaction, and required-file consistency checks
  - **External gate:** `false`
  - **Dependencies:** `VALIDATE-CONTRACTS`
  - **Requirement refs:** `AUT-R009`, `AUT-R010`, `AUT-R011`, `AUT-R018`, `AOB-R015`, `AOB-R018`
  - **E2E refs:** `GOV-EVIDENCE`
  - **Owned paths:** `src/segvision/acceptance/evidence.py`, `tests/unit/test_validate_evidence.py`, `tests/fixtures/governance/evidence/`, `evidence/<run-id>/VALIDATE-EVIDENCE/`
  - **Required inputs:** `acceptance/evidence.schema.json`, `acceptance/run-manifest.schema.json`, `acceptance/scenario-results.schema.json`, `acceptance/checkpoint.schema.json`
  - **Expected outputs:** `validate-evidence CLI`, `Valid and adversarial evidence fixtures`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_validate_evidence.py -q`
    2. `python -m segvision.acceptance validate-evidence --evidence tests/fixtures/governance/evidence/valid`
  - **Required evidence:** `Schema-valid evidence/<run-id>/VALIDATE-EVIDENCE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Valid evidence passes reproducibly
    - Missing files, hash mismatch, non-zero required command, hidden retry, secret leakage, or inconsistent source identity fails with non-zero exit
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve failed evidence immutably and emit exact inconsistencies; never infer omitted success.
  - **Rollback boundary:** Revert only VALIDATE-EVIDENCE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 0.5 `VALIDATE-STATE` — Implement validate-state for task/checklist parity, task state transitions, dependency readiness, checkpoint reuse, and DAG acyclicity
  - **External gate:** `false`
  - **Dependencies:** `VALIDATE-EVIDENCE`
  - **Requirement refs:** `AUT-R002`, `AUT-R003`, `AUT-R004`, `AUT-R010`, `AUT-R014`, `AUT-R020`, `AUT-R021`, `AUT-R022`
  - **E2E refs:** `GOV-DAG`, `GOV-RETRY`, `GOV-BLOCK-CONTINUE`, `GOV-RESUME`, `GOV-OWNERSHIP`
  - **Owned paths:** `src/segvision/acceptance/state.py`, `tests/unit/test_validate_state.py`, `tests/fixtures/governance/state/`, `evidence/<run-id>/VALIDATE-STATE/`
  - **Required inputs:** `acceptance/task-graph.schema.json`, `acceptance/execution-state.schema.json`, `acceptance/blocker.schema.json`, `acceptance/checkpoint.schema.json`, `tasks.md`, `acceptance/task-graph.json`
  - **Expected outputs:** `validate-state CLI`, `DAG, transition, blocker, and checkpoint negative fixtures`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_validate_state.py -q`
    2. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state tests/fixtures/governance/state/valid.json`
    3. `python -m segvision.acceptance validate-contracts --change build-segvision-v1`
    4. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID`
    5. `python -m segvision.acceptance validate-state --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/VALIDATE-STATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Checklist IDs and task IDs agree exactly
    - Every dependency exists and the graph is acyclic
    - Only passed dependencies unlock work and input-hash drift invalidates the affected checkpoint and dependents
    - Every post-bootstrap task inherits the frozen pre-pass validators and every verdict command has successful full-run validators earlier in its command list
    - The three repository validators jointly accept every bootstrap contract, task evidence record, checkpoint, and the proposed execution state
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Retain the last valid execution state and reject the transition; do not rewrite task history.
  - **Rollback boundary:** Revert only VALIDATE-STATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 0.6 `GOV-META-E2E` — Implement governance meta E2E proving fail-closed contracts, evidence, state, retry, blocker, and resume behavior
  - **External gate:** `false`
  - **Dependencies:** `VALIDATE-STATE`
  - **Requirement refs:** `AUT-R002`, `AUT-R003`, `AUT-R004`, `AUT-R009`, `AUT-R010`, `AUT-R011`, `AUT-R012`, `AUT-R018`, `AUT-R020`, `AUT-R021`, `AUT-R022`, `AOB-R015`, `AOB-R018`
  - **E2E refs:** `GOV-DAG`, `GOV-INCOMPLETE`, `GOV-RETRY`, `GOV-BLOCK-CONTINUE`, `GOV-RESUME`, `GOV-OWNERSHIP`, `GOV-EVIDENCE`, `GOV-PROHIBITIONS`
  - **Owned paths:** `tests/governance/test_autonomous_controller.py`, `tests/fixtures/governance/meta/`, `evidence/<run-id>/GOV-META-E2E/`
  - **Required inputs:** `validate-contracts CLI`, `validate-evidence CLI`, `validate-state CLI`, `Governance schemas and adversarial fixtures`
  - **Expected outputs:** `Governance meta E2E suite covering malformed contracts, evidence tampering, cycles, illegal transitions, incomplete blockers, and resume invalidation`
  - **Exact commands:**
    1. `python -m pytest tests/governance/test_autonomous_controller.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GOV-META-E2E`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GOV-META-E2E/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All positive governance flows pass
    - Every prohibited mutation or incomplete proof fails non-zero without corrupting the prior valid state
    - Blocked external task leaves an independent task runnable
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the last schema-valid state and evidence bundle; isolate the failing governance fixture.
  - **Rollback boundary:** Revert only GOV-META-E2E owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 0.7 `POLICY-CONTRACTS` — Implement immutable annotation-policy, acceptance-profile, and pending-external-manifest loaders
  - **External gate:** `false`
  - **Dependencies:** `VALIDATE-STATE`
  - **Requirement refs:** `SES-R002`, `AOB-R002`, `AOB-R013`, `AOB-R017`, `OFR-R005`, `OFR-R010`, `OFR-R015`, `AUT-R013`, `AUT-R024`
  - **E2E refs:** `TIME-BOUNDARY`, `QUALITY-DOMAIN`, `PKG-COMPLIANCE`
  - **Owned paths:** `src/segvision/core/policy.py`, `src/segvision/acceptance/profile.py`, `src/segvision/acceptance/external_gates.py`, `tests/unit/test_policy_contracts.py`, `evidence/<run-id>/POLICY-CONTRACTS/`
  - **Required inputs:** `acceptance/default-annotation-policy.json`, `acceptance/acceptance-profile.json`, `acceptance/external-gates/*.pending.json`
  - **Expected outputs:** `Immutable typed policy/profile values`, `Fail-closed pending-external-gate loader`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_policy_contracts.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/POLICY-CONTRACTS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/POLICY-CONTRACTS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Frozen IDs, thresholds, operators, and minimum sample counts load exactly
    - Per-image hidden overrides and pending manifests presented as approval are rejected
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Retain normative defaults and leave each absent external authority pending.
  - **Rollback boundary:** Revert only POLICY-CONTRACTS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 0.8 `M0-GATE` — Prove governance, contracts, evidence, state, policy, scaffold, and OpenSpec readiness
  - **External gate:** `false`
  - **Dependencies:** `GOV-META-E2E`, `POLICY-CONTRACTS`
  - **Requirement refs:** `AUT-R001`, `AUT-R002`, `AUT-R003`, `AUT-R004`, `AUT-R005`, `AUT-R006`, `AUT-R007`, `AUT-R008`, `AUT-R009`, `AUT-R010`, `AUT-R011`, `AUT-R014`, `AUT-R015`, `AUT-R016`, `AUT-R018`, `AUT-R020`, `AUT-R021`, `AUT-R022`
  - **E2E refs:** `GOV-DAG`, `GOV-INCOMPLETE`, `GOV-RETRY`, `GOV-BLOCK-CONTINUE`, `GOV-RESUME`, `GOV-OWNERSHIP`, `GOV-EVIDENCE`, `GOV-PROHIBITIONS`
  - **Owned paths:** `evidence/<run-id>/M0-GATE/`
  - **Required inputs:** `All M0 task checkpoints`, `Exact lock hash`, `OpenSpec change`
  - **Expected outputs:** `M0 evidence bundle and checkpoint`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_import_contract.py tests/unit/test_validate_contracts.py tests/unit/test_validate_evidence.py tests/unit/test_validate_state.py tests/unit/test_policy_contracts.py tests/governance/test_autonomous_controller.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `openspec validate build-segvision-v1 --strict --no-interactive`
    4. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/M0-GATE`
    5. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/M0-GATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All governance and scaffold gates pass with zero skips
    - M0 checkpoint binds source tree, OpenSpec, lock, policy, profile, graph, and schema hashes
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Do not start a task with an invalid graph or contract; preserve valid preflight and report the exact defect.
  - **Rollback boundary:** Revert only M0-GATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

## M1 — Pure core and deterministic fake backend

- [x] 1.1 `CORE-TYPES` — Define immutable public types, JSON-safe outcomes, warning records, and typed errors
  - **External gate:** `false`
  - **Dependencies:** `M0-GATE`
  - **Requirement refs:** `SES-R003`, `SES-R013`, `MPE-R001`
  - **E2E refs:** `ROI-INVALID`, `REF-UNSUPPORTED`, `MAN-REFINE`
  - **Owned paths:** `src/segvision/core/types.py`, `src/segvision/core/errors.py`, `tests/unit/test_core_types.py`, `evidence/<run-id>/CORE-TYPES/`
  - **Required inputs:** `Policy/profile types`, `Backend and session public-contract requirements`
  - **Expected outputs:** `Immutable type and error modules`, `Serialization and foreign-identity tests`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_core_types.py -q`
    2. `python -m mypy src/segvision/core/types.py src/segvision/core/errors.py`
    3. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    4. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/CORE-TYPES`
    5. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/CORE-TYPES/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Required errors are distinguishable and JSON-facing values canonicalize deterministically
    - No provider tensor, GUI type, or filesystem path leaks through the core API
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep errors typed and recoverable; do not collapse failures into generic success or warnings.
  - **Rollback boundary:** Revert only CORE-TYPES owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.2 `BACKEND-FAKE` — Define the narrow interactive backend protocol and deterministic scripted fake with call ledger
  - **External gate:** `false`
  - **Dependencies:** `CORE-TYPES`
  - **Requirement refs:** `MPE-R001`, `MPE-R003`, `MPE-R005`
  - **E2E refs:** `HP-01`, `REF-01`, `CV-DIRECT`
  - **Owned paths:** `src/segvision/providers/base.py`, `src/segvision/providers/fake.py`, `tests/unit/test_backend_protocol.py`, `evidence/<run-id>/BACKEND-FAKE/`
  - **Required inputs:** `Core types`, `Backend capability contract`, `Deterministic mask fixtures`
  - **Expected outputs:** `Backend protocol`, `Scripted fake backend`, `Encode/decode/mask-prompt/release ledger`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_backend_protocol.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/BACKEND-FAKE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/BACKEND-FAKE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Capability validation is fail-closed
    - Fake calls and results are deterministic and inputs remain byte-identical
    - Opaque state never reaches GUI-facing values
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Use the fake backend for independent work when real artifacts are unavailable.
  - **Rollback boundary:** Revert only BACKEND-FAKE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.3 `ROI-CONTEXT` — Implement half-open ROI validation, frozen padding, outward rounding, and image-bound clamping
  - **External gate:** `false`
  - **Dependencies:** `CORE-TYPES`
  - **Requirement refs:** `ROI-R001`, `ROI-R002`, `ROI-R003`
  - **E2E refs:** `ROI-PAD`, `ROI-CLAMP`, `ROI-INVALID`
  - **Owned paths:** `src/segvision/core/geometry.py`, `tests/unit/test_roi_context.py`, `evidence/<run-id>/ROI-CONTEXT/`
  - **Required inputs:** `Source image shape`, `Full-image ROI`, `Frozen 0.10 padding`
  - **Expected outputs:** `Immutable crop context with distinct user_roi_full and crop_rect_full`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_roi_context.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/ROI-CONTEXT`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/ROI-CONTEXT/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - One-pixel and border ROIs match exact expected coordinates
    - Invalid, non-finite, reversed, empty, or out-of-image public ROIs fail without silent clipping
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Reject invalid ROI and leave the current revision unchanged.
  - **Rollback boundary:** Revert only ROI-CONTEXT owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.4 `ROI-TRANSFORMS` — Implement crop extraction, full/crop point transforms, round trips, and backend-owned model transforms
  - **External gate:** `false`
  - **Dependencies:** `ROI-CONTEXT`
  - **Requirement refs:** `ROI-R004`, `ROI-R005`, `ROI-R006`
  - **E2E refs:** `CAND-POINT`, `MOUSE-FG-BG`
  - **Owned paths:** `src/segvision/core/geometry.py`, `tests/unit/test_roi_transforms.py`, `evidence/<run-id>/ROI-TRANSFORMS/`
  - **Required inputs:** `Crop context`, `Source RGB pixels`, `Integer full-image point fixtures`
  - **Expected outputs:** `Crop pixels and exact public coordinate transforms`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_roi_transforms.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/ROI-TRANSFORMS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/ROI-TRANSFORMS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Crop bytes equal the exact source slice
    - Valid public round trips have at most one-pixel error
    - Fractional/non-finite/outside points fail and model-space details stay backend-owned
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Reject the prompt without calling the backend when public point validation fails.
  - **Rollback boundary:** Revert only ROI-TRANSFORMS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.5 `ROI-COMMIT` — Implement crop-mask validation, full-image reconstruction, work-crop risk, source truncation, and expansion geometry
  - **External gate:** `false`
  - **Dependencies:** `ROI-TRANSFORMS`
  - **Requirement refs:** `ROI-R007`, `ROI-R008`, `ROI-R009`, `ROI-R010`, `ROI-R011`
  - **E2E refs:** `HP-01`, `CAND-EDGE`, `ROI-EDGE-SEM`, `ROI-EXPAND`, `QUALITY-SYNTH`
  - **Owned paths:** `src/segvision/core/geometry.py`, `tests/unit/test_roi_commit.py`, `evidence/<run-id>/ROI-COMMIT/`
  - **Required inputs:** `Crop context`, `Crop-resolution boolean masks`
  - **Expected outputs:** `Full-image boolean mask`, `Separate work-crop and source-boundary provenance`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_roi_commit.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/ROI-COMMIT`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/ROI-COMMIT/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Mask reconstructs at the exact crop offset with false pixels outside
    - Work-crop and source-image edge semantics stay distinct
    - Expansion creates new geometry and never stretches an old mask
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the old revision current if expansion validation fails.
  - **Rollback boundary:** Revert only ROI-COMMIT owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.6 `RECIPE-SCHEMA` — Implement immutable v1 CV recipe schema, defaults, strict validation, class binding, and canonical hash
  - **External gate:** `false`
  - **Dependencies:** `CORE-TYPES`
  - **Requirement refs:** `CVR-R001`, `CVR-R002`, `CVR-R003`, `CVR-R004`, `CVR-R008`, `CVR-R015`
  - **E2E refs:** `CV-ROUNDTRIP`, `CV-DETERMINISM`, `CV-INVALID`
  - **Owned paths:** `src/segvision/core/recipe.py`, `tests/unit/test_recipe_schema.py`, `evidence/<run-id>/RECIPE-SCHEMA/`
  - **Required inputs:** `acceptance/cv-recipe.schema.json`, `Frozen recipe defaults`
  - **Expected outputs:** `Typed recipe parser/serializer`, `Canonical JSON and SHA-256 identity`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_recipe_schema.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/RECIPE-SCHEMA`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/RECIPE-SCHEMA/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Equivalent JSON yields identical canonical bytes and hashes
    - Unsupported versions, algorithms, bridges, ranges, parameters, and class mismatch fail exactly
    - Serialization performs no I/O
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Reject the recipe and leave CV disabled; do not infer thresholds or tune per image.
  - **Rollback boundary:** Revert only RECIPE-SCHEMA owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.7 `SESSION-LIFECYCLE` — Implement in-memory session start, immutable inputs, policy binding, revision ownership, and state release
  - **External gate:** `false`
  - **Dependencies:** `BACKEND-FAKE`, `ROI-COMMIT`, `RECIPE-SCHEMA`
  - **Requirement refs:** `SES-R001`, `SES-R002`, `SES-R003`, `SES-R004`, `MPE-R005`
  - **E2E refs:** `HP-01`, `ROI-STALE-P`, `ROI-STALE-R`, `ROI-EXPAND`
  - **Owned paths:** `src/segvision/core/api.py`, `tests/unit/test_session_lifecycle.py`, `evidence/<run-id>/SESSION-LIFECYCLE/`
  - **Required inputs:** `RGB image`, `Image/class IDs`, `Crop context`, `Optional parsed recipe`, `Backend protocol`
  - **Expected outputs:** `AnnotationSession revision 1`, `Revision update and stale-state invalidation APIs`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_session_lifecycle.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/SESSION-LIFECYCLE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/SESSION-LIFECYCLE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Session owns immutable image/model/candidate/prompt state
    - ROI update increments once, preserves timer origin, invalidates prior handles, and releases old encoded state
    - Core causes no file/network/GUI side effect
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve the active session and expose a typed recoverable error.
  - **Rollback boundary:** Revert only SESSION-LIFECYCLE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.8 `CANDIDATE-VALIDATE` — Implement frozen candidate policy, hard validation, prompt constraints, and deterministic deduplication
  - **External gate:** `false`
  - **Dependencies:** `SESSION-LIFECYCLE`
  - **Requirement refs:** `MPE-R007`, `MPE-R008`, `MPE-R009`, `MPE-R018`
  - **E2E refs:** `CAND-00`, `CAND-CAP`, `CAND-POINT`, `CAND-EDGE`
  - **Owned paths:** `src/segvision/core/candidate_policy.py`, `tests/unit/test_candidate_validation.py`, `evidence/<run-id>/CANDIDATE-VALIDATE/`
  - **Required inputs:** `Decoded mask variants`, `Candidate policy`, `Human prompt history`
  - **Expected outputs:** `Validated and deduplicated candidates with removal diagnostics`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_candidate_validation.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/CANDIDATE-VALIDATE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/CANDIDATE-VALIDATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Empty, near-full, malformed, and point-violating masks are removed at exact boundaries
    - Crop-edge contact remains a warning
    - All-unusable output returns honest zero candidates
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Return zero candidates with diagnostics and retain manual/review fallback.
  - **Rollback boundary:** Revert only CANDIDATE-VALIDATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.9 `CANDIDATE-ALLOCATE` — Implement provider-local ranking, provenance, capability matrix, and deterministic three-slot allocation
  - **External gate:** `false`
  - **Dependencies:** `CANDIDATE-VALIDATE`
  - **Requirement refs:** `SES-R005`, `MPE-R010`, `MPE-R013`, `MPE-R016`
  - **E2E refs:** `CAND-01`, `CAND-02`, `CAND-03`, `CAND-CAP`
  - **Owned paths:** `src/segvision/core/candidate_policy.py`, `tests/unit/test_candidate_allocation.py`, `evidence/<run-id>/CANDIDATE-ALLOCATE/`
  - **Required inputs:** `Validated native, safe-grid, and sam_cv candidates`, `Backend and recipe identities`
  - **Expected outputs:** `Zero-to-three public candidates with stable ordering, provenance, and immutable capabilities`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_candidate_allocation.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/CANDIDATE-ALLOCATE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/CANDIDATE-ALLOCATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - No filler or duplicate display slots are created
    - Slot and tie-break rules are exact
    - Cross-provider values are never presented as unified confidence
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Show only surviving real candidates and keep manual/review available.
  - **Rollback boundary:** Revert only CANDIDATE-ALLOCATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.10 `SAFE-GRID` — Implement bounded stable-intersection safe-grid probing with decoder-only call accounting
  - **External gate:** `false`
  - **Dependencies:** `CANDIDATE-ALLOCATE`
  - **Requirement refs:** `MPE-R004`, `MPE-R006`, `MPE-R011`
  - **E2E refs:** `GRID-01`, `GRID-02`
  - **Owned paths:** `src/segvision/core/candidate_policy.py`, `tests/unit/test_safe_grid.py`, `evidence/<run-id>/SAFE-GRID/`
  - **Required inputs:** `At least two validated native masks`, `Mapped user ROI`, `Encoded state`
  - **Expected outputs:** `At most one safe-grid candidate and complete prompt/call provenance`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_safe_grid.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/SAFE-GRID`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/SAFE-GRID/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - At most two separated frozen-grid points survive the exact safe margin
    - Unsafe or thin intersections produce no probe
    - No extra encode and at most one extra decode occurs
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Skip safe-grid probing; never reduce the safety margin or manufacture points.
  - **Rollback boundary:** Revert only SAFE-GRID owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.11 `UNCERTAINTY-FUSION` — Implement disagreement, work-crop risk, and strict opt-in exactly-three majority fusion
  - **External gate:** `false`
  - **Dependencies:** `CANDIDATE-ALLOCATE`
  - **Requirement refs:** `MPE-R014`, `MPE-R017`
  - **E2E refs:** `CAND-UNCERTAINTY`, `FUSE-01`, `FUSE-02`
  - **Owned paths:** `src/segvision/core/mask_ops.py`, `tests/unit/test_uncertainty_fusion.py`, `evidence/<run-id>/UNCERTAINTY-FUSION/`
  - **Required inputs:** `Zero-to-three compatible candidate masks`
  - **Expected outputs:** `Separate disagreement/risk masks`, `Vote-count majority result and one-vote uncertainty`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_uncertainty_fusion.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/UNCERTAINTY-FUSION`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/UNCERTAINTY-FUSION/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Disagreement equals union minus intersection and edge risk is independent
    - Fusion requires exactly three same-revision/same-crop masks and uses vote_count >= 2
    - No OR or two-mask fallback exists
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep fusion disabled and retain the selected candidate unchanged.
  - **Rollback boundary:** Revert only UNCERTAINTY-FUSION owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.12 `POINT-REFINE` — Implement previous-state single-mask point refinement and automatic-guidance invalidation
  - **External gate:** `false`
  - **Dependencies:** `SAFE-GRID`, `UNCERTAINTY-FUSION`
  - **Requirement refs:** `SES-R006`, `SES-R007`, `MPE-R004`, `MPE-R015`
  - **E2E refs:** `REF-01`, `REF-02`, `REF-03`, `VAL-POINT`
  - **Owned paths:** `src/segvision/core/api.py`, `tests/integration/test_point_refine.py`, `evidence/<run-id>/POINT-REFINE/`
  - **Required inputs:** `Selected current SAM candidate`, `Original box`, `Ordered human points`, `Opaque previous state`
  - **Expected outputs:** `At most one refined candidate per point request`, `Prompt and call ledger provenance`
  - **Exact commands:**
    1. `python -m pytest tests/integration/test_point_refine.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/POINT-REFINE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/POINT-REFINE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Refinement uses selected immediate previous state, original box, and all human points
    - First human point removes auto-grid/fusion context
    - Each successful point adds one decode and zero encodes
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the prior selected candidate available and report typed decode failure.
  - **Rollback boundary:** Revert only POINT-REFINE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.13 `LOCAL-OPS` — Implement copy-on-write brush, erase, one-pixel grow/shrink, and boundary-safe hole fill
  - **External gate:** `false`
  - **Dependencies:** `ROI-COMMIT`, `UNCERTAINTY-FUSION`
  - **Requirement refs:** `SES-R008`
  - **E2E refs:** `EDIT-GROW`, `EDIT-FILL`, `KEY-LOCAL`
  - **Owned paths:** `src/segvision/core/mask_ops.py`, `tests/unit/test_local_ops.py`, `evidence/<run-id>/LOCAL-OPS/`
  - **Required inputs:** `Crop-resolution boolean mask`, `Local operation parameters`
  - **Expected outputs:** `Deterministic edited mask and operation record`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_local_ops.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/LOCAL-OPS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/LOCAL-OPS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Inputs remain unchanged
    - Grow/shrink use a frozen 3x3 8-connected kernel
    - Hole fill preserves crop-boundary-connected background
    - Golden mask hashes match
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Reject the invalid operation and preserve the current mask.
  - **Rollback boundary:** Revert only LOCAL-OPS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.14 `EDIT-UNDO-MANUAL` — Implement terminal local-edit model lock, manual-empty fallback, ancestry, and exact session undo
  - **External gate:** `false`
  - **Dependencies:** `POINT-REFINE`, `LOCAL-OPS`
  - **Requirement refs:** `SES-R008`, `SES-R009`, `SES-R010`
  - **E2E refs:** `EDIT-01`, `EDIT-02`, `MAN-EMPTY`, `MAN-ERASE`, `MAN-BACKEND-FAIL`, `MAN-REFINE`
  - **Owned paths:** `src/segvision/core/api.py`, `tests/integration/test_edit_undo_manual.py`, `evidence/<run-id>/EDIT-UNDO-MANUAL/`
  - **Required inputs:** `Current candidate or zero-candidate proposal`, `Local operation functions`, `Session checkpoints`
  - **Expected outputs:** `manual_empty/manual_edit candidates`, `Exact undo checkpoints and capability restoration`
  - **Exact commands:**
    1. `python -m pytest tests/integration/test_edit_undo_manual.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/EDIT-UNDO-MANUAL`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/EDIT-UNDO-MANUAL/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - First edit locks out model mutation and keeps parent provenance
    - Manual empty requires no model/CV call and cannot commit unchanged
    - Undo restores exact mask, prompts, capabilities, previous state, and revision without decoding
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve the last exact checkpoint and keep Needs Review available.
  - **Rollback boundary:** Revert only EDIT-UNDO-MANUAL owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.15 `COMMIT-REVIEW` — Implement explicit human Accept validation, in-memory commit, warnings acknowledgement, and Needs Review
  - **External gate:** `false`
  - **Dependencies:** `EDIT-UNDO-MANUAL`
  - **Requirement refs:** `SES-R011`, `SES-R012`, `SES-R013`
  - **E2E refs:** `VAL-POINT`, `REVIEW-STATES`, `REVIEW-EMPTY`, `TIME-INVALID`
  - **Owned paths:** `src/segvision/core/api.py`, `tests/integration/test_commit_review.py`, `evidence/<run-id>/COMMIT-REVIEW/`
  - **Required inputs:** `Current candidate`, `Acceptance confirmation and warning acknowledgements`, `Session event state`
  - **Expected outputs:** `CommitResult with full-image mask and JSON-safe provenance`, `ReviewResult with training_eligible false`
  - **Exact commands:**
    1. `python -m pytest tests/integration/test_commit_review.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/COMMIT-REVIEW`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/COMMIT-REVIEW/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Only explicit human confirmation commits
    - Empty, stale, wrong-shape, point-violating, or unacknowledged edge candidates fail
    - Every active non-accepted state permits explicit Review and no core file write occurs
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the session editable/reviewable and return an exact validation reason.
  - **Rollback boundary:** Revert only COMMIT-REVIEW owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.16 `CORE-SCENARIOS` — Implement generated scenario-level tests for every M1 requirement and traceability target
  - **External gate:** `false`
  - **Dependencies:** `COMMIT-REVIEW`
  - **Requirement refs:** `AUT-R008`, `AOB-R004`, `SES-R001`, `SES-R013`, `ROI-R001`, `ROI-R011`, `MPE-R001`, `MPE-R018`, `CVR-R001`, `CVR-R005`
  - **E2E refs:** `HP-01`, `CAND-00`, `CAND-01`, `CAND-02`, `CAND-03`, `GRID-01`, `GRID-02`, `FUSE-01`, `FUSE-02`, `REF-01`, `EDIT-01`, `MAN-EMPTY`, `ROI-PAD`, `ROI-INVALID`
  - **Owned paths:** `tests/unit/test_annotation_session_scenarios.py`, `tests/unit/test_roi_geometry_scenarios.py`, `tests/unit/test_mask_proposal_engine_scenarios.py`, `tests/unit/test_fixed_cv_recipe_contract_scenarios.py`, `evidence/<run-id>/CORE-SCENARIOS/`
  - **Required inputs:** `acceptance/traceability.json`, `M1 implementation`, `Deterministic fake fixtures`
  - **Expected outputs:** `Executable planned-test targets for all M1 traceability entries`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_annotation_session_scenarios.py tests/unit/test_roi_geometry_scenarios.py tests/unit/test_mask_proposal_engine_scenarios.py tests/unit/test_fixed_cv_recipe_contract_scenarios.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/CORE-SCENARIOS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/CORE-SCENARIOS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Every planned M1 scenario target exists and passes
    - Scenario IDs map one-to-one to test IDs and requirement IDs
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep missing scenarios planned and fail the gate; never mark traceability covered by a different test silently.
  - **Rollback boundary:** Revert only CORE-SCENARIOS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 1.17 `M1-GATE` — Prove the complete pure headless core and fake-backend milestone
  - **External gate:** `false`
  - **Dependencies:** `CORE-SCENARIOS`
  - **Requirement refs:** `SES-R001`, `SES-R013`, `ROI-R001`, `ROI-R011`, `MPE-R001`, `MPE-R018`, `CVR-R001`, `CVR-R005`, `AUT-R008`
  - **E2E refs:** `HP-01`, `CAND-00`, `CAND-01`, `CAND-02`, `CAND-03`, `GRID-01`, `GRID-02`, `FUSE-01`, `FUSE-02`, `REF-01`, `REF-02`, `REF-03`, `EDIT-01`, `EDIT-02`, `MAN-EMPTY`, `ROI-PAD`, `ROI-CLAMP`, `ROI-INVALID`
  - **Owned paths:** `evidence/<run-id>/M1-GATE/`
  - **Required inputs:** `All M1 checkpoints`, `M0 contract/evidence/state validators`
  - **Expected outputs:** `M1 milestone evidence and checkpoint`
  - **Exact commands:**
    1. `python -m pytest tests/unit tests/integration -q`
    2. `python -m mypy src/segvision/core src/segvision/providers/base.py src/segvision/providers/fake.py`
    3. `python -m ruff check src tests`
    4. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/M1-GATE`
    5. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    6. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/M1-GATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All pure-core and fake-backend tests pass with zero skips
    - Core imports no GUI or persistence adapter and performs no output I/O
    - Checkpoint binds exact call-ledger and mask hashes
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve the passing M0 checkpoint and isolate the failing M1 task.
  - **Rollback boundary:** Revert only M1-GATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

## M2 — Approved MobileSAM TinyViT CPU backend

- [x] 2.1 `MODEL-MANIFEST` — Implement fail-closed model, artifact, dependency-license, and prohibited-source manifest validation
  - **External gate:** `false`
  - **Dependencies:** `M1-GATE`
  - **Requirement refs:** `MPE-R002`, `OFR-R005`, `OFR-R006`, `OFR-R007`, `AUT-R013`
  - **E2E refs:** `REAL-CHECKSUM`, `PKG-COMPLIANCE`
  - **Owned paths:** `models/manifest.json`, `src/segvision/providers/model_manifest.py`, `tests/unit/test_model_manifest.py`, `evidence/<run-id>/MODEL-MANIFEST/`
  - **Required inputs:** `acceptance/model-manifest.schema.json`, `external-gates/model-artifact-manifest.pending.json`
  - **Expected outputs:** `Model/artifact manifest validator with separate code and weight subjects`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_model_manifest.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/MODEL-MANIFEST`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/MODEL-MANIFEST/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Missing source, revision, hash, license, redistribution, or approval fails closed
    - EdgeSAM without written permission and unapproved GPL copies are excluded
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Leave the artifact excluded and record blocked_license; never infer permission.
  - **Rollback boundary:** Revert only MODEL-MANIFEST owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 2.2 `MODEL-ACQUIRE` — Implement official-source local acquisition, pre-deserialization checksum verification, and quarantine
  - **External gate:** `false`
  - **Dependencies:** `MODEL-MANIFEST`
  - **Requirement refs:** `MPE-R002`, `OFR-R008`, `AUT-R013`
  - **E2E refs:** `REAL-CHECKSUM`
  - **Owned paths:** `src/segvision/providers/acquire.py`, `tests/unit/test_model_acquire.py`, `evidence/<run-id>/MODEL-ACQUIRE/`
  - **Required inputs:** `Approved model manifest entry or pending entry for negative tests`, `Task-owned cache and quarantine roots`
  - **Expected outputs:** `Verified acquisition API and quarantine receipt`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_model_acquire.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/MODEL-ACQUIRE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/MODEL-ACQUIRE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Only the recorded official source is accepted
    - Hash mismatch is quarantined before deserialize
    - No unrecorded mirror, runtime download fallback, or unsafe load occurs
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep fake-backend work runnable and block only real-model consumers.
  - **Rollback boundary:** Revert only MODEL-ACQUIRE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 2.3 `MOBILE-ENCODE` — Implement MobileSAM TinyViT PyTorch CPU initialization, preprocessing, immutable encode, and state identity
  - **External gate:** `false`
  - **Dependencies:** `MODEL-ACQUIRE`, `BACKEND-FAKE`
  - **Requirement refs:** `MPE-R001`, `MPE-R002`, `MPE-R003`, `MPE-R005`
  - **E2E refs:** `REAL-REG`, `PKG-CPU`
  - **Owned paths:** `src/segvision/providers/mobile_sam_torch_cpu.py`, `tests/unit/test_mobile_encode_contract.py`, `evidence/<run-id>/MOBILE-ENCODE/`
  - **Required inputs:** `Backend protocol`, `Verified local artifact interface`, `Controlled model doubles`
  - **Expected outputs:** `CPU-only backend initialization and encoded-state implementation`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_mobile_encode_contract.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/MOBILE-ENCODE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/MOBILE-ENCODE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Contract tests prove CPU device, fixed backend-owned transforms, immutable inputs, complete identity, and explicit release
    - No network, CUDA, GUI, or process-global hidden session is required
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the adapter unavailable and continue with fake backend; do not switch to GPU/cloud.
  - **Rollback boundary:** Revert only MOBILE-ENCODE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 2.4 `MOBILE-DECODE` — Implement box multimask decode, binary mask-prompt conversion, previous-state refinement, and source-resolution masks
  - **External gate:** `false`
  - **Dependencies:** `MOBILE-ENCODE`
  - **Requirement refs:** `MPE-R004`, `MPE-R006`, `MPE-R012`, `MPE-R015`, `MPE-R016`
  - **E2E refs:** `REAL-REG`, `REF-01`, `CV-COARSE`
  - **Owned paths:** `src/segvision/providers/mobile_sam_torch_cpu.py`, `tests/unit/test_mobile_decode_contract.py`, `evidence/<run-id>/MOBILE-DECODE/`
  - **Required inputs:** `Encoded-state implementation`, `Mapped box/point prompts`, `Binary coarse masks`, `Controlled decoder doubles`
  - **Expected outputs:** `Native multimask, sam_cv, and refined backend results with opaque previous state`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_mobile_decode_contract.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/MOBILE-DECODE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/MOBILE-DECODE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Initial box-only decode requests exactly three
    - Mask prompt is converted exactly once and not converted to points
    - Refinement requests one output and no encode
    - Crop-resolution masks and provider-local metrics are owned
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the prior candidate and emit a typed backend diagnostic.
  - **Rollback boundary:** Revert only MOBILE-DECODE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 2.5 `MODEL-FIXTURES` — Create versioned real-backend fixtures, call ledgers, tolerances, and synthetic exact-quality references
  - **External gate:** `false`
  - **Dependencies:** `MOBILE-DECODE`, `VALIDATE-CONTRACTS`
  - **Requirement refs:** `AOB-R004`, `AOB-R012`, `MPE-R004`, `MPE-R015`
  - **E2E refs:** `REAL-REG`, `QUALITY-SYNTH`
  - **Owned paths:** `tests/fixtures/real_model/manifest.json`, `tests/fixtures/real_model/`, `tests/unit/test_real_fixture_manifest.py`, `evidence/<run-id>/MODEL-FIXTURES/`
  - **Required inputs:** `acceptance/fixture-manifest.schema.json`, `Approved fixture-source policy`, `Synthetic geometry fixtures`
  - **Expected outputs:** `Hash-pinned fixture manifest, expected mask hashes/tolerances, and expected call counts`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_real_fixture_manifest.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/MODEL-FIXTURES`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/MODEL-FIXTURES/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Fixture bytes, source, policy, expected outputs, tolerances, and hashes validate
    - Synthetic exact fixtures are explicitly marked non-domain evidence
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Reject changed or untraceable fixtures; do not widen tolerance to hide regression.
  - **Rollback boundary:** Revert only MODEL-FIXTURES owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [ ] 2.6 `X-MODEL` — Verify attributable approval and local availability of the pinned MobileSAM code and checkpoint
  - **External gate:** `true`
  - **Dependencies:** `MODEL-MANIFEST`
  - **Requirement refs:** `MPE-R002`, `OFR-R005`, `OFR-R006`, `OFR-R008`, `AUT-R013`, `AUT-R019`, `AUT-R020`
  - **E2E refs:** `REAL-REG`, `REAL-CHECKSUM`
  - **Owned paths:** `openspec/changes/build-segvision-v1/acceptance/external-gates/model-artifact-manifest.pending.json`, `evidence/external-gates/model/`, `evidence/<run-id>/X-MODEL/`
  - **Required inputs:** `Official source/revision`, `Checkpoint source and SHA-256`, `Code and weight terms`, `Attributable use and redistribution decision`
  - **Expected outputs:** `Approved, signed/attributable model-artifact manifest or schema-valid blocker`
  - **Exact commands:**
    1. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    2. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/X-MODEL`
  - **Required evidence:** `Schema-valid evidence/<run-id>/X-MODEL/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Approval fields change from pending only with attributable external evidence
    - Local checkpoint hash matches before deserialization
    - Absent authority produces blocked_license or blocked_external_input and does not stop independent M3/M4 code work
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 1 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the pending manifest unchanged, use fake backend for independent work, and emit one blocker.
  - **Rollback boundary:** Revert only X-MODEL owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Commercial-use or redistribution authority is absent; Official checkpoint remains unavailable after two verified source attempts; Checkpoint checksum mismatches; quarantine immediately

- [ ] 2.7 `REAL-BACKEND-REG` — Run pinned MobileSAM CPU functional regression for encode-once, multimask, mask-prompt, and refinement
  - **External gate:** `false`
  - **Dependencies:** `MODEL-FIXTURES`, `X-MODEL`
  - **Requirement refs:** `MPE-R002`, `MPE-R004`, `MPE-R006`, `MPE-R012`, `MPE-R015`, `AOB-R012`
  - **E2E refs:** `REAL-REG`, `REAL-CHECKSUM`, `QUALITY-SYNTH`
  - **Owned paths:** `tests/integration/test_real_backend.py`, `tests/e2e/test_mobile_sam_regression.py`, `evidence/<run-id>/REAL-BACKEND-REG/`
  - **Required inputs:** `Approved local checkpoint`, `MobileSAM adapter`, `Real-model fixture manifest`
  - **Expected outputs:** `Real-backend test results, model provenance, output hashes, and call ledger`
  - **Exact commands:**
    1. `python -m pytest tests/integration/test_real_backend.py tests/e2e/test_mobile_sam_regression.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/REAL-BACKEND-REG`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/REAL-BACKEND-REG/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Proposal encode count is one, cv_direct zero, and refinement encode delta zero
    - Fixture masks meet frozen tolerances
    - Model/checkpoint/runtime/preprocessing identities are complete
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve adapter contract tests and block the real gate; never select an unapproved backend.
  - **Rollback boundary:** Revert only REAL-BACKEND-REG owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 2.8 `M2-CODE` — Prove MobileSAM adapter and acquisition code independently of unavailable external approval
  - **External gate:** `false`
  - **Dependencies:** `MOBILE-DECODE`, `MODEL-FIXTURES`
  - **Requirement refs:** `AUT-R021`, `MPE-R001`, `MPE-R003`, `OFR-R008`
  - **E2E refs:** none
  - **Owned paths:** `evidence/<run-id>/M2-CODE/`
  - **Required inputs:** `M2 code checkpoints and controlled doubles`
  - **Expected outputs:** `M2 code-only checkpoint explicitly not claiming real-model acceptance`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_model_manifest.py tests/unit/test_model_acquire.py tests/unit/test_mobile_encode_contract.py tests/unit/test_mobile_decode_contract.py tests/unit/test_real_fixture_manifest.py -q`
    2. `python -m mypy src/segvision/providers`
    3. `python -m ruff check src/segvision/providers tests/unit`
    4. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    5. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/M2-CODE`
    6. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/M2-CODE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All code-testable adapter/acquisition requirements pass
    - Evidence explicitly records external model gate status and does not claim engineering acceptance
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Continue M3 runtime/GUI/persistence against the fake backend while X-MODEL is pending.
  - **Rollback boundary:** Revert only M2-CODE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [ ] 2.9 `M2-GATE` — Prove the approved real MobileSAM CPU backend milestone
  - **External gate:** `false`
  - **Dependencies:** `M2-CODE`, `REAL-BACKEND-REG`
  - **Requirement refs:** `MPE-R001`, `MPE-R002`, `MPE-R003`, `MPE-R004`, `MPE-R005`, `MPE-R006`, `MPE-R012`, `MPE-R015`, `MPE-R016`, `OFR-R005`, `OFR-R006`, `OFR-R008`
  - **E2E refs:** `REAL-REG`, `REAL-CHECKSUM`, `QUALITY-SYNTH`
  - **Owned paths:** `evidence/<run-id>/M2-GATE/`
  - **Required inputs:** `M2 code checkpoint`, `Approved external model gate`, `Real-backend regression evidence`
  - **Expected outputs:** `M2 milestone evidence and checkpoint`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_mobile_encode_contract.py tests/unit/test_mobile_decode_contract.py tests/integration/test_real_backend.py tests/e2e/test_mobile_sam_regression.py -q`
    2. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/M2-GATE`
    3. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/M2-GATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Approved checkpoint loads offline on CPU and every real-backend functional oracle passes
    - No license/checksum/model-identity blocker remains
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Retain M2-CODE as passing and mark only real-model and downstream engineering-release gates blocked.
  - **Rollback boundary:** Revert only M2-GATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

## M3 — Runtime, GUI, and persistence

- [x] 3.1 `RUNTIME-JOBS` — Implement bounded embedding cache, typed jobs/results, cancellation tokens, and CPU thread policy
  - **External gate:** `false`
  - **Dependencies:** `M2-CODE`, `SESSION-LIFECYCLE`
  - **Requirement refs:** `MPE-R005`, `UIW-R015`, `AOB-R008`
  - **E2E refs:** `ROI-STALE-P`, `ROI-STALE-R`, `GUI-RESP`
  - **Owned paths:** `src/segvision/runtime/embedding_cache.py`, `src/segvision/runtime/jobs.py`, `tests/unit/test_runtime_jobs.py`, `evidence/<run-id>/RUNTIME-JOBS/`
  - **Required inputs:** `Session/revision identity`, `Backend protocol`, `Frozen thread defaults`
  - **Expected outputs:** `Bounded in-memory cache and job/result protocols`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_runtime_jobs.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/RUNTIME-JOBS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/RUNTIME-JOBS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Cache eviction/release is deterministic and never persisted
    - Every job/result carries session/revision identity
    - Thread limits are explicit and bounded
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Cancel or evict only the affected job/state and retain manual fallback.
  - **Rollback boundary:** Revert only RUNTIME-JOBS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.2 `RUNTIME-STALE` — Implement background process execution, deterministic cancellation barriers, and stale-result rejection
  - **External gate:** `false`
  - **Dependencies:** `RUNTIME-JOBS`
  - **Requirement refs:** `SES-R004`, `UIW-R015`, `AOB-R004`, `AOB-R008`
  - **E2E refs:** `ROI-STALE-P`, `ROI-STALE-R`, `GUI-RESP`
  - **Owned paths:** `src/segvision/runtime/jobs.py`, `tests/integration/test_runtime_stale.py`, `evidence/<run-id>/RUNTIME-STALE/`
  - **Required inputs:** `Runtime protocols`, `Fake backend barriers`, `Session revision API`
  - **Expected outputs:** `Background worker and stale-publication guard`
  - **Exact commands:**
    1. `python -m pytest tests/integration/test_runtime_stale.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/RUNTIME-STALE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/RUNTIME-STALE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Barrier-controlled old proposal/refine results never enter current session state
    - Cancellation or discard is observable without arbitrary sleeps
    - Manual editing cannot be overwritten by a late model result
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Discard the stale result, release its state, and preserve the current revision.
  - **Rollback boundary:** Revert only RUNTIME-STALE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.3 `PERSIST-CONTRACT` — Implement accepted PNG and versioned sidecar construction with complete integrity and provenance
  - **External gate:** `false`
  - **Dependencies:** `M1-GATE`
  - **Requirement refs:** `PST-R001`, `PST-R002`, `PST-R003`, `PST-R008`, `PST-R009`
  - **E2E refs:** `SAVE-OK`, `SAVE-CORRUPT`
  - **Owned paths:** `src/segvision/adapters/png_sidecar.py`, `tests/unit/test_persistence_contract.py`, `evidence/<run-id>/PERSIST-CONTRACT/`
  - **Required inputs:** `CommitResult`, `acceptance/accepted-sidecar.schema.json`, `Full-image geometry`
  - **Expected outputs:** `Single-channel 0/255 PNG bytes and schema-valid accepted sidecar`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_persistence_contract.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/PERSIST-CONTRACT`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/PERSIST-CONTRACT/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Shape, values, crop containment, revision, filename, hash, policy, prompts, operations, timing, and generator ancestry agree
    - Model/CV/manual provenance is never fabricated
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Reject publication before creating a commit marker and preserve the in-memory CommitResult.
  - **Rollback boundary:** Revert only PERSIST-CONTRACT owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.4 `PAIR-PUBLISH` — Implement pair-consistent temporary write, flush, validation, atomic replacement, and sidecar-last commit marker
  - **External gate:** `false`
  - **Dependencies:** `PERSIST-CONTRACT`
  - **Requirement refs:** `PST-R004`, `PST-R005`
  - **E2E refs:** `SAVE-OK`, `SAVE-FAIL-TEMP-PNG`, `SAVE-FAIL-TEMP-JSON`, `SAVE-FAIL-VERIFY`, `SAVE-FAIL-PNG-PUBLISH`, `SAVE-FAIL-JSON-PUBLISH`
  - **Owned paths:** `src/segvision/adapters/png_sidecar.py`, `tests/unit/test_pair_publish.py`, `evidence/<run-id>/PAIR-PUBLISH/`
  - **Required inputs:** `Validated CommitResult`, `Task-owned destination filesystem`, `Fault injection hooks`
  - **Expected outputs:** `Pair publication receipt and retryable failure result`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_pair_publish.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/PAIR-PUBLISH`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/PAIR-PUBLISH/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - PNG and sidecar use unique same-filesystem temporaries
    - PNG publishes before sidecar
    - Sidecar is the only reader-visible commit marker
    - Every failure preserves retryability
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the validated result live, disable Next, and clean or quarantine only task-owned temporaries.
  - **Rollback boundary:** Revert only PAIR-PUBLISH owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.5 `PAIR-LOADER` — Implement accepted loader, review namespace, overwrite/version policy, corruption rejection, and semantic reload
  - **External gate:** `false`
  - **Dependencies:** `PAIR-PUBLISH`
  - **Requirement refs:** `PST-R006`, `PST-R007`, `PST-R008`, `PST-R009`, `PST-R010`
  - **E2E refs:** `SAVE-ORPHAN`, `SAVE-CORRUPT`, `SAVE-OVERWRITE`, `SAVE-PATH`, `REVIEW-DRAFT`, `REVIEW-EMPTY`
  - **Owned paths:** `src/segvision/adapters/png_sidecar.py`, `tests/unit/test_pair_loader.py`, `evidence/<run-id>/PAIR-LOADER/`
  - **Required inputs:** `Accepted/review sidecar schemas`, `Published and adversarial pair fixtures`
  - **Expected outputs:** `Integrity-validating accepted loader`, `Isolated review store`, `Versioned replacement policy`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_pair_loader.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/PAIR-LOADER`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/PAIR-LOADER/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Only complete accepted training-eligible pairs enumerate
    - Review/orphan/missing/hash/shape/value/schema/path failures are rejected
    - Round trip preserves exact mask and metadata semantics
    - Unrelated accepted data is immutable
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Quarantine/report only the invalid artifact and preserve prior valid versions.
  - **Rollback boundary:** Revert only PAIR-LOADER owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.6 `PERSIST-E2E` — Execute deterministic publication-stage failure, crash, corruption, retry, and review-isolation matrix
  - **External gate:** `false`
  - **Dependencies:** `PAIR-LOADER`, `VALIDATE-EVIDENCE`
  - **Requirement refs:** `PST-R005`, `PST-R006`, `PST-R007`, `PST-R011`, `AOB-R009`
  - **E2E refs:** `SAVE-OK`, `SAVE-FAIL-TEMP-PNG`, `SAVE-FAIL-TEMP-JSON`, `SAVE-FAIL-VERIFY`, `SAVE-FAIL-PNG-PUBLISH`, `SAVE-FAIL-JSON-PUBLISH`, `SAVE-ORPHAN`, `SAVE-CORRUPT`, `SAVE-OVERWRITE`, `SAVE-PATH`, `REVIEW-DRAFT`
  - **Owned paths:** `tests/e2e/test_persistence_matrix.py`, `tests/fixtures/persistence/`, `evidence/<run-id>/PERSIST-E2E/`
  - **Required inputs:** `Fault-injecting task-owned filesystem`, `Persistence adapter and loader`
  - **Expected outputs:** `Persistence matrix scenario results, pair hashes, and loader ledgers`
  - **Exact commands:**
    1. `python -m pytest tests/e2e/test_persistence_matrix.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/PERSIST-E2E`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/PERSIST-E2E/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Every failure stage yields zero newly loadable partial pair until retry succeeds
    - Corrupt/review-only records never enter training enumeration
    - Prior accepted pair remains readable through failed replacement
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Retain task-scoped artifacts for audit and never touch user annotation roots.
  - **Rollback boundary:** Revert only PERSIST-E2E owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.7 `GUI-STATE` — Implement the complete explicit annotation state machine and invalid-transition diagnostics
  - **External gate:** `false`
  - **Dependencies:** `RUNTIME-STALE`, `M1-GATE`
  - **Requirement refs:** `UIW-R001`, `UIW-R011`, `UIW-R012`, `UIW-R013`
  - **E2E refs:** `HP-01`, `KEY-SPACE-N`, `REVIEW-STATES`
  - **Owned paths:** `src/segvision/gui/controller.py`, `tests/unit/test_gui_state.py`, `evidence/<run-id>/GUI-STATE/`
  - **Required inputs:** `Session APIs`, `Runtime result protocol`, `Persistence receipt protocol`
  - **Expected outputs:** `GUI controller state table and typed transition results`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_gui_state.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GUI-STATE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GUI-STATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All named states and legal transitions are table-tested
    - Invalid transition changes no mask/state and starts no hidden work
    - Accepted is unreachable before validation, commit, and successful publish
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Return to the exact prior editable state or SAVE_FAILED while retaining live data.
  - **Rollback boundary:** Revert only GUI-STATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.8 `GUI-CANVAS-CARDS` — Implement canvas ROI/crop transforms, selected-mask rendering, overlays, and zero-to-three candidate cards
  - **External gate:** `false`
  - **Dependencies:** `GUI-STATE`, `ROI-COMMIT`, `CANDIDATE-ALLOCATE`
  - **Requirement refs:** `UIW-R002`, `UIW-R003`, `UIW-R004`, `UIW-R010`
  - **E2E refs:** `CAND-00`, `CAND-01`, `CAND-02`, `CAND-03`, `CAND-CAP`, `ROI-EDGE-SEM`
  - **Owned paths:** `src/segvision/gui/canvas.py`, `src/segvision/gui/panels.py`, `tests/gui/test_canvas_cards.py`, `evidence/<run-id>/GUI-CANVAS-CARDS/`
  - **Required inputs:** `GUI controller`, `Crop context`, `ProposalSet`, `Uncertainty masks`
  - **Expected outputs:** `Canvas and candidate-card widgets with accessible capability state`
  - **Exact commands:**
    1. `python -m pytest tests/gui/test_canvas_cards.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GUI-CANVAS-CARDS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GUI-CANVAS-CARDS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Cards match actual candidates without filler and rank one selects by default
    - Only selected mask is filled
    - User ROI, work crop, disagreement, and edge risk remain distinct
    - Capabilities control enabled states
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Show zero cards plus diagnostics/manual/review actions when no candidate survives.
  - **Rollback boundary:** Revert only GUI-CANVAS-CARDS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.9 `GUI-POINTS` — Implement actual left/right point input, selected-state refinement, and revision-safe presentation
  - **External gate:** `false`
  - **Dependencies:** `GUI-CANVAS-CARDS`, `POINT-REFINE`
  - **Requirement refs:** `UIW-R004`, `UIW-R005`
  - **E2E refs:** `REF-01`, `REF-02`, `REF-03`, `REF-UNSUPPORTED`, `MOUSE-FG-BG`, `KEY-CAP`
  - **Owned paths:** `src/segvision/gui/canvas.py`, `src/segvision/gui/controller.py`, `tests/gui/test_gui_points.py`, `evidence/<run-id>/GUI-POINTS/`
  - **Required inputs:** `Canvas transform`, `Selected candidate capabilities`, `Session refine API`
  - **Expected outputs:** `Foreground/background GUI event routing and pending/refined state transitions`
  - **Exact commands:**
    1. `python -m pytest tests/gui/test_gui_points.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GUI-POINTS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GUI-POINTS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Real GUI events produce correct full-image labels and selected previous-state lineage
    - Non-refinable candidates disable controls and cause no lazy encode
    - Only current-revision output is shown
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the selected candidate and display a typed recoverable refinement error.
  - **Rollback boundary:** Revert only GUI-POINTS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.10 `GUI-LOCAL-SHORTCUTS` — Implement brush, erase, grow, shrink, fill, Undo, Expand ROI, and frozen shortcut routing
  - **External gate:** `false`
  - **Dependencies:** `GUI-POINTS`, `EDIT-UNDO-MANUAL`
  - **Requirement refs:** `UIW-R006`, `UIW-R007`, `UIW-R008`, `UIW-R009`, `UIW-R010`
  - **E2E refs:** `EDIT-01`, `EDIT-02`, `EDIT-GROW`, `EDIT-FILL`, `MAN-EMPTY`, `MAN-ERASE`, `KEY-123`, `KEY-LOCAL`, `KEY-XZ`
  - **Owned paths:** `src/segvision/gui/canvas.py`, `src/segvision/gui/controller.py`, `src/segvision/gui/panels.py`, `tests/gui/test_gui_local_shortcuts.py`, `evidence/<run-id>/GUI-LOCAL-SHORTCUTS/`
  - **Required inputs:** `Local operation APIs`, `Session undo`, `ROI expansion API`, `GUI input framework`
  - **Expected outputs:** `Frozen keyboard/mouse/control mappings and local-edit GUI flow`
  - **Exact commands:**
    1. `python -m pytest tests/gui/test_gui_local_shortcuts.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GUI-LOCAL-SHORTCUTS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GUI-LOCAL-SHORTCUTS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Actual framework events map exactly to required shortcuts and visible Erase
    - Local actions/Undo add zero model calls and golden hashes match
    - Expansion creates a new revision
    - Invalid-state input is non-destructive
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve the current mask and expose the unavailable action reason.
  - **Rollback boundary:** Revert only GUI-LOCAL-SHORTCUTS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.11 `GUI-OUTCOMES-TIMER` — Implement explicit Accept, save retry, Needs Review, Next gating, and first-ROI monotonic timer
  - **External gate:** `false`
  - **Dependencies:** `GUI-LOCAL-SHORTCUTS`, `PAIR-LOADER`
  - **Requirement refs:** `UIW-R011`, `UIW-R012`, `UIW-R013`, `UIW-R014`
  - **E2E refs:** `KEY-SPACE-N`, `REVIEW-STATES`, `REVIEW-TIMEOUT`, `REVIEW-EMPTY`, `TIME-BOUNDARY`, `TIME-INVALID`, `TIME-ROI`, `TIME-REVIEW`, `TIME-SAVE`, `REVIEW-SAVE-FAIL`
  - **Owned paths:** `src/segvision/gui/controller.py`, `src/segvision/gui/panels.py`, `tests/gui/test_gui_outcomes_timer.py`, `evidence/<run-id>/GUI-OUTCOMES-TIMER/`
  - **Required inputs:** `Commit/Review APIs`, `Persistence adapter`, `Injectable monotonic clock`
  - **Expected outputs:** `Accept/save/review state flow, retry action, timer display, and Next gate`
  - **Exact commands:**
    1. `python -m pytest tests/gui/test_gui_outcomes_timer.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GUI-OUTCOMES-TIMER`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GUI-OUTCOMES-TIMER/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Strict within-30 uses validation time <30000 ms
    - Invalid Accept/ROI redraw/edit do not reset or stop time
    - Save retry performs no inference and Next enables only after durable Accepted
    - Review remains non-training
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the session live in the exact editable or SAVE_FAILED state and permit Review.
  - **Rollback boundary:** Revert only GUI-OUTCOMES-TIMER owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.12 `GUI-RESPONSIVE` — Connect background jobs while preserving paint, pan, zoom, redraw, manual fallback, and Review responsiveness
  - **External gate:** `false`
  - **Dependencies:** `GUI-OUTCOMES-TIMER`, `RUNTIME-STALE`
  - **Requirement refs:** `UIW-R015`, `AOB-R004`, `AOB-R008`
  - **E2E refs:** `GUI-RESP`, `ROI-STALE-P`, `ROI-STALE-R`
  - **Owned paths:** `src/segvision/gui/app.py`, `src/segvision/gui/controller.py`, `tests/gui/test_gui_responsive.py`, `evidence/<run-id>/GUI-RESPONSIVE/`
  - **Required inputs:** `Background worker`, `Deterministic job barriers`, `GUI event loop`
  - **Expected outputs:** `Non-blocking controller integration and responsiveness functional tests`
  - **Exact commands:**
    1. `python -m pytest tests/gui/test_gui_responsive.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GUI-RESPONSIVE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GUI-RESPONSIVE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - While encode/refine is barrier-blocked, GUI processes required events
    - Cancelled/late output never changes current cards or manual mask
    - Tests use event conditions, not arbitrary sleeps
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Cancel or stale-discard model work and keep manual/Review available.
  - **Rollback boundary:** Revert only GUI-RESPONSIVE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.13 `GUI-SCOPE` — Implement accessible frozen-scope desktop shell and omit every prohibited v1 control
  - **External gate:** `false`
  - **Dependencies:** `GUI-RESPONSIVE`
  - **Requirement refs:** `UIW-R016`, `AUT-R017`
  - **E2E refs:** `GUI-SCOPE`, `KEY-CAP`
  - **Owned paths:** `src/segvision/gui/app.py`, `src/segvision/gui/panels.py`, `tests/gui/test_gui_scope.py`, `evidence/<run-id>/GUI-SCOPE/`
  - **Required inputs:** `All GUI widgets and controller actions`, `Frozen v1 control inventory`
  - **Expected outputs:** `Launchable PySide6 desktop shell and accessibility inventory`
  - **Exact commands:**
    1. `python -m pytest tests/gui/test_gui_scope.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GUI-SCOPE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GUI-SCOPE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Required ROI/candidate/point/local/timer/Accept/Review controls are accessible
    - VLM, DINO, color sliders, multi-instance/video, auto-Accept, and default fusion are absent
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep optional fusion off and omit the unsupported feature.
  - **Rollback boundary:** Revert only GUI-SCOPE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.14 `GUI-E2E` — Execute actual GUI-input workflows for cards, points, edits, ROI races, Accept, save, Review, and scope
  - **External gate:** `false`
  - **Dependencies:** `GUI-SCOPE`, `PERSIST-E2E`
  - **Requirement refs:** `AOB-R004`, `AOB-R008`, `AOB-R009`, `AOB-R010`
  - **E2E refs:** `KEY-123`, `MOUSE-FG-BG`, `KEY-LOCAL`, `KEY-XZ`, `KEY-SPACE-N`, `KEY-CAP`, `GUI-SCOPE`, `GUI-RESP`
  - **Owned paths:** `tests/gui/test_annotation_workflow.py`, `tests/fixtures/gui/`, `evidence/<run-id>/GUI-E2E/`
  - **Required inputs:** `Off-screen GUI`, `Fake backend barriers`, `Fault persistence`, `Controlled clock`
  - **Expected outputs:** `GUI E2E results, state/event streams, call ledgers, mask hashes, and failure screenshots`
  - **Exact commands:**
    1. `python -m pytest tests/gui/test_annotation_workflow.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/GUI-E2E`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/GUI-E2E/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Every frozen interaction is sent through the GUI framework
    - Machine oracles use state/ledger/hash/loader rather than screenshots
    - Repeated deterministic runs are identical
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Capture diagnostics, preserve live state, and fix the deterministic cause rather than rerun-until-green.
  - **Rollback boundary:** Revert only GUI-E2E owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.15 `M3-SCENARIOS` — Implement planned scenario tests for every runtime, workflow, and persistence requirement
  - **External gate:** `false`
  - **Dependencies:** `GUI-E2E`
  - **Requirement refs:** `AUT-R008`, `UIW-R001`, `UIW-R016`, `PST-R001`, `PST-R011`
  - **E2E refs:** `SAVE-OK`, `SAVE-CORRUPT`, `REVIEW-STATES`, `TIME-BOUNDARY`, `KEY-123`, `GUI-RESP`
  - **Owned paths:** `tests/e2e/test_annotation_workflow_scenarios.py`, `tests/e2e/test_annotation_persistence_scenarios.py`, `evidence/<run-id>/M3-SCENARIOS/`
  - **Required inputs:** `acceptance/traceability.json`, `M3 implementation and deterministic fixtures`
  - **Expected outputs:** `Executable planned-test targets for all M3 traceability entries`
  - **Exact commands:**
    1. `python -m pytest tests/e2e/test_annotation_workflow_scenarios.py tests/e2e/test_annotation_persistence_scenarios.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/M3-SCENARIOS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/M3-SCENARIOS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Every planned workflow/persistence scenario target exists and passes
    - Scenario-to-requirement and E2E links remain exact
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Fail traceability and leave uncovered scenarios planned.
  - **Rollback boundary:** Revert only M3-SCENARIOS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 3.16 `M3-GATE` — Prove runtime, GUI, persistence, and fake-backend desktop workflow milestone
  - **External gate:** `false`
  - **Dependencies:** `M3-SCENARIOS`
  - **Requirement refs:** `UIW-R001`, `UIW-R016`, `PST-R001`, `PST-R011`, `AOB-R008`, `AOB-R009`, `AOB-R010`
  - **E2E refs:** `SAVE-OK`, `SAVE-FAIL-TEMP-PNG`, `SAVE-FAIL-TEMP-JSON`, `SAVE-FAIL-VERIFY`, `SAVE-FAIL-PNG-PUBLISH`, `SAVE-FAIL-JSON-PUBLISH`, `SAVE-ORPHAN`, `SAVE-CORRUPT`, `SAVE-OVERWRITE`, `SAVE-PATH`, `REVIEW-STATES`, `REVIEW-DRAFT`, `REVIEW-TIMEOUT`, `REVIEW-EMPTY`, `KEY-123`, `MOUSE-FG-BG`, `KEY-LOCAL`, `KEY-XZ`, `KEY-SPACE-N`, `KEY-CAP`, `GUI-SCOPE`, `GUI-RESP`
  - **Owned paths:** `evidence/<run-id>/M3-GATE/`
  - **Required inputs:** `All M3 checkpoints`, `M1 checkpoint`, `M2-CODE checkpoint`
  - **Expected outputs:** `M3 milestone evidence and checkpoint`
  - **Exact commands:**
    1. `python -m pytest tests/unit tests/integration tests/gui tests/e2e/test_persistence_matrix.py tests/gui/test_annotation_workflow.py -q`
    2. `python -m mypy src/segvision/runtime src/segvision/adapters src/segvision/gui`
    3. `python -m ruff check src tests`
    4. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/M3-GATE`
    5. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    6. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/M3-GATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All M3 deterministic gates pass with zero stale overwrite, partial pair, auto-Accept, hidden model call, or skipped GUI input
    - Independent M3 work is valid even if X-MODEL remains pending
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Retain M1 and M2-CODE checkpoints and isolate the failing runtime/GUI/persistence task.
  - **Rollback boundary:** Revert only M3-GATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

## M4 — Fixed CV, complete Tier A/B acceptance, offline package, and engineering verdict

- [x] 4.1 `CV-EXECUTOR` — Implement deterministic crop-only LAB resize, blur, inclusive threshold, and nearest-neighbor return pipeline
  - **External gate:** `false`
  - **Dependencies:** `RECIPE-SCHEMA`, `M3-GATE`
  - **Requirement refs:** `CVR-R005`, `CVR-R006`, `CVR-R008`
  - **E2E refs:** `CV-OFF`, `CV-DETERMINISM`
  - **Owned paths:** `src/segvision/cv/fixed_recipe.py`, `tests/unit/test_cv_executor.py`, `evidence/<run-id>/CV-EXECUTOR/`
  - **Required inputs:** `Parsed immutable recipe`, `Original RGB work crop`, `Locked NumPy/OpenCV versions`
  - **Expected outputs:** `Deterministic working mask and pipeline diagnostics`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_cv_executor.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/CV-EXECUTOR`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/CV-EXECUTOR/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Disabled/absent recipe executes zero CV calls
    - Enabled order and aspect ratio are exact
    - Inclusive threshold and nearest mapping match golden hashes
    - Recipe never mutates or tunes per image
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Return invalid diagnostics and continue normal SAM/manual fallback.
  - **Rollback boundary:** Revert only CV-EXECUTOR owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.2 `CV-GATES` — Implement frozen morphology, components, hole fill, validity, direct, and coarse gate semantics
  - **External gate:** `false`
  - **Dependencies:** `CV-EXECUTOR`
  - **Requirement refs:** `CVR-R007`, `CVR-R009`, `CVR-R010`, `CVR-R011`
  - **E2E refs:** `CV-DIRECT`, `CV-COARSE`, `CV-INVALID`
  - **Owned paths:** `src/segvision/cv/fixed_recipe.py`, `tests/unit/test_cv_gates.py`, `evidence/<run-id>/CV-GATES/`
  - **Required inputs:** `Threshold working mask`, `Frozen recipe gates`
  - **Expected outputs:** `Crop-resolution boolean CvResult with invalid/coarse/direct and diagnostics`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_cv_gates.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/CV-GATES`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/CV-GATES/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Morphology and 8-connectivity match exact semantics
    - Validity bounds are inclusive
    - Direct component/border boundaries are exact
    - Recoverable exceptions become invalid, never fabricated direct/coarse
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Return invalid and preserve SAM/manual path; keep ineffective recipe disabled.
  - **Rollback boundary:** Revert only CV-GATES owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.3 `CV-BRIDGE` — Integrate recipe-before-encode invalid, coarse mask-prompt, and zero-model direct proposal paths
  - **External gate:** `false`
  - **Dependencies:** `CV-GATES`, `M2-CODE`, `M3-GATE`
  - **Requirement refs:** `CVR-R012`, `CVR-R013`, `CVR-R014`, `MPE-R004`, `MPE-R012`, `MPE-R013`
  - **E2E refs:** `CV-OFF`, `CV-DIRECT`, `CV-COARSE`, `CV-INVALID`, `CV-UI`
  - **Owned paths:** `src/segvision/core/api.py`, `src/segvision/gui/controller.py`, `tests/integration/test_cv_bridge.py`, `evidence/<run-id>/CV-BRIDGE/`
  - **Required inputs:** `CvResult`, `Backend protocol`, `Candidate allocator`, `GUI capability flow`
  - **Expected outputs:** `Integrated proposal path and truthful CV/model provenance`
  - **Exact commands:**
    1. `python -m pytest tests/integration/test_cv_bridge.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/CV-BRIDGE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/CV-BRIDGE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Direct returns one cv_direct and zero model calls
    - Coarse is internal, converts once to mask state, and only validated sam_cv may display
    - Invalid runs normal one-encode SAM
    - No raw CV mask or automatic points leak
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Record bridge diagnostics and retain box candidates/manual fallback.
  - **Rollback boundary:** Revert only CV-BRIDGE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.4 `CV-E2E` — Execute disabled, invalid, coarse, direct, deterministic, round-trip, and capability GUI CV cases
  - **External gate:** `false`
  - **Dependencies:** `CV-BRIDGE`, `VALIDATE-EVIDENCE`
  - **Requirement refs:** `AOB-R007`, `CVR-R005`, `CVR-R015`
  - **E2E refs:** `CV-OFF`, `CV-DIRECT`, `CV-COARSE`, `CV-INVALID`, `CV-ROUNDTRIP`, `CV-DETERMINISM`, `CV-UI`
  - **Owned paths:** `tests/e2e/test_cv_recipes.py`, `tests/fixtures/cv/`, `evidence/<run-id>/CV-E2E/`
  - **Required inputs:** `Integrated CV proposal path`, `Scripted recipes and golden masks`, `GUI`
  - **Expected outputs:** `CV E2E scenario results, call ledgers, recipe hashes, and mask hashes`
  - **Exact commands:**
    1. `python -m pytest tests/e2e/test_cv_recipes.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/CV-E2E`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/CV-E2E/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All seven CV E2E cases meet exact gate, call-count, display-cap, provenance, and capability oracles
    - Repeat runs are byte/hash identical
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the class recipe disabled and continue SAM/manual workflows if evidence does not pass.
  - **Rollback boundary:** Revert only CV-E2E owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.5 `OBSERVABILITY` — Implement ordered session events, strict monotonic timing, aggregate denominators, and deterministic reports
  - **External gate:** `false`
  - **Dependencies:** `M3-GATE`
  - **Requirement refs:** `AOB-R001`, `AOB-R002`, `AOB-R003`
  - **E2E refs:** `TIME-BOUNDARY`, `TIME-INVALID`, `TIME-ROI`, `TIME-REVIEW`, `TIME-SAVE`, `TIME-AGG`, `REVIEW-TIMEOUT`
  - **Owned paths:** `src/segvision/acceptance/events.py`, `src/segvision/acceptance/reporting.py`, `tests/unit/test_observability.py`, `evidence/<run-id>/OBSERVABILITY/`
  - **Required inputs:** `Session/controller event sources`, `Injectable monotonic clock`, `Mixed outcome fixtures`
  - **Expected outputs:** `Ordered event stream and aggregate timing/outcome reports`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_observability.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/OBSERVABILITY`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/OBSERVABILITY/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Events contain session/revision/sequence/time and relevant IDs
    - Only 29999 ms passes strict within-30
    - Save latency is separate
    - Review/timeout/failure cases remain in all-image denominators
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve raw events and report the failed/unknown outcome without filtering it.
  - **Rollback boundary:** Revert only OBSERVABILITY owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.6 `ACCEPTANCE-RUNNER` — Implement manifest-driven Tier A/B/C runner, scenario dispatch, and mandatory-completeness enforcement
  - **External gate:** `false`
  - **Dependencies:** `OBSERVABILITY`, `VALIDATE-CONTRACTS`, `VALIDATE-EVIDENCE`
  - **Requirement refs:** `AOB-R004`, `AOB-R005`, `AOB-R006`, `AOB-R007`, `AOB-R008`, `AOB-R009`, `AOB-R010`, `AOB-R015`
  - **E2E refs:** none
  - **Owned paths:** `src/segvision/acceptance/runner.py`, `src/segvision/acceptance/cli.py`, `tests/integration/test_acceptance_runner.py`, `evidence/<run-id>/ACCEPTANCE-RUNNER/`
  - **Required inputs:** `acceptance/e2e-cases.json`, `Acceptance profile`, `Scenario implementations`, `Evidence writer`
  - **Expected outputs:** `run --tier CLI and structured scenario results`
  - **Exact commands:**
    1. `python -m pytest tests/integration/test_acceptance_runner.py -q`
    2. `python -m segvision.acceptance validate-manifest openspec/changes/build-segvision-v1/acceptance/e2e-cases.json`
    3. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    4. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/ACCEPTANCE-RUNNER`
    5. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/ACCEPTANCE-RUNNER/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Unknown/missing/duplicate mandatory scenario fails
    - Tier dispatch is deterministic
    - Zero skip/xfail/flaky retry policy is enforced
    - Every result maps to requirement and evidence
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Emit FAIL/BLOCKED with missing IDs and retain all partial results.
  - **Rollback boundary:** Revert only ACCEPTANCE-RUNNER owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.7 `VERDICT-CLASSIFIER` — Implement non-gameable release verdict and project-state classification for engineering and optional domain targets
  - **External gate:** `false`
  - **Dependencies:** `ACCEPTANCE-RUNNER`, `VALIDATE-STATE`
  - **Requirement refs:** `AOB-R017`, `AOB-R018`, `OFR-R014`, `OFR-R015`, `AUT-R023`, `AUT-R024`
  - **E2E refs:** `REL-VERDICT`, `REL-ROLLBACK`
  - **Owned paths:** `src/segvision/acceptance/verdict.py`, `tests/unit/test_verdict_classifier.py`, `tests/governance/test_release_controller.py`, `evidence/<run-id>/VERDICT-CLASSIFIER/`
  - **Required inputs:** `Release-verdict schema`, `Tier results`, `External gate state`, `Target release class`
  - **Expected outputs:** `verdict CLI and structured PASS/FAIL/BLOCKED/project-state output`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_verdict_classifier.py tests/governance/test_release_controller.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/VERDICT-CLASSIFIER`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/VERDICT-CLASSIFIER/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Mandatory failure, missing evidence, hidden retry, changed threshold, or required external blocker cannot yield PASS
    - Engineering target ignores missing Tier C inputs
    - Domain target retains engineering acceptance while honestly blocking promotion
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Emit the exact non-pass state and preserve passing lower-tier classification.
  - **Rollback boundary:** Revert only VERDICT-CLASSIFIER owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.8 `E2E-CANDIDATES` — Implement manifest cases for happy path, zero-to-three candidates, cap, prompts, edge risk, safe-grid, and fusion
  - **External gate:** `false`
  - **Dependencies:** `ACCEPTANCE-RUNNER`, `M3-GATE`
  - **Requirement refs:** `AOB-R004`, `AOB-R005`, `MPE-R007`, `MPE-R018`
  - **E2E refs:** `HP-01`, `CAND-00`, `CAND-01`, `CAND-02`, `CAND-03`, `CAND-CAP`, `CAND-POINT`, `CAND-EDGE`, `CAND-UNCERTAINTY`, `GRID-01`, `GRID-02`, `FUSE-01`, `FUSE-02`
  - **Owned paths:** `tests/e2e/test_candidates.py`, `tests/fixtures/e2e/candidates/`, `evidence/<run-id>/E2E-CANDIDATES/`
  - **Required inputs:** `Fake backend`, `Controlled clock`, `Candidate fixtures`, `Acceptance runner`
  - **Expected outputs:** `Candidate-category scenario results and evidence`
  - **Exact commands:**
    1. `python -m pytest tests/e2e/test_candidates.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/E2E-CANDIDATES`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/E2E-CANDIDATES/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All candidate IDs execute with exact card count/order/hash/capability/warning/call-ledger oracles
    - No duplicate filler, OR, or auto-Accept occurs
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Return zero candidates with diagnostics and preserve manual/review fallback.
  - **Rollback boundary:** Revert only E2E-CANDIDATES owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.9 `E2E-REFINE-ROI` — Implement manifest cases for refinement, edits, manual fallback, point validation, ROI geometry, and stale races
  - **External gate:** `false`
  - **Dependencies:** `E2E-CANDIDATES`, `RUNTIME-STALE`
  - **Requirement refs:** `AOB-R006`, `AOB-R008`, `SES-R004`, `SES-R006`, `SES-R008`, `ROI-R011`
  - **E2E refs:** `REF-01`, `REF-02`, `REF-03`, `REF-UNSUPPORTED`, `EDIT-01`, `EDIT-02`, `EDIT-GROW`, `EDIT-FILL`, `VAL-POINT`, `MAN-EMPTY`, `MAN-ERASE`, `MAN-BACKEND-FAIL`, `MAN-REFINE`, `ROI-PAD`, `ROI-CLAMP`, `ROI-INVALID`, `ROI-STALE-P`, `ROI-STALE-R`, `ROI-EXPAND`, `ROI-EDGE-SEM`, `ROI-DIRECT`
  - **Owned paths:** `tests/e2e/test_refine_and_edit.py`, `tests/e2e/test_manual_fallback.py`, `tests/e2e/test_roi_revision.py`, `tests/fixtures/e2e/refine_roi/`, `evidence/<run-id>/E2E-REFINE-ROI/`
  - **Required inputs:** `Fake backend barriers`, `Core/session/runtime implementation`, `Golden masks`
  - **Expected outputs:** `Refine/edit/manual/ROI scenario results and evidence`
  - **Exact commands:**
    1. `python -m pytest tests/e2e/test_refine_and_edit.py tests/e2e/test_manual_fallback.py tests/e2e/test_roi_revision.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/E2E-REFINE-ROI`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/E2E-REFINE-ROI/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Previous-state and encode/decode counts are exact
    - Manual lock/Undo hashes are exact
    - ROI races use barriers and stale results never present
    - Timer origin and direct zero-encode behavior persist
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep prior valid candidate/revision state and expose typed diagnostics.
  - **Rollback boundary:** Revert only E2E-REFINE-ROI owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.10 `E2E-PERSIST-GUI-TIME` — Implement manifest cases for persistence, Review, timing boundaries, GUI input, scope, and responsiveness
  - **External gate:** `false`
  - **Dependencies:** `E2E-REFINE-ROI`, `PERSIST-E2E`, `GUI-E2E`, `OBSERVABILITY`
  - **Requirement refs:** `AOB-R002`, `AOB-R003`, `AOB-R009`, `AOB-R010`
  - **E2E refs:** `SAVE-OK`, `SAVE-FAIL-TEMP-PNG`, `SAVE-FAIL-TEMP-JSON`, `SAVE-FAIL-VERIFY`, `SAVE-FAIL-PNG-PUBLISH`, `SAVE-FAIL-JSON-PUBLISH`, `SAVE-ORPHAN`, `SAVE-CORRUPT`, `SAVE-OVERWRITE`, `SAVE-PATH`, `REVIEW-STATES`, `REVIEW-DRAFT`, `REVIEW-TIMEOUT`, `REVIEW-EMPTY`, `TIME-BOUNDARY`, `TIME-INVALID`, `TIME-ROI`, `TIME-REVIEW`, `TIME-SAVE`, `TIME-AGG`, `REVIEW-SAVE-FAIL`
  - **Owned paths:** `tests/e2e/test_persistence_faults.py`, `tests/e2e/test_needs_review.py`, `tests/e2e/test_timing.py`, `tests/fixtures/e2e/persist_gui_time/`, `evidence/<run-id>/E2E-PERSIST-GUI-TIME/`
  - **Required inputs:** `Fault persistence`, `Controlled clock`, `Off-screen GUI`, `Acceptance runner`
  - **Expected outputs:** `Persistence/review/timing/GUI scenario results and evidence`
  - **Exact commands:**
    1. `python -m pytest tests/e2e/test_persistence_faults.py tests/e2e/test_needs_review.py tests/e2e/test_timing.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/E2E-PERSIST-GUI-TIME`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/E2E-PERSIST-GUI-TIME/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - All case IDs execute with exact state/event/loader/hash/time/input oracles
    - Screenshots are diagnostic only
    - Failures and Review remain in denominators
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve the live session and all failed evidence; never infer acceptance.
  - **Rollback boundary:** Revert only E2E-PERSIST-GUI-TIME owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.11 `PERFORMANCE-HARNESS` — Implement fingerprinted GUI and backend performance measurement with complete distributions and RAM accounting
  - **External gate:** `false`
  - **Dependencies:** `M3-GATE`, `MODEL-FIXTURES`
  - **Requirement refs:** `AOB-R011`, `AOB-R012`, `OFR-R010`
  - **E2E refs:** `PERF-UI`, `PERF-REFINE`, `PERF-MODEL`, `PERF-WORKFLOW`
  - **Owned paths:** `benchmarks/gui_latency.py`, `benchmarks/model_latency.py`, `src/segvision/acceptance/performance.py`, `tests/unit/test_performance_stats.py`, `evidence/<run-id>/PERFORMANCE-HARNESS/`
  - **Required inputs:** `acceptance/performance-report.schema.json`, `Acceptance profile performance thresholds`, `Reference target schema`
  - **Expected outputs:** `Deterministic benchmark commands and validated performance-report output`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_performance_stats.py -q`
    2. `python benchmarks/gui_latency.py --help`
    3. `python benchmarks/model_latency.py --help`
    4. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    5. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/PERFORMANCE-HARNESS`
    6. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/PERFORMANCE-HARNESS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Reports contain hardware/thread/backend/workload identity, p50/p90/p95/max, sample count, cold/warm split, peak RAM, cache, crop, and occupancy
    - UI hard gate and refine best-effort classification remain distinct
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep timing diagnostic only until run on an approved fingerprinted target.
  - **Rollback boundary:** Revert only PERFORMANCE-HARNESS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.12 `PACKAGE-BUILD` — Build versioned wheel, GUI entry point, exact lock, and repeatable CPU-only artifact inventory
  - **External gate:** `false`
  - **Dependencies:** `M3-GATE`, `M2-CODE`
  - **Requirement refs:** `OFR-R001`, `OFR-R003`, `OFR-R004`
  - **E2E refs:** `PKG-INSTALL`, `PKG-CPU`
  - **Owned paths:** `pyproject.toml`, `requirements/`, `src/segvision/gui/__main__.py`, `tests/packaging/test_build_import.py`, `dist/`, `evidence/<run-id>/PACKAGE-BUILD/`
  - **Required inputs:** `M3 implementation`, `Exact lock`, `Build tools`
  - **Expected outputs:** `Versioned wheel, GUI entry point, dependency inventory, and artifact hashes`
  - **Exact commands:**
    1. `python -m build --wheel`
    2. `python -m pytest tests/packaging/test_build_import.py -q`
    3. `python -c "import segvision"`
    4. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    5. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/PACKAGE-BUILD`
    6. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/PACKAGE-BUILD/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Wheel import is side-effect free and GUI entry is independent
    - Resolved environment matches exact lock
    - Required CUDA/GPU/remote runtime is absent
    - Build artifacts are hash-recorded
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Use reviewed CPU-compatible pins in an isolated environment; do not add GPU/cloud.
  - **Rollback boundary:** Revert only PACKAGE-BUILD owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [x] 4.13 `COMPLIANCE-BUNDLE` — Generate SBOM, third-party notices, model inventory, license checks, and checksum-verified offline bundle
  - **External gate:** `false`
  - **Dependencies:** `PACKAGE-BUILD`, `MODEL-MANIFEST`
  - **Requirement refs:** `OFR-R002`, `OFR-R005`, `OFR-R006`, `OFR-R007`, `OFR-R008`, `OFR-R009`
  - **E2E refs:** `PKG-COMPLIANCE`, `REAL-CHECKSUM`
  - **Owned paths:** `SBOM.json`, `THIRD_PARTY_NOTICES.md`, `dist/offline/`, `src/segvision/acceptance/compliance.py`, `tests/packaging/test_compliance.py`, `evidence/<run-id>/COMPLIANCE-BUNDLE/`
  - **Required inputs:** `Built wheel`, `Exact lock`, `Model manifest`, `Approved local artifact supply`
  - **Expected outputs:** `SBOM/notices/compliance report and content-addressed offline bundle`
  - **Exact commands:**
    1. `python -m pytest tests/packaging/test_compliance.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/COMPLIANCE-BUNDLE`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/COMPLIANCE-BUNDLE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Installed/transitive/model/GUI/CV assets reconcile across lock, SBOM, notices, and manifest
    - Bundle needs no online resolution
    - Unapproved or undocumented material fails closed
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Exclude the artifact and leave bundle/release blocked; never omit a manifest entry.
  - **Rollback boundary:** Revert only COMPLIANCE-BUNDLE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [ ] 4.14 `X-RELEASE-AUTH` — Verify attributable redistribution and release authority for every packaged dependency, model artifact, and asset
  - **External gate:** `true`
  - **Dependencies:** `COMPLIANCE-BUNDLE`, `X-MODEL`
  - **Requirement refs:** `OFR-R005`, `OFR-R006`, `OFR-R007`, `OFR-R009`, `AUT-R013`, `AUT-R019`, `AUT-R020`
  - **E2E refs:** `PKG-COMPLIANCE`
  - **Owned paths:** `evidence/external-gates/release-authority/`, `openspec/changes/build-segvision-v1/acceptance/external-gates/model-artifact-manifest.pending.json`, `evidence/<run-id>/X-RELEASE-AUTH/`
  - **Required inputs:** `SBOM`, `Third-party notices`, `Model manifest`, `Attributable legal/organizational decisions`
  - **Expected outputs:** `Approved authority references for the exact bundle or schema-valid blocker`
  - **Exact commands:**
    1. `python -m pytest tests/packaging/test_compliance.py -q`
    2. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
    3. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    4. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/X-RELEASE-AUTH`
  - **Required evidence:** `Schema-valid evidence/<run-id>/X-RELEASE-AUTH/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Every redistribution subject has attributable approval and required notice
    - Unknown/incompatible terms remain blocked and cannot be inferred by the agent
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 1 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the affected artifact excluded and emit blocked_license while other independent tasks continue.
  - **Rollback boundary:** Revert only X-RELEASE-AUTH owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Commercial-use or redistribution authority is missing or incompatible; A required notice or transitive dependency cannot be reconciled

- [ ] 4.15 `X-REFERENCE` — Verify designated physical performance CPU and separate clean-Windows offline-install target availability
  - **External gate:** `true`
  - **Dependencies:** `PERFORMANCE-HARNESS`
  - **Requirement refs:** `AOB-R011`, `AOB-R012`, `AOB-R016`, `OFR-R010`, `AUT-R019`, `AUT-R020`
  - **E2E refs:** `PERF-UI`, `PERF-REFINE`, `PERF-MODEL`, `PKG-INSTALL`, `PKG-E2E`, `PKG-CPU`, `PKG-PATH`, `PKG-NET`
  - **Owned paths:** `openspec/changes/build-segvision-v1/acceptance/external-gates/reference-targets.pending.json`, `evidence/external-gates/reference-targets/`, `evidence/<run-id>/X-REFERENCE/`
  - **Required inputs:** `Physical performance target fingerprint and access`, `Clean Windows target fingerprint and access`, `Network isolation authority`
  - **Expected outputs:** `Approved reference-target manifest or schema-valid blocker`
  - **Exact commands:**
    1. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    2. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/X-REFERENCE`
  - **Required evidence:** `Schema-valid evidence/<run-id>/X-REFERENCE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Performance and clean-install target roles are explicitly identified
    - Shared/unfingerprinted CI cannot satisfy hard timing
    - Absent target yields blocked_reference_hardware without fabricated values
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 1 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Retain functional engineering evidence and block only target-dependent gates.
  - **Rollback boundary:** Revert only X-REFERENCE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Required physical reference CPU is unavailable; Required clean Windows offline-install target is unavailable; Security policy prevents the prescribed audit

- [ ] 4.16 `REFERENCE-PERF` — Run real backend and UI workloads on the approved fingerprinted physical reference CPU
  - **External gate:** `false`
  - **Dependencies:** `M2-GATE`, `PERFORMANCE-HARNESS`, `X-REFERENCE`
  - **Requirement refs:** `AOB-R011`, `AOB-R012`, `OFR-R010`
  - **E2E refs:** `PERF-UI`, `PERF-REFINE`, `PERF-MODEL`, `REAL-REG`, `PERF-WORKFLOW`
  - **Owned paths:** `tests/e2e/test_reference_performance.py`, `evidence/<run-id>/REFERENCE-PERF/`
  - **Required inputs:** `Approved physical reference target`, `Approved MobileSAM artifact`, `Performance harness`, `Fixed thread policy`
  - **Expected outputs:** `Validated performance report, process/module audit, and real-backend results`
  - **Exact commands:**
    1. `python -m pytest tests/e2e/test_reference_performance.py -q`
    2. `python benchmarks/gui_latency.py --profile openspec/changes/build-segvision-v1/acceptance/acceptance-profile.json --output evidence/$env:SEG_RUN_ID/REFERENCE-PERF/gui.json`
    3. `python benchmarks/model_latency.py --profile openspec/changes/build-segvision-v1/acceptance/acceptance-profile.json --output evidence/$env:SEG_RUN_ID/REFERENCE-PERF/model.json`
    4. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/REFERENCE-PERF`
    5. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    6. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/REFERENCE-PERF/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - At least 1000 UI samples yield p95 strictly below 100 ms
    - Cached refine is honestly classified against the best-effort target
    - Cold/warm backend and peak RAM distributions are complete
    - No GPU/network dependency appears
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Apply at most three profiled CPU/rendering optimizations, then block reference hardware/performance without lowering thresholds.
  - **Rollback boundary:** Revert only REFERENCE-PERF owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Hard UI p95 remains impossible after three measured rendering hypotheses; Target hardware becomes unavailable or fingerprint changes

- [ ] 4.17 `OFFLINE-E2E` — Install the approved bundle on clean Windows with networking disabled and run packaged Accept, Review, restart, and reload
  - **External gate:** `false`
  - **Dependencies:** `COMPLIANCE-BUNDLE`, `X-RELEASE-AUTH`, `X-REFERENCE`, `M2-GATE`
  - **Requirement refs:** `AOB-R016`, `OFR-R002`, `OFR-R011`
  - **E2E refs:** `PKG-INSTALL`, `PKG-E2E`, `PKG-CPU`, `PKG-PATH`, `PKG-COMPLIANCE`, `PKG-NET`
  - **Owned paths:** `tests/packaging/test_offline_release.py`, `evidence/<run-id>/OFFLINE-E2E/`
  - **Required inputs:** `Approved offline bundle`, `Approved clean Windows target`, `Empty dependency/model caches`, `Network-disabled environment`
  - **Expected outputs:** `Clean-install log, runtime audit, accepted pair, review record, reload hashes, and scenario results`
  - **Exact commands:**
    1. `python -m pytest tests/packaging/test_offline_release.py -q`
    2. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/OFFLINE-E2E`
    3. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/OFFLINE-E2E/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - No-index install/import/GUI launch succeeds through paths with spaces and Unicode
    - Packaged real backend Accept/save/restart/reload hashes match
    - Review is excluded
    - No CUDA DLL/provider, login, or outbound connection is required
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Preserve the bundle and evidence, fix only packaging/runtime defects, and never enable network/GPU fallback.
  - **Rollback boundary:** Revert only OFFLINE-E2E owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [ ] 4.18 `TIER-A-B` — Run complete mandatory Tier A and Tier B suites with all existing E2E IDs and evidence consistency checks
  - **External gate:** `false`
  - **Dependencies:** `CV-E2E`, `E2E-PERSIST-GUI-TIME`, `REFERENCE-PERF`, `OFFLINE-E2E`, `VERDICT-CLASSIFIER`
  - **Requirement refs:** `AOB-R004`, `AOB-R005`, `AOB-R006`, `AOB-R007`, `AOB-R008`, `AOB-R009`, `AOB-R010`, `AOB-R011`, `AOB-R012`, `AOB-R015`, `AOB-R016`, `AOB-R017`, `AOB-R018`
  - **E2E refs:** `HP-01`, `CAND-00`, `CAND-01`, `CAND-02`, `CAND-03`, `CAND-CAP`, `CAND-POINT`, `CAND-EDGE`, `GRID-01`, `GRID-02`, `FUSE-01`, `FUSE-02`, `REF-01`, `REF-02`, `REF-03`, `REF-UNSUPPORTED`, `EDIT-01`, `EDIT-02`, `EDIT-GROW`, `EDIT-FILL`, `VAL-POINT`, `CV-OFF`, `CV-DIRECT`, `CV-COARSE`, `CV-INVALID`, `CV-ROUNDTRIP`, `CV-DETERMINISM`, `CV-UI`, `MAN-EMPTY`, `MAN-ERASE`, `MAN-BACKEND-FAIL`, `MAN-REFINE`, `ROI-PAD`, `ROI-CLAMP`, `ROI-INVALID`, `ROI-STALE-P`, `ROI-STALE-R`, `ROI-EXPAND`, `ROI-EDGE-SEM`, `ROI-DIRECT`, `SAVE-OK`, `SAVE-FAIL-TEMP-PNG`, `SAVE-FAIL-TEMP-JSON`, `SAVE-FAIL-VERIFY`, `SAVE-FAIL-PNG-PUBLISH`, `SAVE-FAIL-JSON-PUBLISH`, `SAVE-ORPHAN`, `SAVE-CORRUPT`, `SAVE-OVERWRITE`, `SAVE-PATH`, `REVIEW-STATES`, `REVIEW-DRAFT`, `REVIEW-TIMEOUT`, `REVIEW-EMPTY`, `TIME-BOUNDARY`, `TIME-INVALID`, `TIME-ROI`, `TIME-REVIEW`, `TIME-SAVE`, `TIME-AGG`, `PERF-UI`, `PERF-REFINE`, `PERF-MODEL`, `KEY-123`, `MOUSE-FG-BG`, `KEY-LOCAL`, `KEY-XZ`, `KEY-SPACE-N`, `KEY-CAP`, `GUI-SCOPE`, `GUI-RESP`, `REAL-REG`, `REAL-CHECKSUM`, `QUALITY-SYNTH`, `PKG-INSTALL`, `PKG-E2E`, `PKG-CPU`, `PKG-PATH`, `PKG-COMPLIANCE`, `PKG-NET`, `CAND-UNCERTAINTY`, `REVIEW-SAVE-FAIL`, `GOV-DAG`, `GOV-INCOMPLETE`, `GOV-RETRY`, `GOV-BLOCK-CONTINUE`, `GOV-RESUME`, `GOV-OWNERSHIP`, `GOV-EVIDENCE`, `GOV-PROHIBITIONS`, `REL-VERDICT`, `REL-ROLLBACK`, `PERF-WORKFLOW`
  - **Owned paths:** `evidence/<run-id>/TIER-A-B/`
  - **Required inputs:** `All Tier A/B implementations`, `Approved external engineering gates`, `Acceptance profile`
  - **Expected outputs:** `Complete scenario-results, run manifest, reports, evidence index, and preliminary verdict`
  - **Exact commands:**
    1. `python -m segvision.acceptance run --tier A --evidence evidence`
    2. `python -m segvision.acceptance run --tier B --profile openspec/changes/build-segvision-v1/acceptance/acceptance-profile.json --evidence evidence`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID`
    4. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    5. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/TIER-A-B`
    6. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/TIER-A-B/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Every mandatory Tier A/B case passes once with zero skip/xfail/flaky retry
    - All hashes, thresholds, denominators, external approvals, and target identities reconcile
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Emit FAIL or the exact engineering external blocker; retain every failed scenario and metric.
  - **Rollback boundary:** Revert only TIER-A-B owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [ ] 4.19 `M4-GATE` — Issue and freeze the engineering-target PASS_ENGINEERING release candidate with immutable rollback evidence
  - **External gate:** `false`
  - **Dependencies:** `TIER-A-B`, `X-RELEASE-AUTH`
  - **Requirement refs:** `OFR-R012`, `OFR-R013`, `OFR-R014`, `AOB-R017`, `AOB-R018`, `AUT-R023`, `AUT-R024`
  - **E2E refs:** `REL-VERDICT`, `REL-ROLLBACK`
  - **Owned paths:** `evidence/<run-id>/release-verdict.json`, `dist/release-index.json`, `evidence/<run-id>/M4-GATE/`
  - **Required inputs:** `Complete Tier A/B evidence`, `Exact source, lock, model, recipe, package, SBOM, notice, and target hashes`, `Engineering target`
  - **Expected outputs:** `PASS_ENGINEERING verdict, immutable artifact index, and prior-artifact rollback reference`
  - **Exact commands:**
    1. `openspec validate build-segvision-v1 --strict --no-interactive`
    2. `python -m segvision.acceptance validate-contracts --change build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID`
    4. `python -m segvision.acceptance validate-state --state evidence/execution-state.json`
    5. `python -m segvision.acceptance verdict --evidence evidence/$env:SEG_RUN_ID --target engineering`
  - **Required evidence:** `Schema-valid evidence/<run-id>/M4-GATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Verdict is PASS_ENGINEERING with engineering_accepted true and domain_validated false
    - No mandatory Tier A/B failure, missing evidence, pending engineering authority, or hash drift exists
    - Tier C absence is not a blocker for engineering target
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep the prior verified release artifact and emit FAIL/BLOCKED; never overwrite it or relabel partial success.
  - **Rollback boundary:** Revert only M4-GATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

## M5 — Optional domain validation and promotion

- [x] 5.1 `DOMAIN-TOOLS` — Implement domain input, boundary metric, reviewer/workflow, feature-retention, and quality-report validators
  - **External gate:** `false`
  - **Dependencies:** `VERDICT-CLASSIFIER`
  - **Requirement refs:** `AOB-R013`, `AOB-R014`, `AOB-R017`, `AOB-R018`, `OFR-R015`
  - **E2E refs:** `QUALITY-DOMAIN`
  - **Owned paths:** `src/segvision/acceptance/domain.py`, `tests/unit/test_domain_validation.py`, `evidence/<run-id>/DOMAIN-TOOLS/`
  - **Required inputs:** `acceptance/domain-inputs.schema.json`, `acceptance/quality-report.schema.json`, `Frozen domain profile`
  - **Expected outputs:** `Domain manifest validator, boundary F1 evaluator, workflow/reviewer aggregator, and quality report`
  - **Exact commands:**
    1. `python -m pytest tests/unit/test_domain_validation.py -q`
    2. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/DOMAIN-TOOLS`
    4. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/DOMAIN-TOOLS/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Boundary tolerance and minimums are exact
    - At least 100 representative and 30 independent-gold inputs are required
    - Synthetic/self-generated gold or reviewer evidence is rejected
    - Feature retention needs measured benefit without boundary degradation
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Leave domain promotion unavailable while retaining PASS_ENGINEERING.
  - **Rollback boundary:** Revert only DOMAIN-TOOLS owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [ ] 5.2 `X-DOMAIN` — Verify annotation-policy approval, representative data, independent gold, real annotator/reviewer evidence, data authority, and release signoff
  - **External gate:** `true`
  - **Dependencies:** `DOMAIN-TOOLS`, `M4-GATE`
  - **Requirement refs:** `AOB-R013`, `OFR-R015`, `AUT-R018`, `AUT-R019`, `AUT-R020`, `AUT-R024`
  - **E2E refs:** `QUALITY-DOMAIN`
  - **Owned paths:** `openspec/changes/build-segvision-v1/acceptance/external-gates/domain-inputs.pending.json`, `evidence/external-gates/domain/`, `evidence/<run-id>/X-DOMAIN/`
  - **Required inputs:** `Attributable approval of the exact immutable annotation policy`, `At least 100 representative real images`, `At least 30 independently produced gold masks`, `Real annotator sessions`, `Independent reviews`, `Data-use authority`, `Release signoff`
  - **Expected outputs:** `Approved domain-input manifest with immutable hashes or schema-valid blocker`
  - **Exact commands:**
    1. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    2. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/X-DOMAIN`
  - **Required evidence:** `Schema-valid evidence/<run-id>/X-DOMAIN/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Domain manifest approval binds the exact policy ID and content SHA-256 without mutating policy semantics
    - Every input and human/authority claim is externally attributable and linked to the engineering candidate
    - Missing inputs retain PASS_ENGINEERING and block only domain target
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 1 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Keep domain_validated false, preserve PASS_ENGINEERING, and emit one BLOCKED_EXTERNAL_INPUT record.
  - **Rollback boundary:** Revert only X-DOMAIN owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Attributable annotation-policy approval is unavailable; Representative data or independent gold is unavailable; Real annotator or independent reviewer evidence is unavailable; Data-use authority or final domain release signoff is unavailable

- [ ] 5.3 `DOMAIN-EVALUATE` — Run approved real-domain boundary, workflow, reviewer, wrong-Accept, timeout, and feature-retention evaluation
  - **External gate:** `false`
  - **Dependencies:** `DOMAIN-TOOLS`, `X-DOMAIN`, `M4-GATE`
  - **Requirement refs:** `AOB-R013`, `AOB-R014`, `OFR-R015`
  - **E2E refs:** `QUALITY-DOMAIN`
  - **Owned paths:** `tests/e2e/test_domain_verdict.py`, `evidence/<run-id>/DOMAIN-EVALUATE/`
  - **Required inputs:** `Approved domain-input manifest`, `Engineering-accepted exact candidate`, `Frozen acceptance profile`
  - **Expected outputs:** `Per-image boundary metrics, outcome denominators, independent review results, and quality report`
  - **Exact commands:**
    1. `python -m pytest tests/e2e/test_domain_verdict.py -q`
    2. `python -m segvision.acceptance run --tier C --profile openspec/changes/build-segvision-v1/acceptance/acceptance-profile.json --evidence evidence`
    3. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/DOMAIN-EVALUATE`
    4. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
    5. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
  - **Required evidence:** `Schema-valid evidence/<run-id>/DOMAIN-EVALUATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Median boundary F1 >= 0.95 and every evaluated image >= 0.90
    - At least 90 of 100 presented images are durably accepted and valid_accept_rate is at least 0.90
    - Accepted-conditional within-30 rate is 100%, all-presented within-30 Accept rate is at least 90%, Needs Review is at most 10%, and timeout, unresolved, and wrong Accept are zero
    - At least 30 accepted images receive independent review and training-usable rate is 100%
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Retain PASS_ENGINEERING, report failing domain gates unchanged, and keep non-beneficial optional features disabled.
  - **Rollback boundary:** Revert only DOMAIN-EVALUATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [ ] 5.4 `DOMAIN-VERDICT` — Issue PASS_DOMAIN_VALIDATED only for the exact engineering candidate with complete real external evidence
  - **External gate:** `false`
  - **Dependencies:** `DOMAIN-EVALUATE`
  - **Requirement refs:** `AOB-R017`, `AOB-R018`, `OFR-R015`, `AUT-R023`, `AUT-R024`
  - **E2E refs:** `QUALITY-DOMAIN`
  - **Owned paths:** `evidence/<run-id>/release-verdict.json`, `evidence/<run-id>/DOMAIN-VERDICT/`
  - **Required inputs:** `PASS_ENGINEERING candidate`, `Tier C evidence`, `Approved domain/signoff inputs`
  - **Expected outputs:** `Domain verdict bound to source, lock, model, recipe, package, data, gold, reviewer, and evidence hashes`
  - **Exact commands:**
    1. `python -m segvision.acceptance validate-contracts --change build-segvision-v1`
    2. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID`
    3. `python -m segvision.acceptance validate-state --state evidence/execution-state.json`
    4. `python -m segvision.acceptance verdict --evidence evidence/$env:SEG_RUN_ID --target domain`
  - **Required evidence:** `Schema-valid evidence/<run-id>/DOMAIN-VERDICT/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Verdict is PASS_DOMAIN_VALIDATED only when every Tier C gate and external authority passes
    - Any candidate/hash change invalidates affected gates
    - Engineering acceptance remains truthful if domain promotion fails
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Emit BLOCKED_EXTERNAL_INPUT or FAIL for domain while retaining the exact prior PASS_ENGINEERING candidate.
  - **Rollback boundary:** Revert only DOMAIN-VERDICT owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition

- [ ] 5.5 `M5-GATE` — Audit and freeze optional domain-validated promotion without altering the engineering release history
  - **External gate:** `false`
  - **Dependencies:** `DOMAIN-VERDICT`
  - **Requirement refs:** `OFR-R013`, `OFR-R015`, `AUT-R014`, `AUT-R015`, `AUT-R023`, `AUT-R024`
  - **E2E refs:** `QUALITY-DOMAIN`
  - **Owned paths:** `evidence/<run-id>/M5-GATE/`, `dist/release-index.json`
  - **Required inputs:** `Domain verdict`, `M4 immutable release index`, `Complete Tier C evidence`
  - **Expected outputs:** `Immutable domain promotion index and rollback link to engineering candidate`
  - **Exact commands:**
    1. `python -m segvision.acceptance validate-evidence --evidence evidence/$env:SEG_RUN_ID/M5-GATE`
    2. `python -m segvision.acceptance validate-state --graph openspec/changes/build-segvision-v1/acceptance/task-graph.json --state evidence/execution-state.json`
    3. `openspec validate build-segvision-v1 --strict --no-interactive`
    4. `python -m segvision.acceptance validate-contracts --change openspec/changes/build-segvision-v1`
  - **Required evidence:** `Schema-valid evidence/<run-id>/M5-GATE/evidence.json`, `Exact command lines, exit codes, and stdout/stderr SHA-256 values`, `Pre-task input hashes and post-task owned-output SHA-256 manifest`, `Focused-test and affected-regression result counts with zero hidden skips`
  - **Pass criteria:**
    - Domain promotion is traceable to an exact engineering candidate and external inputs
    - Prior engineering artifacts/evidence remain unchanged
    - All task/checklist IDs and final states validate
    - All declared commands exit zero, required outputs validate, and no file outside owned_paths changes
    - Evidence validates and records zero prohibited shortcut, hidden retry, skipped mandatory test, or weakened threshold
  - **Retry:** maximum 3 attempt(s); every retry requires a materially different evidence-based hypothesis.
  - **Fallback:** Retain PASS_ENGINEERING and the prior release index; domain promotion remains blocked or failed.
  - **Rollback boundary:** Revert only M5-GATE owned paths or select the prior verified checkpoint; preserve user files, accepted annotations, and earlier evidence.
  - **Escalation conditions:** Three materially different attempts fail and the remaining cause is an allowed autonomous-execution escalation condition
