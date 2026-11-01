import { expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  e2eUrl,
  stageMvtecCapsuleDataset,
  startStack,
  stopStack,
  type RunningStack,
} from "./harness";

let stack: RunningStack;

test.beforeAll(async () => {
  const staged = stageMvtecCapsuleDataset();
  stack = await startStack(fs.mkdtempSync(path.join(os.tmpdir(), "segvision-cim-out-")), staged.datasetDir);
  stack.items = staged.items;
});

test.afterAll(() => {
  if (stack) stopStack(stack);
});

function cimUrl(): string {
  const url = new URL(e2eUrl(stack));
  url.searchParams.delete("e2e");
  url.searchParams.set("host", "cim");
  url.searchParams.delete("secret");
  url.searchParams.delete("dataset");
  url.searchParams.delete("output");
  return url.toString();
}

test("CIM host path opens a real dataset through the folder picker", async ({ page }, testInfo) => {
  await page.addInitScript(({ datasetDir, sidecarUrl, secret }) => {
    (window as unknown as { __SEGVISION_NATIVEAPP__: { sidecarUrl: string; secret: string } }).__SEGVISION_NATIVEAPP__ =
      { sidecarUrl, secret };
    (window as unknown as { cimHost: { chooseFile: () => Promise<{ canceled: boolean; paths: string[] }> } }).cimHost =
      {
        chooseFile: async () => ({ canceled: false, paths: [datasetDir] }),
      };
  }, {
    datasetDir: stack.datasetDir,
    sidecarUrl: `http://127.0.0.1:${stack.sidecarPort}`,
    secret: stack.secret,
  });

  await page.goto(cimUrl());
  await page.getByTestId("open-dataset").click();
  await expect(page.getByText("000.png")).toBeVisible({ timeout: 30000 });
  await page.getByTestId("choose-output").click();
  await expect(page.getByTestId("output-grant")).toBeVisible();
  await testInfo.attach("cim-shell-dataset", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  });
});
