"""
Product loading: pull the garment image from a URL and the sizing dimensions
from a structured product spec, instead of hardcoding a local shirt.jpg + a
built-in chart.

WHY A SPEC INSTEAD OF LIVE-SCRAPING A RETAIL PAGE:
Retail pages (Amazon etc.) block automated fetching (robots.txt) and every
site lays out its size chart differently, so live-scraping an arbitrary
product URL is unreliable. The robust pattern — and how the rest of ENOUGH
should feed this — is a product spec (JSON) that carries the image link and
the size chart as data. That spec can be produced however you like (a curated
catalog, a server-side scrape, the resource-matcher's output); this module
just consumes it.

PRODUCT SPEC FORMAT (JSON, local file OR https URL):
{
  "name": "NeoStride Boxy Cropped Tee",
  "brand": "neostride_boxy_tee",
  "description": "charcoal grey boxy oversized heavyweight cotton t-shirt, drop shoulder",
  "image_url": "https://.../shirt.jpg",     # or "image": "local_path.jpg"
  "size_chart": {                            # body-fit ranges per size, cm
    "XS": {"chest_cm": [78, 86], "shoulder_cm": [38, 41]},
    "S":  {"chest_cm": [86, 94], "shoulder_cm": [41, 44]},
    ...
  }
}
size_chart may instead be a URL/path string pointing at a JSON of the same shape.

USAGE:
    from product import load_product
    p = load_product("products/neostride.json")   # or an https URL
    # p["image_path"] -> a local file ready for try-on
    # p["size_chart"] -> dict for size_chart.fit_confidence(..., chart=...)
    # p["description"], p["brand"], p["name"]
"""

import os
import json
import tempfile
import urllib.request

_CACHE = os.path.join(tempfile.gettempdir(), "enough_products")


def _is_url(s):
    return isinstance(s, str) and s.lower().startswith(("http://", "https://"))


def _fetch_bytes(url, timeout=30):
    # Browser-like headers so retail pages (Amazon etc.) serve the real product
    # page rather than an immediate block. Not foolproof — bot detection can
    # still return a robot/captcha page, which the parser then treats as "no
    # chart found" instead of crashing.
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# ---- HTML size-chart + image scraping (works on pages that expose an HTML
# size table, e.g. Amazon). Best-effort: returns (None, None) quietly if the
# page can't be parsed, so the caller can say "unable to find size chart". ----

_SIZE_ALIASES = {
    "X-SMALL": "XS", "XSMALL": "XS", "XS": "XS",
    "SMALL": "S", "S": "S",
    "MEDIUM": "M", "M": "M",
    "LARGE": "L", "L": "L",
    "X-LARGE": "XL", "XLARGE": "XL", "XL": "XL",
    "XX-LARGE": "2XL", "XXLARGE": "2XL", "2XL": "2XL", "XXL": "2XL",
    "XXX-LARGE": "3XL", "3XL": "3XL", "XXXL": "3XL",
}


def _extract_tables(html):
    """Return every HTML <table> as a list of rows (each row a list of cell texts)."""
    from html.parser import HTMLParser

    class T(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tables, self.cur, self.row, self.cell = [], None, None, None
        def handle_starttag(self, tag, attrs):
            if tag == "table":
                self.cur = []
            elif tag == "tr" and self.cur is not None:
                self.row = []
            elif tag in ("td", "th") and self.row is not None:
                self.cell = []
        def handle_data(self, data):
            if self.cell is not None:
                self.cell.append(data)
        def handle_endtag(self, tag):
            if tag in ("td", "th") and self.cell is not None:
                self.row.append(" ".join("".join(self.cell).split()))
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.cur.append(self.row)
                self.row = None
            elif tag == "table" and self.cur is not None:
                self.tables.append(self.cur)
                self.cur = None

    p = T()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.tables


def _parse_size_table(html):
    """
    Find a size table with a Chest column and return a GARMENT chart in cm:
      {size_code: {chest_cm, shoulder_cm|None, length_cm|None}}
    Returns {} if none found.
    """
    import re
    for rows in _extract_tables(html):
        if len(rows) < 2:
            continue
        header = [c.lower() for c in rows[0]]
        if not any("chest" in c for c in header):
            continue

        def col(key):
            for i, c in enumerate(header):
                if key in c:
                    return i
            return None

        ci, shi, li = col("chest"), col("shoulder"), col("length")
        if ci is None:
            continue
        # inches vs cm from the header text
        htext = " ".join(header)
        to_cm = 2.54 if ("in" in htext or '"' in htext) and "cm" not in htext else 1.0

        def num(row, idx):
            if idx is None or idx >= len(row):
                return None
            m = re.search(r"[\d.]+", row[idx])
            return round(float(m.group()) * to_cm, 1) if m else None

        chart = {}
        for row in rows[1:]:
            if not row:
                continue
            raw = row[0].strip().upper().replace(" ", "")
            code = _SIZE_ALIASES.get(raw)
            if not code:
                continue
            chest = num(row, ci)
            if chest is None:
                continue
            chart[code] = {"chest_cm": chest,
                           "shoulder_cm": num(row, shi),
                           "length_cm": num(row, li)}
        if chart:
            return chart
    return {}


def _garment_to_fit_chart(garment_chart):
    """
    Convert GARMENT chest measurements into body-fit chest ranges the sizing
    engine can score against. A garment fits a body chest that's smaller than
    the garment by a comfortable ease; we accept body chest in
    [garment - 20cm, garment - 6cm] (relaxed-to-oversized window, since this
    line is boxy/oversized). Heuristic, not exact — the plumbing pulls the real
    numbers from the page; the ease window is the tunable assumption.
    """
    fit = {}
    for size, d in garment_chart.items():
        g = d.get("chest_cm")
        if g:
            # wearable body-chest window: ease 4cm (fitted) to 28cm (very boxy)
            fit[size] = {"chest_cm": (round(g - 28, 1), round(g - 4, 1))}
    return fit


def _scrape_rendered_sizechart(url, headed=True, timeout_ms=30000):
    """
    Use a real browser (Playwright) to load the product page, click the
    "Size Chart" / "Size Guide" link, and read the popup table — the size
    chart on Amazon lives in a click-triggered popup, so a plain fetch never
    sees it. Returns a GARMENT chart dict (cm) or {}.

    Requires Playwright:  pip install playwright  &&  playwright install chromium
    headed=True launches a VISIBLE browser, which Amazon bot-detects less than
    headless (and is fine to show at a demo). Returns {} on any failure.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. For automatic size-chart reading from "
            "retail pages run:  pip install playwright  &&  playwright install chromium"
        )

    html = ""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        page = browser.new_page(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"))
        try:
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            # click the size-chart trigger (several possible labels)
            for sel in ["text=/size chart/i", "text=/size guide/i"]:
                try:
                    page.click(sel, timeout=5000)
                    page.wait_for_timeout(1800)   # let the popup render
                    break
                except Exception:
                    continue
            html = page.content()
        finally:
            browser.close()
    return _parse_size_table(html)


def _extract_image_from_page(html):
    import re
    for pat in [r'"hiRes":"(https:[^"]+?)"',
                r'data-old-hires="([^"]+)"',
                r'"large":"(https://m\.media-amazon\.com/images/[^"]+?)"',
                r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)']:
        m = re.search(pat, html)
        if m:
            return m.group(1).replace("\\/", "/")
    return None


def resolve_image(source, cache_dir=_CACHE):
    """Return a local path to the garment image. Downloads it if `source` is a URL."""
    if not _is_url(source):
        if not os.path.exists(source):
            raise FileNotFoundError(f"garment image not found: {source}")
        return source
    os.makedirs(cache_dir, exist_ok=True)
    ext = os.path.splitext(source.split("?")[0])[1] or ".jpg"
    dest = os.path.join(cache_dir, "garment_" + str(abs(hash(source)) % (10**8)) + ext)
    data = _fetch_bytes(source)
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def _load_json_source(source):
    """Load JSON from a local path or an https URL."""
    if _is_url(source):
        return json.loads(_fetch_bytes(source).decode("utf-8"))
    with open(source, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_chart(chart):
    """Accept a chart dict, or a URL/path string pointing at one. Coerce
    range lists to tuples so it matches size_chart.py's expected format."""
    if isinstance(chart, str):
        chart = _load_json_source(chart)
    norm = {}
    for size, d in chart.items():
        norm[size] = {k: tuple(v) if isinstance(v, list) else v for k, v in d.items()}
    return norm


def load_product(source):
    """
    Load a product spec (JSON file or URL) and return a ready-to-use dict:
      { name, brand, description, image_path, size_chart }
    The garment image is downloaded to a local cache if given as image_url.
    """
    spec = _load_json_source(source) if isinstance(source, str) else dict(source)

    img_source = spec.get("image_url") or spec.get("image")
    if not img_source:
        raise ValueError("product spec has no 'image_url' or 'image'")
    image_path = resolve_image(img_source)

    size_chart = spec.get("size_chart")
    size_chart = _normalize_chart(size_chart) if size_chart else None

    return {
        "name": spec.get("name", "product"),
        "brand": spec.get("brand", "product"),
        "description": spec.get("description"),
        "image_path": image_path,
        "size_chart": size_chart,
    }


def load_from_link(link):
    """
    Robustly turn a user-pasted link into what we can use, WITHOUT crashing.
    Handles: a product-spec JSON (image + size chart), a direct image URL, or
    a web page (tries og:image for the garment). Always returns a dict:
      { image_path, size_chart, description, notes: [str] }
    Any of image_path / size_chart may be None; `notes` explains what happened.
    The caller decides how to degrade (e.g. "unable to find size chart").
    """
    result = {"image_path": None, "size_chart": None, "description": None, "notes": []}
    try:
        raw = _fetch_bytes(link)
    except Exception as e:
        result["notes"].append(f"could not open the link ({e})")
        return result

    # 1) product-spec JSON?
    spec = None
    try:
        spec = json.loads(raw.decode("utf-8"))
    except Exception:
        spec = None
    if isinstance(spec, dict):
        result["description"] = spec.get("description")
        img = spec.get("image_url") or spec.get("image")
        if img:
            try:
                result["image_path"] = resolve_image(img)
            except Exception as e:
                result["notes"].append(f"couldn't fetch the spec's image ({e})")
        else:
            result["notes"].append("spec has no image_url")
        if spec.get("size_chart"):
            try:
                result["size_chart"] = _normalize_chart(spec["size_chart"])
            except Exception as e:
                result["notes"].append(f"size chart in spec was unreadable ({e})")
        else:
            result["notes"].append("spec contained no size_chart")
        return result

    # 2) a direct image? (JPEG / PNG magic bytes)
    if raw[:3] == b"\xff\xd8\xff" or raw[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
        os.makedirs(_CACHE, exist_ok=True)
        dest = os.path.join(_CACHE, "garment_" + str(abs(hash(link)) % (10**8)) + ext)
        with open(dest, "wb") as f:
            f.write(raw)
        result["image_path"] = dest
        result["notes"].append("link was a direct image (no size chart on an image link)")
        return result

    # 3) a product web page (Amazon etc.) — pull BOTH the image and the size
    #    chart table straight from the page.
    try:
        html = raw.decode("utf-8", "ignore")
    except Exception as e:
        result["notes"].append(f"couldn't read the page ({e})")
        return result

    # detect a robot/captcha wall so we can say so plainly
    low = html.lower()
    if ("captcha" in low or "api-services-support@amazon" in low
            or "to discuss automated access" in low or "enter the characters you see" in low):
        result["notes"].append("the site served a bot/captcha page instead of the product "
                               "(automated fetch blocked) — paste a product-spec JSON link "
                               "or a direct image URL instead")
        return result

    # image
    img = _extract_image_from_page(html)
    if img:
        try:
            result["image_path"] = resolve_image(img)
            result["notes"].append("pulled the garment image from the page")
        except Exception as e:
            result["notes"].append(f"found an image on the page but couldn't fetch it ({e})")
    else:
        result["notes"].append("couldn't find a garment image on the page")

    # size chart — try the static HTML first (fast), then a real browser that
    # clicks the "Size Chart" popup (Amazon loads it only on click).
    garment = {}
    try:
        garment = _parse_size_table(html)
    except Exception as e:
        result["notes"].append(f"static size-chart parse failed ({e})")

    if not garment:
        result["notes"].append("size chart not in page HTML — opening the page in a "
                               "browser to click the Size Chart popup...")
        try:
            garment = _scrape_rendered_sizechart(link)
        except RuntimeError as e:
            result["notes"].append(str(e))
        except Exception as e:
            result["notes"].append(f"browser size-chart read failed ({e})")

    if garment:
        result["size_chart"] = _garment_to_fit_chart(garment)
        result["garment_chart"] = garment
        result["notes"].append(f"got the size chart ({', '.join(garment.keys())})")
    else:
        result["notes"].append("could not extract a size chart from this link")
    return result


def prompt_and_load():
    """Interactive: ask for a product link, load it, and report gracefully."""
    while True:
        link = input("Product link (image URL, or product-spec JSON URL): ").strip()
        if not link:
            print("  Please paste a link.")
            continue
        print("  Fetching...")
        res = load_from_link(link)
        for n in res["notes"]:
            print(f"  - {n}")
        if res["image_path"] is None:
            again = input("  Couldn't get a garment image from that link. Try another? [y/N]: ").strip().lower()
            if again == "y":
                continue
        return res


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python product.py <product.json | https-url>")
        sys.exit(1)
    p = load_product(sys.argv[1])
    print("name:", p["name"])
    print("brand:", p["brand"])
    print("description:", p["description"])
    print("image ->", p["image_path"], "(exists:", os.path.exists(p["image_path"]), ")")
    print("size_chart sizes:", list(p["size_chart"]) if p["size_chart"] else None)
