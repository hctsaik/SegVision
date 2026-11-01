## ADDED Requirements

### Requirement: [OFR-R001] CPU-only release composition
Every SegVision v1 release package SHALL target Windows x64 CPU execution and MUST operate without CUDA, a GPU driver, a GPU runtime, or a hosted inference service. The dependency lock and installed environment MUST NOT contain a GPU-only runtime or a package selected solely to enable GPU execution.

#### Scenario: [OFR-R001-S01] CPU-only dependency inspection succeeds
- **WHEN** release verification inspects the locked dependencies and a clean installed environment
- **THEN** it SHALL find only the approved CPU inference path
- **AND** it SHALL find no required CUDA, NVIDIA, GPU-specific ONNX Runtime, or remote-inference dependency

#### Scenario: [OFR-R001-S02] GPU dependency is introduced
- **WHEN** a release candidate contains a required GPU runtime or cannot launch without a GPU
- **THEN** the offline release gate MUST fail
- **AND** the candidate MUST NOT receive a release label

### Requirement: [OFR-R002] Offline installation and runtime
The release bundle SHALL contain or reference a prepared, checksum-verified local supply of every artifact needed to install and run the common package and GUI. After that bundle is prepared, installation, GUI launch, model loading, annotation, Accept, Needs Review, save, and reload MUST succeed with network access disabled and MUST NOT require an account login.

#### Scenario: [OFR-R002-S01] Clean machine has no network access
- **WHEN** an operator installs the release bundle on a clean supported Windows machine with outbound network access disabled
- **THEN** the common package SHALL import and the GUI SHALL launch
- **AND** the scripted annotation workflow SHALL complete without a download, login, or remote request

#### Scenario: [OFR-R002-S02] Runtime attempts an online dependency
- **WHEN** any required runtime path attempts to download a model, contact a hosted service, or request account authentication
- **THEN** offline verification MUST fail
- **AND** the release candidate MUST remain unaccepted

### Requirement: [OFR-R003] Importable package and launchable GUI
The release SHALL provide a versioned Python distribution that another project can import and a documented local command or entry point that launches the thin GUI. Importing the common package MUST NOT initialize the GUI, open files, download models, or create a hidden process-global model session.

#### Scenario: [OFR-R003-S01] Consumer imports the wheel
- **WHEN** a clean environment installs the built wheel and executes `import segvision`
- **THEN** the import SHALL succeed without filesystem, network, GUI, or model-loading side effects
- **AND** the documented GUI entry point SHALL remain independently launchable

### Requirement: [OFR-R004] Locked and reproducible dependency set
The release process SHALL pin the exact Python and runtime dependency versions used to build and verify the candidate. It MUST record the dependency-lock hash, build-tool versions, and resulting package hashes, and it MUST fail when the resolved installed environment disagrees with the approved lock.

#### Scenario: [OFR-R004-S01] Locked environment is reproduced
- **WHEN** the release is built twice from the same source revision, lock, and approved inputs
- **THEN** both runs SHALL report the same dependency set
- **AND** each produced artifact SHALL have a recorded cryptographic hash

#### Scenario: [OFR-R004-S02] Dependency resolution drifts
- **WHEN** clean installation resolves an unapproved version or reports an incompatible dependency
- **THEN** the packaging gate MUST fail
- **AND** the agent MUST update and re-review the lock instead of silently accepting the drift

### Requirement: [OFR-R005] Complete model and artifact manifest
The repository SHALL maintain a machine-readable model manifest for every model-related artifact included in or required by a release. Each entry MUST separately identify the source URL, source revision, checkpoint URL, checkpoint SHA-256, code license, weight or model-card license, redistribution status, conversion tool and version when applicable, and approval status.

#### Scenario: [OFR-R005-S01] Manifest entry is complete
- **WHEN** packaging selects a model artifact
- **THEN** the release validator SHALL find every required manifest field
- **AND** the selected file hash SHALL match the approved checkpoint hash

#### Scenario: [OFR-R005-S02] Manifest field is missing
- **WHEN** a selected model lacks a recorded license, checksum, source, redistribution decision, or approval state
- **THEN** packaging MUST stop before the artifact enters the release bundle
- **AND** the missing authority MUST be reported as a license blocker

### Requirement: [OFR-R006] License authorization is fail-closed
The release tooling SHALL include only dependencies, model code, weights, GUI libraries, and assets whose applicable use and redistribution terms are recorded as approved. It MUST treat repository code, model weights, model cards, converted artifacts, and transitive dependencies as separate authorization subjects.

#### Scenario: [OFR-R006-S01] Approved dependency is packaged
- **WHEN** every applicable artifact has an approved manifest entry and required notice text
- **THEN** packaging SHALL include the artifact and its required attribution or notice

#### Scenario: [OFR-R006-S02] Approval is absent or incompatible
- **WHEN** an artifact is unapproved, non-commercial for the intended company use, or has incompatible redistribution terms
- **THEN** the artifact MUST be excluded
- **AND** the release MUST remain blocked until it is removed, replaced, or explicitly authorized

### Requirement: [OFR-R007] Prohibited third-party sources remain excluded
SegVision v1 MUST NOT ship EdgeSAM unless written commercial authorization is recorded, and MUST NOT copy GPL-licensed X-AnyLabeling source code or assets into a distribution that is not intentionally licensed compatibly. PySide6 and every other redistributable runtime MUST have its applicable notice and distribution obligations represented in the release evidence.

#### Scenario: [OFR-R007-S01] EdgeSAM lacks written authorization
- **WHEN** the model manifest has no written commercial approval for EdgeSAM
- **THEN** the backend MUST be excluded from build, test-selection, and release packaging

#### Scenario: [OFR-R007-S02] Prohibited GPL material is detected
- **WHEN** source or asset provenance identifies copied X-AnyLabeling GPL material in the release scope
- **THEN** the license gate MUST fail
- **AND** the material MUST be removed or the distribution license decision MUST be explicitly escalated

### Requirement: [OFR-R008] Verified and safe model acquisition
Model acquisition SHALL use the pinned official source recorded in the approved manifest. The system MUST verify the artifact checksum before loading, MUST quarantine a mismatching artifact, and MUST NOT fall back to an unrecorded mirror or execute an untrusted serialized checkpoint.

#### Scenario: [OFR-R008-S01] Official checkpoint matches
- **WHEN** the approved checkpoint is obtained from its recorded source
- **THEN** the acquisition tool SHALL verify its SHA-256 before making it available to the backend

#### Scenario: [OFR-R008-S02] Checkpoint checksum mismatches
- **WHEN** the downloaded or cached checkpoint hash differs from the approved manifest
- **THEN** the system MUST prevent model loading
- **AND** it MUST quarantine the artifact and record an integrity failure

### Requirement: [OFR-R009] Software bill of materials and notices
Every release candidate SHALL include a software bill of materials and `THIRD_PARTY_NOTICES` covering the common package, GUI, inference runtime, CV runtime, model code, model weights, and packaged assets. The recorded inventory MUST agree with the clean installed environment and model manifest.

#### Scenario: [OFR-R009-S01] Installed inventory matches release records
- **WHEN** the release verifier compares the clean environment with the lock, SBOM, notices, and model manifest
- **THEN** every installed runtime component SHALL be represented
- **AND** every represented redistributable component SHALL have its required license information

#### Scenario: [OFR-R009-S02] Undocumented transitive dependency is installed
- **WHEN** a runtime dependency is absent from the SBOM or required notices
- **THEN** the license gate MUST fail
- **AND** the candidate MUST NOT be labeled `engineering-accepted`

### Requirement: [OFR-R010] Fingerprinted reference-CPU verification
The release process SHALL execute its hard performance and real-backend gates on a designated physical Windows CPU machine. Evidence MUST record OS, CPU, RAM, Python, dependency lock, thread settings, model and checkpoint hashes, recipe hashes, cold load, encoder and decoder distributions, peak RAM, and GUI input-to-frame latency. Shared CI timing MUST NOT substitute for this evidence.

#### Scenario: [OFR-R010-S01] Reference benchmark is valid
- **WHEN** the benchmark runs on the designated machine in the recorded configuration
- **THEN** it SHALL emit p50, p90, p95, and maximum values for required latency metrics
- **AND** it SHALL record enough fingerprints to reproduce the run

#### Scenario: [OFR-R010-S02] Overlay or brush responsiveness exceeds the hard limit
- **WHEN** overlay or brush input-to-frame p95 is not less than 100 milliseconds on the reference machine
- **THEN** the reference-CPU gate MUST fail
- **AND** the candidate MUST NOT be labeled `engineering-accepted`

### Requirement: [OFR-R011] Scripted offline end-to-end verification
The release verifier SHALL exercise an installed package through a deterministic offline workflow that loads an image, creates an ROI, obtains or deterministically replays proposals, selects or refines a candidate, performs a local edit, explicitly accepts, writes the PNG and sidecar pair, and reloads the accepted annotation. The workflow MUST also verify a Needs Review outcome that is excluded from training data.

#### Scenario: [OFR-R011-S01] Accepted workflow completes offline
- **WHEN** the scripted workflow runs from the clean installed release bundle
- **THEN** it SHALL produce a full-image binary PNG and matching accepted sidecar
- **AND** the loader SHALL verify schema, shape, filename, status, and hash consistency

#### Scenario: [OFR-R011-S02] Review workflow completes offline
- **WHEN** the scripted workflow selects Needs Review
- **THEN** it SHALL produce review metadata with `training_eligible=false`
- **AND** no accepted training annotation SHALL be published

### Requirement: [OFR-R012] Release evidence bundle
Every release candidate SHALL produce an immutable evidence bundle that records source revision, pre-existing dirty-state hash, operating system, CPU, RAM, Python version, dependency-lock hash, model and checkpoint hashes, recipe hashes, commands, exit codes, test results, benchmark results, logs, produced-artifact hashes, retry history, and applicable approvals. A required gate without evidence MUST be treated as failed.

#### Scenario: [OFR-R012-S01] Evidence bundle is complete
- **WHEN** all engineering gates finish
- **THEN** the release classifier SHALL be able to trace every passed requirement to commands, results, and artifact hashes in the bundle

#### Scenario: [OFR-R012-S02] Required evidence is absent
- **WHEN** a required test, performance result, license approval, or artifact hash is missing or unverifiable
- **THEN** the corresponding gate MUST be marked failed or blocked
- **AND** the classifier MUST NOT infer success

### Requirement: [OFR-R013] Immutable release artifacts and recoverable rollback
Published release artifacts SHALL be versioned and content-addressed or hash-recorded. A failed candidate MUST NOT overwrite a previously accepted package or its evidence, and rollback MUST select or republish the prior verified artifact without deleting its evidence.

#### Scenario: [OFR-R013-S01] New candidate fails after a prior release
- **WHEN** build, offline verification, or license validation fails for a newer candidate
- **THEN** the prior accepted artifact SHALL remain available and unchanged
- **AND** the failed candidate SHALL retain a distinct failed evidence record

### Requirement: [OFR-R014] Engineering-accepted classification
A candidate SHALL receive the `engineering-accepted` label only when all deterministic CI, real-backend, reference-CPU, GUI responsiveness, persistence, clean-machine offline, integrity, dependency, and license-manifest gates pass. Missing representative domain data MUST NOT prevent this engineering classification, but missing required artifact authorization MUST prevent it.

#### Scenario: [OFR-R014-S01] All engineering gates pass
- **WHEN** every Tier A and Tier B requirement has passing, reproducible evidence and required artifact authorization is recorded
- **THEN** the classifier SHALL label the exact source and artifact hashes `engineering-accepted`

#### Scenario: [OFR-R014-S02] Engineering gate is blocked or failed
- **WHEN** any required Tier A or Tier B gate lacks passing evidence
- **THEN** the candidate MUST NOT receive `engineering-accepted`

### Requirement: [OFR-R015] Domain-validated classification
A candidate SHALL receive the `domain-validated` label only when it is already `engineering-accepted` and approved representative real-scene images, independent gold masks, the frozen boundary-quality gate, and real annotator workflow evidence all pass. Synthetic, replayed, or self-generated evidence MUST NOT substitute for these inputs.

#### Scenario: [OFR-R015-S01] Domain evidence passes
- **WHEN** an engineering-accepted candidate passes the approved real-domain boundary and annotator gates
- **THEN** the classifier SHALL label that exact candidate `domain-validated`

#### Scenario: [OFR-R015-S02] Domain evidence is unavailable
- **WHEN** representative data, independent gold truth, or real annotator evidence is missing
- **THEN** the candidate MUST remain at most `engineering-accepted`
- **AND** the missing evidence MUST be reported without weakening the gate
