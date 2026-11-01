export type Rect = [number, number, number, number];

export interface Viewport {
  zoom: number;
  panX: number;
  panY: number;
  dpr: number;
}

export function cssToImage(
  cssX: number,
  cssY: number,
  viewport: Viewport,
  imageWidth: number,
  imageHeight: number,
): { x: number; y: number } {
  const x = Math.floor((cssX - viewport.panX) / viewport.zoom);
  const y = Math.floor((cssY - viewport.panY) / viewport.zoom);
  return {
    x: Math.max(0, Math.min(imageWidth - 1, x)),
    y: Math.max(0, Math.min(imageHeight - 1, y)),
  };
}

export function imageToCss(x: number, y: number, viewport: Viewport): { x: number; y: number } {
  return { x: x * viewport.zoom + viewport.panX, y: y * viewport.zoom + viewport.panY };
}

export function roundTripXyxy(rect: Rect, viewport: Viewport, width: number, height: number): Rect {
  const a = imageToCss(rect[0], rect[1], viewport);
  const b = imageToCss(rect[2], rect[3], viewport);
  const p0 = cssToImage(a.x, a.y, viewport, width, height);
  const p1 = cssToImage(b.x - 1e-6, b.y - 1e-6, viewport, width, height);
  return [p0.x, p0.y, p1.x + 1, p1.y + 1];
}

export const DEFAULT_VIEWPORT: Viewport = { zoom: 1, panX: 0, panY: 0, dpr: 1 };

export const CANVAS_VIEW_WIDTH = 800;
export const CANVAS_VIEW_HEIGHT = 500;
export const MIN_ZOOM = 0.05;
export const MAX_ZOOM = 32;
export const ZOOM_STEP = 1.12;

export function clampZoom(zoom: number): number {
  if (!Number.isFinite(zoom) || zoom <= 0) return 1;
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/** Show the entire image, letterboxed in the annotation canvas. */
export function fitContainViewport(
  imageWidth: number,
  imageHeight: number,
  viewW: number = CANVAS_VIEW_WIDTH,
  viewH: number = CANVAS_VIEW_HEIGHT,
): Viewport {
  const width = Math.max(1, imageWidth);
  const height = Math.max(1, imageHeight);
  const zoom = clampZoom(Math.min(viewW / width, viewH / height));
  return {
    zoom,
    panX: (viewW - width * zoom) / 2,
    panY: (viewH - height * zoom) / 2,
    dpr: 1,
  };
}

/** Zoom toward a canvas CSS point so the image pixel under the cursor stays put. */
export function zoomViewportAt(
  viewport: Viewport,
  cssX: number,
  cssY: number,
  factor: number,
): Viewport {
  const zoom = clampZoom(viewport.zoom * factor);
  const imgX = (cssX - viewport.panX) / viewport.zoom;
  const imgY = (cssY - viewport.panY) / viewport.zoom;
  return {
    zoom,
    panX: cssX - imgX * zoom,
    panY: cssY - imgY * zoom,
    dpr: viewport.dpr,
  };
}

export function panViewport(viewport: Viewport, dx: number, dy: number): Viewport {
  return { ...viewport, panX: viewport.panX + dx, panY: viewport.panY + dy };
}

export type ViewSize = { width: number; height: number };

/** Keep the image point at the old view center in the new view center. */
export function preserveViewCenter(
  viewport: Viewport,
  oldView: ViewSize,
  newView: ViewSize,
): Viewport {
  const imgX = (oldView.width / 2 - viewport.panX) / viewport.zoom;
  const imgY = (oldView.height / 2 - viewport.panY) / viewport.zoom;
  return {
    zoom: viewport.zoom,
    panX: newView.width / 2 - imgX * viewport.zoom,
    panY: newView.height / 2 - imgY * viewport.zoom,
    dpr: viewport.dpr,
  };
}

/** 1 image pixel = 1 CSS pixel, image centered. */
export function actualSizeViewport(
  imageWidth: number,
  imageHeight: number,
  viewW: number = CANVAS_VIEW_WIDTH,
  viewH: number = CANVAS_VIEW_HEIGHT,
): Viewport {
  return {
    zoom: 1,
    panX: (viewW - Math.max(1, imageWidth)) / 2,
    panY: (viewH - Math.max(1, imageHeight)) / 2,
    dpr: 1,
  };
}

/** Frame a locked user ROI inside the annotation canvas. */
export function viewportForRoi(
  roi: Rect,
  viewW: number = CANVAS_VIEW_WIDTH,
  viewH: number = CANVAS_VIEW_HEIGHT,
  margin = 0.22,
): Viewport {
  const width = Math.max(8, roi[2] - roi[0]);
  const height = Math.max(8, roi[3] - roi[1]);
  const zoom = Math.max(
    MIN_ZOOM,
    Math.min(viewW / (width * (1 + margin)), viewH / (height * (1 + margin)), 16),
  );
  const cx = (roi[0] + roi[2]) / 2;
  const cy = (roi[1] + roi[3]) / 2;
  return {
    zoom,
    panX: viewW / 2 - cx * zoom,
    panY: viewH / 2 - cy * zoom,
    dpr: 1,
  };
}
