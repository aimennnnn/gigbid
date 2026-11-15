import { defineConfig } from "@playwright/test";

// Starts the API with stand-in models (no key, no network) and the built web app, then runs the specs in Chrome.
// Run `npm run build` first. Locally: `npm run test:e2e`.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  workers: 1, // the degraded-mode test switches the shared simulator off for a moment
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: "http://localhost:3000", channel: "chrome", trace: "retain-on-failure" },
  projects: [
    { name: "laptop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "phone", use: { viewport: { width: 390, height: 844 } }, grep: /@phone/ },
  ],
  webServer: [
    {
      command: "uv run uvicorn apps.api.main:app --port 8000",
      cwd: "../..",
      url: "http://localhost:8000/docs",
      reuseExistingServer: true,
      timeout: 120_000,
      env: { GIGBID_LLM: "fake", GIGBID_RAG_MODELS: "fake", GIGSIM_ERROR_RATE: "0", GIGBID_STATE_DIR: "data/processed/app-e2e" },
    },
    { command: "npm run start", url: "http://localhost:3000/login", reuseExistingServer: true, timeout: 120_000 },
  ],
});
