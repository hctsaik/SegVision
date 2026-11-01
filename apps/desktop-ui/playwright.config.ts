import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: "../../playwright-report/desktop-gui", open: "never" }],
  ],
  use: {
    ...devices["Desktop Chrome"],
    screenshot: "on",
    video: "on",
    trace: "on",
    viewport: { width: 1280, height: 800 },
  },
});
