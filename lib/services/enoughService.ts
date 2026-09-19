import type { MissionExperience } from "../types";
export interface EnoughService {
  prepareMission(
    input: string,
    signal?: AbortSignal,
  ): Promise<MissionExperience>;
}
