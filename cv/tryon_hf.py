"""
Realistic virtual try-on via a hosted diffusion model (IDM-VTON) on a
Hugging Face Space, called with gradio_client.

Unlike the flat warp in garment_overlay.py, IDM-VTON *generates* a new image
of the person wearing the garment — real drape, folds, occlusion, lighting.

WHERE TO RUN: your native Windows terminal (python 3.11, internet works) —
NOT the Cowork bridge, whose network is walled off from Hugging Face.

SETUP (once):
    python -m pip install gradio_client pillow

RUN (single image):
    python tryon_hf.py viren_test.jpg shirt.jpg
    # -> writes tryon_hf_result.png

Or import make_client() / tryon_one() from photoshoot.py to run a batch on
one connection.

HONEST CAVEATS:
    - Free public Space (yisol/IDM-VTON) on shared ZeroGPU: can be asleep
      (cold start ~1-2 min), queued, or over quota for anonymous callers.
      Set a free HF token via the HF_TOKEN env var if you hit quota.
    - Each generation is ~10-60s. Not real-time. Pre-generate for the demo.
"""

import os
import sys
import shutil

SPACE = "yisol/IDM-VTON"
DEFAULT_DESC = "charcoal grey boxy oversized heavyweight cotton t-shirt, drop shoulder"


def make_client(hf_token=None):
    """Connect to the Space once; reuse for many generations."""
    from gradio_client import Client
    hf_token = hf_token or os.environ.get("HF_TOKEN")
    # gradio_client renamed hf_token -> token across versions; try modern first.
    try:
        return Client(SPACE, token=hf_token) if hf_token else Client(SPACE)
    except TypeError:
        return Client(SPACE, hf_token=hf_token) if hf_token else Client(SPACE)


def tryon_one(client, person_path, garment_path, desc=DEFAULT_DESC,
              denoise_steps=30, seed=42):
    """
    Run one try-on. Returns the path to the generated image (in a temp
    location) or raises. Caller copies it wherever it wants.

    garment_path may be a local path OR an http(s) URL — a URL is downloaded
    first (via product.resolve_image).
    """
    from gradio_client import handle_file
    if isinstance(garment_path, str) and garment_path.lower().startswith(("http://", "https://")):
        from product import resolve_image
        garment_path = resolve_image(garment_path)
    result = client.predict(
        dict={"background": handle_file(person_path), "layers": [], "composite": None},
        garm_img=handle_file(garment_path),
        garment_des=desc,
        is_checked=True,        # auto-generate the body mask
        is_checked_crop=True,   # auto-crop & resize (helps on full-body photos)
        denoise_steps=denoise_steps,
        seed=seed,
        api_name="/tryon",
    )
    out = result[0] if isinstance(result, (list, tuple)) else result
    if isinstance(out, dict):
        out = out.get("path") or out.get("url")
    if not out or not os.path.exists(out):
        raise RuntimeError(f"Unexpected result shape from the Space: {result!r}")
    return out


def _cli():
    if len(sys.argv) < 3:
        print("Usage: python tryon_hf.py <person_photo> <garment_image> [description]")
        sys.exit(1)
    person, garment = sys.argv[1], sys.argv[2]
    desc = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_DESC
    for f in (person, garment):
        if not os.path.exists(f):
            print(f"File not found: {f}")
            sys.exit(1)

    try:
        import gradio_client  # noqa
    except ImportError:
        print("gradio_client not installed. Run:  python -m pip install gradio_client pillow")
        sys.exit(1)

    print(f"Connecting to {SPACE} (free Space — may cold-start ~1-2 min or queue)...")
    try:
        client = make_client()
    except Exception as e:
        print(f"\nCould not connect: {e}")
        print("Get a free token at https://huggingface.co/settings/tokens, then:")
        print("  set HF_TOKEN=hf_xxx    (Windows)   and re-run.")
        sys.exit(1)

    try:
        out = tryon_one(client, person, garment, desc)
    except Exception as e:
        print(f"\nTry-on failed: {e}")
        print("If it's a ZeroGPU quota error, set a free HF_TOKEN and retry.")
        sys.exit(1)

    dest = "tryon_hf_result.png"
    shutil.copy(out, dest)
    print(f"\nSUCCESS -> {dest}")


if __name__ == "__main__":
    _cli()
