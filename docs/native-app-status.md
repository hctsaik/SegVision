# SegVision 功能、進度與測試說明

> 日期：2026-11-04
>
> 這份文件記錄**現況**，不是完成宣告。Chromium Playwright 流程已有可重現的影像／ROI／遮罩／Accept 持久化驗證；真正 Tauri 視窗仍未完成同等 E2E。

---

## 1. 產品是什麼

SegVision 是 **Windows x64、CPU-only、離線** 的靜態圖二值標註工具。

工程師畫一小塊 ROI，系統最多給 **3 個真實候選**（不填假卡），人用快捷鍵挑選、正負點 refinement、筆刷修補，再明確 **Accept** 或 **Needs Review**。最終 mask 只在人 Accept 且通過驗證後才寫出。

凍結規則（不可在 GUI 改寫）：

- 不自動 Accept
- 不跑 GPU / 雲端推論 / VLM / DINO / SAM 2
- 核心 `src/segvision/core` 保持 headless、in-memory
- Python session 是 mask / revision / 候選的唯一真相

---

## 2. 現在的架構

預設桌面殼層是 Native App，不是把演算法改寫成 JS/Rust：

```text
操作者
  → React UI（apps/desktop-ui）顯示與未提交預覽
  → Tauri 2 Host（apps/desktop-host），或 NativeApp 公開 HTTP web host（同源 /v1 proxy、cimHost 資料夾選擇）
  → Python sidecar（127.0.0.1 隨機 port）
  → 既有 SegVision core / fake 或 MobileSAM / PNG+JSON 持久化
```

| 層 | 路徑 | 責任 |
| --- | --- | --- |
| 協定 | `packages/desktop-protocol/` | OpenAPI 1.1、事件 schema、錯誤碼 |
| Sidecar | `src/segvision/application/`、`src/segvision/transport/desktop_api/` | session、revision、job、asset |
| UI | `apps/desktop-ui/` | Canvas、候選卡、快捷鍵 |
| Host | `apps/desktop-host/src-tauri/` | 檔案選擇器、proxy、`segvision-asset://` |
| 舊 GUI | `src/segvision/gui/` | PySide6，仍可啟動 |

啟動入口（預設 Native App）：

```powershell
segvision-gui
segvision gui
npm --prefix apps/desktop-host run dev
```

舊 PySide6：

```powershell
segvision-pyside6
segvision pyside6
```

`import segvision` 仍不會開視窗、綁 port 或載模型。

---

## 3. 工作進度

### 3.1 已完成（機器可驗）

| 區塊 | 狀態 |
| --- | --- |
| v1 Python 核心（ROI、最多 3 候選、refinement、local edit、Accept / Needs Review） | 已有既有 pytest / GUI / E2E |
| OpenSpec change `adopt-react-tauri-desktop`（proposal / design / specs / tasks） | 規格齊，`openspec validate` 曾通過 |
| 桌面協定 1.1（含 `lock_roi` / `select` / `undo` / `close` 等） | 已落地 |
| Python sidecar（health、資料集、session、binary asset、Accept / Review） | 已落地 |
| React UI + Vitest | 2026-11-04 在此分支重跑 `npm --prefix apps/desktop-ui test`：6 個測試檔、68/68 通過；`npm --prefix apps/desktop-ui run build` 正式建置通過。涵蓋資產載入錯誤、快速切圖與 mutation 不會套用舊 snapshot、輸出 grant、關閉舊 session、host-private 持久化路徑不留在 store、資料集 cursor 續載與全清單搜尋、選擇輸出資料夾後刷新目前清單的工作狀態，以及 durable Needs Review 的非訓練結果與 Accept 失敗不得誤報成功 |
| Chromium Playwright E2E | `tests/desktop-e2e` 驗證受保護 asset、160×120 影像、gold 與候選 overlay、ROI authoritative snapshot、candidate mask hash；另分別驗證 Accept PNG+sidecar 與 Needs Review metadata/draft/hash、`training_eligible=false` 且沒有 accepted pair。這是 Chromium+Vite，不是真實 Tauri 視窗 |
| NativeApp 公開 web-host E2E | 2026-11-04 source 可見旅程經 NativeApp SegVision wrapper、React dist、同源 `/v1` proxy 與合成資料夾 picker，走完 ROI、候選及 Accept，再停止 host 並以不同 PID 重啟。Chromium 重開 React、重新選資料集與輸出資料夾後，畫面仍顯示「已接受 1」；PNG 與 sidecar bytes／hash 完全相同，fixture 原始檔 hash 不變。fake backend `1 passed`（11.56 秒）；opt-in MobileSAM CPU local-evaluation `1 passed`（CPython 3.11.9 AMD64、CPU PyTorch 2.7.1，36.87 秒），checkpoint SHA-256 `6dbb90523a35330fedd7f1d3dfc66f995213d81b29a5ca8108dbcdd4e37d6c2f`，health 明示 local evaluation／release not approved。這是來源版 React／API host 證據，不是 packaged release；使用合成影像與資料夾 picker。OS picker、真實 Tauri 視窗及發布包仍未驗。`test_work_status_reloads_accepted_output_root_after_service_restart` 仍另驗 sidecar 的輸出根目錄狀態讀回 |
| Tauri host 編譯與資產 proxy | `cargo test` 3 項通過；`segvision-asset://localhost/<token>` path token、已知 WebView CORS origin、output grant proxy 與 cursor command 編譯驗證 |
| 預設啟動改為 Native App | `segvision-gui` → `segvision.desktop:main` |

### 3.2 尚未完成的 Native App 門檻

這輪已修正舊的錯誤吞沒、50×40 固定 Canvas、直接 HTTP asset 無法帶授權 header、gold overlay 未投影、單層資料集掃描、fake backend 跨 crop 尺寸錯誤、Tauri asset token/CORS、output grant、切圖舊回應覆寫、nested image id 的持久化路徑問題、接受後舊草稿遮蔽完成狀態，以及選取輸出資料夾後未刷新工作狀態的問題。不過下列限制仍成立：

1. **Native App 開發路徑已接上官方 MobileSAM TinyViT CPU**：Tauri 以 `--prefer-real` 啟動 sidecar，runtime 先核對本機評估授權、provenance 與 checkpoint SHA-256，再建立官方 `SamPredictor`。目前核准範圍僅為本機 CPU 評估，`release_approved=false`；缺檔、hash／授權不符時會明確退回 fake backend 並回報 setup blocker，不得據此宣告 release approval。
2. **資料集掃描有意限制為直接檔案或一層子目錄。** 更深的樹狀資料集仍應選擇實際含影像的子資料夾，避免任意遞迴掃描。
3. **尚未用真實 Tauri 視窗跑完整 E2E。** 現有自動化是 Chromium + Vite + sidecar（`?e2e=1`），因此尚未覆蓋 Tauri picker、custom protocol 與不同 DPR 的整合。
4. **Canvas 已有 pan／zoom／DPR 導覽與座標單元測試**；真正 Tauri 視窗的不同 DPI 與大圖互動仍未完成端到端驗收。
5. **資料集已按 cursor 續載**：React 清單顯示已載入／總數，可逐頁載入；「下一張」會跨頁尋找未完成項目。搜尋或狀態篩選時可按「載入完整清單後套用篩選」，續載剩餘項目摘要後再篩選；分頁失敗會顯示清單錯誤並保留重試操作。選擇輸出資料夾及儲存 Accept／Needs Review 後會刷新已載入項目的狀態。一般瀏覽仍逐頁載入，避免一開始讀入整份清單。
6. **沒有離線安裝包 / 乾淨 VM 驗收。**
7. OpenSpec `tasks.md` 仍幾乎全是未勾選；parity 未過時就把預設切到 Native App，是依你後來的指示，與原規格「先對等再切預設」不一致。
8. NativeApp web-host 的 fake backend 與 opt-in MobileSAM local-evaluation 都已通過合成影像 ROI／候選／Accept 可見旅程，並在新 host PID 與重新開啟的 React UI 核對已接受狀態、PNG／sidecar 完全不變及原始 fixture hash；MobileSAM checkpoint 僅限 local evaluation，未獲 release approval。兩者都使用合成 picker 與 fixture，不代表真實業務影像品質、OS picker、Tauri 視窗或發布包通過。

結論：**Chromium 自動化標註流程現在可重現且可檢查；Native Tauri 視窗仍不是可宣告完成或可發布的穩定工具。**

---

## 4. 測試資料路徑

Open dataset 支援「資料夾裡直接有圖」或「下一層子資料夾有圖」；深層樹狀資料集仍請選實際含圖的子資料夾。

| 用途 | 路徑 |
| --- | --- |
| **建議先用**（3 張合成圖 + `gold/`） | `testdata/desktop-smoke` in this repository |
| 真實 MVTec can/bad（僅該層有 png） | `$env:SEGVISION_MVTEC2_ROOT\can\test_public\bad` |

MVTec 的 `bad` grant 僅包含 source images；其 sibling `test_public\ground_truth\bad` 不在 grant 範圍內，因此 `gold_mask_token` 會是 `null`。要驗證 MVTec gold overlay，請將 `test_public` 作為明確的 dataset grant，勿讓 sidecar 由 `bad` 自動讀取 grant 外路徑。

不要選：

- The MVTec AD 2 dataset root (image depth exceeds the current one-level scan limit)
- A parent directory that contains multiple unrelated datasets

---

## 5. 怎麼測（建議順序）

從 repository root 啟用 `.venv`（CPython 3.11）：

```powershell
$env:Path = (Join-Path (Get-Location) ".venv\Scripts") + ";" + $env:Path
```

### 5.1 協定與 sidecar（目前最可靠）

涵蓋 health、secret、version、開資料集、binary mask、IMAGE_OPEN→lock_roi、候選、refinement、edit、revision_conflict、Accept、Needs Review 的實際 review sidecar/draft 輸出及非訓練狀態、本機 process。

```powershell
python -m pytest tests/contract tests/integration/test_desktop_sidecar.py -q
```

預期：全綠。

### 5.2 React 元件

```powershell
Set-Location apps\desktop-ui
npm test
```

預期：座標 round-trip、資產與 Tauri-shaped 錯誤顯示、切圖／revision stale rejection、輸出 grant 與 App 元件測試通過。

### 5.3 自動化「視窗」E2E（Chromium，不是 Tauri）

```powershell
python -m pytest tests/desktop-e2e -q
```

會起 sidecar + Vite，用 Playwright 開資料集、選 output grant、點 ROI 兩個角、驗證 candidate overlay，並分別走 Accept 與 Needs Review。Accept 必須輸出 PNG+sidecar；Needs Review 必須輸出 `review/` metadata 與 hash 對應 draft，標記 `training_eligible=false`，且不得在輸出根目錄產生 accepted pair。測試會檢查受保護 source／gold／candidate PNG、160×120 的真實影像尺寸、畫布疊圖像素、sidecar authoritative ROI 與 candidate mask hash。這**不證明** Tauri 檔案選擇器與 `segvision-asset://` 的實際視窗整合。

### 5.4 NativeApp 公開 web-host E2E（opt-in）

先建置 React dist，並將 `NATIVEAPP_V2_ROOT` 設為 NativeApp v2 checkout，再以含 sidecar 依賴的 Python 環境執行。預設是 fake backend 的 host/UI 接線驗證：

```powershell
$env:NATIVEAPP_V2_ROOT = 'C:\work\nativeApp_v2'
.\.venv\Scripts\python.exe -m pytest tests\desktop-e2e\test_desktop_annotation_loop.py::test_nativeapp_public_same_origin_web_host_reaches_visible_segmentation_flow -q
```

要在同一條 React browser journey 上驗證真 MobileSAM CPU，需使用已核准的本機評估設定，並確保執行 Python 環境已安裝 `torch` 與 `mobile_sam`：

```powershell
$env:SEGVISION_TEST_PREFER_REAL = '1'
$env:SEGVISION_TEST_MOBILESAM_CONFIG = 'D:\models\segvision\local-evaluation.json'
python -m pytest tests\desktop-e2e\test_desktop_annotation_loop.py::test_nativeapp_public_same_origin_web_host_reaches_visible_segmentation_flow -q
```

測試會要求 health 回報 `backend.name=mobilesam`、`approval_scope=local_evaluation` 及 `release_approved=false`，再以合成影像執行 ROI／候選操作；模型設定、checkpoint、授權與 provenance 不會打包或下載。兩種模式都使用合成 `cimHost.chooseFile`，不會開啟作業系統 picker，也不證明真實業務影像品質、Tauri 視窗或發布包已通過。

### 5.5 Native App 手動 smoke

```powershell
npm --prefix apps\desktop-host run dev
```

若使用 NativeApp 的 `cim-light.exe` 殼，請改用：

```powershell
npm --prefix apps\desktop-host run dev:cim
```

此腳本會以 `--prefer-real` 啟動 sidecar，並等待 MobileSAM CPU 冷啟動完成後才開啟視窗；因此健康狀態中的 `backend.name` 應為 `mobilesam`，不應默默落回 fake。

開發機預設讀取 `models/local-evaluation.json`。健康狀態必須顯示 `MobileSAM CPU`，且 `approval_scope=local_evaluation`、`release_approved=false`；若顯示 fake backend，先檢查 runtime config 所指的 checkpoint、authorization 與 provenance 是否存在且 SHA-256 一致。模型冷啟動可能需要數秒，Tauri host 會等待最多 60 秒才判定 sidecar 不可用。

等視窗標題 **SegVision**。

1. 按 **Open dataset**
2. 選 repository 內的 `testdata/desktop-smoke`
3. 按 **Choose output folder**，選一個可寫入的空白資料夾
4. 左側應出現 `part_a.png` / `part_b.png` / `part_c.png`
5. 點一張圖，狀態應為 `IMAGE_OPEN`
6. 在畫布**影像本身**上點 ROI 左上角與右下角（這批圖很小，要點左上角那塊色塊）
7. 選候選後按 **Accept**；輸出資料夾應有 PNG + JSON pair

若點了 Open dataset 沒有檔案清單：先看畫面上的錯誤列；常見原因是選到超過一層的資料夾，或 host invoke 失敗。必要時再看 `tauri-dev.err.log`。

### 5.6 既有 v1 Python / PySide 回歸（不應被 Native App 改壞）

```powershell
python -m pytest tests/unit/test_import_contract.py tests/gui tests/unit/test_core_smoke.py -q
```

---

## 6. 快捷鍵（契約；UI 已接但依賴 sidecar 成功）

| 鍵 | 行為 |
| --- | --- |
| `1` `2` `3` | 選候選 |
| 右側「取消選擇」 | 清除目前選取但保留全部候選；可再選 1／2／3，取消後不可 Accept |
| 左鍵 / 右鍵 | 正點 / 負點 |
| `B` | 筆刷 |
| `[` `]` | shrink / grow |
| `F` | fill holes |
| `X` | Expand ROI |
| `Z` | Undo |
| `Space` | Accept |
| `N` | 下一張（僅 Accept 或 Needs Review 成功後） |

Erase 有按鈕，沒有快捷鍵。

---

## 7. 相關文件

| 文件 | 用途 |
| --- | --- |
| `PRD.md` | 凍結產品決策 |
| `openspec/changes/build-segvision-v1/` | v1 核心契約 |
| `openspec/changes/adopt-react-tauri-desktop/` | Native App 規格 |
| `docs/react-tauri-architecture-recommendation.md` | 架構建議原文 |
| `apps/README.md` | 啟動指令短表 |

---

## 8. 下一步（若要把「能給人測」做完）

1. 用真實 Tauri 視窗跑一條 Open dataset → output grant → ROI → Accept E2E，覆蓋 picker、`segvision-asset://`、CORS 與不同 DPR  
2. 補齊 sidecar crash/restart 事件與恢復流程的桌面測試
3. 依實際資料集需求決定是否擴大目前的一層掃描限制
4. 通過後再談核准 MobileSAM、離線安裝包與 parity 勾選
