"""
AAP - Actress Actor and Pinups
Main Video Generator

Creates ~20 minute slideshow videos with:
- Branded intro
- ~100 images at 12 seconds each (the verified reference-channel container)
- Era-angle image selection rotated daily (anti-template variation)
- Succinct outlined captions
- Continuous background music
"""

import os
import sys
import csv
import json
import random
import re
import subprocess
import unicodedata
import tempfile
import shutil
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import requests
from PIL import Image
import config
from scrape_descriptions import scrape_batch, get_wikimedia_description

# Try to import browser downloader (preferred method)
try:
    from browser_downloader import BrowserDownloader
    BROWSER_DOWNLOAD_AVAILABLE = True
except ImportError:
    BROWSER_DOWNLOAD_AVAILABLE = False
    print("Warning: browser_downloader not available, using requests (may hit rate limits)")


# Promotional-graphic terms to EXCLUDE — the owner wants real photographs of the
# stars (portraits, publicity photos, candids, film stills), NOT promo art. Film
# "stills" are real photographs and are deliberately KEPT.
_JUNK_TERMS = (
    'poster', 'one sheet', 'one-sheet', 'onesheet', 'half sheet', 'half-sheet',
    'three sheet', 'three-sheet', 'window card', 'lobby card', 'lobbycard', 'lobby',
    'herald', 'playbill', 'broadside', 'press book', 'pressbook', 'press sheet',
    'magazine', 'sheet music', 'cigarette card', 'trading card', 'postcard',
    'caricature', 'cartoon', 'title card', 'logo', 'advert', 'advertis',
    'front cover', 'back cover', 'dust jacket', 'diagram', 'map of',
)


def _passes_quality(row: Dict) -> bool:
    """True if the row looks like a real photo of a person, not promotional graphics."""
    t = ((row.get('image_filename') or '') + ' ' + (row.get('source_category') or '')).lower()
    return not any(term in t for term in _JUNK_TERMS)


def _row_is_available(row: Dict) -> bool:
    """
    Availability with RECYCLING. The PD photo pool is finite (the curated
    goldmine3 drained from 1,300 to ~32 usable rows in under a month), so
    marking a row used-forever starves the channel. mark_images_used now stamps
    a DATE; a dated row becomes available again after IMG_REUSE_DAYS (viewers
    don't notice a photo repeating two months later — the reference channels
    recycle far more aggressively). Legacy 'TRUE' marks carry no date and stay
    blocked, so recycling only ever applies to precisely-known usage.
    """
    used = (row.get('used') or '').strip()
    if not used:
        return True
    if used.upper() == 'TRUE':
        return False                      # legacy mark, date unknown → blocked
    try:
        used_on = datetime.strptime(used[:10], '%Y-%m-%d')
        cooldown = int(getattr(config, 'IMG_REUSE_DAYS', 60))
        return (datetime.now() - used_on).days >= cooldown
    except ValueError:
        return False


def _read_image_csv(path: str):
    """Read a goldmine CSV -> (rows, fieldnames). Tolerant of a missing file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader), reader.fieldnames
    except FileNotFoundError:
        print(f"Warning: {path} not found")
    except Exception as e:
        print(f"Error reading {path}: {e}")
    return [], None


# === Content angles (anti-template variation) ===
# Each day biases image selection toward a distinct era window so consecutive
# videos differ visibly in CONTENT, not just title — near-identical daily
# uploads are what tripped the mass-produced/"inauthentic content" demotion.
# 'mixed' days interleave so thin era buckets aren't exhausted. Era days take
# ~60% of the video from the window (rest mixed); a day degrades to mixed when
# fewer than 30 matching rows remain. Rotation is date-based and stateless.
_CONTENT_ANGLES = [
    ('silent-to-prewar', 1920, 1939),
    ('mixed', None, None),
    ('forties-fifties', 1940, 1959),
    ('mixed', None, None),
    ('fifties-to-seventies', 1950, 1979),
    ('mixed', None, None),
]

_ANGLE_YEAR_RE = re.compile(r'\b(19[0-7]\d)\b')


def _row_year(row: Dict) -> Optional[int]:
    """Year parsed from a goldmine row's filename/category text, else None."""
    m = _ANGLE_YEAR_RE.search((row.get('image_filename') or '') + ' '
                              + (row.get('source_category') or ''))
    return int(m.group(1)) if m else None


def get_daily_angle() -> Tuple[str, Optional[int], Optional[int]]:
    """Today's content angle (name, year_lo, year_hi); deterministic by date."""
    idx = datetime.now().date().toordinal() % len(_CONTENT_ANGLES)
    return _CONTENT_ANGLES[idx]


# === STAR-FOCUSED EPISODES (2026-07) ===
# The channel's biggest structural weakness was that content selection was
# random: every video held 60-90 unrelated people, so no video was ever ABOUT
# anything, nothing was searchable, and no title could be specific. On this
# channel's own data (controlled window, same template) star-named titles ran
# median 380 views vs 233 for generic hooks, and every all-time best video is a
# single-star episode. A star day builds most of the video from ONE star.
STAR_EPISODE_SHARE = 0.65      # fraction of the video drawn from the focus star
# 15, down from 25 (2026-08): five consecutive production days produced ZERO
# star episodes — the volume's used-state pushed per-star unused counts below
# 25, and the 'mixed'-day gate skipped half of all days outright. 15 rows of
# one star (plus era-matched contemporaries) is still a coherent episode, and
# 51 stars clear it against the seed pools.
STAR_EPISODE_MIN_ROWS = 15


def _rows_for_star(pools, star: str) -> List[Dict]:
    """Unused rows whose filename/category names this star."""
    return [r for _, usable in pools for r in usable
            if star in ((r.get('image_filename') or '') + ' '
                        + (r.get('source_category') or '')).lower()]


def pick_focus_star(pools) -> Optional[str]:
    """
    Choose the star for today's episode: the one with the most unused material,
    excluding those used in recent episodes so the channel doesn't run five
    Marilyn videos in a row. Returns a proper-cased name, or None if no star has
    enough material (caller then falls back to an era/mixed day).

    Every early return prints WHY. The first live star-episode run (2026-07-29)
    declined silently and the video shipped as a generic era day; nothing in the
    log said the star pass had even been attempted, so the regression was only
    findable by reading the source.
    """
    try:
        from youtube_uploader import LEADING_LADIES, KNOWN_STARS
        candidates = list(LEADING_LADIES) + [s for s in KNOWN_STARS
                                             if s not in LEADING_LADIES]
    except Exception as e:
        print(f"  STAR EPISODE: skipped — could not load star lists ({e})")
        return None

    recent = set()
    try:
        with open(config.STAR_RECENT_LEDGER, 'r', encoding='utf-8') as f:
            recent = {s.lower() for s in (json.load(f) or [])[-8:]}
    except Exception:
        pass

    counts = []
    all_counts = []
    for s in candidates:
        n = len(_rows_for_star(pools, s))
        if n:
            all_counts.append((n, s))
        if s in recent:
            continue
        if n >= STAR_EPISODE_MIN_ROWS:
            counts.append((n, s))
    if not counts:
        # Almost always a SUPPLY problem: the curated star-dense pool
        # (goldmine3) drains first because it is priority-one in pass 2, and
        # once it is spent no star clears the bar. Print the bench so the next
        # reader can see how far short we are and top up goldmine3.
        all_counts.sort(reverse=True)
        bench = ', '.join(f"{s}:{n}" for n, s in all_counts[:8]) or '(none)'
        print(f"  STAR EPISODE: declined — no star has "
              f"{STAR_EPISODE_MIN_ROWS}+ unused rows. Deepest: {bench}"
              + (f" | skipped as recent: {sorted(recent)}" if recent else ""))
        return None
    # Among those with enough material, prefer the deepest bench, breaking ties
    # by date so the choice is stable within a day.
    counts.sort(reverse=True)
    top = counts[:6]
    return top[datetime.now().date().toordinal() % len(top)][1]


def record_focus_star(star: str):
    """Remember today's star so the next few episodes pick someone else."""
    try:
        try:
            with open(config.STAR_RECENT_LEDGER, 'r', encoding='utf-8') as f:
                ledger = json.load(f) or []
        except Exception:
            ledger = []
        ledger.append(star)
        os.makedirs(os.path.dirname(config.STAR_RECENT_LEDGER), exist_ok=True)
        with open(config.STAR_RECENT_LEDGER, 'w', encoding='utf-8') as f:
            json.dump(ledger[-60:], f)
    except Exception as e:
        print(f"  Could not update star ledger: {e}")


def select_unused_images(count: int = config.IMAGES_PER_VIDEO,
                         angle: Optional[Tuple[str, Optional[int], Optional[int]]] = None,
                         pool_paths: Optional[Tuple[str, ...]] = None,
                         star_share: Optional[float] = None
                         ) -> List[Dict]:
    """
    Select unused, quality (real-photo) images across the goldmine CSVs,
    biased toward today's content angle (era window) when one is active.

    Skips promotional graphics (posters, lobby cards, magazine covers, ads,
    etc.) and any row already marked used. All CSVs are 'used'-tracked.
    """
    angle_name, lo, hi = angle or get_daily_angle()

    # Usable rows per CSV, kept in priority order (goldmine3 curated first).
    # pool_paths lets a caller restrict the draw: a 13-photo SHORT can afford to
    # take everything from the curated pool, where the bulk pools are where the
    # damaged scans, scene stills and title cards live.
    pools: List[Tuple[str, List[Dict]]] = []
    for path in (pool_paths or (config.GOLDMINE3_CSV, config.GOLDMINE_CSV, config.GOLDMINE2_CSV)):
        rows, _ = _read_image_csv(path)
        if not rows:
            continue
        usable = [r for r in rows
                  if _row_is_available(r) and _passes_quality(r)]
        pools.append((os.path.basename(path), usable))

    selected: List[Dict] = []
    picked = set()  # id()s of already-chosen rows
    focus_star: Optional[str] = None

    def take(candidates: List[Dict], need: int) -> List[Dict]:
        chosen = random.sample(candidates, min(need, len(candidates))) if candidates else []
        picked.update(id(r) for r in chosen)
        return chosen

    # Pass 0 — STAR EPISODE. Build most of the video from one star so the video
    # is actually ABOUT someone: that is what makes a searchable title, a
    # coherent playlist and a thumbnail that matches the promise. Runs EVERY
    # day now — the old 'mixed'-day skip silently disabled star episodes on
    # half of all days, and star rotation already provides the day-to-day
    # variety the mixed days existed for.
    if getattr(config, 'STAR_EPISODES', True):
        star = pick_focus_star(pools)
        if star is None:
            best = max(((len(_rows_for_star(pools, s)), s) for s in
                        __import__('youtube_uploader').LEADING_LADIES),
                       default=(0, '-'))
            print(f"  No star episode: best available is {best[1]} with {best[0]} rows "
                  f"(need {STAR_EPISODE_MIN_ROWS})")
        if star:
            star_rows = [r for r in _rows_for_star(pools, star) if id(r) not in picked]
            # star_share=1.0 (used by SHORTS) makes the whole video one star.
            # A long-form video can mix in contemporaries, but a short burns the
            # star's NAME on screen, so any other face is a visible lie.
            share = STAR_EPISODE_SHARE if star_share is None else star_share
            got = take(star_rows, max(1, int(count * share)))
            # Scale the bar to the request. A 1-minute short selects ~17 rows,
            # so demanding a flat 15 star photos made star episodes impossible
            # for Shorts while long-form (130 rows) was unaffected.
            need = min(STAR_EPISODE_MIN_ROWS,
                       max(4, int(count * share * 0.8)))
            if len(got) >= need:
                selected.extend(got)
                focus_star = ' '.join(w.capitalize() for w in star.split())
                print(f"  STAR EPISODE: {focus_star} — {len(got)} photos "
                      f"({len(star_rows)} available)")
            else:
                # Not enough after filtering; give the rows back to the pool.
                print(f"  STAR EPISODE: declined — {star} had {len(star_rows)} "
                      f"rows but only {len(got)} survived selection "
                      f"(need {STAR_EPISODE_MIN_ROWS})")
                picked.difference_update(id(r) for r in got)
    elif getattr(config, 'STAR_EPISODES', True):
        print(f"  STAR EPISODE: not attempted — angle is '{angle_name}'")

    # Pass 1 — era-biased picks (~60% of the video) on era-angle days.
    if focus_star is None and lo is not None:
        in_window = lambda r: (y := _row_year(r)) is not None and lo <= y <= hi
        pref_total = sum(1 for _, usable in pools for r in usable if in_window(r))
        if pref_total >= 30:
            pref_target = int(count * 0.6)
            for name, usable in pools:
                if len(selected) >= pref_target:
                    break
                pref = [r for r in usable if id(r) not in picked and in_window(r)]
                got = take(pref, pref_target - len(selected))
                selected.extend(got)
                if got:
                    print(f"  {name}: took {len(got)} era-biased ({angle_name})")
        else:
            print(f"  angle '{angle_name}': only {pref_total} matching rows left — running as mixed")

    # Pass 2 — fill the remainder from all pools in priority order.
    for name, usable in pools:
        if len(selected) >= count:
            break
        rest = [r for r in usable if id(r) not in picked]
        got = take(rest, count - len(selected))
        selected.extend(got)
        print(f"  {name}: {len(rest)} usable photos available, took {len(got)}")

    # Ordering. On a star episode the star's photos are FRONT-LOADED, not
    # shuffled into the mix: at 12s/photo, 15-22 star rows fill the first
    # 3-4.5 minutes — which matches the channel's average view duration, so
    # the title's promise ("Lana Turner: ...") is delivered inside the window
    # people actually watch, even when the star is a minority of the full 20
    # minutes. This is what makes a sub-25-row star episode honest packaging
    # rather than the May-style promise mismatch.
    if focus_star:
        star_l = focus_star.lower()
        star_block = [r for r in selected
                      if star_l in ((r.get('image_filename') or '') + ' '
                                    + (r.get('source_category') or '')).lower()]
        rest = [r for r in selected if r not in star_block]
        random.shuffle(star_block)
        random.shuffle(rest)
        selected = star_block + rest
    else:
        random.shuffle(selected)  # interleave era-biased and mixed picks
    label = f"star:{focus_star}" if focus_star else f"angle:{angle_name}"
    print(f"Selected {len(selected)} images total ({label})")
    # Stamp the focus star on every row so it survives into metadata, where the
    # title, tags and playlist all need it.
    for r in selected:
        r['focus_star'] = focus_star or ''
    return selected


def mark_images_used(images: List[Dict]):
    """
    Mark selected images used in whichever goldmine CSV they came from. Adds a 'used'
    column to goldmine2 on first write (it shipped without one), so images stop
    repeating across videos and the remaining-supply count becomes accurate.
    """
    # A row that failed for a property of the FILE (deleted from Commons,
    # too small, blank) will fail identically next time, so it is retired
    # with a reason label instead of a date. Any non-date mark is permanently
    # unavailable in _row_is_available, whereas a date would recycle it into
    # the same failure 60 days later.
    today = datetime.now().strftime('%Y-%m-%d')
    mark_for = {img['image_url']: (img.get('retire') or today)
                for img in images if img.get('image_url')}
    used_urls = set(mark_for)
    if not used_urls:
        return
    for path in (config.GOLDMINE3_CSV, config.GOLDMINE_CSV, config.GOLDMINE2_CSV):
        rows, fieldnames = _read_image_csv(path)
        if not rows:
            continue
        fieldnames = list(fieldnames or rows[0].keys())
        if 'used' not in fieldnames:
            fieldnames.append('used')
        n = 0
        for row in rows:
            row.setdefault('used', '')
            if row.get('image_url') in used_urls:
                # Date-stamped (not 'TRUE') so _row_is_available can recycle
                # this row after the IMG_REUSE_DAYS cooldown.
                row['used'] = mark_for[row['image_url']]
                n += 1
        if n:
            try:
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                print(f"  Marked {n} images used in {os.path.basename(path)}")
            except Exception as e:
                print(f"Error updating {path}: {e}")


def convert_to_thumbnail_url(url: str, width: int = 3840) -> str:
    """
    Convert Wikimedia Commons URL to thumbnail URL.
    Thumbnail URLs are faster and less likely to trigger rate limits.

    Original: https://upload.wikimedia.org/wikipedia/commons/a/ab/File.jpg
    Thumbnail: https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/File.jpg/1920px-File.jpg
    """
    if '/thumb/' in url:
        return url  # Already a thumbnail

    # Pattern: /wikipedia/commons/X/XY/Filename.ext
    if '/wikipedia/commons/' in url and '/thumb/' not in url:
        parts = url.split('/wikipedia/commons/')
        if len(parts) == 2:
            base = parts[0] + '/wikipedia/commons/thumb/' + parts[1]
            filename = url.split('/')[-1]
            return f"{base}/{width}px-{filename}"

    return url  # Return original if can't convert


def download_image(url: str, save_path: str) -> bool:
    """Download an image from URL to local path. Uses thumbnail URLs to avoid rate limits."""
    headers = {
        "User-Agent": "AAP-Bot/1.0 (Actress Actor and Pinups; educational/research use)"
    }

    # Try thumbnail URL first (recommended by Wikimedia). 3840px is the PROVEN
    # width: probing live URLs showed Wikimedia returns HTTP 400 for the same
    # files at 2048px but 200 at 3840px (the 2026-08-08 run starved to ~24
    # images per video because of this). Download width is independent of the
    # 1080p canvas - resize handles the downscale.
    thumbnail_url = convert_to_thumbnail_url(url, 3840)

    for attempt in range(config.MAX_RETRIES):
        try:
            # Try thumbnail first, fall back to original
            try_url = thumbnail_url if attempt == 0 else url

            response = requests.get(try_url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()

            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True

        except Exception as e:
            if attempt < config.MAX_RETRIES - 1:
                print(f"  Retry {attempt + 1}/{config.MAX_RETRIES}: {e}")
                time.sleep(5)  # Wait longer between retries
                continue
            print(f"  Failed to download: {e}")
            return False

    return False


def _load_logo_overlay(target_w: int, target_h: int) -> Optional[Image.Image]:
    """Load and resize channel logo for watermark overlay. Cached after first call."""
    if not hasattr(_load_logo_overlay, '_cache'):
        _load_logo_overlay._cache = None
        _load_logo_overlay._tried = False

    if _load_logo_overlay._tried:
        return _load_logo_overlay._cache

    _load_logo_overlay._tried = True

    if not os.path.exists(config.LOGO_PATH):
        return None

    try:
        logo = Image.open(config.LOGO_PATH).convert('RGBA')
        # Logo height scales with canvas — ~80px at 1080p, ~160px at 4K.
        logo_h = int(80 * config.SCALE)
        logo_w = int(logo.width * (logo_h / logo.height))
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        # Make semi-transparent (70% opacity)
        alpha = logo.split()[3]
        alpha = alpha.point(lambda p: int(p * 0.7))
        logo.putalpha(alpha)
        _load_logo_overlay._cache = logo
        return logo
    except Exception:
        return None


def _create_branded_frame(target_w: int, target_h: int) -> Image.Image:
    """
    Create a branded overlay frame inspired by Retro Reflections style.
    Includes: decorative top border, side text, subtle vignette, logo watermark.

    All pixel dimensions scale with config.SCALE so the frame looks visually
    identical proportional to the canvas at any resolution (1080p, 1440p, 4K).
    """
    from PIL import ImageDraw

    s = config.SCALE
    sz = lambda n: int(n * s)

    frame = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    edge_depth = sz(180)
    max_alpha = 100
    for x in range(edge_depth):
        a = int(max_alpha * ((1 - x / edge_depth) ** 2.5))
        draw.line([(x, 0), (x, target_h)], fill=(0, 0, 0, a))
        draw.line([(target_w - 1 - x, 0), (target_w - 1 - x, target_h)], fill=(0, 0, 0, a))

    top_depth = sz(100)
    for y in range(top_depth):
        a = int(60 * ((1 - y / top_depth) ** 2))
        draw.line([(0, y), (target_w, y)], fill=(0, 0, 0, a))

    gold = (255, 215, 0, 120)
    draw.line([(sz(60), sz(30)), (target_w - sz(60), sz(30))], fill=gold, width=max(1, sz(1)))

    try:
        from PIL import ImageFont
        side_font = None
        for font_path in ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try:
                side_font = ImageFont.truetype(font_path, sz(16))
                break
            except (IOError, OSError):
                continue

        if side_font:
            side_text = "ACTRESS ACTOR AND PINUPS"
            txt_img = Image.new('RGBA', (sz(300), sz(24)), (0, 0, 0, 0))
            txt_draw = ImageDraw.Draw(txt_img)
            txt_draw.text((0, 0), side_text, font=side_font, fill=(255, 255, 255, 60))
            rotated = txt_img.rotate(90, expand=True)
            frame.paste(rotated, (sz(12), target_h // 2 - rotated.height // 2), rotated)

            era_text = "GOLDEN AGE OF HOLLYWOOD"
            txt_img2 = Image.new('RGBA', (sz(300), sz(24)), (0, 0, 0, 0))
            txt_draw2 = ImageDraw.Draw(txt_img2)
            txt_draw2.text((0, 0), era_text, font=side_font, fill=(255, 215, 0, 50))
            rotated2 = txt_img2.rotate(-90, expand=True)
            frame.paste(rotated2, (target_w - sz(36), target_h // 2 - rotated2.height // 2), rotated2)

    except Exception:
        pass

    logo = _load_logo_overlay(target_w, target_h)
    if logo:
        logo_x = target_w - logo.width - sz(30)
        logo_y = sz(45)
        frame.paste(logo, (logo_x, logo_y), logo)

    return frame


# Cache the branded frame (same for all images)
_branded_frame_cache = None


def _is_portrait(path: str) -> bool:
    """True if the ORIGINAL image is portrait-oriented. In this pool, portrait
    aspect ≈ a person; landscape ≈ cars/scenery/wide stills — used to keep
    face-less frames out of the thumbnail candidate set."""
    try:
        with Image.open(path) as im:
            w, h = im.size
        return h >= w * 0.95
    except Exception:
        return False


def check_image_quality(path: str) -> Tuple[bool, str]:
    """
    (ok, reason) for a freshly downloaded image. The absolute gates are
    RESOLUTION and ASPECT — reliable on vintage material. Sharpness
    (edge-variance) is off by default: film grain reads as "sharp" on old
    scans, so it's only trustworthy for RELATIVE ranking (see thumbnails).
    """
    min_edge = getattr(config, 'IMG_MIN_LONG_EDGE', 1200)
    max_aspect = getattr(config, 'IMG_MAX_ASPECT', 2.4)
    min_sharp = getattr(config, 'IMG_MIN_SHARPNESS', 0)
    try:
        with Image.open(path) as img:
            w, h = img.size
            if min_edge and max(w, h) < min_edge:
                return False, f"low-res {w}x{h} (< {min_edge}px)"
            aspect = max(w, h) / max(1, min(w, h))
            if max_aspect and aspect > max_aspect:
                return False, f"extreme aspect {aspect:.1f}"
            if min_sharp:
                from PIL import ImageFilter, ImageStat
                g = img.convert('L')
                g.thumbnail((1024, 1024))
                ev = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0]
                if ev < min_sharp:
                    return False, f"blurry (edge-var {ev:.0f} < {min_sharp})"
    except Exception as e:
        return False, f"unreadable ({e})"
    return True, "ok"


def resize_image_for_video(input_path: str, output_path: str) -> bool:
    """
    Resize image to fit 1920x1080 while showing the ENTIRE image.
    Creates a blurred background from the image itself to fill gaps.
    Adds branded frame overlay (logo, vignette, side text).
    No cropping - viewers see the complete original image.
    """
    global _branded_frame_cache

    try:
        from PIL import ImageFilter

        with Image.open(input_path) as img:
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            orig_w, orig_h = img.size
            target_w, target_h = config.WIDTH, config.HEIGHT
            target_ratio = target_w / target_h
            orig_ratio = orig_w / orig_h

            # Create blurred background from the original image
            # Scale to cover entire frame, then blur heavily
            bg_scale = max(target_w / orig_w, target_h / orig_h) * 1.2
            bg_w = int(orig_w * bg_scale)
            bg_h = int(orig_h * bg_scale)
            background = img.resize((bg_w, bg_h), Image.LANCZOS)

            # Crop background to target size (centered)
            bg_left = (bg_w - target_w) // 2
            bg_top = (bg_h - target_h) // 2
            background = background.crop((bg_left, bg_top, bg_left + target_w, bg_top + target_h))

            # Apply heavy blur to background
            background = background.filter(ImageFilter.GaussianBlur(radius=30))

            # Darken the background slightly so main image pops
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Brightness(background)
            background = enhancer.enhance(0.4)

            # Scale main image to fit entirely within frame (no cropping)
            scale = min(target_w / orig_w, target_h / orig_h)
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)
            main_img = img.resize((new_w, new_h), Image.LANCZOS)

            # Center the main image on the blurred background
            paste_x = (target_w - new_w) // 2
            paste_y = (target_h - new_h) // 2
            background.paste(main_img, (paste_x, paste_y))

            # Apply branded frame overlay (logo, vignette, side text)
            if _branded_frame_cache is None:
                _branded_frame_cache = _create_branded_frame(target_w, target_h)

            background = background.convert('RGBA')
            background = Image.alpha_composite(background, _branded_frame_cache)
            background = background.convert('RGB')

            background.save(output_path, 'JPEG', quality=95)
            return True

    except Exception as e:
        print(f"  Error resizing image: {e}")
        return False


# Wikimedia's User-Agent policy asks automated clients to identify themselves
# with a contact URL. The old path spoofed desktop Chrome from GitHub's shared
# Azure IPs -- the exact profile Wikimedia throttles -- and one 2026-09-21 run
# spent 77 min in 429 backoff for 24 images. Honest bots get treated better.
COMMONS_UA = ("VintageArchiveBot/1.0 (https://github.com/hashiraarchives; "
              "public-domain photo compilations) python-requests")
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def _commons_title(url: str) -> str:
    from urllib.parse import unquote
    return "File:" + unquote(url.split('?')[0].rstrip('/').split('/')[-1]).replace('_', ' ')


def resolve_commons_urls(urls: List[str], width: int) -> Dict[str, str]:
    """Map original upload URLs to a fetchable URL at <= `width` px, 50 files
    per API request. The API returns a valid thumbnail when the file is wider
    than `width` and the original otherwise -- hand-built "/thumb/.../3840px-"
    URLs 400'd for every file narrower than 3840 (Wikimedia will not upscale),
    which was ~2/3 of the pool."""
    import requests as _rq
    title_of = {u: _commons_title(u) for u in urls if u}
    by_title: Dict[str, str] = {}
    titles = list(dict.fromkeys(title_of.values()))
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        try:
            r = _rq.get(COMMONS_API, params={
                "action": "query", "format": "json", "prop": "imageinfo",
                "iiprop": "url|size", "iiurlwidth": width,
                "titles": "|".join(chunk)},
                headers={"User-Agent": COMMONS_UA}, timeout=30)
            data = r.json().get("query", {})
        except Exception as e:
            print(f"  Commons API batch failed ({type(e).__name__}); using raw URLs")
            continue
        # The API normalises titles; map normalised names back to what we sent.
        norm = {n["to"]: n["from"] for n in data.get("normalized", [])}
        for page in data.get("pages", {}).values():
            ii = (page.get("imageinfo") or [{}])[0]
            got = ii.get("thumburl") or ii.get("url")
            if got:
                by_title[norm.get(page.get("title"), page.get("title"))] = got
    return {u: by_title.get(t, u) for u, t in title_of.items()}


def _fetch(session, url: str, save_path: str, max_retries: int = 3) -> Tuple[bool, int]:
    """GET one file. Honours Retry-After on 429/503; permanent errors return
    immediately instead of sleeping through retries."""
    for attempt in range(max_retries + 1):
        try:
            r = session.get(url, timeout=30)
        except Exception as e:
            print(f"    fetch error: {type(e).__name__}")
            if attempt < max_retries:
                time.sleep(2 + attempt * 2)
                continue
            return False, 0
        if r.status_code == 200 and r.content:
            with open(save_path, 'wb') as f:
                f.write(r.content)
            return True, 200
        if r.status_code in (429, 503) and attempt < max_retries:
            try:
                wait = float(r.headers.get('Retry-After', ''))
            except ValueError:
                wait = 10 * (2 ** attempt)
            wait = min(max(wait, 5), 90) + random.uniform(0, 3)
            print(f"    {r.status_code}: waiting {wait:.0f}s (retry {attempt + 1}/{max_retries})")
            time.sleep(wait)
            continue
        return False, r.status_code
    return False, 429


async def download_with_browser(images: List[Dict], temp_dir: str,
                                target_count: Optional[int] = None) -> List[Dict]:
    """
    Download pool images from Wikimedia Commons.

    (Name kept for its callers: this no longer drives a headless browser. The
    Playwright path hit "Download is starting" on direct image URLs and, from
    datacenter IPs, drew heavy 429 throttling for its spoofed-Chrome profile.)

    1. Resolve every URL through the MediaWiki API in 50-file batches.
    2. Fetch serially over one keep-alive session with an honest bot UA and a
       short politeness delay; back off only when Wikimedia actually asks.

    Returns list of dicts with 'path', 'caption', 'index' for successfully
    downloaded images.
    """
    import requests as _rq
    width = int(getattr(config, 'DOWNLOAD_WIDTH', 1920))
    resolved = resolve_commons_urls([img.get('image_url') for img in images], width)
    session = _rq.Session()
    session.headers.update({"User-Agent": COMMONS_UA})
    image_paths = []
    failures = 0

    for i, img in enumerate(images):
        # Over-selection: stop as soon as enough images PASSED the gate.
        if target_count and len(image_paths) >= target_count:
            print(f"  Target of {target_count} quality images reached "
                  f"({i} of {len(images)} rows attempted)")
            break

        url = img.get('image_url')
        if not url:
            continue
        fetch_url = resolved.get(url, url)
        ext = os.path.splitext(fetch_url.split('?')[0])[-1] or '.jpg'
        download_path = os.path.join(temp_dir, f"orig_{i:03d}{ext}")

        success, status = _fetch(session, fetch_url, download_path)
        if not success:
            failures += 1
            print(f"  [{i+1}/{len(images)}] download failed ({status})")
            if status in (404, 410):
                img['quality_rejected'] = True   # gone from Commons: retire the row
                img['retire'] = 'GONE'
        else:
            ok, reason = check_image_quality(download_path)
            if not ok:
                # Blacklist the row (marked used later) so junk self-cleans.
                img['quality_rejected'] = True
                img['retire'] = 'LOWRES' if 'low-res' in str(reason) else 'REJECT'
                print(f"  [{i+1}/{len(images)}] quality reject: {reason}")
            elif resize_image_for_video(download_path,
                                        os.path.join(temp_dir, f"img_{i:03d}.jpg")):
                img['downloaded'] = True
                image_paths.append({
                    'path': os.path.join(temp_dir, f"img_{i:03d}.jpg"),
                    'orig': download_path,  # original photo (thumbnail source)
                    'caption': img.get('generated_caption', ''),
                    'filename': img.get('image_filename', ''),
                    'category': img.get('source_category', ''),
                    'index': i,
                    'portrait': _is_portrait(download_path),
                })

        await asyncio.sleep(random.uniform(0.6, 1.2))   # politeness, not evasion

    session.close()
    print(f"  Downloaded and processed {len(image_paths)}/{len(images)} images "
          f"({failures} failed)")
    return image_paths


def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file in seconds using ffprobe."""
    cmd = [
        config.FFPROBE_PATH,
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting audio duration: {e}")
        return 0


def create_audio_concat_file(video_duration: float, temp_dir: str) -> str:
    """
    Create a concat file for chaining audio tracks to cover video duration.
    Returns path to the audio concat file list.
    """
    # Get durations of all audio files
    audio_info = []
    for audio_path in config.AUDIO_FILES:
        if os.path.exists(audio_path):
            duration = get_audio_duration(audio_path)
            if duration > 0:
                audio_info.append((audio_path, duration))

    if not audio_info:
        raise ValueError("No valid audio files found!")

    # Shuffle for variety
    random.shuffle(audio_info)

    # Create concat list that covers video duration
    concat_list = []
    total_audio = 0
    i = 0

    while total_audio < video_duration:
        audio_path, duration = audio_info[i % len(audio_info)]
        concat_list.append(audio_path)
        total_audio += duration
        i += 1

    # Write concat file
    concat_file = os.path.join(temp_dir, "audio_concat.txt")
    with open(concat_file, 'w', encoding='utf-8') as f:
        for path in concat_list:
            # FFmpeg concat requires escaped paths
            escaped = path.replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    return concat_file


def _ffmpeg_escape_path(path: str) -> str:
    """
    Escape a filesystem path for use inside an FFmpeg filter argument.

    FFmpeg parses filter args with `:` as a key/value separator, so colons in
    paths (Windows drive letters, etc.) must be escaped. Backslashes are
    swapped to forward slashes so single-backslash escapes don't get consumed.
    """
    return path.replace('\\', '/').replace(':', r'\:')


# Max characters per line that fit inside the frame. Lowered for the larger
# prestige caption font so big white-outlined text doesn't overflow the edges
# (succinct captions are short, so they still fit in 1-2 lines).
_CAPTION_MAX_CHARS_PER_LINE = 40

# Smart-typography characters that DejaVu/Arial often render as tofu boxes
# in FFmpeg drawtext. Replace with ASCII fallbacks before drawing.
_CAPTION_REPLACEMENTS = {
    '—': ' - ',  # em dash
    '–': '-',    # en dash
    '‒': '-',    # figure dash
    '‐': '-',    # hyphen
    '‘': "'",    # left single quote
    '’': "'",    # right single quote / apostrophe
    '‚': "'",    # single low-9 quote
    '“': '"',    # left double quote
    '”': '"',    # right double quote
    '„': '"',    # double low-9 quote
    '…': '...',  # horizontal ellipsis
    ' ': ' ',    # non-breaking space
    ' ': ' ',    # thin space
    ' ': ' ',    # narrow no-break space
    '​': '',     # zero-width space
    '‌': '',     # zero-width non-joiner
    '‍': '',     # zero-width joiner
    '­': '',     # soft hyphen
    '﻿': '',     # BOM
}


def _sanitize_caption(text: str) -> str:
    """
    Force captions to pure ASCII so FFmpeg drawtext can render every glyph
    no matter which font ships on the host (Arial on Windows, DejaVu on
    Railway, etc.). The previous pass kept Latin-1 chars (é, ô, ñ) which
    rendered as small tofu rectangles at the end of lines on some hosts.

    Pipeline:
      1. Replace smart-typography NFKD can't handle (em-dash, smart quotes).
      2. NFKD decomposes accented chars (é -> e + combining acute) and many
         compat-form punctuation (… -> ..., NBSP -> space).
      3. `encode('ascii', 'ignore')` drops the combining marks and any other
         non-ASCII byte that survived.
      4. Collapse whitespace runs.
    """
    if not text:
        return text
    for k, v in _CAPTION_REPLACEMENTS.items():
        text = text.replace(k, v)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    text = ' '.join(text.split())
    return text.strip()


_YEAR_RE = re.compile(r'\b(18[5-9]\d|19[0-8]\d)\b')


def _extract_year(filename: str, caption: str) -> Optional[str]:
    """
    Pull a 4-digit year (1850-1989, the AAP era window) from the caption
    first; if the caption already has one, return None so we don't double-up.
    Otherwise try the source filename, which usually leads with the year
    (e.g. `1947-rita-hayworth-still.jpg`).
    """
    if caption and _YEAR_RE.search(caption):
        return None
    if filename:
        m = _YEAR_RE.search(filename)
        if m:
            return m.group(1)
    return None


def _wrap_caption(caption: str, filename: str = '') -> Optional[Dict]:
    """
    Wrap a caption into 1–3 lines that fit inside the 1920px frame and pick
    a font size that keeps every line within the safe text width.

    Returns a dict with the wrapped text and drawtext layout values, or None
    if the caption is empty.
    """
    caption = _sanitize_caption(caption or '')
    if not caption:
        return None

    # Year is mandatory — prepend `(YYYY)` if not already in the caption.
    year = _extract_year(filename, caption)
    if year:
        caption = f"({year}) {caption}"

    # Hard cap at 165 chars (~3 full lines). Ellipsize on a word boundary.
    if len(caption) > 165:
        cut = caption[:162].rfind(' ')
        caption = (caption[:cut] if cut > 100 else caption[:162]).rstrip(' ,.;:') + '...'

    # Greedy word wrap to MAX_CHARS_PER_LINE
    words = caption.split()
    lines: List[str] = []
    current: List[str] = []
    current_len = 0
    for word in words:
        added = len(word) + (1 if current else 0)
        if current and current_len + added > _CAPTION_MAX_CHARS_PER_LINE:
            lines.append(' '.join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += added
    if current:
        lines.append(' '.join(current))

    # Cap at 3 lines — merge overflow into the third with ellipsis
    if len(lines) > 3:
        merged_tail = ' '.join(lines[2:])
        if len(merged_tail) > _CAPTION_MAX_CHARS_PER_LINE:
            cut = merged_tail[:_CAPTION_MAX_CHARS_PER_LINE - 3].rfind(' ')
            tail_cut = merged_tail[:cut] if cut > 30 else merged_tail[:_CAPTION_MAX_CHARS_PER_LINE - 3]
            merged_tail = tail_cut.rstrip(' ,.;:') + '...'
        lines = lines[:2] + [merged_tail]

    # Absorb a single-word orphan last line into the previous line if it still
    # fits the per-line width (avoids an ugly lone word on its own line).
    if len(lines) >= 2 and len(lines[-1].split()) == 1:
        merged = lines[-2] + ' ' + lines[-1]
        if len(merged) <= _CAPTION_MAX_CHARS_PER_LINE:
            lines = lines[:-2] + [merged]

    n_lines = len(lines)
    # Sizes are expressed at the 1080p baseline; config.SCALE multiplies them
    # so captions stay visually proportional on 1440p/4K canvases. CAPTION_FONT_SCALE
    # is the Phase B 65+ legibility knob (1.0 = current); it scales font, box, and
    # offsets together so the layout stays coherent.
    s = config.SCALE * getattr(config, 'CAPTION_FONT_SCALE', 1.0)
    sz = lambda n: int(n * s)
    # Enlarged for the prestige look (succinct captions are short, so they fit big).
    if n_lines == 1:
        font_size, box_h, text_y_off, line_sp = sz(62), sz(118), sz(86), 0
    elif n_lines == 2:
        font_size, box_h, text_y_off, line_sp = sz(54), sz(158), sz(144), sz(12)
    else:  # 3 lines
        font_size, box_h, text_y_off, line_sp = sz(46), sz(196), sz(188), sz(8)
    text_y = f'h-{text_y_off}'

    return {
        'text': '\n'.join(lines),
        'font_size': font_size,
        'box_height': box_h,
        'text_y': text_y,
        'line_spacing': line_sp,
    }


def _build_caption_filter(wrap_info: Dict, caption_file_path: str) -> str:
    """
    Build the drawtext filter for a slideshow caption.

    Writes the wrapped caption to a UTF-8 sidecar file and references it via
    textfile=, which sidesteps drawtext's inline-escape rules for special
    characters. Three of every 45 clips were silently dropped under the old
    text= path because of unescaped specials in Wikimedia captions.

    NOTE: file is written with LF-only line endings (newline=''); the default
    Windows text-mode CRLF translation made FFmpeg's drawtext render the CR
    as visual whitespace, doubling effective line spacing and pushing the
    third caption line off the bottom of the 1080px frame.
    """
    with open(caption_file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(wrap_info['text'])

    font_path = _ffmpeg_escape_path(config.CAPTION_FONT_FILE)
    text_path = _ffmpeg_escape_path(caption_file_path)

    # Prestige caption look: pristine WHITE text with a bold BLACK OUTLINE
    # (borderw) + a soft drop shadow for separation. The outline thickness scales
    # with the font so it reads as a clean edge, not a thin grey halo. The dark
    # bar is OFF by default (CAPTION_BAR) — the outline carries contrast on its own.
    fs = wrap_info['font_size']
    outline = max(3, int(fs * getattr(config, 'CAPTION_OUTLINE_RATIO', 0.085)))
    shadow = max(2, outline // 2)

    layers = []
    if getattr(config, 'CAPTION_BAR', False):
        bo = getattr(config, 'CAPTION_BOX_OPACITY', 0.55)
        layers.append(
            f"drawbox=x=0:y=ih-{wrap_info['box_height']}:w=iw:h={wrap_info['box_height']}:color=black@{bo}:t=fill"
        )
    layers.append(
        f"drawtext=textfile='{text_path}':"
        f"fontfile='{font_path}':"
        f"fontsize={fs}:fontcolor=white:"
        f"borderw={outline}:bordercolor=black:"
        f"shadowx={shadow}:shadowy={shadow}:shadowcolor=black@0.5:"
        f"x=(w-text_w)/2:y={wrap_info['text_y']}:"
        f"line_spacing={wrap_info['line_spacing']}"
    )
    return "," + ",".join(layers)


def generate_ken_burns_filter(index: int, duration: float) -> str:
    """
    Generate FFmpeg filter for static image display.

    UPDATED: Removed zoom/pan effects as they caused shaky video
    and reduced viewer retention (3 min -> 1.21 min average view time).
    Static images perform better for the 65+ audience.
    """
    frames = int(duration * config.FPS)

    # Static display - no zoom, no pan, just centered image
    # zoompan with z=1 (no zoom) and centered x,y
    filter_str = (
        f"zoompan=z=1:"
        f"x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={config.WIDTH}x{config.HEIGHT}:fps={config.FPS}"
    )

    return filter_str


def _build_xfade_filter(clip_durations: List[float], xfade_dur: float = 0.5) -> Tuple[str, str]:
    """
    Build a chained `xfade` filter_complex string for smooth crossfade
    transitions between clips. Each transition overlaps the previous clip's
    final `xfade_dur` seconds with the next clip's first `xfade_dur` seconds.

    Returns (filter_complex_string, final_video_label). For a single clip
    the filter is empty and the label is "0:v".
    """
    if len(clip_durations) < 2:
        return "", "0:v"

    parts = []
    prev_label = "0:v"
    cumulative = clip_durations[0]
    for i in range(1, len(clip_durations)):
        offset = max(0.0, cumulative - xfade_dur)
        new_label = f"v{i}"
        parts.append(
            f"[{prev_label}][{i}:v]xfade=transition=fade:duration={xfade_dur}:offset={offset}[{new_label}]"
        )
        prev_label = new_label
        cumulative = cumulative + clip_durations[i] - xfade_dur

    return ";".join(parts), prev_label


def get_intro_voice() -> Optional[str]:
    """Pick a random pre-recorded intro voice file from assets/intro_voice/."""
    intro_dir = os.path.join(config.ASSETS_FOLDER, "intro_voice")
    if not os.path.exists(intro_dir):
        return None
    voices = [
        os.path.join(intro_dir, f)
        for f in os.listdir(intro_dir)
        if f.lower().endswith(('.wav', '.mp3'))
    ]
    return random.choice(voices) if voices else None


def generate_personalized_voiceover(images: List[Dict], theme: str) -> Optional[str]:
    """
    Generate a personalized voiceover intro using Gemini + edge-tts.
    Falls back to pre-recorded intro voice if generation fails.
    """
    try:
        from voiceover_generator import generate_voiceover

        metadata = {
            'theme': theme,
            'image_count': len(images),
            'images': images,
        }

        voice_path = generate_voiceover(metadata, output_dir=config.TEMP_FOLDER)
        if voice_path:
            print(f"  Personalized voiceover generated: {voice_path}")
            return voice_path

    except ImportError:
        print("  voiceover_generator not available, using pre-recorded intro")
    except Exception as e:
        print(f"  Personalized voiceover failed ({e}), falling back to pre-recorded")

    # Fallback to pre-recorded
    return get_intro_voice()


def create_video(images: List[Dict], output_path: str, theme: str = "Classic_Hollywood",
                 target_count: Optional[int] = None):
    """
    Create the full slideshow video with all effects.

    Args:
        images: List of image dicts with 'image_url', 'generated_caption', etc.
            (may be OVER-SELECTED — more rows than the video needs, so quality
            rejects don't shrink the video)
        output_path: Path for output MP4 file
        theme: Theme name for the video
        target_count: stop downloading once this many images pass the quality
            gate (None = use every row)
    """
    temp_dir = tempfile.mkdtemp(prefix="aap_video_")

    try:
        print(f"\n=== Creating Video: {theme} ===")
        print(f"Temp directory: {temp_dir}")

        # Generate personalized voiceover (falls back to pre-recorded)
        intro_voice = generate_personalized_voiceover(images, theme)
        intro_duration = 0
        if intro_voice:
            intro_duration = get_audio_duration(intro_voice)
            print(f"Intro voice: {os.path.basename(intro_voice)} ({intro_duration:.1f}s)")

        # Calculate durations.
        # Variable pacing: first 3 images play for 10s instead of the full 15s
        # to create early momentum and hook viewers past the 1-minute drop-off.
        # Final values are recomputed from actual clip outputs after generation
        # (factoring xfade overlap and any clips that fail to render).
        logo_duration = config.LOGO_DURATION
        image_duration = config.IMAGE_DURATION
        XFADE_DUR = getattr(config, 'XFADE_DUR', 0.5)
        FAST_OPENING_CLIPS = getattr(config, 'FAST_OPENING_CLIPS', 3)
        FAST_OPENING_DURATION = getattr(config, 'FAST_OPENING_DURATION', 10)

        def planned_image_duration(idx: int) -> int:
            return FAST_OPENING_DURATION if idx < FAST_OPENING_CLIPS else image_duration

        planned_count = min(target_count or len(images), len(images))
        planned_total = logo_duration + sum(planned_image_duration(i) for i in range(planned_count))
        print(f"Video will be ~{planned_total} seconds ({planned_total/60:.1f} minutes)")

        # Step 1: Download and resize all images
        print("\n[1/5] Downloading and resizing images...")
        image_paths = []

        if BROWSER_DOWNLOAD_AVAILABLE:
            # Use browser-based downloading (no rate limits!)
            print("  Using headless browser (bypasses rate limits)...")
            image_paths = asyncio.run(download_with_browser(images, temp_dir, target_count))
        else:
            # Fallback to requests-based downloading (may hit rate limits)
            print("  Using requests (may hit rate limits)...")
            for i, img in enumerate(images):
                if target_count and len(image_paths) >= target_count:
                    print(f"  Target of {target_count} quality images reached "
                          f"({i} of {len(images)} rows attempted)")
                    break

                url = img.get('image_url')
                if not url:
                    print(f"  [{i+1}/{len(images)}] Skipping - no URL")
                    continue

                print(f"  [{i+1}/{len(images)}] Downloading...")

                # Download
                ext = os.path.splitext(url.split('?')[0])[-1] or '.jpg'
                download_path = os.path.join(temp_dir, f"orig_{i:03d}{ext}")

                if not download_image(url, download_path):
                    time.sleep(5)  # Wait even after failures
                    continue

                # Rate limiting delay to avoid Wikimedia 429 errors
                time.sleep(5)

                ok, reason = check_image_quality(download_path)
                if not ok:
                    img['quality_rejected'] = True
                    print(f"    Quality reject: {reason}")
                    continue

                # Resize
                resized_path = os.path.join(temp_dir, f"img_{i:03d}.jpg")
                if resize_image_for_video(download_path, resized_path):
                    img['downloaded'] = True
                    image_paths.append({
                        'path': resized_path,
                        'orig': download_path,  # original photo (thumbnail source)
                        'caption': img.get('generated_caption', ''),
                        'filename': img.get('image_filename', ''),
                        'category': img.get('source_category', ''),
                        'index': i,
                        'portrait': _is_portrait(download_path),
                    })

        if not image_paths:
            raise ValueError("No images were successfully processed!")

        print(f"  Processed {len(image_paths)} images")

        # --- RETENTION HOOK: promote the strongest image to position 0 ---
        # The opening 5–15 seconds is where viewers decide to keep watching.
        # Move the photo whose caption mentions a recognized celebrity (from
        # the curated KNOWN_STARS set) to the front so the video opens with
        # a familiar face rather than a random photo.
        if len(image_paths) > 1:
            try:
                from youtube_uploader import KNOWN_STARS

                def _hook_score(clip: Dict) -> int:
                    cap = (clip.get('caption') or '').lower()
                    star_hit = any(star in cap for star in KNOWN_STARS)
                    return (100 if star_hit else 0) + min(len(cap), 50)

                best_idx = max(range(len(image_paths)), key=lambda i: _hook_score(image_paths[i]))
                if best_idx != 0:
                    image_paths.insert(0, image_paths.pop(best_idx))
                    print(f"  Promoted image {best_idx} to opening slot for retention hook")
            except Exception as e:
                print(f"  Could not score clips for hook ({e}), keeping original order")

        # Persist thumbnail candidates (real compilation images) before temp
        # cleanup — the thumbnail is built from these (split-screen diptych),
        # so it always reflects the actual video. Candidates are chosen
        # FACE-FIRST: portrait-aspect originals (≈ a person, not a car/scenery
        # still) with a recognized star caption ranked highest — the crispness
        # ranking in _pick_split_pair then chooses among faces, never instead
        # of them. 8 candidates give the pair picker real choice.
        try:
            from youtube_uploader import KNOWN_STARS as _KS, LEADING_LADIES as _LL
        except Exception:
            _KS, _LL = [], set()

        # Filenames that signal an ENVIRONMENTAL shot (a place/object, not a
        # face) — a producer's office, a house, a car, a street. These slip past
        # the portrait-aspect check (a tall library photo is "portrait") and once
        # landed on a thumbnail, so demote them out of candidacy.
        _ENV_TERMS = ('house', 'office', 'library', 'works', 'building', 'street',
                      'exterior', 'interior', 'room', 'car', 'automobile', 'ferrari',
                      'aircraft', 'airplane', 'yacht', 'boat', 'mansion', 'estate',
                      'studio lot', 'set ', 'on set', 'premiere', 'funeral', 'grave')
        # Pinup-era FIGURE shots — the verified CTR drivers on both reference
        # channels (full-frame swimsuit/gown glamour, face + figure visible).
        # Owner decision 2026-07: lead thumbnails with these when the video has
        # them ("authentic pinup era", not boudoir).
        _PINUP_TERMS = ('pin-up', 'pinup', 'swimsuit', 'bathing suit', 'bathing beauty',
                        'swimwear', 'beach', 'pool', 'leggy', 'legs', 'dancer',
                        'showgirl', 'chorus', 'gown', 'evening dress', 'stocking',
                        'fishnet', 'shorts', 'cheesecake', 'glamour')

        # Frames that must NEVER be the thumbnail: movie title cards and trailer
        # screenshots (a "The Palm Beach Story" title card actually shipped as a
        # thumbnail), and multi-person/scene shots. The bulk goldmine2 pool holds
        # ~123 trailer/screenshot rows, which is where these come from.
        _NOTHUMB_TERMS = ('trailer', 'screenshot', 'screen capture', 'title card',
                          'credits', 'opening', 'poster', 'lobby', 'magazine',
                          'cover', 'still from', 'scene from', 'group', 'cast',
                          'premiere', 'award', 'ceremony', 'crowd', 'party')
        # Couple/group detection. Counting capitalised words was far too blunt
        # ("Betty Grable Studio portrait" read as 3 names); instead count how
        # many DISTINCT known stars are named, and catch explicit joiners.
        _SURNAMES = {s.split()[-1] for s in _KS}
        _JOINER = re.compile(r'\b(and|with|&)\b', re.I)
        # "Firstname Lastname" pairs — two of them means two people are named,
        # which catches couples where the man isn't a KNOWN_STAR
        # (e.g. "Ray Anthony Marilyn Monroe 1952").
        _NAME_PAIR = re.compile(r'\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b')

        def _is_solo(blob: str, fn: str) -> bool:
            named = {s for s in _KS if s in blob}
            if len(named) >= 2:
                return False
            surnames = {w for w in _SURNAMES if re.search(rf'\b{re.escape(w)}\b', blob)}
            if len(surnames) >= 2:
                return False
            if len(_NAME_PAIR.findall(fn)) >= 2:
                return False
            # "<Name> and <Name>" / "X with Y" style filenames
            return not _JOINER.search(fn)

        def _cand_rank(clip: Dict):
            cap = (clip.get('caption') or '').lower()
            fn = (clip.get('filename') or '')
            fnl = fn.lower()
            blob = fnl + ' ' + cap
            # HARD gates first — these dominate the ordering.
            lady = any(s in blob for s in _LL)          # a leading lady, by name
            clean = not any(t in blob for t in _NOTHUMB_TERMS)   # not a card/scene
            solo = _is_solo(blob, fn)                   # not a couple/group shot
            not_env = not any(t in blob for t in _ENV_TERMS)
            pinup = any(t in blob for t in _PINUP_TERMS)
            star = any(s in cap for s in _KS)
            return (lady and clean and solo, clean, not_env, solo,
                    pinup, clip.get('portrait', False), star)

        candidates = sorted(image_paths, key=_cand_rank, reverse=True)[:8]
        _lead = candidates[0] if candidates else None
        if _lead is not None:
            _ok = _cand_rank(_lead)[0]
            print(f"  Thumbnail lead candidate: {(_lead.get('filename') or '?')[:60]} "
                  f"({'leading-lady match' if _ok else 'NO leading-lady match — fallback'})")
        for idx, clip in enumerate(candidates):
            dst = os.path.join(config.OUTPUT_FOLDER, f"{theme}_thumb_{idx}.jpg")
            dst_orig = os.path.join(config.OUTPUT_FOLDER, f"{theme}_thumborig_{idx}.jpg")
            try:
                shutil.copy(clip['path'], dst)
                # Persist the ORIGINAL photo too — the full-frame thumbnail is
                # rendered from it (the canvas is pillarboxed; subject too small).
                has_orig = False
                if clip.get('orig') and os.path.exists(clip['orig']):
                    shutil.copy(clip['orig'], dst_orig)
                    has_orig = True
                # Map to the ORIGINAL images entry (image_paths is reordered by the
                # hook + sparse from skipped downloads), so local_path stays attached
                # to the metadata entry whose caption matches the frame.
                orig_i = clip.get('index', idx)
                if orig_i < len(images):
                    images[orig_i]['local_path'] = dst
                    if has_orig:
                        images[orig_i]['local_orig'] = dst_orig
                    # Carry the ranking through to the renderer. Without this the
                    # thumbnail generator re-reads images in METADATA order and
                    # picks purely on _frame_score, silently discarding the
                    # leading-lady / no-title-card / solo gating done here.
                    images[orig_i]['thumb_rank'] = idx
                    images[orig_i]['thumb_eligible'] = bool(_cand_rank(clip)[0])
            except Exception as e:
                print(f"  Thumbnail candidate {idx} copy failed: {e}")

        # Step 2: Prepare intro video
        print("\n[2/5] Preparing intro video...")

        # Step 3: Create individual image clips with Ken Burns effect
        print("\n[3/5] Creating image clips with Ken Burns effect...")
        clip_paths: List[str] = []
        clip_durations: List[float] = []  # parallel to clip_paths; powers xfade chain + audio length
        clip_meta: List[Dict] = []        # caption/filename per IMAGE clip (for description chapters)

        # Intro video clip — use the branded intro.mp4, scaled to match output
        intro_clip = os.path.join(temp_dir, "clip_intro.mp4")
        if os.path.exists(config.INTRO_VIDEO_PATH):
            # Scale intro video to exact output resolution, re-encode to match stream params.
            # INTRO_DURATION_OVERRIDE (if set) trims the branded intro so a photo lands sooner.
            intro_override = getattr(config, 'INTRO_DURATION_OVERRIDE', None)
            cmd = [config.FFMPEG_PATH, '-y', '-i', config.INTRO_VIDEO_PATH]
            if intro_override:
                cmd += ['-t', str(intro_override)]
            cmd += [
                '-vf', f"scale={config.WIDTH}:{config.HEIGHT}:force_original_aspect_ratio=decrease,"
                       f"pad={config.WIDTH}:{config.HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps={config.FPS}",
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
                '-pix_fmt', 'yuv420p',
                '-an',  # Strip audio — background music is added later
                intro_clip
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            actual_intro_dur = get_audio_duration(intro_clip) or float(logo_duration)
            clip_paths.append(intro_clip)
            clip_durations.append(actual_intro_dur)
            print(f"  Intro video ready ({actual_intro_dur:.1f}s)")
        else:
            # Fallback: static logo image if intro.mp4 is missing
            print("  Warning: intro.mp4 not found, falling back to static logo")
            logo_resized = os.path.join(temp_dir, "logo.jpg")
            if os.path.exists(config.LOGO_PATH):
                resize_image_for_video(config.LOGO_PATH, logo_resized)
            else:
                black = Image.new('RGB', (config.WIDTH, config.HEIGHT), 'black')
                black.save(logo_resized, 'JPEG')
            cmd = [
                config.FFMPEG_PATH, '-y',
                '-loop', '1',
                '-i', logo_resized,
                '-t', str(logo_duration),
                '-vf', f"scale={config.WIDTH}:{config.HEIGHT},fps={config.FPS}",
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
                '-pix_fmt', 'yuv420p',
                intro_clip
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            clip_paths.append(intro_clip)
            clip_durations.append(float(logo_duration))

        # Image clips with Ken Burns and text overlay
        for i, img_info in enumerate(image_paths):
            this_duration = planned_image_duration(i)
            print(f"  [{i+1}/{len(image_paths)}] Processing clip ({this_duration}s)...")

            clip_path = os.path.join(temp_dir, f"clip_{i:03d}.mp4")

            # Build filter for Ken Burns + text overlay
            kb_filter = generate_ken_burns_filter(i, this_duration)

            # Text overlay — wrap caption to fit the 1920px frame, then write
            # to a sidecar file referenced via textfile= (avoids drawtext's
            # brittle inline escape rules for special characters).
            wrap_info = _wrap_caption(
                img_info['caption'] or '',
                filename=img_info.get('filename', ''),
            )
            if wrap_info:
                caption_file_path = os.path.join(temp_dir, f"caption_{i:03d}.txt")
                text_filter = _build_caption_filter(wrap_info, caption_file_path)
            else:
                text_filter = ""

            full_filter = kb_filter + text_filter

            cmd = [
                config.FFMPEG_PATH, '-y',
                '-loop', '1',
                '-i', img_info['path'],
                '-t', str(this_duration),
                '-vf', full_filter,
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
                '-pix_fmt', 'yuv420p',
                clip_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                # Show the last 600 chars of stderr — that's where the actual error message lives
                err_tail = (result.stderr or '')[-600:]
                print(f"    Warning: FFmpeg error on clip with text overlay: ...{err_tail}")

                # Retry without the text overlay so the image still appears.
                # Better to lose the caption than silently drop the photo.
                fallback_cmd = [
                    config.FFMPEG_PATH, '-y',
                    '-loop', '1',
                    '-i', img_info['path'],
                    '-t', str(this_duration),
                    '-vf', kb_filter,
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
                    '-pix_fmt', 'yuv420p',
                    clip_path
                ]
                fallback_result = subprocess.run(fallback_cmd, capture_output=True, text=True)
                if fallback_result.returncode != 0:
                    print(f"    Failed even without overlay, dropping clip: ...{(fallback_result.stderr or '')[-300:]}")
                    continue
                print(f"    Recovered without text overlay")

            clip_paths.append(clip_path)
            clip_durations.append(float(this_duration))
            clip_meta.append({
                'caption': img_info.get('caption', ''),
                'filename': img_info.get('filename', ''),
            })

        # Step 4: Stitch clips with crossfade transitions
        # Crossfading replaces the previous abrupt-cut concat. Each transition
        # overlaps XFADE_DUR seconds of the outgoing clip with the incoming
        # one, producing a more cinematic feel that proven retention-optimized
        # vintage channels use. Tradeoff: requires re-encoding the full timeline
        # (vs. -c copy concat), so this step is the expensive one in the cron.
        print(f"\n[4/5] Stitching {len(clip_paths)} clips with crossfade transitions...")

        video_only = os.path.join(temp_dir, "video_only.mp4")

        used_xfade = False  # tracks whether clips actually overlap (for accurate timing)
        if len(clip_paths) == 1:
            # Single clip — no transitions needed, just remux
            cmd = [
                config.FFMPEG_PATH, '-y',
                '-i', clip_paths[0],
                '-c', 'copy',
                video_only
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        else:
            filter_complex, final_label = _build_xfade_filter(clip_durations, xfade_dur=XFADE_DUR)

            cmd = [config.FFMPEG_PATH, '-y']
            for clip in clip_paths:
                cmd.extend(['-i', clip])
            cmd.extend([
                '-filter_complex', filter_complex,
                '-map', f'[{final_label}]',
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21',
                '-pix_fmt', 'yuv420p',
                video_only
            ])
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                # Fall back to plain concat if xfade chain fails (e.g. arg-list overflow)
                print(f"  xfade stitch failed, falling back to abrupt-cut concat: ...{(result.stderr or '')[-300:]}")
                concat_file = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_file, 'w', encoding='utf-8') as f:
                    for clip in clip_paths:
                        f.write(f"file '{clip}'\n")
                subprocess.run([
                    config.FFMPEG_PATH, '-y',
                    '-f', 'concat', '-safe', '0',
                    '-i', concat_file,
                    '-c', 'copy',
                    video_only
                ], capture_output=True, check=True)
            else:
                used_xfade = True  # clips overlap by XFADE_DUR each

        # Recompute total_duration from actual generated clips so the audio mix
        # matches the stitched video length. Only subtract xfade overlap when
        # the xfade stitch actually succeeded (the concat fallback has no overlap).
        n_xfades = max(0, len(clip_paths) - 1) if used_xfade else 0
        total_duration = sum(clip_durations) - n_xfades * XFADE_DUR
        print(f"  Final stitched video: {total_duration:.1f}s ({total_duration/60:.1f} min)")

        # Step 5: Add audio
        print("\n[5/5] Adding background music...")

        # Create concatenated audio that covers video duration
        audio_concat_file = create_audio_concat_file(total_duration, temp_dir)

        combined_audio = os.path.join(temp_dir, "audio_combined.mp3")
        fade_in = getattr(config, 'AUDIO_FADE_IN', 0.0)
        af = (f'afade=t=out:st={total_duration - config.AUDIO_FADE_OUT}:d={config.AUDIO_FADE_OUT},'
              f'volume={config.MUSIC_VOLUME}')
        if fade_in and fade_in > 0:
            af = f'afade=t=in:st=0:d={fade_in},' + af
        cmd = [
            config.FFMPEG_PATH, '-y',
            '-f', 'concat', '-safe', '0',
            '-i', audio_concat_file,
            '-t', str(total_duration),
            '-af', af,
            '-c:a', 'libmp3lame', '-q:a', '2',
            combined_audio
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # Mix intro voice over background music (if available)
        if intro_voice and intro_duration > 0:
            print(f"  Mixing intro voice over background music...")
            final_audio = os.path.join(temp_dir, "final_audio.mp3")
            # Duck music to 40% during voice, restore after voice ends
            # Voice fades in over 0.3s; music cross-fades back up over 2s
            fade_back = intro_duration - 1  # music starts rising 1s before voice ends
            cmd = [
                config.FFMPEG_PATH, '-y',
                '-i', intro_voice,
                '-i', combined_audio,
                '-filter_complex',
                f"[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
                f"afade=t=in:st=0:d=0.3,afade=t=out:st={intro_duration - 0.5}:d=0.5[voice];"
                f"[1:a]volume='if(lt(t,{fade_back}),0.4,1)':eval=frame[music];"
                f"[voice][music]amix=inputs=2:duration=longest:dropout_transition=2[out]",
                '-map', '[out]',
                '-c:a', 'libmp3lame', '-q:a', '2',
                final_audio
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                audio_to_mux = final_audio
                print(f"  Intro voice mixed successfully")
            else:
                print(f"  Warning: Intro voice mixing failed, using music only")
                print(f"  FFmpeg error: {result.stderr[:200]}")
                audio_to_mux = combined_audio
        else:
            audio_to_mux = combined_audio

        # Combine video and audio
        cmd = [
            config.FFMPEG_PATH, '-y',
            '-i', video_only,
            '-i', audio_to_mux,
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # Build the real per-image timeline (for accurate description chapters).
        # clip index 0 is the intro; image clip j maps to clip_meta[j-1].
        # Only subtract the crossfade overlap if the xfade stitch actually ran.
        gap = XFADE_DUR if used_xfade else 0.0
        starts = [0.0]
        for k in range(1, len(clip_durations)):
            starts.append(starts[-1] + clip_durations[k - 1] - gap)
        timeline: List[Dict] = []
        for j, meta in enumerate(clip_meta):
            clip_index = j + 1  # offset by the intro at index 0
            if clip_index < len(starts):
                timeline.append({
                    'start': round(max(0.0, starts[clip_index]), 1),
                    'caption': meta.get('caption', ''),
                    'filename': meta.get('filename', ''),
                })

        print(f"\n=== Video created successfully! ===")
        print(f"Output: {output_path}")
        print(f"Duration: {total_duration} seconds ({total_duration/60:.1f} minutes)")

        return output_path, total_duration, timeline

    finally:
        # Clean up temp directory
        print(f"\nCleaning up temp files...")
        shutil.rmtree(temp_dir, ignore_errors=True)


def generate_video(image_count: int = config.IMAGES_PER_VIDEO, theme: str = None) -> Optional[str]:
    """
    Main function to generate a complete video.

    Args:
        image_count: Number of images to use
        theme: Optional theme name

    Returns:
        Path to generated video file, or None if failed
    """
    print("=" * 60)
    print("AAP Video Generator")
    print("=" * 60)

    # Generate theme from date if not provided
    if not theme:
        theme = datetime.now().strftime("Classic_Hollywood_%Y%m%d")

    # Step 1: Select images — over-select by SELECT_BUFFER so post-download
    # quality rejects (low-res/extreme-aspect scans) still fill the video.
    print("\n[Step 1] Selecting images...")
    buffer = getattr(config, 'SELECT_BUFFER', 1.3)
    images = select_unused_images(int(image_count * buffer))

    if len(images) < 1:
        print("Error: No images available!")
        return None

    if len(images) < image_count:
        print(f"Warning: Only {len(images)} images available (requested {image_count})")

    # Step 2: Scrape descriptions
    print("\n[Step 2] Scraping descriptions from Wikimedia...")
    images = scrape_batch(images)

    # Step 3: Create video
    output_filename = f"AAP_{datetime.now().strftime('%Y-%m-%d')}_{theme}.mp4"
    output_path = os.path.join(config.OUTPUT_FOLDER, output_filename)

    print(f"\n[Step 3] Creating video...")
    result = create_video(images, output_path, theme, target_count=image_count)

    if result:
        video_path, actual_duration, timeline = result

        # Step 4: Mark used ONLY what was consumed: rows whose image is in the
        # video ('downloaded') plus quality-rejected junk (blacklisted so it
        # never gets re-picked). Untouched over-selection rows and transient
        # download failures stay fresh in the pool.
        print("\n[Step 4] Updating CSV...")
        consumed = [img for img in images
                    if img.get('downloaded') or img.get('quality_rejected')]
        n_rej = sum(1 for img in images if img.get('quality_rejected'))
        print(f"  Consumed {len(consumed)} rows "
              f"({len(consumed) - n_rej} in video, {n_rej} quality-rejected)")
        mark_images_used(consumed)

        # Save metadata for upload. Only rows whose image is actually IN the
        # video — titles/tags/chapters/decade labels must describe the real
        # content ("100 Photos" has to mean 100), not the over-selected pool.
        video_images = [img for img in images if img.get('downloaded')] or images
        # The star this episode is about (empty on mixed days). Titles, tags and
        # the thumbnail all key off this.
        focus_star = next((i.get('focus_star') for i in video_images
                           if i.get('focus_star')), '')
        if focus_star:
            record_focus_star(focus_star)
        metadata_path = os.path.join(config.OUTPUT_FOLDER, output_filename.replace('.mp4', '_metadata.json'))
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump({
                'video_file': output_path,
                'theme': theme,
                'focus_star': focus_star,
                'image_count': len(video_images),
                'duration_seconds': actual_duration,
                'timeline': timeline,   # real per-image start times → accurate chapters
                'images': video_images,
                'created': datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)

        # Step 5: Generate thumbnail and title
        print("\n[Step 5] Generating thumbnail and title...")
        try:
            from generate_thumbnail import generate_thumbnail_and_title
            youtube_assets = generate_thumbnail_and_title(metadata_path)
            print(f"  Title: {youtube_assets.get('title', '').encode('ascii', 'replace').decode()}")
            print(f"  Thumbnail: {youtube_assets.get('thumbnail_path')}")
        except Exception as e:
            print(f"  Warning: Could not generate thumbnail/title: {e}")

        return output_path

    return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='AAP Video Generator')
    parser.add_argument('--count', type=int, default=config.IMAGES_PER_VIDEO,
                        help=f'Number of images (default: {config.IMAGES_PER_VIDEO})')
    parser.add_argument('--theme', type=str, default=None,
                        help='Theme name for the video')
    parser.add_argument('--test', action='store_true',
                        help='Test mode: use only 5 images')

    args = parser.parse_args()

    count = 5 if args.test else args.count

    result = generate_video(image_count=count, theme=args.theme)

    if result:
        print(f"\nSuccess! Video saved to: {result}")
    else:
        print("\nFailed to generate video.")
        sys.exit(1)
