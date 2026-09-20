import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  testMatch: "backend-browser.spec.ts",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3002", channel: "chrome" },
  webServer: {
    command:
      "npm run build && npm run start -- --hostname 127.0.0.1 --port 3002",
    url: "http://127.0.0.1:3002",
    reuseExistingServer: false,
    timeout: 120000,
    env: {
      NEXT_PUBLIC_DEMO_MODE: "false",
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000/api",
      NEXT_PUBLIC_DEMO_USER_ID: "test-user",
    },
  },
});
