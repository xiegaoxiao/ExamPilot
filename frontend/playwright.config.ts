import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  workers: 1,
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:8001",
    headless: true,
    screenshot: "only-on-failure",
  },
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 30000,
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: '"../.venv/Scripts/python.exe" ../backend/tests/serve_e2e.py',
        url: "http://127.0.0.1:8001/api/health",
        reuseExistingServer: false,
        timeout: 60000,
      },
});
