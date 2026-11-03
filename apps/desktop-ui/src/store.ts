import { create } from "zustand";
import type { DatasetItemSummary, DatasetWorkItemStatus, Snapshot } from "./host";
import {
  CANVAS_VIEW_HEIGHT,
  CANVAS_VIEW_WIDTH,
  DEFAULT_VIEWPORT,
  actualSizeViewport,
  fitContainViewport,
  viewportForRoi,
  type Rect,
  type ViewSize,
  type Viewport,
} from "./coordinates";

export type Tool =
  | "roi"
  | "edit-region"
  | "point"
  | "point-remove"
  | "prompt-select"
  | "brush"
  | "erase"
  | "lock-region"
  | "pan";
/** Stable fallback category used when a dataset has no manifest class_id. */
export const DEFAULT_CLASS_ID = "Defect";
/** Supported brush diameters: 1 px pencil, 3 px brush, and 5 px brush. */
export const BRUSH_RADII = [0, 1, 2] as const;
export type ViewIntent = "fit" | "roi" | "free";

type ViewState = {
  snapshot: Snapshot | null;
  viewport: Viewport;
  viewSize: ViewSize;
  viewIntent: ViewIntent;
  tool: Tool;
  engine: "ready" | "engine_unavailable" | "recovering";
  grantId: string | null;
  datasetId: string | null;
  datasetItemCount: number | null;
  outputGrantId: string | null;
  outputDisplayName: string | null;
  items: DatasetItemSummary[];
  currentItemId: string | null;
  uiError: string | null;
  reuseLastRoi: boolean;
  dinoPrototype: boolean;
  railCollapsed: boolean;
  inspectorCollapsed: boolean;
  brushRadius: number;
  selectedPromptId: string | null;
  applySnapshot: (snap: Snapshot) => void;
  setTool: (tool: Tool) => void;
  setEngine: (engine: ViewState["engine"]) => void;
  setViewport: (viewport: Viewport) => void;
  setViewMetrics: (viewSize: ViewSize, dpr: number) => void;
  fitImage: (imageWidth: number, imageHeight: number) => void;
  frameRoi: (roi: Rect) => void;
  actualSize: (imageWidth: number, imageHeight: number) => void;
  setDataset: (grantId: string, datasetId: string, items: DatasetItemSummary[], itemCount: number) => void;
  appendDatasetItems: (items: DatasetItemSummary[]) => void;
  refreshDatasetItemStatuses: (items: DatasetWorkItemStatus[]) => void;
  setOutputGrant: (grantId: string | null, displayName: string | null) => void;
  beginItem: (itemId: string) => void;
  setCurrentItemId: (itemId: string | null) => void;
  setUiError: (message: string | null) => void;
  setReuseLastRoi: (value: boolean) => void;
  setDinoPrototype: (value: boolean) => void;
  setRailCollapsed: (value: boolean) => void;
  setInspectorCollapsed: (value: boolean) => void;
  setBrushRadius: (value: number) => void;
  setSelectedPromptId: (value: string | null) => void;
};

function withDpr(viewport: Viewport, dpr: number): Viewport {
  return { ...viewport, dpr };
}

export const useViewStore = create<ViewState>((set) => ({
  snapshot: null,
  viewport: DEFAULT_VIEWPORT,
  viewSize: { width: CANVAS_VIEW_WIDTH, height: CANVAS_VIEW_HEIGHT },
  viewIntent: "fit",
  tool: "roi",
  engine: "ready",
  grantId: null,
  datasetId: null,
  datasetItemCount: null,
  outputGrantId: null,
  outputDisplayName: null,
  items: [],
  currentItemId: null,
  uiError: null,
  reuseLastRoi: false,
  dinoPrototype: false,
  railCollapsed: false,
  inspectorCollapsed: false,
  // Radius 0 is the default one-pixel pencil (diameter = 2 * radius + 1).
  brushRadius: 0,
  selectedPromptId: null,
  applySnapshot: (snapshot) =>
    set((state) => {
      const points = snapshot.prompt_points ??
        snapshot.candidates.find((candidate) => candidate.candidate_id === snapshot.selected_candidate_id)
          ?.prompt_points ?? [];
      const selectedPromptStillExists = points.some(
        (point, index) => (point.point_id ?? `prompt-${index}`) === state.selectedPromptId,
      );
      return {
        snapshot: {
          ...snapshot,
          persist: snapshot.persist
            ? {
                kind: snapshot.persist.kind,
                training_eligible: snapshot.persist.training_eligible,
              }
            : undefined,
        },
        selectedPromptId: selectedPromptStillExists ? state.selectedPromptId : null,
      };
    }),
  setTool: (tool) => set({ tool }),
  setEngine: (engine) => set({ engine }),
  setViewport: (viewport) => set((state) => ({ viewport: withDpr(viewport, state.viewport.dpr), viewIntent: "free" })),
  setViewMetrics: (viewSize, dpr) =>
    set((state) => ({
      viewSize,
      viewport: state.viewport.dpr === dpr ? state.viewport : { ...state.viewport, dpr },
    })),
  fitImage: (imageWidth, imageHeight) =>
    set((state) => ({
      viewIntent: "fit",
      viewport: withDpr(
        fitContainViewport(imageWidth, imageHeight, state.viewSize.width, state.viewSize.height),
        state.viewport.dpr,
      ),
    })),
  frameRoi: (roi) =>
    set((state) => ({
      viewIntent: "roi",
      viewport: withDpr(
        viewportForRoi(roi, state.viewSize.width, state.viewSize.height),
        state.viewport.dpr,
      ),
    })),
  actualSize: (imageWidth, imageHeight) =>
    set((state) => ({
      viewIntent: "free",
      viewport: withDpr(
        actualSizeViewport(imageWidth, imageHeight, state.viewSize.width, state.viewSize.height),
        state.viewport.dpr,
      ),
    })),
  setDataset: (grantId, datasetId, items, datasetItemCount) =>
    set({ grantId, datasetId, datasetItemCount, items, currentItemId: null, snapshot: null }),
  appendDatasetItems: (items) =>
    set((state) => {
      const seen = new Set(state.items.map((item) => item.item_id));
      const additions = items.filter((item) => {
        if (seen.has(item.item_id)) return false;
        seen.add(item.item_id);
        return true;
      });
      return additions.length > 0 ? { items: [...state.items, ...additions] } : state;
    }),
  refreshDatasetItemStatuses: (items) =>
    set((state) => {
      const statuses = new Map(items.map((item) => [item.item_id, item.status]));
      return {
        items: state.items.map((item) => {
          const status = statuses.get(item.item_id);
          return status ? { ...item, status } : item;
        }),
      };
    }),
  setOutputGrant: (outputGrantId, outputDisplayName) => set({ outputGrantId, outputDisplayName }),
  beginItem: (currentItemId) => set({ currentItemId, snapshot: null }),
  setCurrentItemId: (currentItemId) => set({ currentItemId }),
  setUiError: (uiError) => set({ uiError }),
  setReuseLastRoi: (reuseLastRoi) => set({ reuseLastRoi }),
  setDinoPrototype: (dinoPrototype) => set({ dinoPrototype }),
  setRailCollapsed: (railCollapsed) => set({ railCollapsed }),
  setInspectorCollapsed: (inspectorCollapsed) => set({ inspectorCollapsed }),
  setBrushRadius: (brushRadius) => set({ brushRadius: Math.max(0, Math.min(32, Math.round(brushRadius))) }),
  setSelectedPromptId: (selectedPromptId) => set({ selectedPromptId }),
}));
