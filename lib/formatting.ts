/** Domain prices are USD dollars; retain cents without adding .00 to whole prices. */
export function money(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: Number.isInteger(rounded) ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(rounded);
}
export const percent = (fraction: number) => `${Math.round(fraction * 100)}%`;
