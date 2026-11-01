# LabelMe 匯出

SegVision 的正式存檔仍以全圖二值遮罩 PNG 與 JSON sidecar 為來源，這樣可保留每一個版本與 provenance。需要交給 LabelMe 時，可將已接受的輸出轉成標準 polygon JSON：

```powershell
.venv\Scripts\python.exe -m segvision.cli export-labelme `
  <accepted-output> <labelme-output> `
  --image-root <dataset-root>
```

若資料集沒有提供 `manifest.json` 的 `class_id`，SegVision 會將存檔與
LabelMe 匯出的預設類別固定為 `Defect`。若 manifest 明確指定類別，則保留
該類別；匯出時也可使用 `--label` 覆寫，之後再於 LabelMe 內細分名稱。

每個輸出 JSON 都包含 `imagePath`、`imageHeight`、`imageWidth` 與 `shapes`，不嵌入影像 bytes；`--image-root` 若能找到對應原圖，會寫入相對路徑。未提供時則以 sidecar 的 `image_id` 推導 `<image_id>.png`。匯出前會只在匯出副本上補合一像素小缺口、填滿封閉空洞，並以 0.5px 容差移除鋸齒節點，讓每個 shape 成為封閉多邊形；原始二值遮罩仍可保留給 SegVision 重新載入。
