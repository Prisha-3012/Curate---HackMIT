"""
Calibrate the height+weight -> circumference fallback formula using YOUR
OWN team's real measurements. This is the fast, low-risk way to get a
"real" (data-fit, not guessed) formula instead of the rough defaults in
measurement.py, without pulling in a full 3D body-shape model (ROMP/SMPL)
under time pressure.

HOW TO USE (takes ~10 minutes with 3-4 people):
1. Grab a tape measure or a length of string + ruler.
2. For each person: record height (cm), weight (kg), and ACTUAL measured
   waist circumference and hip circumference (wrap the tape around the
   widest point, snug but not tight).
3. Add each row to WAIST_DATA / HIP_DATA below as (height_cm, weight_kg, measured_cm).
4. Run: python3 calibrate.py
5. Paste the printed coefficients into measurement.py's WAIST_COEFFS / HIP_COEFFS.

More people = better fit. 3 is a bare minimum (3 unknowns: a, b, c) — more
than 3 lets it average out measurement noise instead of fitting it exactly.
If you only have time to measure ONE circumference (waist OR hip), that's
still strictly better than the current guessed defaults.
"""

import numpy as np

# --- FILL THESE IN WITH REAL DATA FROM YOUR TEAM ---
# (height_cm, weight_kg, measured_waist_circumference_cm)
WAIST_DATA = [
    # (175.0, 70.0, 82.0),
    # (182.88, 78.0, 88.0),
]

# (height_cm, weight_kg, measured_hip_circumference_cm)
HIP_DATA = [
    # (175.0, 70.0, 95.0),
    # (182.88, 78.0, 98.0),
]


def fit_coeffs(data, label):
    if len(data) < 3:
        print(f"[{label}] Need at least 3 data points to fit a,b,c — got {len(data)}. Skipping.")
        return None

    heights = np.array([d[0] for d in data])
    weights = np.array([d[1] for d in data])
    measured = np.array([d[2] for d in data])

    # Solve measured = a*height + b*weight + c via least squares.
    A = np.column_stack([heights, weights, np.ones(len(data))])
    (a, b, c), residuals, rank, sv = np.linalg.lstsq(A, measured, rcond=None)

    predicted = A @ np.array([a, b, c])
    errors = predicted - measured
    print(f"[{label}] Fitted on {len(data)} people:")
    print(f"  a (height coeff) = {a:.4f}")
    print(f"  b (weight coeff) = {b:.4f}")
    print(f"  c (intercept)    = {c:.4f}")
    print(f"  Mean absolute error on training data: {np.mean(np.abs(errors)):.1f}cm")
    print(f"  (this is fit error, not held-out accuracy — with only a few points "
          f"it WILL look better than it really is; don't oversell this number)")
    print(f"  -> paste into measurement.py: {{'a': {a:.4f}, 'b': {b:.4f}, 'c': {c:.4f}}}")
    print()
    return {"a": round(a, 4), "b": round(b, 4), "c": round(c, 4)}


if __name__ == "__main__":
    print("=== Waist circumference fit ===")
    waist_coeffs = fit_coeffs(WAIST_DATA, "waist")
    print("=== Hip circumference fit ===")
    hip_coeffs = fit_coeffs(HIP_DATA, "hip")

    if waist_coeffs is None and hip_coeffs is None:
        print("No data yet — fill in WAIST_DATA and/or HIP_DATA at the top of this file first.")
