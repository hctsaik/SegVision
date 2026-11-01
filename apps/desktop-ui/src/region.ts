export type ComputePhase = "idle" | "locking-sam" | "matching-dino" | "fitting-dino";

export function computePhaseFromJob(
  wait: ComputePhase,
  job?: { kind?: string | null; status?: string | null } | null,
): ComputePhase {
  if (job?.status === "running") {
    if (job.kind === "propose" || job.kind === "refine" || job.kind === "expand") return "locking-sam";
  }
  return wait;
}

export function candidateSourceLabel(source: string): string {
  switch (source) {
    case "sam_box":
      return "來自黃框";
    case "sam_safe_grid":
      return "框內網格";
    case "sam_cv":
      return "來自黃框";
    case "cv_direct":
      return "來自黃框";
    case "manual_empty":
      return "空遮罩";
    case "manual_edit":
      return "已手改";
    default:
      return source.replaceAll("_", " ");
  }
}

export function workflowLabel(state: string): string {
  switch (state) {
    case "NONE":
      return "尚無影像";
    case "IMAGE_OPEN":
      return "請畫框";
    case "ROI_LOCKED":
    case "PROPOSING":
    case "REFINE_PENDING":
      return "正在找遮罩…";
    case "PROPOSAL_READY":
    case "REFINED_READY":
    case "LOCAL_EDITING":
      return "請選遮罩";
    case "ACCEPTED":
      return "已儲存";
    case "NEEDS_REVIEW":
      return "待覆核";
    case "MANUAL_EMPTY":
      return "空遮罩";
    case "SAVE_FAILED":
      return "儲存失敗";
    default:
      return state.replaceAll("_", " ");
  }
}

export function backendLabel(name: string | null | undefined): string {
  switch (name) {
    case "mobilesam":
      return "MobileSAM CPU";
    case "fake":
      return "假後端（非 MobileSAM）";
    default:
      return name ? name : "後端未回報";
  }
}

export function engineLabel(engine: string): string {
  switch (engine) {
    case "ready":
      return "就緒";
    case "engine_unavailable":
      return "引擎不可用";
    case "recovering":
      return "恢復中";
    default:
      return engine;
  }
}

export function jobLabel(kind: string | null, status: string | null): string {
  const kinds: Record<string, string> = {
    propose: "計算遮罩",
    refine: "微調",
    expand: "擴大框",
  };
  const statuses: Record<string, string> = {
    running: "進行中",
    failed: "失敗",
    completed: "完成",
  };
  const k = (kind && kinds[kind]) || kind || "";
  const s = (status && statuses[status]) || status || "";
  return `${k} ${s}`.trim();
}

export function regionStatus(input: {
  hasImage: boolean;
  workflow: string;
  dinoOn: boolean;
  computePhase: ComputePhase;
  hasRoi: boolean;
  candidateCount: number;
  prototype?: {
    teacher?: boolean;
    matched?: boolean;
    abstained?: boolean;
    note?: string | null;
  } | null;
}): string {
  if (input.computePhase === "matching-dino") {
    return "正在這張圖上尋找相似區域…";
  }
  if (input.computePhase === "fitting-dino") {
    return "正在記住這個遮罩，下一張會依外觀尋找…";
  }
  if (input.computePhase === "locking-sam") {
    return "正在黃框內尋找最多 3 個遮罩…";
  }
  if (input.prototype?.matched && input.candidateCount > 0) {
    return "已找到相似區域。粉紅＝切割結果。黃框＝搜尋範圍。按 1–3 比較。";
  }
  if (input.prototype?.matched && input.hasRoi) {
    return "已找到相似區域。遮罩只在這個黃框內計算。";
  }
  if (input.candidateCount > 0) {
    return "粉紅＝切割結果 · 黃框＝搜尋範圍。按 1–3 比較。空白鍵儲存。";
  }
  if (input.workflow === "IMAGE_OPEN" && input.prototype?.abstained) {
    return "沒找到相似區域。請在缺陷周圍點兩個角建立黃框。";
  }
  if (!input.hasImage) {
    return "請開啟圖片資料夾，然後在缺陷周圍點兩個角建立黃框。";
  }
  if (input.workflow === "IMAGE_OPEN" || !input.hasRoi) {
    return "在缺陷周圍點兩個角建立黃框。遮罩只會在這個框裡計算。";
  }
  if (input.workflow === "PROPOSING" || input.workflow === "REFINE_PENDING") {
    return "正在黃框內尋找最多 3 個遮罩…";
  }
  if (input.prototype?.teacher) {
    return "已記住這個遮罩。下一張會依外觀尋找。";
  }
  return "黃框是搜尋範圍。粉紅像素才是切割結果。";
}

export function regionBadge(input: {
  computePhase: ComputePhase;
  dinoMatched: boolean;
  drafting: boolean;
}): string {
  if (input.computePhase === "matching-dino") return "搜尋中…";
  if (input.computePhase === "locking-sam" || input.computePhase === "fitting-dino") {
    return "正在找遮罩…";
  }
  if (input.drafting) return "搜尋框";
  if (input.dinoMatched) return "黃框＝搜尋範圍，不是切割結果";
  return "黃框＝搜尋範圍，不是切割結果";
}
