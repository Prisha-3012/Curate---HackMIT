import type { EnoughService } from "./enoughService";
export function createEnoughApi(baseUrl: string): EnoughService {
  async function post<T>(path: string, payload: unknown): Promise<T> {
    const response = await fetch(`${baseUrl}/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok)
      throw new Error("Otto couldn’t finish that step. Please try again.");
    return response.json() as Promise<T>;
  }
  return {
    understandMission: (input) => post("missions/understand", { input }),
    searchResources: (mission, inventory) =>
      post("resources/search", { mission, inventory }),
    optimizePlan: (mission, resources) =>
      post("plans/optimize", { mission, resources }),
  };
}
