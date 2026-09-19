import type { Mission, Resource, OptimizedPlan } from "../types";
export interface EnoughService {
  understandMission(input: string): Promise<Mission>;
  searchResources(mission: Mission, inventory: Resource[]): Promise<Resource[]>;
  optimizePlan(mission: Mission, resources: Resource[]): Promise<OptimizedPlan>;
}
