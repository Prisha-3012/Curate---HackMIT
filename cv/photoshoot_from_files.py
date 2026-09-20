"""
Same as photoshoot.py, but WITHOUT the webcam — use this when the laptop
camera is blocked. You supply the pose photos yourself (phone photos are
better anyway: higher res, easier to get your full body in frame).

HOW TO USE:
  1. Take several full-body photos on your phone in different poses
     (front, 3/4 turn, side, arms up...), fitted or not, whole body in frame.
  2. Put them in a folder (default: photoshoot_in/). Any names/extensions are
     fine (.jpg/.jpeg/.png) — they're processed in sorted order.
  3. Run:
        python photoshoot_from_files.py shirt.jpg
        # or point at a different folder:
        python photoshoot_from_files.py shirt.jpg my_photos_folder

It validates each photo's pose, runs the IDM-VTON try-on on each, and saves
the results plus a combined gallery — identical output to photoshoot.py.
"""

import os
import sys
import glob
import shutil

IN_DIR_DEFAULT = "photoshoot_in"
OUT_DIR = "photoshoot_out"


# Our own output files — skip these so you can point this at photoshoot_out/
# (which holds pose_*.jpg captures alongside generated tryon/error/gallery images).
_OUTPUT_PREFIXES = ("tryon_", "error_", "face_restored")
_OUTPUT_SUBSTR = ("gallery", "result", "cam_ok", "blank_test", "synthetic_", "_nochain", "withchain")


def _is_output(name):
    n = name.lower()
    return n.startswith(_OUTPUT_PREFIXES) or any(s in n for s in _OUTPUT_SUBSTR)


def gather(in_dir):
    exts = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG")
    files = []
    for e in exts:
        files.extend(glob.glob(os.path.join(in_dir, e)))
    # keep only input photos, not our generated outputs
    files = [f for f in sorted(set(files)) if not _is_output(os.path.basename(f))]
    return files


def validate_photos(paths):
    """Returns (good, skipped) — skipped is a list of (path, reason)."""
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
    import os
    print("\n=== Summary ===")
    for i, p in enumerate(all_photos, 1):
        state, detail = status.get(p, ("not_processed", "not attempted"))
        name = os.path.basename(p)
        if state == "ok":
            print(f"  Image {i} ({name}): processed -> {os.path.basename(detail)}")
        else:
            print(f"  Image {i} ({name}): NOT PROCESSED — {detail}")


def build_gallery(result_paths, out_path="photoshoot_gallery.png", header=None):
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


def main():
    # Args are optional. With no args the script is fully interactive:
    #   1) asks for the product link, 2) height, 3) weight.
    # Args still work for automation:
    #   --product <spec.json|url> [input_folder]
    #   <garment_image_or_url> [input_folder] [description]
    argv = sys.argv[1:]
    product = None
    if "--product" in argv:
        i = argv.index("--product")
        try:
            product = argv[i + 1]
        except IndexError:
            print("--product needs a path or URL")
            sys.exit(1)
        del argv[i:i + 2]

    product_chart = None
    product_name = None
    from_link = False

    if product:
        from product import load_product
        print(f"Loading product from: {product}")
        p = load_product(product)
        garment = p["image_path"]
        desc = p.get("description")
        product_chart = p.get("size_chart")
        product_name = p.get("name")
        in_dir = argv[0] if argv else "photoshoot_out"
    elif argv:
        garment = argv[0]
        in_dir = argv[1] if len(argv) > 1 else "photoshoot_out"
        desc = argv[2] if len(argv) > 2 else None
        if garment.lower().startswith(("http://", "https://")):
            from product import resolve_image
            print(f"Downloading garment image: {garment}")
            garment = resolve_image(garment)
    else:
        # ---- fully interactive: LINK first ----
        print("=== Product link ===")
        from product import prompt_and_load
        res = prompt_and_load()
        garment = res["image_path"]
        product_chart = res["size_chart"]
        desc = res["description"]
        from_link = True
        in_dir = "photoshoot_out"
        if garment is None:
            print("\nNo garment image could be loaded from that link. Stopping.")
            sys.exit(1)

    # ---- HEIGHT, then WEIGHT ----
    print("\n=== Your details ===")
    try:
        from userinput import prompt_height_cm, prompt_weight_kg
        height_cm = prompt_height_cm()
        weight_kg = prompt_weight_kg()
    except ImportError:
        height_cm, weight_kg = None, None
        print("(userinput.py not found — skipping sizing, try-on only)")

    if not garment or not os.path.exists(garment):
        print(f"Garment image not found: {garment}")
        sys.exit(1)
    if not os.path.isdir(in_dir):
        os.makedirs(in_dir, exist_ok=True)
        print(f"Created empty folder ./{in_dir}/ — put your pose photos in it and re-run.")
        sys.exit(1)

    photos = gather(in_dir)
    if not photos:
        print(f"No photos found in ./{in_dir}/. Add some .jpg/.png full-body pose photos and re-run.")
        sys.exit(1)
    print(f"Found {len(photos)} photo(s): {', '.join(os.path.basename(p) for p in photos)}")

    print("\n=== Validate poses ===")
    good, skipped = validate_photos(photos)

    status = {}  # path -> (state, detail)
    for p, reason in skipped:
        status[p] = ("not_processed", f"rejected at validation: {reason}")

    if not good:
        print("None had a usable full-body pose. Make sure your whole body (head to feet) is in frame.")
        _print_summary(photos, status)
        sys.exit(1)

    size_line = None
    size_block = None
    if height_cm is not None:
        print("\n=== Size recommendation ===")
        try:
            from pose_estimation import extract_keypoints
            from measurement import compute_measurements, validate_measurements
            from size_chart import fit_confidence, BRAND_SIZE_CHARTS
            pose = extract_keypoints(good[0])
            m = compute_measurements(pose, height_cm, weight_kg=weight_kg)
            meas_line = (f"Chest ~{m.photo_est_chest_circumference_cm}cm, "
                         f"hip ~{m.final_hip_circumference_cm}cm ({m.hip_circumference_source})")

            if product_chart:
                # sizing dimensions came from the link's product spec
                fit = fit_confidence(m, chart=product_chart)
                size_line = f"Recommended size: {fit.recommended_size}  (confidence {fit.confidence})"
                size_block = f"{size_line}\n  {meas_line}"
                print(f"  {meas_line}")
                print(f"  {size_line}")
                for w in validate_measurements(m):
                    print(f"  note: {w}")
            elif from_link:
                # graceful: link had no usable size chart — DON'T crash, DON'T
                # silently use some other brand's chart. Say so plainly.
                print("  UNABLE TO FIND SIZE CHART from this link.")
                print(f"  Your measurements: {meas_line}")
                print("  (No size recommendation — the link didn't provide a size chart.)")
                size_line = "Size chart not found for this item"
                size_block = f"Unable to find size chart from this link.\n  Your measurements: {meas_line}"
            else:
                # local garment with no chart supplied → built-in generic chart
                brand = next(iter(BRAND_SIZE_CHARTS))
                fit = fit_confidence(m, brand)
                size_line = f"Recommended size: {fit.recommended_size}  (confidence {fit.confidence})"
                size_block = f"{size_line}\n  Brand chart: {brand}\n  {meas_line}"
                print(f"  {meas_line}")
                print(f"  Recommended size ({brand}): {fit.recommended_size} "
                      f"(confidence {fit.confidence})")
                for w in validate_measurements(m):
                    print(f"  note: {w}")
        except Exception as e:
            print(f"  sizing skipped ({e})")

    print(f"\n=== Try-on ({len(good)} photos) ===")
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

    os.makedirs(OUT_DIR, exist_ok=True)
    results = []
    for p in good:
        num = photos.index(p) + 1  # its number in the input set
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

    # One cell per input image, in order: a try-on for the ones that worked,
    # an error card (its own saved image) for the ones that didn't.
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
