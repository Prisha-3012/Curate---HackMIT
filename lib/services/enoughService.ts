import type { MissionExperience } from "../types";
export interface EnoughService {
  prepareMission(
    input: string,
    signal?: AbortSignal,
    /**
     * Overrides the budget parsed out of `input`. /api/converse gathers the
     * budget as its own turn, so it is not in the goal text — and undefined
     * must stay distinct from null, which means "explicitly no budget".
     */
    budgetCents?: number | null,
  ): Promise<MissionExperience>;
}
