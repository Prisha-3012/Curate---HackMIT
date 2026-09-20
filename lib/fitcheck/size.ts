/**
 * Size scoring — a TypeScript port of cv/size_chart.py `fit_confidence`.
 *
 * Scores body measurements against a garment's size chart with a triangular
 * membership function, combines chest (0.6) and shoulder (0.4), and falls back
 * to the nearest size when the body is outside every listed range, so it never
 * returns null when a chart exists.
 */

import type { SizeChart } from "./garments";

export interface FitResult {
  recommendedSize: string;
  alternateSize: string | null;
  confidence: number; // 0..1
  band: "HIGH" | "MEDIUM" | "LOW";
  perSize: Record<string, { chest: number; shoulder: number | null; combined: number }>;
  note: string;
}

/** 1.0 mid-range, tapering to 0 at the edges, small tolerance just outside. */
function scoreAgainstRange(value: number, low: number, high: number): number {
  if (value < low || value > high) {
    const tolerance = (high - low) * 0.15;
    if (low - tolerance <= value && value < low)
      return Math.max(0, 1 - (low - value) / tolerance) * 0.5;
    if (high < value && value <= high + tolerance)
      return Math.max(0, 1 - (value - high) / tolerance) * 0.5;
    return 0;
  }
  const mid = (low + high) / 2;
  const half = (high - low) / 2;
  return 1 - Math.abs(value - mid) / half;
}

function band(confidence: number): "HIGH" | "MEDIUM" | "LOW" {
  if (confidence >= 0.75) return "HIGH";
  if (confidence >= 0.5) return "MEDIUM";
  return "LOW";
}

export function fitConfidence(
  chestCm: number,
  shoulderCm: number,
  chart: SizeChart,
): FitResult {
  let bestSize = "";
  let bestScore = -1;
  let secondSize: string | null = null;
  let secondScore = -1;
  let nearestSize = "";
  let nearestDist = Infinity;
  const perSize: FitResult["perSize"] = {};

  for (const [size, ranges] of Object.entries(chart)) {
    const [clo, chi] = ranges.chest_cm;
    const chestScore = scoreAgainstRange(chestCm, clo, chi);
    const dist = chestCm >= clo && chestCm <= chi ? 0 : Math.min(Math.abs(chestCm - clo), Math.abs(chestCm - chi));
    if (dist < nearestDist) {
      nearestDist = dist;
      nearestSize = size;
    }

    let shoulderScore: number | null = null;
    let combined: number;
    if (ranges.shoulder_cm) {
      shoulderScore = scoreAgainstRange(shoulderCm, ranges.shoulder_cm[0], ranges.shoulder_cm[1]);
      combined = 0.6 * chestScore + 0.4 * shoulderScore;
    } else {
      combined = chestScore;
    }
    perSize[size] = {
      chest: Math.round(chestScore * 100) / 100,
      shoulder: shoulderScore === null ? null : Math.round(shoulderScore * 100) / 100,
      combined: Math.round(combined * 100) / 100,
    };
    if (combined > bestScore) {
      secondScore = bestScore;
      secondSize = bestSize || null;
      bestScore = combined;
      bestSize = size;
    } else if (combined > secondScore) {
      secondScore = combined;
      secondSize = size;
    }
  }

  if (bestScore > 0) {
    const confidence = Math.round(bestScore * 100) / 100;
    let note = "";
    if (bestScore < 0.35)
      note = "Low confidence — you sit between sizes. Consider the neighboring size too.";
    else if (bestScore < 0.6)
      note = "Moderate confidence — borderline between two adjacent sizes.";
    // Only surface an alternate when it is genuinely close.
    const alt = secondSize && secondScore >= 0.4 ? secondSize : null;
    return {
      recommendedSize: bestSize,
      alternateSize: alt,
      confidence,
      band: band(confidence),
      perSize,
      note,
    };
  }

  // Body outside every range → nearest size, low confidence.
  return {
    recommendedSize: nearestSize,
    alternateSize: null,
    confidence: 0.2,
    band: "LOW",
    perSize,
    note: `Your chest (~${Math.round(chestCm)}cm) is outside this item's listed range; ${nearestSize} is the closest fit (${Math.round(nearestDist)}cm off). Treat as approximate.`,
  };
}
