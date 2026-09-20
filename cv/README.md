# FitCheck CV — sizing + virtual try-on (ENOUGH)

The computer-vision half of ENOUGH: from a photo + height (+ optional weight)
it estimates body measurements, recommends a size with a confidence score, and
generates a realistic virtual try-on of a garment on the person.

## Setup (once, on the machine with a webcam + internet)

```bash
python -m venv .venv
source .venv/Scripts/activate     # Git Bash on Windows
python -m pip install -r requirements.txt
```

Pin `mediapipe==0.10.9` (already in requirements) — newer mediapipe dropped the
simple `mp.solutions` API this code uses.

For the try-on you need a free Hugging Face token (the hosted model is on a
shared GPU with a per-account quota):
```bash
export HF_TOKEN=hf_xxxxxxxx        # from https://huggingface.co/settings/tokens
```

## The two things this does

### 1. Sizing (photo + height, optional weight)
```bash
python measurement.py <photo.jpg> <height_cm> [weight_kg]
python size_chart.py <photo.jpg> <height_cm> <brand>
```
- `pose_estimation.py` — MediaPipe pose keypoints, plus `assess_framing()` which
  rejects photos that are too far / off-center / side-on (bad try-on inputs).
- `measurement.py` — pixel keypoints + height → real-world measurements.
  Limb/torso lengths come from the photo; chest/hip **circumference** falls back
  to a height+weight estimate when loose clothing makes the photo width
  unreliable (auto-detected).
- `size_chart.py` — measurements → recommended size + confidence.
- `calibrate.py` — fit the height+weight circumference formula to real
  tape-measured data from your own team (replaces the rough defaults).

### 2. Virtual try-on (realistic, generated)
```bash
# one photo:
python tryon_hf.py <photo.jpg> <garment.jpg>

# hands-free multi-pose photoshoot (webcam, auto-captures 5 shots 15s apart):
python photoshoot.py <garment.jpg>

# same, but from photos you supply instead of the webcam (put them in photoshoot_in/):
python photoshoot_from_files.py <garment.jpg>

# put the person's REAL face back on a try-on result (the model repaints it):
python face_restore.py <original_photo.jpg> <tryon_result.png> <out.png>
```
- `tryon_hf.py` — calls the IDM-VTON diffusion model on Hugging Face. Generates
  a realistic image of the person wearing the garment (~10-60s each).
- `photoshoot.py` / `photoshoot_from_files.py` — capture/collect several poses,
  validate framing, run the try-on on each, save a combined gallery.
- `face_restore.py` — composites the original face back onto the result, aligned
  by the eyes (IDM-VTON re-encodes and drifts the face; this is the standard
  paste-back fix).

## Known limits (say these in the pitch)
- Try-on quality is bounded by input quality: front-facing, centered, full body,
  plain background, no other people, no chain/accessories over the garment.
- The model repaints the face — use `face_restore.py` to keep the real one.
- Diffusion is seconds-per-image, not real-time. Pre-generate demo images.
- Free HF GPU quota is limited; a token raises it. Paid (Replicate) removes it.
- Sizing circumference from a single photo is approximate; height+weight is the
  reliable fallback. Calibrate `calibrate.py` on real data before trusting numbers.
