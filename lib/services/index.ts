import { DEMO_MODE } from "../demo-data";
import type { DemoFixture } from "../types";
import { createMockEnoughService } from "./mockEnoughService";
export function getEnoughService(fixture: DemoFixture) {
  if (!DEMO_MODE)
    throw new Error(
      "Backend integration is not enabled. Use DEMO_MODE for local fixtures.",
    );
  return createMockEnoughService(fixture);
}
