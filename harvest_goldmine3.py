"""
AAP - goldmine3 harvester

Builds seed_data/goldmine3_links.csv: clean, commercial-safe (public-domain),
real SOLO vintage glamour PORTRAITS of actresses/actors (1900-1979), sourced from
the Wikimedia Commons MediaWiki Action API.

Why this exists: the original goldmine CSVs draw from studio "publicity photos"
categories that are ~50% posters / lobby cards / magazine pages / group scenes.
This harvester pulls from the profession-tagged PORTRAIT categories and per-star
trees, and filters per-file on license / era / dimensions / solo-ness so the
output CSV arrives pre-cleaned (the pipeline's own filter is only a filename
denylist and cannot judge license/era/resolution).

Output columns match the pipeline: image_filename,file_page_url,image_url,source_category,license,used
  - image_url = the ORIGINAL upload.wikimedia.org URL (the pipeline derives its
    own 3840px thumbnail from it via convert_to_thumbnail_url()).
  - used = "" (empty -> not used).
Accepted rows -> goldmine3_links.csv ; uncertain rows -> goldmine3_review.csv (human spot-check).

License/likeness note: "PD" clears COPYRIGHT only. Right-of-publicity is separate;
the 1900-1979 era gate (long-dead subjects) is the mitigation. This ships
copyright-clear images, not a blanket legal guarantee.

Usage:
  python harvest_goldmine3.py --target 3000 --max-cats 1200
  python harvest_goldmine3.py --target 80 --max-cats 8   # quick validation run
"""

import os
import re
import csv
import sys
import json
import time
import argparse
import urllib.parse
import requests

API = "https://commons.wikimedia.org/w/api.php"
UA = "VintageArchiveBot/1.0 (https://github.com/hashiraarchives; public-domain photo compilations) python-requests"
HERE = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.join(HERE, "seed_data")
OUT_CSV = os.path.join(SEED_DIR, "goldmine3_links.csv")   # shipped (seeded to /data)
# Review pile + crawl state stay in the project root (NOT seed_data), so they are
# never copied to the Railway volume and don't get committed as pipeline data.
REVIEW_CSV = os.path.join(HERE, "goldmine3_review.csv")
STATE_JSON = os.path.join(HERE, "harvest_state.json")
HEADER = ["image_filename", "file_page_url", "image_url", "source_category", "license", "used"]

# Seed categories. The channel is HOLLYWOOD glamour/pinup, so we lead with per-star
# trees of recognizable US stars (inherently on-brand) + US studio publicity, and
# treat the generic international "portrait photographs" categories as secondary
# (they're flooded with non-Hollywood European stage portraits — see
# EUROPEAN_STAGE_DENY, which prunes that flood).
_HOLLYWOOD_STARS = [
    "Marilyn Monroe", "Grace Kelly", "Lana Turner", "Rita Hayworth", "Ava Gardner",
    "Clara Bow", "Lillian Gish", "Mary Pickford", "Hedy Lamarr", "Veronica Lake",
    "Gene Tierney", "Carole Lombard", "Vivien Leigh", "Elizabeth Taylor", "Sophia Loren",
    "Audrey Hepburn", "Bette Davis", "Joan Crawford", "Greta Garbo", "Jean Harlow",
    "Louise Brooks", "Barbara Stanwyck", "Claudette Colbert", "Myrna Loy", "Ingrid Bergman",
    "Lauren Bacall", "Dorothy Lamour", "Ginger Rogers", "Katharine Hepburn", "Maureen O'Hara",
    "Jane Russell", "Betty Grable", "Bettie Page", "Jayne Mansfield", "Kim Novak",
    "Natalie Wood", "Raquel Welch", "Brigitte Bardot", "Marlene Dietrich", "Mae West",
    "Doris Day", "Debbie Reynolds", "Shirley Temple", "Judy Garland", "Rita Moreno",
    "Anita Ekberg", "Gina Lollobrigida", "Dolores del Rio", "Joan Bennett", "Hedda Hopper",
    # Leading men (the 65+ audience skews male; recognizable faces still hook)
    "Cary Grant", "Clark Gable", "Humphrey Bogart", "James Dean", "Gary Cooper",
    "Errol Flynn", "Gregory Peck", "Marlon Brando", "James Stewart", "Spencer Tracy",
    "Tyrone Power", "Robert Mitchum", "Kirk Douglas", "Burt Lancaster", "Rock Hudson",
    "Paul Newman", "Frank Sinatra", "Fred Astaire", "Gene Kelly", "Steve McQueen",
    # 2026-07 expansion (second harvest wave — new star trees for fresh material)
    "Olivia de Havilland", "Joan Fontaine", "Irene Dunne", "Loretta Young",
    "Paulette Goddard", "Ann Sheridan", "Susan Hayward", "Esther Williams",
    "Cyd Charisse", "Eleanor Powell", "Alice Faye", "Betty Hutton",
    "Linda Darnell", "Jeanne Crain", "Gloria Swanson", "Norma Shearer",
    "Constance Bennett", "Kay Francis", "Miriam Hopkins", "Sylvia Sidney",
    "Jean Arthur", "Rosalind Russell", "Donna Reed", "Deborah Kerr",
    "Janet Leigh", "Anne Baxter", "Gene Autry", "William Holden",
    "Henry Fonda", "Robert Taylor (actor)", "Alan Ladd", "Glenn Ford",
    "Montgomery Clift", "Charlton Heston", "Dean Martin", "John Wayne",
    "Buster Keaton", "Charlie Chaplin", "Rudolph Valentino", "Douglas Fairbanks",
    # 2026-09 third wave. The audience is US men 65+, i.e. born in the 1940s-50s:
    # the stars they grew up WITH are 1950s-60s film and TV faces, which the
    # earlier (silent/1930s-heavy) waves under-represent. Nostalgia lands hardest
    # on people the viewer actually remembers.
    "Ann-Margret", "Barbara Eden", "Tina Louise", "Angie Dickinson", "Julie Newmar",
    "Mamie Van Doren", "Jane Wyman", "Ann Miller", "June Allyson", "Vera-Ellen",
    "Virginia Mayo", "Yvonne De Carlo", "Rhonda Fleming", "Arlene Dahl", "Piper Laurie",
    "Jean Simmons", "Eva Marie Saint", "Dorothy Malone", "Joan Collins", "Julie London",
    "Terry Moore", "Stella Stevens", "Lee Remick", "Carroll Baker", "Shirley MacLaine",
    "Tuesday Weld", "Sandra Dee", "Vera Miles", "Mitzi Gaynor", "Lucille Ball",
    "Ida Lupino", "Merle Oberon", "Gloria Grahame", "Lizabeth Scott", "Jane Powell",
    "Kathryn Grayson", "Dorothy Dandridge", "Lena Horne", "Jill St. John", "Elke Sommer",
    "Ursula Andress", "Claudia Cardinale", "Martha Hyer", "Evelyn Keyes", "Fay Wray",
    "Anna May Wong", "Theda Bara", "Colleen Moore", "Pola Negri", "Marion Davies",
    "Tony Curtis", "Robert Wagner", "Rory Calhoun", "Tab Hunter", "Troy Donahue",
    "Victor Mature", "Dana Andrews", "Van Johnson", "Randolph Scott", "Joel McCrea",
    "Fred MacMurray", "Ray Milland", "Audie Murphy", "Jeff Chandler", "Cornel Wilde",
    "Clint Walker", "James Garner", "Richard Widmark", "Sterling Hayden", "Robert Ryan",
]
SEED_CATEGORIES = (
    [f"Category:{s}" for s in _HOLLYWOOD_STARS] + [
        "Category:Pin-up girls",
        "Category:Glamour photographs of women",
        "Category:Black and white portrait photographs of actresses",
        "Category:Black and white portrait photographs of actors",
        # 2026-07 expansion: master-photographer & studio-portrait troves
        "Category:Photographs by George Hurrell",
        "Category:Photographs by Carl Van Vechten",
        "Category:Publicity photographs of actors",
        "Category:Studio portrait photographs of women",
    ]
)

# ---- filtering constants (from the sourcing spec) ----
PD_TAG_ALLOW = [
    'pd us no notice', 'pd-us-no notice', 'pd us not renewed', 'pd-us-not renewed',
    'pd us expired', 'pd-us-expired', 'pd-1996', 'pd-old', 'pd-usgov',
    'pd us government', 'cc0', 'cc-zero', 'public domain',
]
FILENAME_DENY = [
    'poster', 'one sheet', 'one-sheet', 'half sheet', 'half-sheet', 'three sheet', 'insert',
    'lobby', 'lobbycard', 'lobby card', 'title card', 'herald', 'pressbook', 'press book',
    'press sheet', 'sheet music', 'song sheet', 'advert', 'advertis', 'trade ad', 'billboard',
    'magazine', 'photoplay', 'photo-play', 'picture-play', 'picture play', 'motion picture',
    'picture show', 'shadowland', 'film fun', 'movie weekly', 'movie classic', 'movie mirror',
    'silver screen', 'screen book', 'exhibitor', 'screenland', 'modern screen',
    'motion picture herald', 'program', 'programme', 'brochure', 'flyer', 'handbill', 'window card',
    'display', 'scene from', 'a scene', 'still from', 'film still', 'production still', 'montage',
    'collage', 'contact sheet', 'cast', 'group', 'ensemble', 'premiere', 'banquet', 'party',
    'crowd', 'on the set', 'behind the scenes', ' bts', 'screenshot', 'screen capture', 'frame from',
    'newspaper', 'clipping', 'cartoon', 'caricature', 'drawing', 'illustration', 'sketch', 'painting',
    'autograph', 'signature', 'letter', 'document', ' map', 'logo', 'trademark', 'ticket',
    'handprint', 'playbill', 'postcard', 'front cover', 'back cover',
    'theater ad', 'theatre ad', 'newspaper', ' theater -', ' theatre -',
]
CATEGORY_DENY = [
    'film posters', 'movie posters', 'lobby cards', 'advertisements', 'magazine covers',
    'film stills', 'title cards', 'sheet music', 'heralds', 'pressbooks', 'group photographs',
    'scenes from', 'posters', 'cigarette cards', 'caricatures', 'paintings', 'drawings',
]
# Non-Hollywood European stage portraits (esp. the Swedish "SMV" theatre-museum
# collection) flood the generic international portrait categories — drop them.
EUROPEAN_STAGE_DENY = [
    'teatern', 'operan', 'rollporträtt', 'rollportratt', 'smv -', '- smv', 'smv-',
    'dramatiska', 'oscarsteatern', 'folkteatern', 'svenska teatern', 'kungliga',
    'stadsteater', 'dramaten', 'theatermuseum', 'teatermuseum', 'skbl',
    'pictorial history of the silent screen', 'a pictorial history',
]
# Subcategory titles to NOT recurse into (off-glamour branches that waste the crawl).
SUBCAT_SKIP = [
    'grave', 'ship', 'handprint', 'footprint', 'statue', 'plaque', 'wedding', 'funeral',
    'tomb', 'exhibition', 'award', 'ceremon', 'signature', 'stamp', 'coin', 'street',
    'building', 'house', 'memorial', 'document', 'poster', 'lobby', 'magazine', 'museum',
    'memorabilia', 'filmography', 'trading card', 'audio', 'video', 'trailer',
]
PORTRAIT_BOOST_CATS = ['portrait photographs', 'studio portraits', 'publicity photographs']
# Minimum long edge in px (metadata check, no download). 2026-07: aligned with
# the runtime gate (config.IMG_MIN_LONG_EDGE = 1200) — the first 1400px run
# starved the harvest (166 accepted, 17k rejects) by discarding the
# 1200-1399px tier the pipeline happily uses. Overridable via --min-edge.
MIN_LONG_EDGE = 1200
ALLOW_SIGNALS = ['portrait', 'headshot', 'publicity', 'glamour', 'studio portrait', 'sayre', 'hurrell']
_YEAR_RE = re.compile(r'\b(18\d\d|19\d\d|20\d\d)\b')
_NAME_RUN = re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+')
_VARIANT_SUFFIX = re.compile(
    r'\s*\((cropped|tighter crop|tight crop|edit\d*|retouched|restored|colou?rized|\d+)\)', re.I)


def _ext(f, key):
    try:
        return (f['imageinfo'][0]['extmetadata'].get(key, {}) or {}).get('value', '') or ''
    except (KeyError, IndexError, TypeError):
        return ''


def parse_year(*texts):
    for t in texts:
        for m in _YEAR_RE.findall(t or ''):
            y = int(m)
            if 1850 <= y <= 2100:
                return y
    return None


def count_person_runs(title):
    base = _VARIANT_SUFFIX.sub('', re.sub(r'\.(jpg|jpeg|png|tif|tiff)$', '', title, flags=re.I))
    base = re.sub(r'\bin\b.*$', '', base)  # drop "<Name> in <Film>" tail
    runs = 0
    for c in re.split(r'\band\b|\bwith\b|&|,', base, flags=re.I):
        if _NAME_RUN.search(c):
            runs += 1
    return runs


def evaluate(f):
    """Return 'ACCEPT' | 'FLAG_REVIEW' | 'REJECT' for a single API file object."""
    try:
        ii = f['imageinfo'][0]
    except (KeyError, IndexError):
        return 'REJECT'
    w, h = ii.get('width', 0), ii.get('height', 0)
    if not w or not h:
        return 'REJECT'
    title = f.get('title', '')
    n = title.lower()
    catblob = _ext(f, 'Categories').lower()
    licval = _ext(f, 'License').lower()
    shortname = _ext(f, 'LicenseShortName').lower()
    copyrighted = str(_ext(f, 'Copyrighted')).lower()
    restrictions = _ext(f, 'Restrictions').strip()

    # 1) LICENSE GATE (advertiser safety; non-negotiable)
    if ii.get('mediatype') != 'BITMAP':
        return 'REJECT'
    if copyrighted == 'true':
        return 'REJECT'
    if restrictions:
        return 'REJECT'
    if ('cc-by' in licval or 'cc by' in shortname or 'share alike' in shortname
            or str(_ext(f, 'AttributionRequired')).lower() == 'true'):
        return 'REJECT'
    if 'pd-art' in catblob or 'licensed-pd-art' in catblob:
        return 'REJECT'
    pd_specific = any(t in catblob for t in PD_TAG_ALLOW)
    pd_generic = licval in ('pd', 'cc0', 'public domain') and copyrighted == 'false' and not restrictions
    if not (pd_specific or pd_generic):
        return 'REJECT'

    # 2) ERA GATE (1900-1979)
    yr = parse_year(_ext(f, 'DateTimeOriginal'), title, catblob)
    if yr is None or not (1900 <= yr <= 1979):
        return 'REJECT'

    # 3) FILENAME DENYLIST + multi-person + non-Hollywood European stage
    if any(tok in n for tok in FILENAME_DENY):
        return 'REJECT'
    if any(tok in n or tok in catblob for tok in EUROPEAN_STAGE_DENY):
        return 'REJECT'
    if count_person_runs(title) >= 2:
        return 'REJECT'

    # 4) CATEGORY DENYLIST + multi-person from categories
    if any(bad in catblob for bad in CATEGORY_DENY):
        return 'REJECT'
    person_cats = [c for c in catblob.split('|')
                   if re.fullmatch(r"[a-z][a-z]+(?:\s+[a-z.']+){1,3}", c.strip())]
    if len(person_cats) >= 3:
        return 'REJECT'

    # 5) DIMENSION / ASPECT (no download)
    longedge = max(w, h)
    if longedge < MIN_LONG_EDGE:
        return 'REJECT'
    if w / h > 1.5:
        return 'REJECT'
    if h / w > 2.2:
        return 'REJECT'

    # 6) SOFT SCORE -> ACCEPT / FLAG_REVIEW
    s = 0
    if any(p in catblob for p in PORTRAIT_BOOST_CATS):
        s += 3
    if any(tok in n for tok in ALLOW_SIGNALS):
        s += 1
    if 1.1 <= h / w <= 1.6:
        s += 1
    if re.search(r'\b19[0-7]\d\b', title):
        s += 1
    if ' in ' in n and not any(p in catblob for p in PORTRAIT_BOOST_CATS):
        s -= 2
    return 'ACCEPT' if s >= 2 else 'FLAG_REVIEW'


# ---- Commons API plumbing ----
_session = requests.Session()
_session.headers.update({"User-Agent": UA})


def api_get(params, retries=5):
    params = dict(params)
    params.update({"format": "json", "maxlag": 5})
    backoff = 5
    for attempt in range(retries):
        try:
            r = _session.get(API, params=params, timeout=30)
            if r.status_code == 429 or 'maxlag' in r.text[:200].lower():
                wait = int(r.headers.get('Retry-After', backoff))
                time.sleep(min(wait, 60))
                backoff = min(backoff * 2, 60)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == retries - 1:
                print(f"  API error ({e}) on {params.get('gcmtitle') or params.get('cmtitle')}")
                return {}
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
    return {}


def iter_files(category):
    """Yield file objects (with imageinfo) for a category, paginated."""
    cont = {}
    while True:
        params = {
            "action": "query", "generator": "categorymembers",
            "gcmtitle": category, "gcmtype": "file", "gcmlimit": 500,
            "prop": "imageinfo", "iiprop": "url|size|mediatype|extmetadata",
            "iiextmetadatafilter": "License|LicenseShortName|UsageTerms|Copyrighted|Restrictions|"
                                   "AttributionRequired|Categories|ImageDescription|DateTimeOriginal|"
                                   "ObjectName|Artist",
        }
        params.update(cont)
        data = api_get(params)
        for page in (data.get("query", {}).get("pages", {}) or {}).values():
            if "imageinfo" in page:
                yield page
        cont = data.get("continue", {})
        if not cont:
            break


def iter_subcats(category):
    cont = {}
    while True:
        params = {"action": "query", "list": "categorymembers", "cmtitle": category,
                  "cmtype": "subcat", "cmlimit": 500}
        params.update(cont)
        data = api_get(params)
        for m in data.get("query", {}).get("categorymembers", []):
            yield m["title"]
        cont = data.get("continue", {})
        if not cont:
            break


def load_existing_urls():
    urls = set()
    for name in ("goldmine_links.csv", "goldmine2_links.csv", "goldmine3_links.csv"):
        p = os.path.join(SEED_DIR, name)
        if os.path.exists(p):
            try:
                for row in csv.DictReader(open(p, encoding='utf-8')):
                    if row.get('image_url'):
                        urls.add(row['image_url'])
            except Exception as e:
                print(f"  could not read {name} for dedup: {e}")
    return urls


def _skip_subcat(title):
    """Don't recurse into off-glamour branches or post-1979 year subcats."""
    t = title.lower()
    if any(k in t for k in SUBCAT_SKIP):
        return True
    m = re.search(r'\bin (\d{4})\b', t)
    if m and int(m.group(1)) > 1979:
        return True
    return False


def norm_base(title):
    """Collapse crop/edit variants to a common key so we keep only the best version."""
    t = re.sub(r'\.(jpg|jpeg|png|tif|tiff)$', '', title, flags=re.I)
    return _VARIANT_SUFFIX.sub('', t).strip().lower()


def row_from_file(f, source_category):
    title = f['title'].replace('File:', '', 1)
    ii = f['imageinfo'][0]
    return {
        'image_filename': title,
        'file_page_url': "https://commons.wikimedia.org/wiki/File:" +
                         urllib.parse.quote(title.replace(' ', '_')),
        'image_url': ii['url'],
        'source_category': source_category.replace('Category:', ''),
        'license': _ext(f, 'LicenseShortName') or _ext(f, 'License') or 'Public domain',
        'used': '',
        '_longedge': max(ii.get('width', 0), ii.get('height', 0)),
    }


def main():
    global MIN_LONG_EDGE
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', type=int, default=3000, help='stop after this many accepted rows')
    ap.add_argument('--max-cats', type=int, default=1200, help='cap categories crawled')
    ap.add_argument('--depth', type=int, default=3, help='subcategory recursion depth')
    ap.add_argument('--min-edge', type=int, default=MIN_LONG_EDGE,
                    help='min long edge px (metadata check)')
    ap.add_argument('--revisit', action='store_true',
                    help='re-crawl categories already visited in a previous run')
    args = ap.parse_args()
    MIN_LONG_EDGE = args.min_edge

    os.makedirs(SEED_DIR, exist_ok=True)
    existing = load_existing_urls()
    print(f"Loaded {len(existing)} existing image_urls for dedup")

    # Resume awareness: skip categories a previous run already crawled (their
    # accepted files are in the CSVs; re-crawling only burns API time on dups).
    prior_visited = set()
    if not args.revisit and os.path.exists(STATE_JSON):
        try:
            prior_visited = set(json.load(open(STATE_JSON)).get('visited', []))
            print(f"Resuming: skipping {len(prior_visited)} previously crawled categories "
                  f"(--revisit to override)")
        except Exception as e:
            print(f"Could not read {STATE_JSON}: {e}")

    seen_urls = set()
    best_by_base = {}   # normalized base -> accepted row (keep largest)
    review = []
    counts = {'ACCEPT': 0, 'FLAG_REVIEW': 0, 'REJECT': 0, 'DUP': 0}

    # BFS over categories
    queue = [(c, 0) for c in SEED_CATEGORIES]
    visited = set(prior_visited)
    cats_done = 0

    while queue and len(best_by_base) < args.target and cats_done < args.max_cats:
        cat, depth = queue.pop(0)
        if cat in visited:
            continue
        visited.add(cat)
        cats_done += 1
        cat_accept = 0
        for f in iter_files(cat):
            url = f.get('imageinfo', [{}])[0].get('url')
            if not url:
                continue
            if url in existing or url in seen_urls:
                counts['DUP'] += 1
                continue
            verdict = evaluate(f)
            counts[verdict] += 1
            if verdict == 'REJECT':
                continue
            seen_urls.add(url)
            row = row_from_file(f, cat)
            if verdict == 'FLAG_REVIEW':
                review.append(row)
                continue
            base = norm_base(row['image_filename'])
            prev = best_by_base.get(base)
            if prev is None or row['_longedge'] > prev['_longedge']:
                best_by_base[base] = row
                if prev is None:
                    cat_accept += 1
            if len(best_by_base) >= args.target:
                break
        # enqueue subcats (skip off-glamour / post-1979 branches)
        if depth < args.depth:
            for sub in iter_subcats(cat):
                if sub not in visited and not _skip_subcat(sub):
                    queue.append((sub, depth + 1))
        print(f"[{cats_done}] {cat[:60]:60s} +{cat_accept} accepted "
              f"(total {len(best_by_base)} | review {len(review)} | dup {counts['DUP']})")

    # write outputs
    def write(path, rows):
        new = not os.path.exists(path)
        with open(path, 'a', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=HEADER)
            if new:
                w.writeheader()
            for r in rows:
                w.writerow({k: r[k] for k in HEADER})

    accepted = list(best_by_base.values())
    write(OUT_CSV, accepted)
    if review:
        write(REVIEW_CSV, review)
    json.dump({'visited': sorted(visited), 'accepted': len(accepted)},
              open(STATE_JSON, 'w'), indent=2)

    print("\n=== DONE ===")
    print(f"Accepted (shipped): {len(accepted)} -> {OUT_CSV}")
    print(f"Flagged for review: {len(review)} -> {REVIEW_CSV}")
    print(f"Verdicts: {counts}")
    print(f"Categories crawled: {cats_done}")


if __name__ == "__main__":
    main()
