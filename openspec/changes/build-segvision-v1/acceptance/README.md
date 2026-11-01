# SegVision v1 machine acceptance contracts

This directory is the machine-readable companion to `../e2e-acceptance.md`. Markdown explains intent; these JSON instances and schemas decide whether an autonomous run may mark a task or release as passed.

## Frozen inputs

- `acceptance-profile.json`: exact functional, timing, performance, storage, real-backend, domain, and offline thresholds.
- `default-annotation-policy.json`: immutable versioned visible-pixel annotation semantics. Domain approval is a separate, attributable field in the domain-input manifest so approval metadata cannot change the policy content hash.
- `e2e-cases.json`: mandatory Tier A/B/C case definitions, exact pytest nodes, actors, steps, oracles, and evidence.
- `traceability.json`: one entry for every normative OpenSpec scenario and reciprocal links to E2E cases.
- `task-graph.json`: executable M0–M5 DAG. `../tasks.md` is its human-readable projection.

Any semantic change to these inputs requires review as a contract change. A test runner MUST NOT silently replace thresholds, drop mandatory cases, or substitute a different policy.

## Runtime and evidence schemas

| Contract | Purpose |
|---|---|
| `execution-state.schema.json` | resumable task states and declared release target |
| `checkpoint.schema.json` | immutable passed-task checkpoint |
| `blocker.schema.json` | bounded escalation and safe continuation |
| `evidence.schema.json` | task/case/gate evidence with hashes and command outcomes |
| `run-manifest.schema.json` | self-describing acceptance run |
| `scenario-results.schema.json` | one non-retried result per executed E2E case |
| `session-events.schema.json` | canonical workflow event stream |
| `call-ledger.schema.json` | backend, CV, GUI, and filesystem calls |
| `performance-report.schema.json` | fingerprinted latency and resource measurements |
| `quality-report.schema.json` | engineering and domain quality outcomes |
| `release-verdict.schema.json` | target, verdict, project state, labels, gates, and bound hashes |

## Product data schemas

- `accepted-sidecar.schema.json`: training-eligible accepted annotation and full provenance.
- `review-sidecar.schema.json`: durable review-only disposition, never training eligible.
- `cv-recipe.schema.json`: immutable class-level deterministic CV recipe.
- `annotation-policy.schema.json`: annotation-policy contract.

## External inputs

Files under `external-gates/` are fail-closed templates. An AI may verify technical facts and content hashes, but it may not invent organizational license authority, designated hardware, annotation-policy approval, representative domain data, independent gold masks, real annotator sessions, independent review, or release signoff.

- A default `engineering` target ignores missing Tier C-only inputs, but still requires all applicable model, license, reference-machine, and offline Tier B gates.
- A `domain` target may retain `engineering_accepted=true` while promotion is blocked. It may not emit `PASS_DOMAIN_VALIDATED` until every Tier C input and threshold passes.

## Mandatory validator order

After the acceptance CLI is implemented, every task pass and release verdict runs:

```powershell
python -m segvision.acceptance validate-contracts --change build-segvision-v1
python -m segvision.acceptance validate-evidence --evidence <evidence-file-or-run-directory>
python -m segvision.acceptance validate-state --state evidence\execution-state.json
```

`validate-contracts` MUST perform JSON Schema checks plus cross-file semantic checks that JSON Schema alone cannot express:

1. unique requirement, scenario, E2E, task, and checklist IDs;
2. exact human/machine E2E ID equality;
3. every requirement/scenario/E2E/task reference exists and reciprocal links agree;
4. every normative scenario appears exactly once in traceability;
5. task dependencies exist, the graph is acyclic, and only passed dependencies unlock a task;
6. task/checklist projections and owned-file rules agree;
7. CV range ordering, geometry/dimension invariants, sidecar hashes, and policy hashes are valid;
8. verdict classifications, target release class, project state, applicable gates, and bound hashes agree;
9. blocked and passed evidence satisfy their conditional requirements;
10. no mandatory test, threshold, actor provenance, or external authority is fabricated or omitted.

The canonical `specs_sha256` is SHA-256 over a byte stream formed by sorting every `specs/*/spec.md` by POSIX relative path and appending, for each file, `relative_path + "\n" + UTF-8 file bytes`.

All implementation tasks intentionally begin unchecked. These authoring artifacts are plans and contracts, not evidence that SegVision has already been implemented or accepted.
