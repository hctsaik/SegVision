import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { drawRoi, waitImage } from "./canvas-nav";
import {
  e2eUrl,
  stageMvtecCapsuleDataset,
  startStack,
  stopStack,
  type RunningStack,
  type StagedItem,
} from "./harness";

let stack: RunningStack;
let items: StagedItem[];

test.beforeAll(async () => {
  const staged = stageMvtecCapsuleDataset();
  items = staged.items;
  stack = await startStack(fs.mkdtempSync(path.join(os.tmpdir(), "segvision-e2e-out-")), staged.datasetDir);
  stack.items = items;
});

test.afterAll(() => {
  if (stack) stopStack(stack);
});

function paddedRoi(item: StagedItem, pad = 16): [number, number, number, number] {
  const [x0, y0, x1, y1] = item.gold_bbox;
  return [
    Math.max(0, x0 - pad),
    Math.max(0, y0 - pad),
    Math.min(item.width, x1 + pad),
    Math.min(item.height, y1 + pad),
  ];
}

test("DINO prototype matches a moved scratch instead of copying the previous ROI", async ({
  page,
}, testInfo) => {
  const first = items[0];
  const second = items[1];
  if (!first || !second) throw new Error("missing staged items");

  await page.goto(e2eUrl(stack));
  await page.getByTestId("open-dataset").click();
  await page.getByTestId("choose-output").click();
  await page.getByTestId("toggle-advanced").click();
  await page.getByTestId("dino-prototype").check();
  await expect(page.getByTestId("reuse-last-roi")).not.toBeChecked();

  await page.getByText("000.png").click();
  await waitImage(page, first);
  await drawRoi(page, paddedRoi(first));
  await expect(page.getByTestId("candidate-1")).toBeVisible({ timeout: 30000 });
  await page.getByTestId("accept").click();
  await expect(page.getByTestId("workflow-state")).toHaveAttribute("data-state", "ACCEPTED", { timeout: 120000 });
  await expect(page.getByTestId("roi-reuse-status")).toContainText("fitted", { timeout: 120000 });
  const teacherRoi = await page.getByTestId("annotation-canvas").getAttribute("data-user-roi");
  await testInfo.attach("01-teacher-fitted", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });

  await page.getByTestId("next-image").click();
  await expect(page.getByTestId("roi-reuse-status")).toContainText("matched", { timeout: 120000 });
  await expect(page.getByTestId("workflow-state")).not.toHaveAttribute("data-state", "IMAGE_OPEN", {
    timeout: 30000,
  });
  const matchedRoi = (await page.getByTestId("annotation-canvas").getAttribute("data-user-roi")) ?? "";
  expect(matchedRoi).toMatch(/^\d+,\d+,\d+,\d+$/);
  expect(matchedRoi).not.toBe(teacherRoi);
  const [x0, y0, x1, y1] = matchedRoi.split(",").map(Number);
  const [gx0, gy0, gx1, gy1] = second.gold_bbox;
  const overlap =
    Math.max(0, Math.min(x1, gx1) - Math.max(x0, gx0)) *
    Math.max(0, Math.min(y1, gy1) - Math.max(y0, gy0));
  expect(overlap).toBeGreaterThan(0);
  await testInfo.attach("02-dino-matched-moved-scratch", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
