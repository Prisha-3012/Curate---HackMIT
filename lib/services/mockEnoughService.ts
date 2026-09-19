import { TIMING } from "../demo-data";
import { prepareFixture } from "../plan";
import type { DemoFixture } from "../types";
import type { EnoughService } from "./enoughService";
export function waitForDemo(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Cancelled", "AbortError"));
      return;
    }
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException("Cancelled", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", abort, { once: true });
  });
}
export function createMockEnoughService(fixture: DemoFixture): EnoughService {
  return {
    async prepareMission(input, signal) {
      await waitForDemo(TIMING.understand, signal);
      return prepareFixture(fixture, input);
    },
  };
}
