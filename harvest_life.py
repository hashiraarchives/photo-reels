"""
Harvest public-domain "life moments" photos for themed videos (2026-10).

The Golden Frame Hollywood study found its winners were REAL MOMENTS (a day
at the beach, a kiss, a night out), not studio portraits -- but its press
photos are copyrighted. This harvests the public-domain equivalent from
Wikimedia Commons, by category, into seed_data/goldmine_life_links.csv with a
`life_theme` column. Same license gate as harvest_goldmine3.py (PD/CC0 only,
no attribution-required licenses, no PD-Art reproductions).

Hard lines, enforced here before any photo reaches a video:
  * no children: anything whose title or description mentions a child, girl
    of school age, boy, baby, kids, family outing, etc. is skipped
  * no modern photos: 1900-1979 only
  * no print matter: posters, ads, postcards, magazine pages, drawings

    python harvest_life.py              # harvest all themes
    python harvest_life.py --dry-run    # count only
"""
import argparse
import csv
import html
import os
import re
import sys

import harvest_goldmine3 as h

OUT_CSV = os.path.join(h.SEED_DIR, "goldmine_life_links.csv")
HEADER = h.HEADER + ['life_theme', 'description']

THEME_CATEGORIES = {
    'beach': [
        "Category:Sennett Bathing Beauties",
        "Category:Bathing beauties",
        "Category:1910s swimwear",
        "Category:1920s swimwear",
        "Category:1930s swimwear",
        "Category:1940s swimwear",
        "Category:1950s swimwear",
    ],
}

_CHILD = re.compile(
    r"\b(child|children|kid|kids|boy|boys|baby|babies|infant|toddler|tot|tots|little girl|"
    r"little girls|schoolgirl|schoolgirls|school|youngster|youngsters|juvenile|junior|"
    r"son|daughter|family|families|mother and|father and|aged? \d|\d+[- ]year[- ]old|"
    r"pupils?|students?|scouts?|camp ?fire girls|orphan)\b", re.I)
_PRINT = re.compile(
    r"\b(poster|advert|advertisement|ad\b|postcard|post card|magazine|cover|catalog|catalogue|"
    r"drawing|illustration|painting|sketch|cartoon|pattern|label|brochure|newspaper|clipping|"
    r"sheet music|fashion plate|mannequin|statue|sculpture)\b", re.I)
_BEACH = re.compile(r"\b(swim\w*|bath\w*|beach\w*|surf\w*|seaside|sea shore|seashore|shore|"
                    r"pool|tidal basin|ocean|bikini\w*|sun ?bath\w*|lido|boardwalk|sand)\b", re.I)
# The swimwear categories are mostly European sports and fashion archives
# (Paris swimming championships, Dutch/Norwegian/Hungarian collections).
# Keep the American, Hollywood and Library of Congress beach photos.
_US = re.compile(r"\b(LCCN\d+|Bain|Sennett|bathing beaut\w*|Laurell|California|Cal\b|Washington|"
                 r"Atlantic City|Coney Island|Long Beach|Seal Beach|Palm Beach|Miami|Florida|Tidal Basin|"
                 r"Nantucket|Hollywood|Santa Monica|Malibu|Galveston|New Jersey|New York|Chicago|"
                 r"Asbury Park|Rockaway|Brighton Beach|American|National Photo Company)\b", re.I)
_FOREIGN = re.compile(r"\b(Sujet|Omschrijving|Bildet|Fortepan|btv1\w*|Tourelles|piscine|nageur\w*|Strand|"
                      r"Badmode|Frau|Postkarte|Engraving|photomechanical|Costume de bain|Joinville|SFA0\d+|"
                      r"no-nb|digifoto|Natation|France|Hungarian|Capbreton|serenade)\b", re.I)


def life_relevant(text: str) -> bool:
    import star_data as sd
    if _FOREIGN.search(text):
        return False
    return bool(_US.search(text)) or bool(sd.identify(text))


_MEN_ONLY = re.compile(r"\b(men's|mens|male|lifeguards?|swimming team|water polo)\b", re.I)


def _desc(f) -> str:
    raw = h._ext(f, 'ImageDescription') or h._ext(f, 'ObjectName') or ''
    txt = html.unescape(re.sub(r'<[^>]+>', ' ', raw))
    return ' '.join(txt.split())[:240]


def life_ok(f) -> str:
    """'' if acceptable, else the reason it was skipped."""
    try:
        ii = f['imageinfo'][0]
    except (KeyError, IndexError):
        return 'no info'
    title = f.get('title', '')
    catblob = h._ext(f, 'Categories').lower()
    licval = h._ext(f, 'License').lower()
    short = h._ext(f, 'LicenseShortName').lower()
    copyrighted = str(h._ext(f, 'Copyrighted')).lower()
    if ii.get('mediatype') != 'BITMAP':
        return 'not a photo'
    if copyrighted == 'true' or h._ext(f, 'Restrictions').strip():
        return 'license'
    if ('cc-by' in licval or 'cc by' in short or 'share alike' in short
            or str(h._ext(f, 'AttributionRequired')).lower() == 'true'):
        return 'license'
    if 'pd-art' in catblob or 'licensed-pd-art' in catblob:
        return 'license'
    pd_specific = any(t in catblob for t in h.PD_TAG_ALLOW)
    pd_generic = licval in ('pd', 'cc0', 'public domain') and copyrighted == 'false'
    if not (pd_specific or pd_generic):
        return 'license'
    yr = h.parse_year(h._ext(f, 'DateTimeOriginal'), title, catblob)
    if yr is None or not (1900 <= yr <= 1979):
        return 'era'
    text = f"{title} {_desc(f)}"
    if _CHILD.search(text):
        return 'child'
    if _PRINT.search(text) or any(b in catblob for b in h.CATEGORY_DENY):
        return 'print'
    if _MEN_ONLY.search(text):
        return 'men only'
    # the photo itself must be a beach/bathing moment (a star's subcategory
    # also holds her studio portraits, which would break the theme's promise)
    if not _BEACH.search(f"{text} {catblob}"):
        return 'off theme'
    if not life_relevant(f"{text} {catblob}"):
        return 'not American'
    w, hh = ii.get('width', 0), ii.get('height', 0)
    if max(w, hh) < 1200 or w / max(hh, 1) > 2.0 or hh / max(w, 1) > 2.4:
        return 'size'
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--depth', type=int, default=1, help='subcategory depth')
    args = ap.parse_args()

    existing = h.load_existing_urls()
    if os.path.exists(OUT_CSV):
        existing |= {r['image_url'] for r in csv.DictReader(open(OUT_CSV, encoding='utf-8'))}
    rows, seen, reasons = [], set(), {}
    for theme, cats in THEME_CATEGORIES.items():
        queue = [(c, 0) for c in cats]
        visited = set()
        while queue:
            cat, depth = queue.pop(0)
            if cat in visited:
                continue
            visited.add(cat)
            n_cat = 0
            for f in h.iter_files(cat):
                why = life_ok(f)
                if why:
                    reasons[why] = reasons.get(why, 0) + 1
                    continue
                row = h.row_from_file(f, cat)
                key = h.norm_base(row['image_filename'])
                if row['image_url'] in existing or key in seen:
                    continue
                seen.add(key)
                row.pop('_longedge', None)
                row['life_theme'] = theme
                row['description'] = _desc(f)
                rows.append(row)
                n_cat += 1
            print(f"  {theme}: {cat} -> {n_cat}")
            if depth < args.depth:
                for sub in h.iter_subcats(cat):
                    if not h._skip_subcat(sub) and not re.search(r'\b(19[89]\d|20\d\d)s?\b', sub):
                        queue.append((sub, depth + 1))
    print(f"accepted {len(rows)} | skipped: {reasons}")
    if args.dry_run or not rows:
        return
    new_file = not os.path.exists(OUT_CSV)
    with open(OUT_CSV, 'a', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=HEADER, extrasaction='ignore')
        if new_file:
            w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {OUT_CSV}")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
