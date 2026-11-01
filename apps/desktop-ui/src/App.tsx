import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnnotationCanvas } from "./canvas";
import { resolveHost, type DatasetItemSummary, type HostClient, type Snapshot } from "./host";
import {
  backendLabel,
  candidateSourceLabel,
  computePhaseFromJob,
  engineLabel,
  jobLabel,
  regionStatus,
  workflowLabel,
  type ComputePhase,
} from "./region";
import { DEFAULT_CLASS_ID, useViewStore } from "./store";
import { uniqueWarnings, warningMessageZh } from "./warnings";

export function operatorMessage(error: unknown): string {
  const raw =
    error instanceof Error && error.message
      ? error.message
      : typeof error === "string"
        ? error
        : "";
  let code = "";
  let message = raw;
  if (raw.startsWith("{")) {
    try {
      const parsed = JSON.parse(raw) as { code?: unknown; message?: unknown };
      if (typeof parsed.code === "string") code = parsed.code;
      if (typeof parsed.message === "string") message = parsed.message;
    } catch {
      message = raw;
    }
  } else {
    const split = raw.match(/^([a-z_]+): ([\s\S]+)$/);
    if (split) {
      code = split[1] ?? "";
      message = split[2] ?? raw;
    }
  }
  if (/POINT_CONSTRAINT_VIOLATION/i.test(message)) {
    return "MobileSAM 沒有符合這個點，已保留上一個遮罩。請在目標內側換個位置再點一次，或使用畫筆修補。";
  }
  if (/EMPTY_MASK/i.test(message)) {
    return "MobileSAM 這次產生了空遮罩，已保留上一個結果。請換個位置再點一次。";
  }
  if (/NEAR_FULL_MASK/i.test(message)) {
    return "MobileSAM 這次選取範圍過大，已保留上一個結果。請加入排除點後再試。";
  }
  if (code === "validation_failed" && message) return message;
  if (code === "grant_invalid" || /folder access was cancelled/i.test(message)) {
    return "沒有選擇資料夾。請再按「開啟圖片資料夾」或「儲存遮罩」並選一個資料夾。";
  }
  if (code === "engine_unreachable" || /Failed to fetch/i.test(raw)) {
    return "連不上標註引擎。請再試一次，或選一個資料夾名稱不含中文的路徑。";
  }
  if (code === "revision_conflict") {
    return "影像在你操作時已變更。請再畫一次框。";
  }
  if (message) return message;
  return "這一步無法完成。請再試一次。";
}

/** Convert canvas full-image stroke samples to the active crop coordinate space. */
export function strokePointsToCrop(
  points: number[][],
  cropRect: number[] | null | undefined,
): number[][] {
  if (!cropRect || cropRect.length !== 4) return points;
  const [x0, y0, x1, y1] = cropRect;
  if (![x0, y0, x1, y1].every((value) => Number.isFinite(value))) return [];
  return points
    .map(([x, y]) => [Math.round(x - x0), Math.round(y - y0)])
    .filter(([x, y]) => x >= 0 && y >= 0 && x < x1 - x0 && y < y1 - y0);
}

/** Convert a full-image edit work area to the active crop coordinate space. */
export function editRegionToCrop(
  rect: number[] | null | undefined,
  cropRect: number[] | null | undefined,
): number[] | null {
  if (!rect || rect.length !== 4 || !cropRect || cropRect.length !== 4) return null;
  if (![...rect, ...cropRect].every((value) => Number.isFinite(value))) return null;
  const [cx0, cy0, cx1, cy1] = cropRect;
  const x0 = Math.max(0, Math.min(cx1 - cx0, Math.round(rect[0] - cx0)));
  const y0 = Math.max(0, Math.min(cy1 - cy0, Math.round(rect[1] - cy0)));
  const x1 = Math.max(0, Math.min(cx1 - cx0, Math.round(rect[2] - cx0)));
  const y1 = Math.max(0, Math.min(cy1 - cy0, Math.round(rect[3] - cy0)));
  return x1 > x0 && y1 > y0 ? [x0, y0, x1, y1] : null;
}

function useAssetUrl(
  client: HostClient,
  token: string | null | undefined,
  onFailure: (message: string) => void,
): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let ownedUrl: string | null = null;
    setUrl(null);
    if (!token) return () => undefined;
    void client
      .loadAsset(token)
      .then((asset) => {
        if (!active) {
          if (asset.revoke) URL.revokeObjectURL(asset.url);
          return;
        }
        if (asset.revoke) ownedUrl = asset.url;
        setUrl(asset.url);
      })
      .catch(() => {
        if (active) onFailure("無法載入標註圖層。");
      });
    return () => {
      active = false;
      if (ownedUrl) URL.revokeObjectURL(ownedUrl);
    };
  }, [client, onFailure, token]);

  return url;
}

function CandidateCard(props: {
  client: HostClient;
  index: number;
  candidate: Snapshot["candidates"][number];
  selected: boolean;
  onSelect: () => void;
}) {
  const ignore = useCallback(() => undefined, []);
  const url = useAssetUrl(props.client, props.candidate.mask_token, ignore);
  return (
    <button
      type="button"
      data-testid={`candidate-${props.index}`}
      className={props.selected ? "candidate selected" : "candidate"}
      onClick={props.onSelect}
    >
      <span className="candidate-index">{props.index}</span>
      {url ? <img className="candidate-thumb" src={url} alt="" /> : <span className="candidate-thumb placeholder" />}
      <span className="candidate-copy">
        <strong>選項 {props.index}</strong>
        <span className="candidate-source">{candidateSourceLabel(props.candidate.source)}</span>
        {props.selected ? <span className="candidate-cta">已選 · 可取消或改選</span> : <span className="candidate-cta">切換到這個選項</span>}
      </span>
    </button>
  );
}

export function App({ host }: { host?: HostClient }) {
  const client = useMemo(() => host ?? resolveHost(), [host]);
  const snapshot = useViewStore((s) => s.snapshot);
  const engine = useViewStore((s) => s.engine);
  const items = useViewStore((s) => s.items);
  const datasetItemCount = useViewStore((s) => s.datasetItemCount);
  const outputGrantId = useViewStore((s) => s.outputGrantId);
  const outputDisplayName = useViewStore((s) => s.outputDisplayName);
  const currentItemId = useViewStore((s) => s.currentItemId);
  const uiError = useViewStore((s) => s.uiError);
  const applySnapshot = useViewStore((s) => s.applySnapshot);
  const setDataset = useViewStore((s) => s.setDataset);
  const setOutputGrant = useViewStore((s) => s.setOutputGrant);
  const beginItem = useViewStore((s) => s.beginItem);
  const setEngine = useViewStore((s) => s.setEngine);
  const setTool = useViewStore((s) => s.setTool);
  const selectedPromptId = useViewStore((s) => s.selectedPromptId);
  const setSelectedPromptId = useViewStore((s) => s.setSelectedPromptId);
  const setUiError = useViewStore((s) => s.setUiError);
  const visibleWarnings = uniqueWarnings(snapshot?.warnings ?? []);
  const reuseLastRoi = useViewStore((s) => s.reuseLastRoi);
  const setReuseLastRoi = useViewStore((s) => s.setReuseLastRoi);
  const dinoPrototype = useViewStore((s) => s.dinoPrototype);
  const setDinoPrototype = useViewStore((s) => s.setDinoPrototype);
  const frameRoi = useViewStore((s) => s.frameRoi);
  const railCollapsed = useViewStore((s) => s.railCollapsed);
  const inspectorCollapsed = useViewStore((s) => s.inspectorCollapsed);
  const setRailCollapsed = useViewStore((s) => s.setRailCollapsed);
  const setInspectorCollapsed = useViewStore((s) => s.setInspectorCollapsed);
  const [roiNote, setRoiNote] = useState<string | null>(null);
  const [saveNote, setSaveNote] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [itemSearch, setItemSearch] = useState("");
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingItems, setLoadingItems] = useState(false);
  const [datasetPageError, setDatasetPageError] = useState<string | null>(null);
  const [openingDataset, setOpeningDataset] = useState(false);
  const [advancingItem, setAdvancingItem] = useState(false);
  // Frozen regions are intentionally kept in a small, explicit picker (a
  // "Dropbox") so unlocking never silently targets the last region.
  const [selectedFrozenRegionId, setSelectedFrozenRegionId] = useState<string | null>(null);
  const [qaResult, setQaResult] = useState<Snapshot["qa"] | null>(null);
  const [labelmePreview, setLabelmePreview] = useState<Record<string, unknown> | null>(null);
  const [labelmeCleanupAcknowledged, setLabelmeCleanupAcknowledged] = useState(false);
  const [labelmeReplaceDraft, setLabelmeReplaceDraft] = useState(false);
  const [promptMoveMode, setPromptMoveMode] = useState(false);
  const [dirtyNavigation, setDirtyNavigation] = useState<{
    itemId: string;
    carriedRoi?: { roi: number[]; classId: string };
  } | null>(null);
  const [computePhase, setComputePhase] = useState<ComputePhase>("idle");
  const [backendName, setBackendName] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const timerOrigin = useRef<{ session: string; wall: number } | null>(null);
  const currentItem = items.find((item) => item.item_id === currentItemId) ?? null;
  const navigationEpoch = useRef(0);
  const datasetEpoch = useRef(0);
  const pageCursor = useRef<string | null>(null);
  const pageRequest = useRef<Promise<DatasetItemSummary[]> | null>(null);
  const advancingItemRef = useRef(false);
  const mutationQueue = useRef<Promise<void>>(Promise.resolve());
  const outputPickerEpoch = useRef(0);
  const selectedCandidate = snapshot?.candidates.find(
    (candidate) => candidate.candidate_id === snapshot.selected_candidate_id,
  );
  const promptPoints = snapshot?.prompt_points ?? selectedCandidate?.prompt_points ?? [];
  const selectedPrompt = promptPoints.find(
    (point, index) => (point.point_id ?? `prompt-${index}`) === selectedPromptId,
  );
  const frozenRegions = snapshot?.frozen_regions ?? [];
  const filteredItems = useMemo(() => {
    const query = itemSearch.trim().toLowerCase();
    return items.filter((item) => {
      const matchesStatus = statusFilter === "all" || (item.status ?? "unstarted") === statusFilter;
      const matchesSearch = !query || `${item.display_name} ${item.image_id}`.toLowerCase().includes(query);
      return matchesStatus && matchesSearch;
    });
  }, [items, itemSearch, statusFilter]);
  const progress = useMemo(() => {
    const counts = { accepted: 0, draft: 0, review: 0, failure: 0 };
    for (const item of items) {
      if (item.status === "accepted") counts.accepted += 1;
      if (item.status === "draft") counts.draft += 1;
      if (item.status === "needs-review") counts.review += 1;
      if (item.status === "save-failed" || item.status === "conflict-or-corrupt") counts.failure += 1;
    }
    return counts;
  }, [items]);
  const frozenRegionKey = `${snapshot?.protocol_session_id ?? ""}:${frozenRegions
    .map((region) => region.region_id)
    .join("|")}`;

  useEffect(() => {
    const ids = frozenRegions.map((region) => region.region_id);
    setSelectedFrozenRegionId((current) => {
      if (current && ids.includes(current)) return current;
      return ids[ids.length - 1] ?? null;
    });
  }, [frozenRegionKey]);

  const showAssetError = useCallback(
    (message: string) => setUiError(message ? message : null),
    [setUiError],
  );
  const imageUrl = useAssetUrl(client, snapshot?.assets.source_image, showAssetError);
  const viewerMaskToken =
    snapshot?.workflow_state === "IMAGE_OPEN"
      ? currentItem?.gold_mask_token ?? null
      : snapshot?.assets.mask ?? null;
  const maskUrl = useAssetUrl(client, viewerMaskToken, showAssetError);
  const lockedForegroundUrl = useAssetUrl(
    client,
    snapshot?.assets.locked_foreground,
    showAssetError,
  );
  const lockedBackgroundUrl = useAssetUrl(
    client,
    snapshot?.assets.locked_background,
    showAssetError,
  );

  useEffect(() => {
    let active = true;
    void client
      .engineHealth()
      .then((health) => {
        if (!active) return;
        setEngine(health.ready ? "ready" : "engine_unavailable");
        setBackendName(health.backend?.name ?? null);
        if (!health.ready) setUiError(`標註引擎尚未就緒：${health.setup_state}`);
      })
      .catch(() => {
        if (!active) return;
        setEngine("engine_unavailable");
        setUiError("無法連上標註引擎。");
      });
    return () => {
      active = false;
    };
  }, [client, setEngine, setUiError]);

  useEffect(() => {
    const sessionId = snapshot?.protocol_session_id;
    const job = snapshot?.job;
    if (!sessionId || job?.status !== "running" || !job.job_id) return;
    let cancelled = false;
    const tick = () => {
      void client.sessionsGet(sessionId).then((snap) => {
        if (cancelled) return;
        const latest = useViewStore.getState().snapshot;
        if (!latest || latest.protocol_session_id !== sessionId) return;
        if (snap.revision < latest.revision) return;
        applySnapshot(snap);
      });
    };
    const id = window.setInterval(tick, 250);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [applySnapshot, client, snapshot?.job?.job_id, snapshot?.job?.status, snapshot?.protocol_session_id]);

  function withSnap(work: (current: Snapshot) => Promise<Snapshot>) {
    const requested = useViewStore.getState().snapshot;
    if (engine !== "ready" || !requested) return Promise.resolve();
    const epoch = navigationEpoch.current;
    const sessionId = requested.protocol_session_id;
    const run = async () => {
      const current = useViewStore.getState().snapshot;
      if (
        epoch !== navigationEpoch.current ||
        current?.protocol_session_id !== sessionId
      ) {
        return;
      }
      try {
        setUiError(null);
        const snap = await work(current);
        const latest = useViewStore.getState().snapshot;
        if (
          epoch !== navigationEpoch.current ||
          latest?.protocol_session_id !== sessionId ||
          snap.protocol_session_id !== sessionId ||
          snap.revision < latest.revision
        ) {
          return;
        }
        applySnapshot(snap);
        if (snap.prototype?.note) setRoiNote(snap.prototype.note);
        setUiError(snap.last_error ?? null);
      } catch (error) {
        if (epoch === navigationEpoch.current) setUiError(operatorMessage(error));
      }
    };
    const queued = mutationQueue.current.then(run, run);
    mutationQueue.current = queued.catch(() => undefined);
    return queued;
  }

  async function returnToSam() {
    // A manual session can contain several completed strokes.  Undo until
    // the authoritative SAM candidate is restored, but stop if the host did
    // not change the snapshot (for example, an empty undo history).
    for (let attempt = 0; attempt < 32; attempt += 1) {
      const before = useViewStore.getState().snapshot;
      if (!before) return;
      const selected = before.candidates.find(
        (candidate) => candidate.candidate_id === before.selected_candidate_id,
      );
      if (selected && selected.source !== "manual_edit" && selected.source !== "manual_empty") {
        setTool("point");
        return;
      }
      const beforeId = before.selected_candidate_id;
      await withSnap((current) =>
        client.sessionsUndo(current.protocol_session_id, current.revision),
      );
      const after = useViewStore.getState().snapshot;
      if (!after || after.selected_candidate_id === beforeId) return;
    }
  }

  async function loadNextDatasetPage(): Promise<DatasetItemSummary[]> {
    if (pageRequest.current) return pageRequest.current;
    const state = useViewStore.getState();
    const datasetId = state.datasetId;
    const cursor = pageCursor.current;
    if (!datasetId || !cursor) return [];

    const requestEpoch = datasetEpoch.current;
    setDatasetPageError(null);
    setLoadingItems(true);
    const request = (async () => {
      try {
        const page = await client.datasetsListItems(datasetId, cursor);
        const latest = useViewStore.getState();
        if (requestEpoch !== datasetEpoch.current || latest.datasetId !== datasetId) return [];
        if (page.next_cursor === cursor) throw new Error("dataset cursor did not advance");
        pageCursor.current = page.next_cursor;
        setNextCursor(page.next_cursor);
        latest.appendDatasetItems(page.items);
        return page.items;
      } catch (error) {
        if (requestEpoch === datasetEpoch.current) setDatasetPageError(operatorMessage(error));
        return [];
      } finally {
        if (requestEpoch === datasetEpoch.current) setLoadingItems(false);
      }
    })();
    pageRequest.current = request;
    const result = await request;
    if (pageRequest.current === request) pageRequest.current = null;
    return result;
  }

  async function loadAllDatasetPages(): Promise<void> {
    const requestEpoch = datasetEpoch.current;
    while (pageCursor.current && requestEpoch === datasetEpoch.current) {
      const cursorBefore = pageCursor.current;
      await loadNextDatasetPage();
      if (pageCursor.current === cursorBefore) return;
    }
  }

  async function openDataset() {
    const epoch = ++navigationEpoch.current;
    const openEpoch = ++datasetEpoch.current;
    setDatasetPageError(null);
    pageRequest.current = null;
    setLoadingItems(false);
    setOpeningDataset(true);
    mutationQueue.current = Promise.resolve();
    try {
      setUiError(null);
      const grant = await client.pickerOpenFolder("dataset");
      const opened = await client.datasetsOpen(grant.grant_id);
      const listed = await client.datasetsListItems(opened.dataset_id);
      if (epoch !== navigationEpoch.current || openEpoch !== datasetEpoch.current) return;
      pageCursor.current = listed.next_cursor;
      setNextCursor(listed.next_cursor);
      setLoadingItems(false);
      setDataset(grant.grant_id, opened.dataset_id, listed.items, opened.item_count);
      const first = listed.items[0];
      if (first) await openItem(first.item_id);
    } catch (error) {
      if (epoch === navigationEpoch.current) setUiError(operatorMessage(error));
    } finally {
      if (openEpoch === datasetEpoch.current) setOpeningDataset(false);
    }
  }

  async function chooseOutputFolder(): Promise<boolean> {
    const epoch = ++outputPickerEpoch.current;
    try {
      setUiError(null);
      const grant = await client.pickerOpenFolder("output");
      if (epoch !== outputPickerEpoch.current) return false;
      setOutputGrant(grant.grant_id, grant.display_name);
      return true;
    } catch (error) {
      if (epoch === outputPickerEpoch.current) setUiError(operatorMessage(error));
      return false;
    }
  }

  async function ensureOutputGrant(): Promise<string | null> {
    const existing = useViewStore.getState().outputGrantId;
    if (existing) return existing;
    const picked = await chooseOutputFolder();
    if (!picked) return null;
    return useViewStore.getState().outputGrantId;
  }

  function frameLockedRoi(roi: number[] | null | undefined) {
    if (!roi || roi.length !== 4) return;
    frameRoi([roi[0], roi[1], roi[2], roi[3]]);
  }

  async function openItem(
    itemId: string,
    carriedRoi?: { roi: number[]; classId: string },
    bypassDirtyGuard = false,
  ) {
    const ds = useViewStore.getState().datasetId;
    if (!ds) return;
    const current = useViewStore.getState().snapshot;
    if (!bypassDirtyGuard && current?.draft?.dirty) {
      setDirtyNavigation({ itemId, carriedRoi });
      return;
    }
    const epoch = ++navigationEpoch.current;
    mutationQueue.current = Promise.resolve();
    beginItem(itemId);
    setRoiNote(null);
    try {
      setUiError(null);
      if (current) {
        await client.sessionsClose(current.protocol_session_id, current.revision);
        if (epoch !== navigationEpoch.current) return;
      }
      const useDino = useViewStore.getState().dinoPrototype;
      if (useDino) setComputePhase("matching-dino");
      const snap = await client.sessionsCreate(ds, itemId, useDino);
      if (epoch !== navigationEpoch.current) return;
      applySnapshot(snap);
      setUiError(snap.last_error ?? null);
      if (snap.prototype?.note) setRoiNote(snap.prototype.note);
      if (snap.prototype?.matched && snap.user_roi_full) {
        frameLockedRoi(snap.user_roi_full);
        setComputePhase("idle");
        return;
      }
      setComputePhase("idle");
      if (useDino || !carriedRoi) return;
      const outputGrant = useViewStore.getState().outputGrantId;
      try {
        setComputePhase("locking-sam");
        const locked = await client.sessionsLockRoi(
          snap.protocol_session_id,
          snap.revision,
          carriedRoi.classId,
          carriedRoi.roi,
          outputGrant,
        );
        if (epoch !== navigationEpoch.current) return;
        if (locked.protocol_session_id !== snap.protocol_session_id) return;
        applySnapshot(locked);
        frameLockedRoi(locked.user_roi_full);
        setRoiNote("已沿用上一張的框。");
        setUiError(locked.last_error ?? null);
      } catch (error) {
        if (epoch === navigationEpoch.current) {
          setRoiNote(null);
          setUiError(operatorMessage(error));
        }
      }
    } catch (error) {
      if (epoch === navigationEpoch.current) setUiError(operatorMessage(error));
    } finally {
      if (epoch === navigationEpoch.current) setComputePhase("idle");
    }
  }

  function carriedRoiFrom(snapshot: Snapshot | null): { roi: number[]; classId: string } | undefined {
    if (!snapshot) return undefined;
    const roi = snapshot.user_roi_full;
    if (!roi || roi.length !== 4 || roi.some((value) => !Number.isInteger(value))) return undefined;
    const order = filteredItems.length > 0 ? filteredItems : items;
    const nextIndex = order.findIndex((item) => item.item_id === currentItemId) + 1;
    const nextItem = order.slice(nextIndex).find((item) => item.status !== "accepted" && item.status !== "needs-review");
    const classId = snapshot.class_id || nextItem?.class_id || currentItem?.class_id || DEFAULT_CLASS_ID;
    return { roi: [...roi], classId };
  }

  async function openNextItem() {
    if (advancingItemRef.current) return;
    advancingItemRef.current = true;
    const epoch = navigationEpoch.current;
    setAdvancingItem(true);
    try {
      while (true) {
        const state = useViewStore.getState();
        const query = itemSearch.trim().toLowerCase();
        const matchingItems = state.items.filter((item) => {
          const matchesStatus = statusFilter === "all" || (item.status ?? "unstarted") === statusFilter;
          const matchesSearch = !query || `${item.display_name} ${item.image_id}`.toLowerCase().includes(query);
          return matchesStatus && matchesSearch;
        });
        const order = matchingItems.length > 0 ? matchingItems : state.items;
        const currentIndex = order.findIndex((item) => item.item_id === currentItemId);
        const next = order
          .slice(currentIndex + 1)
          .find((item) => item.status !== "accepted" && item.status !== "needs-review");
        if (next) {
          const carried =
            state.dinoPrototype || !state.reuseLastRoi ? undefined : carriedRoiFrom(state.snapshot);
          await openItem(next.item_id, carried);
          return;
        }
        if (!pageCursor.current) return;
        const cursorBefore = pageCursor.current;
        const appended = await loadNextDatasetPage();
        if (epoch !== navigationEpoch.current) return;
        if (appended.length === 0 && cursorBefore === pageCursor.current) return;
      }
    } finally {
      advancingItemRef.current = false;
      setAdvancingItem(false);
    }
  }

  async function resolveDirtyNavigation(action: "save" | "discard" | "cancel") {
    const pending = dirtyNavigation;
    if (!pending) return;
    if (action === "cancel") {
      setDirtyNavigation(null);
      return;
    }
    const state = useViewStore.getState();
    const current = state.snapshot;
    try {
      setUiError(null);
      if (action === "save") {
        if (!current || !client.draftsFlush) throw new Error("draft_flush_unavailable");
        const flushed = await client.draftsFlush(current.protocol_session_id, current.revision);
        applySnapshot(flushed);
      } else if (client.draftsDiscard && state.datasetId && state.currentItemId) {
        await client.draftsDiscard(state.datasetId, state.currentItemId, current?.draft && (current.draft as { draft_id?: string }).draft_id);
      }
      setDirtyNavigation(null);
      await openItem(pending.itemId, pending.carriedRoi, true);
    } catch (error) {
      setUiError(operatorMessage(error));
    }
  }

  function acceptCurrent(advance = false) {
    const ready = useViewStore.getState().snapshot;
    if (!ready?.controls.accept) return;
    void (async () => {
      const grant = await ensureOutputGrant();
      if (!grant) return;
      const current = useViewStore.getState().snapshot;
      if (!current?.controls.accept) return;
      const acknowledgements = (current.warnings || []).map((warning) => warning.code);
      const fit = useViewStore.getState().dinoPrototype;
      if (fit) setComputePhase("fitting-dino");
      try {
        await withSnap((session) =>
          client.sessionsAccept(
            session.protocol_session_id,
            session.revision,
            acknowledgements,
            grant,
            fit,
          ),
        );
        const folder = useViewStore.getState().outputDisplayName;
        setSaveNote(folder ? `已儲存到 ${folder}` : "已儲存遮罩。");
        if (advance) openNextItem();
      } finally {
        setComputePhase("idle");
      }
    })();
  }

  function needsReviewCurrent() {
    const ready = useViewStore.getState().snapshot;
    if (!ready?.controls.needs_review) return;
    void (async () => {
      const grant = await ensureOutputGrant();
      if (!grant) return;
      const current = useViewStore.getState().snapshot;
      if (!current?.controls.needs_review) return;
      await withSnap((session) =>
        client.sessionsNeedsReview(
          session.protocol_session_id,
          session.revision,
          "needs review",
          grant,
        ),
      );
    })();
  }

  function previewLabelMe() {
    const current = useViewStore.getState().snapshot;
    if (!current || !client.labelmePreview) return;
    void client.labelmePreview(current.protocol_session_id)
      .then((preview) => {
        setLabelmePreview(preview);
        setLabelmeCleanupAcknowledged(false);
      })
      .catch((error) => setUiError(operatorMessage(error)));
  }

  async function exportLabelMe() {
    const current = useViewStore.getState().snapshot;
    if (!current || !client.labelmeExport) return;
    const grant = await ensureOutputGrant();
    if (!grant) return;
    try {
      const result = await client.labelmeExport(current.protocol_session_id, grant, labelmeCleanupAcknowledged);
      setSaveNote(`LabelMe JSON 已輸出：${String(result.path ?? "完成")}`);
    } catch (error) {
      setUiError(operatorMessage(error));
    }
  }

  async function importLabelMeFile(file: File | undefined) {
    const current = useViewStore.getState().snapshot;
    if (!file || !current || !client.labelmeImport) return;
    try {
      const parsed = JSON.parse(await file.text()) as Record<string, unknown>;
      const result = await client.labelmeImport(
        current.protocol_session_id,
        parsed,
        undefined,
        labelmeReplaceDraft ? "replace" : undefined,
      );
      if (result.snapshot) applySnapshot(result.snapshot as Snapshot);
      setSaveNote("LabelMe 標註已匯入為可編輯草稿。");
      setLabelmeReplaceDraft(false);
    } catch (error) {
      setUiError(operatorMessage(error));
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const snap = useViewStore.getState().snapshot;
      if (!snap) return;
      if (e.key === "1" || e.key === "2" || e.key === "3") {
        const card = Number(e.key) - 1;
        const id = snap.candidates[card]?.candidate_id;
        if (id) {
          void withSnap((current) =>
            client.sessionsSelect(current.protocol_session_id, current.revision, id),
          );
        }
      } else if (e.key.toLowerCase() === "b" && snap.controls.local_edit) {
        setTool("brush");
      } else if (e.key.toLowerCase() === "e" && snap.controls.local_edit) {
        setTool("erase");
      } else if (e.key.toLowerCase() === "h") {
        setTool("pan");
      } else if (e.key === "[" && snap.controls.local_edit) {
        void withSnap((current) =>
          client.sessionsEdit(current.protocol_session_id, current.revision, "shrink"),
        );
      } else if (e.key === "]" && snap.controls.local_edit) {
        void withSnap((current) =>
          client.sessionsEdit(current.protocol_session_id, current.revision, "grow"),
        );
      } else if (e.key.toLowerCase() === "f" && snap.controls.local_edit) {
        void withSnap((current) =>
          client.sessionsEdit(current.protocol_session_id, current.revision, "fill_holes"),
        );
      } else if (e.key.toLowerCase() === "x" && snap.controls.roi) {
        void withSnap((current) =>
          client.sessionsExpandRoi(current.protocol_session_id, current.revision),
        );
      } else if (e.key.toLowerCase() === "z") {
        void withSnap((current) =>
          client.sessionsUndo(current.protocol_session_id, current.revision),
        );
      }
      else if (e.key === " ") {
        e.preventDefault();
        if (snap.controls.accept) acceptCurrent(false);
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (snap.controls.accept) acceptCurrent(true);
        else if (snap.controls.next) openNextItem();
      } else if (e.key.toLowerCase() === "n") {
        if (snap.controls.next) openNextItem();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [client, engine, items, filteredItems, currentItemId, outputGrantId, statusFilter, itemSearch, setTool]);

  const displayedError = uiError ?? snapshot?.last_error ?? null;
  const workflow = snapshot?.workflow_state ?? "NONE";
  const displayedCompute = computePhaseFromJob(computePhase, snapshot?.job);

  useEffect(() => {
    const session = snapshot?.protocol_session_id ?? null;
    const locked = snapshot?.first_roi_locked_at;
    if (!session || locked == null) {
      if (timerOrigin.current?.session !== session) {
        timerOrigin.current = null;
        setElapsed(null);
      }
      return;
    }
    if (timerOrigin.current?.session !== session) {
      timerOrigin.current = { session, wall: Date.now() };
    }
    const tick = () => {
      const origin = timerOrigin.current;
      if (!origin) return;
      setElapsed((Date.now() - origin.wall) / 1000);
    };
    tick();
    const id = window.setInterval(tick, 250);
    return () => window.clearInterval(id);
  }, [snapshot?.protocol_session_id, snapshot?.first_roi_locked_at]);

  function itemLabel(item: { display_name?: string; image_id?: string; item_id: string }): string {
    if (item.display_name) return item.display_name;
    const id = item.image_id || "";
    const slash = Math.max(id.lastIndexOf("/"), id.lastIndexOf("\\"));
    return (slash >= 0 ? id.slice(slash + 1) : id) || item.item_id;
  }

  return (
    <div
      className="app"
      data-rail-collapsed={railCollapsed ? "true" : "false"}
      data-inspector-collapsed={inspectorCollapsed ? "true" : "false"}
    >
      <header>
        <h1>SegVision</h1>
        <span data-testid="engine-state" data-state={engine} className="pill">
          {engineLabel(engine)}
        </span>
        <span
          data-testid="backend-name"
          data-backend={backendName ?? ""}
          className={backendName === "fake" ? "pill timer-hot" : "pill"}
        >
          {backendLabel(backendName)}
        </span>
        <span data-testid="workflow-state" data-state={workflow} className="pill">
          {workflowLabel(workflow)}
        </span>
        <span data-testid="revision" className="pill pill-muted">
          版次 {snapshot?.revision ?? 0}
        </span>
        {snapshot?.job?.job_id ? (
          <span
            data-testid="job-state"
            data-kind={snapshot.job.kind ?? ""}
            data-status={snapshot.job.status ?? ""}
            className={snapshot.job.status === "running" ? "pill timer-hot" : "pill pill-muted"}
          >
            {jobLabel(snapshot.job.kind, snapshot.job.status)}
          </span>
        ) : null}
        {elapsed != null ? (
          <span
            data-testid="roi-timer"
            className={elapsed >= 30 ? "pill timer-hot" : "pill"}
          >
            {elapsed.toFixed(1)}s
          </span>
        ) : null}
        <button className="btn header-btn" data-testid="open-dataset" disabled={openingDataset} onClick={() => void openDataset()}>
          {openingDataset ? "載入資料夾…" : "開啟圖片資料夾"}
        </button>
        <button className="btn header-btn" data-testid="choose-output" onClick={() => void chooseOutputFolder()}>
          {outputGrantId ? "更改儲存資料夾" : "儲存資料夾"}
        </button>
        {outputDisplayName ? (
          <span data-testid="output-grant" className="muted-line header-grant" title={outputDisplayName}>
            儲存於 {outputDisplayName}
          </span>
        ) : (
          <span data-testid="output-missing" className="muted-line header-grant">
            儲存時再選資料夾
          </span>
        )}
        <div className="header-right">
          {roiNote ? (
            <span data-testid="roi-reuse-status" className="note-chip">
              {roiNote}
            </span>
          ) : null}
          {saveNote && !displayedError ? (
            <span data-testid="save-note" className="note-chip ok">
              {saveNote}
            </span>
          ) : null}
          {snapshot?.draft?.state ? (
            <span data-testid="draft-status" className={snapshot.draft.dirty ? "note-chip warn" : "note-chip ok"}>
              草稿：{snapshot.draft.state === "saved" ? "已自動儲存" : snapshot.draft.state}
            </span>
          ) : null}
          {engine !== "ready" ? (
            <span className="note-chip" data-testid="engine-banner">
              標註引擎尚未就緒
            </span>
          ) : null}
          <button
            type="button"
            className="btn"
            data-testid="restart-engine"
            disabled={!client.engineRestart || engine === "recovering"}
            onClick={() => {
              if (!client.engineRestart) return;
              setEngine("recovering");
              void client.engineRestart()
                .then(() => client.engineHealth())
                .then((health) => setEngine(health.ready ? "ready" : "engine_unavailable"))
                .catch((error) => {
                  setEngine("engine_unavailable");
                  setUiError(operatorMessage(error));
                });
            }}
          >
            重新啟動 MobileSAM 引擎
          </button>
          {displayedError ? (
            <output data-testid="operation-error" role="alert">
              {displayedError}
            </output>
          ) : null}
        </div>
      </header>
      {dirtyNavigation ? (
        <div className="modal-backdrop" data-testid="dirty-navigation-dialog" role="dialog" aria-modal="true">
          <div className="modal-card">
            <strong>目前有尚未完成的草稿</strong>
            <p>切換前請選擇儲存草稿、捨棄，或取消。</p>
            <div className="edit-row">
              <button type="button" className="btn accept" data-testid="dirty-save" onClick={() => void resolveDirtyNavigation("save")}>先儲存草稿</button>
              <button type="button" className="btn review" data-testid="dirty-discard" onClick={() => void resolveDirtyNavigation("discard")}>捨棄</button>
              <button type="button" className="btn" data-testid="dirty-cancel" onClick={() => void resolveDirtyNavigation("cancel")}>取消</button>
            </div>
          </div>
        </div>
      ) : null}
      <aside className="rail">
        <button
          type="button"
          className="collapse-strip"
          data-testid="toggle-rail"
          onClick={() => setRailCollapsed(!railCollapsed)}
        >
          {railCollapsed ? "影像" : "收合"}
        </button>
        <div className="rail-body">
        <div className="rail-list">
          <div className="section-label">影像</div>
          <input
            data-testid="item-search"
            className="item-search"
            value={itemSearch}
            placeholder="搜尋已載入影像"
            onChange={(event) => setItemSearch(event.target.value)}
          />
          <select data-testid="status-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">全部</option>
            <option value="unstarted">未開始</option>
            <option value="draft">草稿</option>
            <option value="accepted">已接受</option>
            <option value="needs-review">待複核</option>
            <option value="save-failed">儲存失敗</option>
            <option value="conflict-or-corrupt">衝突/損壞</option>
          </select>
          <div data-testid="dataset-page-status" className="muted-line">
            {`已載入 ${items.length} / ${datasetItemCount ?? items.length} 張`}
          </div>
          {datasetPageError ? (
            <div data-testid="dataset-page-error" className="muted-line" role="alert">{datasetPageError}</div>
          ) : null}
          <div data-testid="work-progress" className="muted-line">
            {`已接受 ${progress.accepted} · 草稿 ${progress.draft} · 待複核 ${progress.review} · 未解決 ${progress.failure}（已載入項目）`}
          </div>
          <ul data-testid="item-list">
            {filteredItems.map((item) => (
              <li key={item.item_id}>
                <button
                  className={item.item_id === currentItemId ? "item-row current" : "item-row"}
                  title={itemLabel(item)}
                  onClick={() => void openItem(item.item_id)}
                >
                  <span>{itemLabel(item)}</span>
                  <span data-testid={`item-status-${item.item_id}`} className="item-status">
                    {item.status ?? "unstarted"}
                  </span>
                </button>
              </li>
            ))}
            {items.length > 0 && filteredItems.length === 0 ? (
              <li className="muted-line" role="status">目前已載入的影像沒有符合條件的項目。</li>
            ) : null}
          </ul>
          {nextCursor ? (
            <button
              type="button"
              className="btn load-more-items"
              data-testid="load-more-items"
              disabled={loadingItems || openingDataset || advancingItem}
              onClick={() => void loadNextDatasetPage()}
            >
              {loadingItems ? "載入中…" : "載入更多影像"}
            </button>
          ) : null}
          {nextCursor && (itemSearch.trim() || statusFilter !== "all") ? (
            <button
              type="button"
              className="btn load-more-items"
              data-testid="load-all-filtered-items"
              disabled={loadingItems || openingDataset || advancingItem}
              onClick={() => void loadAllDatasetPages()}
            >
              載入完整清單後套用篩選
            </button>
          ) : null}
        </div>
        <div className="rail-session">
          <div className="section-label">工作階段</div>
          <label>
            <input
              type="checkbox"
              data-testid="reuse-last-roi"
              checked={reuseLastRoi}
              onChange={(event) => setReuseLastRoi(event.target.checked)}
            />
            下一張沿用上一個框
          </label>
          <button
            type="button"
            className="advanced-toggle"
            data-testid="toggle-advanced"
            onClick={() => setShowAdvanced((value) => !value)}
          >
            {showAdvanced ? "收合進階" : "進階"}
          </button>
          {showAdvanced ? (
            <label title="儲存後記住這個遮罩。下一張會依外觀尋找，而不是複製這個框。">
              <input
                type="checkbox"
                data-testid="dino-prototype"
                checked={dinoPrototype}
                onChange={(event) => setDinoPrototype(event.target.checked)}
              />
              下一張依外觀尋找相似區域
            </label>
          ) : null}
        </div>
        </div>
      </aside>
      <main>
        <div className="viewer-shell">
        <AnnotationCanvas
          imageUrl={imageUrl}
          maskUrl={maskUrl}
          lockedForegroundUrl={lockedForegroundUrl}
          lockedBackgroundUrl={lockedBackgroundUrl}
          onAssetError={showAssetError}
          computePhase={displayedCompute}
          statusText={regionStatus({
            hasImage: Boolean(imageUrl),
            workflow,
            dinoOn: dinoPrototype,
            computePhase: displayedCompute,
            hasRoi: Boolean(snapshot?.user_roi_full),
            candidateCount: snapshot?.candidates.length ?? 0,
            prototype: snapshot?.prototype,
          })}
          onRoi={(roi) => {
            const current = useViewStore.getState().snapshot;
            if (!current?.controls.roi) return;
            const classId = current.class_id || useViewStore.getState().items.find(
              (item) => item.item_id === useViewStore.getState().currentItemId,
            )?.class_id || DEFAULT_CLASS_ID;
            setComputePhase("locking-sam");
            void withSnap((current) =>
              client.sessionsLockRoi(
                current.protocol_session_id,
                current.revision,
                classId,
                roi,
                useViewStore.getState().outputGrantId,
              ),
            )
              .then(() => {
                const locked = useViewStore.getState().snapshot;
                frameLockedRoi(locked?.user_roi_full);
                setRoiNote(null);
                if (
                  locked &&
                  (locked.candidates?.length ?? 0) === 0 &&
                  locked.workflow_state !== "MANUAL_EMPTY" &&
                  locked.job?.status !== "failed"
                ) {
                  return withSnap((current) =>
                    client.sessionsPropose(current.protocol_session_id, current.revision),
                  );
                }
                return undefined;
              })
              .finally(() => setComputePhase("idle"));
          }}
          onPoint={(x, y, label) => {
            // Read capabilities at pointer time.  Candidate selection and
            // sidecar job completion can land between the render that
            // enabled the point tool and the actual canvas click; using the
            // render closure here silently drops that click.
            const current = useViewStore.getState().snapshot;
            if (!current?.controls.refine) {
              setUiError("目前已進入手動編輯，SAM 點選暫停；請按「回到 SAM 結果」後再加點或排除。");
              return;
            }
            void withSnap((current) =>
              client.sessionsRefine(current.protocol_session_id, current.revision, x, y, label),
            );
          }}
          onStroke={(points, erase, editRegion) => {
            // Read the store at pointer-up time.  A SAM response can arrive
            // between pointer-down and pointer-up; the render closure may
            // otherwise still carry the previous (disabled) capability.
            const current = useViewStore.getState().snapshot;
            if (!current || points.length === 0 || (!current.controls.local_edit && !editRegion)) return;
            const radius = useViewStore.getState().brushRadius;
            void withSnap(async (current) => {
              let active = current;
              if (!active.controls.local_edit) {
                if (!editRegion) return active;
                active = await client.sessionsManualEmpty(
                  active.protocol_session_id,
                  active.revision,
                  editRegion,
                );
              }
              const cropPoints = strokePointsToCrop(points, active.crop_rect_full);
              if (cropPoints.length === 0) return active;
              const clipRect = editRegionToCrop(editRegion, active.crop_rect_full);
              // `null` means an unrestricted edit to the sidecar. If a user
              // explicitly drew a work area, a missing crop intersection
              // must fail closed instead of accidentally removing the clip.
              if (editRegion && !clipRect) return active;
              return client.sessionsEdit(
                active.protocol_session_id,
                active.revision,
                erase ? "erase" : "brush",
                cropPoints,
                radius,
                clipRect,
              );
            });
          }}
          onLockRegion={(x, y) => {
            if (!snapshot?.controls.lock_region) return;
            void withSnap((current) =>
              client.sessionsLockRegion(
                current.protocol_session_id,
                current.revision,
                x,
                y,
                true,
              ),
            );
          }}
          onReturnToSam={() => {
            void returnToSam();
          }}
          promptMoveMode={promptMoveMode}
          onPromptMove={(pointId, x, y) => {
            if (!client.sessionsUpdatePrompt) return;
            void withSnap((current) =>
              client.sessionsUpdatePrompt!(current.protocol_session_id, current.revision, pointId, x, y),
            );
          }}
          onPromptMoveDone={() => setPromptMoveMode(false)}
        />
        {!imageUrl && !snapshot?.assets.source_image ? (
          <div className="empty-canvas" data-testid="empty-canvas">
            {items.length === 0 ? (
              <>
                <p>開啟圖片資料夾開始標註</p>
                <p className="empty-sub">選好圖片資料夾後，在缺陷周圍點兩個角建立黃框。儲存資料夾可等到按儲存再選。</p>
                <button type="button" className="btn accept save-bar-accept" onClick={() => void openDataset()}>
                  開啟圖片資料夾
                </button>
              </>
            ) : (
              <p>請點左側影像</p>
            )}
          </div>
        ) : null}
        {snapshot?.controls.accept && engine === "ready" ? (
          <div className="save-bar" data-testid="save-bar">
            <div className="save-bar-copy">
              <strong>儲存這個遮罩</strong>
              <p>
                {outputDisplayName
                  ? `會寫入 ${outputDisplayName}。空白鍵只儲存，Enter 儲存並下一張。`
                  : "點儲存後會先選資料夾，再寫入 PNG。空白鍵只儲存，Enter 儲存並下一張。"}
              </p>
            </div>
            <button
              type="button"
              data-testid="save-bar-accept"
              className="btn accept save-bar-accept"
              onClick={() => acceptCurrent(false)}
            >
              {outputGrantId ? "儲存遮罩" : "選擇資料夾並儲存"}
            </button>
            <button
              type="button"
              data-testid="save-and-next"
              className="btn header-btn"
              onClick={() => acceptCurrent(true)}
            >
              儲存並下一張
            </button>
            <button
              type="button"
              data-testid="save-bar-review"
              className="btn review"
              title="遮罩不確定時用，不會當成已完成標註"
              disabled={!snapshot.controls.needs_review}
              onClick={needsReviewCurrent}
            >
              待覆核
            </button>
          </div>
        ) : null}
        {snapshot?.workflow_state === "ACCEPTED" && engine === "ready" ? (
          <div className="save-bar saved" data-testid="saved-bar">
            <div className="save-bar-copy">
              <strong>已儲存</strong>
              <p>{saveNote || "遮罩 PNG 已寫入資料夾。"}</p>
            </div>
            <button
              type="button"
              className="btn accept save-bar-accept"
              disabled={!snapshot.controls.next}
              onClick={openNextItem}
            >
              下一張
            </button>
          </div>
        ) : null}
        </div>
      </main>
      <section className="inspector">
        <button
          type="button"
          className="collapse-strip"
          data-testid="toggle-inspector"
          onClick={() => setInspectorCollapsed(!inspectorCollapsed)}
        >
          {inspectorCollapsed ? "檢查" : "收合"}
        </button>
        <div className="inspector-body">
        <div>
          <div className="section-label">這個框裡的選項</div>
          <div data-testid="candidate-cards" className="candidate-stack">
            {(snapshot?.candidates ?? []).length === 0 ? (
              <ol className="workflow-steps" data-testid="region-empty">
                <li>在缺陷周圍點兩個角建立黃框</li>
                <li>這裡最多出現 3 個遮罩選項</li>
                <li>點最貼合的一個，再儲存遮罩</li>
              </ol>
            ) : null}
            {(snapshot?.candidates ?? []).map((c, i) => (
              <CandidateCard
                key={c.candidate_id}
                client={client}
                index={i + 1}
                candidate={c}
                selected={c.candidate_id === snapshot?.selected_candidate_id}
                onSelect={() => {
                  if (!snapshot) return;
                  void withSnap((current) =>
                    client.sessionsSelect(current.protocol_session_id, current.revision, c.candidate_id),
                  );
                }}
              />
            ))}
            {snapshot?.selected_candidate_id &&
            ["PROPOSAL_READY", "REFINED_READY"].includes(snapshot.workflow_state) ? (
              <button
                type="button"
                data-testid="cancel-candidate-selection"
                className="btn"
                onClick={() =>
                  void withSnap((current) =>
                    client.sessionsClearSelection(
                      current.protocol_session_id,
                      current.revision,
                    ),
                  )
                }
              >
                取消選擇
              </button>
            ) : null}
          </div>
        </div>
        {promptPoints.length > 0 ? (
          <div className="prompt-panel" data-testid="prompt-panel">
            <div className="section-label">SAM 提示點（{promptPoints.length}）</div>
            <div className="prompt-chips">
              {promptPoints.map((point, index) => {
                const id = point.point_id ?? `prompt-${index}`;
                return (
                  <button
                    key={id}
                    type="button"
                    className={selectedPromptId === id ? "prompt-chip selected" : "prompt-chip"}
                    data-testid={`prompt-chip-${index}`}
                    aria-pressed={selectedPromptId === id}
                    onClick={() => {
                      setSelectedPromptId(id);
                      setTool("prompt-select");
                    }}
                  >
                    {point.label === 1 ? "＋" : "－"} {point.x}, {point.y}
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              className="btn edit-btn prompt-delete"
              data-testid="delete-prompt"
              disabled={!selectedPrompt?.point_id || !snapshot?.controls.delete_prompt}
              title={
                selectedPrompt?.point_id
                  ? "刪除後 MobileSAM 會使用其餘提示點重算"
                  : "請先選一個提示點"
              }
              onClick={() => {
                if (!selectedPrompt?.point_id) return;
                const promptId = selectedPrompt.point_id;
                void withSnap((current) =>
                  client.sessionsDeletePrompt(current.protocol_session_id, current.revision, promptId),
                );
              }}
            >
              刪除選取點
            </button>
          </div>
        ) : null}
            <button
              type="button"
              className="btn edit-btn"
              data-testid="move-prompt"
              disabled={!selectedPrompt?.point_id || !snapshot?.controls.refine || !client.sessionsUpdatePrompt}
              onClick={() => {
                setPromptMoveMode(true);
                setTool("prompt-select");
              }}
            >
              移動提示點
            </button>
            <button
              type="button"
              className="btn edit-btn"
              data-testid="relabel-prompt-foreground"
              disabled={!selectedPrompt?.point_id || !client.sessionsUpdatePrompt}
              onClick={() => {
                if (!selectedPrompt?.point_id || !client.sessionsUpdatePrompt) return;
                void withSnap((current) =>
                  client.sessionsUpdatePrompt!(current.protocol_session_id, current.revision, selectedPrompt.point_id!, undefined, undefined, 1),
                );
              }}
            >
              設為前景
            </button>
            <button
              type="button"
              className="btn edit-btn"
              data-testid="relabel-prompt-background"
              disabled={!selectedPrompt?.point_id || !client.sessionsUpdatePrompt}
              onClick={() => {
                if (!selectedPrompt?.point_id || !client.sessionsUpdatePrompt) return;
                void withSnap((current) =>
                  client.sessionsUpdatePrompt!(current.protocol_session_id, current.revision, selectedPrompt.point_id!, undefined, undefined, 0),
                );
              }}
            >
              設為背景
            </button>
        <div className="region-work-panel" data-testid="region-work-panel">
          <div className="section-label">區塊工作</div>
          <p className="tool-explanation">
            已鎖定 {frozenRegions.length} 個區塊
            {snapshot?.pass_index ? ` · 第 ${snapshot.pass_index} 輪` : ""}
          </p>
          {frozenRegions.length > 0 ? (
            <p className="tool-explanation" data-testid="region-repair-hint">
              中間有小缺陷時，先用「補選」點一下缺口，或用 1px／3px 筆刷補上；要移除多選區則用「排除」或擦除。完成多個區塊後按「合併區塊」，就能當成一層繼續編輯。
            </p>
          ) : null}
          {frozenRegions.length > 0 ? (
            <div className="frozen-region-dropbox" data-testid="frozen-region-dropbox">
              <label htmlFor="frozen-region-select">已鎖定區塊（可選取解鎖）</label>
              <select
                id="frozen-region-select"
                data-testid="frozen-region-select"
                value={selectedFrozenRegionId ?? ""}
                onChange={(event) => setSelectedFrozenRegionId(event.target.value || null)}
                disabled={!snapshot?.controls.unlock_region}
              >
                {frozenRegions.map((region, index) => {
                  const pixels = region.area ?? region.pixel_count;
                  const label = region.label === 0 ? "排除" : "前景";
                  return (
                    <option key={region.region_id} value={region.region_id}>
                      {`區塊 ${index + 1} · ${label}${pixels != null ? ` · ${pixels}px` : ""}`}
                    </option>
                  );
                })}
              </select>
              <span className="muted-line">選取後按「解除選取區塊」，只會解鎖該區塊。</span>
            </div>
          ) : null}
          <div className="edit-row region-work-actions">
            <button
              type="button"
              className="btn edit-btn"
              data-testid="lock-region"
              disabled={!snapshot?.controls.lock_region}
              title="選取後到畫布點一下要保護的粉紅區塊"
              onClick={() => setTool("lock-region")}
            >
              鎖定區塊
            </button>
            <button
              type="button"
              className="btn edit-btn"
              data-testid="unlock-region"
              disabled={!snapshot?.controls.unlock_region || !selectedFrozenRegionId}
              onClick={() => {
                const regionId = selectedFrozenRegionId;
                if (!regionId) return;
                void withSnap((current) =>
                  client.sessionsUnlockRegion(current.protocol_session_id, current.revision, regionId),
                );
              }}
            >
              解除選取區塊
            </button>
            <button
              type="button"
              className="btn edit-btn merge-regions"
              data-testid="merge-regions"
              disabled={!snapshot?.controls.merge_regions}
              title="將所有已鎖定的前景區塊合併成目前可編輯遮罩；排除區塊仍會保留鎖定"
              onClick={() => {
                void withSnap((current) =>
                  client.sessionsEdit(current.protocol_session_id, current.revision, "merge"),
                );
              }}
            >
              合併區塊
            </button>
            <button
              type="button"
              className="btn edit-btn"
              data-testid="next-region"
              disabled={!snapshot?.controls.next_region}
              onClick={() => {
                void withSnap((current) =>
                  client.sessionsStartNextRegion(current.protocol_session_id, current.revision),
                ).then(() => setTool("roi"));
              }}
            >
              新增下一區
            </button>
          </div>
        </div>
        {visibleWarnings.length > 0 ? (
          <div>
            <div className="section-label">提醒</div>
            <ul data-testid="session-warnings" className="warning-list">
              {visibleWarnings.map((warning) => (
                <li key={warning.code} className="warn-chip">
                  {warningMessageZh(warning)}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div>
          <div className="section-label">微調</div>
          <div className="edit-row">
            <button
              data-testid="edit-shrink"
              className="btn edit-btn"
              disabled={!snapshot?.controls.local_edit}
              onClick={() =>
                void withSnap((current) =>
                  client.sessionsEdit(current.protocol_session_id, current.revision, "shrink"),
                )
              }
            >
              收縮
            </button>
            <button
              data-testid="edit-grow"
              className="btn edit-btn"
              disabled={!snapshot?.controls.local_edit}
              onClick={() =>
                void withSnap((current) =>
                  client.sessionsEdit(current.protocol_session_id, current.revision, "grow"),
                )
              }
            >
              擴張
            </button>
            <button
              data-testid="edit-fill"
              className="btn edit-btn"
              disabled={!snapshot?.controls.local_edit}
              onClick={() =>
                void withSnap((current) =>
                  client.sessionsEdit(current.protocol_session_id, current.revision, "fill_holes"),
                )
              }
            >
              填洞
            </button>
            <button
              data-testid="expand-roi"
              className="btn edit-btn"
              disabled={!snapshot?.controls.roi}
              onClick={() =>
                void withSnap((current) =>
                  client.sessionsExpandRoi(current.protocol_session_id, current.revision),
                )
              }
            >
              擴大框
            </button>
            <button
              data-testid="undo"
              className="btn edit-btn"
              disabled={!snapshot || (snapshot.history ? !snapshot.history.can_undo : false)}
              onClick={() =>
                void withSnap((current) =>
                  client.sessionsUndo(current.protocol_session_id, current.revision),
                )
              }
            >
              復原
            </button>
            <button
              data-testid="redo"
              className="btn edit-btn"
              disabled={!snapshot?.history?.can_redo || !client.sessionsRedo}
              onClick={() =>
                void withSnap((current) =>
                  client.sessionsRedo
                    ? client.sessionsRedo(current.protocol_session_id, current.revision)
                    : Promise.resolve(current),
                )
              }
            >
              重做
            </button>
            <details data-testid="operation-history" className="operation-history">
              <summary>操作記錄（{snapshot?.history?.operations.length ?? 0}）</summary>
              <ol>
                {(snapshot?.history?.operations ?? []).slice(-12).map((operation, index) => {
                  const parameters = operation.parameters ?? {};
                  const affected = parameters.point_id
                    ? `提示點 ${String(parameters.point_id)}`
                    : parameters.region_id
                      ? `區塊 ${String(parameters.region_id)}`
                      : parameters.region_ids
                        ? `區塊 ${String((parameters.region_ids as unknown[]).length)} 個`
                        : "整體遮罩";
                  const stateLabel = operation.status === "undone" ? "已復原" : operation.status === "unavailable" ? "不可用" : "目前";
                  return (
                    <li key={`${operation.sequence ?? index}-${operation.kind ?? "operation"}`}>
                      <span>{operation.kind ?? "operation"}</span>
                      <span className="muted-line"> · {affected} · 修訂 {operation.revision ?? snapshot?.revision ?? 0} · {stateLabel}</span>
                    </li>
                  );
                })}
              </ol>
            </details>
            <button
              data-testid="run-qa"
              className="btn edit-btn"
              disabled={!snapshot || !client.sessionsQa}
              onClick={() => {
                if (!snapshot || !client.sessionsQa) return;
                void client.sessionsQa(snapshot.protocol_session_id).then((result) => setQaResult(result));
              }}
            >
              執行品質檢查
            </button>
            {qaResult?.issues?.length ? (
              <ul data-testid="qa-issues" className="warning-list">
                {qaResult.issues.map((issue) => (
                  <li key={`${issue.code}-${issue.bbox?.join(",")}`}>
                    <button
                      type="button"
                      className="qa-issue-link"
                      onClick={() => issue.bbox && issue.bbox.length === 4 && frameRoi([issue.bbox[0], issue.bbox[1], issue.bbox[2], issue.bbox[3]])}
                    >
                      {issue.message}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            <button
              data-testid="labelme-preview"
              className="btn edit-btn"
              disabled={!snapshot || !client.labelmePreview}
              onClick={previewLabelMe}
            >
              LabelMe 預覽
            </button>
            <button
              data-testid="labelme-export"
              className="btn edit-btn"
              disabled={!snapshot || !client.labelmeExport}
              onClick={() => void exportLabelMe()}
            >
              匯出 LabelMe
            </button>
            <label className="btn" data-testid="labelme-import">
              匯入 LabelMe
              <input
                type="file"
                accept="application/json,.json"
                hidden
                data-testid="labelme-import-input"
                disabled={!snapshot || !client.labelmeImport}
                onChange={(event) => {
                  void importLabelMeFile(event.currentTarget.files?.[0]);
                  event.currentTarget.value = "";
                }}
              />
            </label>
            {snapshot?.draft?.dirty ? (
              <label className="muted-line">
                <input
                  type="checkbox"
                  data-testid="labelme-replace-draft"
                  checked={labelmeReplaceDraft}
                  onChange={(event) => setLabelmeReplaceDraft(event.target.checked)}
                />
                匯入時取代未儲存草稿
              </label>
            ) : null}
            {labelmePreview ? (
              <output data-testid="labelme-preview-result" className="muted-line">
                {`label=${String(labelmePreview.label ?? "Defect")} · components=${String(labelmePreview.component_count ?? 0)} · polygons=${String(labelmePreview.polygon_count ?? 0)}`}
              </output>
            ) : null}
            {labelmePreview && Number(labelmePreview.area_delta_fraction ?? 0) > 0.02 ? (
              <button
                type="button"
                className={labelmeCleanupAcknowledged ? "btn active" : "btn review"}
                data-testid="labelme-ack-cleanup"
                onClick={() => setLabelmeCleanupAcknowledged((value) => !value)}
              >
                {labelmeCleanupAcknowledged ? "已確認清理差異" : "確認清理差異後輸出"}
              </button>
            ) : null}
          </div>
        </div>
        <div className="commit-block">
          <div className="section-label">儲存</div>
          <p className="commit-hint" data-testid="save-hint">
            {!snapshot?.controls.accept
              ? "先畫框，再點選項 1/2/3。影像上會出現儲存按鈕。"
              : outputDisplayName
                ? `儲存會把 PNG 寫入 ${outputDisplayName}。`
                : "點儲存後會跳出資料夾視窗，PNG 寫進那個資料夾。"}
          </p>
          {!snapshot?.controls.accept ? (
            <p className="commit-hint" data-testid="accept-blocked-reason">
              還沒選遮罩選項，不能儲存。
            </p>
          ) : null}
          <button
            data-testid="accept"
            className="btn accept"
            title="空白鍵只儲存，Enter 儲存並下一張"
            disabled={!snapshot?.controls.accept || engine !== "ready"}
            onClick={() => acceptCurrent(false)}
          >
            儲存遮罩
          </button>
          <button
            data-testid="needs-review"
            className="btn review"
            title="遮罩不確定時用，不會當成已完成標註"
            disabled={!snapshot?.controls.needs_review || engine !== "ready"}
            onClick={needsReviewCurrent}
          >
            待覆核
          </button>
          <button
            data-testid="next-image"
            className="btn"
            disabled={!snapshot?.controls.next || advancingItem}
            title={!snapshot?.controls.next ? "先儲存或待覆核" : undefined}
            onClick={openNextItem}
          >
            下一張
          </button>
          {!snapshot?.controls.next && snapshot ? (
            <p className="commit-hint" data-testid="next-blocked-reason">
              儲存或待覆核之後才能下一張。
            </p>
          ) : null}
          <p className="kbd-legend" data-testid="kbd-legend">
            點兩角建框 · 滾輪縮放 · Alt 拖移 · 1–3 選項 · 空白鍵儲存 · Enter 儲存並下一張 · Z 復原 · O 隱藏切割 · N 下一張
          </p>
        </div>
        </div>
      </section>
    </div>
  );
}
