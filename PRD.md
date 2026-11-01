# SegVision — PRD (v1 凍結)

## 一句話

一個可重用的 **common function + 薄 GUI**，讓工程師在**全新場景、無 GPU、零標註資料**下，
先畫**小 ROI**，再於 crop 上用 CPU 輕量 SAM 出 **3 個候選**，人在 **< 30 秒/張** 內 Accept，
產出可餵訓練的 mask。

## 使用者與情境

- 使用者：公司內部 ML / 影像工程師，不是專職標註員。
- 資料：**靜態圖**（非影片）。
- 目標物：v1 **一張圖一塊二值前景**。少數類別 later（每類各算 30 秒）。
- 場景：**全新 domain**，沒有既有標註、不能先訓模型。
- 硬體：**沒有本機 GPU**。加速手段不是換卡，而是**人把 ROI 畫小**，只對 crop 跑 CPU 推論。

## 核心痛點

SAM 單點對位置敏感，常常拿不齊人眼看得見的邊。
正解不是多點聯集，而是 **ROI＝box prompt → 一次編碼 → 3 候選讓人秒選 → 正負點帶著上一張 mask 迭代 → 只修不確定帶**。

## 凍結決策（2026-08-27 人拍板）

| # | 決策 |
|---|---|
| 1 | 無本機 GPU。加速 = 人畫小 ROI，只對 crop 跑 CPU SAM / 輕量模型。 |
| 2–3 | 傳統 CV **每類鎖死一份配方**。可 **匯出 / 匯入** 沿用。禁止每張調直方圖。 |
| 4 | 成功標準 **兩者都要**：客觀邊誤差（輪廓距離或 trimap）**以及** 工程師 Accept＝可餵訓練。 |
| 5 | 預設 **秀 3 個候選**（鍵 `1`/`2`/`3`）。融合是 opt-in，不是預設。 |

補充凍結：

- common function **回候選，不回最終答案**。最終 mask 只在人 Accept 後產生。
- 禁止像素 OR / 未校準分數投票當預設融合。
- v1 不訓練自訂模型；VLM / DINO 尋點不進主路徑。

## 硬性限制

| 項目 | 值 |
| --- | --- |
| 每張人力時間 | < 30 秒（ROI 鎖定 → Accept） |
| Overlay / 筆刷 | < 100 ms |
| 第一次候選（crop encoder + 3 mask） | 盡力；無 GPU 時靠 ROI 夠小才成立 |
| 之後每次正負點（只跑 decoder） | 盡力 ≤ 1 s；ROI 太大就提示縮小 |
| 訓練資料 | 無 |
| 影像 | 靜態圖 |
| 交付 | `import` 得了的 common function + 包在外面的 GUI |

## v1 範圍

**In**

- 人畫矩形 ROI（可 pad ~10%）。分析與 SAM 都只在 crop 上跑。
- ROI 當 **box prompt**；另加 ROI 內少量 grid 正點。
- CPU 輕量 SAM（優先 MobileSAM / EdgeSAM / ViT-B ONNX；不以 ViT-H 當預設）。
- 同一 crop **編碼一次、解碼很多次**。ROI 變才重算 embedding。
- 回 **1 主候選 + 2 替代**（SAM 原生 3-mask + iou/stability 排序）。
- 正 / 負點 refine，必須帶 **上一張 mask logits**。禁止無記憶的裸連點。
- 不確定帶（候選不一致或貼齊 ROI 邊）給人看。
- 筆刷、±1px、補洞。這段 **不再跑 SAM**。
- 每類一份 CV recipe：可關；匯出 JSON、之後載入。CV 粗 mask 餵 SAM 用 **mask prompt**，不是抽成點。CV 已夠乾淨則 **跳過 SAM**。
- 輸出：全圖 PNG mask + sidecar（ROI、class、prompts、來源、recipe id、時序）。

**Out（v1）**

- 本機 GPU 假設、ViT-H、四路每次全開。
- 預設像素融合 / 全域 OR。
- 每張現場調 HSV。
- VLM / 文字進自動熱路徑。
- DINO 自動尋點。
- 多類別 tab、影片、訓練自訂模型、自動 Accept。
- 把 Qt / Web / napari / CVAT 當開工阻塞。

**Later**

- opt-in 融合（最多三張 logits：`sam_box`、`sam_cv`、之後的 `dino`；票≥2 為 FG、票=0 為 BG、票=1 為黃帶）。
- DINO / TokenCut 尋點（只在 ROI crop、失敗才開）。
- 文字 / Grounding DINO / SAM3（寫進該類配方，不每張問模型）。
- HQ-SAM / FocalClick 式 Focus Crop 修邊。
- 少數類別（不重畫 ROI、不重編碼）。
- 其他輸出格式（COCO RLE 等）。

## 每張圖流程（目標 ≤30s）

| 階段 | 誰 | 做什麼 |
|---|---|---|
| 0 畫 ROI | 人 | 框小區域。構圖穩可沿用上一張。太大 → UI 警告 CPU 會慢。 |
| 1 crop | 系統 | 裁切；顯示給 SAM 的最短邊建議 ≥256、最長邊建議 ≤512（無 GPU）。 |
| 2 編碼一次 | 系統 | 只算這個 crop 的 embedding。 |
| 3 必跑 | 系統 | ROI box → 3 張 mask。 |
| 4 條件 | 系統 | 該類 recipe 開了 CV 才跑；品質差或貼邊泄漏才考慮。 |
| 5 顯示 | 系統 | 3 候選 + 黃帶。預設高亮第 1。 |
| 6 選 | 人 | `1`/`2`/`3`，或直接點。 |
| 7 迭代 | 人+decoder | 左正右負。cached embedding + 點 + 目前 logits。 |
| 8 像素 | 人 | `[` `]`、補洞、筆刷。 |
| 9 提交 | 人 | uncrop 回全圖。`N` 下一張。 |

人一開始點正負點：**當輪融合結果丟掉**，改走迭代。人的點硬優先。

## Common function 契約

GUI、快捷鍵、之後腳本都打同一層。無副作用、不碰檔案（I/O 由呼叫端做）。

```
propose(image, roi, class_id, recipe) ->
  ProposalSet {
    embedding_id,
    candidates[≤3],      # mask, logits, score, source, warnings
    uncertainty,         # 黃帶
    crop_ctx,
    timings
  }

refine(embedding_id, mask_logits, pos_points, neg_points) ->
  Candidate                  # 禁止重算 encoder

edit_local(mask, op) -> mask # grow|shrink|fill_holes|brush；不再跑 SAM

fuse(candidates, mode) ->    # v1 可存在但 GUI 預設不呼叫
  FusionResult               # 禁止全域 OR

commit(mask_in_roi, crop_ctx) ->
  full_image_mask

recipe_export(class_id) -> JSON
recipe_import(JSON) -> recipe
```

失敗要誠實：低分、貼邊泄漏、空 mask → 呼叫端應直接進筆刷，不裝成好邊。

## GUI 方向

- 中：原圖 + ROI + 當前候選填色 + 黃帶。預設不疊三張半透明。
- 右：3 張候選卡（縮圖、source、score、警告）。
- 左：該類 recipe 開關（CV 預設跟配方走）；`匯出設定` / `載入設定`。
- 融合開關預設關。打開才套 `fuse()`，人仍可改選候選。
- 操作：點 ROI 第一角，再點對角；`1/2/3`；左/右鍵正負點；`[` `]`；`F` 補洞；`Z` undo；`Space` Accept；`N` 下一張。
- 游標旁 loupe 修邊。
- ROI 面積超過 CPU 預算時，提示縮小，不要默默卡死。

## 成功標準（兩者都記）

每張 Accept 時寫 sidecar：

1. **客觀：** 若有 GT 或抽樣複核，記輪廓距離（例如 mean boundary distance）或 trimap 帶內誤差。回歸用這個，不要只用 IoU。
2. **主觀：** 工程師 Accept＝可餵訓練。記秒數、點擊數、筆劃數、是否縮小過 ROI、用了哪條候選 / 是否開融合。

v1 沒有大規模 GT 時：先用（2）當開工閘，抽一小批人工複核補（1）。

## 現況

- 規格已凍結到本文件。尚無產品程式碼。
- 討論紀錄：`.ai-staff/discussions/`（含 2026-08-27 人決策）。
