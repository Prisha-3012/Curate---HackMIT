export type AppStage =
  | "mission"
  | "conversation"
  | "understanding"
  | "searching"
  | "optimizing"
  | "plan";
export type OttoState =
  | "idle"
  | "thinking"
  | "scanning"
  | "searching"
  | "optimizing"
  | "learning"
  | "success";
export type ResourceSource =
  "owned" | "borrow" | "share" | "used" | "rent" | "new";
/** Abstract artwork hints, never inferred categories or suitability claims. */
export type VisualMotif =
  "fold" | "frame" | "vessel" | "beam" | "shelter" | "stack";
export interface Resource {
  id: string;
  name: string;
  category?: string;
  source: ResourceSource;
  rung?: string;
  price: number;
  retailPrice: number;
  description: string;
  distanceMiles?: number;
  ownerName?: string;
  condition?: string;
  image?: string;
  imageAlt?: string;
  visual?: VisualMotif;
  matchScore?: number;
  needsFitcheck?: boolean;
}
export interface NeedGroup {
  id: string;
  label: string;
}
export interface Need {
  id: string;
  label: string;
  category?: string;
  group?: NeedGroup;
  rationale?: string;
  priority: "required" | "preferred";
  /** Preserve provider order: a higher score does not outrank an earlier source. */
  options: Resource[];
  recommendedOptionId: string | null;
  /** Optional future user selection; absent means use the recommendation. */
  selectedOptionId?: string;
  recommendationReason?: string;
  unmetReason?: string;
}
export interface Preference {
  id: string;
  label: string;
  weight: number;
}
export interface Mission {
  id?: string;
  rawInput: string;
  title: string;
  /** null means no budget stated; zero is a real constraint. */
  budget: number | null;
  duration?: string;
  location?: string;
  needs: Need[];
  preferences?: Preference[];
}
export interface PlanItem {
  needId: string;
  resource: Resource;
  reasoning: string;
}
export interface OptimizedPlan {
  items: PlanItem[];
  totalCost: number;
  retailEquivalent: number;
  savings: number;
  newPurchasesAvoided: number;
  reusedResources: number;
  reuseLabel?: string;
  textileKgAvoided?: number;
  /** Unknown when no selected resource supplies a distance. */
  nearbyResources?: number;
  unmetNeedIds: string[];
  totalNeeds: number;
  impactAssumptions: string;
}
export interface SearchSource {
  id: string;
  label: string;
  subtitle: string;
  sources: ResourceSource[];
  checked?: number;
}
export interface ExperienceCopy {
  exampleLabel: string;
  placeholder: string;
  disclosure: string;
  summary: string;
  planCollectionLabel: string;
  planNote: string;
  completion: string;
  optimizationCriteria?: string;
}
export interface DemoFixture {
  id: string;
  label: string;
  badge: string;
  mission: Mission;
  sources: SearchSource[];
  copy: ExperienceCopy;
  impactAssumptions: string;
  optimizationNeedId?: string;
}
export interface MissionExperience {
  mission: Mission;
  sources: SearchSource[];
  copy: ExperienceCopy;
  plan: OptimizedPlan;
  optimizationNeedId?: string;
  provenance: "local-fixture" | "backend-live" | "backend-demo";
  backendFixture?: string;
}
export interface UserFeedback {
  resourceId: string;
  reason: "distance" | "price" | "condition" | "ownership" | "other";
}
