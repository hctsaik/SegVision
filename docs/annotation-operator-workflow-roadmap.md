# SegVision 標註操作完整化路線圖

## 目的

SegVision 已具備 MobileSAM 框選、加入／排除提示點、畫筆、擦除、Undo、區塊鎖定、Merge、多區塊工作及 lossless PNG + JSON sidecar 存檔。下一階段的重點不是增加模型，而是讓日常標註具備以下特性：

1. 工作不會因當機、切圖或關閉 App 而遺失。
2. MobileSAM 計算卡住時，操作者能取消、重試或復原。
3. 大量圖片能依狀態排程、恢復與追蹤進度。
4. 存檔前能看懂遮罩品質問題，並快速跳到問題位置修正。
5. 不離開 Native App 就能完成 LabelMe 匯出、預覽及回匯。
6. 安裝與更新可驗證、可離線，且預設不連網、不回傳遙測。

## 產品原則

- 既有 MobileSAM CPU 路徑維持唯一模型 hot path，不新增 GPU、雲端推論或其他模型提供者。
- 自動儲存只能產生「草稿」，不得偽裝成 Accepted，也不得進入訓練資料 loader。
- Accepted PNG + JSON sidecar 保持 lossless source of truth；LabelMe polygon 是衍生輸出。
- `Defect` 是沒有專案設定時的固定預設類別；明確的專案類別必須留下來源與版本。
- 每個會改變遮罩的操作都必須可追溯，Undo／Redo 不得偷偷重跑模型。
- App 不得因背景計算、更新檢查或診斷上傳而依賴網路。

## 操作者主流程

```text
開啟資料集
   ↓
挑選「未完成／草稿」圖片
   ↓
框選 → SAM 候選 → 加入／排除點 → 畫筆／擦除 → 鎖定／Merge
   ↓                         ↓
每個完成操作原子寫入草稿       可取消／重試 MobileSAM
   ↓
品質檢查：破洞、孤立小點、邊界、區塊數、空遮罩、近全圖
   ↓
預覽最終 PNG 與 LabelMe 清理後 polygon
   ↓
Accept / Needs Review
   ↓
直接匯出 LabelMe → 下一張未完成圖片
```

## P0：工作安全與交付閉環

### 1. 自動儲存草稿與當機恢復

每次完成的 ROI、SAM 提示點、候選切換、畫筆／擦除 stroke、鎖定、解鎖、Merge、Undo 或 Redo 都建立一個 session-owned checkpoint。checkpoint 以 sidecar-last 的原子方式寫入專用 draft namespace；pointer move 與尚未 pointer-up 的 stroke 不寫入。

重啟 App 後，若目前圖片有 loader 驗證通過的草稿，顯示：

- `繼續上次標註`
- `檢視草稿資訊`
- `捨棄草稿`

草稿必須包含圖片 fingerprint、class、ROI、active mask、鎖定區塊、提示點、操作歷史、revision 與 checksum。來源圖片或版本不符時只顯示隔離警告，不可自動套用。

### 2. 未存檔防呆

以下行為若存在 dirty draft，必須先顯示具有明確結果的確認：

- 切換圖片
- 開啟另一個資料集
- 關閉 App
- 重新啟動 sidecar
- 安裝更新

選項為 `先儲存草稿`、`捨棄並繼續`、`取消`。不得以模糊的「確定／取消」代替。

### 3. MobileSAM 取消、重試與引擎恢復

當 job 為 pending 或 running 時顯示 elapsed time 與 `取消計算`。取消必須是 job-scoped，不能清除目前可見的已完成遮罩。

失敗或逾時後提供：

- `使用相同 ROI 重試`
- `回到上一個 checkpoint`
- `重新啟動 MobileSAM 引擎`
- `匯出診斷資料`

引擎重啟必須取得新的 port/secret，重新驗證草稿後才恢復 mutation。診斷資料只能包含去識別的版本、模型 checksum、job 狀態、錯誤碼與時間，不得洩漏圖片路徑、launch secret 或原始影像。

### 4. Native App 內 LabelMe 匯出

Accepted 後顯示 `匯出 LabelMe`，支援單張與整批輸出。輸出前顯示：

- Label：預設 `Defect`
- polygon 數量
- 清理前／清理後面積差
- 是否補洞、閉合一像素缺口或簡化輪廓
- imagePath 是否能解析到原圖

使用者確認後才寫入標準 LabelMe JSON。Accepted PNG 與 sidecar 不因 polygon 清理而修改。

### 5. LabelMe 多邊形預覽

Canvas 可切換：

- lossless mask
- 邊界線
- LabelMe 清理後 polygon
- 清理差異區域

若面積差超過凍結門檻，匯出必須要求確認或阻擋，並指出受影響區域。

## P1：標註效率與品質

### 6. Redo 與操作歷史

新增 Redo 與可折疊操作歷史。歷史項目至少包含：

- SAM ROI
- 候選選擇
- 加入／排除提示點
- 提示點移動或類型切換
- 畫筆／擦除 stroke
- grow／shrink／fill holes
- 鎖定／解鎖區塊
- Merge
- Undo／Redo 的目標 checkpoint

Undo／Redo 必須恢復精確 session state，不能由 React 自行保存遮罩，也不能為了恢復歷史重新 encode。

### 7. SAM 提示點移動與加入／排除切換

選取既有提示點後，可：

- 拖曳或點選新位置
- 將加入點切換為排除點
- 將排除點切換為加入點
- 刪除提示點

每次變更由原始 SAM state 依有序提示點 replay，encoder call 必須為零。若新結果失敗，原提示點與遮罩原子復原。

### 8. Dataset 工作佇列

左側圖片清單新增狀態：

- 未處理
- 草稿
- 已接受
- 待複核
- 存檔失敗
- 草稿衝突／損毀

支援狀態篩選、檔名搜尋、進度統計、下一張未完成、重新開啟草稿，以及 Accepted／Needs Review 的唯讀檢視。`下一張` 預設跳到下一張未完成，而非單純下一個檔名。

### 9. 遮罩品質檢查

在 Accept 前執行快速、確定性的本機檢查：

- 空遮罩或近全圖遮罩
- 碰到來源影像邊界或 padded crop 邊界
- 孤立小區塊
- 封閉孔洞
- 過窄的一像素橋接
- 前景區塊數量異常
- LabelMe 清理前後差異過大

右側顯示問題清單；點選問題後縮放至對應 bbox。警告需中文顯示、可去重、可回復，且 acknowledgement 寫入 sidecar。

### 10. LabelMe 匯入與 round-trip

Native App 可讀取標準 LabelMe polygon JSON，驗證 imagePath、尺寸、label 與 polygon 合法性後 rasterize 成新草稿。匯入不得覆寫 Accepted 結果；若同一圖片已有 dirty draft，必須要求另存新草稿或明確取代。

匯出後再匯入的 round-trip 必須在凍結容差內保持遮罩與 label；不支援的 shape_type 必須明確列出，不能靜默忽略。

## P2：專案與交付管理

### 11. 專案類別管理

沒有設定時固定使用 `Defect`。專案可選擇性定義少量類別清單、顯示名稱、快捷鍵與輸出 label。類別變更屬於 project-level metadata，不是每次存檔臨時輸入。

已開啟 session 的 class 不可無聲變更；重新分類時要留下原類別、新類別、操作者與時間。

### 12. 版本、安裝與更新

About／版本頁顯示 App、protocol、Python sidecar、MobileSAM model checksum 與 build ID。更新支援：

- 手動選取已簽章的離線更新包
- checksum 與簽章驗證
- 更新前草稿 flush 與 session 關閉
- 更新失敗 rollback
- 更新後啟動、sidecar health 與 loader smoke

自動網路更新、telemetry、analytics 與 crash upload 預設關閉；沒有網路時完整標註流程仍必須可用。

## 既有功能的收尾

獨立的 `編輯範圍` 已採 PhoneCV 兩點式操作，但仍需完成正式 native 驗收：

1. 第一點與對角第二點建立 half-open `XYXY` 範圍。
2. 完成後點擊會更新距離較近的角點。
3. 畫筆與擦除的完整 radius 都不得越過範圍。
4. 操作不得呼叫 `sessions.lock_roi` 或觸發 MobileSAM。
5. 在原圖縮放、平移及非 1.0 DPR 下仍保持相同 full-image 座標。

## 分階段交付

| 階段 | 內容 | 完成條件 |
|---|---|---|
| R1 工作安全 | 草稿、dirty guard、取消／重試／引擎恢復、診斷 | 強制終止 sidecar／App 後可恢復最後 checkpoint；未發布假 Accept |
| R2 LabelMe 閉環 | App 內匯出、polygon 預覽、差異警告、匯入 | 單張與整批 round-trip E2E 通過 |
| R3 生產力 | Redo、歷史、提示點移動／切換、工作佇列 | 100 張資料集可依狀態篩選並續作 |
| R4 品質與類別 | QA、問題導航、專案類別 | 警告、acknowledgement、sidecar provenance 一致 |
| R5 更新交付 | 版本頁、簽章離線更新、rollback | clean Windows、離線、更新前後 Accept／reload smoke 通過 |

## 非目標

- 不新增 GPU、cloud inference、SAM 2/3、HQ-SAM 或第二個模型 provider。
- 不增加自動 Accept。
- 不讓 LabelMe polygon 取代 lossless PNG + sidecar。
- 不做多人即時協作、帳號系統或雲端同步。
- 不在未取得簽章、授權與 clean-machine evidence 前宣稱正式可更新版本。

## OpenSpec 對應

本文件由 `complete-annotation-operator-workflow` change 規範。OpenSpec artifacts 位於：

`openspec/changes/complete-annotation-operator-workflow/`

實作時應依 `tasks.md` 順序進行，先完成安全與持久化，再做互通、效率、品質，最後才做更新交付。
