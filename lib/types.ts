export type AppStage =
  "mission" | "understanding" | "searching" | "optimizing" | "plan";
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
export interface Need {
  id: string;
  category: string;
  label: string;
  priority: "required" | "preferred";
}
export interface Preference {
  id: string;
  label: string;
  weight: number;
}
export interface Mission {
  rawInput: string;
  title: string;
  budget: number;
  duration: string;
  location: string;
  needs: Need[];
  preferences: Preference[];
}
export interface Resource {
  id: string;
  name: string;
  category: string;
  source: ResourceSource;
  price: number;
  retailPrice: number;
  distanceMiles?: number;
  ownerName?: string;
  condition?: string;
  image?: string;
  confidence?: number;
  description: string;
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
  nearbyResources: number;
}
export interface SearchSource {
  id: string;
  label: string;
  subtitle: string;
  sources: ResourceSource[];
  checked: number;
}
export interface UserFeedback {
  resourceId: string;
  reason: "distance" | "price" | "condition" | "ownership" | "other";
}
