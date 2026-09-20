import { DEMO_MODE } from "../demo-data";
import type { DemoFixture } from "../types";
import { createMockEnoughService } from "./mockEnoughService";
import { createEnoughApi } from "./enoughApi";
export function getEnoughService(fixture: DemoFixture) {
  return DEMO_MODE
    ? createMockEnoughService(fixture)
    : createEnoughApi(
        process.env.NEXT_PUBLIC_API_BASE_URL ?? "",
        process.env.NEXT_PUBLIC_DEMO_USER_ID ?? "",
      );
}
