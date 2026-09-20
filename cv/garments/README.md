# Curated garment catalog

The controlled set of garments the **virtual try-on + size recommendation** runs on.

## Why this exists

The try-on model needs a clean image of **one** garment, and the size
recommendation needs a **readable size chart**. Neither can be pulled reliably
from an arbitrary live product page (a listing page has no single item, and size
charts live in wildly different places per retailer). So the demo splits in two:

- **Live web search** supplies the "where to buy" links (new + secondhand) in the
  plan. Great for browsing, unreliable for images/charts.
- **This catalog** supplies the garments the try-on itself uses: each one has a
  verified clean image and a real size chart, so the try-on and sizing work every
  time.

## Format

Each `*.json` is the same spec `cv/product.py` already loads:

```json
{
  "name": "Uniqlo Crew Neck T-Shirt",
  "brand": "uniqlo_crew_tee",
  "category": "top",
  "fit": "regular",
  "description": "white regular-fit short-sleeve cotton crew neck t-shirt",
  "product_url": "https://www.uniqlo.com/us/en/products/E422992-000/00",
  "image_url": "https://image.uniqlo.com/.../422992/item/....jpg",
  "size_chart": {
    "S": {"chest_cm": [88, 96], "shoulder_cm": [43, 45]},
    "M": {"chest_cm": [96, 104], "shoulder_cm": [45, 47]}
  }
}
```

- `image_url` — a clean, hotlinkable product photo the try-on downloads. May also
  be a local path (e.g. `../shirt.jpg`) if you'd rather not depend on a URL.
- `size_chart` — body chest circumference and shoulder-width ranges (cm) that each
  size fits. This is what `cv/size_chart.py` `fit_confidence()` scores against.
- `chest_cm` is the body measurement that fits that size, not a flat garment
  measurement. Three fits are included on purpose (oversized / regular / slim) so
  the same body maps to different sizes across garments.

## Run the try-on against a catalog garment

```bash
cd cv
python photoshoot.py --product garments/uniqlo_crew_tee.json
# or from files:
python photoshoot_from_files.py --product garments/uniqlo_oxford_slim.json
```

`index.json` lists the whole catalog (id, category, fit, product_url, image_url)
so the app can offer a garment picker instead of hardcoding one.

## Add a garment

1. Copy any `*.json` here, change the fields.
2. Put a real, hotlinkable `image_url` (or a local image path).
3. Add the size chart in cm.
4. Add a matching row to `index.json`.

Size charts here are representative body-fit ranges good enough to demo the
mapping. Swap in a brand's exact published chart when you have it.
