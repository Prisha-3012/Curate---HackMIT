import { defineConfig } from "@playwright/test";

/**
 * Voice capture needs a microphone. Chrome's fake device grants and feeds one
 * without hardware, so getUserMedia and MediaRecorder run for real — only the
 * transcription response is stubbed.
 */
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  timeout: 60000,
  use: {
    baseURL: "http://127.0.0.1:3000",
    channel: "chrome",
    permissions: ["microphone"],
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
      ],
    },
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: true,
    timeout: 120000,
    env: {
      NEXT_PUBLIC_DEMO_MODE: "false",
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8000/api",
      NEXT_PUBLIC_DEMO_USER_ID: "00000000-0000-0000-0000-000000000001",
    },
  },
});
