import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { clickImagePoint, drawRoi, previewRoi, waitImage } from "./canvas-nav";
import {
  e2eUrl,
  pythonBin,
  repoRoot,
  stageCapsuleCrack004,
  startStack,
  stopStack,
  type RunningStack,
  type StagedItem,
} from "./harness";

const here = path.dirname(fileURLToPath(import.meta.url));
const reportDir = path.join(repoRoot, "playwright-report", "capsule-crack-004");

type Score = {
  iou: number;
  f1: number;
  precision: number;
  recall: number;
  tp: number;
  fp: number;
  fn: number;
  pred_area: number;
  gold_area: number;
};

type Step = { id: string; title: string; note: string; image?: string; overlay?: string; score?: Score };

let stack: RunningStack;
let item: StagedItem;
const steps: Step[] = [];

test.beforeAll(async () => {
  fs.rmSync(reportDir, { recursive: true, force: true });
  fs.mkdirSync(reportDir, { recursive: true });
  const staged = stageCapsuleCrack004();
  stack = await startStack(
    fs.mkdtempSync(path.join(os.tmpdir(), "segvision-crack004-out-")),
    staged.datasetDir,
    { preferReal: true },
  );
  stack.items = staged.items;
  const first = staged.items[0];
  if (!first) throw new Error("004.png was not staged");
  item = first;
}, { timeout: 180000 });

test.afterAll(() => {
  if (stack) stopStack(stack);
});

function sidecarHeaders(): Record<string, string> {
  return {
    "X-SegVision-Launch-Secret": stack.secret,
    "X-SegVision-Protocol-Version": "1.1",
    "X-SegVision-Host-Proxy": "1",
    "X-SegVision-Resolved-Path": stack.datasetDir,
    "X-SegVision-Output-Path": stack.outputDir,
  };
}

function paddedRoi(pad = 6): [number, number, number, number] {
  const [x0, y0, x1, y1] = item.gold_bbox;
  return [
    Math.max(0, x0 - pad),
    Math.max(0, y0 - pad),
    Math.min(item.width, x1 + pad),
    Math.min(item.height, y1 + pad),
  ];
}

async function attachShot(page: Page, id: string, title: string, note: string) {
  const file = path.join(reportDir, `${id}.png`);
  await page.screenshot({ path: file, fullPage: true });
  steps.push({ id, title, note, image: `${id}.png` });
}

async function fetchJson(url: string): Promise<Record<string, unknown>> {
  const response = await fetch(url, { headers: sidecarHeaders() });
  const body = (await response.json()) as Record<string, unknown>;
  if (!response.ok) throw new Error(`sidecar ${response.status} ${url}: ${JSON.stringify(body)}`);
  return body;
}

function writeHtml(health: Record<string, unknown>) {
  const backend = (health.backend as { name?: string } | undefined)?.name ?? "unknown";
  const setup = String(health.setup_state ?? "");
  const rows = steps
    .map((step) => {
      const score = step.score
        ? `<p>IoU <b>${step.score.iou}</b> · F1 ${step.score.f1} · P ${step.score.precision} · R ${step.score.recall} · pred ${step.score.pred_area}px · gold ${step.score.gold_area}px</p>`
        : "";
      const img = step.image ? `<img src="${step.image}" alt="${step.title}"/>` : "";
      const overlay = step.overlay
        ? `<p>Blue = gold only, red = SAM only, green = overlap</p><img src="${step.overlay}" alt="${step.title} overlay"/>`
        : "";
      return `<section><h2>${step.title}</h2><p>${step.note}</p>${score}${img}${overlay}</section>`;
    })
    .join("\n");
  const html = `<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"/>
<title>capsule crack 004 E2E</title>
<style>
body{font:15px/1.45 Segoe UI,sans-serif;max-width:1100px;margin:24px auto;color:#1c2430;background:#f4f6f8}
h1{font-size:22px} h2{font-size:16px;margin-top:0}
section{background:#fff;border:1px solid #d5dde6;border-radius:8px;padding:16px;margin:0 0 16px}
img{max-width:100%;border:1px solid #d5dde6;border-radius:6px}
.meta{color:#5b6b7c;font:13px/1.4 Consolas,monospace}
</style></head><body>
<h1>MVTec capsule crack 004 — white top crack</h1>
<p class="meta">source: MVTec capsule dataset — crack 004.png<br/>
gold bbox: ${item.gold_bbox.join(", ")} (${item.gold_bbox[2] - item.gold_bbox[0]}×${item.gold_bbox[3] - item.gold_bbox[1]})<br/>
backend: ${backend} · setup_state: ${setup}<br/>
legend: green overlap · blue gold-only · red SAM-only</p>
${rows}
</body></html>`;
  fs.writeFileSync(path.join(reportDir, "index.html"), html, "utf8");
}

test("tight ROI + points on the white top crack of 004.png", async ({ page }, testInfo) => {
  test.setTimeout(180000);
  const goldPath = path.join(stack.datasetDir, "004_gold.png");
  const rgbPath = path.join(stack.datasetDir, "004.png");
  const health = await fetchJson(`http://127.0.0.1:${stack.sidecarPort}/v1/health`);

  async function scoreMaskFromSession(stepId: string): Promise<Score | null> {
    const sessionId = await page.getByTestId("annotation-canvas").getAttribute("data-session-id");
    if (!sessionId) return null;
    const snap = await fetchJson(`http://127.0.0.1:${stack.sidecarPort}/v1/sessions/${sessionId}`);
    const assets = snap.assets as { mask?: string | null } | undefined;
    const crop = snap.crop_rect_full as number[] | undefined;
    const token = assets?.mask;
    if (!token) return null;
    const response = await fetch(`http://127.0.0.1:${stack.sidecarPort}/v1/assets/${encodeURIComponent(token)}`, {
      headers: sidecarHeaders(),
    });
    if (!response.ok) return null;
    const predPath = path.join(reportDir, `${stepId}-pred.png`);
    const overlayPath = path.join(reportDir, `${stepId}-overlay.png`);
    fs.writeFileSync(predPath, Buffer.from(await response.arrayBuffer()));
    const scoreArgs = [path.join(here, "score-mask.py"), predPath, goldPath, overlayPath, rgbPath];
    if (crop && crop.length === 4) scoreArgs.push(String(crop[0]), String(crop[1]), String(crop[2]), String(crop[3]));
    const scored = JSON.parse(
      execFileSync(pythonBin(), scoreArgs, {
        cwd: repoRoot,
        encoding: "utf8",
      }),
    ) as Score;
    const last = steps[steps.length - 1];
    if (last) {
      last.score = scored;
      last.overlay = `${stepId}-overlay.png`;
    }
    return scored;
  }

  await test.step("open 004.png", async () => {
    await page.goto(e2eUrl(stack));
    await page.getByTestId("open-dataset").click();
    await expect(page.getByText("004.png")).toBeVisible();
    await page.getByTestId("choose-output").click();
    await expect(page.getByTestId("output-grant")).toBeVisible();
    await page.getByText("004.png").click();
    await waitImage(page, item);
    await attachShot(
      page,
      "01-open",
      "1. Open 004.png",
      "Full capsule. The white crack sits on the top edge of the orange half, left of the printed 500.",
    );
  });

  await test.step("frame the gold crack", async () => {
    await previewRoi(page, paddedRoi(24));
    await attachShot(
      page,
      "02-gold-framed",
      "2. Frame the gold crack",
      `Gold XYXY ${item.gold_bbox.join(", ")}. Viewport zoomed onto the white chip on the orange cap.`,
    );
  });

  await test.step("draw a tight SAM box on the crack", async () => {
    const roi = paddedRoi(8);
    await drawRoi(page, roi);
    await expect(page.getByTestId("candidate-1")).toBeVisible({ timeout: 60000 });
    await attachShot(
      page,
      "03-roi-locked",
      "3. Lock tight ROI",
      `User ROI ≈ ${roi.join(", ")}. SAM must propose only inside this box, not the whole orange half.`,
    );
    await scoreMaskFromSession("03-roi-locked");
  });

  const candidateCount = await page.locator("[data-testid=candidate-cards] button").count();
  for (let index = 1; index <= Math.min(3, candidateCount); index += 1) {
    await test.step(`inspect candidate ${index}`, async () => {
      await page.getByTestId(`candidate-${index}`).click();
      await page.waitForTimeout(400);
      const label = (await page.getByTestId(`candidate-${index}`).textContent()) ?? `candidate ${index}`;
      await attachShot(page, `04-candidate-${index}`, `4.${index} ${label.trim()}`, "Selected SAM proposal overlaid on the crack region.");
      await scoreMaskFromSession(`04-candidate-${index}`);
    });
  }

  await test.step("foreground points on the white crack, background on orange body", async () => {
    await page.getByTestId("tool-point").click();
    await previewRoi(page, paddedRoi(24));
    const fg: Array<[number, number]> = [
      [560, 375],
      [624, 378],
      [685, 376],
    ];
    const bg: Array<[number, number]> = [
      [624, 430],
      [560, 450],
      [700, 440],
    ];
    for (const [x, y] of fg) {
      await clickImagePoint(page, x, y, "left");
      await page.waitForTimeout(500);
    }
    for (const [x, y] of bg) {
      await clickImagePoint(page, x, y, "right");
      await page.waitForTimeout(500);
    }
    await attachShot(
      page,
      "05-points",
      "5. Point refine",
      "Foreground clicks on the white crack; background clicks on the orange body below it. Goal: keep the chip, drop the SAM blob.",
    );
    await scoreMaskFromSession("05-points");
  });

  await test.step("write HTML report", async () => {
    writeHtml(health);
    const html = fs.readFileSync(path.join(reportDir, "index.html"));
    await testInfo.attach("capsule-crack-004-report", { body: html, contentType: "text/html" });
    expect(fs.existsSync(path.join(reportDir, "index.html"))).toBe(true);
    await expect(page.getByTestId("candidate-1")).toBeVisible();
  });
});
