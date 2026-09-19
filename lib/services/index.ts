import { DEMO_MODE } from "../demo-data";
import { mockEnoughService } from "./mockEnoughService";
import { createEnoughApi } from "./enoughApi";
export const enoughService = DEMO_MODE
  ? mockEnoughService
  : createEnoughApi("/api");
