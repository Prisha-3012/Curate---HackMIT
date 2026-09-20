import { defineConfig } from "@playwright/test";
/** Requires the unmodified backend running with DEMO_MODE=off on port 8000. */
export default defineConfig({
  testDir: "./tests",
  testMatch: "real-stack.spec.ts",
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:3000",
    channel: "chrome",
    reducedMotion: "reduce",
    viewport: { width: 1440, height: 1050 },
  },
  webServer: {
    command: "npm run build && npm run start -- --hostname 127.0.0.1",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: false,
    timeout: 120000,
    env: {
      NEXT_PUBLIC_DEMO_MODE: "false",
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000/api",
      NEXT_PUBLIC_DEMO_USER_ID: "00000000-0000-0000-0000-000000000001",
    },
  },
});
