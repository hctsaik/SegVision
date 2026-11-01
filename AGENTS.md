# SegVision AI Agent Instructions

## Mission

Implement SegVision v1 autonomously from the active OpenSpec change. Continue until every safe runnable task is complete and machine-verifiable evidence exists. Do not stop after planning while implementation work remains.

## Source priority

1. `PRD.md` frozen product decisions.
2. `openspec/changes/build-segvision-v1/specs/*/spec.md` behavioral contracts.
3. `openspec/changes/build-segvision-v1/design.md` architecture.
4. `openspec/changes/build-segvision-v1/tasks.md` execution order.
5. `openspec/changes/build-segvision-v1/e2e-acceptance.md` and `acceptance/*` gates.
6. `docs/final-development-recommendation.md` background and rationale.

If these sources conflict, stop only if the conflict changes public behavior. Otherwise follow the highest-priority source and record the lower-priority discrepancy.

## Startup

1. Read all files listed above and `openspec/changes/build-segvision-v1/autonomous-execution.md`.
2. Run:

   ```powershell
   openspec validate build-segvision-v1 --strict --no-interactive
   openspec status --change build-segvision-v1
   ```

3. Preserve pre-existing user files and changes.
4. If the `SCAFFOLD` checkpoint exists, prepend `.venv\Scripts` to the process `PATH` and verify that `python` is the repository CPython 3.11 x64 environment; do not use the ambient host Python for project commands.
5. Resume the first unchecked task whose dependencies are satisfied.
6. Use focused tests, then affected regressions, then evidence validation.

Once the repository-owned acceptance CLI exists, also run `validate-contracts` and `validate-state` during startup. The task that first implements these commands MUST execute them successfully before its own checkbox is marked.

## Completion discipline

- Mark a `tasks.md` checkbox only after implementation, required tests, documentation, and evidence are complete.
- A prose summary is not evidence.
- Do not skip, xfail, weaken, delete, or rewrite a required test/threshold to obtain green status.
- Keep task evidence under `evidence/<run-id>/<task-id>/` using the prescribed schema.
- Run OpenSpec strict validation after spec/task changes.
- Keep core headless and in-memory; GUI and filesystem adapters remain outside core.

Before marking any task checkbox, run all three commands against the current change, task evidence, and proposed execution state:

```powershell
python -m segvision.acceptance validate-contracts --change build-segvision-v1
python -m segvision.acceptance validate-evidence --evidence evidence\<run-id>\<task-id>\evidence.json
python -m segvision.acceptance validate-state --state evidence\execution-state.json
```

Before emitting or changing a release verdict, run the same contract and state validators plus `validate-evidence` against the complete run directory. A checkbox or verdict is invalid if any command is missing, non-zero, or refers to different source, task-graph, profile, or evidence hashes.

## Defaults and autonomy

Use the normative defaults in `design.md` and `acceptance/acceptance-profile.json`. Do not ask the user about routine implementation choices that those documents already decide.

Milestones are fixed: M0 governance/scaffold; M1 pure core plus fake backend; M2 approved MobileSAM CPU backend; M3 runtime, GUI, and persistence; M4 fixed CV plus complete Tier A/B acceptance, offline package, and engineering verdict; M5 optional domain promotion. M0 documents and M1 fake/core work may proceed in parallel. Missing model/data/human inputs do not block independent tasks.

Every run SHALL record `target_release_class` as `engineering` or `domain`; use `engineering` when no explicit repository-owned target is present. An engineering target requires M0 through M4 and is not blocked by missing Tier C/M5 input. A domain target requires M0 through M5; when M0 through M4 pass but Tier C promotion input is missing, retain `engineering_accepted=true`, keep `domain_validated=false`, emit the applicable blocked verdict, and use `project_state=implementation_complete_release_blocked`.

## Hard prohibitions

- No GPU, cloud inference, remote service, VLM, DINO, SAM 2/3, HQ-SAM, multi-provider hot path, or automatic Accept.
- No per-image color sliders, default OR, more than three candidates, cloned filler candidates, or model overwrite after local edit.
- No unapproved/checksum-invalid model; no commercial EdgeSAM without written permission; no unapproved GPL copy.
- No fabricated performance, gold mask, human Accept, user study, legal approval, or release signoff.
- No destructive reset/checkout/cleanup of user work.

## Verdict and project-state semantics

- `PASS_ENGINEERING`: the engineering target completed M0 through M4; `project_state=complete`, `engineering_accepted=true`, and `domain_validated=false`.
- `PASS_DOMAIN_VALIDATED`: the domain target completed M0 through M5; `project_state=complete`, and both classifications are true.
- `BLOCKED_EXTERNAL_INPUT`, `BLOCKED_LICENSE`, or `BLOCKED_REFERENCE_HARDWARE`: a required external gate for the declared target is unavailable after all independent work completes; `project_state=implementation_complete_release_blocked`. A domain-target promotion blocker MAY retain `engineering_accepted=true` when M0 through M4 still pass.
- `FAIL`: use only after every independent runnable task is exhausted and a mandatory non-external gate remains finally failed or its owning task is `rejected` after the allowed materially different attempts; `project_state=failed`.

Do not report `FAIL` while independent work remains runnable, and never turn missing Tier C input into a blocker for an engineering target. Never relabel `implementation_complete_release_blocked` as a passing release.
