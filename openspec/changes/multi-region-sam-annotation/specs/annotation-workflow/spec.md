## MODIFIED Requirements

### Requirement: [UIW-R004] Candidate controls shall respect candidate capabilities
The GUI SHALL keep foreground/background SAM controls visible. When refinement is unavailable, the controls SHALL be disabled with a Chinese explanation and a direct `回到 SAM 結果` or `新增下一區塊` action. Local tools SHALL remain available when the active pass permits them.

#### Scenario: [UIW-R004-S01] SAM candidate permits point refinement
- **WHEN** the selected active source is SAM-generated and no manual delta is pending
- **THEN** foreground and background controls SHALL be enabled

#### Scenario: [UIW-R004-S02] Manual active pass explains disabled refinement
- **WHEN** the active pass contains a brush or erase edit
- **THEN** SAM controls SHALL remain visible but disabled
- **AND** the GUI SHALL explain in Chinese that `回到 SAM 結果` discards local edits

#### Scenario: [UIW-R004-S03] New pass re-enables SAM
- **WHEN** the user starts a new region after locking the previous one
- **THEN** the new ROI workflow SHALL expose enabled SAM controls after encode

### Requirement: [UIW-R005] Point refinement shall be previous-state and revision safe
For a refinable active pass, the workflow SHALL send full-image prompts, retain the original box and prompt IDs, refine from the selected opaque state, and reject stale results. Deleting a prompt SHALL trigger deterministic replay without re-encoding.

#### Scenario: [UIW-R005-S01] Delete any prompt
- **WHEN** the user deletes a selected prompt marker or list item
- **THEN** the workflow SHALL replay remaining prompts and show the result only if session and revision remain current

### Requirement: [UIW-R007] Local editing shall protect locked regions
Local editing SHALL create one checkpoint per completed stroke, modify only unlocked active pixels, and prevent model results for that active pass from changing manual pixels. A later pass MAY invoke MobileSAM, but its output MUST be clipped/composited around locked regions.

#### Scenario: [UIW-R007-S01] Brush and erase are pixel tools
- **WHEN** the user paints or erases with the selected 1 px, 3 px, or 5 px pencil/brush size (1 px by default)
- **THEN** the active mask SHALL change without an encoder or decoder call
- **AND** locked pixels SHALL be untouched

#### Scenario: [UIW-R007-S02] Late result after locking
- **WHEN** an older model job completes after a lock or next-region action
- **THEN** it SHALL be discarded and the composed mask SHALL remain unchanged

#### Scenario: [UIW-R007-S03] LabelMe export closes and simplifies brush contours
- **WHEN** an accepted brush-edited mask is exported to LabelMe
- **THEN** export SHALL operate on a copy of the binary mask, close one-pixel gaps, fill enclosed voids, and simplify boundary noise into closed polygon shapes
- **AND** the accepted PNG and JSON sidecar SHALL remain the lossless source of truth

### Requirement: [UIW-R008] Undo shall restore session-owned checkpoints
Undo SHALL restore the exact preceding active and locked state without a backend call, including after lock, unlock, prompt deletion, or a local stroke.

#### Scenario: [UIW-R008-S01] Undo lock or prompt deletion
- **WHEN** the user presses Undo after either operation
- **THEN** the previous mask, provenance, prompts, and controls SHALL be restored exactly

### Requirement: [UIW-R009] The GUI shall implement the frozen shortcut contract
The existing shortcuts SHALL remain valid. `B` SHALL activate brush, `E` SHALL activate erase, `L` SHALL preview/lock a component, `U` SHALL unlock the selected region, and `N` SHALL mean next region while a multi-region session is active; next-image remains gated by durable Accept/Needs Review.

#### Scenario: [UIW-R009-S01] Lock and next-region shortcuts
- **WHEN** the user presses `L` and then `N` after confirming a component
- **THEN** the component SHALL lock and a fresh ROI pass SHALL begin without changing it

### Requirement: [UIW-R016] The v1 GUI shall expose only frozen-scope annotation controls
The GUI MUST NOT expose prohibited prompting, providers, sliders, or automatic Accept controls. It MAY expose protected multi-region annotation, prompt management, lock/unlock, and next-region controls defined by this change.

#### Scenario: [UIW-R016-S01] Multi-region controls are in scope
- **WHEN** the GUI starts with the feature enabled
- **THEN** it SHALL expose SAM prompts, pixel tools, lock/unlock, next-region, Accept, and Needs Review controls
- **AND** it SHALL omit prohibited controls

### Requirement: [UIW-R017] The GUI shall explain small-gap repair and foreground merge
When frozen foreground regions exist, the GUI SHALL explain that a small missing area can be added with the foreground point tool or a pixel brush, removed with the background point tool or erase, and flattened with `合併區塊`. The merge control SHALL be disabled when no foreground region exists and SHALL invoke the local merge operation when enabled.

#### Scenario: [UIW-R017-S01] Repair a small gap then merge
- **WHEN** the user adds a small missing area and clicks `合併區塊`
- **THEN** the active editable mask SHALL contain the repaired area and every previously frozen foreground region
- **AND** the GUI SHALL keep frozen background exclusions protected

### Requirement: [UIW-R018] The native shell shall prove SAM point delivery on 014.png
The native desktop workflow SHALL include a reproducible Playwright E2E using the local `014.png` fixture and the approved CPU MobileSAM backend. The scenario SHALL lock an ROI, enable the point tool, deliver a full-image point through the canvas, and verify prompt history without requiring a revision increment.

#### Scenario: [UIW-R018-S01] 014.png point click reaches refinement
- **WHEN** the E2E opens `014.png`, locks the defect ROI, and clicks the foreground point tool
- **THEN** the canvas click SHALL reach the refinement endpoint and add a prompt marker
- **AND** the selected candidate SHALL remain current with no operation error

### Requirement: [UIW-R019] The GUI shall distinguish SAM box selection from a two-point edit area
The GUI SHALL expose `框選` as the MobileSAM ROI tool and SHALL define its rectangular search area with two primary corner clicks; dragging SHALL NOT be required. It SHALL separately expose `編輯範圍` for a local pixel-edit work area. In `編輯範圍`, the first primary click SHALL mark one corner and the second primary click SHALL mark the opposite corner. A valid edit rectangle SHALL use full-image, half-open `XYXY` coordinates and SHALL remain a local UI edit boundary; it MUST NOT invoke `sessions.lock_roi` or rerun MobileSAM. Subsequent brush and erase strokes SHALL be clipped to this rectangle, including the selected brush radius. The UI SHALL show numbered corner markers and Chinese instructions, and pressing `編輯範圍` again SHALL clear the current work area so the user can redraw after a mistake.

#### Scenario: [UIW-R019-S01] Two clicks establish a local work area
- **WHEN** the user selects `編輯範圍`, clicks `(x0, y0)`, and then clicks `(x1, y1)` at least four pixels away in each axis
- **THEN** the GUI SHALL show corner markers `1` and `2`, construct `[min(x0,x1), min(y0,y1), max(x0,x1)+1, max(y0,y1)+1]`, and keep the SAM ROI/session revision unchanged

#### Scenario: [UIW-R019-S02] Brush and erase are confined to the work area
- **WHEN** the user selects 畫筆 or 擦除 after establishing a work area and paints with a 1 px, 3 px, or 5 px size
- **THEN** the resulting mask SHALL change only inside the half-open work-area rectangle, while the operation remains undoable as one local edit checkpoint

#### Scenario: [UIW-R019-S03] A small or mistaken pair remains recoverable
- **WHEN** the second click is too close to the first, or the user presses `編輯範圍` again
- **THEN** the GUI SHALL keep the mask/session unchanged, explain the correction in Chinese, and allow a fresh pair of corners without dragging

#### Scenario: [UIW-R019-S04] A nearby click adjusts one completed corner
- **WHEN** both corners are already set and the user clicks near corner `1` or corner `2`
- **THEN** only the nearer corner SHALL move to the new pixel, the other corner SHALL remain unchanged, and the brush/erase boundary SHALL update without invoking MobileSAM

#### Scenario: [UIW-R019-S05] Work-area selection is available before local editing
- **WHEN** the session is at `IMAGE_OPEN` or another non-terminal state with no selected candidate yet
- **THEN** `編輯範圍` SHALL remain enabled whenever the image/ROI session is editable, independently of `controls.local_edit`; selecting a work area SHALL not change the SAM revision or invoke MobileSAM
