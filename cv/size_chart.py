"""
Size mapper + fit-confidence scoring (FitCheck CV pipeline, stage 3).

Takes BodyMeasurements and scores them against a small brand size chart.
Per the plan doc: keep this to 2-3 brands with simple, scrapeable charts
rather than trying to be broad. These numbers below are PLACEHOLDER /
representative unisex top charts for demo purposes — swap in real scraped
brand charts before the actual demo (D's seed-data task, or whoever ends up
owning it now that D is on the SMS channel).
"""

from dataclasses import dataclass
from typing import Optional
from measurement import BodyMeasurements

# chest/shoulder ranges in cm, per brand per size.
# shoulder_cm here is shoulder-to-shoulder width; chest_cm is circumference.
BRAND_SIZE_CHARTS = {
    "genericbrand_unisex_tops": {
        "XS": {"chest_cm": (78, 86), "shoulder_cm": (38, 41)},
        "S":  {"chest_cm": (86, 94), "shoulder_cm": (41, 44)},
        "M":  {"chest_cm": (94, 102), "shoulder_cm": (44, 47)},
        "L":  {"chest_cm": (102, 110), "shoulder_cm": (47, 50)},
        "XL": {"chest_cm": (110, 118), "shoulder_cm": (50, 53)},
    },
    "genericbrand_slim_tops": {
        # A brand that runs narrower — same measurements can map to a
        # different size here, which is the whole point of per-brand charts.
        "XS": {"chest_cm": (74, 82), "shoulder_cm": (36, 39)},
        "S":  {"chest_cm": (82, 90), "shoulder_cm": (39, 42)},
        "M":  {"chest_cm": (90, 98), "shoulder_cm": (42, 45)},
        "L":  {"chest_cm": (98, 106), "shoulder_cm": (45, 48)},
        "XL": {"chest_cm": (106, 114), "shoulder_cm": (48, 51)},
    },
}


@dataclass
class FitResult:
    brand: str
    recommended_size: Optional[str]
    confidence: float  # 0..1
    per_measurement: dict  # measurement_name -> {size, score} for transparency
    notes: str


def _score_against_range(value: float, low: float, high: float) -> float:
    """
    1.0 if value sits in the middle of the range, tapering to 0 at the edges,
    and 0 outside the range. Simple triangular membership function — good
    enough to rank candidate sizes without pretending to more precision than
    a single-photo estimate actually has.
    """
    if value < low or value > high:
        # small tolerance band just outside the range before hard-zeroing,
        # since our own measurement error (see measurement.py limitations)
        # is easily a few cm.
        tolerance = (high - low) * 0.15
        if low - tolerance <= value < low:
            return max(0.0, 1.0 - (low - value) / tolerance) * 0.5
        if high < value <= high + tolerance:
            return max(0.0, 1.0 - (value - high) / tolerance) * 0.5
        return 0.0
    mid = (low + high) / 2.0
    half_range = (high - low) / 2.0
    return 1.0 - abs(value - mid) / half_range


def fit_confidence(measurements: BodyMeasurements, brand: str = None, chart: dict = None) -> FitResult:
    """
    Score measurements against a size chart. Pass either `brand` (a key in the
    built-in BRAND_SIZE_CHARTS) or `chart` (a chart dict supplied by a product
    spec — see product.py). `chart` takes precedence when both are given.
    """
    if chart is None:
        if brand not in BRAND_SIZE_CHARTS:
            raise ValueError(f"Unknown brand '{brand}'. Known: {list(BRAND_SIZE_CHARTS)}")
        chart = BRAND_SIZE_CHARTS[brand]
        brand_label = brand
    else:
        brand_label = brand or "product"

    best_size = None
    best_score = -1.0
    per_measurement = {}

    # also track the nearest size by distance, so we never return "None" when a
    # real chart exists — if the body is outside every size's range (e.g. a slim
    # person + a very oversized garment), the closest size is still the answer.
    v_chest = measurements.photo_est_chest_circumference_cm
    nearest_size = None
    nearest_dist = float("inf")

    for size, ranges in chart.items():
        lo, hi = ranges["chest_cm"]
        chest_score = _score_against_range(v_chest, lo, hi)
        dist = 0.0 if lo <= v_chest <= hi else min(abs(v_chest - lo), abs(v_chest - hi))
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_size = size

        if "shoulder_cm" in ranges and ranges["shoulder_cm"]:
            shoulder_score = _score_against_range(
                measurements.shoulder_width_cm, *ranges["shoulder_cm"]
            )
            combined = 0.6 * chest_score + 0.4 * shoulder_score
        else:
            shoulder_score = None
            combined = chest_score  # chest-only when no shoulder range
        per_measurement[size] = {
            "chest_score": round(chest_score, 2),
            "shoulder_score": round(shoulder_score, 2) if shoulder_score is not None else None,
            "combined": round(combined, 2),
        }
        if combined > best_score:
            best_score = combined
            best_size = size

    if best_score > 0:
        rec_size = best_size
        confidence = round(best_score, 2)
        if best_score < 0.35:
            notes = ("Low confidence — measurements sit between sizes. Consider "
                     "the neighboring size too.")
        elif best_score < 0.6:
            notes = "Moderate confidence — borderline between two adjacent sizes."
        else:
            notes = ""
    else:
        # body is outside every size's range → recommend the closest size
        rec_size = nearest_size
        confidence = 0.2
        notes = (f"Your chest (~{v_chest}cm) is outside this item's listed range; "
                 f"{nearest_size} is the closest fit ({nearest_dist:.0f}cm off). "
                 "Treat as approximate.")

    return FitResult(
        brand=brand_label,
        recommended_size=rec_size,
        confidence=confidence,
        per_measurement=per_measurement,
        notes=notes,
    )


if __name__ == "__main__":
    import sys
    from pose_estimation import extract_keypoints
    from measurement import compute_measurements

    if len(sys.argv) != 4:
        print("Usage: python size_chart.py <image_path> <height_cm> <brand>")
        print(f"Known brands: {list(BRAND_SIZE_CHARTS)}")
        sys.exit(1)

    pose = extract_keypoints(sys.argv[1])
    m = compute_measurements(pose, float(sys.argv[2]))
    result = fit_confidence(m, sys.argv[3])
    print(f"Recommended size: {result.recommended_size}  (confidence {result.confidence})")
    print(result.notes)
    for size, scores in result.per_measurement.items():
        print(f"  {size}: {scores}")
