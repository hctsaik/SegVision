## Context

SegVision v1 is a Windows x64, CPU-only, offline annotation tool. The frozen product contract is unchanged by this change: one binary foreground per image, a user-defined ROI, at most three real machine candidates, previous-state point refinement, terminal local pixel editing, explicit Accept or Needs Review, and pair-consistent full-image PNG plus JSON provenance. Core remains headless and in-memory. MobileSAM TinyViT + PyTorch CPU remains the approved correctness backend. GPU, cloud inference, VLM, DINO, SAM 2/3, HQ-SAM, automatic Accept, per-image color sliders, default-on fusion, and pixel-OR fusion remain prohibited.

`openspec/changes/build-segvision-v1/design.md` still owns those core decisions. It currently freezes **PySide6** as the isolated desktop GUI (`src/segvision/gui/`, entry point `segvision-gui`). This change does **not** rewrite ROI geometry, candidate policy, revision/stale rejection, persistence, model approval, or acceptance classifications. It replaces only the **GUI shell and desktop deployment path**: React + Vite for the annotation surface, Tauri 2 for the native host, and a Python localhost sidecar as a transport adapter over the existing application/core stack.

The existing v1 capabilities (`annotation-workflow`, `annotation-session`, `roi-geometry`, `mask-proposal-engine`, `annotation-persistence`, `offline-release`, and related specs) remain in force. The five new capabilities in this change (`desktop-protocol`, `desktop-host`, `desktop-ui`, `desktop-sidecar`, `desktop-parity-release`) add the transport, host, UI, sidecar, and cutover contracts. PySide6 stays the shipped default until hash-bound parity evidence exists; after an authorized switch it stays deprecated-in-place. Removal of PySide6 is out of scope.

Authoritative inputs for this change, in descending priority:

1. `PRD.md` frozen product rules;
2. existing v1 capability specs (behavioral truth for annotation);
3. this change's five capability specs;
4. this `design.md` (desktop architecture and ADRs);
5. `docs/react-tauri-architecture-recommendation.md` (rationale; not a license to change product semantics).

## Goals / Non-Goals

**Goals:**

- Freeze a dedicated React + Vite + Tauri 2 + Python sidecar architecture that can replace the PySide6 shell without changing annotation semantics.
- Keep Python session state the only authority for masks, candidates, jobs, revisions, Accept, Needs Review, and persistence.
- Ship a versioned localhost protocol with separate control, event, and binary data planes, generated from one OpenAPI 3.1 + JSON Schema source of truth.
- Confine new Python code to `src/segvision/application/` and `src/segvision/transport/desktop_api/`; do not fork `src/segvision/core`.
- Make production React talk only to the Tauri host; never to the sidecar port, secret, or raw filesystem.
- Package an offline Windows x64 CPU installer: Tauri app + one-folder sidecar + notices; model weights as a separate verified component.
- Require additive contract, sidecar, Vitest, real-window E2E, and clean-machine offline gates before any default-GUI switch.
- Keep existing pytest, E2E, acceptance, `validate-contracts`, `validate-evidence`, and `validate-state` gates mandatory and unmodified.

**Non-Goals:**

- Changing ROI padding, half-open `XYXY`, candidate cap, fusion default, Accept/Needs Review rules, undo semantics, or shortcut meanings.
- Rewriting or deleting PySide6 in this change.
- A portal, iframe host, tool registry, plugin runtime, Streamlit container, or generic HTTP/shell bridge.
- GPU, CUDA, cloud inference, runtime model download, telemetry, updater, or account login.
- Shared-memory or WebGL as the v1 default renderer/transport.
- Packing MVTec corpora, unapproved weights, EdgeSAM, or GPL X-AnyLabeling material.
- Inventing new latency numbers, relaxing the existing overlay/brush p95 hard gate, or fabricating human Accept / gold masks / legal signoff / Tier C evidence.
- Cloning `src/segvision/core` into the sidecar tree or making `import segvision` start a GUI or HTTP server.

## Decisions

### ADR-001 — React/Vite + Tauri 2 + Python sidecar is the target architecture

**Decision.** The target desktop architecture is:

- **React 19 + TypeScript + Vite** in `apps/desktop-ui`: dedicated annotation UI (layout, tools, canvas preview, projection of snapshots).
- **Tauri 2 (Rust) + WebView2** in `apps/desktop-host`: native window, capability grants, sidecar lifecycle, typed command/event bridge, restricted asset protocol, CSP, and production lockdown.
- **Python sidecar**: existing SegVision core, providers, runtime, adapters, and acceptance, plus a thin application service and localhost transport adapter. CPU-only PyTorch/MobileSAM stay in this process.

This is a GUI/deploy replacement, not a rewrite of the engine. Core stays importable, headless, and GUI-free. The production operator launches the Tauri executable; the host starts the sidecar. `import segvision` MUST NOT open a window, bind a port, or create a process-global session.

**Alternatives considered.**

| Option | Why rejected / deferred |
| --- | --- |
| Keep PySide6 as the long-term default | Meets v1 isolation, but the annotation surface (zoom/pan, ROI, candidates, brush, jobs, recovery) is cheaper to build and test in React. PySide6 remains until parity, then deprecated-in-place. |
| Electron + React | Mature Chromium, but larger installer/memory/update surface for an offline CPU tool. |
| Rewrite engine in Rust or TypeScript | Would duplicate ranking, geometry, MobileSAM, persistence, and acceptance. Out of scope and high risk. |
| Serve React as a public website against FastAPI | Violates offline/localhost/security contracts and makes React the owner of a remote API. |

**Relationship to v1 design.** `build-segvision-v1` Decision 2 (“GUI: PySide6, isolated from core”) remains true until `desktop-parity-release` authorizes cutover. After cutover, the default GUI is this Tauri app; isolation of core from GUI remains mandatory.

### ADR-002 — React never talks to the sidecar in production; Tauri is the only control and asset bridge

**Decision.** Production data flow is strictly:

```text
React typed client
  → Tauri invoke / host events / segvision-asset:// URIs
  → Rust host (injects per-launch secret, resolves grants)
  → Python sidecar on 127.0.0.1:<random port>
```

The production React bundle MUST NOT contain, discover, display, or persist the sidecar listen port, per-launch secret, or a sidecar base URL. The host injects authentication on the proxy and MUST NOT return that credential to the WebView.

Production sidecar:

- binds **IPv4 loopback only** (`127.0.0.1`);
- uses an **OS-assigned random port** each launch;
- authenticates with a **per-launch secret** generated by the host;
- **MUST NOT enable CORS**;
- MUST NOT serve a public HTML app or unauthenticated OpenAPI explorer.

A development-only React-direct sidecar connection, if present at all, MUST allow one exact local Vite origin and MUST NOT ship in the production installer, WebView policy, or default profile.

The host MUST NOT expose generic `read_file`, `write_file`, `run_command`, or an untyped HTTP-forward command. Allowed commands are SegVision-specific (see ADR-002a).

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| React `fetch` to localhost sidecar | Leaks port/secret into the WebView, requires CORS, and makes any local process a caller. Forbidden in production by `desktop-host` and `desktop-protocol`. |
| Wildcard CORS + “localhost is safe” | LAN-adjacent and browser-extension risk; production CORS stays off. |
| Generic Tauri HTTP/shell bridge | Turns the host into a confused-deputy. Rejected. |

#### ADR-002a — Host command allowlist and asset scheme

Production Tauri commands (names are the allowlist; unknown invokes fail):

| Command | Purpose |
| --- | --- |
| `engine_health` | Engine-ready summary without port/secret |
| `picker_open_folder` / `picker_open_file` | Native picker → opaque `grant_id` + display name |
| `datasets_open` | Open dataset by `grant_id` |
| `datasets_list_items` | Cursor page of item summaries |
| `sessions_create` / `sessions_get` | Create/read authoritative snapshot |
| `sessions_propose` / `sessions_refine` / `sessions_edit` | ROI propose, points, local-edit delta |
| `sessions_accept` / `sessions_needs_review` | Explicit outcomes |
| `jobs_cancel` | Cancel in-flight job |
| `diagnostics_export` | Redacted host/sidecar log export |

Binary images and masks use a restricted custom protocol `segvision-asset://<opaque-token>` (equivalent host-owned scheme allowed if the token rules are identical). React never receives a filesystem path. The host validates the token, then streams sidecar bytes. Requests containing `..`, `file:`, drive letters, or UNC paths are rejected.

Control JSON is small. Images, masks, embeddings, and logits MUST NOT travel as Tauri command JSON, base64, data URLs, or integer arrays.

Typed events from the host to React preserve sidecar `event_id`, `request_id`, `job_id`, `session_id`, `revision`, `kind`, and `timestamp`. The host MUST NOT synthesize `completed`, `accepted`, or save-success from process liveness.

### ADR-003 — Python session is authoritative state; all mutations use revision concurrency

**Decision.** Ownership is exclusive. There is one current mask, and it lives in the Python `AnnotationSession`.

| State | Owner | UI/host may |
| --- | --- | --- |
| Zoom, pan, hover, panel visibility, current tool | React | Update immediately |
| Uncommitted ROI / points / brush preview | React | Preview locally; submit with `session_id` + `base_revision` |
| `session_id`, `revision`, selected candidate, capabilities, warnings, durable outcome | Python session | Display snapshot only |
| Masks, candidate graph, provenance, local-edit lock, undo checkpoints | Python core/session | Fetch binary assets and summaries |
| Jobs, cancel, stale | Python runtime | Command + subscribe; never infer completion |
| Sidecar PID, port, secret, health | Tauri host | Show a redacted health summary |
| File/folder canonical paths | Tauri grant table | Return `grant_id` + display name only |
| PNG/JSON persistence, drafts, evidence | Existing Python adapters | Show confirmed save/review results |

**Mutation envelope (protocol `1.0`).** Every control request carries `protocol_version` exactly `"1.0"`. Mutations also carry a unique `request_id`. Session-scoped mutations carry `session_id` and `base_revision` equal to the current session revision. `sessions.create` omits `session_id` and sends `base_revision` `0`; success returns a new `session_id` and `revision` `1`. Non-session ops such as `datasets.open` carry `protocol_version` and `request_id` and MUST NOT invent a `session_id`. Reads (`health`, `sessions.get`) MUST NOT increment `revision`. The UI and host MUST NOT assign authoritative revisions.

If `base_revision` is not exactly the current revision, the sidecar returns `revision_conflict`, applies nothing, and the client MUST `sessions.get` before retrying. Silent overwrite is forbidden.

**`jobs.cancel` exception.** Cancel is job-scoped. It includes `protocol_version`, `request_id`, `session_id`, and `job_id`. It MUST still attempt cancel when the session revision has advanced, MUST NOT write a new snapshot or candidates, and MUST NOT fail solely as `revision_conflict` because the revision moved. Cancel is observable `cancelled`, never success.

**Dual stale rejection.** Python marks late worker results stale and MUST NOT install them. Every desktop receiver discards events whose `session_id` mismatches or whose `revision` is older than the displayed snapshot. Duplicate `event_id` values are the same event.

**Crash recovery.** Sidecar process death discards in-memory sessions. The host reports `engine_unavailable` / `recovering`, freezes mutations, keeps currently painted pixels, and MUST NOT fake completion or Accept. After restart: new port, new secret, new handshake. Restore only loader-verified persisted drafts; otherwise require `sessions.create`. React memory is never authority.

**Idempotency (implementation freeze).** A replay of a completed mutating `request_id` on the same session returns the original result without a second job or persist. Malformed or missing `request_id` is `validation_failed`. (See Open Questions if a later spec amendment prefers hard reject-only.)

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| React as mask source of truth with Python as a helper | Three copies of “current mask”; stale jobs paint over local edits. |
| OT/CRDT merge of UI and engine masks | Product forbids model overwrite of local edits; revision + reject is the contract. |
| Host-assigned revisions | Makes Rust an engine. Forbidden. |

### ADR-004 — Images and masks use a binary asset channel, not base64 JSON

**Decision.** Protocol `1.0` has three planes:

1. **Control plane** — small JSON for the frozen operation set.
2. **Event plane** — typed job/session events (`progress`, `completed`, `cancelled`, `stale`, `failed`).
3. **Data plane** — opaque short-lived asset tokens redeemed as binary bytes.

Control and event payloads MUST NOT contain images, masks, embeddings, logits, giant integer arrays, or Python tracebacks. Overlay composition happens in the UI from source image + binary mask. A precomposed overlay is never authoritative.

**Asset tokens** bind `session_id`, `revision`, kind (`source_image` | `thumbnail` | `mask`), and expiry. Tokens are unguessable and MUST NOT embed filesystem paths. `assets.get` redeems only a live matching token. Path-like values (`..`, absolute, UNC) are rejected. A valid token does not authorize arbitrary file reads.

**Default encodings (implementation freeze, not a new product metric):**

- source image / thumbnail: original bytes when already PNG/JPEG, otherwise PNG;
- binary mask: PNG with `{0,255}` pixels at the mask’s existing resolution contract (crop vs full-image as produced by the session);
- edits on the control plane: stroke/delta samples, never a full-canvas upload per mouse move.

Shared memory, memory-mapped files, and GPU IPC are **out of scope** for protocol `1.0`. Adding them requires a new protocol version or OpenSpec change.

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| Base64 images in JSON / Tauri command payloads | Inflates IPC, blocks the UI thread, and is forbidden by `desktop-protocol`. |
| Sidecar-composited overlay as the canvas truth | Splits overlay style from the frozen UI contract; specs require UI composition. |
| Shared memory in v1 | Extra security/cleanup complexity without a measured bottleneck. |

### ADR-005 — Sidecar is a one-folder offline bundle; model weights are a separate verified component

**Decision.** The shipped engine is a **versioned one-folder directory**, not a one-file PyInstaller executable:

```text
SegVision Desktop installer
├─ Tauri executable + WebView assets
├─ versioned Python sidecar directory
│  ├─ segvision-engine entrypoint
│  ├─ CPython / runtime libraries
│  ├─ CPU-only torch / MobileSAM dependencies
│  └─ component manifest + hashes + notices
├─ licenses / THIRD_PARTY_NOTICES
└─ configuration templates
```

Reasons: inspectable DLL/component hashes, no self-extract on every launch, clearer offline smoke tests, lower false-positive AV risk than a giant one-file unpacker.

**Model weights** are a separate versioned, checksum-verified offline component. The installer MUST NOT silently download weights at build, install, or first launch. Approval-status and SHA-256 verification remain a **Python** gate before deserialize. Tauri MUST NOT load tensors or treat a file-picker grant as approval. Missing or mismatched checkpoints yield a diagnostic setup / `engine_unavailable` state, not a network fetch. Unapproved artifacts are refused and quarantined.

Packaging uses an allowlist plus manifest scan. MVTec images/gold, EdgeSAM (unless written commercial approval is in the model manifest), unapproved weights, and GPL X-AnyLabeling copies MUST NOT appear in the installer. Local E2E MAY read an operator-granted MVTec tree that stays outside the package.

Tauri updater, telemetry, crash-upload, and other runtime network features default **OFF**. Required annotation paths MUST work with outbound network disabled.

Production sidecar launch is CPU-only: no CUDA/GPU device flags, no hosted inference.

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| One-file PyTorch sidecar | Hidden unpack, hard to hash, packaging gate failure by spec. |
| Bake approved weights into the installer by default | Redistribution/approval is a separate gate; missing weights must be diagnostic. |
| Runtime download of checkpoints | Violates offline-release and this change’s host/sidecar specs. |

### ADR-006 — First version Canvas2D; WebGL / shared memory only if benchmarks prove a bottleneck

**Decision.** The annotation canvas is **Canvas2D** with four logical layers:

1. source image;
2. authoritative mask overlay (application-fixed color and alpha; no per-image color sliders);
3. interaction (ROI, points, brush cursor, uncommitted strokes);
4. selection / provenance hints for the current candidate (only the selected candidate is the filled mask).

Points and pixels MUST NOT be DOM nodes. WebGL is not the default and is outside this change unless a later measured Canvas2D failure on designated reference hardware is recorded; that upgrade is a new change. Shared-memory transport is likewise out of scope for protocol `1.0`.

Coordinate conversion lives in **one tested module**:

```text
CSS pixel ↔ device-pixel ratio ↔ viewport transform (zoom/pan) ↔ full-image integer coordinate
```

ROI display and submit use the existing half-open full-image `XYXY`. Pointer-move updates local preview only. Strokes submit on pointer-up or throttled delta batches, never a full mask per move.

Existing hard UI gate is unmodified: overlay and brush input-to-frame p95 remains **strictly below 100 ms** on the designated reference machine. This change invents no new latency numbers. Shared CI timing does not satisfy that gate. Cached refine remains a best-effort target that must report a miss.

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| WebGL from day one | Extra complexity before a measured Canvas2D miss. |
| SVG/DOM per point | Will not meet dense overlay/brush interaction. |
| Pre-optimize shared memory | Forbidden as a silent `1.0` dependency. |

### ADR-007 — PySide6 is not removed until functional parity and complete E2E; after switch it stays deprecated-in-place

**Decision.** Cutover is gated, staged, and reversible.

- Until every mandatory `desktop-parity-release` scenario has passing hash-bound evidence, the documented launch command, installer default, and release notes start **PySide6**. Tauri may exist only as an explicit non-default experimental path.
- React/Tauri becomes default only after **equivalent or stronger** gates: all existing Python unit/integration/E2E/GUI/packaging/acceptance cases still pass at current thresholds, **plus** protocol contract, sidecar integration, Vitest/component, real-window desktop E2E, and clean-machine offline installer layers.
- Completing this change means at most: Tauri is default and PySide6 is **deprecated-in-place**, still in-tree and launchable for rollback. Deleting PySide6 source, tests, or launch paths fails this change.
- Engineering/domain verdicts MUST NOT claim the new GUI is default until parity evidence exists. No `PARTIAL_PASS` / skip-to-green labels. Scripted E2E Accept records `acceptance_actor=scripted_test` and is not Tier C.
- Missing Tier C input MUST NOT block this engineering GUI-shell change and MUST NOT be fabricated.

Existing `segvision-gui` / `src/segvision/gui/` remains the PySide6 path. The importable `segvision` package stays GUI-free.

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| Delete PySide6 as soon as Tauri launches | Leaves no rollback; forbidden by `DPR-R003`. |
| Dual default / unmarked installer choice | Would advertise Tauri before parity. |
| Weaken or xfail PySide6 GUI tests during migration | Forbidden; existing contracts stay mandatory. |

### ADR-008 — SegVision is a dedicated app, not a portal / iframe / plugin runtime

**Decision.** The desktop product is a **dedicated annotation application**. Cold launch presents the SegVision workspace only. The host and UI MUST NOT provide a tool registry, plugin loader, iframe/microfrontend container, Streamlit host, or remote-document embedding.

Implementers MAY reuse `nativeApp` **engineering** patterns: Vite workspace, Tauri 2 host, Python sidecar packaging, random localhost port, health/readiness, hidden child process, stdout/stderr capture, graceful shutdown, crash detection, file-picker grants, shared protocol, Vitest, real desktop E2E.

They MUST NOT copy `nativeApp` **product** structure: portal, tool registry, iframe tools, wildcard origin, production mock-auth, React knowledge of sidecar port/secret/absolute paths, or JSON/base64 full images.

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| Embed SegVision as one tool in a portal | Conflicts with CSP, navigation lock, and dedicated-app specs. |
| Load arbitrary local HTML as plugins | Turns WebView into a browser; rejected. |

### ADR-009 — OpenAPI 3.1 + JSON Schema events are the single protocol source of truth

**Decision.** Protocol version is the string `1.0` with **exact** match. `"1"`, `"1.0.0"`, `"1.1"`, and `"v1.0"` are incompatible (`protocol_version_mismatch`). Missing/empty/unknown versions fail closed with no session, job, persist, or asset side effects.

**Normative files** live in `packages/desktop-protocol/`:

- `openapi.yaml` — OpenAPI 3.1 for control-plane requests, responses, and error objects;
- `events.schema.json` — JSON Schema union of event-plane kinds.

TypeScript, Rust, and Python consume that source. They MUST NOT each hand-write divergent operation names, event kinds, or error codes.

- **TypeScript:** generated client/types (for example `openapi-typescript`) used by `apps/desktop-ui`.
- **Python:** load and validate the published schemas at sidecar **startup** and in contract tests; reject schema-invalid requests before mutation.
- **Rust:** serde types whose enums/required fields are checked by the same contract tests against the published schemas.

A green protocol contract suite is required before a protocol change is complete. Extra/missing/renamed operations, `kind` values, or error codes fail the suite.

**Frozen conceptual operations** (transport shape only; mapped onto existing application/core methods with no second ranking/geometry/validation implementation):

`health`, `datasets.open`, `datasets.list_items`, `sessions.create`, `sessions.get`, `sessions.propose`, `sessions.refine`, `sessions.edit`, `sessions.accept`, `sessions.needs_review`, `jobs.cancel`, `assets.get`.

Unknown operations return `unsupported_operation` and are not forwarded to core, GPU, or a remote service.

**HTTP mapping (sidecar, host-only).** FastAPI implements these routes behind the host. React never calls them in production.

| Operation | HTTP |
| --- | --- |
| `health` | `GET /v1/health` |
| `datasets.open` | `POST /v1/datasets/open` |
| `datasets.list_items` | `GET /v1/datasets/{dataset_id}/items` |
| `sessions.create` | `POST /v1/sessions` |
| `sessions.get` | `GET /v1/sessions/{session_id}` |
| `sessions.propose` | `POST /v1/sessions/{session_id}/proposals` |
| `sessions.refine` | `POST /v1/sessions/{session_id}/refinements` |
| `sessions.edit` | `POST /v1/sessions/{session_id}/edits` |
| `sessions.accept` | `POST /v1/sessions/{session_id}/accept` |
| `sessions.needs_review` | `POST /v1/sessions/{session_id}/needs-review` |
| `jobs.cancel` | `POST /v1/jobs/{job_id}/cancel` |
| `assets.get` | `GET /v1/assets/{token}` (binary, not JSON) |

**Event plane.** The sidecar exposes an authenticated loopback **SSE** stream consumed **only by the Tauri host** (not a React production URL). The host forwards typed Tauri events. SSE is not a twelfth control-plane operation in the React client. WebSocket is not required for `1.0`.

**ASGI.** FastAPI is the sidecar HTTP stack (schema/OpenAPI/testability). It remains a private desktop transport, not a public website. Starlette-only is an allowed equivalent if it validates the same schemas; FastAPI is the default.

**Authentication header (host → sidecar):** `X-SegVision-Launch-Secret`. Never logged, persisted, or returned to React.

**Frozen UI error codes:** `protocol_version_mismatch`, `revision_conflict`, `unauthorized`, `engine_unavailable`, `validation_failed`, `unsupported_operation`, `not_found`, `stale_job`. The UI contract is `code` + operator-safe message. Tracebacks are host-local logs only.

**Core exception mapping (implementation freeze; see Open Questions for gaps):**

| Existing typed failure | Protocol `code` |
| --- | --- |
| Envelope/schema/`protocol_version` problems | `protocol_version_mismatch` or `validation_failed` as specified |
| Missing/invalid launch secret | `unauthorized` |
| Unknown session/job/dataset/asset | `not_found` |
| `base_revision` mismatch before core apply | `revision_conflict` |
| Late/superseded job apply or fetch | `stale_job` |
| `InvalidRoi`, `RecipeSchemaError`, `RecipeClassMismatch` | `validation_failed` |
| `UnsupportedOperation` | `unsupported_operation` |
| `BackendUnavailable` / model not ready | `engine_unavailable` |
| Windows path/read-only/locked/disconnected drive | stable `code` plus actionable message; UI process must not crash |

`StaleRevision` from core after the adapter already treats envelope conflicts as `revision_conflict` maps to `stale_job` when it refers to a job/result, not a client `base_revision` mismatch. `EmbeddingExpired` mapping is an Open Question.

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| Three hand-written enums (TS/Rust/Python) | Spec-forbidden drift. |
| gRPC / Cap’n Proto | Extra toolchain; JSON + binary assets meet the frozen ops. |
| WebSocket as the only plane | Mixes control and events; SSE keeps events one-way and host-owned. |

### ADR-010 — Repository layout (do not clone Python core into the sidecar tree)

**Decision.** Layout:

```text
SegVision/
├─ apps/
│  ├─ desktop-ui/                 # React 19 + Vite + TypeScript
│  └─ desktop-host/
│     └─ src-tauri/               # Tauri 2 / Rust host
├─ packages/
│  └─ desktop-protocol/           # OpenAPI 3.1, event JSON Schema, generated TS client
├─ src/segvision/
│  ├─ core/                       # existing pure core — do not copy
│  ├─ providers/
│  ├─ runtime/
│  ├─ adapters/
│  ├─ cv/
│  ├─ gui/                        # existing PySide6; remains until a later removal change
│  ├─ application/                # NEW: desktop use-case orchestration
│  └─ transport/desktop_api/      # NEW: sidecar adapter + explicit entrypoint
├─ tests/
│  ├─ unit/
│  ├─ contract/                   # protocol schema/bindings
│  ├─ integration/                # real localhost sidecar
│  └─ desktop-e2e/                # real Tauri window
└─ openspec/
```

The packaged sidecar directory **imports the same** `segvision` package (installed or bundled from `src/segvision`). It MUST NOT contain a forked copy of `core`. Sidecar HTTP starts only via an explicit entrypoint invoked by the host (for example `python -m segvision.transport.desktop_api` in development, and `segvision-engine` in the one-folder bundle). `import segvision` stays inert.

New tests are additive. Existing pytest node IDs, thresholds, and GUI driver contracts for PySide6 remain.

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| Copy core into `apps/desktop-host/sidecar/` | Immediate fork; ranking/geometry would diverge. |
| Put React under `src/segvision/gui/` | Mixes Python package with WebView assets; breaks GUI-free import. |
| New Python package name for the sidecar | Splits application service from the importable product. |

### ADR-011 — Unidirectional dependency

**Decision.** Allowed compile/import direction:

```text
React UI → Tauri Host → Desktop Transport → Application Service → Core / Providers / Runtime / Adapters
```

Rules:

- `src/segvision/core` MUST NOT import GUI, Tauri, WebView, HTTP handlers, or `segvision.transport.desktop_api`.
- Providers, runtime, adapters, and acceptance MUST NOT depend on React, Tauri, or browser objects.
- Transport MAY depend on application; application MAY depend downward on core/runtime/adapters/acceptance.
- Tauri MUST NOT reimplement ranking, ROI, mask merge, Accept eligibility, or tensor parsing.
- React MUST NOT own embeddings, logits, checkpoints, authoritative masks, job-completion inference, raw paths, or shell execution.
- Application service sequences use cases (dataset open, paging, session create/close in-process, propose/refine/edit, jobs, persistence, evidence, drafts) without reimplementing candidate validation, ranking, duplicate filtering, ROI padding, morphology, fusion, or recipes.

Heavy inference stays on the existing CPU runtime worker with bounded threads. The ASGI event loop MUST NOT run encoder/decoder work. Health, cancel, and snapshot remain schedulable during inference. One approved model instance and the existing bounded embedding cache per sidecar process; encodings never leave Python.

**Alternatives considered.**

| Option | Why rejected |
| --- | --- |
| Bidirectional “engine callbacks into React” | Couples core to WebView lifetime. |
| Second FastAPI-thread model call | Violates single-instance / runtime-job contracts. |

### Additional implementation freezes

#### UI stack and store

- React 19, TypeScript strict, Vite, Vitest + Testing Library.
- Global store holds only small JSON-serializable view models: `session_id`, `revision`, selected candidate id, current tool, viewport transform, panel visibility, recovery status, dataset list summaries, candidate card summaries (ids, capabilities, scores as provided).
- Decoded bitmaps live in an asset cache for Canvas, not in the global store.
- Uncommitted stroke samples stay in local interaction state until submit.
- Default store library: a small typed Zustand store (or an equivalent reducer module). It is not a second engine.
- Frozen shortcuts match `annotation-workflow` UIW-R009: `1`/`2`/`3`, left/right clicks, `B`, `[`/`]`, `F`, `X`, `Z`, `Space`, `N`; erase remains an explicit control. `N` stays disabled until durable `ACCEPTED` or durable `NEEDS_REVIEW`.
- Accept is explicit only. High score, 30s timer, idle, or job completion MUST NOT auto-accept.
- Fusion, if exposed, defaults off, never pixel-OR, invalidated by the first human point.
- Timer origin remains the Python session; the UI displays it.

#### Host lifecycle

- Hidden Windows sidecar process (no console window in normal operator flow); stdout/stderr captured.
- Health-check before exposing engine-ready.
- On crash: `engine_unavailable`/`recovering`, freeze mutations, keep pixels, new handshake after restart.
- On app close: graceful shutdown first; if the sidecar has not exited within a host-configured timeout (default **5 seconds**), terminate; retain redacted diagnostic logs.
- Production: CSP denies remote scripts, frames, wildcard origins, and arbitrary `connect-src`; devtools off; external navigation forbidden; WebView loads only packaged UI plus host asset protocol.
- Grants: picker stores canonical path in a host-private table; React sees `grant_id` + display name. Dataset open resolves the grant in Rust, then the sidecar verifies existence, format, manifest, and required hashes using existing contracts.
- Unicode, spaces, long paths, read-only directories, disconnected drives, and locked files map to stable errors without hanging the UI thread.

#### Test layers required before default cutover

| Layer | Must prove |
| --- | --- |
| Existing Python unit/integration/E2E/GUI/packaging/governance | Unmodified thresholds; `validate-contracts` / `validate-evidence` / `validate-state` still bind hashes |
| Protocol contract | Schema round-trip; TS/Rust/Python enums and error codes agree |
| Sidecar integration (real process) | Health, session, cancel, stale rejection, binary assets (not JSON/base64), crash handshake |
| React unit/component | Tools, 0–3 cards, recovery, DPR/zoom/pan coordinates |
| Real-window desktop E2E | Injected mouse/keyboard/picker; oracles are session/revision/event/hash, not store mocks or screenshots alone |
| Offline installer on clean Windows x64, network blocked | Install, launch, sidecar ready, local model when present, scripted Accept and Needs Review, save/reload, Unicode paths, uninstall smoke |

Desktop E2E minimum paths are those listed in `DPR-R010` (open+overlay, Tier-1 ROI ≤3 candidates, points+revision, local-edit lockout, Accept vs Needs Review, stale after rapid ROI/cancel/switch, crash recovery, missing/bad checksum model, read-only output, offline network).

Screenshots are forensic only.

## Risks / Trade-offs

| Risk | Mitigation |
| --- | --- |
| React, Rust, and Python each keep a “current mask” | Python snapshot + `base_revision` / `revision_conflict`; UI yields to newer snapshots; no local pixel authority |
| Fast ROI/cancel/image-switch lets old inference paint | Full `request_id` / `job_id` / `session_id` / `revision` chain; dual stale rejection; cancel ≠ success |
| Large image/mask IPC stalls WebView | Binary tokens, UI composition, bounded asset cache; shared memory only after measured failure |
| Canvas coordinates drift from core `XYXY` | Single mapping module; property tests for DPR/zoom/pan/half-open round-trip |
| PyTorch sidecar size and cold start | One-folder bundle, one model instance, readiness via health, clean-VM smoke; no invented latency claims |
| Localhost called by other processes | Random port, per-launch secret, Rust-only proxy, no production CORS, loopback bind |
| Sidecar crash loses unsaved work | Freeze UI, keep pixels, re-handshake, restore only verified drafts |
| Windows paths, AV, DLL load | Unicode/long-path/locked-file tests; component hashes; installer smoke; hidden process with captured logs |
| Licensed content packed by mistake | Allowlist + manifest scan; MVTec/weights separated; notices/SBOM for Tauri, WebView2, React, Vite, Rust crates, Python sidecar |
| GUI migration breaks v1 acceptance | Core untouched; staged parity; PySide6 stays; no weakened tests |
| Dev CORS or direct-connect ships | Production profile fails closed if CORS/devtools/direct-connect enabled |
| Agent marks cutover without evidence | Parity capability + verdict rules; screenshot-only cases fail validation |

Trade-off accepted: three processes (WebView, Rust host, Python engine) add operational complexity versus in-process PySide6. The gain is a testable annotation UI and a hard security boundary, without moving algorithm truth out of Python.

## Migration Plan

Adoption is independently verifiable and reversible. Completing an early stage MUST NOT delete PySide6 or change the default GUI. A later stage MUST NOT be marked passed if an earlier required stage lacks evidence. Rollback restores the prior verified host/UI/sidecar/installer artifact and keeps its evidence.

1. **OpenSpec freeze (this change)** — protocol, host, UI, sidecar, and parity contracts; this design.
2. **Protocol and host skeleton** — `packages/desktop-protocol`, generated TS client, FastAPI health/handshake, Tauri spawn/health/shutdown/logs, typed errors, loopback + secret, CSP/allowlist stubs. Evidence: contract tests + sidecar health integration.
3. **Read-only dataset viewer** — folder grant, paging, image + mask overlay, coordinate module tests. No mutation yet. Evidence: grant opacity, binary assets, overlay composition.
4. **Full annotation loop** — ROI, ≤3 candidates, points, local-edit deltas, cancel/stale, frozen shortcuts, fake backend. Evidence: sidecar integration + Vitest + first real-window E2E subset.
5. **Persistence and recovery** — Accept, Needs Review, pair-consistent PNG/JSON, drafts, crash/reopen. Evidence: hashes, `training_eligible=false` for review, recovery handshake.
6. **MobileSAM and authorized local dataset E2E** — focused then Tier A/B paths against operator-granted local data; MVTec stays outside the package. Existing real-model gates remain. Evidence: same oracles as v1, plus desktop driver.
7. **Offline installer and security gates** — one-folder sidecar, notices/SBOM, allowlist scan, updater/telemetry off, clean Windows x64 with outbound network blocked.
8. **Default GUI switch** — only after every mandatory parity scenario has hash-bound evidence. Document Tauri as default; mark PySide6 deprecated-in-place. Update launch docs and installer default. Do not remove `src/segvision/gui/`.
9. **Later change (out of scope)** — after a stable deprecated period, a new OpenSpec change may remove PySide6. Not a completion condition here.

Development workflow during stages 2–7: optional Vite exact-origin direct-connect for UI iteration; production path always host-mediated. Experimental Tauri launch is explicit and cannot satisfy a default-GUI release claim.

## Open Questions

These were spec or external-input gaps. Spec amendments in this change closed items 1–4. Implementers MUST NOT silently change public annotation behavior to resolve remaining items.

1. **Unexpected-exception error code.** **Decided.** The eight sidecar JSON UI codes remain exhaustive. Untyped exceptions MUST NOT leak tracebacks and MUST map to one of those eight; DSS-R004-S02 uses `engine_unavailable` when the sidecar cannot serve. Do not add `internal-failure` or a ninth public `1.0` code.

2. **`sessions.close` vs frozen operations.** **Decided.** DTP-R002 includes `sessions.close` in the frozen `1.0` operation set, together with `sessions.select`, `sessions.undo`, `sessions.begin_manual_empty`, `sessions.lock_roi`, `sessions.expand_roi`, and `sessions.acknowledge_warning`.

3. **`EmbeddingExpired` mapping.** **Decided.** DTP-R016 maps `EmbeddingExpired` to `stale_job`. Late-job `StaleRevision` also maps to `stale_job`; client `base_revision` behind the current snapshot maps to `revision_conflict`.

4. **Host-only event subscription.** **Decided.** Production event plane is sidecar emission on loopback using host-owned SSE or an equivalent host-only HTTP channel authenticated with the per-launch secret. Tauri forwards typed events. React MUST NOT subscribe to sidecar event URLs. Shared memory remains out of `1.0`.

5. **Idempotent `request_id` replay.** DSS-R002-S05 allows **either** reject **or** return the original result. This design freezes original-result idempotency for completed mutations on the same session. If product owners want reject-only, amend the sidecar spec.

6. **External inputs (not GUI-shell blockers).** Commercial redistribution approval for model weights and new desktop-stack licenses; designated reference CPU if it differs from the agent host; Tier C representative images, independent gold, and real annotators. Absence keeps `domain_validated=false` and MUST NOT fail this engineering change or be fabricated.

Related protocol freeze recorded by the spec amendment (not left open): `sessions.create` opens a desktop protocol session in `IMAGE_OPEN` at protocol `revision` `0` without `SegVisionEngine.start`; `sessions.lock_roi` is the only operation that calls `start` and mints core revision `1`.

No unresolved preference blocks implementation of protocol, host skeleton, fake-backend annotation loop, or packaging work that does not require those external inputs.
