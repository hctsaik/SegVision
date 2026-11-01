# 同類多張：reference-mask transfer 與同圖確認 refine

> 狀態：**研究建議稿**（非正式 v1 開工規格；**不構成實作授權**）  
> 日期：2026-08-29（2026-08-29 可行性修訂）  
> 產品規格權威：[`PRD.md`](../PRD.md)  
> 契約權威：`openspec/changes/build-segvision-v1/specs/*`  
> 相關：[`SAM-assisted-annotation-strategy.md`](SAM-assisted-annotation-strategy.md)、[`final-development-recommendation.md`](final-development-recommendation.md)  
> 結論一句話：**學「這是目標物」，不要把「邊緣像素」當成可跨圖遷移的外觀類別；最終邊界仍交給 SAM + 人。同圖「確認一部分」只能當約束，不能當 brush、也不能當跨圖 teacher。**

本文件討論兩件**不同**的事，不可寫進同一個 OpenSpec change：

1. **同圖**：人選候選後，先確認一部分前景／背景，再讓 SAM 在同一 encoded crop 上修邊。
2. **跨圖**：一張人工 Accept 的 mask，能否幫後續張少畫 ROI、少點、少刷。較精確的名稱是 **reference-mask transfer** 或 **exemplar-conditioned proposal**，不是保證跨實例泛化的「class transfer」。

它不改變 v1 凍結決策：v1 不訓練自訂模型、DINO 不進熱路徑、禁止自動 Accept、公開候選最多三個、refine 每次最多一張新候選、既有 CV recipe 仍為明示且不可變的配方。

若本文件與 PRD 或 OpenSpec 衝突，以 PRD 與現行 change specs 為準。進入程式與 tasks 前必須另開 **單一主題** 的 later change；禁止把本檔 §11 當成 `build-segvision-v1` 的續作清單。

---

## 0. 怎麼用這份文件

| 可以 | 不可以 |
| --- | --- |
| 當 later 產品拆分與 spike 設計 | 當現行 v1 任務、或一次實作全部軌道 |
| 把「確認」拆成 `lock_roi` / `sure_fg` / `sure_bg` / `Accept` | 再用「確認 ROI」這種混用語當需求 |
| 先量測 **沿用 ROI + 既有 SAM** | 把 gold-replay F1=1.0 或 3 張 smoke IoU 當成 retention 證據 |
| 預設關閉、顯式 Fit、可 abstain | 第一張 Accept 自動寫回 recipe 或 prototype |

一次只開一條軌道。其餘在該 change 的 Non-Goals 寫死。

---

## 1. 四條軌道：不要做成一條 pipeline

| ID | 軌道 | 要解決的成本 | 與 v1 的關係 | 何時可開 OpenSpec |
| --- | --- | --- | --- | --- |
| **A** | 下一張沿用 ROI | 重畫框 | PRD 已允許「構圖穩可沿用上一張」；GUI 換圖目前開新 session、**不帶 ROI** | 現在就可當 later/small GUI+session change；不碰模型 |
| **B** | 同圖 confirm-as-constraint | 局部修邊筆畫 | 正負點 + previous mask 已存在；區域確認、且確認後仍可 SAM，是新契約 | 先證明點選不夠用；第一刀不含 Focus Crop、不含 3 張 refine |
| **C** | 離線 LAB calibration | 每類手寫 recipe | `CVR-R008` 禁止熱路徑 fitting | 獨立 change；輸出新 recipe 版本，不改已載入配方 |
| **D** | 跨圖 prototype proposal | 找錯目標、重複點選 | 現行 backend **沒有** dense feature API；encode 也不產生 TinyViT embedding | **先離線 spike**；過不了軌道 A 的對照就不要寫 production tasks |

建議量測順序：**A → 量 bottleneck → 才決定 B 或 D**。不要先做 B 再假設 D 需要它。C 只在同相機、同光照、顏色可分時才值得與 D 比較。

可證偽的產品主張（軌道必須擇一寫進 change）：

```text
軌道 A：在構圖穩定的批次，換圖後可一鍵沿用上一張 user_roi；
        仍要人確認或重畫；編碼仍綁新圖；不得重用上一張 embedding。
        成功 = 相對「每張重畫 ROI + SAM」，降低 time-to-accept 或 ROI 操作次數，
        且不傷 frozen boundary gate。

軌道 B：在同一張、同一 ROI revision，人可用非 brush 的 confirm-FG/BG
        標記 sure_fg / sure_bg；系統在現有 encoded crop 上做一次
        previous-mask decode（multimask_count=1）；違反約束的候選必須丟棄，
        不得 pixel OR。成功 = 相對既有正負點+brush，降低 stroke/retry，
        且已確認像素 violation = 0。

軌道 D：同一 class_id + 同一 capture 條件，一張 interactive_user Accept
        經顯式 Fit 產生 immutable PrototypeArtifact 後，新圖仍要有 ROI，
        系統最多增加 1 張 prototype-prompted 候選，信心不足則 0 張並回退
        既有 SAM。成功 = 相對「沿用 ROI + SAM」（不是相對重畫 ROI），
        降低時間或操作且不增加 wrong-target；否則維持預設關閉。
```

「少畫 ROI」**不是**軌道 D 的預設效果。D 的流程仍是 `新圖 + ROI → match or abstain`。若產品要自動提案 ROI，那是偵測器，必須另開 change，且不得把 DINO/TokenCut 塞進 v1 熱路徑。

---

## 2. 現行 v1：已經有的，不要重做

同圖迭代 SAM 已經是凍結行為：

1. 人畫矩形 `user_roi`（搜尋範圍 + box prompt）。這就是 **lock_roi**。沒有第二個「確認 ROI」控件。
2. 該 crop **encode 一次**；公開最多 3 張提案卡（`sam_box` / `sam_safe_grid` / `sam_cv`）。
3. 人選一張；左鍵 FG / 右鍵 BG **點** + 該候選的 previous mask state；`multimask_count=1`；**零次**額外 encode。
4. 人的點是硬約束（驗證與 Accept 都檢查該像素）。
5. 第一次 brush / erase / grow / shrink / fill → `manual_edit`，**模型鎖死**（`SES-R008`）。
6. 只有人 Accept；common function 只回候選。
7. 換圖不得重用上一張 encoded crop（`SES-R004`）。沿用 ROI 座標 ≠ 沿用 embedding。

後端協議凍結為 `encode` / `decode` / `mask_prompt_from_binary` / `release`。公開紀錄不得含 embedding 或 logits。現行 `CandidateSource` 只有：

`sam_box | sam_safe_grid | sam_cv | cv_direct | manual_empty | manual_edit`

現行 `MobileSAMCPUBackend.encode` 把 RGB crop 放進內部 state，`opaque=None`，**不跑 TinyViT**。因此軌道 D **不是**在現有 encode 上加一層 pooling 就能上線。

CV 契約凍結：`lab_threshold` + 明示 L/A/B ranges；每張 runtime 不得估 histogram、fit color model、或改已載入 recipe（`CVR-R001/002/008`）。下列敘述**不是**現行能力：

```text
第一張 Accept → 自動估 threshold／GMM／histogram → 寫回現有 CV recipe
```

---

## 3. 用詞：四種「確認」必須分開

| 使用者動作 | 系統名稱 | 給 SAM 的資訊 | v1 現況 |
| --- | --- | --- | --- |
| 框出／鎖定工作範圍 | `lock_roi` | 搜尋範圍與 box prompt | 已有；換圖未沿用 |
| 點一下「這裡是目標」 | FG `PromptPoint` | 單一 must-include 像素 + previous mask | 已有 |
| 點一下「這裡不是」 | BG `PromptPoint` | 單一 must-exclude 像素 | 已有 |
| 塗一塊「這區是對的目標」且 **仍要 SAM** | `sure_fg` 約束 | 區域 must-include；**不是** brush | **沒有**；軌道 B |
| 塗一塊「這區不是目標」且仍要 SAM | `sure_bg` 約束 | 區域 must-exclude | **沒有**；軌道 B |
| 筆刷改像素 | `manual_edit` | 此後不再跑 SAM | 已有，終端鎖 |
| 提交整張可用 mask | `Accept` | 才有資格當軌道 D 的 teacher | 已有；不可自動升格 artifact |

只做 `lock_roi` **不會**讓邊更準。要修邊，至少需要 sure-FG，通常還需要 sure-BG。把邊緣 pixel 當可遷移外觀類別，不適合作為跨圖主路徑：輪廓是空間交界，略內像前景、略外像背景。

---

## 4. 軌道 A — 下一張沿用 ROI（建議最先量、也最先做）

PRD 階段 0 已寫「構圖穩可沿用上一張」。目前 `openNextItem()` 對新 `item_id` 建新 session，ROI 為空。

**範圍**

- 換圖後可套用上一張已 Accept（或上一張最後鎖定）的 `user_roi_full`，人可立刻改框。
- 新圖仍 **encode 一次**；舊 embedding、候選、點、edits 全丟棄。
- 預設建議：opt-in「沿用上一張框」，不要靜默強迫。
- ROI 超出新圖邊界：clamp 失敗則清空並提示，不得 silently clip 成非法框（遵守 `ROI-R001`）。

**非目標**

- 不沿用 embedding、候選、ConstraintSet、prototype。
- 不自動 Accept。
- 不宣稱這是 class transfer。

這條若已把時間降下來，軌道 D 的「少畫 ROI」主張就沒有獨立價值。§10 的對照組 2 必須先存在，才能評估 D。

---

## 5. 軌道 B — 同圖 confirm-as-constraint（幫助 SAM 的第一刀）

這是「同一張圖先確認一部分，再讓邊緣更準」的**可開發**版本。它是 session／revision 內狀態，**不是** class prototype。局部確認不得自動變成跨圖 teacher。

### 5.1 第一刀範圍（必須 freeze）

做：

- session 擁有 `ConstraintSet`：`sure_fg`、`sure_bg`（crop 解析度 bool mask，互斥）。
- GUI：Confirm-FG / Confirm-BG 工具。可用 lasso、對當前 mask 的 fill-component、或獨立 confirm-brush。
- **不得**呼叫 `session.edit()`，**不得**把快捷鍵 `B` 當確認。
- 在**目前** encoded crop 上：original box + 由 sure 區域抽出的少量內點 + previous mask → `decode(..., multimask_count=1)`。
- 新候選若 `sure_fg` 有任何像素變成背景，或 `sure_bg` 有任何像素變成前景 → 丟棄；**禁止**用 parent OR decode 掩蓋。
- 零張存活：保留父候選、encoder 次數不變、發出 `CONSTRAINT_VIOLATION` 診斷（含違規像素數）；不自動 Accept。
- Undo 可回到確認前的 SAM 候選。ROI 重畫則 ConstraintSet 與 prompt 一起失效。

不做（本軌道 Non-Goals）：

- refine 一次出 3 張卡（凍結 `MPE-R015` / `SES-R006` 為一張）。
- `protected_region` 像素級 equality（可 derived：未標記區當 unknown）。
- 對 unknown band 做 Focus Crop 再 encode（PRD Later：HQ-SAM / FocalClick）。顯示層 zoom 可以，那不是新 crop。
- 把確認當 teacher / `PrototypeArtifact`。
- 新模型、DINO、自動 Accept、預設 pixel OR。

### 5.2 與 brush 鎖的關係（必須寫進 change）

| 操作 | 之後能否 SAM refine |
| --- | --- |
| Confirm-FG/BG | **能**；這是約束，不是 `manual_edit` |
| 既有左／右點 | 能；與 sure 同時生效 |
| 第一次真正 brush/erase/grow/shrink/fill | **不能**；`SES-R008` 維持 |

實作若把 confirm 接去 `edit()`，產品行為會與 5.1 相反。必須新增 op kind（`confirm_fg` / `confirm_bg`），或等價 API，**不可 overload `edit()`**。

真實 local edit 之後：constrained refine 關閉，直到 Undo 回 SAM checkpoint。Local edit 碰到 `sure_*` 的政策第一刀選：**拒絕該筆劃**（比允許改完卻無法 Accept 更可測）。

### 5.3 點怎麼從區域來

第一刀凍結，避免實作時發明：

- `sure_fg`：最大連通元件的內點 medoid **1** 個 FG 點（必須落在腐蝕後仍為 FG 的像素；腐蝕後為空則只用區域約束、不造點）。
- `sure_bg`：最大連通元件 medoid **1** 個 BG 點，規則同上。
- 確認出現後，適用既有「第一個人為提示後丟掉 auto-grid / fusion」（`SES-R007`）。
- 區域約束是候選**過濾器**，不是把 sure_fg 貼到新 mask 上。

可選強化（仍同一 encoded crop）：把 `sure_fg` 當 `mask_prompt_from_binary` 的來源。第一刀**不要**同時開「內點」與「mask prompt」兩條 decode；預設走 **previous-mask + 內點**，因為這是現有 `refine()` 路徑。

### 5.4 建議 API（core，不洩漏 tensor）

```text
confirm_region(candidate_id, kind: sure_fg|sure_bg, region_mask) -> ConstraintSet
clear_constraints()
refine(candidate_id, new_points=())  # 既有；confirm 後仍走這條，multimask_count=1
```

`ConstraintSet` 至少：

- `revision`、`parent_candidate_id`、`crop_fingerprint`、`crop_rect_full`
- `sure_fg`、`sure_bg`（互斥；其餘為 unknown）
- 來源 candidate id

Accept 必須連 dense 約束一起檢查，不只檢查稀疏點。

### 5.5 驗收 oracle（沒有這些不可勾任務）

| ID | 必須為真 |
| --- | --- |
| `CS-ENCODE` | confirm + refine 的 encoder call delta = 0 |
| `CS-FG-HOLD` | `sum(sure_fg & ~mask) == 0` |
| `CS-BG-HOLD` | `sum(sure_bg & mask) == 0` |
| `CS-NO-OR` | 丟棄違規 decode 時，輸出位元 ≠ parent OR decode |
| `CS-EMPTY-FALLBACK` | 0 存活 → 父候選仍選中；無 Accept |
| `CS-NOT-EDIT` | confirm 後 `can_refine=true`，source 不是 `manual_edit` |
| `CS-EDIT-LOCK` | 真 brush 後 constrained refine 被拒 |
| `CS-ROI` | `update_roi` 丟掉 ConstraintSet |
| `CS-TEACHER` | confirm/refine 不寫 `PrototypeArtifact` |
| `CS-COMMIT` | 違規 mask 不得 Accept |

違規次數必須在 **filter 前** 記錄。只報「畫面上 0 違規」不算品質證據（過濾器會把它做成恆真）。

---

## 6. 軌道 C — 離線 LAB calibration（獨立 change）

若要做，流程只能是：

```text
人工 Accept 的 reference
    → 使用者明確執行 calibration
    → 產生新的 immutable CVRecipe（新 recipe_id / hash）
    → 人工檢查後啟用
```

限制：

1. fitting 不在每張 annotation 熱路徑。
2. 不得修改目前已載入的 recipe。
3. 第一刀只估保守、明示的 L/A/B quantile ranges，仍輸出合法 `lab_threshold` JSON。
4. GMM、histogram model、feature prototype **不得**進 `CVRecipe` schema。
5. 資料不足必須 abstain，不得留下看似有效的配方。
6. 獨立 calibration split；不得在 teacher 或 test sibling 上調 threshold。

這條解決的是「顏色可分、不想每次重寫 recipe」，不是「跨圖學邊」。

---

## 7. 軌道 D — 跨圖 prototype proposal（spike 後才寫規格）

### 7.1 適用範圍

強度由高到低：

| 情境 | 預期 |
| --- | --- |
| 同一實體、固定相機／工作距離／光照，只有平移、曝光等小變化 | 最適合 |
| 同一產品類別、不同實例，外觀與拍攝受控 | 可能有效；必須報 teacher sensitivity |
| 跨材質、跨視角、跨產線 | 預設停用 |
| anomaly／defect | 可能只學到該張 defect 外觀，**不得**宣稱學到一般異常性 |

Artifact 至少綁：

```text
(class_id, capture_profile_id, model_identity, feature_layer, preprocessing_identity)
```

`capture_profile_id` 在現行程式**不存在**。第一個 spike 允許用手動字串（例如 `line-A/wd-300mm/ring-light`）。要進 OpenSpec 時必須定義：誰建立、何時 mismatch hard-fail、不相等不得靜默沿用。若暫時不定義，就從 artifact 拿掉這個欄位，並接受 §3 寫過的 domain-shift 風險。

相機、crop 規則、checkpoint 或 preprocessing 改變時必須重新 Fit 或拒絕，不能因「向量維度都是 256」判定相容。

### 7.2 三條路徑不要混

| 路徑 | 知道什麼 | 本軌道 |
| --- | --- | --- |
| Reference prototype matching | 使用者指定的是哪個目標 | **唯一主路徑** |
| 同圖 TokenCut／SSL | 哪裡像一個完整物體，不知道是不是指定 instance | Non-Goal；PRD Later |
| 一張圖 fine-tune（PerSAM-F 等） | 可能過擬合也可能有效，必須另證 | Non-Goal；v1 禁止自訂訓練 |

### 7.3 Teacher trimap（spike 凍結一條公式）

Teacher **必須**是 `interactive_user` Accept，且 `training_eligible=true`。未確認的 SAM 卡不得建 artifact。Scripted Accept 不得當 production teacher。

Spike 與第一個 change 使用**同一條**公式，不要「像素或對角線或物件尺寸」三選一寫在規格裡：

```text
erode_px = clamp(round(0.01 * diagonal_full), min=2, max=15)
dilate_px = erode_px

sure-FG  = erode(accepted_mask, erode_px)
near-BG  = dilate(accepted_mask, dilate_px) 的外側環帶
global-BG = 該張 user_roi 內、非 dilate(mask) 的背景，分層下採樣
unknown  = 其餘，不參與 fitting

若 sure-FG 映射到 feature grid 後有效 token < 8 → abstain，不建 artifact
若 sure-BG token < 8 → abstain
```

採樣：FG/BG 都分層，避免大背景淹沒 hard negatives。第一個 spike **同時記錄**單一 mean 與最多 4 個 BG medoid，但 **production 預設先不定**；由校正 split 選一個政策後寫進 artifact，之後凍結。

絕對相似度易隨光照／crop 變。排序與 abstain 用 `margin = sim_fg - sim_bg`（cosine，L2-normalized）。閾值只在獨立 calibration split 上定，禁止在 teacher 或 test sibling 上調。

### 7.4 產品資料流

```text
人工 Accept 的 reference（全圖 PNG + sidecar，不是 session logits）
        ↓
使用者明確 Fit（離線，非熱路徑）
        ↓
immutable PrototypeArtifact（hash；失敗則不寫檔）
        ↓
新圖：人 lock_roi（可來自軌道 A）→ 該圖 encode 一次
        ↓
provider 內 match（重用這個 EncodedState，禁止第二輪 target encode）
        ├─ abstain：0 張 prototype 候選，走既有 SAM／manual
        └─ 粗 binary（crop 解析度）→ mask_prompt_from_binary → decode
                                ↓
                      公開候選仍 ≤3，其中 prototype 最多佔 1 槽
                                ↓
                      人選 → 既有點 refine / brush / Accept
```

第一個人工正／負點、confirm、或 local edit 出現後，prototype 慢路徑必須丟棄，不得覆寫。

### 7.5 Prototype 只提案，且必須能在 decode 前 abstain

凍結第一刀的提示轉換（只選一條）：

- **用** crop 解析度粗 binary → 既有 `mask_prompt_from_binary`（與 `sam_cv` 同機制，但 **source 不得叫 `sam_cv`**）。
- **不用**自動抽正負點當第一刀。自動點已有 bounded safe-grid（`MPE-R011`）；粗 mask 抽點與 `MPE-R012`／`CVR-R014` 衝突風險高。

Abstain（**decode 之前**，不可用 SAM quality/stability 救援弱匹配）：

- checkpoint / preprocess / feature_layer 不符
- FG/BG token 不足
- `margin` 低於 artifact 內凍結閾值
- 高於 1 個相近峰值（多 instance；第一刀直接 abstain，不要猜哪顆）
- 粗 mask 碰到 `crop_rect` 邊超過既有 crop-edge 規則能接受的程度
- 相容性 hard-fail

Abstain 回傳 0 張 prototype 候選，不是一張空 mask、也不是複製 `sam_box` 填滿三槽。

### 7.6 現行程式缺口（spike 必須面對）

| 項目 | 現況 | 之後 |
| --- | --- | --- |
| Provider API | `encode/decode/mask_prompt_from_binary/release` | 可選 `supports_reference_prototype`；`fit_reference` / `match_reference` 留在 provider 內 |
| MobileSAM encode | RGB + `opaque=None` | spike 用官方 `SamPredictor.features`（256×64×64）；正式 backend 若要支援 D，必須先有真 encode |
| 特徵格子 | 未公開 | `cell_px = 16 * max(H,W) / 1024`（long side resize 到 1024）。256 長邊 ≈ 4 px/cell；512 ≈ 8 px/cell |
| 候選來源 | 無 prototype | 新增 `sam_prototype`；**禁止**假扮 `sam_cv`；`allocate_candidates` 最多 1 張；計入 3 槽 |
| `refine()` allow-list | box / grid / `sam_cv` | 若 `can_refine=true`，prototype-prompted SAM 必須明文列入 |
| 持久化 | 無 | artifact 走 adapter，不進 accepted training 目錄；**禁止**把 session embedding 寫碟（`MPE-R005`） |
| `CVRecipe` | `additionalProperties: false` | 禁止 union 成 `recipe_or_prototype` |

Mean FG/BG 是 **spike baseline**，不是已證明的 production 預設。TinyViT 特徵是給 decoder 用的。小缺陷在 64×64 上可能 <1 cell；ROI 內多個相似物會讓 mean prototype 點亮所有實例，SAM 再畫出「很銳利但找錯目標」的邊。這是負遷移，不是品質成功。

Matcher / DINOv2 完整對應：另一次 later，且要過 CPU/RAM/license。本軌道第一刀失敗時，**預設結論是停用 D**，不是自動改上 DINO。

### 7.7 `PrototypeArtifact` 最小欄位

與 `CVRecipe` 分開的新 schema。至少：

- `schema_version`、`artifact_id`、`class_id`、可選 `capture_profile_id`
- reference annotation id、reference image SHA-256、accepted mask SHA-256
- `ModelIdentity` + `feature_layer`（例如 `mobilesam-image-encoder-v1`）
- reference ROI/crop geometry、feature grid shape、trimap 參數（含 `erode_px`）
- prototypes：dtype、normalization、mean 或 medoid 向量；**canonical 序列化後再 hash**（禁止 raw `numpy.save` 當契約）
- `similarity: cosine`、凍結 `abstain_margin`、`max_peaks`
- 建立時間與建立者；immutable；重建 = 新 `artifact_id`

原始 provider tensor 不得進 GUI/core。Fit 回傳的 artifact 只含向量與 metadata。

### 7.8 開工前必做的離線 spike（沒過就不要開 D 的 tasks）

Harness：官方 `SamPredictor`（與 `benchmarks/mvtec_mobilesam_smoke.py` 同源），**禁止** gold-replay backend，**禁止**改正式 `Backend` 協議當第一步。

1. Teacher：Accept/gold mask → §7.3 trimap → 記錄 FG/BG token 數。
2. `set_image` 後讀 `predictor.features`。Fit mean FG/BG 與 2–4 medoid。只持久化向量。
3. Target：**一次** `set_image`；算 margin heatmap；連通元件；畫 abstain 曲線（margin / peak 數 / token 數）。
4. 未 abstain：粗 binary → mask prompt → 既有 predict。公開仍 ≤3。
5. 四組對照見 §10；**按 base/scene ID 分組**；多個 teacher，報 median **與** worst teacher。
6. 切片：目標在 feature grid 的面積（&lt;9 / 9–100 / &gt;100 cell）、ROI 內 distractor 數、BG 是否與 teacher 同類。
7. 記錄：target 額外 encode 必須為 0、CPU p50/p90/p95、peak RAM vs SAM-only、wrong-target、worse-than-沿用 ROI+SAM、boundary F1（IoU 僅輔助）。

**Go / no-go：** 相對對照組 2（沿用 ROI + SAM）沒有降低時間或操作、邊界退步、或多 instance 切片 wrong-target 高 → **停用**，不要加 Matcher/DINO 進同一 change。

負遷移（規格必須當失敗，不當「模型很有信心」）：

- 多相似實例 → 高分錯目標
- teacher 略肥的 mask 污染 sure-FG
- 新圖背景改變導致 `sim_fg - sim_bg` 反號
- crop 長寬比改變，padded 64×64 上的位置先驗不可搬
- 把 SAM 分數當 matching 信心

---

## 8. 什麼時候可能加速（期望管理）

較可能有用：

- 同一 `class_id` 與拍攝條件；目標在 ROI 內可分；相似干擾少。
- reference mask 可靠；目標不是極小／極細（feature 上至少數個 cell）。
- 軌道 A 已沿用 ROI，D 只負責少點錯目標。

較可能沒有幫助：

- 細長、低對比、半透明、強反光邊（prototype 頂多幫定位）。
- 每張光照或外觀差很大。
- 滿屏相似物且無 ROI。
- 沒在 reference 出現過的 defect mode。

即使粗定位準，輪廓仍以 boundary F1／boundary distance／trimap 與人工 Accept 衡量。不得宣稱「邊緣已被學會」。

---

## 9. 驗證：先排除「沿用 ROI」的貢獻

`AOB-R014`：optional post-baseline feature 只有在受控比較中降低時間或操作、且不傷 frozen boundary gate，才能預設啟用。缺 Tier C 不得拿來阻擋 M0–M4；缺證據時特徵維持關閉。

### 9.1 四組對照（同一批圖、同一候選上限、同一人工流程）

1. 每張重畫 ROI + SAM。
2. **沿用 ROI + SAM**（評估 D 的對照組；沒有這組不准宣稱 prototype 有效）。
3. 沿用 ROI + **人手明示**的固定 CV recipe（禁止用本實驗臨時 fit 的 recipe 冒充 v1 CV）。
4. 沿用 ROI + prototype proposal + SAM。

軌道 B 另比：既有點+brush vs confirm-as-constraint；不要跟跨圖混在同一張表。

### 9.2 防洩漏與防灌水

- MVTec 的 `000_regular` / `000_shift_*` / `000_overexposed` 是同一 capture group。Teacher、calibration、test 不得跨組拆開又當「跨圖」。
- 輪流不同 teacher；報 median 與 worst。不得只報最好的一張。
- 106/120 scene 共用同一張 mask 的衍生圖：那是光照不變性，**不是** class transfer。若要用 MVTec，結論只能寫「同實例、不同曝光／平移」，不能寫「類別遷移成功」。
- MVTec AD 2 為 CC BY-NC-SA、`commercial_use_authorized: false`。它不能當出貨品質門或訓練資料。出貨主張需要另份已授權 corpus。
- **禁止** gold-replay harness（已知可把 boundary F1 做到 1.0、數十毫秒）當 retention 證據。
- **禁止** `acceptance_actor=scripted_test` 證明 time-to-accept 或人 Accept（`SES-R011-S05`）。Spike 可標成 observational；預設開啟需要 `interactive_user` 或維持關閉。
- IoU 輔助。主度量用既有 `segvision-symmetric-boundary-f1-v1`、全圖 mask。Teacher 與 sibling 不得混進 test 聚合。
- Constraint-violation=0 若只在過濾後計算，不得當品質門（見 `CS-*`）。

### 9.3 必報指標

- time-to-accept（起點 `first_roi_locked`）、prompt、click、stroke、Undo、Needs Review。
- candidate recall@3、實際選卡率。
- wrong-target、negative-transfer、worse-than-對照組 2 的比例。
- boundary F1 / boundary distance / frozen trimap；IoU 輔助。
- abstain 率、abstain 後 fallback 成功率（高 abstain 不是自動失敗，但也不能當「功能有效」）。
- 軌道 B：filter **前** 的 constraint violation、retry；畫面上已確認像素 violation 必須為 0。
- CPU p50/p90/p95、peak RAM、artifact load/compatibility failure。
- export/import 後 artifact hash 可重現。

人工任務順序需隨機化或 counterbalance。若 prototype 只改善 teacher 或同 base-ID sibling，維持預設關閉。

尚未凍結、因此 **不可寫進第一個 production schema 當魔法數字** 的項目：`abstain_margin`、medoid 數、是否上 Matcher。這些只能來自校正 split，再寫進該版 artifact。

---

## 10. 建議執行順序

1. **保住 frozen v1。** 不要把 fitting、ConstraintSet、prototype 插入 `build-segvision-v1`。
2. **軌道 A。** 換圖沿用 ROI；建立對照組 1 vs 2。
3. **量 bottleneck。** 時間主要在重畫框、選錯目標、還是刷邊？沒有這份數字，不准開 B+D 大包。
4. **軌道 B 第一刀**（僅當刷邊／retry 是主成本）：confirm-as-constraint，§5 範圍，§5.5 oracle 全綠。Focus Crop 與 3-card refine 明確 Later。
5. **軌道 D 離線 spike**（僅當錯目標是主成本，且 A 的對照已存在）。不過 go/no-go 就停。
6. **過 spike 後才開 D 的 OpenSpec：** capability、artifact、`sam_prototype` 佔槽、abstain、adapter 持久化、AOB-R014 預設關。
7. **軌道 C** 僅在顏色可分且不想手寫 recipe 時獨立開。
8. **永遠不插隊：** silent online update、prototype 當最終 mask、候選複製填滿、模型覆寫人工編輯、自動 Accept、DINO 熱路徑、gold-replay 當品質證據、未授權 MVTec 當出貨門。

---

## 11. 決策摘要

```text
一張已標圖的槓桿 = 把「使用者要的是誰」凍結成 reference artifact
                 ≠ 把「邊在哪」訓練成可跨圖 appearance class

同圖確認一部分     = sure_fg / sure_bg 約束 + 現有 previous-mask decode
                 ≠ brush、≠ 3 張 refine、≠ Focus Crop、≠ teacher

現行 v1           = 明示 immutable LAB recipe + ROI box SAM + 點 refine + brush 鎖 + 人 Accept
軌道 A            = 換圖沿用 ROI 座標（仍重新 encode）
軌道 C            = 顯式離線 calibration，新 recipe 版本
軌道 D            = 可 abstain 的粗 mask prompt，最多 1 張新來源候選

粗區域：固定 CV 或（later）feature similarity
最終邊：SAM（或已過 direct gate 的固定 CV）+ 人 Accept
```

本文件仍不構成 v1 實作授權。開 change 時標題只能是 A、B、C、D 其中一個；把其餘列為 Non-Goals。
