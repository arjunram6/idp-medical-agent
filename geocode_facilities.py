#!/usr/bin/env python3
"""
Backfill latitude/longitude for the Ghana facilities CSV using geocode.maps.co.

Requires GEOCODE_API_KEY in .env (get a free key at https://geocode.maps.co/).

Usage:
  python geocode_facilities.py              # geocode all rows missing lat/lon
  python geocode_facilities.py --dry-run    # show how many would be geocoded
  python geocode_facilities.py --limit 50   # geocode first 50 missing only

Writes: data/<source_name>_geocoded.csv (or alongside CSV if loaded from Desktop).
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import _find_ghana_csv, GEOCODE_API_KEY
from src.geocode_maps import build_address_from_row, geocode_with_rate_limit


def has_coords(row: dict) -> bool:
    lat = (row.get("latitude") or row.get("lat") or "").strip()
    lon = (row.get("longitude") or row.get("lon") or "").strip()
    if not lat or not lon:
        return False
    try:
        float(lat)
        float(lon)
        return True
    except ValueError:
        return False


def main():
    import argparse
    p = argparse.ArgumentParser(description="Geocode Ghana facilities CSV via geocode.maps.co")
    p.add_argument("--dry-run", action="store_true", help="Only count rows to geocode, do not call API")
    p.add_argument("--limit", type=int, default=None, help="Max number of rows to geocode (default: all)")
    p.add_argument("--delay", type=float, default=1.2, help="Seconds between API calls (default: 1.2)")
    args = p.parse_args()

    path = _find_ghana_csv()
    if not path or not path.exists():
        print("Ghana CSV not found in data/ or Desktop.")
        sys.exit(1)

    if not GEOCODE_API_KEY:
        print("Set GEOCODE_API_KEY in .env (get a free key at https://geocode.maps.co/).")
        sys.exit(1)

    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if "latitude" not in fieldnames:
        fieldnames.append("latitude")
    if "longitude" not in fieldnames:
        fieldnames.append("longitude")

    to_geocode = [i for i, row in enumerate(rows) if not has_coords(row)]
    if args.limit is not None:
        to_geocode = to_geocode[: args.limit]

    if args.dry_run:
        print(f"Rows missing lat/lon: {len(to_geocode)} (of {len(rows)} total). Would write to {path.parent / (path.stem + '_geocoded' + path.suffix)}")
        return

    if not to_geocode:
        print("All rows already have latitude/longitude.")
        out_path = path.parent / (path.stem + "_geocoded" + path.suffix)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                r = dict(row)
                r.setdefault("latitude", "")
                r.setdefault("longitude", "")
                w.writerow(r)
        print(f"Wrote {out_path}")
        return

    print(f"Geocoding {len(to_geocode)} rows (delay {args.delay}s between calls)...")
    for idx, i in enumerate(to_geocode):
        row = rows[i]
        addr = build_address_from_row(row)
        if not addr:
            addr = (row.get("address_city") or "Ghana").strip() or "Ghana"
        coord = geocode_with_rate_limit(addr, delay_seconds=args.delay)
        if coord:
            row["latitude"] = str(coord[0])
            row["longitude"] = str(coord[1])
            if (idx + 1) % 20 == 0:
                print(f"  {idx + 1}/{len(to_geocode)} ...")
        else:
            row["latitude"] = ""
            row["longitude"] = ""

    out_path = path.parent / (path.stem + "_geocoded" + path.suffix)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            r = dict(row)
            r.setdefault("latitude", "")
            r.setdefault("longitude", "")
            w.writerow(r)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
