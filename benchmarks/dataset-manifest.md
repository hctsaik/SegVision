# `dataset-manifest.jsonl` — MVTec AD 2 gold subset

M0 deliverable. 705 defect image + pixel ground-truth mask pairs, from the eight
MVTec AD 2 categories, used as the boundary-metric baseline for the ROI → SAM
candidate path.

## Provenance

| | |
|---|---|
| Dataset | MVTec AD 2 ([arXiv:2503.21622](https://arxiv.org/abs/2503.21622)) |
| Archive | The externally obtained `mvtec_ad_2.tar.gz`, sha256 `c0ded99e…3505e4`, 32,739,596,982 bytes |
| Extracted to | A local, repository-external dataset directory (2.6 GB, `test_public/bad` + `test_public/ground_truth/bad` only) |
| License | CC BY-NC-SA 4.0, © 2025 MVTec Software GmbH — **non-commercial only** |

Every record carries `"commercial_use_authorized": false`. Commercial use needs a
separate agreement with MVTec; this subset is for internal benchmarking, and no
mask derived from it is shippable training data.

## Reproducing

Keep the extracted dataset outside the repository and set `SEGVISION_MVTEC2_ROOT`
to its `mvtec_ad_2` directory before running the commands below. The generated
`dataset-manifest.jsonl` stays local and is ignored by Git.

The MVTec capsule GUI E2E and capsule scratch benchmark scripts also require
`SEGVISION_MVTEC_CAPSULE_ROOT` for a separately obtained capsule dataset.

```
tar -xzf mvtec_ad_2.tar.gz -C <dest> --wildcards \
  'mvtec_ad_2/*/test_public/bad/*' 'mvtec_ad_2/*/test_public/ground_truth/bad/*' \
  'mvtec_ad_2/license.txt' 'mvtec_ad_2/readme.txt'

python benchmarks/build_dataset_manifest.py --root <dest>/mvtec_ad_2 \
  --out benchmarks/dataset-manifest.jsonl
```

The archive is a single gzip stream, so extraction is one sequential pass over
all 32 GB (~5 min) regardless of how little is selected.

## Data-driven core E2E

`mvtec_e2e.py` runs the real image/mask files through the headless core.  It
verifies manifest file hashes, loads RGB images and binary masks, derives a
gold-bbox ROI, and executes `propose -> select -> Accept -> full-image
reconstruction`.  It reports exact-mask and symmetric boundary F1 results for
every record.  The backend is a deterministic gold replay, so this is a
geometry/persistence/integration regression and **not** a MobileSAM quality or
domain-validation claim.

```powershell
$env:SEGVISION_MVTEC2_ROOT = "<local path to mvtec_ad_2>"
.venv\Scripts\python.exe benchmarks\mvtec_e2e.py `
  --root $env:SEGVISION_MVTEC2_ROOT `
  --manifest benchmarks\dataset-manifest.jsonl `
  --tier 1 --output evidence\<run-id>\MVTEC-E2E\report.json
```

Use `--tier 2`, `--tier 3`, or `--tier all` for the corresponding stress and
out-of-scope strata; `--gold-only` restricts the run to the 120 regular scenes.

`mvtec_mobilesam_smoke.py` is a separate opt-in check for the externally
downloaded official MobileSAM source/checkpoint.  It runs three Tier 1 regular
scenes on CPU and records the model's three box-prompt masks.  Its output is
observational only: the checkpoint remains outside the repository release
bundle until model redistribution authority is approved.

```powershell
$env:SEGVISION_MOBILESAM_SOURCE = "<local MobileSAM source directory>"
$env:SEGVISION_MOBILESAM_CHECKPOINT = "<local mobile_sam.pt path>"
.venv\Scripts\python.exe benchmarks\mvtec_mobilesam_smoke.py `
  --source $env:SEGVISION_MOBILESAM_SOURCE `
  --checkpoint $env:SEGVISION_MOBILESAM_CHECKPOINT `
  --root $env:SEGVISION_MVTEC2_ROOT `
  --manifest benchmarks\dataset-manifest.jsonl --limit 3 `
  --run-id <run-id> --output evidence\<run-id>\MOBILE-SAM-DATA-SMOKE\report.json
```

## Structure

8 categories × 15 defect scenes = **120 scenes**, each captured under 4–7
appearance variants (`regular`, `overexposed`, `underexposed`, `shift_1..4`) for
705 records total.

`gold_subset: true` marks the 120 `regular` captures — one per scene, the
stratified subset the PRD's 100–300 image target refers to. The other 585
records are the robustness axis, not extra scenes.

**Masks are shared across variants.** 705 records hold only 155 distinct masks;
106 of 120 scenes reuse one mask for every variant. Measured by best-offset
search, the `shift_*` variants carry no geometric translation — they are
illumination and appearance changes — so the shared masks stay valid. Two
consequences:

- Boundary metrics must aggregate per **scene**, not per record, or scenes with
  seven variants outvote scenes with four.
- Same GT under changed appearance is exactly the test for "one frozen CV recipe
  per category": the recipe must land on the same boundary in all variants.

## Fields

`record_id`, `category`, `scene_id`, `variant`, `gold_subset`, plus:

- `image` / `mask` — relative path, sha256, dimensions, mode. All masks are
  strictly binary `{0, 255}`, matching the sidecar mask contract.
- `mask_stats` — `foreground_pixels`, `area_fraction`, `components_8conn`,
  `largest_component_pixels`, `largest_component_share`,
  `component_sizes_top5`, `bbox_full` (`[x, y, w, h]`), `bbox_area_fraction`,
  `touches_image_border`.
- `stratum.shape` — `single_blob` (1 component) / `dominant_blob` (largest holds
  ≥ 95 % of foreground: one blob plus specks) / `multi_blob`.
- `stratum.size` — `tiny` (< 0.1 % of image) / `small` (< 1 %) / `medium`
  (< 10 %) / `large`.
- `stratum.v1_single_foreground_compatible` — true for `single_blob` and
  `dominant_blob`.

Connected components are 8-connected, computed by run-length union-find in
[build_dataset_manifest.py](build_dataset_manifest.py) so the script stays on
the declared numpy + Pillow dependency set. Cross-checked against
`cv2.connectedComponents` on random sparse masks.

## Fit against the v1 contract

v1 is "one binary foreground blob per image". 463 of 705 records (76 of the 120
gold scenes) satisfy it.

| category | n | single | dominant | multi | median components | median defect area | median bbox area | mask touches border |
|---|---|---|---|---|---|---|---|---|
| wallplugs | 90 | 90 | 0 | 0 | 1 | 0.04 % | 0.12 % | 6 |
| can | 90 | 84 | 6 | 0 | 1 | 0.006 % | 0.01 % | 0 |
| rice | 90 | 78 | 0 | 12 | 1 | 0.11 % | 0.16 % | 12 |
| vial | 105 | 49 | 28 | 28 | 2 | 1.07 % | 3.07 % | 0 |
| fabric | 90 | 48 | 12 | 30 | 1 | 0.01 % | 0.05 % | 6 |
| walnuts | 90 | 36 | 6 | 48 | 3 | 1.22 % | 11.56 % | 6 |
| sheet_metal | 90 | 18 | 0 | 72 | 5 | 0.25 % | **47.1 %** | 54 |
| fruit_jelly | 60 | 0 | 8 | 52 | 3 | 0.40 % | 7.34 % | 20 |

Recommended tiers:

- **Tier 1 — v1 acceptance gate.** `wallplugs`, `can`, `rice`. Near-uniformly one
  blob, defect bbox comfortably under 1024 px, so a tight ROI is genuinely small
  and the CPU-crop premise holds.
- **Tier 2 — stress, expected partial.** `vial`, `fabric`, `walnuts`. Mixed
  multi-component; useful for exercising the uncertainty band and Needs Review,
  not for gating.
- **Tier 3 — out of v1 scope.** `sheet_metal`, `fruit_jelly`. `sheet_metal`
  defects span a median 47 % of the frame across a median 5 components, which
  breaks the "human draws a small ROI" speedup outright; `fruit_jelly` has zero
  single-blob records. Both belong to the `Later` multi-region work.

## Two things that will bite

**ROI vs the 1024 backend.** Defect bbox + 10 % pad, long side:

| category | median | p90 | over 1024 px |
|---|---|---|---|
| can | 28 | 91 | 0 / 90 |
| wallplugs | 101 | 569 | 0 / 90 |
| rice | 116 | 1109 | 12 / 90 |
| vial | 427 | 818 | 7 / 105 |
| fabric | 72 | 1433 | 24 / 90 |
| fruit_jelly | 663 | 985 | 0 / 60 |
| walnuts | 1331 | 2141 | 48 / 90 |
| sheet_metal | 2188 | 3348 | 72 / 90 |

Tier 1 ROIs sit far below 1024, so a fixed-1024 backend spends most of its
compute on padding. This is the measurement ADR-0002 wants: encoder latency is
constant, ROI size only decides how much of it is wasted.

**Tiny defects.** 45 % of records cover under 0.1 % of the image; 144 masks are
under 500 px and the smallest is 25 px, all in `can`, `fabric`, `wallplugs`.
Foreground-area IoU is close to meaningless at that scale — a one-pixel dilation
moves it tens of percent. Boundary error thresholds must be set in absolute
pixels against these masks, not as an IoU fraction.
