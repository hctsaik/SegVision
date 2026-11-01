## ADDED Requirements

### Requirement: [CVR-R001] Versioned class-bound recipe schema

Every v1 CV recipe SHALL be a JSON-serializable immutable value containing `schema_version`, `recipe_id`, `class_id`, `enabled`, `working_long_side`, `algorithm`, algorithm parameters, preprocessing parameters, postprocessing parameters, validity-gate parameters, direct-gate parameters, and bridge policy. `schema_version` SHALL equal integer `1`; `recipe_id` and `class_id` SHALL be non-empty strings. The only required v1 algorithm SHALL be `lab_threshold`, and the only v1 bridge policy SHALL be `direct_if_clean_else_mask_prompt`.

#### Scenario: [CVR-R001-S01] Parse a valid v1 recipe

- **GIVEN** a recipe with schema version `1`, a matching class ID, algorithm `lab_threshold`, complete parameters, and the supported bridge policy
- **WHEN** `recipe_from_json(...)` parses it
- **THEN** the system SHALL return an immutable typed recipe

#### Scenario: [CVR-R001-S02] Reject an unsupported schema version

- **GIVEN** a recipe whose schema version is absent, non-integer, or not `1`
- **WHEN** it is parsed
- **THEN** the system SHALL raise `RecipeSchemaError`
- **AND** SHALL NOT execute any CV operation

#### Scenario: [CVR-R001-S03] Reject an unsupported algorithm or bridge

- **GIVEN** a recipe naming an algorithm other than `lab_threshold` or a bridge policy other than `direct_if_clean_else_mask_prompt`
- **WHEN** it is parsed
- **THEN** the system SHALL raise `RecipeSchemaError`
- **AND** SHALL NOT silently substitute another operation

### Requirement: [CVR-R002] Frozen recipe defaults

The v1 recipe constructor SHALL use these explicit defaults when the corresponding optional fields are omitted: `enabled=false`, `working_long_side=512`, `median_blur_px=3`, `open_radius_px=0`, `close_radius_px=0`, `fill_holes=false`, `min_component_area=0`, `min_area_fraction=0.01`, `max_area_fraction=0.85`, `max_crop_border_fraction=0.02`, and `max_components=4`. Threshold channel ranges and class identity MUST be supplied explicitly and SHALL have no inferred default.

#### Scenario: [CVR-R002-S01] Construct a recipe with safe defaults

- **GIVEN** a recipe definition with explicit LAB ranges and class identity but without optional processing and gate fields
- **WHEN** the typed recipe is constructed
- **THEN** every omitted optional field SHALL take the frozen value above
- **AND** the recipe SHALL remain disabled until explicitly enabled

#### Scenario: [CVR-R002-S02] Reject missing LAB thresholds

- **GIVEN** a `lab_threshold` recipe without explicit L, A, or B ranges
- **WHEN** the recipe is parsed
- **THEN** the system SHALL raise `RecipeSchemaError`
- **AND** SHALL NOT derive thresholds from the current image or a histogram

### Requirement: [CVR-R003] Strict parameter validation

LAB channel bounds SHALL be integers in `[0,255]` with lower bound less than or equal to upper bound. `working_long_side` SHALL be a positive integer. Median blur SHALL be `0` or an odd positive integer. Morphology radii and minimum component area SHALL be non-negative integers. Area and border fractions SHALL lie in `[0,1]`, `min_area_fraction` SHALL be strictly less than `max_area_fraction`, and `max_components` SHALL be a positive integer.

#### Scenario: [CVR-R003-S01] Reject invalid channel ranges

- **GIVEN** a LAB range outside `[0,255]` or with lower bound greater than upper bound
- **WHEN** the recipe is parsed
- **THEN** the system SHALL raise `RecipeSchemaError`

#### Scenario: [CVR-R003-S02] Reject invalid processing parameters

- **GIVEN** an even non-zero median kernel, negative morphology radius, non-positive working long side, invalid fraction, or non-positive component maximum
- **WHEN** the recipe is parsed
- **THEN** the system SHALL raise `RecipeSchemaError`
- **AND** SHALL identify the invalid field

### Requirement: [CVR-R004] Per-class binding

A parsed recipe SHALL execute only when its `class_id` exactly equals the active session class ID. Class-to-recipe mapping SHALL be owned by the caller or adapter, not by hidden global state in the core.

#### Scenario: [CVR-R004-S01] Execute a matching class recipe

- **GIVEN** an enabled recipe whose class ID equals the session class ID
- **WHEN** proposal begins
- **THEN** the system SHALL execute that recipe once for the current crop revision before optional model encoding

#### Scenario: [CVR-R004-S02] Reject a class mismatch

- **GIVEN** a parsed recipe whose class ID differs from the session class ID
- **WHEN** the session attempts to use it
- **THEN** the system SHALL raise `RecipeClassMismatch`
- **AND** SHALL NOT execute CV or silently relabel the recipe

### Requirement: [CVR-R005] Disabled-or-absent recipe behavior

CV SHALL be off when a recipe is absent or has `enabled=false`. The normal SAM box proposal path SHALL remain available, and no CV timing, threshold, morphology, component, or mask-prompt operation SHALL run.

#### Scenario: [CVR-R005-S01] No class recipe

- **GIVEN** a session without a recipe
- **WHEN** proposal runs
- **THEN** CV execution count SHALL equal `0`
- **AND** proposal SHALL continue through the normal SAM box path

#### Scenario: [CVR-R005-S02] Disabled class recipe

- **GIVEN** a valid recipe with `enabled=false`
- **WHEN** proposal runs
- **THEN** CV execution count SHALL equal `0`
- **AND** the disabled recipe SHALL NOT affect candidate masks or ranking

### Requirement: [CVR-R006] Crop-only deterministic CV pipeline

An enabled recipe SHALL execute only on the original RGB work crop, never on the full image or a viewer thumbnail. The deterministic operation order SHALL be: isotropically resize so the longest side equals `working_long_side`; convert RGB to OpenCV-compatible 8-bit LAB; apply the fixed median blur when non-zero; apply inclusive L/A/B range thresholding; apply opening; apply closing; optionally fill holes; remove components smaller than `min_component_area`; map the binary mask back to original crop resolution with nearest-neighbor sampling; and then evaluate gates. OpenCV and NumPy versions SHALL be locked by the release environment.

#### Scenario: [CVR-R006-S01] Repeat the same recipe

- **GIVEN** identical crop bytes, recipe bytes, and locked dependency versions
- **WHEN** the recipe is executed twice
- **THEN** the two crop-resolution binary masks, gates, diagnostics, and intermediate call counts SHALL be identical

#### Scenario: [CVR-R006-S02] Preserve aspect ratio

- **GIVEN** a non-square crop and `working_long_side=512`
- **WHEN** the CV working image is created
- **THEN** its longest side SHALL equal `512`
- **AND** its aspect ratio SHALL match the crop up to integer resize rounding
- **AND** it SHALL NOT be padded into a square

#### Scenario: [CVR-R006-S03] Use inclusive channel ranges

- **GIVEN** a LAB pixel equal to a configured lower or upper bound on every channel
- **WHEN** thresholding runs
- **THEN** that pixel SHALL pass the corresponding channel tests

### Requirement: [CVR-R007] Frozen morphology semantics

Opening SHALL mean erosion followed by dilation; closing SHALL mean dilation followed by erosion. A radius of `0` SHALL be a no-op. A positive radius `r` SHALL use an 8-connected square kernel of shape `(2r+1, 2r+1)`. Hole filling SHALL fill only background components not connected to the working-mask boundary. Component filtering SHALL use 8-connectivity and SHALL be disabled when `min_component_area=0`.

#### Scenario: [CVR-R007-S01] Default postprocessing is non-destructive

- **GIVEN** the frozen defaults `open_radius_px=0`, `close_radius_px=0`, `fill_holes=false`, and `min_component_area=0`
- **WHEN** postprocessing runs
- **THEN** the threshold mask SHALL remain unchanged

#### Scenario: [CVR-R007-S02] Remove a small component when configured

- **GIVEN** an 8-connected foreground component with area below a positive `min_component_area`
- **WHEN** component filtering runs
- **THEN** that component SHALL be removed
- **AND** components at or above the threshold SHALL remain

### Requirement: [CVR-R008] Immutable per-image runtime behavior

Recipe execution SHALL NOT tune thresholds, inspect a histogram to change parameters, alter morphology, fit a color model, or persist a modified recipe based on the current image. The annotation hot path MUST NOT expose HSV/LAB sliders or per-image recipe overrides.

#### Scenario: [CVR-R008-S01] Difficult image does not mutate the recipe

- **GIVEN** an enabled recipe and a crop for which thresholding performs poorly
- **WHEN** recipe execution finishes
- **THEN** the original typed recipe and canonical hash SHALL remain unchanged
- **AND** the result SHALL be classified through the frozen gates rather than retuned

#### Scenario: [CVR-R008-S02] Runtime override attempt

- **GIVEN** an active session
- **WHEN** a caller supplies an image-specific threshold or morphology override not present in the parsed recipe
- **THEN** the core SHALL reject the override as unsupported

### Requirement: [CVR-R009] Three-state CV result

Every successful recipe invocation SHALL return exactly one `CvResult` with a crop-resolution boolean mask, gate in `{invalid, coarse, direct}`, diagnostics, recipe ID, and canonical recipe hash. Execution exceptions SHALL be converted into an `invalid` result with an error diagnostic when safe SAM/manual fallback remains available; they MUST NOT fabricate `coarse` or `direct`.

#### Scenario: [CVR-R009-S01] Empty threshold result is invalid

- **GIVEN** deterministic processing produces no foreground pixels
- **WHEN** gate evaluation runs
- **THEN** gate SHALL equal `invalid`
- **AND** diagnostics SHALL include `EMPTY_MASK`

#### Scenario: [CVR-R009-S02] CV execution error is invalid

- **GIVEN** a recoverable OpenCV execution error
- **WHEN** the recipe invocation ends
- **THEN** gate SHALL equal `invalid`
- **AND** diagnostics SHALL record the error type
- **AND** normal SAM or manual fallback SHALL remain possible

### Requirement: [CVR-R010] Explicit validity-gate semantics

Foreground area fraction SHALL equal foreground pixel count divided by crop pixel count after mapping back to crop resolution. A non-empty result with area fraction below `min_area_fraction` or above `max_area_fraction` SHALL be `invalid`. Bounds SHALL be inclusive for validity: a mask exactly at either bound SHALL pass the validity gate.

#### Scenario: [CVR-R010-S01] Reject an area-invalid mask

- **GIVEN** a non-empty mask whose foreground area fraction is outside `[0.01,0.85]` under default gates
- **WHEN** validity evaluation runs
- **THEN** gate SHALL equal `invalid`
- **AND** the raw mask SHALL NOT become a public candidate or mask prompt

#### Scenario: [CVR-R010-S02] Accept a bound-equal area as valid

- **GIVEN** a mask whose area fraction equals the configured minimum or maximum exactly
- **WHEN** validity evaluation runs
- **THEN** the mask SHALL pass the area validity check

### Requirement: [CVR-R011] Explicit direct-gate semantics

For a validity-passing mask, component count SHALL use 8-connectivity after postprocessing. Crop-border contact fraction SHALL equal the number of foreground pixels on the one-pixel crop boundary divided by the total number of pixels on that boundary. The result SHALL be `direct` only when component count is less than or equal to `max_components` and border contact fraction is less than or equal to `max_crop_border_fraction`; otherwise it SHALL be `coarse`.

#### Scenario: [CVR-R011-S01] Produce a direct result

- **GIVEN** a validity-passing mask with no more than four components and crop-border fraction no greater than `0.02` under default gates
- **WHEN** direct-gate evaluation runs
- **THEN** gate SHALL equal `direct`

#### Scenario: [CVR-R011-S02] Produce a coarse result from excess components

- **GIVEN** a validity-passing mask with more than the configured maximum components
- **WHEN** direct-gate evaluation runs
- **THEN** gate SHALL equal `coarse`

#### Scenario: [CVR-R011-S03] Produce a coarse result from border contact

- **GIVEN** a validity-passing mask whose crop-border fraction exceeds the configured maximum
- **WHEN** direct-gate evaluation runs
- **THEN** gate SHALL equal `coarse`
- **AND** diagnostics SHALL report the measured and allowed fractions

### Requirement: [CVR-R012] CV execution precedes optional model encoding

An enabled class recipe SHALL run once immediately after crop creation and before any model encode for that revision. Its gate SHALL determine the call path: `invalid` continues to normal SAM box proposal, `coarse` continues to one encode plus mask-prompt decode, and `direct` returns a CV candidate with zero model calls.

#### Scenario: [CVR-R012-S01] Invalid result falls back to SAM

- **GIVEN** an enabled recipe returning `invalid`
- **WHEN** proposal continues
- **THEN** backend encode count SHALL equal `1`
- **AND** the initial box-only SAM path SHALL run

#### Scenario: [CVR-R012-S02] Coarse result feeds SAM

- **GIVEN** an enabled recipe returning `coarse`
- **WHEN** proposal continues
- **THEN** backend encode count SHALL equal `1`
- **AND** the coarse binary mask SHALL be converted through `mask_prompt_from_binary`
- **AND** it SHALL NOT be converted into automatic positive or negative points

#### Scenario: [CVR-R012-S03] Direct result skips SAM

- **GIVEN** an enabled recipe returning `direct`
- **WHEN** proposal completes
- **THEN** backend encode and decode counts SHALL both equal `0`
- **AND** exactly one `cv_direct` candidate SHALL be returned

### Requirement: [CVR-R013] Direct-candidate safety and capabilities

A `cv_direct` result SHALL remain a proposal requiring explicit human Accept. It SHALL carry recipe identity and diagnostics, SHALL support local editing and Needs Review, SHALL NOT support point refinement, and SHALL NOT trigger lazy model encoding on a point-tool request.

#### Scenario: [CVR-R013-S01] Edit a direct candidate locally

- **GIVEN** a selected `cv_direct` candidate
- **WHEN** the user applies brush, erase, grow, shrink, or fill holes
- **THEN** a manual candidate SHALL be created with the CV candidate as parent
- **AND** backend call count SHALL remain zero

#### Scenario: [CVR-R013-S02] Attempt point refinement on a direct candidate

- **GIVEN** a selected `cv_direct` candidate
- **WHEN** point refinement is requested
- **THEN** the session SHALL raise `UnsupportedOperation`
- **AND** SHALL NOT initialize or call the model backend

#### Scenario: [CVR-R013-S03] High-quality direct result is not auto-accepted

- **GIVEN** a `cv_direct` candidate satisfying every recipe gate
- **WHEN** no human Accept action occurs
- **THEN** no training-eligible result SHALL be produced

### Requirement: [CVR-R014] Coarse-mask handoff safety

A raw `coarse` mask SHALL remain internal evidence. It MUST NOT occupy a displayed candidate slot, be treated as final annotation, replace the RGB crop, or be decomposed into SAM points. Only a backend-decoded, validated `sam_cv` result MAY occupy one candidate slot.

#### Scenario: [CVR-R014-S01] Backend rejects the mask prompt

- **GIVEN** a `coarse` CV result but mask-state conversion or mask-prompt decode fails
- **WHEN** proposal assembly continues
- **THEN** no raw CV candidate SHALL be shown
- **AND** box candidates and manual fallback SHALL remain available
- **AND** diagnostics SHALL record the failed CV bridge

### Requirement: [CVR-R015] Pure recipe serialization and canonical identity

`recipe_to_json(recipe)` and `recipe_from_json(payload)` SHALL be pure functions with no file I/O or global class registry. Recipe identity SHALL use SHA-256 of a deterministic canonical UTF-8 JSON representation with keys sorted, no insignificant whitespace, and numeric values serialized consistently.

#### Scenario: [CVR-R015-S01] Canonical round trip

- **GIVEN** two semantically identical recipes whose input JSON key order and whitespace differ
- **WHEN** both are parsed and canonically serialized
- **THEN** canonical JSON bytes SHALL be identical
- **AND** recipe SHA-256 values SHALL be identical

#### Scenario: [CVR-R015-S02] Serialization performs no I/O

- **GIVEN** a valid typed recipe
- **WHEN** it is serialized or parsed
- **THEN** no filesystem or network operation SHALL occur
