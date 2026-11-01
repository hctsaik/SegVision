import { execFileSync, spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createServer } from "node:net";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const repoRoot = path.resolve(here, "..", "..", "..");
export const uiRoot = path.resolve(here, "..");

export function mvtecCapsuleRoot(): string {
  const root = process.env.SEGVISION_MVTEC_CAPSULE_ROOT;
  if (!root) {
    throw new Error("Set SEGVISION_MVTEC_CAPSULE_ROOT to the local MVTec capsule dataset directory");
  }
  return path.resolve(root);
}

export type StagedItem = {
  name: string;
  width: number;
  height: number;
  gold_bbox: [number, number, number, number];
};

export type RunningStack = {
  sidecar: ChildProcessWithoutNullStreams;
  ui: ChildProcessWithoutNullStreams;
  sidecarPort: number;
  uiPort: number;
  secret: string;
  outputDir: string;
  datasetDir: string;
  items: StagedItem[];
};

export function pythonBin(): string {
  return path.join(repoRoot, ".venv", "Scripts", "python.exe");
}

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      if (!address || typeof address === "string") {
        server.close();
        reject(new Error("no port"));
        return;
      }
      const port = address.port;
      server.close((error) => (error ? reject(error) : resolve(port)));
    });
  });
}

function killTree(child: ChildProcessWithoutNullStreams): void {
  if (child.pid && process.platform === "win32") {
    spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    return;
  }
  child.kill("SIGTERM");
}

async function waitHttp(
  url: string,
  timeoutMs = 20000,
  headers?: Record<string, string>,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let last = "";
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, headers ? { headers } : undefined);
      if (response.ok) return;
      last = `${response.status}`;
    } catch (error) {
      last = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`timeout waiting for ${url}: ${last}`);
}

export function stageCapsuleCrack004(): { datasetDir: string; items: StagedItem[] } {
  const capsuleRoot = mvtecCapsuleRoot();
  if (!fs.existsSync(path.join(capsuleRoot, "test", "crack", "004.png"))) {
    throw new Error(`MVTec capsule crack 004.png not found under ${capsuleRoot}`);
  }
  const datasetDir = fs.mkdtempSync(path.join(os.tmpdir(), "segvision-capsule-crack-004-"));
  const result = JSON.parse(
    execFileSync(pythonBin(), [path.join(here, "stage-capsule-crack-004.py"), datasetDir, "--source", capsuleRoot], {
      cwd: repoRoot,
      encoding: "utf8",
    }),
  ) as { root: string; items: StagedItem[] };
  return { datasetDir: result.root, items: result.items };
}

export function stageMvtecCapsuleDataset(): { datasetDir: string; items: StagedItem[] } {
  const capsuleRoot = mvtecCapsuleRoot();
  if (!fs.existsSync(path.join(capsuleRoot, "test", "crack"))) {
    throw new Error(`MVTec capsule not found under ${capsuleRoot}`);
  }
  const datasetDir = fs.mkdtempSync(path.join(os.tmpdir(), "segvision-mvtec-capsule-"));
  const result = JSON.parse(
    execFileSync(pythonBin(), [path.join(here, "stage-dataset-capsule.py"), datasetDir, "--source", capsuleRoot], {
      cwd: repoRoot,
      encoding: "utf8",
    }),
  ) as { root: string; items: StagedItem[] };
  return { datasetDir: result.root, items: result.items };
}

export async function startStack(
  outputDir: string,
  datasetDir: string,
  options: { preferReal?: boolean } = {},
): Promise<RunningStack> {
  const secret = "e2e-secret";
  const uiPort = await freePort();
  const env = {
    ...process.env,
    CUDA_VISIBLE_DEVICES: "-1",
    PYTHONUNBUFFERED: "1",
  };
  const sidecarArgs = [
    "-m",
    "segvision.transport.desktop_api",
    "--secret",
    secret,
    "--port",
    "0",
    "--actor",
    "scripted_test",
    "--dev-origin",
    `http://127.0.0.1:${uiPort}`,
  ];
  if (options.preferReal) sidecarArgs.push("--prefer-real");
  const sidecar = spawn(pythonBin(), sidecarArgs, {
    cwd: repoRoot,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const readyLine = await new Promise<string>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("sidecar did not print ready JSON")), 20000);
    sidecar.stdout.once("data", (chunk: Buffer) => {
      clearTimeout(timer);
      resolve(String(chunk));
    });
    sidecar.once("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`sidecar exited ${code}`));
    });
  });
  const ready = JSON.parse(readyLine.split("\n")[0] ?? "{}") as { port?: number };
  const sidecarPort = Number(ready.port);
  if (!sidecarPort) throw new Error(`sidecar ready JSON missing port: ${readyLine}`);
  await waitHttp(`http://127.0.0.1:${sidecarPort}/v1/health`, 20000, {
    "X-SegVision-Launch-Secret": secret,
    "X-SegVision-Protocol-Version": "1.1",
  });

  const ui = spawn("npx", ["vite", "--host", "127.0.0.1", "--port", String(uiPort)], {
    cwd: uiRoot,
    env,
    stdio: ["ignore", "pipe", "pipe"],
    shell: true,
  });
  await waitHttp(`http://127.0.0.1:${uiPort}/`);
  return {
    sidecar,
    ui,
    sidecarPort,
    uiPort,
    secret,
    outputDir,
    datasetDir,
    items: [],
  };
}

export function e2eUrl(stack: RunningStack): string {
  const dataset = encodeURIComponent(stack.datasetDir);
  const output = encodeURIComponent(stack.outputDir);
  return (
    `http://127.0.0.1:${stack.uiPort}/?e2e=1` +
    `&sidecar=http://127.0.0.1:${stack.sidecarPort}` +
    `&secret=${stack.secret}` +
    `&dataset=${dataset}` +
    `&output=${output}`
  );
}

export function stopStack(stack: RunningStack): void {
  killTree(stack.ui);
  killTree(stack.sidecar);
}
