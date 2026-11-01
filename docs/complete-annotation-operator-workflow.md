# SegVision 標註操作與恢復流程

本文件是 `complete-annotation-operator-workflow` OpenSpec 的操作摘要；完整需求、情境、任務與驗收閘門位於
`openspec/changes/complete-annotation-operator-workflow/`。

## 日常標註

1. 在 Native App / Tauri 殼中開啟資料夾與輸出資料夾。
2. 以兩次點擊建立 SAM 框選：第一次是左上角、第二次是右下角。完成後再點擊時，系統會移動距離較近的角點；不會呼叫 `sessions.lock_roi`。
3. 以「補選」加入前景點，以「排除」加入背景點。點選既有點後可移動、改前景/背景或刪除；服務端會依穩定點 ID 重新播放 decoder。
4. 「畫筆」與「擦除」只作用於目前編輯範圍，可選 1 px、3 px、5 px。邊界使用半開區間 `[x0,y0,x1,y1)`，因此筆刷半徑也不會越界。
5. 可用 Undo / Redo 與操作歷史回到任何已完成 checkpoint。新的修改會清除 redo 分支；Undo/Redo 不會重新 encode 或 decode。
6. 確認的區塊可「鎖定區塊」；已鎖定區塊會出現在 Dropbox 選單，可單獨解鎖或用 Merge 合併到目前遮罩。

## 草稿、崩潰與切換

- 每次權威修改完成後，sidecar 會把完整影像遮罩寫到獨立 `drafts/` 命名空間。遮罩與 JSON 使用暫存檔、fsync、JSON sidecar 最後發佈；Accepted/Needs Review 不會被草稿清理碰觸。
- Draft 狀態會顯示 `saved`、`flushing`、`failed`、`resumable`。切換圖片、重開資料集、重啟引擎或更新前，若草稿為 dirty，必須選「先儲存草稿」、「捨棄」或「取消」。
- sidecar 重啟會換用新的隨機 port/launch secret。只接受通過 source hash、mask hash、schema 與 protocol 驗證的草稿；畫布像素不作為恢復輸入。

## QA 與 LabelMe

- QA 在本機、以完整影像遮罩執行，檢查空遮罩、近乎全圖、影像/裁切邊界、微小元件、孔洞、單像素橋接、元件數與多邊形面積差。空遮罩會阻擋 Accept；提示性問題須明確確認。
- LabelMe 匯出前先產生預覽；輸出只使用 polygon、封閉點列與 `Defect` 預設標籤。匯入會嚴格檢查尺寸、imagePath、label、點數與 shape type，成功後建立可編輯草稿，不覆寫 Accepted。
- LabelMe 預覽/匯入/匯出與草稿均透過 opaque grant；控制平面不傳影像、遮罩或原始檔案路徑。

## 版本與安全

目前 protocol 是精確比對的 `1.1`。About/health 會顯示 App、sidecar、protocol 與模型身份；自動網路更新、telemetry、crash upload、remote inference 預設關閉。離線更新在缺少可歸屬簽章權限或支援的 clean Windows x64 參考機前，維持 fail-closed，不宣稱已驗證。

## 驗證命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix apps/desktop-ui test -- --run
npm.cmd --prefix apps/desktop-ui run build
npm.cmd --prefix apps/desktop-ui run e2e -- e2e/sam-point-014.spec.ts --workers=1
openspec validate complete-annotation-operator-workflow --strict --no-interactive
```
