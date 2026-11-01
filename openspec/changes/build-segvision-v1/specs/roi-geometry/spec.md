## ADDED Requirements

### Requirement: [ROI-R001] Full-image image and ROI contract

The geometry layer SHALL accept source images with positive integer height and width. Public ROIs SHALL use finite full-image half-open `XYXY` coordinates `[x0, y0, x1, y1)`, SHALL have width and height of at least one source pixel, and SHALL be fully contained within `[0, width] x [0, height]`. Invalid public ROIs SHALL NOT be silently clipped or reordered.

#### Scenario: [ROI-R001-S01] Accept a one-pixel ROI

- **GIVEN** an image of width and height greater than one and ROI `[x, y, x+1, y+1)` inside the image
- **WHEN** the ROI is validated
- **THEN** the geometry layer SHALL accept it as a one-pixel ROI

#### Scenario: [ROI-R001-S02] Reject reversed or empty bounds

- **GIVEN** an ROI where `x1 <= x0` or `y1 <= y0`
- **WHEN** the ROI is validated
- **THEN** the geometry layer SHALL raise `InvalidRoi`
- **AND** SHALL NOT create a crop context

#### Scenario: [ROI-R001-S03] Reject non-finite or out-of-image bounds

- **GIVEN** an ROI containing NaN, infinity, a negative coordinate, or a coordinate beyond the image's half-open bounds
- **WHEN** the ROI is validated
- **THEN** the geometry layer SHALL raise `InvalidRoi`
- **AND** SHALL NOT silently clamp the user prompt

### Requirement: [ROI-R002] Frozen padded-crop default

The default ROI padding fraction SHALL be `0.10`. Before image-boundary clamping, horizontal padding on each side SHALL equal `0.10 * user_roi_width` and vertical padding on each side SHALL equal `0.10 * user_roi_height`. The integer crop SHALL use floor for left/top and ceil for right/bottom so it fully contains the padded floating rectangle.

#### Scenario: [ROI-R002-S01] Compute an unclamped padded crop

- **GIVEN** `user_roi_full=[100,100,200,200)` in a sufficiently large image and no explicit padding override
- **WHEN** the crop context is created
- **THEN** `crop_rect_full` SHALL equal `[90,90,210,210)`
- **AND** `padding_fraction` SHALL equal `0.10`

#### Scenario: [ROI-R002-S02] Round fractional padding outward

- **GIVEN** `user_roi_full=[10,20,21,31)`
- **WHEN** default padding is applied
- **THEN** the floating padded rectangle SHALL be `[8.9,18.9,22.1,32.1)` before integer conversion
- **AND** `crop_rect_full` SHALL use `[8,18,23,33)` before image clamping

#### Scenario: [ROI-R002-S03] Clamp only the padded crop

- **GIVEN** a valid user ROI near a source-image border whose padded rectangle exceeds that border
- **WHEN** the crop context is created
- **THEN** `crop_rect_full` SHALL clamp to the image bounds
- **AND** `user_roi_full` SHALL remain unchanged
- **AND** the context SHALL record the realized crop and that padding was boundary-clamped

### Requirement: [ROI-R003] Distinct user ROI and work crop

The system SHALL preserve `user_roi_full` and `crop_rect_full` as separate immutable fields. `user_roi_full` SHALL be the segmentation box prompt. `crop_rect_full` SHALL only define pixels supplied to CV, the model backend, candidate masks, and local editing.

#### Scenario: [ROI-R003-S01] Map the box prompt into a padded crop

- **GIVEN** a user ROI strictly inside a larger padded crop
- **WHEN** the proposal engine constructs a backend prompt
- **THEN** it SHALL subtract the crop origin from `user_roi_full`
- **AND** SHALL pass the mapped user ROI as the box
- **AND** SHALL NOT pass the complete padded crop rectangle as the box

#### Scenario: [ROI-R003-S02] Preserve both rectangles in provenance

- **GIVEN** a crop context created from a valid ROI
- **WHEN** a candidate, commit result, or review result records geometry provenance
- **THEN** it SHALL record both `user_roi_full` and `crop_rect_full`
- **AND** the two fields SHALL NOT be aliases of one another when padding is realized

### Requirement: [ROI-R004] Public point and rectangle coordinate spaces

All public point prompts SHALL use finite integer full-image source-pixel indices `(x, y)` satisfying `0 <= x < image_width` and `0 <= y < image_height`. All public rectangles SHALL use full-image half-open `XYXY`. Crop coordinates SHALL be internal values derived by subtracting `crop_rect_full` origin; point-to-mask checks SHALL index exactly `(row=y-y0, column=x-x0)` with no rounding or pixel-center offset. The backend SHALL exclusively own model-space resize, normalization, padding, and prompt transforms.

#### Scenario: [ROI-R004-S01] Convert a full-image point to crop coordinates

- **GIVEN** `crop_rect_full=[40,60,140,180)` and public point `(55,79)`
- **WHEN** the point is mapped to crop coordinates
- **THEN** the result SHALL be `(15,19)`

#### Scenario: [ROI-R004-S02] Reject a point outside the work crop

- **GIVEN** a valid full-image point outside the current `crop_rect_full`
- **WHEN** it is requested as a prompt or local-edit control point for that crop
- **THEN** geometry validation SHALL reject it
- **AND** SHALL NOT clamp it into the crop

#### Scenario: [ROI-R004-S03] Reject a fractional or non-finite point

- **GIVEN** a public point with a fractional, NaN, or infinite coordinate
- **WHEN** prompt validation runs
- **THEN** geometry validation SHALL reject it and SHALL NOT round it to a pixel index

#### Scenario: [ROI-R004-S04] Keep model transforms backend-owned

- **GIVEN** a valid crop-space point or box
- **WHEN** the proposal engine requests model inference
- **THEN** only the backend adapter SHALL convert it to model coordinates
- **AND** GUI and core candidate-policy code SHALL NOT depend on the model input size

### Requirement: [ROI-R005] Coordinate round-trip accuracy

For every supported backend, full-to-crop-to-model-to-crop-to-full point and box transforms SHALL round-trip within one source-image pixel at every finite coordinate inside the user ROI. Crop-to-full and full-to-crop transforms that involve only integer origin translation SHALL be exact.

#### Scenario: [ROI-R005-S01] Integer translation round trip

- **GIVEN** an integer full-image point or half-open box inside a crop
- **WHEN** it is mapped full-to-crop-to-full without model scaling
- **THEN** the original coordinates SHALL be restored exactly

#### Scenario: [ROI-R005-S02] Backend model-space round trip

- **GIVEN** representative edge, center, fractional, odd-size, and even-size points and boxes
- **WHEN** they are mapped through the backend model transform and back
- **THEN** absolute error on each coordinate SHALL be no greater than one source-image pixel

### Requirement: [ROI-R006] Crop pixel extraction

The crop SHALL be extracted from the original RGB image using `crop_rect_full` without first resizing the viewer image. The extracted crop SHALL have shape `(crop_height, crop_width, 3)` where width is `x1-x0` and height is `y1-y0`.

#### Scenario: [ROI-R006-S01] Ignore the viewer thumbnail

- **GIVEN** an original RGB image and a lower-resolution viewer representation
- **WHEN** the work crop is extracted
- **THEN** every crop pixel SHALL originate from the original RGB image
- **AND** the viewer representation SHALL NOT be used as inference input

#### Scenario: [ROI-R006-S02] Extract a border crop

- **GIVEN** a clamped crop touching the right and bottom image borders
- **WHEN** pixels are extracted
- **THEN** the resulting array dimensions SHALL exactly equal the half-open crop dimensions
- **AND** no padding pixels outside the source image SHALL be invented

### Requirement: [ROI-R007] Crop-resolution candidate mask contract

Every candidate and local-edit mask SHALL be a two-dimensional `numpy.bool_` array at the original work-crop resolution. A model-resolution or low-resolution tensor MUST NOT enter candidate or local-edit APIs before backend postprocessing.

#### Scenario: [ROI-R007-S01] Accept a valid crop mask

- **GIVEN** `crop_rect_full` with height `h` and width `w`
- **WHEN** a candidate is constructed from a boolean array of shape `(h,w)`
- **THEN** mask geometry validation SHALL accept it

#### Scenario: [ROI-R007-S02] Reject a wrong mask shape or dtype

- **GIVEN** a mask with model resolution, full-image resolution, three channels, or a non-boolean dtype
- **WHEN** candidate or local-edit validation runs
- **THEN** the system SHALL reject the mask with a typed validation error
- **AND** SHALL NOT silently reshape, threshold, or reinterpret it

### Requirement: [ROI-R008] Full-image mask reconstruction

Commit geometry SHALL create a new full-image boolean mask of the original image height and width, initialize it to background, and copy the accepted crop mask only into `crop_rect_full`. Commit geometry SHALL NOT mutate the crop mask.

#### Scenario: [ROI-R008-S01] Commit an interior crop

- **GIVEN** a valid crop-sized candidate mask
- **WHEN** full-image reconstruction runs
- **THEN** the corresponding crop region in the full mask SHALL equal the candidate mask exactly
- **AND** every pixel outside `crop_rect_full` SHALL be false
- **AND** the full mask shape SHALL equal `(source_height, source_width)` and SHALL NOT include the RGB channel dimension

#### Scenario: [ROI-R008-S02] Commit a crop clamped at image borders

- **GIVEN** a crop touching one or more source-image borders
- **WHEN** reconstruction runs
- **THEN** placement SHALL remain exact without negative indexing, wrapping, padding, or one-pixel shift

### Requirement: [ROI-R009] Work-crop edge risk

Crop-edge risk SHALL be evaluated against the one-pixel boundary of `crop_rect_full`, not against `user_roi_full`. A foreground contact with the work-crop boundary SHALL emit `TOUCHES_WORK_CROP_EDGE`; contact with only the user ROI boundary SHALL NOT emit that warning.

#### Scenario: [ROI-R009-S01] Touch only the user ROI

- **GIVEN** a candidate whose foreground touches the mapped user ROI but remains at least one pixel away from every work-crop edge
- **WHEN** edge-risk analysis runs
- **THEN** `TOUCHES_WORK_CROP_EDGE` SHALL NOT be emitted

#### Scenario: [ROI-R009-S02] Touch the padded crop edge

- **GIVEN** a candidate with at least one foreground pixel on the top, bottom, left, or right crop boundary
- **WHEN** edge-risk analysis runs
- **THEN** `TOUCHES_WORK_CROP_EDGE` SHALL be emitted
- **AND** the candidate SHALL NOT be silently cropped, removed, or accepted

### Requirement: [ROI-R010] Source-image truncation provenance

Visible foreground SHALL be clipped at the source-image boundary. If committed foreground touches a source-image boundary, the geometry result SHALL record `IMAGE_BOUNDARY_TRUNCATED` independently from work-crop edge acknowledgement.

#### Scenario: [ROI-R010-S01] Object reaches the source-image boundary

- **GIVEN** an accepted crop mask whose reconstructed foreground touches the source image boundary
- **WHEN** commit geometry produces provenance
- **THEN** it SHALL record `IMAGE_BOUNDARY_TRUNCATED`
- **AND** SHALL NOT hallucinate pixels beyond the image

### Requirement: [ROI-R011] ROI expansion creates new geometry

Expand ROI SHALL set the proposed new `user_roi_full` to the current `crop_rect_full`, then apply the normal `0.10` padding and image-boundary clamping to derive a proposed new `crop_rect_full`. It SHALL succeed only when the proposed work crop strictly contains the current work crop in at least one direction. It SHALL produce newly validated geometry and SHALL NOT stretch, translate, or reuse old crop masks as current candidates. If clamping prevents strict enlargement, it SHALL return `CANNOT_EXPAND_AT_IMAGE_BOUNDARY` without changing geometry or session revision.

#### Scenario: [ROI-R011-S01] Expand a crop-edge-risk ROI

- **GIVEN** a current candidate with `TOUCHES_WORK_CROP_EDGE`
- **WHEN** the user invokes Expand ROI and the new ROI is valid
- **THEN** geometry SHALL create a new crop context
- **AND** session revision SHALL advance
- **AND** all old crop-sized candidates SHALL become stale

#### Scenario: [ROI-R011-S02] Expansion cannot enlarge at the image boundary

- **GIVEN** the current work crop already equals the full image bounds
- **WHEN** the user invokes Expand ROI
- **THEN** the operation SHALL return `CANNOT_EXPAND_AT_IMAGE_BOUNDARY`
- **AND** geometry, candidates, encoded state, and session revision SHALL remain unchanged
