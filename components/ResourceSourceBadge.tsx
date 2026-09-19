import type { ResourceSource } from "@/lib/types";
const labels: Record<ResourceSource, string> = {
  owned: "ALREADY OWN",
  borrow: "BORROW",
  share: "SHARE",
  used: "USED",
  rent: "RENT",
  new: "BUY NEW",
};
export function ResourceSourceBadge({ source }: { source: ResourceSource }) {
  return (
    <span className={`source-badge source-${source}`}>{labels[source]}</span>
  );
}
