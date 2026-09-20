"""
Hands-free virtual-try-on photoshoot.

Launch it, and it:
  1. Opens your webcam with a live preview + on-screen countdown.
  2. Auto-captures NUM_PHOTOS photos, INTERVAL_SEC apart, with NO clicking —
     you just change pose between shots (front, 3/4 turn, side, arms up...).
  3. Checks each photo has a usable full-body pose (skips bad ones so we
     don't waste generation time on them).
  4. Runs the IDM-VTON try-on on each good photo (one connection, reused).
  5. Saves every result AND a combined gallery contact-sheet you can show.

WHERE TO RUN: your native Windows terminal (webcam + internet both work
there). NOT the Cowork bridge.

SETUP (once):
    python -m pip install gradio_client pillow opencv-python mediapipe==0.10.9

RUN:
    python photoshoot.py shirt.jpg
    # optional: python photoshoot.py shirt.jpg "green striped polo"

TIPS:
  - Prop the laptop back so your WHOLE body is in frame (head to feet).
  - Use the 15s gaps to change pose. The on-screen counter tells you when
    the next shot fires.
  - Total time: ~75s capture + ~1-5 min generation (5 diffusion runs). For a
    live demo, run this BEFORE and show the saved gallery instantly.
"""

import os
import sys
import time
import glob
import cv2

# ---- tunables ----
NUM_PHOTOS = 5
INTERVAL_SEC = 15
OUT_DIR = "photoshoot_out"
# ------------------


def capture_burst():
    """Auto-capture NUM_PHOTOS frames INTERVAL_SEC apart. Returns list of paths."""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: couldn't open the webcam. Check Windows camera privacy "
              "('Let desktop apps access your camera' must be ON), and that no "
              "other app (Zoom/Teams) is using it.")
        return []
    # Request the camera's NATIVE resolution (1920x1080, 16:9). Asking for a
    # size the sensor doesn't natively produce (e.g. 1280x720) makes some
    # drivers center-crop or mishandle the frame, which shows up as a
    # shifted / off-center image. Matching native res avoids that. We also
    # read back what the driver actually gave us and print it.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    aw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ah = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Camera resolution in use: {aw}x{ah}")

    # Preview is shown DOWNSCALED to fit the screen, but the SAVED frame is
    # the full-resolution original — better input for the try-on, and the
    # window won't overflow / look shifted on a smaller display.
    PREVIEW_W = 960

    def show(img, tag=None):
        disp = cv2.resize(img, (PREVIEW_W, int(img.shape[0] * PREVIEW_W / img.shape[1])))
        if tag:
            for t, y, col, sc in tag:
                cv2.putText(disp, t, (15, y), cv2.FONT_HERSHEY_SIMPLEX, sc, col, 2)
        cv2.imshow("FitCheck photoshoot", disp)

    os.makedirs(OUT_DIR, exist_ok=True)
    paths = []
    print(f"Photoshoot: {NUM_PHOTOS} photos, one every {INTERVAL_SEC}s. "
          "Change pose between shots. Press ESC to abort.")

    for i in range(1, NUM_PHOTOS + 1):
        shot_deadline = time.time() + INTERVAL_SEC
        while True:
            ok, frame = cap.read()
            if not ok:
                print("ERROR: lost the webcam feed.")
                cap.release(); cv2.destroyAllWindows()
                return paths
            remaining = shot_deadline - time.time()
            if remaining > 0:
                show(frame, [
                    (f"Photo {i}/{NUM_PHOTOS}  next in {remaining:0.0f}s", 30, (0, 255, 0), 0.7),
                    ("Center yourself. Change pose. ESC to abort.", 58, (0, 255, 255), 0.55),
                ])
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                print("Aborted.")
                cap.release(); cv2.destroyAllWindows()
                return paths
            if remaining <= 0:
                flash = frame.copy()
                cv2.rectangle(flash, (0, 0), (flash.shape[1]-1, flash.shape[0]-1), (255, 255, 255), 30)
                show(flash, [(f"CAPTURED {i}/{NUM_PHOTOS}", 90, (0, 0, 255), 1.0)])
                cv2.waitKey(300)
                p = os.path.join(OUT_DIR, f"pose_{i}.jpg")
                cv2.imwrite(p, frame)  # save FULL-RES original, not the preview
                paths.append(p)
                print(f"  captured {p}")
                break

    cap.release()
    cv2.destroyAllWindows()
    return paths


def validate_photos(paths):
    """
    Returns (good, skipped) where good is a list of usable paths and skipped
    is a list of (path, reason) for the ones rejected — so the caller can tell
    the user exactly which images weren't processed and why.
    """
    try:
        from pose_estimation import extract_keypoints, assess_framing
    except ImportError:
        return list(paths), []
    good, skipped = [], []
    for p in paths:
        try:
            pose = extract_keypoints(p)
        except Exception as e:
            print(f"  {p}: skipped ({e})")
            skipped.append((p, str(e)))
            continue
        ok, reason = assess_framing(pose)
        if not ok:
            print(f"  {p}: skipped — {reason}")
            skipped.append((p, reason))
            continue
        good.append(p)
        print(f"  {p}: OK (good pose + framing)")
    return good, skipped


def build_gallery(result_paths, out_path="photoshoot_gallery.png", header=None):
    """Stitch the try-on results into one horizontal contact sheet, with an
    optional header banner across the top (used for the recommended size)."""
    from PIL import Image, ImageDraw
    if not result_paths:
        return None
    imgs = [Image.open(p).convert("RGB") for p in result_paths]
    h = 640
    resized = []
    for im in imgs:
        w = int(im.width * h / im.height)
        resized.append(im.resize((w, h)))
    total_w = sum(im.width for im in resized) + 10 * (len(resized) + 1)
    banner_h = 96 if header else 0
    sheet = Image.new("RGB", (total_w, h + 20 + banner_h), (245, 245, 245))
    if header:
        d = ImageDraw.Draw(sheet)
        d.rectangle((0, 0, total_w, banner_h), fill=(28, 28, 32))
        d.text((24, 26), header, font=_load_font(40), fill=(255, 255, 255))
    x = 10
    for im in resized:
        sheet.paste(im, (x, 10 + banner_h))
        x += im.width + 10
    sheet.save(out_path)
    return out_path


def _load_font(size):
    from PIL import ImageFont
    import os as _os
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    try:
        import matplotlib
        candidates.append(_os.path.join(_os.path.dirname(matplotlib.__file__),
                                        "mpl-data/fonts/ttf/DejaVuSans.ttf"))
    except Exception:
        pass
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_error_card(num, reason, w=480, h=640):
    """A placeholder image with the error text, shown in place of a missing try-on."""
    from PIL import Image, ImageDraw
    import textwrap
    img = Image.new("RGB", (w, h), (24, 24, 28))
    d = ImageDraw.Draw(img)
    d.text((30, 45), f"IMAGE {num}", font=_load_font(36), fill=(240, 120, 120))
    d.text((30, 95), "NOT PROCESSED", font=_load_font(30), fill=(240, 120, 120))
    d.line((30, 145, w - 30, 145), fill=(80, 80, 88), width=2)
    y = 175
    body = _load_font(22)
    for line in textwrap.wrap(reason, width=34):
        d.text((30, y), line, font=body, fill=(230, 230, 230))
        y += 32
    return img


def _print_summary(all_photos, status):
    """Per-image outcome, so the user sees exactly what was and wasn't processed."""
    print("\n=== Summary ===")
    for i, p in enumerate(all_photos, 1):
        state, detail = status.get(p, ("not_processed", "not attempted"))
        name = os.path.basename(p)
        if state == "ok":
            print(f"  Image {i} ({name}): processed -> {os.path.basename(detail)}")
        else:
            print(f"  Image {i} ({name}): NOT PROCESSED — {detail}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python photoshoot.py <garment_image> [garment_description]")
        sys.exit(1)
    garment = sys.argv[1]
    desc = sys.argv[2] if len(sys.argv) > 2 else None
    if not os.path.exists(garment):
        print(f"Garment image not found: {garment}")
        sys.exit(1)

    # User inputs (for the size recommendation). Not hardcoded — prompted here,
    # and in the web app these come from form fields.
    print("=== Your details (for size recommendation) ===")
    try:
        from userinput import prompt_height_cm, prompt_weight_kg
        height_cm = prompt_height_cm()
        weight_kg = prompt_weight_kg()
    except ImportError:
        height_cm, weight_kg = None, None
        print("(userinput.py not found — skipping sizing, try-on only)")

    print("\n=== Phase 1: capture ===")
    photos = capture_burst()
    if not photos:
        print("No photos captured. Exiting.")
        sys.exit(1)

    print("\n=== Phase 2: validate poses ===")
    good, skipped = validate_photos(photos)

    # Track the fate of every captured image, by capture number.
    status = {}  # path -> (state, detail)   state in {"ok","not_processed"}
    for p, reason in skipped:
        status[p] = ("not_processed", f"rejected at validation: {reason}")

    if not good:
        print("None of the photos had a usable full-body pose. Re-run and make "
              "sure your whole body is in frame.")
        _print_summary(photos, status)
        sys.exit(1)

    # Sizing on the best photo (uses the height/weight entered above).
    size_line = None       # short line for the gallery banner
    size_block = None      # full text for the final prominent block
    if height_cm is not None:
        print("\n=== Size recommendation ===")
        try:
            from pose_estimation import extract_keypoints
            from measurement import compute_measurements, validate_measurements
            from size_chart import fit_confidence, BRAND_SIZE_CHARTS
            pose = extract_keypoints(good[0])
            m = compute_measurements(pose, height_cm, weight_kg=weight_kg)
            brand = next(iter(BRAND_SIZE_CHARTS))
            fit = fit_confidence(m, brand)
            size_line = f"Recommended size: {fit.recommended_size}  (confidence {fit.confidence})"
            size_block = (
                f"{size_line}\n"
                f"  Brand chart: {brand}\n"
                f"  Chest ~{m.photo_est_chest_circumference_cm}cm, "
                f"hip ~{m.final_hip_circumference_cm}cm ({m.hip_circumference_source})"
            )
            print(f"  Chest ~{m.photo_est_chest_circumference_cm}cm, "
                  f"hip ~{m.final_hip_circumference_cm}cm ({m.hip_circumference_source})")
            print(f"  Recommended size ({brand}): {fit.recommended_size} "
                  f"(confidence {fit.confidence})")
            for w in validate_measurements(m):
                print(f"  note: {w}")
        except Exception as e:
            print(f"  sizing skipped: {e}")

    print(f"\n=== Phase 3: try-on ({len(good)} photos) ===")
    try:
        from tryon_hf import make_client, tryon_one, DEFAULT_DESC
    except ImportError:
        print("tryon_hf.py not found next to this script.")
        sys.exit(1)
    if desc is None:
        desc = DEFAULT_DESC

    try:
        client = make_client()
    except Exception as e:
        print(f"Could not connect to the try-on Space: {e}")
        print("Set a free HF_TOKEN (https://huggingface.co/settings/tokens) and retry.")
        sys.exit(1)

    import shutil
    results = []
    for p in good:
        num = photos.index(p) + 1  # its capture number
        print(f"  [image {num}] generating try-on for {os.path.basename(p)} ... (~10-60s)")
        try:
            out = tryon_one(client, p, garment, desc)
            dest = os.path.join(OUT_DIR, f"tryon_{num}.png")
            shutil.copy(out, dest)
            results.append(dest)
            status[p] = ("ok", dest)
            print(f"      -> {dest}")
        except Exception as e:
            status[p] = ("not_processed", f"try-on failed: {e}")
            print(f"      FAILED on image {num} ({os.path.basename(p)}): {e}")

    print("\n=== Phase 4: gallery + error cards ===")
    # Build one cell per input image, in order: a try-on for the ones that
    # worked, an error card (saved as its own image) for the ones that didn't.
    cells = []
    for i, p in enumerate(photos, 1):
        state, detail = status.get(p, ("not_processed", "not attempted"))
        if state == "ok":
            cells.append(detail)
        else:
            card_path = os.path.join(OUT_DIR, f"error_{i}.png")
            make_error_card(i, detail).save(card_path)
            cells.append(card_path)
            print(f"  wrote error card: {card_path}")
    gallery = build_gallery(cells, header=size_line) if cells else None

    _print_summary(photos, status)
    if size_block:
        print("\n" + "=" * 44)
        print("  RECOMMENDED SIZE")
        print("=" * 44)
        print("  " + size_block.replace("\n", "\n  "))
        print("=" * 44)
    print(f"\nAll outputs (try-ons + error cards) in ./{OUT_DIR}/")
    if gallery:
        print(f"Combined gallery (size banner + error cards): {gallery}")


if __name__ == "__main__":
    main()
