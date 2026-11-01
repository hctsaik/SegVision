import { useEffect, useRef, useState } from "react";
import {
  cssToImage,
  imageToCss,
  panViewport,
  preserveViewCenter,
  zoomViewportAt,
  ZOOM_STEP,
  type Rect,
  type Viewport,
} from "./coordinates";
import { regionBadge, type ComputePhase } from "./region";
import { BRUSH_RADII, useViewStore, type Tool } from "./store";

const OVERLAY_FILL = "rgba(255, 32, 160, 0.22)";
const OVERLAY_RGB: readonly [number, number, number] = [255, 32, 160];
const OVERLAY_FILL_A = 18;
const OVERLAY_EDGE_A = 235;
const MIN_STAGE = 32;

type ImageSize = { width: number; height: number };
export type ImagePoint = { x: number; y: number };
export type TwoPointCorner = "first" | "opposite";

/** Build a half-open XYXY rectangle from two opposite image pixels. */
export function rectFromCorners(first: ImagePoint, opposite: ImagePoint): Rect {
  return [
    Math.min(first.x, opposite.x),
    Math.min(first.y, opposite.y),
    Math.max(first.x, opposite.x) + 1,
    Math.max(first.y, opposite.y) + 1,
  ];
}

/** Return the closer corner that a completed two-point box should update. */
export function nearestTwoPointCorner(
  point: ImagePoint,
  first: ImagePoint,
  opposite: ImagePoint,
): TwoPointCorner {
  const firstDistance = Math.hypot(point.x - first.x, point.y - first.y);
  const oppositeDistance = Math.hypot(point.x - opposite.x, point.y - opposite.y);
  return firstDistance <= oppositeDistance ? "first" : "opposite";
}

export function pointLabelForInput(tool: Tool, button: number): 0 | 1 {
  return tool === "point-remove" || button === 2 ? 0 : 1;
}

function drawMaskOverlay(
  ctx: CanvasRenderingContext2D,
  mask: HTMLImageElement,
  x: number,
  y: number,
  width: number,
  height: number,
  rgb: readonly [number, number, number] = OVERLAY_RGB,
  fillAlpha = OVERLAY_FILL_A,
  edgeAlpha = OVERLAY_EDGE_A,
) {
  const layer = document.createElement("canvas");
  layer.width = mask.naturalWidth;
  layer.height = mask.naturalHeight;
  const layerCtx = layer.getContext("2d", { willReadFrequently: true });
  if (!layerCtx) return;
  layerCtx.drawImage(mask, 0, 0);
  const pixels = layerCtx.getImageData(0, 0, layer.width, layer.height);
  const { data } = pixels;
  const w = layer.width;
  const h = layer.height;
  const covered = new Uint8Array(w * h);
  for (let p = 0, offset = 0; offset < data.length; p += 1, offset += 4) {
    covered[p] = data[offset] > 24 && data[offset + 3] > 24 ? 1 : 0;
  }
  for (let yPix = 0; yPix < h; yPix += 1) {
    for (let xPix = 0; xPix < w; xPix += 1) {
      const p = yPix * w + xPix;
      const offset = p * 4;
      if (!covered[p]) {
        data[offset + 3] = 0;
        continue;
      }
      const edge =
        xPix === 0 ||
        yPix === 0 ||
        xPix === w - 1 ||
        yPix === h - 1 ||
        !covered[p - 1] ||
        !covered[p + 1] ||
        !covered[p - w] ||
        !covered[p + w];
      data[offset] = rgb[0];
      data[offset + 1] = rgb[1];
      data[offset + 2] = rgb[2];
      data[offset + 3] = edge ? edgeAlpha : fillAlpha;
    }
  }
  layerCtx.putImageData(pixels, 0, 0);
  ctx.drawImage(layer, x, y, width, height);
}

function drawStrokePreview(
  ctx: CanvasRenderingContext2D,
  points: number[][],
  viewport: Viewport,
  radius: number,
  color: string,
) {
  if (points.length === 0) return;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = Math.max(2, (radius * 2 + 1) * viewport.zoom);
  ctx.beginPath();
  points.forEach((point, index) => {
    if (!point) return;
    const css = imageToCss(point[0] ?? 0, point[1] ?? 0, viewport);
    const x = css.x + 0.5 * viewport.zoom;
    const y = css.y + 0.5 * viewport.zoom;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.restore();
}

function drawPromptPoint(
  ctx: CanvasRenderingContext2D,
  point: { x: number; y: number; label: 0 | 1 },
  viewport: Viewport,
  selected = false,
) {
  const css = imageToCss(point.x, point.y, viewport);
  const x = css.x + 0.5 * viewport.zoom;
  const y = css.y + 0.5 * viewport.zoom;
  const radius = 7;
  ctx.save();
  if (selected) {
    ctx.beginPath();
    ctx.arc(x, y, radius + 4, 0, Math.PI * 2);
    ctx.strokeStyle = "#ffd43b";
    ctx.lineWidth = 3;
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fillStyle = point.label === 1 ? "#20a05a" : "#d83b3b";
  ctx.fill();
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x - 3.5, y);
  ctx.lineTo(x + 3.5, y);
  if (point.label === 1) {
    ctx.moveTo(x, y - 3.5);
    ctx.lineTo(x, y + 3.5);
  }
  ctx.stroke();
  ctx.restore();
}

function strokeRect(
  ctx: CanvasRenderingContext2D,
  rect: Rect,
  viewport: { zoom: number; panX: number; panY: number },
  color: string,
  dashed = false,
) {
  ctx.save();
  if (dashed) ctx.setLineDash([5, 4]);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(
    rect[0] * viewport.zoom + viewport.panX,
    rect[1] * viewport.zoom + viewport.panY,
    (rect[2] - rect[0]) * viewport.zoom,
    (rect[3] - rect[1]) * viewport.zoom,
  );
  ctx.restore();
}

function dimOutsideRegion(
  ctx: CanvasRenderingContext2D,
  rect: Rect,
  viewport: Viewport,
  viewW: number,
  viewH: number,
) {
  const x = rect[0] * viewport.zoom + viewport.panX;
  const y = rect[1] * viewport.zoom + viewport.panY;
  const width = (rect[2] - rect[0]) * viewport.zoom;
  const height = (rect[3] - rect[1]) * viewport.zoom;
  ctx.save();
  ctx.fillStyle = "rgba(28, 36, 48, 0.22)";
  ctx.beginPath();
  ctx.rect(0, 0, viewW, viewH);
  ctx.rect(x, y, Math.max(1, width), Math.max(1, height));
  ctx.fill("evenodd");
  ctx.restore();
}

export function AnnotationCanvas(props: {
  imageUrl?: string | null;
  maskUrl?: string | null;
  lockedForegroundUrl?: string | null;
  lockedBackgroundUrl?: string | null;
  computePhase?: ComputePhase;
  statusText?: string;
  onRoi: (rect: [number, number, number, number]) => void;
  onPoint: (x: number, y: number, label: number) => void;
  onStroke: (points: number[][], erase: boolean, editRegion?: Rect | null) => void;
  onLockRegion?: (x: number, y: number) => void;
  onReturnToSam?: () => void;
  promptMoveMode?: boolean;
  onPromptMove?: (pointId: string, x: number, y: number) => void;
  onPromptMoveDone?: () => void;
  onAssetError?: (message: string) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayRef = useRef<HTMLCanvasElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const minimapRef = useRef<HTMLCanvasElement | null>(null);
  const drag = useRef<{ x: number; y: number } | null>(null);
  const pan = useRef<{ x: number; y: number } | null>(null);
  const stroke = useRef<number[][]>([]);
  const activePointerId = useRef<number | null>(null);
  const imageSizeRef = useRef<ImageSize | null>(null);
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [mask, setMask] = useState<HTMLImageElement | null>(null);
  const [lockedForeground, setLockedForeground] = useState<HTMLImageElement | null>(null);
  const [lockedBackground, setLockedBackground] = useState<HTMLImageElement | null>(null);
  const [imageSize, setImageSize] = useState<ImageSize | null>(null);
  const [panning, setPanning] = useState(false);
  const [altHeld, setAltHeld] = useState(false);
  const [hover, setHover] = useState<{ x: number; y: number } | null>(null);
  const [twoPointFirst, setTwoPointFirst] = useState<ImagePoint | null>(null);
  const [twoPointOpposite, setTwoPointOpposite] = useState<ImagePoint | null>(null);
  const [editRegion, setEditRegion] = useState<Rect | null>(null);
  const [editRegionDraft, setEditRegionDraft] = useState<Rect | null>(null);
  const visibleEditRegion = editRegionDraft ?? editRegion;
  const [draftStroke, setDraftStroke] = useState<number[][]>([]);
  const [maskVisible, setMaskVisible] = useState(true);
  const [boxTip, setBoxTip] = useState<string | null>(null);
  const [pendingLock, setPendingLock] = useState<{ x: number; y: number } | null>(null);
  const snapshot = useViewStore((s) => s.snapshot);
  const viewport = useViewStore((s) => s.viewport);
  const viewSize = useViewStore((s) => s.viewSize);
  const tool = useViewStore((s) => s.tool);
  const setTool = useViewStore((s) => s.setTool);
  const brushRadius = useViewStore((s) => s.brushRadius);
  const selectedPromptId = useViewStore((s) => s.selectedPromptId);
  const setSelectedPromptId = useViewStore((s) => s.setSelectedPromptId);
  const setBrushRadius = useViewStore((s) => s.setBrushRadius);
  const setViewport = useViewStore((s) => s.setViewport);
  const fitImage = useViewStore((s) => s.fitImage);
  const frameRoi = useViewStore((s) => s.frameRoi);
  const actualSize = useViewStore((s) => s.actualSize);
  imageSizeRef.current = imageSize;

  useEffect(() => {
    if (tool !== "lock-region") setPendingLock(null);
  }, [tool]);

  useEffect(() => {
    // A pending corner belongs to one image/session and must never leak into
    // the next dataset item.
    setTwoPointFirst(null);
    setTwoPointOpposite(null);
    setEditRegion(null);
    setEditRegionDraft(null);
    setBoxTip(null);
  }, [snapshot?.protocol_session_id]);

  function fitFullImage(size?: ImageSize | null) {
    const next = size ?? imageSizeRef.current;
    if (!next || next.width <= 0 || next.height <= 0) return;
    fitImage(next.width, next.height);
  }

  function frameCurrentRoi() {
    const roi = useViewStore.getState().snapshot?.user_roi_full;
    if (!roi || roi.length !== 4) return;
    frameRoi([roi[0], roi[1], roi[2], roi[3]]);
  }

  function viewportAfterImageLoad(size: ImageSize) {
    const roi = useViewStore.getState().snapshot?.user_roi_full;
    if (roi && roi.length === 4) {
      frameRoi([roi[0], roi[1], roi[2], roi[3]]);
      return;
    }
    fitFullImage(size);
  }

  function zoomAtCenter(factor: number) {
    const size = useViewStore.getState().viewSize;
    setViewport(zoomViewportAt(useViewStore.getState().viewport, size.width / 2, size.height / 2, factor));
  }

  useEffect(() => {
    setImage(null);
    setImageSize(null);
    if (!props.imageUrl) {
      return;
    }
    let active = true;
    const next = new Image();
    if (props.imageUrl.startsWith("http")) next.crossOrigin = "anonymous";
    const loaded = () => {
      if (!active || next.naturalWidth <= 0 || next.naturalHeight <= 0) return;
      const size = { width: next.naturalWidth, height: next.naturalHeight };
      setImage(next);
      setImageSize(size);
      viewportAfterImageLoad(size);
      props.onAssetError?.("");
    };
    const failed = () => {
      if (!active) return;
      setImage(null);
      setImageSize(null);
      props.onAssetError?.("無法載入影像。");
    };
    next.addEventListener("load", loaded);
    next.addEventListener("error", failed);
    next.src = props.imageUrl;
    if (next.complete) loaded();
    return () => {
      active = false;
      next.removeEventListener("load", loaded);
      next.removeEventListener("error", failed);
    };
  }, [props.imageUrl, props.onAssetError]);

  useEffect(() => {
    setMask(null);
    if (!props.maskUrl) {
      return;
    }
    let active = true;
    const next = new Image();
    if (props.maskUrl.startsWith("http")) next.crossOrigin = "anonymous";
    const loaded = () => {
      if (active && next.naturalWidth > 0 && next.naturalHeight > 0) setMask(next);
    };
    const failed = () => {
      if (!active) return;
      setMask(null);
      props.onAssetError?.("無法載入遮罩。");
    };
    next.addEventListener("load", loaded);
    next.addEventListener("error", failed);
    next.src = props.maskUrl;
    if (next.complete) loaded();
    return () => {
      active = false;
      next.removeEventListener("load", loaded);
      next.removeEventListener("error", failed);
    };
  }, [props.maskUrl, props.onAssetError]);

  useEffect(() => {
    let active = true;
    setLockedForeground(null);
    if (!props.lockedForegroundUrl) return () => undefined;
    const next = new Image();
    if (props.lockedForegroundUrl.startsWith("http")) next.crossOrigin = "anonymous";
    next.onload = () => {
      if (active && next.naturalWidth > 0 && next.naturalHeight > 0) setLockedForeground(next);
    };
    next.src = props.lockedForegroundUrl;
    return () => {
      active = false;
      next.onload = null;
    };
  }, [props.lockedForegroundUrl]);

  useEffect(() => {
    let active = true;
    setLockedBackground(null);
    if (!props.lockedBackgroundUrl) return () => undefined;
    const next = new Image();
    if (props.lockedBackgroundUrl.startsWith("http")) next.crossOrigin = "anonymous";
    next.onload = () => {
      if (active && next.naturalWidth > 0 && next.naturalHeight > 0) setLockedBackground(next);
    };
    next.src = props.lockedBackgroundUrl;
    return () => {
      active = false;
      next.onload = null;
    };
  }, [props.lockedBackgroundUrl]);

  useEffect(() => {
    const stage = stageRef.current;
    const canvas = canvasRef.current;
    if (!stage || !canvas) return;

    const applyStageSize = (width: number, height: number) => {
      const cssW = Math.max(1, Math.round(width));
      const cssH = Math.max(1, Math.round(height));
      if (cssW < MIN_STAGE || cssH < MIN_STAGE) return;
      const dpr = Math.min(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1, 2);
      const state = useViewStore.getState();
      const prev = state.viewSize;
      const bufferW = Math.max(1, Math.round(cssW * dpr));
      const bufferH = Math.max(1, Math.round(cssH * dpr));
      if (canvas.width !== bufferW) canvas.width = bufferW;
      if (canvas.height !== bufferH) canvas.height = bufferH;
      const sizeChanged = prev.width !== cssW || prev.height !== cssH;
      state.setViewMetrics({ width: cssW, height: cssH }, dpr);
      if (!sizeChanged) return;
      const img = imageSizeRef.current;
      if (!img) return;
      if (state.viewIntent === "fit") {
        state.fitImage(img.width, img.height);
      } else if (state.viewIntent === "roi") {
        const roi = state.snapshot?.user_roi_full;
        if (roi && roi.length === 4) state.frameRoi([roi[0], roi[1], roi[2], roi[3]]);
        else {
          state.setViewport(preserveViewCenter(state.viewport, prev, { width: cssW, height: cssH }));
        }
      } else {
        state.setViewport(preserveViewCenter(state.viewport, prev, { width: cssW, height: cssH }));
      }
    };

    applyStageSize(stage.clientWidth, stage.clientHeight);
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      applyStageSize(entry.contentRect.width, entry.contentRect.height);
    });
    observer.observe(stage);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = viewport.dpr || 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = "#d8dee6";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#e7ecf1";
    ctx.fillRect(0, 0, viewSize.width, viewSize.height);
    ctx.imageSmoothingEnabled = viewport.zoom < 1.5;
    ctx.imageSmoothingQuality = viewport.zoom < 1.5 ? "high" : "low";
    if (image && imageSize) {
      ctx.drawImage(
        image,
        viewport.panX,
        viewport.panY,
        imageSize.width * viewport.zoom,
        imageSize.height * viewport.zoom,
      );
    }
    if (mask && imageSize && maskVisible) {
      const crop = snapshot?.crop_rect_full;
      const isCropMask =
        crop && (mask.naturalWidth !== imageSize.width || mask.naturalHeight !== imageSize.height);
      const maskX = isCropMask ? crop[0] : 0;
      const maskY = isCropMask ? crop[1] : 0;
      const maskWidth = isCropMask ? crop[2] - crop[0] : imageSize.width;
      const maskHeight = isCropMask ? crop[3] - crop[1] : imageSize.height;
      try {
        drawMaskOverlay(
          ctx,
          mask,
          maskX * viewport.zoom + viewport.panX,
          maskY * viewport.zoom + viewport.panY,
          maskWidth * viewport.zoom,
          maskHeight * viewport.zoom,
        );
      } catch {
        props.onAssetError?.("無法合成遮罩圖層。");
      }
    }
    if (lockedForeground && imageSize && maskVisible) {
      try {
        drawMaskOverlay(
          ctx,
          lockedForeground,
          viewport.panX,
          viewport.panY,
          imageSize.width * viewport.zoom,
          imageSize.height * viewport.zoom,
          [22, 150, 116],
          42,
          245,
        );
      } catch {
        props.onAssetError?.("無法顯示鎖定區塊。");
      }
    }
    if (lockedBackground && imageSize && maskVisible) {
      try {
        drawMaskOverlay(
          ctx,
          lockedBackground,
          viewport.panX,
          viewport.panY,
          imageSize.width * viewport.zoom,
          imageSize.height * viewport.zoom,
          [82, 96, 112],
          18,
          210,
        );
      } catch {
        props.onAssetError?.("無法顯示鎖定背景區塊。");
      }
    }
    const crop = snapshot?.crop_rect_full;
    const roi = snapshot?.user_roi_full;
    const cropIsRoi =
      Boolean(crop && roi && crop[0] === roi[0] && crop[1] === roi[1] && crop[2] === roi[2] && crop[3] === roi[3]);
    if (crop && !cropIsRoi) strokeRect(ctx, [crop[0], crop[1], crop[2], crop[3]], viewport, "#3aa0d8", true);
  }, [image, imageSize, lockedBackground, lockedForeground, mask, maskVisible, props.onAssetError, snapshot, viewport, viewSize]);

  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    const ctx = overlay.getContext("2d");
    if (!ctx) return;
    const dpr = viewport.dpr || 1;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, overlay.width, overlay.height);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const focus = snapshot?.user_roi_full;
    if (focus && focus.length === 4) {
      dimOutsideRegion(ctx, [focus[0], focus[1], focus[2], focus[3]], viewport, viewSize.width, viewSize.height);
      strokeRect(
        ctx,
        [focus[0], focus[1], focus[2], focus[3]],
        viewport,
        snapshot?.prototype?.matched ? "#7c3aed" : "#e6b800",
        false,
      );
    }
    if (visibleEditRegion) {
      strokeRect(ctx, visibleEditRegion, viewport, "#149447", true);
    }
    const selected = snapshot?.candidates.find(
      (candidate) => candidate.candidate_id === snapshot.selected_candidate_id,
    );
    const promptPoints = snapshot?.prompt_points ?? selected?.prompt_points ?? [];
    promptPoints.forEach((point, index) => {
      drawPromptPoint(
        ctx,
        point,
        viewport,
        selectedPromptId === (point.point_id ?? `prompt-${index}`),
      );
    });
    if (draftStroke.length > 0) {
      drawStrokePreview(
        ctx,
        draftStroke,
        viewport,
        brushRadius,
        tool === "erase" ? "rgba(198, 40, 40, 0.7)" : "rgba(47, 111, 237, 0.7)",
      );
    }
  }, [brushRadius, draftStroke, selectedPromptId, snapshot, tool, viewport, viewSize, visibleEditRegion]);

  useEffect(() => {
    const mini = minimapRef.current;
    if (!mini || !image || !imageSize) return;
    const maxW = 168;
    const maxH = 120;
    const scale = Math.min(maxW / imageSize.width, maxH / imageSize.height);
    const w = Math.max(1, Math.round(imageSize.width * scale));
    const h = Math.max(1, Math.round(imageSize.height * scale));
    if (mini.width !== w) mini.width = w;
    if (mini.height !== h) mini.height = h;
    const ctx = mini.getContext("2d");
    if (!ctx) return;
    ctx.imageSmoothingEnabled = true;
    ctx.fillStyle = "#cfd6de";
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(image, 0, 0, w, h);
    const visX = -viewport.panX / viewport.zoom;
    const visY = -viewport.panY / viewport.zoom;
    const visW = viewSize.width / viewport.zoom;
    const visH = viewSize.height / viewport.zoom;
    ctx.strokeStyle = "#2f6fed";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(visX * scale, visY * scale, visW * scale, visH * scale);
  }, [image, imageSize, viewport, viewSize]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const factor = event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP;
      setViewport(
        zoomViewportAt(
          useViewStore.getState().viewport,
          event.clientX - rect.left,
          event.clientY - rect.top,
          factor,
        ),
      );
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => canvas.removeEventListener("wheel", onWheel);
  }, [setViewport]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Alt") setAltHeld(true);
      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement
      ) {
        return;
      }
      if (event.key === "0") {
        event.preventDefault();
        fitFullImage();
        return;
      }
      if (event.key === "9") {
        event.preventDefault();
        frameCurrentRoi();
        return;
      }
      if (event.key.toLowerCase() === "o") {
        event.preventDefault();
        setMaskVisible((value) => !value);
        return;
      }
      if (event.key.toLowerCase() === "h") {
        event.preventDefault();
        setTool("pan");
        return;
      }
      if (event.key.toLowerCase() === "e" && useViewStore.getState().snapshot?.controls.local_edit) {
        event.preventDefault();
        setTool("erase");
        return;
      }
      if (event.key === "+" || event.key === "=") {
        event.preventDefault();
        zoomAtCenter(ZOOM_STEP);
        return;
      }
      if (event.key === "-" || event.key === "_") {
        event.preventDefault();
        zoomAtCenter(1 / ZOOM_STEP);
      }
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.key === "Alt") setAltHeld(false);
    };
    const onBlur = () => setAltHeld(false);
    window.addEventListener("keydown", onKey);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onBlur);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
    };
  }, [actualSize, fitImage, frameRoi, setTool, setViewport]);

  function pointForEvent(e: React.PointerEvent<HTMLCanvasElement>) {
    if (!imageSize) return null;
    const rect = e.currentTarget.getBoundingClientRect();
    return cssToImage(
      e.clientX - rect.left,
      e.clientY - rect.top,
      viewport,
      imageSize.width,
      imageSize.height,
    );
  }

  function isPanGesture(e: React.PointerEvent<HTMLCanvasElement>) {
    return e.button === 1 || (e.button === 0 && (e.altKey || tool === "pan"));
  }

  function releasePointerCapture(e: React.PointerEvent<HTMLCanvasElement>) {
    if (
      typeof e.currentTarget.hasPointerCapture === "function" &&
      e.currentTarget.hasPointerCapture(e.pointerId) &&
      typeof e.currentTarget.releasePointerCapture === "function"
    ) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
    activePointerId.current = null;
  }

  function capturePointer(e: React.PointerEvent<HTMLCanvasElement>) {
    if (typeof e.currentTarget.setPointerCapture === "function") {
      e.currentTarget.setPointerCapture(e.pointerId);
    }
    activePointerId.current = e.pointerId;
  }

  const imageFits =
    !!imageSize &&
    imageSize.width * viewport.zoom <= viewSize.width + 1 &&
    imageSize.height * viewport.zoom <= viewSize.height + 1;
  const showMinimap = Boolean(image && imageSize && !imageFits);
  const hasRoi = Boolean(snapshot?.user_roi_full && snapshot.user_roi_full.length === 4);
  const selectedCandidate = snapshot?.candidates.find(
    (candidate) => candidate.candidate_id === snapshot.selected_candidate_id,
  );
  const promptPoints = snapshot?.prompt_points ?? selectedCandidate?.prompt_points ?? [];
  const samToolReason = snapshot?.controls.refine
    ? null
    : selectedCandidate?.source === "manual_edit" || selectedCandidate?.source === "manual_empty"
      ? "SAM 點選已暫停：你已進入手動畫筆模式。按「復原」回到 SAM 結果後，就能繼續加點或排除。"
      : selectedCandidate
        ? "目前選項不支援 SAM 加點；可改選 SAM 選項，或使用畫筆修補。"
        : "請先選擇一個 SAM 選項，才能使用補選或排除。";
  const cursor =
    panning || altHeld || tool === "pan"
      ? panning
        ? "grabbing"
        : "grab"
      : tool === "point" || tool === "point-remove"
        ? "cell"
        : tool === "brush" || tool === "erase"
          ? "none"
          : tool === "prompt-select" || tool === "lock-region"
            ? "pointer"
          : "crosshair";

  const overlayTools: Array<{
    id: Tool;
    label: string;
    testid: string;
    enabled: boolean;
    title?: string;
  }> = [
    {
      id: "roi",
      label: "框選",
      testid: "tool-roi",
      enabled: Boolean(snapshot?.controls.roi),
      title: "點第一個角，再點對角建立 SAM 搜尋範圍",
    },
    {
      id: "edit-region",
      label: "編輯範圍",
      testid: "tool-edit-region",
      // Work-area selection is independent from candidate/local-edit
      // availability.  It can be prepared as soon as the current session is
      // still editable; brush/erase remains gated by its own capability.
      enabled: Boolean(snapshot?.controls.roi),
      title: "點第一個角，再點對角；限制畫筆與擦除範圍",
    },
    {
      id: "point",
      label: "＋ 補選",
      testid: "tool-point",
      enabled: Boolean(snapshot?.controls.refine),
      title: "在漏選區域點一下；也可用滑鼠右鍵快速排除",
    },
    {
      id: "point-remove",
      label: "－ 排除",
      testid: "tool-point-remove",
      enabled: Boolean(snapshot?.controls.refine),
      title: "在誤選區域點一下，告訴 MobileSAM 這裡是背景",
    },
    {
      id: "prompt-select",
      label: "管理點位",
      testid: "tool-prompt-select",
      enabled: promptPoints.length > 0,
      title: "點選畫布上的綠色或紅色提示點，再到右側刪除",
    },
    {
      id: "brush",
      label: "畫筆",
      testid: "tool-brush",
      enabled: Boolean(snapshot?.controls.local_edit || editRegion),
      title: editRegion ? "在編輯範圍內畫筆修補" : undefined,
    },
    {
      id: "erase",
      label: "擦除",
      testid: "tool-erase",
      enabled: Boolean(snapshot?.controls.local_edit || editRegion),
      title: editRegion ? "在編輯範圍內擦除" : undefined,
    },
    {
      id: "lock-region",
      label: "鎖定區塊",
      testid: "tool-lock-region",
      enabled: Boolean(snapshot?.controls.lock_region && props.onLockRegion),
      title: "點一下已完成的粉紅區塊，保護它並繼續處理其他區域",
    },
    { id: "pan", label: "平移", testid: "tool-pan", enabled: Boolean(imageSize) },
  ];
  const focusRect = snapshot?.user_roi_full ?? null;
  const focusCss = focusRect ? imageToCss(focusRect[0], focusRect[1], viewport) : null;
  const computing = Boolean(props.computePhase && props.computePhase !== "idle");
  const badge = focusRect
    ? regionBadge({
        computePhase: props.computePhase ?? "idle",
        dinoMatched: Boolean(snapshot?.prototype?.matched),
        drafting: false,
      })
    : null;
  const pendingLockCss = pendingLock
    ? imageToCss(pendingLock.x, pendingLock.y, viewport)
    : null;


  return (
    <div className="viewer">
      <div className="viewer-chrome">
        <p className="viewer-hint" data-testid="region-status">
          {props.statusText ?? "在缺陷周圍點兩個角建立黃框。遮罩只會在這個框裡計算。"}
        </p>
        <div className="viewer-actions">
          <span data-testid="viewer-hover" className="viewer-hover">
            {hover ? `${hover.x}, ${hover.y}` : imageSize ? `${imageSize.width}×${imageSize.height}` : "–"}
          </span>
          <button
            type="button"
            className="btn viewer-fit"
            data-testid="viewer-zoom"
            title="實際像素 1:1"
            onClick={() => {
              if (!imageSize) return;
              actualSize(imageSize.width, imageSize.height);
            }}
            disabled={!imageSize}
          >
            {Math.round(viewport.zoom * 100)}%
          </button>
          <button
            type="button"
            className="btn viewer-fit"
            data-testid="viewer-zoom-out"
            onClick={() => zoomAtCenter(1 / ZOOM_STEP)}
            disabled={!imageSize}
          >
            −
          </button>
          <button
            type="button"
            className="btn viewer-fit"
            data-testid="viewer-zoom-in"
            onClick={() => zoomAtCenter(ZOOM_STEP)}
            disabled={!imageSize}
          >
            +
          </button>
          <button
            type="button"
            className="btn viewer-fit"
            data-testid="viewer-fit"
            title="讓整張圖符合視窗"
            onClick={() => fitFullImage()}
            disabled={!imageSize}
          >
            適應
          </button>
          <button
            type="button"
            className="btn viewer-fit"
            data-testid="viewer-frame-roi"
            title={hasRoi ? "把畫面縮放到黃框" : "先點兩個角建立黃框才能縮放"}
            onClick={frameCurrentRoi}
            disabled={!hasRoi}
          >
            縮放至黃框
          </button>
          <button
            type="button"
            className={maskVisible ? "btn viewer-fit active" : "btn viewer-fit"}
            data-testid="toggle-mask"
            title="顯示或隱藏切割結果（O）"
            onClick={() => setMaskVisible((value) => !value)}
            disabled={!mask}
          >
            {maskVisible ? "隱藏切割" : "顯示切割"}
          </button>
          {tool === "brush" || tool === "erase"
            ? BRUSH_RADII.map((radius) => (
                <button
                  key={radius}
                  type="button"
                  className={brushRadius === radius ? "btn viewer-fit active" : "btn viewer-fit"}
                  data-testid={`brush-radius-${radius}`}
                  onClick={() => setBrushRadius(radius)}
                  title={radius === 0 ? "單一像素鉛筆" : `筆刷半徑 ${radius}px`}
                >
                  {radius === 0 ? "1px 鉛筆" : `${radius * 2 + 1}px`}
                </button>
              ))
            : null}
        </div>
      </div>
      <div className="viewer-stage" ref={stageRef}>
        <div className="viewer-tools" role="toolbar" aria-label="Annotation tools">
          {overlayTools.map((item) => (
            <button
              key={item.id}
              type="button"
              data-testid={item.testid}
              className={tool === item.id ? "tool-chip active" : "tool-chip"}
              disabled={!item.enabled}
              title={item.title}
              aria-pressed={tool === item.id}
              onClick={() => {
                if (item.id === "roi" || item.id === "edit-region") {
                  // Clicking the mode button again starts a fresh pair of
                  // corners, which is also the escape hatch after a bad box.
                  setTwoPointFirst(null);
                  setTwoPointOpposite(null);
                  setEditRegion(null);
                  setEditRegionDraft(null);
                  setBoxTip(null);
                }
                setTool(item.id);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
        {samToolReason ? (
          <div className="viewer-tool-note" data-testid="sam-tool-reason">
            <span>{samToolReason}</span>
            {selectedCandidate?.source === "manual_edit" || selectedCandidate?.source === "manual_empty" ? (
              <button
                type="button"
                className="btn"
                data-testid="return-to-sam"
                onClick={() => props.onReturnToSam?.()}
              >
                回到 SAM 結果
              </button>
            ) : null}
          </div>
        ) : null}
        {tool === "roi" || tool === "edit-region" ? (
          <div className="two-point-box-note" data-testid="two-point-box-instruction">
            {tool === "roi"
              ? twoPointFirst
                ? "第一個角已選，請再點對角送出 SAM 框選"
                : "請點第一個角，再點對角建立 SAM 搜尋範圍"
              : twoPointOpposite
                ? "編輯範圍已建立；繼續點擊會替換距離最近的角點，或選畫筆／擦除"
                : twoPointFirst
                  ? "第一個角已選，請再點對角完成編輯範圍"
                  : "請點第一個角，再點對角建立畫筆／擦除編輯範圍"}
          </div>
        ) : null}
        {editRegion && (tool === "brush" || tool === "erase") ? (
          <div className="edit-region-note" data-testid="edit-region-note">
            編輯範圍：畫筆／擦除只修改框內
            <button
              type="button"
              className="btn"
              data-testid="clear-edit-region"
              onClick={() => {
                setEditRegion(null);
                setEditRegionDraft(null);
                setTwoPointFirst(null);
                setTwoPointOpposite(null);
              }}
            >
              清除範圍
            </button>
          </div>
        ) : null}
        {pendingLock && pendingLockCss ? (
          <div
            className="lock-preview"
            data-testid="lock-preview"
            style={{
              left: pendingLockCss.x + 0.5 * viewport.zoom,
              top: pendingLockCss.y + 0.5 * viewport.zoom,
            }}
          >
            <span>預覽鎖定此區塊？</span>
            <button
              type="button"
              className="btn accept"
              data-testid="confirm-lock-region"
              onClick={() => {
                props.onLockRegion?.(pendingLock.x, pendingLock.y);
                setPendingLock(null);
              }}
            >
              確認鎖定
            </button>
            <button
              type="button"
              className="btn"
              data-testid="cancel-lock-region"
              onClick={() => setPendingLock(null)}
            >
              取消
            </button>
          </div>
        ) : null}
        <canvas
          ref={canvasRef}
          data-testid="annotation-canvas"
          data-image-width={imageSize?.width}
          data-image-height={imageSize?.height}
          data-session-id={snapshot?.protocol_session_id ?? ""}
          data-user-roi={snapshot?.user_roi_full?.join(",") ?? ""}
          data-zoom={viewport.zoom.toFixed(4)}
          data-pan-x={viewport.panX.toFixed(2)}
          data-pan-y={viewport.panY.toFixed(2)}
          data-view-width={viewSize.width}
          data-view-height={viewSize.height}
          width={Math.max(1, Math.round(viewSize.width * (viewport.dpr || 1)))}
          height={Math.max(1, Math.round(viewSize.height * (viewport.dpr || 1)))}
          style={{ touchAction: "none", cursor }}
          onPointerDown={(e) => {
            if (isPanGesture(e)) {
              e.preventDefault();
              capturePointer(e);
              pan.current = { x: e.clientX, y: e.clientY };
              setPanning(true);
              return;
            }
            const img = pointForEvent(e);
            if (!img) return;
            if (tool === "roi" || tool === "edit-region") {
              // PhoneCV-compatible tap mode: do not capture the pointer or
              // start a drag. The click is committed in pointer-up below.
              return;
            }
            // Prevent the WebView's native drag/text-selection handling from
            // swallowing a brush stroke before pointer-up reaches React.
            e.preventDefault();
            if (tool === "point" || tool === "point-remove") {
              props.onPoint(img.x, img.y, pointLabelForInput(tool, e.button));
              return;
            }
            if (tool === "prompt-select") {
              if (props.promptMoveMode && selectedPromptId) {
                props.onPromptMove?.(selectedPromptId, img.x, img.y);
                props.onPromptMoveDone?.();
                return;
              }
              const rect = e.currentTarget.getBoundingClientRect();
              const clickX = e.clientX - rect.left;
              const clickY = e.clientY - rect.top;
              const closest = promptPoints
                .map((point, index) => {
                  const css = imageToCss(point.x, point.y, viewport);
                  return {
                    id: point.point_id ?? `prompt-${index}`,
                    distance: Math.hypot(clickX - css.x, clickY - css.y),
                  };
                })
                .filter((point) => point.distance <= 14)
                .sort((a, b) => a.distance - b.distance)[0];
              setSelectedPromptId(closest?.id ?? null);
              return;
            }
            if (tool === "lock-region") {
              setPendingLock({ x: img.x, y: img.y });
              return;
            }
            capturePointer(e);
            drag.current = { x: img.x, y: img.y };
            stroke.current = [[img.x, img.y]];
            if (tool === "brush" || tool === "erase") setDraftStroke([[img.x, img.y]]);
          }}
          onPointerMove={(e) => {
            if (activePointerId.current !== null && e.pointerId !== activePointerId.current) return;
            const img = pointForEvent(e);
            if (img) setHover(img);
            if (pan.current) {
              setViewport(
                panViewport(
                  useViewStore.getState().viewport,
                  e.clientX - pan.current.x,
                  e.clientY - pan.current.y,
                ),
              );
              pan.current = { x: e.clientX, y: e.clientY };
              return;
            }
            if (!drag.current) return;
            if (img) {
              stroke.current.push([img.x, img.y]);
              if (tool === "brush" || tool === "erase") {
                setDraftStroke(stroke.current.slice());
              }
            }
          }}
          onPointerLeave={() => setHover(null)}
          onPointerUp={(e) => {
            if (activePointerId.current !== null && e.pointerId !== activePointerId.current) return;
            if (pan.current) {
              pan.current = null;
              setPanning(false);
              releasePointerCapture(e);
              return;
            }
            if (tool === "roi" || tool === "edit-region") {
              if (e.button !== 0) return;
              e.preventDefault();
              const img = pointForEvent(e);
              if (!img) {
                return;
              }
              if (!twoPointFirst) {
                setTwoPointFirst(img);
                setTwoPointOpposite(null);
                // Keep the first tap as a marker only. PhoneCV does not draw
                // a cursor-following preview rectangle between taps.
                setEditRegionDraft(null);
                setBoxTip(null);
                return;
              }
              if (twoPointOpposite) {
                if (tool === "roi") {
                  // A SAM box is submitted on the second tap.  The local
                  // edit-area tool is the one that supports repeated corner
                  // replacement after a rectangle already exists.
                  setTwoPointFirst(null);
                  setTwoPointOpposite(null);
                  setEditRegion(null);
                  setEditRegionDraft(null);
                  setBoxTip(null);
                  return;
                }
                // Match PhoneCV: every subsequent tap replaces whichever
                // corner is closer in on-screen image pixels; no drag or hit
                // radius is involved.
                const corner = nearestTwoPointCorner(img, twoPointFirst, twoPointOpposite);
                const nextFirst = corner === "first" ? img : twoPointFirst;
                const nextOpposite = corner === "opposite" ? img : twoPointOpposite;
                const nextRect = rectFromCorners(nextFirst, nextOpposite);
                if (nextRect[2] - nextRect[0] < 4 || nextRect[3] - nextRect[1] < 4) {
                  setEditRegionDraft(editRegion);
                  setBoxTip("兩個角點至少要相隔 4 個像素");
                  return;
                }
                setTwoPointFirst(nextFirst);
                setTwoPointOpposite(nextOpposite);
                setEditRegion(nextRect);
                setEditRegionDraft(null);
                setBoxTip(null);
                return;
              }
              const rect = rectFromCorners(twoPointFirst, img);
              if (rect[2] - rect[0] < 4 || rect[3] - rect[1] < 4) {
                setBoxTip("兩個角要離遠一點，才能包住缺陷");
                return;
              }
              setTwoPointOpposite(img);
              if (tool === "roi") {
                props.onRoi(rect);
                setTwoPointFirst(null);
                setTwoPointOpposite(null);
                setEditRegion(null);
                setEditRegionDraft(null);
              } else {
                setEditRegion(rect);
                setEditRegionDraft(null);
              }
              setBoxTip(null);
              return;
            }
            if (!drag.current) return;
            e.preventDefault();
            drag.current = null;
            setDraftStroke([]);
            if (tool === "brush" || tool === "erase") {
              props.onStroke(stroke.current, tool === "erase", editRegion);
            }
            releasePointerCapture(e);
            stroke.current = [];
          }}
          onPointerCancel={(e) => {
            releasePointerCapture(e);
            pan.current = null;
            drag.current = null;
            setPanning(false);
            setDraftStroke([]);
            stroke.current = [];
          }}
          onDoubleClick={(e) => {
            e.preventDefault();
            fitFullImage();
          }}
          onAuxClick={(e) => e.preventDefault()}
          onContextMenu={(e) => e.preventDefault()}
        />
        <canvas
          ref={overlayRef}
          className="viewer-overlay"
          width={Math.max(1, Math.round(viewSize.width * (viewport.dpr || 1)))}
          height={Math.max(1, Math.round(viewSize.height * (viewport.dpr || 1)))}
        />
        {visibleEditRegion ? (
          <div
            className="edit-region-label"
            data-testid="edit-region-overlay"
            style={{
              left: Math.max(4, visibleEditRegion[0] * viewport.zoom + viewport.panX),
              top: Math.max(4, visibleEditRegion[1] * viewport.zoom + viewport.panY - 20),
            }}
          >
            編輯範圍
          </div>
        ) : null}
        {twoPointFirst ? (() => {
          const css = imageToCss(twoPointFirst.x, twoPointFirst.y, viewport);
          return (
            <div
              className="two-point-corner"
              data-testid="two-point-corner-1"
              data-image-x={twoPointFirst.x}
              data-image-y={twoPointFirst.y}
              style={{ left: css.x + 0.5 * viewport.zoom, top: css.y + 0.5 * viewport.zoom }}
              aria-label="第一個角"
            >1</div>
          );
        })() : null}
        {twoPointOpposite ? (() => {
          const css = imageToCss(twoPointOpposite.x, twoPointOpposite.y, viewport);
          return (
            <div
              className="two-point-corner"
              data-testid="two-point-corner-2"
              data-image-x={twoPointOpposite.x}
              data-image-y={twoPointOpposite.y}
              style={{ left: css.x + 0.5 * viewport.zoom, top: css.y + 0.5 * viewport.zoom }}
              aria-label="第二個角"
            >2</div>
          );
        })() : null}
        {hover && (tool === "brush" || tool === "erase") && draftStroke.length === 0
          ? (() => {
              const css = imageToCss(hover.x, hover.y, viewport);
              const diameter = Math.max(8, (brushRadius * 2 + 1) * viewport.zoom);
              return (
                <div
                  className={tool === "erase" ? "brush-cursor erase" : "brush-cursor"}
                  data-testid="brush-cursor"
                  style={{
                    width: diameter,
                    height: diameter,
                    left: css.x + 0.5 * viewport.zoom - diameter / 2,
                    top: css.y + 0.5 * viewport.zoom - diameter / 2,
                  }}
                />
              );
            })()
          : null}
        {focusRect && focusCss ? (
          <div
            className={snapshot?.prototype?.matched ? "region-badge dino" : "region-badge"}
            data-testid="region-badge"
            style={{ left: Math.max(8, focusCss.x), top: Math.max(8, focusCss.y - 22) }}
          >
            {badge}
            {` · ${Math.max(0, focusRect[2] - focusRect[0])}×${Math.max(0, focusRect[3] - focusRect[1])}`}
          </div>
        ) : null}
        {boxTip ? (
          <div className="box-tip" data-testid="box-too-small">
            {boxTip}
          </div>
        ) : null}
        {hasRoi || mask ? (
          <div className="overlay-legend" data-testid="overlay-legend">
            <span>
              <i className="swatch mask" /> 粉紅＝切割結果（遮罩）
            </span>
            <span>
              <i className="swatch box" /> 黃框＝搜尋範圍，不是遮罩
            </span>
            <span>變暗區域不計算</span>
          </div>
        ) : null}
        {computing ? (
          <div className="compute-banner" data-testid="compute-banner">
            {props.statusText}
          </div>
        ) : null}
        {showMinimap ? (
          <button
            type="button"
            className="viewer-minimap"
            data-testid="viewer-minimap"
            title="點一下可平移"
            onClick={(event) => {
              if (!imageSize) return;
              const mini = minimapRef.current;
              if (!mini) return;
              const rect = mini.getBoundingClientRect();
              const scaleX = imageSize.width / rect.width;
              const scaleY = imageSize.height / rect.height;
              const imgX = (event.clientX - rect.left) * scaleX;
              const imgY = (event.clientY - rect.top) * scaleY;
              const size = useViewStore.getState().viewSize;
              const vp = useViewStore.getState().viewport;
              setViewport({
                ...vp,
                panX: size.width / 2 - imgX * vp.zoom,
                panY: size.height / 2 - imgY * vp.zoom,
              });
            }}
          >
            <canvas ref={minimapRef} />
          </button>
        ) : null}
      </div>
    </div>
  );
}

export const overlayFill = OVERLAY_FILL;
