import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { drawRoi, previewRoi, waitImage } from "./canvas-nav";
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
  const outputDir = fs.mkdtempSync(path.join(os.tmpdir(), "segvision-e2e-out-"));
  stack = await startStack(outputDir, staged.datasetDir);
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

async function previewDefect(page: Page, item: StagedItem) {
  await previewRoi(page, paddedRoi(item, 40));
}

async function openDataset(page: Page) {
  await page.goto(e2eUrl(stack));
  await page.getByTestId("open-dataset").click();
  await expect(page.getByText("000.png")).toBeVisible();
  await page.getByTestId("choose-output").click();
  await expect(page.getByTestId("output-grant")).toBeVisible();
}

test.describe("Reuse last ROI on MVTec capsule scratch", () => {
  test("tight ROI on similar scratches: reuse off, reuse on, list does not carry", async ({
    page,
  }, testInfo) => {
    const first = items[0];
    const second = items[1];
    const third = items[2];
    if (!first || !second || !third) throw new Error("staged MVTec items missing");

    await test.step("open real capsule scratch batch", async () => {
      await openDataset(page);
      await expect(page.getByTestId("reuse-last-roi")).not.toBeChecked();
      await testInfo.attach("01-batch", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    });

    await test.step("tight ROI on 000 scratch and Accept", async () => {
      await page.getByText("000.png").click();
      await waitImage(page, first);
      await previewDefect(page, first);
      await testInfo.attach("02-000-gold", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
      await drawRoi(page, paddedRoi(first));
      await expect(page.getByTestId("candidate-1")).toBeVisible({ timeout: 30000 });
      await page.getByTestId("accept").click();
      await expect(page.getByTestId("workflow-state")).toHaveAttribute("data-state", "ACCEPTED");
      await testInfo.attach("03-000-accepted-tight", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    });

    await test.step("Next with reuse OFF shows 002 gold, no ROI", async () => {
      await page.getByTestId("next-image").click();
      await expect(page.getByTestId("workflow-state")).toHaveAttribute("data-state", "IMAGE_OPEN");
      await waitImage(page, second);
      await previewDefect(page, second);
      await expect(page.getByTestId("annotation-canvas")).toHaveAttribute("data-user-roi", "");
      await expect(page.getByTestId("roi-reuse-status")).toHaveCount(0);
      await testInfo.attach("04-002-reuse-off", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    });

    await test.step("enable reuse; Next frames the same tight box on 003", async () => {
      await drawRoi(page, paddedRoi(second));
      await expect(page.getByTestId("candidate-1")).toBeVisible({ timeout: 30000 });
      const secondRoi = await page.getByTestId("annotation-canvas").getAttribute("data-user-roi");
      await page.getByTestId("accept").click();
      await expect(page.getByTestId("workflow-state")).toHaveAttribute("data-state", "ACCEPTED");
      await page.getByTestId("reuse-last-roi").check();
      await page.getByTestId("next-image").click();
      await expect(page.getByTestId("annotation-canvas")).toHaveAttribute(
        "data-user-roi",
        secondRoi ?? "",
        { timeout: 30000 },
      );
      await expect(page.getByTestId("roi-reuse-status")).toHaveText("Reused last ROI on this image.");
      await expect(page.getByTestId("candidate-1")).toBeVisible({ timeout: 30000 });
      await testInfo.attach("05-003-reuse-on-framed", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    });

    await test.step("list click back to 000 does not carry", async () => {
      await page.getByTestId("accept").click();
      await expect(page.getByTestId("workflow-state")).toHaveAttribute("data-state", "ACCEPTED");
      await page.getByText("000.png").click();
      await expect(page.getByTestId("workflow-state")).toHaveAttribute("data-state", "IMAGE_OPEN");
      await waitImage(page, first);
      await previewDefect(page, first);
      await expect(page.getByTestId("annotation-canvas")).toHaveAttribute("data-user-roi", "");
      await expect(page.getByTestId("roi-reuse-status")).toHaveCount(0);
      await testInfo.attach("06-list-000-no-carry", {
        body: await page.screenshot({ fullPage: true }),
        contentType: "image/png",
      });
    });
  });
});
