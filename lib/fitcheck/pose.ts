/**
 * In-browser pose estimation via MediaPipe Tasks Vision (WASM).
 *
 * Loads the vision bundle + pose model from a CDN at runtime, so there is no
 * build dependency and this ships on Vercel unchanged. Runs the pose landmarker
 * on a captured frame and returns pixel-space keypoints named the same way as
 * cv/pose_estimation.py, so the measurement port consumes them directly.
 */

import type { Keypoints, Point } from "./measure";

const VISION_CDN = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";

// BlazePose 33-landmark indices → the names measurement.ts expects.
const IDX: Record<string, number> = {
  nose: 0,
  left_eye: 2,
  right_eye: 5,
  left_shoulder: 11,
  right_shoulder: 12,
  left_elbow: 13,
  right_elbow: 14,
  left_wrist: 15,
  right_wrist: 16,
  left_hip: 23,
  right_hip: 24,
  left_knee: 25,
  right_knee: 26,
  left_ankle: 27,
  right_ankle: 28,
  left_heel: 29,
  right_heel: 30,
};

const CRITICAL = ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_ankle", "right_ankle"];

export interface PoseResult {
  keypoints: Keypoints;
  visibility: Record<string, number>;
  width: number;
  height: number;
}

export class PoseError extends Error {}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let landmarkerPromise: Promise<any> | null = null;

async function getLandmarker() {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      // Runtime CDN import; webpackIgnore keeps Next from trying to bundle it.
      const vision = await import(
        /* webpackIgnore: true */ `${VISION_CDN}/vision_bundle.mjs`
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ) as any;
      const fileset = await vision.FilesetResolver.forVisionTasks(`${VISION_CDN}/wasm`);
      return vision.PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: MODEL_URL },
        runningMode: "IMAGE",
        numPoses: 1,
        minPoseDetectionConfidence: 0.5,
      });
    })();
  }
  return landmarkerPromise;
}

/** Warm the model up front (e.g. when the fit-check modal opens). */
export async function preloadPose(): Promise<void> {
  try {
    await getLandmarker();
  } catch {
    /* surfaced later on detect */
  }
}

export async function detectPose(
  source: HTMLCanvasElement | HTMLImageElement | HTMLVideoElement,
  width: number,
  height: number,
  minVisibility = 0.4,
): Promise<PoseResult> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let landmarker: any;
  try {
    landmarker = await getLandmarker();
  } catch (e) {
    throw new PoseError("Could not load the pose model. Check your connection and try again.");
  }

  const result = landmarker.detect(source);
  const sets = result?.landmarks;
  if (!sets || sets.length === 0) {
    throw new PoseError("No person detected. Stand back so your whole body is in frame, facing the camera.");
  }
  const lms = sets[0];

  const keypoints: Keypoints = {};
  const visibility: Record<string, number> = {};
  for (const [name, idx] of Object.entries(IDX)) {
    const lm = lms[idx];
    if (!lm) continue;
    keypoints[name] = [lm.x * width, lm.y * height] as Point;
    visibility[name] = typeof lm.visibility === "number" ? lm.visibility : 1;
  }

  const missing = CRITICAL.filter((n) => !keypoints[n] || visibility[n] < minVisibility);
  if (missing.length) {
    throw new PoseError("Step back so your full body — head to feet — is in frame, facing the camera.");
  }
  return { keypoints, visibility, width, height };
}
