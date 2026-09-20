"""
Flexible height/weight input parsing + interactive prompts.

Lets the user type natural formats instead of forcing raw cm/kg:
  height: "183", "183cm", "1.83m", "6ft", "6'", "6'0", "5'11", "5ft11", "5 ft 11 in"
  weight: "52", "52kg", "115lb", "115 lbs", "8st 3" (stone)

For the web app / backend these become form fields; these helpers are for the
standalone scripts and for validating whatever the form sends.
"""

import re

CM_PER_IN = 2.54
KG_PER_LB = 0.453592


def parse_height_cm(s: str):
    """Return height in cm, or raise ValueError."""
    s = s.strip().lower()
    if not s:
        raise ValueError("empty height")

    # feet/inches: 6'0, 6'0", 6ft, 6 ft 0 in, 5'11, 5ft11
    m = re.match(r"^(\d+)\s*(?:'|ft|feet|foot)\s*(\d+(?:\.\d+)?)?\s*(?:\"|in|inch|inches)?$", s)
    if m:
        feet = float(m.group(1))
        inches = float(m.group(2)) if m.group(2) else 0.0
        return round((feet * 12 + inches) * CM_PER_IN, 1)

    # metres: 1.83m
    m = re.match(r"^(\d+(?:\.\d+)?)\s*m$", s)
    if m:
        return round(float(m.group(1)) * 100, 1)

    # centimetres: 183, 183cm
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:cm)?$", s)
    if m:
        val = float(m.group(1))
        # a bare number < 3 is almost certainly metres typed without 'm'
        if val < 3:
            return round(val * 100, 1)
        return round(val, 1)

    raise ValueError(f"couldn't parse height: {s!r}")


def parse_weight_kg(s: str):
    """Return weight in kg, or raise ValueError."""
    s = s.strip().lower()
    if not s:
        raise ValueError("empty weight")

    # stone: 8st 3, 8 st 3 lb
    m = re.match(r"^(\d+)\s*(?:st|stone)\s*(\d+(?:\.\d+)?)?\s*(?:lb|lbs)?$", s)
    if m:
        stone = float(m.group(1))
        lb = float(m.group(2)) if m.group(2) else 0.0
        return round((stone * 14 + lb) * KG_PER_LB, 1)

    # pounds: 115lb, 115 lbs
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:lb|lbs|pounds?)$", s)
    if m:
        return round(float(m.group(1)) * KG_PER_LB, 1)

    # kilograms: 52, 52kg
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilos?)?$", s)
    if m:
        return round(float(m.group(1)), 1)

    raise ValueError(f"couldn't parse weight: {s!r}")


def prompt_height_cm():
    while True:
        raw = input("Your height (e.g. 6ft, 5'11, 183cm): ").strip()
        try:
            cm = parse_height_cm(raw)
            if not (120 <= cm <= 230):
                print(f"  {cm}cm seems off — please re-enter.")
                continue
            print(f"  -> {cm} cm")
            return cm
        except ValueError as e:
            print(f"  {e}. Try again.")


def prompt_weight_kg():
    while True:
        raw = input("Your weight (e.g. 52kg, 115lb) [enter to skip]: ").strip()
        if raw == "":
            return None  # weight is optional; sizing falls back to photo-only
        try:
            kg = parse_weight_kg(raw)
            if not (30 <= kg <= 250):
                print(f"  {kg}kg seems off — please re-enter.")
                continue
            print(f"  -> {kg} kg")
            return kg
        except ValueError as e:
            print(f"  {e}. Try again.")


if __name__ == "__main__":
    # quick self-test of the parsers
    tests_h = ["6ft", "6'0", "5'11", "183", "183cm", "1.83m", "5ft11"]
    tests_w = ["52", "52kg", "115lb", "115 lbs", "8st 3"]
    for t in tests_h:
        print(f"height {t!r:10} -> {parse_height_cm(t)} cm")
    for t in tests_w:
        print(f"weight {t!r:10} -> {parse_weight_kg(t)} kg")
