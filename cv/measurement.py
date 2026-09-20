"""
Measurement engine (FitCheck CV pipeline, stage 2).

Converts pixel-space keypoints from pose_estimation.py into real-world
centimeter measurements, using the user's self-reported height as the only
scale reference (no calibration object, no camera intrinsics — this is the
whole trick that makes "just a photo + height" work).

HONEST LIMITATIONS (say these in the pitch, don't hide them):
- MediaPipe has no "top of head" landmark, so total height is approximated as
  eye-level-to-heel plus a fixed head-crown correction. This is a standard
  anthropometric approximation, not a measured value.
- Girth measurements (chest/waist/hip circumference) CANNOT be reliably
  derived from a single frontal photo's WIDTH when clothing is loose — real
  testing on an actual person found MediaPipe's hip landmarks shift toward
  the visible fabric silhouette under baggy pants, not the real joint
  (produced an anatomically impossible 21cm hip width on a real 6ft person).
  Shoulder width, height, arm length, and torso length are more robust
  (bony/joint landmarks, less obscured by typical clothing) — circumference
  is the one that needs a second, clothing-independent signal. See the
  height+weight fallback below, which is what most "no-photo" size quizzes
  already rely on.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional
import numpy as np

from pose_estimation import PoseResult, _dist

# Eye-level-to-crown-of-head is roughly 6-7% of total standing height for an
# adult (anthropometric tables vary slightly by population). We use 6.5%.
HEAD_CROWN_CORRECTION = 0.065

# Converts a frontal shoulder/hip WIDTH into an estimated circumference,
# treating the torso cross-section as an ellipse with the measured width as
# the major axis and a fixed width:depth ratio. This is a coarse stand-in —
# only trustworthy when the width measurement itself passed
# validate_measurements(); see the fallback below for when it doesn't.
#
# CALIBRATION NOTE: 2.9 was an untested "average build" guess and produced a
# real miscalibration — tested against a real person (38.3cm shoulder width,
# self-reported as wearing size Medium tops), it predicted XL (111cm chest)
# instead of M (~94-102cm, midpoint 98cm). Back-solving from that one real
# data point (98 / 38.3) gives ~2.56. This is still a SINGLE anecdotal
# calibration point (self-reported clothing size varies by brand/fit
# preference, isn't a lab measurement) — treat 2.56 as "less wrong than 2.9",
# not "correct". Add real tape-measured chest circumference data points to
# calibrate.py the same way HIP_COEFFS/WAIST_COEFFS get calibrated, and this
# constant should ideally vary by build (BMI) rather than being one global
# number at all — that's the real fix if there's time for it.
CIRCUMFERENCE_SHAPE_FACTOR = 2.56  # width_cm * this ≈ circumference_cm

# --- height+weight circumference fallback ---
# These are ROUGH STARTING COEFFICIENTS for circumference_cm = a*height_cm +
# b*weight_kg + c, NOT a cited published formula — don't present them as
# clinically validated. They're a reasonable starting point (built from
# general BMI/circumference relationships) meant to be REPLACED with real
# coefficients fit on your own team's measurements via calibrate.py before
# the demo. This is the "real-time testable" fix: get 3-4 people to self-report
# height+weight and have someone tape-measure their actual waist/hip, run
# calibrate.py on that data, paste the fitted coefficients in here.
WAIST_COEFFS = {"a": 0.20, "b": 0.87, "c": -5.0}   # a*height_cm + b*weight_kg + c
HIP_COEFFS = {"a": 0.25, "b": 0.62, "c": 10.0}


def estimate_circumference_from_height_weight(height_cm: float, weight_kg: float,
                                               coeffs: dict) -> float:
    return coeffs["a"] * height_cm + coeffs["b"] * weight_kg + coeffs["c"]


@dataclass
class BodyMeasurements:
    height_cm: float  # the input, echoed back for the record
    shoulder_width_cm: float
    hip_width_cm: float
    torso_length_cm: float  # shoulder midpoint to hip midpoint
    arm_length_cm: float  # shoulder to wrist, averaged L/R
    inseam_cm: float  # hip to ankle, averaged L/R

    # Photo-based (width -> ellipse-approx circumference). Always computed,
    # but only trustworthy if hip_width_cm/shoulder_width_cm passed
    # validate_measurements().
    photo_est_chest_circumference_cm: float
    photo_est_hip_circumference_cm: float

    # height+weight regression fallback. None if weight wasn't provided.
    hw_est_waist_circumference_cm: Optional[float]
    hw_est_hip_circumference_cm: Optional[float]

    # What compute_measurements() actually recommends using, chosen
    # automatically based on plausibility (see the `source` fields).
    final_hip_circumference_cm: float
    hip_circumference_source: str  # "photo" or "height_weight_fallback" or "photo_unvalidated"

    pixel_scale_cm_per_px: float  # for debugging / showing your work


def compute_measurements(pose: PoseResult, known_height_cm: float,
                          weight_kg: Optional[float] = None) -> BodyMeasurements:
    kp = pose.keypoints_px

    eye_y = (kp["left_eye"][1] + kp["right_eye"][1]) / 2.0
    heel_y = (kp["left_heel"][1] + kp["right_heel"][1]) / 2.0
    eye_to_heel_px = abs(heel_y - eye_y)

    # Total height in pixels = eye-to-heel, grossed up for the head-crown gap.
    total_height_px = eye_to_heel_px / (1.0 - HEAD_CROWN_CORRECTION)

    if total_height_px <= 0:
        raise ValueError("Degenerate pose: eye and heel landmarks coincide.")

    scale = known_height_cm / total_height_px  # cm per pixel

    shoulder_width_px = _dist(kp["left_shoulder"], kp["right_shoulder"])
    hip_width_px = _dist(kp["left_hip"], kp["right_hip"])

    shoulder_mid = (
        (kp["left_shoulder"][0] + kp["right_shoulder"][0]) / 2.0,
        (kp["left_shoulder"][1] + kp["right_shoulder"][1]) / 2.0,
    )
    hip_mid = (
        (kp["left_hip"][0] + kp["right_hip"][0]) / 2.0,
        (kp["left_hip"][1] + kp["right_hip"][1]) / 2.0,
    )
    torso_length_px = _dist(shoulder_mid, hip_mid)

    left_arm_px = _dist(kp["left_shoulder"], kp["left_elbow"]) + _dist(kp["left_elbow"], kp["left_wrist"])
    right_arm_px = _dist(kp["right_shoulder"], kp["right_elbow"]) + _dist(kp["right_elbow"], kp["right_wrist"])
    arm_length_px = (left_arm_px + right_arm_px) / 2.0

    left_inseam_px = _dist(kp["left_hip"], kp["left_knee"]) + _dist(kp["left_knee"], kp["left_ankle"])
    right_inseam_px = _dist(kp["right_hip"], kp["right_knee"]) + _dist(kp["right_knee"], kp["right_ankle"])
    inseam_px = (left_inseam_px + right_inseam_px) / 2.0

    shoulder_width_cm = round(shoulder_width_px * scale, 1)
    hip_width_cm = round(hip_width_px * scale, 1)

    photo_chest = round(shoulder_width_cm * CIRCUMFERENCE_SHAPE_FACTOR, 1)
    photo_hip = round(hip_width_cm * CIRCUMFERENCE_SHAPE_FACTOR, 1)

    hw_waist = hw_hip = None
    if weight_kg is not None:
        hw_waist = round(estimate_circumference_from_height_weight(known_height_cm, weight_kg, WAIST_COEFFS), 1)
        hw_hip = round(estimate_circumference_from_height_weight(known_height_cm, weight_kg, HIP_COEFFS), 1)

    # Decide which hip circumference to actually trust. Plausibility check
    # mirrors validate_measurements()'s hip-width bounds, done here directly
    # on the width so we can pick a source before returning.
    hip_width_plausible = 28 <= hip_width_cm <= 45
    ratio_plausible = (shoulder_width_cm > 0 and 0.55 <= hip_width_cm / shoulder_width_cm <= 1.15)

    if hip_width_plausible and ratio_plausible:
        final_hip = photo_hip
        source = "photo"
    elif hw_hip is not None:
        final_hip = hw_hip
        source = "height_weight_fallback"
    else:
        # No weight provided to fall back on — report the photo number but
        # flag it as unvalidated so callers don't silently trust it.
        final_hip = photo_hip
        source = "photo_unvalidated"

    return BodyMeasurements(
        height_cm=known_height_cm,
        shoulder_width_cm=shoulder_width_cm,
        hip_width_cm=hip_width_cm,
        torso_length_cm=round(torso_length_px * scale, 1),
        arm_length_cm=round(arm_length_px * scale, 1),
        inseam_cm=round(inseam_px * scale, 1),
        photo_est_chest_circumference_cm=photo_chest,
        photo_est_hip_circumference_cm=photo_hip,
        hw_est_waist_circumference_cm=hw_waist,
        hw_est_hip_circumference_cm=hw_hip,
        final_hip_circumference_cm=final_hip,
        hip_circumference_source=source,
        pixel_scale_cm_per_px=round(scale, 4),
    )


def validate_measurements(m: BodyMeasurements) -> list:
    """
    Catches anatomically implausible results BEFORE they reach a size
    recommendation. Found necessary by testing on a real photo: loose/baggy
    clothing doesn't just lower MediaPipe's landmark confidence (see
    pose_estimation.py's threshold note) — it can shift the landmark's
    actual PIXEL POSITION, because the model anchors to visible fabric edges
    rather than the real joint underneath. A real 6ft person in baggy pants
    produced a 21cm hip width in testing — anatomically impossible (normal
    adult range is roughly 28-45cm) — while shoulder width and height came
    out fine.

    compute_measurements() already auto-falls-back to the height+weight
    estimate when this would fire on hip width (see hip_circumference_source)
    — this function is for surfacing the warning to the user/logs, not for
    gating the fallback itself.

    Returns a list of human-readable warning strings; empty list = looks sane.
    """
    warnings = []

    if not (28 <= m.hip_width_cm <= 45):
        warnings.append(
            f"Hip width ({m.hip_width_cm}cm) is outside the plausible adult "
            "range (28-45cm) — likely loose clothing throwing off the hip "
            "landmarks, not a real measurement."
        )

    if m.shoulder_width_cm > 0:
        ratio = m.hip_width_cm / m.shoulder_width_cm
        if not (0.55 <= ratio <= 1.15):
            warnings.append(
                f"Hip/shoulder width ratio ({ratio:.2f}) is atypical — "
                "one of the two measurements is probably wrong, not a real "
                "body shape."
            )

    if not (30 <= m.shoulder_width_cm <= 60):
        warnings.append(
            f"Shoulder width ({m.shoulder_width_cm}cm) is outside the "
            "plausible adult range (30-60cm)."
        )

    if m.hip_circumference_source == "height_weight_fallback":
        warnings.append(
            "Hip circumference used the height+weight fallback, not the "
            "photo — the photo-based width measurement failed plausibility "
            "checks (see above)."
        )
    elif m.hip_circumference_source == "photo_unvalidated":
        warnings.append(
            "Hip width failed plausibility checks and no weight was given "
            "to fall back on — the reported hip circumference is unreliable. "
            "Ask for weight, or recapture in fitted clothing."
        )

    return warnings


if __name__ == "__main__":
    import sys
    from pose_estimation import extract_keypoints

    if len(sys.argv) not in (3, 4):
        print("Usage: python measurement.py <image_path> <height_cm> [weight_kg]")
        sys.exit(1)

    weight = float(sys.argv[3]) if len(sys.argv) == 4 else None
    pose = extract_keypoints(sys.argv[1])
    measurements = compute_measurements(pose, float(sys.argv[2]), weight_kg=weight)
    for k, v in asdict(measurements).items():
        print(f"  {k:32s} {v}")
    warnings = validate_measurements(measurements)
    if warnings:
        print("\n  WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
