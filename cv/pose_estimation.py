"""
Pose estimation module (FitCheck CV pipeline, stage 1).

Wraps MediaPipe Pose to extract body keypoints from a single photo.
Input: a photo where the person is fully visible, standing, facing the camera
(the "capture flow" screen on the frontend should enforce this with an outline
guide — garbage in, garbage out for everything downstream).
"""

from dataclasses import dataclass
from typing import Optional
import cv2
import mediapipe as mp
import numpy as np

mp_pose = mp.solutions.pose

# The MediaPipe Pose landmark indices we actually need downstream.
# (Full list has 33 points; we only care about these for sizing.)
LANDMARK_NAMES = {
    "nose": mp_pose.PoseLandmark.NOSE,
    "left_eye": mp_pose.PoseLandmark.LEFT_EYE,
    "right_eye": mp_pose.PoseLandmark.RIGHT_EYE,
    "left_shoulder": mp_pose.PoseLandmark.LEFT_SHOULDER,
    "right_shoulder": mp_pose.PoseLandmark.RIGHT_SHOULDER,
    "left_elbow": mp_pose.PoseLandmark.LEFT_ELBOW,
    "right_elbow": mp_pose.PoseLandmark.RIGHT_ELBOW,
    "left_wrist": mp_pose.PoseLandmark.LEFT_WRIST,
    "right_wrist": mp_pose.PoseLandmark.RIGHT_WRIST,
    "left_hip": mp_pose.PoseLandmark.LEFT_HIP,
    "right_hip": mp_pose.PoseLandmark.RIGHT_HIP,
    "left_knee": mp_pose.PoseLandmark.LEFT_KNEE,
    "right_knee": mp_pose.PoseLandmark.RIGHT_KNEE,
    "left_ankle": mp_pose.PoseLandmark.LEFT_ANKLE,
    "right_ankle": mp_pose.PoseLandmark.RIGHT_ANKLE,
    "left_heel": mp_pose.PoseLandmark.LEFT_HEEL,
    "right_heel": mp_pose.PoseLandmark.RIGHT_HEEL,
    "left_foot_index": mp_pose.PoseLandmark.LEFT_FOOT_INDEX,
    "right_foot_index": mp_pose.PoseLandmark.RIGHT_FOOT_INDEX,
}


@dataclass
class PoseResult:
    keypoints_px: dict  # name -> (x_px, y_px)
    visibility: dict  # name -> 0..1 confidence from MediaPipe
    image_width: int
    image_height: int


class PoseEstimationError(Exception):
    """Raised when no person / not enough of the body is visible."""


def extract_keypoints(image_path: str, min_visibility: float = 0.4) -> PoseResult:
    """
    Run MediaPipe Pose on an image file and return pixel-space keypoints
    for the landmarks we use for sizing.

    Raises PoseEstimationError if no pose is found, or if critical landmarks
    (shoulders, hips, ankles — needed for every downstream measurement) are
    below the visibility threshold. Surface this back to the user as
    "step back so your whole body is in frame" rather than a silent bad guess.

    Threshold note (found by testing on a real photo, not a guess): baggy
    pants noticeably lower confidence on knee/ankle/heel landmarks — MediaPipe
    can't pin the exact joint location through loose fabric as well as it can
    through fitted clothing. A real, fully-visible person in loose pants can
    still land around 0.43-0.51 on ankle visibility, which is why the default
    here is 0.4 rather than something stricter like 0.6-0.7. Worth telling the
    capture-flow screen to nudge people toward fitted bottoms for a more
    confident read, rather than relying on the threshold alone.
    """
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        raise PoseEstimationError(f"Could not read image at {image_path}")

    h, w = image_bgr.shape[:2]
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    with mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,  # balanced accuracy/speed — "heavy" (2) is noticeably slower to
                              # download and run and isn't worth it for a live demo; bump to
                              # 2 only if accuracy is visibly bad and you have time to spare
        enable_segmentation=False,
        min_detection_confidence=0.5,
    ) as pose:
        results = pose.process(image_rgb)

    if not results.pose_landmarks:
        raise PoseEstimationError(
            "No person detected. Make sure you're fully visible, well-lit, "
            "and facing the camera."
        )

    landmarks = results.pose_landmarks.landmark
    keypoints_px = {}
    visibility = {}
    for name, idx in LANDMARK_NAMES.items():
        lm = landmarks[idx]
        keypoints_px[name] = (lm.x * w, lm.y * h)
        visibility[name] = lm.visibility

    critical = ["left_shoulder", "right_shoulder", "left_hip", "right_hip",
                "left_ankle", "right_ankle"]
    low_conf = [n for n in critical if visibility[n] < min_visibility]
    if low_conf:
        raise PoseEstimationError(
            f"Low confidence on: {', '.join(low_conf)}. "
            "Step back so your full body — head to feet — is in frame."
        )

    return PoseResult(
        keypoints_px=keypoints_px,
        visibility=visibility,
        image_width=w,
        image_height=h,
    )


def _dist(p1, p2) -> float:
    return float(np.hypot(p1[0] - p2[0], p1[1] - p2[1]))


def assess_framing(pose: "PoseResult",
                   min_fill_fraction: float = 0.55,
                   max_center_offset: float = 0.30,
                   min_frontal_ratio: float = 0.22):
    """
    Judge whether a photo is a GOOD input for virtual try-on, beyond just
    "is a pose present". Found necessary after real failures: (1) a wide,
    cluttered hall shot where the subject was small/off to one side produced
    a garbage try-on, and (2) a full side/profile pose, which IDM-VTON (a
    front-facing-trained model) garbles. Try-on quality is bounded by input
    quality, so reject bad frames BEFORE spending 30-60s generating on them.

    Returns (ok: bool, reason: str). reason is '' when ok.

    Checks:
      - fill fraction: person's eye->heel height / image height. Too small =
        too far away / lost in a wide shot.
      - horizontal centering: body midline shouldn't be jammed to one edge.
      - frontal-ness: shoulder width relative to torso height. Facing the
        camera, the shoulders are wide (ratio ~0.4-0.8); turned sideways the
        shoulders collapse toward each other (ratio small). IDM-VTON needs a
        roughly front-facing subject, so reject a profile/side turn.
    Cheap heuristics, not a quality model — they catch the gross failures.
    """
    kp = pose.keypoints_px
    eye_y = (kp["left_eye"][1] + kp["right_eye"][1]) / 2.0
    heel_y = (kp["left_heel"][1] + kp["right_heel"][1]) / 2.0
    person_h = abs(heel_y - eye_y)
    fill = person_h / max(pose.image_height, 1)
    if fill < min_fill_fraction:
        return False, (f"Subject too small/far (fills only {fill:.0%} of the "
                       "frame vertically; want >55%). Move closer or crop so "
                       "you fill the frame head-to-feet.")

    body_mid_x = (kp["left_shoulder"][0] + kp["right_shoulder"][0] +
                  kp["left_hip"][0] + kp["right_hip"][0]) / 4.0
    center_offset = abs(body_mid_x - pose.image_width / 2.0) / max(pose.image_width, 1)
    if center_offset > max_center_offset:
        return False, (f"Subject off-center ({center_offset:.0%} from center). "
                       "Center yourself in the frame — an off-center subject "
                       "confuses the try-on's auto-crop.")

    # frontal check: shoulder width vs shoulder->hip vertical distance
    shoulder_w = abs(kp["left_shoulder"][0] - kp["right_shoulder"][0])
    torso_h = abs(((kp["left_hip"][1] + kp["right_hip"][1]) / 2.0) -
                  ((kp["left_shoulder"][1] + kp["right_shoulder"][1]) / 2.0))
    frontal = shoulder_w / max(torso_h, 1)
    if frontal < min_frontal_ratio:
        return False, (f"Looks like a side/turned pose (shoulder-to-torso "
                       f"ratio {frontal:.2f}). Face the camera — IDM-VTON is "
                       "trained on front-facing shots and garbles profiles.")

    return True, ""


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python pose_estimation.py <image_path>")
        sys.exit(1)
    result = extract_keypoints(sys.argv[1])
    print(f"Image: {result.image_width}x{result.image_height}")
    for name, (x, y) in result.keypoints_px.items():
        print(f"  {name:18s} ({x:7.1f}, {y:7.1f})  vis={result.visibility[name]:.2f}")
