# SegVision v1 implementation handoff

This repository contains a CPU-first, headless annotation core with a thin
optional desktop shell.  The core accepts an injected backend and keeps model
state, revision barriers, crop geometry, candidate ranking, local edits, undo,
acceptance validation, and review outcomes in memory.  Filesystem persistence,
model acquisition, evidence, and GUI concerns are adapters.

## Runtime flow

1. Construct `SegVisionEngine` with `FakeBackend` for deterministic tests or
   an explicitly approved `MobileSAMCPUBackend`.
2. Start a session with a `uint8[H,W,3]` RGB image, image/class IDs, and a
   full-image half-open ROI.
3. Call `propose()`; the session encodes once per crop revision, returns at
   most three real candidates, and exposes crop-edge/disagreement masks.
4. Select a candidate, refine with full-image foreground/background points,
   or use brush/erase/grow/shrink/fill-holes.  Local edits lock out model
   mutation until `undo()` restores a model checkpoint.
5. Call `accept()` only after warning acknowledgement, then save the
   `CommitResult` through `AcceptedStore`; use `ReviewStore` for
   `needs_review()` outcomes.  Save failures retain the session and expose a
retry path.

In the React/Tauri canvas, `＋ 補選` sends a foreground point to MobileSAM and
`－ 排除` sends a background point. Right-clicking while `＋ 補選` is active is
also a background-point shortcut. Successful refinements reuse the current
crop embedding and display green `+` and red `−` prompt markers on the canvas.
Candidate warnings are aggregated by warning code, shown once, and translated
into actionable Traditional Chinese in the desktop UI. Crop-edge warnings stay
visible because expanding ROI or explicitly acknowledging the risk is required
before Accept; the application does not silently alter ROI geometry.
If a MobileSAM refinement output violates a foreground/background point, the
core rejects that output and rolls back the attempted point. The desktop UI
keeps the prior valid mask and presents a recoverable Traditional Chinese hint
instead of exposing the internal candidate-validation diagnostic.
The MobileSAM adapter requests source-resolution logits and normally applies
the model's fixed threshold. For human refinement only, if that threshold
violates a point, the adapter selects the nearest feasible logit threshold that
satisfies every accumulated foreground/background point. It records the
applied threshold in the backend ledger and never paints prompt pixels into the
mask or performs another encode.

The optional PySide6 shell in `segvision.gui.app` only translates mouse,
keyboard, and button events to `AnnotationController`.  It is not imported by
the headless package and never handles tensors or persistence directly.

## Verification and delivery

Use the repository CPython 3.11 x64 environment:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m segvision.acceptance validate-contracts --change build-segvision-v1
.venv\Scripts\python.exe -m segvision.acceptance validate-state --state evidence\execution-state.json
.venv\Scripts\python.exe -m segvision.acceptance execute --max-tasks 1
```

`execute` is fail-closed: it schedules only dependency-ready tasks, resolves
bare Python tools to `.venv`, records command/output hashes, validates
contracts/evidence/state before publishing a checkbox, and emits machine-
readable blocker artifacts for external gates.  The acceptance runner executes
the manifest's Tier A/B/C pytest nodes without hidden retries.  Offline output
is `dist/offline/segvision-offline-bundle.zip`; verify it with
`segvision.acceptance.offline.verify_offline_bundle`.

The current release evidence is kept under
`evidence/sv-20260828T005825Z-93d6f1c2/`.  It records 94/94 mandatory scenarios
passing.  Release classification remains fail-closed until the official
MobileSAM approval/checksum and designated reference-machine evidence are
provided; those are external gates, not simulated by this implementation.
