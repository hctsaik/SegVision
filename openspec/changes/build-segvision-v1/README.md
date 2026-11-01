# build-segvision-v1

Implement the complete CPU-only SegVision v1 annotation workflow with machine-verifiable E2E acceptance and autonomous AI-agent delivery gates.

## Implementation handoff

Read in this order:

1. `proposal.md` — scope and product outcome.
2. `design.md` — frozen architecture and implementation decisions.
3. `specs/*/spec.md` — 141 normative requirements with stable IDs and scenario contracts.
4. `e2e-acceptance.md` — human-readable Tier A/B/C acceptance rules.
5. `acceptance/README.md` — machine-contract index and validation semantics.
6. `acceptance/e2e-cases.json` and `acceptance/traceability.json` — exact pytest nodes, actors, oracles, evidence, and every normative scenario mapping.
7. `tasks.md` and `acceptance/task-graph.json` — the same 74-task M0–M5 plan in human and executable DAG forms.
8. `autonomous-execution.md` — startup, retry, evidence, rollback, blocker, resume, and completion protocol.

All task checkboxes intentionally remain unchecked because this change defines the work; it does not claim the product has already been implemented. The next agent starts at P00 and selects the lowest runnable task whose dependencies pass.

## Completion meaning

- Default target: `engineering`.
- `PASS_ENGINEERING` requires M0–M4, all mandatory Tier A/B cases, approved model and release authority, the designated reference targets, and clean offline verification.
- `PASS_DOMAIN_VALIDATED` additionally requires M5, approved representative real data, independent gold, real annotator sessions, independent review, and signoff.
- An AI may verify and transcribe attributable evidence but must never invent an approval, hardware result, gold mask, human decision, or signoff. Missing external input blocks only its dependent release target while independent tasks continue.

## Authoring validation

```powershell
openspec validate build-segvision-v1 --strict --no-interactive
openspec status --change build-segvision-v1
```

After the M0 acceptance CLI exists, every task pass and release verdict also requires `validate-contracts`, `validate-evidence`, and `validate-state` as defined by the task graph execution contract.
