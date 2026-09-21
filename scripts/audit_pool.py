"""
Pool audit: retire rows that can never make a usable frame, without
downloading anything.

One MediaWiki API call returns the true dimensions of 50 files, so the whole
pool (~10k rows) is checked in a few minutes. Rows whose file is deleted from
Commons are marked used='GONE'; rows whose long edge is below
IMG_MIN_LONG_EDGE are marked used='LOWRES'. Any non-date mark is permanently
unavailable to select_unused_images, so shorts stop spending their slots on
photos the quality gate would reject anyway. Existing marks are never
overwritten, and a run is idempotent.

    python scripts/audit_pool.py            # audit and write
    python scripts/audit_pool.py --dry-run  # report only
"""
import csv
import os
import sys
import time
import argparse
from urllib.parse import unquote

import requests

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault('GITHUB_ACTIONS', 'true')   # repo-local seed_data paths
import config                                          # noqa: E402

API = "https://commons.wikimedia.org/w/api.php"
UA = ("VintageArchiveBot/1.0 (https://github.com/hashiraarchives; "
      "public-domain photo compilations) python-requests")
POOLS = [config.GOLDMINE3_CSV, config.GOLDMINE2_CSV, config.GOLDMINE_CSV]


def title_of(url: str) -> str:
    return "File:" + unquote(url.split('?')[0].rstrip('/').split('/')[-1]).replace('_', ' ')


def sizes(titles):
    """{title: (w, h)} for existing files, {title: None} for missing ones."""
    out = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        for attempt in range(4):
            r = requests.get(API, params={
                "action": "query", "format": "json", "prop": "imageinfo",
                "iiprop": "size", "titles": "|".join(chunk)},
                headers={"User-Agent": UA}, timeout=30)
            if r.status_code == 429:
                time.sleep(float(r.headers.get('Retry-After') or 10 * (attempt + 1)))
                continue
            break
        q = r.json().get("query", {})
        back = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for p in q.get("pages", {}).values():
            t = back.get(p.get("title"), p.get("title"))
            ii = (p.get("imageinfo") or [{}])[0]
            out[t] = None if "missing" in p else (ii.get("width") or 0, ii.get("height") or 0)
        time.sleep(0.3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    min_edge = int(getattr(config, 'IMG_MIN_LONG_EDGE', 1200))

    for path in POOLS:
        with open(path, encoding='utf-8', newline='') as f:
            rd = csv.DictReader(f)
            rows, fields = list(rd), list(rd.fieldnames or [])
        if 'used' not in fields:
            fields.append('used')
        # Only rows not already carrying a permanent mark need checking.
        todo = [r for r in rows if r.get('image_url')
                and (r.get('used') or '').strip().upper() not in ('GONE', 'LOWRES', 'REJECT', 'TRUE')]
        dims = sizes(list(dict.fromkeys(title_of(r['image_url']) for r in todo)))
        gone = low = ok = 0
        for r in todo:
            d = dims.get(title_of(r['image_url']), 'unknown')
            if d == 'unknown':
                continue                      # API didn't answer for it: leave alone
            if d is None:
                r['used'] = 'GONE'; gone += 1
            elif max(d) < min_edge:
                r['used'] = 'LOWRES'; low += 1
            else:
                ok += 1
        name = os.path.basename(path)
        print(f"{name}: checked {len(todo)} | ok {ok} | retired LOWRES {low} | GONE {gone}")
        if not args.dry_run and (gone or low):
            with open(path, 'w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                for r in rows:
                    w.writerow({k: r.get(k, '') for k in fields})


if __name__ == '__main__':
    main()
