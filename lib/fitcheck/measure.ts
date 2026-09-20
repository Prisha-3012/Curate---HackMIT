/**
 * Measurement engine — a TypeScript port of cv/measurement.py.
 *
 * Turns pixel-space pose keypoints + the person's height into cm measurements,
 * using height as the only scale reference (no calibration object). Same
 * constants and logic as the Python version, including the chest = shoulder
 * width x SHAPE_FACTOR estimate and the height+weight hip fallback.
 */

export type Point = [number, number];
export type Keypoints = Record<string, Point>;

export const HEAD_CROWN_CORRECTION = 0.065;
export const CIRCUMFERENCE_SHAPE_FACTOR = 2.56; // width_cm * this ~= circumference_cm
const WAIST_COEFFS = { a: 0.2, b: 0.87, c: -5.0 };
const HIP_COEFFS = { a: 0.25, b: 0.62, c: 10.0 };

export interface BodyMeasurements {
  heightCm: number;
  shoulderWidthCm: number;
  hipWidthCm: number;
  torsoLengthCm: number;
  armLengthCm: number;
  photoChestCircumferenceCm: number;
  photoHipCircumferenceCm: number;
  hwHipCircumferenceCm: number | null;
  finalHipCircumferenceCm: number;
  hipSource: "photo" | "height_weight_fallback" | "photo_unvalidated";
  pixelScaleCmPerPx: number;
  warnings: string[];
}

const dist = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const mid = (a: Point, b: Point): Point => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
const round1 = (n: number) => Math.round(n * 10) / 10;

export class MeasurementError extends Error {}

export function computeMeasurements(
  kp: Keypoints,
  heightCm: number,
  weightKg?: number | null,
): BodyMeasurements {
  const eyeY = (kp.left_eye[1] + kp.right_eye[1]) / 2;
  const heelY = (kp.left_heel[1] + kp.right_heel[1]) / 2;
  const eyeToHeelPx = Math.abs(heelY - eyeY);
  const totalHeightPx = eyeToHeelPx / (1 - HEAD_CROWN_CORRECTION);
  if (totalHeightPx <= 0)
    throw new MeasurementError("Degenerate pose: eye and heel landmarks coincide.");

  const scale = heightCm / totalHeightPx; // cm per pixel

  const shoulderWidthCm = round1(dist(kp.left_shoulder, kp.right_shoulder) * scale);
  const hipWidthCm = round1(dist(kp.left_hip, kp.right_hip) * scale);
  const torsoLengthCm = round1(dist(mid(kp.left_shoulder, kp.right_shoulder), mid(kp.left_hip, kp.right_hip)) * scale);

  const leftArm = dist(kp.left_shoulder, kp.left_elbow) + dist(kp.left_elbow, kp.left_wrist);
  const rightArm = dist(kp.right_shoulder, kp.right_elbow) + dist(kp.right_elbow, kp.right_wrist);
  const armLengthCm = round1(((leftArm + rightArm) / 2) * scale);

  const photoChest = round1(shoulderWidthCm * CIRCUMFERENCE_SHAPE_FACTOR);
  const photoHip = round1(hipWidthCm * CIRCUMFERENCE_SHAPE_FACTOR);

  let hwHip: number | null = null;
  if (weightKg != null) {
    hwHip = round1(HIP_COEFFS.a * heightCm + HIP_COEFFS.b * weightKg + HIP_COEFFS.c);
  }

  const hipWidthPlausible = hipWidthCm >= 28 && hipWidthCm <= 45;
  const ratioPlausible =
    shoulderWidthCm > 0 && hipWidthCm / shoulderWidthCm >= 0.55 && hipWidthCm / shoulderWidthCm <= 1.15;

  let finalHip: number;
  let hipSource: BodyMeasurements["hipSource"];
  if (hipWidthPlausible && ratioPlausible) {
    finalHip = photoHip;
    hipSource = "photo";
  } else if (hwHip != null) {
    finalHip = hwHip;
    hipSource = "height_weight_fallback";
  } else {
    finalHip = photoHip;
    hipSource = "photo_unvalidated";
  }

  const warnings: string[] = [];
  if (!(shoulderWidthCm >= 30 && shoulderWidthCm <= 60))
    warnings.push(`Shoulder width (${shoulderWidthCm}cm) is outside the plausible adult range (30-60cm) — recapture facing the camera, full body in frame.`);
  if (hipSource === "photo_unvalidated")
    warnings.push("Hip width failed plausibility checks and no weight was given — hip-based sizing is unreliable.");

  return {
    heightCm,
    shoulderWidthCm,
    hipWidthCm,
    torsoLengthCm,
    armLengthCm,
    photoChestCircumferenceCm: photoChest,
    photoHipCircumferenceCm: photoHip,
    hwHipCircumferenceCm: hwHip,
    finalHipCircumferenceCm: finalHip,
    hipSource,
    pixelScaleCmPerPx: Math.round(scale * 10000) / 10000,
    warnings,
  };
}

// void the unused waist coeffs reference so tree-shakers keep intent clear.
void WAIST_COEFFS;
