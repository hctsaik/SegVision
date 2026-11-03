import { PROTOCOL_VERSION } from "./protocol";

export type Snapshot = {
  protocol_session_id: string;
  workflow_state: string;
  revision: number;
  image_id?: string;
  class_id?: string | null;
  user_roi_full?: number[] | null;
  crop_rect_full?: number[] | null;
  selected_candidate_id?: string | null;
  prompt_points?: Array<{ point_id: string; x: number; y: number; label: 0 | 1 }>;
  frozen_regions?: Array<{
    region_id: string;
    label?: 0 | 1;
    /** Number of pixels in the frozen crop mask (sidecar calls this `area`). */
    area?: number;
    /** Kept for snapshots produced by older sidecars. */
    pixel_count?: number;
    pass_index?: number;
    mask_sha256?: string;
  }>;
  pass_index?: number;
  candidates: Array<{
    candidate_id: string;
    source: string;
    capabilities: { can_refine: boolean; can_local_edit: boolean; can_commit: boolean };
    mask_token: string;
    prompt_points?: Array<{ point_id?: string; x: number; y: number; label: 0 | 1 }>;
  }>;
  warnings: Array<{ code: string; message: string }>;
  acknowledged_warnings?: string[];
  job: { job_id: string | null; kind: string | null; status: string | null };
  assets: {
    source_image: string | null;
    thumbnail: string | null;
    mask: string | null;
    locked_foreground?: string | null;
    locked_background?: string | null;
  };
  first_roi_locked_at?: number | null;
  persist?: { kind?: string; training_eligible?: boolean };
  controls: Record<string, boolean>;
  last_error?: string | null;
  prototype?: {
    teacher?: boolean;
    matched?: boolean;
    abstained?: boolean;
    note?: string | null;
    roi?: number[] | null;
  } | null;
  history?: {
    can_undo: boolean;
    can_redo: boolean;
    past_depth: number;
    future_depth: number;
    current_revision?: number;
    operations: Array<{
      sequence?: number;
      kind?: string;
      revision?: number;
      status?: "current" | "undone" | "unavailable";
      parameters?: Record<string, unknown>;
    }>;
  };
  draft?: { state?: string; dirty?: boolean; error?: string | null };
  qa?: { schema_version?: number; issues?: Array<{ code: string; severity: string; message: string; bbox?: number[] }>; blocking?: boolean };
};

export type LoadedAsset = {
  url: string;
  revoke: boolean;
};

export type DatasetItemSummary = {
  item_id: string;
  image_id: string;
  class_id: string;
  display_name: string;
  status?: "unstarted" | "draft" | "accepted" | "needs-review" | "save-failed" | "conflict-or-corrupt";
  thumbnail_token?: string | null;
  gold_mask_token?: string | null;
};

export type DatasetWorkItemStatus = {
  item_id: string;
  status: NonNullable<DatasetItemSummary["status"]>;
};

export type DatasetWorkStatus = {
  dataset_id: string;
  items: DatasetWorkItemStatus[];
  counts: Record<string, number>;
  total: number;
};

export type FolderGrantKind = "dataset" | "output";

export type HostClient = {
  engineHealth(): Promise<{
    ready: boolean;
    setup_state: string;
    backend?: { name?: string; approved?: boolean };
  }>;
  engineRestart?(): Promise<{ state: string; restarted: boolean }>;
  pickerOpenFolder(kind: FolderGrantKind): Promise<{ grant_id: string; display_name: string }>;
  datasetsOpen(grantId: string): Promise<{ dataset_id: string; class_id: string; item_count: number }>;
  datasetsListItems(datasetId: string, cursor?: string | null): Promise<{
    items: DatasetItemSummary[];
    next_cursor: string | null;
  }>;
  datasetsWorkStatus?(datasetId: string): Promise<DatasetWorkStatus>;
  sessionsCreate(datasetId: string, itemId: string, prototypeMatch?: boolean): Promise<Snapshot>;
  sessionsGet(sessionId: string): Promise<Snapshot>;
  sessionsLockRoi(
    sessionId: string,
    base: number,
    classId: string,
    roi: number[],
    outputGrantId?: string | null,
  ): Promise<Snapshot>;
  sessionsPropose(sessionId: string, base: number): Promise<Snapshot>;
  sessionsSelect(sessionId: string, base: number, candidateId: string): Promise<Snapshot>;
  sessionsClearSelection(sessionId: string, base: number): Promise<Snapshot>;
  sessionsRefine(sessionId: string, base: number, x: number, y: number, label: number): Promise<Snapshot>;
  sessionsDeletePrompt(sessionId: string, base: number, promptId: string): Promise<Snapshot>;
  sessionsLockRegion(
    sessionId: string,
    base: number,
    x: number,
    y: number,
    guard?: boolean,
  ): Promise<Snapshot>;
  sessionsUnlockRegion(sessionId: string, base: number, regionId?: string): Promise<Snapshot>;
  sessionsStartNextRegion(sessionId: string, base: number): Promise<Snapshot>;
  sessionsEdit(
    sessionId: string,
    base: number,
    operation: string,
    points?: number[][],
    radius?: number,
    clipRect?: number[] | null,
  ): Promise<Snapshot>;
  sessionsUndo(sessionId: string, base: number): Promise<Snapshot>;
  sessionsRedo?(sessionId: string, base: number): Promise<Snapshot>;
  sessionsUpdatePrompt?(sessionId: string, base: number, promptId: string, x?: number, y?: number, label?: number): Promise<Snapshot>;
  sessionsQa?(sessionId: string): Promise<{ schema_version: number; issues: Array<{ code: string; severity: string; message: string; bbox?: number[] }>; blocking: boolean }>;
  labelmePreview?(sessionId: string): Promise<Record<string, unknown>>;
  labelmeExport?(sessionId: string, outputGrantId: string, acknowledgeCleanup?: boolean): Promise<Record<string, unknown>>;
  labelmeImport?(sessionId: string, document: Record<string, unknown>, labelMapping?: Record<string, string>, decision?: "replace" | "cancel"): Promise<Record<string, unknown>>;
  draftsInspect?(datasetId: string, itemId: string): Promise<Record<string, unknown>>;
  draftsFlush?(sessionId: string, base: number): Promise<Snapshot>;
  draftsLoad?(datasetId: string, itemId: string, draftId?: string, sessionId?: string): Promise<Record<string, unknown>>;
  draftsDiscard?(datasetId: string, itemId: string, draftId?: string): Promise<unknown>;
  labelsList?(datasetId?: string): Promise<Record<string, unknown>>;
  labelsReclassify?(sessionId: string, base: number, classId: string): Promise<Snapshot>;
  updatesInfo?(): Promise<Record<string, unknown>>;
  updatesVerify?(packagePath: string): Promise<Record<string, unknown>>;
  sessionsManualEmpty(sessionId: string, base: number, roi?: number[] | null): Promise<Snapshot>;
  sessionsExpandRoi(sessionId: string, base: number): Promise<Snapshot>;
  sessionsAccept(
    sessionId: string,
    base: number,
    acks: string[],
    outputGrantId: string,
    fitPrototype?: boolean,
  ): Promise<Snapshot>;
  sessionsNeedsReview(
    sessionId: string,
    base: number,
    reason: string,
    outputGrantId: string,
  ): Promise<Snapshot>;
  sessionsClose(sessionId: string, base: number): Promise<Snapshot>;
  jobsCancel(sessionId: string, jobId: string): Promise<unknown>;
  loadAsset(token: string): Promise<LoadedAsset>;
};

function rid(): string {
  return crypto.randomUUID();
}

function toCamelArgs(args: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(args)) {
    const camel = key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
    out[camel] = value;
  }
  return out;
}

async function tauriInvoke<T>(cmd: string, args: Record<string, unknown>): Promise<T> {
  const w = window as unknown as {
    __TAURI_INTERNALS__?: { invoke: (c: string, a?: unknown) => Promise<T> };
    __TAURI__?: {
      core?: { invoke: (c: string, a?: unknown) => Promise<T> };
      invoke?: (c: string, a?: unknown) => Promise<T>;
    };
  };
  const invoke =
    w.__TAURI_INTERNALS__?.invoke || w.__TAURI__?.core?.invoke || w.__TAURI__?.invoke;
  if (!invoke) {
    throw new Error("Tauri host is unavailable");
  }
  return invoke(cmd, toCamelArgs(args));
}

export function encodeHostPathHeader(path: string): string {
  if (!path) return "";
  for (let i = 0; i < path.length; i += 1) {
    if (path.charCodeAt(i) > 255) return encodeURIComponent(path);
  }
  return path;
}

async function sidecarJson<T>(
  url: string,
  init: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (error) {
    const detail = error instanceof Error && error.message ? error.message : "network error";
    throw new Error(
      `engine_unreachable: the annotation sidecar did not respond (${detail}). ` +
        "If this happened on Accept, pick a folder again; Unicode folder names are now encoded.",
    );
  }
  let json: { code?: string; message?: string } | T | null = null;
  try {
    json = (await res.json()) as T;
  } catch {
    json = null;
  }
  if (!res.ok) {
    const body = json as { code?: string; message?: string } | null;
    const code = body?.code || `http_${res.status}`;
    const message = body?.message || res.statusText || "request failed";
    throw new Error(`${code}: ${message}`);
  }
  if (!json) throw new Error("engine_unreachable: sidecar returned a non-JSON response");
  return json as T;
}

export function createE2EHost(baseUrl: string, secret: string, datasetPath: string, outputPath: string): HostClient {
  const headers = {
    "X-SegVision-Launch-Secret": secret,
    "X-SegVision-Protocol-Version": PROTOCOL_VERSION,
    "X-SegVision-Host-Proxy": "1",
    "X-SegVision-Resolved-Path": encodeHostPathHeader(datasetPath),
    "X-SegVision-Output-Path": encodeHostPathHeader(outputPath),
    "Content-Type": "application/json",
  };
  async function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
    return sidecarJson<T>(`${baseUrl}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify({ protocol_version: PROTOCOL_VERSION, request_id: rid(), ...body }),
    });
  }
  async function get<T>(path: string): Promise<T> {
    return sidecarJson<T>(`${baseUrl}${path}`, { headers });
  }
  async function loadAsset(token: string): Promise<LoadedAsset> {
    const res = await fetch(`${baseUrl}/v1/assets/${encodeURIComponent(token)}`, { headers });
    if (!res.ok) {
      let code = "asset_load_failed";
      try {
        const body = (await res.json()) as { code?: string };
        code = body.code || code;
      } catch {
        // A binary asset endpoint is not required to return JSON on every error.
      }
      throw new Error(code);
    }
    return { url: URL.createObjectURL(await res.blob()), revoke: true };
  }
  return {
    engineHealth: () => get("/v1/health"),
    engineRestart: () => post("/v1/engine/restart", {}),
    pickerOpenFolder: async (kind) => ({ grant_id: `e2e-${kind}`, display_name: `e2e-${kind}` }),
    datasetsOpen: (grantId) => post("/v1/datasets/open", { grant_id: grantId, base_revision: 0 }),
    datasetsListItems: (datasetId, cursor) =>
      get(`/v1/datasets/${datasetId}/items${cursor == null ? "" : `?cursor=${encodeURIComponent(cursor)}`}`),
    datasetsWorkStatus: (datasetId) => get(`/v1/datasets/${datasetId}/work-status`),
    sessionsCreate: (datasetId, itemId, prototypeMatch = false) =>
      post("/v1/sessions", {
        dataset_id: datasetId,
        item_id: itemId,
        base_revision: 0,
        prototype_match: prototypeMatch,
      }),
    sessionsGet: (sessionId) => get(`/v1/sessions/${sessionId}`),
    sessionsLockRoi: (sessionId, base, classId, roi, _outputGrantId) =>
      post(`/v1/sessions/${sessionId}/lock-roi`, { base_revision: base, class_id: classId, roi_xyxy: roi }),
    sessionsPropose: (sessionId, base) =>
      post(`/v1/sessions/${sessionId}/proposals`, { base_revision: base }),
    sessionsSelect: (sessionId, base, candidateId) =>
      post(`/v1/sessions/${sessionId}/select`, { base_revision: base, candidate_id: candidateId }),
    sessionsClearSelection: (sessionId, base) =>
      post(`/v1/sessions/${sessionId}/select`, { base_revision: base, candidate_id: null }),
    sessionsRefine: (sessionId, base, x, y, label) =>
      post(`/v1/sessions/${sessionId}/refinements`, { base_revision: base, x, y, label }),
    sessionsDeletePrompt: (sessionId, base, promptId) =>
      post(`/v1/sessions/${sessionId}/prompts/delete`, {
        base_revision: base,
        prompt_id: promptId,
      }),
    sessionsLockRegion: (sessionId, base, x, y, guard = true) =>
      post(`/v1/sessions/${sessionId}/regions/lock`, {
        base_revision: base,
        x,
        y,
        guard,
      }),
    sessionsUnlockRegion: (sessionId, base, regionId) =>
      post(`/v1/sessions/${sessionId}/regions/unlock`, {
        base_revision: base,
        region_id: regionId ?? null,
      }),
    sessionsStartNextRegion: (sessionId, base) =>
      post(`/v1/sessions/${sessionId}/regions/next`, { base_revision: base }),
    sessionsEdit: (sessionId, base, operation, points = [], radius = 0, clipRect = null) =>
      post(`/v1/sessions/${sessionId}/edits`, {
        base_revision: base,
        operation,
        points,
        radius,
        clip_rect: clipRect,
      }),
    sessionsUndo: (sessionId, base) => post(`/v1/sessions/${sessionId}/undo`, { base_revision: base }),
    sessionsRedo: (sessionId, base) => post(`/v1/sessions/${sessionId}/redo`, { base_revision: base }),
    sessionsUpdatePrompt: (sessionId, base, promptId, x, y, label) =>
      post(`/v1/sessions/${sessionId}/prompts/update`, {
        base_revision: base,
        prompt_id: promptId,
        ...(x === undefined || y === undefined ? {} : { x, y }),
        ...(label === undefined ? {} : { label }),
      }),
    sessionsQa: (sessionId) => post(`/v1/sessions/${sessionId}/qa`, {}),
    labelmePreview: (sessionId) => post("/v1/labelme/preview", { session_id: sessionId }),
    labelmeExport: (sessionId, _outputGrantId, acknowledgeCleanup = false) => post("/v1/labelme/export", { session_id: sessionId, acknowledge_cleanup: acknowledgeCleanup }),
    labelmeImport: (sessionId, document, labelMapping, decision) =>
      post("/v1/labelme/import", {
        session_id: sessionId,
        document,
        label_mapping: labelMapping,
        decision,
      }),
    draftsFlush: (sessionId, base) => post("/v1/drafts/flush", { session_id: sessionId, base_revision: base }),
    draftsDiscard: (datasetId, itemId, draftId) => post("/v1/drafts/discard", { dataset_id: datasetId, item_id: itemId, draft_id: draftId }),
    sessionsManualEmpty: (sessionId, base, roi = null) =>
      post(`/v1/sessions/${sessionId}/manual-empty`, {
        base_revision: base,
        roi_xyxy: roi,
      }),
    sessionsExpandRoi: (sessionId, base) =>
      post(`/v1/sessions/${sessionId}/expand-roi`, { base_revision: base }),
    sessionsAccept: (sessionId, base, acks, _outputGrantId, fitPrototype = false) =>
      post(`/v1/sessions/${sessionId}/accept`, {
        base_revision: base,
        acknowledge_warnings: acks,
        fit_prototype: fitPrototype,
        output_root: outputPath || undefined,
      }),
    sessionsNeedsReview: (sessionId, base, reason, _outputGrantId) =>
      post(`/v1/sessions/${sessionId}/needs-review`, {
        base_revision: base,
        reason,
        output_root: outputPath || undefined,
      }),
    sessionsClose: (sessionId, base) => post(`/v1/sessions/${sessionId}/close`, { base_revision: base }),
    jobsCancel: (sessionId, jobId) =>
      post(`/v1/jobs/${jobId}/cancel`, { session_id: sessionId, job_id: jobId }),
    loadAsset,
  };
}

export function createTauriHost(): HostClient {
  return {
    engineHealth: () => tauriInvoke("engine_health", {}),
    engineRestart: () => tauriInvoke("engine_restart", {}),
    pickerOpenFolder: (kind) => tauriInvoke("picker_open_folder", { kind }),
    datasetsOpen: (grantId) => tauriInvoke("datasets_open", { grant_id: grantId }),
    datasetsListItems: (datasetId, cursor) =>
      tauriInvoke("datasets_list_items", { dataset_id: datasetId, cursor: cursor ?? null }),
    datasetsWorkStatus: (datasetId) => tauriInvoke("datasets_work_status", { dataset_id: datasetId }),
    sessionsCreate: (datasetId, itemId, prototypeMatch = false) =>
      tauriInvoke("sessions_create", {
        dataset_id: datasetId,
        item_id: itemId,
        prototype_match: prototypeMatch,
      }),
    sessionsGet: (sessionId) => tauriInvoke("sessions_get", { session_id: sessionId }),
    sessionsLockRoi: (sessionId, base, classId, roi, outputGrantId) =>
      tauriInvoke("sessions_lock_roi", {
        session_id: sessionId,
        base_revision: base,
        class_id: classId,
        roi_xyxy: roi,
        output_grant_id: outputGrantId ?? null,
      }),
    sessionsPropose: (sessionId, base) =>
      tauriInvoke("sessions_propose", { session_id: sessionId, base_revision: base }),
    sessionsSelect: (sessionId, base, candidateId) =>
      tauriInvoke("sessions_select", { session_id: sessionId, base_revision: base, candidate_id: candidateId }),
    sessionsClearSelection: (sessionId, base) =>
      tauriInvoke("sessions_select", { session_id: sessionId, base_revision: base, candidate_id: null }),
    sessionsRefine: (sessionId, base, x, y, label) =>
      tauriInvoke("sessions_refine", { session_id: sessionId, base_revision: base, x, y, label }),
    sessionsDeletePrompt: (sessionId, base, promptId) =>
      tauriInvoke("sessions_delete_prompt", {
        session_id: sessionId,
        base_revision: base,
        prompt_id: promptId,
      }),
    sessionsLockRegion: (sessionId, base, x, y, guard = true) =>
      tauriInvoke("sessions_lock_region", {
        session_id: sessionId,
        base_revision: base,
        x,
        y,
        guard,
      }),
    sessionsUnlockRegion: (sessionId, base, regionId) =>
      tauriInvoke("sessions_unlock_region", {
        session_id: sessionId,
        base_revision: base,
        region_id: regionId ?? null,
      }),
    sessionsStartNextRegion: (sessionId, base) =>
      tauriInvoke("sessions_start_next_region", {
        session_id: sessionId,
        base_revision: base,
      }),
    sessionsEdit: (sessionId, base, operation, points = [], radius = 0, clipRect = null) =>
      tauriInvoke("sessions_edit", {
        session_id: sessionId,
        base_revision: base,
        operation,
        points,
        radius,
        clip_rect: clipRect,
      }),
    sessionsUndo: (sessionId, base) => tauriInvoke("sessions_undo", { session_id: sessionId, base_revision: base }),
    sessionsRedo: (sessionId, base) => tauriInvoke("sessions_redo", { session_id: sessionId, base_revision: base }),
    sessionsUpdatePrompt: (sessionId, base, promptId, x, y, label) =>
      tauriInvoke("sessions_update_prompt", {
        session_id: sessionId,
        base_revision: base,
        prompt_id: promptId,
        x: x ?? null,
        y: y ?? null,
        label: label ?? null,
      }),
    sessionsQa: (sessionId) => tauriInvoke("sessions_qa", { session_id: sessionId }),
    labelmePreview: (sessionId) => tauriInvoke("labelme_preview", { session_id: sessionId }),
    labelmeExport: (sessionId, outputGrantId, acknowledgeCleanup = false) =>
      tauriInvoke("labelme_export", { session_id: sessionId, output_grant_id: outputGrantId, acknowledge_cleanup: acknowledgeCleanup }),
    labelmeImport: (sessionId, document, labelMapping, decision) =>
      tauriInvoke("labelme_import", { session_id: sessionId, document, label_mapping: labelMapping ?? null, decision: decision ?? null }),
    draftsInspect: (datasetId, itemId) =>
      tauriInvoke("drafts_inspect", { dataset_id: datasetId, item_id: itemId }),
    draftsFlush: (sessionId, base) =>
      tauriInvoke("drafts_flush", { session_id: sessionId, base_revision: base }),
    draftsLoad: (datasetId, itemId, draftId, sessionId) =>
      tauriInvoke("drafts_load", {
        dataset_id: datasetId,
        item_id: itemId,
        draft_id: draftId ?? null,
        session_id: sessionId ?? null,
      }),
    draftsDiscard: (datasetId, itemId, draftId) =>
      tauriInvoke("drafts_discard", { dataset_id: datasetId, item_id: itemId, draft_id: draftId ?? null }),
    labelsList: (datasetId) => tauriInvoke("labels_list", { dataset_id: datasetId ?? null }),
    labelsReclassify: (sessionId, base, classId) =>
      tauriInvoke("labels_reclassify", { session_id: sessionId, base_revision: base, class_id: classId }),
    updatesInfo: () => tauriInvoke("updates_info", {}),
    updatesVerify: (packagePath) => tauriInvoke("updates_verify", { package_path: packagePath }),
    sessionsManualEmpty: (sessionId, base, roi = null) =>
      tauriInvoke("sessions_begin_manual_empty", {
        session_id: sessionId,
        base_revision: base,
        roi_xyxy: roi,
      }),
    sessionsExpandRoi: (sessionId, base) =>
      tauriInvoke("sessions_expand_roi", { session_id: sessionId, base_revision: base }),
    sessionsAccept: (sessionId, base, acks, outputGrantId, fitPrototype = false) =>
      tauriInvoke("sessions_accept", {
        session_id: sessionId,
        base_revision: base,
        acknowledge_warnings: acks,
        output_grant_id: outputGrantId,
        fit_prototype: fitPrototype,
      }),
    sessionsNeedsReview: (sessionId, base, reason, outputGrantId) =>
      tauriInvoke("sessions_needs_review", {
        session_id: sessionId,
        base_revision: base,
        reason,
        output_grant_id: outputGrantId,
      }),
    sessionsClose: (sessionId, base) => tauriInvoke("sessions_close", { session_id: sessionId, base_revision: base }),
    jobsCancel: (sessionId, jobId) => tauriInvoke("jobs_cancel", { session_id: sessionId, job_id: jobId }),
    loadAsset: async (token) => {
      const payload = await tauriInvoke<{ mime?: string; data_url?: string; dataUrl?: string }>(
        "load_asset",
        { token },
      );
      const dataUrl = payload?.data_url || payload?.dataUrl;
      if (!dataUrl) {
        throw new Error("asset_load_failed");
      }
      return { url: dataUrl, revoke: false };
    },
  };
}

type CimHostBridge = {
  chooseFile?: (options: { properties?: string[] }) => Promise<{
    canceled?: boolean;
    paths?: string[];
  }>;
};

function tauriInvokeRaw(cmd: string, args?: Record<string, unknown>): Promise<unknown> {
  const w = window as unknown as {
    __TAURI_INTERNALS__?: { invoke: (c: string, a?: unknown) => Promise<unknown> };
    __TAURI__?: { core?: { invoke: (c: string, a?: unknown) => Promise<unknown> } };
  };
  const invoke = w.__TAURI_INTERNALS__?.invoke || w.__TAURI__?.core?.invoke;
  if (!invoke) throw new Error("Tauri host is unavailable");
  return invoke(cmd, args);
}

function folderDisplayName(path: string): string {
  const slash = Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"));
  return slash >= 0 ? path.slice(slash + 1) : path;
}

export async function pickDirectoryViaCimShell(title = "開啟資料夾"): Promise<string> {
  const errors: string[] = [];
  try {
    const picked = await tauriInvokeRaw("plugin:dialog|open", {
      directory: true,
      multiple: false,
      title,
    });
    const path = Array.isArray(picked) ? picked[0] : picked;
    if (typeof path === "string" && path) return path;
  } catch (error) {
    errors.push(error instanceof Error ? error.message : String(error));
  }
  const cim = (window as unknown as { cimHost?: CimHostBridge }).cimHost;
  if (cim?.chooseFile) {
    try {
      const result = await cim.chooseFile({ properties: ["openDirectory"] });
      if (!result.canceled && result.paths?.[0]) return result.paths[0];
      throw JSON.stringify({ code: "grant_invalid", message: "folder access was cancelled" });
    } catch (error) {
      errors.push(error instanceof Error ? error.message : String(error));
    }
  }
  throw JSON.stringify({
    code: "grant_invalid",
    message: errors[0] || "folder picker is unavailable",
  });
}

export function createCimShellHost(baseUrl: string, secret: string): HostClient {
  const paths = { dataset: "", output: "" };
  const live = () => createE2EHost(baseUrl, secret, paths.dataset, paths.output);
  return {
    engineHealth: () => live().engineHealth(),
    engineRestart: () => live().engineRestart!(),
    pickerOpenFolder: async (kind) => {
      const path = await pickDirectoryViaCimShell(kind === "output" ? "選擇儲存資料夾" : "開啟圖片資料夾");
      if (kind === "output") paths.output = path;
      else paths.dataset = path;
      return { grant_id: kind, display_name: folderDisplayName(path) };
    },
    datasetsOpen: (grantId) => live().datasetsOpen(grantId),
    datasetsListItems: (datasetId, cursor) => live().datasetsListItems(datasetId, cursor),
    datasetsWorkStatus: (datasetId) => live().datasetsWorkStatus!(datasetId),
    sessionsCreate: (datasetId, itemId, prototypeMatch) =>
      live().sessionsCreate(datasetId, itemId, prototypeMatch),
    sessionsGet: (sessionId) => live().sessionsGet(sessionId),
    sessionsLockRoi: (sessionId, base, classId, roi, outputGrantId) =>
      live().sessionsLockRoi(sessionId, base, classId, roi, outputGrantId),
    sessionsPropose: (sessionId, base) => live().sessionsPropose(sessionId, base),
    sessionsSelect: (sessionId, base, candidateId) => live().sessionsSelect(sessionId, base, candidateId),
    sessionsClearSelection: (sessionId, base) => live().sessionsClearSelection(sessionId, base),
    sessionsRefine: (sessionId, base, x, y, label) => live().sessionsRefine(sessionId, base, x, y, label),
    sessionsDeletePrompt: (sessionId, base, promptId) =>
      live().sessionsDeletePrompt(sessionId, base, promptId),
    sessionsLockRegion: (sessionId, base, x, y, guard) =>
      live().sessionsLockRegion(sessionId, base, x, y, guard),
    sessionsUnlockRegion: (sessionId, base, regionId) =>
      live().sessionsUnlockRegion(sessionId, base, regionId),
    sessionsStartNextRegion: (sessionId, base) =>
      live().sessionsStartNextRegion(sessionId, base),
    sessionsEdit: (sessionId, base, operation, points, radius, clipRect) =>
      live().sessionsEdit(sessionId, base, operation, points, radius, clipRect),
    sessionsUndo: (sessionId, base) => live().sessionsUndo(sessionId, base),
    sessionsRedo: (sessionId, base) => live().sessionsRedo!(sessionId, base),
    sessionsUpdatePrompt: (sessionId, base, promptId, x, y, label) =>
      live().sessionsUpdatePrompt!(sessionId, base, promptId, x, y, label),
    sessionsQa: (sessionId) => live().sessionsQa!(sessionId),
    labelmePreview: (sessionId) => live().labelmePreview!(sessionId),
    labelmeExport: (sessionId, outputGrantId, acknowledgeCleanup) => live().labelmeExport!(sessionId, outputGrantId, acknowledgeCleanup),
    labelmeImport: (sessionId, document, labelMapping, decision) => live().labelmeImport!(sessionId, document, labelMapping, decision),
    draftsFlush: (sessionId, base) => live().draftsFlush!(sessionId, base),
    draftsDiscard: (datasetId, itemId, draftId) => live().draftsDiscard!(datasetId, itemId, draftId),
    sessionsManualEmpty: (sessionId, base, roi) => live().sessionsManualEmpty(sessionId, base, roi),
    sessionsExpandRoi: (sessionId, base) => live().sessionsExpandRoi(sessionId, base),
    sessionsAccept: (sessionId, base, acks, outputGrantId, fitPrototype) =>
      live().sessionsAccept(sessionId, base, acks, outputGrantId, fitPrototype),
    sessionsNeedsReview: (sessionId, base, reason, outputGrantId) =>
      live().sessionsNeedsReview(sessionId, base, reason, outputGrantId),
    sessionsClose: (sessionId, base) => live().sessionsClose(sessionId, base),
    jobsCancel: (sessionId, jobId) => live().jobsCancel(sessionId, jobId),
    loadAsset: (token) => live().loadAsset(token),
  };
}

/**
 * Use the public NativeApp web bridge: same-origin /v1 requests are proxied by
 * the host, while folder selection is provided by window.cimHost.chooseFile.
 */
export function createNativeAppHost(secret: string): HostClient {
  return createCimShellHost(window.location.origin, secret);
}

export function resolveHost(): HostClient {
  const w = window as unknown as {
    __SEGVISION_E2E_HOST__?: HostClient;
    __SEGVISION_CIM_HOST__?: HostClient;
    cimHost?: unknown;
    __TAURI_INTERNALS__?: unknown;
  };
  if (w.__SEGVISION_E2E_HOST__) return w.__SEGVISION_E2E_HOST__;
  if (w.__SEGVISION_CIM_HOST__) return w.__SEGVISION_CIM_HOST__;
  if (w.__TAURI_INTERNALS__ && !w.cimHost) return createTauriHost();
  throw new Error("SegVision host bridge is not available");
}
