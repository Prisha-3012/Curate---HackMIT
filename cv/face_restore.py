"""
Restore the person's REAL face onto an IDM-VTON try-on result.

Why: IDM-VTON regenerates the upper body and often repaints the face, so the
output looks like a different person (real complaint from testing). The body +
garment are good; only the face identity is wrong. This composites the ORIGINAL
photo's head back onto the generated body, aligned by the eyes, with a
feathered blend so the seam at the neck/hairline is soft.

APPROACH:
  1. Detect the face in BOTH the original photo and the try-on result
     (MediaPipe Face Detection -> bounding box + eye/nose keypoints).
  2. Estimate a similarity transform (scale+rotate+translate) from the
     original's eyes/nose to the result's, so the original head maps onto the
     result head even if IDM-VTON cropped/resized.
  3. Warp the original head + a feathered elliptical mask into the result
     frame, and alpha-blend. Model keeps the body/shirt; you get your face.

LIMITATIONS (honest):
  - Skin tone can differ slightly if the model shifted it; the blend hides
    most of it but a hard lighting mismatch can still show.
  - Needs a detectable, roughly front-facing face in both images.
  - It's a 2D paste, not a relight — good enough for a demo, not a photo
    retoucher.

USAGE:
    python face_restore.py <original_photo> <tryon_result> [output.png]
"""

import sys
import cv2
import numpy as np
import mediapipe as mp

mp_fd = mp.solutions.face_detection


def _detect_face(image_bgr):
    """Return (box_xywh, keypoints dict) in pixels, or None."""
    h, w = image_bgr.shape[:2]
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    with mp_fd.FaceDetection(model_selection=1, min_detection_confidence=0.4) as fd:
        res = fd.process(rgb)
    if not res.detections:
        return None
    det = res.detections[0]
    rbb = det.location_data.relative_bounding_box
    box = (rbb.xmin * w, rbb.ymin * h, rbb.width * w, rbb.height * h)
    kps = det.location_data.relative_keypoints
    # order: right_eye, left_eye, nose_tip, mouth_center, right_ear, left_ear
    names = ["right_eye", "left_eye", "nose", "mouth", "right_ear", "left_ear"]
    keypoints = {names[i]: (kps[i].x * w, kps[i].y * h) for i in range(min(len(kps), 6))}
    return box, keypoints


def restore_face(original_path, result_path, out_path="face_restored.png",
                 head_scale=1.7, feather=0.35):
    original = cv2.imread(original_path)
    result = cv2.imread(result_path)
    if original is None or result is None:
        raise FileNotFoundError("Could not read one of the input images.")

    od = _detect_face(original)
    rd = _detect_face(result)
    if od is None or rd is None:
        raise RuntimeError(
            "Face not detected in " +
            ("original " if od is None else "") +
            ("result " if rd is None else "") +
            "- can't restore. Use a clearer front-facing shot."
        )
    o_box, o_kp = od
    r_box, r_kp = rd

    # similarity transform from original -> result using 3 stable points
    src = np.float32([o_kp["right_eye"], o_kp["left_eye"], o_kp["nose"]])
    dst = np.float32([r_kp["right_eye"], r_kp["left_eye"], r_kp["nose"]])
    M, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.LMEDS)
    if M is None:
        raise RuntimeError("Could not compute face alignment transform.")

    H, W = result.shape[:2]
    warped_head = cv2.warpAffine(original, M, (W, H), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_REFLECT)

    # elliptical head mask in ORIGINAL coords, expanded to include hair/chin
    ox, oy, ow, oh = o_box
    cx, cy = ox + ow / 2.0, oy + oh / 2.0
    ax, ay = ow * head_scale / 2.0, oh * head_scale / 2.0
    mask = np.zeros(original.shape[:2], dtype=np.float32)
    cv2.ellipse(mask, (int(cx), int(cy)), (int(ax), int(ay)), 0, 0, 360, 1.0, -1)
    # feather the mask edges
    k = int(max(ax, ay) * feather) | 1  # odd kernel
    if k >= 3:
        mask = cv2.GaussianBlur(mask, (k, k), 0)

    # warp the mask into result frame with the same transform
    warped_mask = cv2.warpAffine(mask, M, (W, H), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    warped_mask = np.clip(warped_mask, 0, 1)[:, :, None]

    blended = result.astype(np.float32) * (1 - warped_mask) + \
              warped_head.astype(np.float32) * warped_mask
    out = blended.astype(np.uint8)
    cv2.imwrite(out_path, out)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python face_restore.py <original_photo> <tryon_result> [output.png]")
        sys.exit(1)
    out = sys.argv[3] if len(sys.argv) > 3 else "face_restored.png"
    try:
        path = restore_face(sys.argv[1], sys.argv[2], out)
        print(f"Wrote {path} (your real face on the try-on body).")
    except Exception as e:
        print(f"Face restore failed: {e}")
        sys.exit(1)
