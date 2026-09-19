import { calculatePlan, demoMission, resources, TIMING } from "../demo-data";
import type { EnoughService } from "./enoughService";
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
export const mockEnoughService: EnoughService = {
  async understandMission(input) {
    await delay(TIMING.understand);
    return structuredClone({ ...demoMission, rawInput: input });
  },
  async searchResources() {
    await delay(TIMING.search);
    return structuredClone(resources);
  },
  async optimizePlan(_mission, candidates) {
    await delay(TIMING.optimize);
    return calculatePlan(candidates);
  },
};
