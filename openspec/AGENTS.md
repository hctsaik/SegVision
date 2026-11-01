# OpenSpec Authoring and Execution Rules

- Active change: `build-segvision-v1`.
- Specs are behavior-first and use `## ADDED Requirements`, `### Requirement:`, and exact `#### Scenario:` headings.
- Every requirement uses SHALL/MUST and has at least one WHEN/THEN scenario.
- Implementation details belong in `design.md` or `tasks.md`, not behavioral requirements.
- Every task is a `- [ ] X.Y ...` checkbox and is small enough for one focused implementation session.
- Mark tasks complete only with implementation, focused tests, regression tests, documentation, and schema-valid evidence.
- Run `openspec validate build-segvision-v1 --strict --no-interactive` after any OpenSpec edit.
- Do not archive while a required task is unchecked or a mandatory acceptance gate is missing.
- Release labels and external blockers follow `autonomous-execution.md`; never fabricate Tier C inputs.
