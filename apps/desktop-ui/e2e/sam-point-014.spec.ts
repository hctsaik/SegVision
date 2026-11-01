import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { clickImagePoint, drawRoi, previewRoi, waitImage } from "./canvas-nav";
import {
  e2eUrl,
  mvtecCapsuleRoot,
  pythonBin,
  repoRoot,
  startStack,
  stopStack,
  type RunningStack,
  type StagedItem,
} from "./harness";
import { execFileSync } from "node:child_process";

const here = path.dirname(fileURLToPath(import.meta.url));
const stageScript = path.join(here, "stage-capsule-crack-014.py");

let stack: RunningStack;
let item: StagedItem;

test.beforeAll(async () => {
  const datasetDir = fs.mkdtempSync(path.join(os.tmpdir(), "segvision-capsule-crack-014-"));
  const staged = JSON.parse(
    execFileSync(
      pythonBin(),
      [stageScript, datasetDir, "--source", mvtecCapsuleRoot()],
      { cwd: repoRoot, encoding: "utf8" },
    ),
  ) as { root: string; items: StagedItem[] };
  item = staged.items[0]!;
  stack = await startStack(
    fs.mkdtempSync(path.join(os.tmpdir(), "segvision-capsule-crack-014-out-")),
    staged.root,
    { preferReal: true },
  );
  stack.items = staged.items;
}, { timeout: 180000 });

test.afterAll(() => {
  if (stack) stopStack(stack);
});

function paddedRoi(pad = 24): [number, number, number, number] {
  const [x0, y0, x1, y1] = item.gold_bbox;
  return [
    Math.max(0, x0 - pad),
    Math.max(0, y0 - pad),
    Math.min(item.width, x1 + pad),
    Math.min(item.height, y1 + pad),
  ];
}

test("014.png SAM point click reaches refine and updates prompt history", async ({ page }) => {
  test.setTimeout(300000);
  await page.goto(e2eUrl(stack));
  await expect(page.getByTestId("backend-name")).toHaveAttribute("data-backend", "mobilesam", {
    timeout: 30000,
  });
  await page.getByTestId("open-dataset").click();
  await expect(page.getByText("014.png")).toBeVisible();
  await page.getByText("014.png").click();
  await waitImage(page, item);

  const roi = paddedRoi();
  await drawRoi(page, roi);
  await expect(page.getByTestId("candidate-1")).toBeVisible({ timeout: 30000 });
  await expect(page.getByTestId("tool-point")).toBeEnabled();
  await page.getByTestId("tool-point").click();

  const [x0, y0, x1, y1] = roi;
  await previewRoi(page, roi);
  await clickImagePoint(page, Math.floor((x0 + x1) / 2), Math.floor((y0 + y1) / 2), "left");

  // Refinement keeps the same ROI revision; prompt history and the selected
  // candidate are the observable proof that the click reached MobileSAM.
  await expect(page.getByTestId("prompt-chip-0")).toBeVisible({ timeout: 30000 });
  await page.getByTestId("undo").click();
  await expect(page.getByTestId("redo")).toBeEnabled({ timeout: 30000 });
  await page.getByTestId("redo").click();
  await expect(page.getByTestId("prompt-chip-0")).toBeVisible({ timeout: 30000 });
  await expect(page.getByTestId("operation-error")).toHaveCount(0);
});

test("014.png independent edit area uses two taps and clips a brush", async ({ page }) => {
  test.setTimeout(180000);
  const lockRoiCalls: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/lock-roi")) lockRoiCalls.push(request.url());
  });
  await page.goto(e2eUrl(stack));
  await page.getByTestId("open-dataset").click();
  await page.getByText("014.png").click();
  await waitImage(page, item);
  await page.getByTestId("tool-edit-region").click();
  const area: [number, number, number, number] = [
    Math.max(0, item.gold_bbox[0] - 8),
    Math.max(0, item.gold_bbox[1] - 8),
    Math.min(item.width, item.gold_bbox[2] + 8),
    Math.min(item.height, item.gold_bbox[3] + 8),
  ];
  await previewRoi(page, area);
  await clickImagePoint(page, area[0], area[1]);
  await clickImagePoint(page, area[2] - 1, area[3] - 1);
  await expect(page.getByTestId("edit-region-overlay")).toBeVisible();
  // A later tap replaces the nearest corner, matching PhoneCV's point
  // interaction instead of requiring a drag gesture.
  await clickImagePoint(page, area[0] + 2, area[1] + 2);
  await page.evaluate(() => {
    (window as any).__SEGVISION_E2E__.setViewport({ zoom: 1.25, panX: -11, panY: 7, dpr: 1.5 });
  });
  await page.getByTestId("tool-brush").click();
  const canvas = page.getByTestId("annotation-canvas");
  const box = await canvas.boundingBox();
  if (!box) throw new Error("canvas has no box");
  const viewport = await page.evaluate(() => (window as any).__SEGVISION_E2E__.getViewport());
  const sx = box.x + (area[0] + 1) * viewport.zoom + viewport.panX;
  const sy = box.y + (area[1] + 1) * viewport.zoom + viewport.panY;
  await page.mouse.move(sx, sy);
  await page.mouse.down();
  await page.mouse.move(sx + 4 * viewport.zoom, sy + 2 * viewport.zoom);
  await page.mouse.up();
  await expect(page.getByTestId("draft-status")).toBeVisible({ timeout: 30000 });
  expect(lockRoiCalls).toHaveLength(0);
  await expect(page.getByTestId("operation-error")).toHaveCount(0);
});
