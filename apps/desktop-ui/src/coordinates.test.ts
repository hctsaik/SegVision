import { describe, expect, it } from "vitest";
import {
  actualSizeViewport,
  cssToImage,
  fitContainViewport,
  imageToCss,
  panViewport,
  preserveViewCenter,
  roundTripXyxy,
  viewportForRoi,
  zoomViewportAt,
  type Viewport,
} from "./coordinates";

describe("coordinates", () => {
  it("round-trips half-open XYXY at dpr 1", () => {
    const vp: Viewport = { zoom: 1, panX: 0, panY: 0, dpr: 1 };
    expect(roundTripXyxy([10, 8, 38, 36], vp, 50, 40)).toEqual([10, 8, 38, 36]);
  });

  it("handles non-1 DPR and zoom/pan", () => {
    const vp: Viewport = { zoom: 2, panX: 5, panY: 7, dpr: 1.5 };
    const css = imageToCss(10, 8, vp);
    const img = cssToImage(css.x, css.y, vp, 50, 40);
    expect(img).toEqual({ x: 10, y: 8 });
  });

  it("frames a tight ROI inside the canvas", () => {
    const vp = viewportForRoi([100, 100, 300, 300], 800, 500, 0);
    expect(vp.zoom).toBeCloseTo(2.5, 5);
    const css = imageToCss(200, 200, vp);
    expect(css.x).toBeCloseTo(400, 5);
    expect(css.y).toBeCloseTo(250, 5);
  });

  it("fits a square image so the full frame is visible", () => {
    const vp = fitContainViewport(1000, 1000, 800, 500);
    expect(vp.zoom).toBeCloseTo(0.5, 5);
    expect(vp.panX).toBeCloseTo(150, 5);
    expect(vp.panY).toBeCloseTo(0, 5);
    expect(imageToCss(0, 0, vp)).toEqual({ x: 150, y: 0 });
    expect(imageToCss(1000, 1000, vp)).toEqual({ x: 650, y: 500 });
  });

  it("keeps the image pixel under the cursor when zooming", () => {
    const start = fitContainViewport(1000, 1000, 800, 500);
    const cssX = 400;
    const cssY = 250;
    const before = cssToImage(cssX, cssY, start, 1000, 1000);
    const zoomed = zoomViewportAt(start, cssX, cssY, 2);
    const after = cssToImage(cssX, cssY, zoomed, 1000, 1000);
    expect(zoomed.zoom).toBeCloseTo(1, 5);
    expect(after).toEqual(before);
  });

  it("pans in canvas pixels", () => {
    const start: Viewport = { zoom: 0.5, panX: 150, panY: 0, dpr: 1 };
    expect(panViewport(start, -20, 10)).toEqual({ zoom: 0.5, panX: 130, panY: 10, dpr: 1 });
  });

  it("keeps the view center when the canvas is resized", () => {
    const start = fitContainViewport(1000, 1000, 800, 500);
    const resized = preserveViewCenter(start, { width: 800, height: 500 }, { width: 1200, height: 700 });
    const before = cssToImage(400, 250, start, 1000, 1000);
    const after = cssToImage(600, 350, resized, 1000, 1000);
    expect(after).toEqual(before);
  });

  it("centers the image at 1:1", () => {
    const vp = actualSizeViewport(1000, 1000, 800, 500);
    expect(vp.zoom).toBe(1);
    expect(vp.panX).toBe(-100);
    expect(vp.panY).toBe(-250);
  });
});
