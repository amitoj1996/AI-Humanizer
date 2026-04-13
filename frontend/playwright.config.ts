import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright config — end-to-end smoke tests for the AI Humanizer UI.
 *
 * `webServer` starts BOTH the backend (with a FakeRegistry + mocked Ollama,
 * so no HuggingFace models or live Ollama required) and the frontend dev
 * server.  Both are killed when the test run finishes.
 */
const BACKEND_PORT = 8001;
const FRONTEND_PORT = 3001;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false, // we have a single backend; keep tests sequential
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  // Nuke ./e2e-data before every run so the first-test "No projects yet"
  // assertion is deterministic across local re-runs.
  globalSetup: "./e2e/globalSetup.ts",
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: [
    {
      command: "../backend/venv/bin/python ../backend/run_test_server.py",
      port: BACKEND_PORT,
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
      env: {
        AI_HUMANIZER_TEST_PORT: String(BACKEND_PORT),
        AI_HUMANIZER_DATA_DIR: "./e2e-data",
        AI_HUMANIZER_DB_PATH: "./e2e-data/e2e.db",
      },
    },
    {
      command: `next dev --port ${FRONTEND_PORT}`,
      port: FRONTEND_PORT,
      timeout: 60_000,
      reuseExistingServer: !process.env.CI,
      env: {
        NEXT_PUBLIC_API_BASE: `http://127.0.0.1:${BACKEND_PORT}`,
      },
    },
  ],
});
