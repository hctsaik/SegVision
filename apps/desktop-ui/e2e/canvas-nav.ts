import type { Page } from "@playwright/test";
import type { StagedItem } from "./harness";

type E2EWindow = {
  __SEGVISION_E2E__: {
    setViewport: (viewport: { zoom: number; panX: number; panY: number; dpr: number }) => void;
    getViewport: () => { zoom: number; panX: number; panY: number; dpr: number };
    getViewSize: () => { width: number; height: number };
  };
};

export async function waitImage(page: Page, item: StagedItem) {
  await page.waitForFunction(
    ({ width, height }) => {
      const canvas = document.querySelector("[data-testid=annotation-canvas]");
      return (
        canvas?.getAttribute("data-image-width") === String(width) &&
        canvas?.getAttribute("data-image-height") === String(height) &&
        Number(canvas.getAttribute("data-view-width")) >= 32
      );
    },
    { width: item.width, height: item.height },
    { timeout: 30000 },
  );
}

export async function previewRoi(page: Page, roi: [number, number, number, number]) {
  const view = await page.evaluate(() => {
    const api = (window as unknown as E2EWindow).__SEGVISION_E2E__;
    return { ...api.getViewport(), ...api.getViewSize() };
  });
  const width = Math.max(64, roi[2] - roi[0]);
  const height = Math.max(64, roi[3] - roi[1]);
  const zoom = Math.max(0.25, Math.min(view.width / width, view.height / height, 4));
  await page.evaluate(
    ({ zoom, cx, cy, viewW, viewH }) => {
      (window as unknown as E2EWindow).__SEGVISION_E2E__.setViewport({
        zoom,
        panX: viewW / 2 - cx * zoom,
        panY: viewH / 2 - cy * zoom,
        dpr: 1,
      });
    },
    { zoom, cx: (roi[0] + roi[2]) / 2, cy: (roi[1] + roi[3]) / 2, viewW: view.width, viewH: view.height },
  );
}

export async function clickImagePoint(
  page: Page,
  x: number,
  y: number,
  button: "left" | "right" = "left",
) {
  const canvas = page.getByTestId("annotation-canvas");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("canvas has no box");
  const viewport = await page.evaluate(
    () => (window as unknown as E2EWindow).__SEGVISION_E2E__.getViewport(),
  );
  await page.mouse.click(box.x + x * viewport.zoom + viewport.panX, box.y + y * viewport.zoom + viewport.panY, {
    button,
  });
}

export async function drawRoi(page: Page, roi: [number, number, number, number]) {
  await previewRoi(page, roi);
  const canvas = page.getByTestId("annotation-canvas");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("canvas has no box");
  const viewport = await page.evaluate(
    () => (window as unknown as E2EWindow).__SEGVISION_E2E__.getViewport(),
  );
  const startX = box.x + roi[0] * viewport.zoom + viewport.panX;
  const startY = box.y + roi[1] * viewport.zoom + viewport.panY;
  const endX = box.x + (roi[2] - 1) * viewport.zoom + viewport.panX;
  const endY = box.y + (roi[3] - 1) * viewport.zoom + viewport.panY;
  // ROI selection is a PhoneCV-style two-tap interaction.  Keep the
  // navigation helper click-only so E2E coverage does not accidentally rely
  // on the old drag gesture.
  await page.mouse.click(startX, startY);
  await page.mouse.click(endX, endY);
  await page.waitForFunction(() => {
    const value = document
      .querySelector("[data-testid=annotation-canvas]")
      ?.getAttribute("data-user-roi");
    return Boolean(value && value.split(",").length === 4);
  });
}
