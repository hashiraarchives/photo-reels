"""
AAP - Actress Actor and Pinups
Thumbnail & Title Generator  (Phase A CTR redesign)

New thumbnail style, modeled on the successful same-niche channels
(@yapaknews / @OldWorldPhotos): the beautiful image sells the click.
- ONE dominant, gorgeous face filling the frame (bigger crop)
- Warm vintage color grading (greyscale sources get a warm sepia colorize)
- NO red arrow and NO on-thumbnail text by default (both behind config flags)
- A thin warm-gold border + a small corner monogram as a consistent brand signature
- Sourced from a large, rotated pool (recently-used ledger) so the channel grid stays fresh

Every behavioral change is a config kill-switch (config.THUMB_*), so the old
look can be recovered without a code change.
"""

import os
import json
import random
import re
import math
from typing import List, Dict, Optional, Tuple
from PIL import (Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance,
                 ImageOps, ImageStat, ImageChops)
import config


# Path to curated portrait images for thumbnails
THUMBNAIL_BASES_DIR = os.path.join(config.ASSETS_FOLDER, "thumbnail_bases")
_GOLD = (212, 175, 55)


def extract_names_from_metadata(metadata: Dict) -> List[str]:
    """Extract celebrity names from video metadata (KNOWN_STARS weighted 10x)."""
    from youtube_uploader import KNOWN_STARS, _looks_like_movie_title

    name_counts: Dict[str, int] = {}
    for img in metadata.get('images', []):
        title = img.get('title', '') or ''
        caption = img.get('generated_caption', '') or ''
        for text in [title, caption]:
            text_lower = text.lower()
            for star in KNOWN_STARS:
                if star in text_lower:
                    proper_name = ' '.join(w.capitalize() for w in star.split())
                    name_counts[proper_name] = name_counts.get(proper_name, 0) + 10
            for match in re.findall(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b', text):
                if _looks_like_movie_title(match):
                    continue
                if any(w in match.lower() for w in ['film', 'movie', 'picture', 'photo', 'magazine']):
                    continue
                name_counts[match] = name_counts.get(match, 0) + 1

    return [name for name, _ in sorted(name_counts.items(), key=lambda x: x[1], reverse=True)[:5]]


def generate_title(metadata: Dict) -> str:
    """Fallback title (Gemini-unavailable path) — delegates to the shared builder."""
    from youtube_uploader import build_fallback_title
    return build_fallback_title(metadata)


# ---------------------------------------------------------------------------
# Thumbnail subject sourcing: large rotated pool + recently-used ledger
# ---------------------------------------------------------------------------
def _candidate_portraits() -> List[str]:
    """
    Curated portrait pool = the hand-picked thumbnail_bases PLUS the per-actress
    asset folders (assets/<Name>/photo_*.jpg). Far larger and more varied than
    the original 25 fixed portraits, so the channel grid looks fresh.
    """
    cands: List[str] = []
    if os.path.isdir(THUMBNAIL_BASES_DIR):
        for f in os.listdir(THUMBNAIL_BASES_DIR):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                cands.append(os.path.join(THUMBNAIL_BASES_DIR, f))
    assets = config.ASSETS_FOLDER
    if os.path.isdir(assets):
        for name in os.listdir(assets):
            sub = os.path.join(assets, name)
            if os.path.isdir(sub) and name not in ('thumbnail_bases', 'intro_voice'):
                for f in os.listdir(sub):
                    if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                        cands.append(os.path.join(sub, f))
    return cands


def _load_recent() -> List[str]:
    try:
        with open(config.THUMB_RECENT_LEDGER, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _record_recent(base_path: str):
    """Append a used base to the recently-used ledger (best-effort)."""
    try:
        ledger = _load_recent()
        ledger.append(os.path.basename(base_path))
        os.makedirs(os.path.dirname(config.THUMB_RECENT_LEDGER), exist_ok=True)
        with open(config.THUMB_RECENT_LEDGER, 'w', encoding='utf-8') as f:
            json.dump(ledger[-200:], f)
    except Exception as e:
        print(f"  Could not update thumbnail ledger: {e}")


def _pick_fresh(cands: List[str]) -> Optional[str]:
    """Choose from candidates, avoiding the last THUMB_RECENT_AVOID used ones."""
    if not cands:
        return None
    avoid_n = getattr(config, 'THUMB_RECENT_AVOID', 20)
    avoid = set(_load_recent()[-avoid_n:])
    fresh = [c for c in cands if os.path.basename(c) not in avoid]
    return random.choice(fresh or cands)


def get_curated_portrait() -> Optional[str]:
    """Pick any curated portrait (used for mixed/generic videos) — max variety."""
    return _pick_fresh(_candidate_portraits())


def get_portrait_for_star(name: str) -> Optional[str]:
    """
    Pick a curated portrait that actually depicts `name`, so the thumbnail face
    matches a star named in the title (avoids click-and-quit). Returns None if we
    have no curated image of that star (caller then falls back to the pool).
    """
    if not name:
        return None
    key = name.lower().replace(' ', '_')
    key2 = name.lower().replace(' ', '')
    matches = [
        c for c in _candidate_portraits()
        if key in c.lower().replace(' ', '_') or key2 in os.path.basename(c).lower().replace('_', '')
    ]
    return _pick_fresh(matches)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for font_path in ["arialbd.ttf", "impact.ttf", "arial.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(font_path, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def _is_low_saturation(img: Image.Image) -> bool:
    """True for near-greyscale source photos."""
    s = img.convert('HSV').split()[1]
    px = img.size[0] * img.size[1] or 1
    return (sum(s.histogram()[:40]) / px) > 0.85


def _is_toned_monochrome(img: Image.Image) -> bool:
    """
    True for a SEPIA / albumen / age-toned scan: monochrome carrying a single
    tint rather than real colour photography.

    Saturation alone cannot tell these apart — an aged sepia print is highly
    "saturated" while containing no colour information at all, so a pure
    saturation test lets exactly the muddy-yellow images we are trying to
    eliminate through as "real colour". Real colour photography spreads across
    many hues (skin, sky, fabric, backdrop); a toned print concentrates in one
    narrow hue band.
    """
    try:
        h, s, _ = img.convert('HSV').split()
        hist = h.histogram()
        # Only consider pixels that carry some colour at all.
        total = sum(hist) or 1
        # Hue is 0-255 in Pillow. Find the widest contiguous band holding 80%.
        peak = max(range(256), key=lambda i: hist[i])
        acc = hist[peak]
        lo = hi = peak
        while acc < 0.80 * total and (hi - lo) < 255:
            nxt_hi = hist[(hi + 1) % 256]
            nxt_lo = hist[(lo - 1) % 256]
            if nxt_hi >= nxt_lo:
                hi += 1
                acc += nxt_hi
            else:
                lo -= 1
                acc += nxt_lo
        spread = hi - lo
        # Calibrated on real thumbnails: sepia/age-toned scans measured 5, 7,
        # 22, 23; genuine colour photographs measured 36, 130, 140. 30 sits in
        # the gap with margin on both sides, so the gold-costume Colbert shot
        # (our best-performing thumbnail, narrow-hue but truly colour) is kept
        # in colour while every toned scan is neutralised.
        return spread <= 30
    except Exception:
        return False


def _looks_like_print_matter(path: str) -> bool:
    """
    Content-based veto for ADS, POSTERS and TITLE CARDS reaching thumbnails.
    The filename gate cannot catch these — a magazine ad page scanned as
    "Gloria Swanson 1923.jpg" passes every name check, and exactly that (plus a
    Shanghai Express poster and a title card) shipped on live thumbnails.

    Type and layout spread strong small-scale contrast across MOST of the frame,
    while a photograph of a person concentrates its detail in the subject.
    Measured on the actual shipped junk vs good panels:
      ad page 0.51 · poster 0.54 · title card 1.00
      portraits/figures 0.08–0.38 (worst case: a sequin gown at 0.38)
    0.45 sits between with margin on both sides.
    """
    try:
        g = Image.open(path).convert('L').resize((128, 144))
        e = g.filter(ImageFilter.FIND_EDGES)
        busy = total = 0
        for ty in range(0, 144, 12):
            for tx in range(0, 128, 16):
                m = ImageStat.Stat(e.crop((tx, ty, tx + 16, ty + 12))).mean[0]
                total += 1
                if m > 40:
                    busy += 1
        return (busy / max(total, 1)) > 0.45
    except Exception:
        return False


# Figure/pinup hints — used to pair one FIGURE panel with one FACE panel, the
# contrast that makes the diptych seductive rather than two similar close-ups.
_FIGURE_HINT = re.compile(
    r'\b(swimsuit|bathing|pin-?up|swimwear|beach|pool|leggy|legs|dancer|showgirl|'
    r'chorus|gown|evening dress|stocking|fishnet|shorts|cheesecake|full[- ]length|'
    r'figure|posing|glamour)\b', re.I)


def _subject_point(img: Image.Image) -> Tuple[float, float]:
    """
    Estimate where the subject's head is, Pillow-only (no OpenCV / no ML).

    In a cover-cropped vintage portrait the head is the most detailed region in
    the upper half of the frame, and it is lighter than the backdrop far more
    often than not. We take the detail (edge) energy in the upper band, weight
    it toward mid/high luminance so hair-vs-backdrop edges don't dominate, and
    return its centroid. Falls back to upper-centre if the image is featureless.
    """
    W, H = img.size
    try:
        g = img.convert('L').resize((96, 54), Image.BILINEAR)
        edges = g.filter(ImageFilter.FIND_EDGES)
        ep = list(edges.getdata())
        lp = list(g.getdata())
        gw, gh = 96, 54
        top = int(gh * 0.72)          # head lives in the upper ~72% after cropping
        sx = sy = tot = 0.0
        for y in range(1, top):
            for x in range(2, gw - 2):   # ignore the frame border columns
                i = y * gw + x
                lum = lp[i]
                # Detail, biased toward brighter (skin/lit) areas.
                wgt = ep[i] * (0.35 + 0.65 * (lum / 255.0))
                sx += x * wgt
                sy += y * wgt
                tot += wgt
        if tot <= 0:
            raise ValueError('no detail')
        cx, cy = sx / tot, sy / tot
        px = (cx / gw) * W
        py = (cy / gh) * H
        # HARD ENVELOPE. Adversarial testing across 25 real pool images showed a
        # pure edge-energy centroid mislocating the subject roughly a quarter of
        # the time (landing on a lace bodice, a pair of shoes, a torso). Because
        # create_thumbnail cover-crops head-safe, the head is *always* in the
        # upper-centre band — so we clamp hard into it and let the centroid only
        # nudge within that band. Wrong-but-plausible beats confidently-wrong,
        # and this cannot fail silently in an ugly way.
        px = min(W * 0.72, max(W * 0.28, px))
        py = min(H * 0.38, max(H * 0.12, py))
        return px, py
    except Exception:
        return W * 0.5, H * 0.26


def _draw_curled_arrow(img: Image.Image,
                       color: Tuple[int, int, int] = (230, 30, 45),
                       stroke: int = 11) -> Image.Image:
    """
    Senior-friendly red pointer (2026-07 redesign, owner request): a BOLD,
    smooth single arc with a large head, red with a white outline so it reads
    instantly against any photo — no thin squiggles. It starts in the upper
    corner opposite the subject's lean and points toward the face/figure
    (upper-center of the cover-cropped frame). Both reference channels use
    this device on nearly every thumbnail.
    """
    THUMB_W, THUMB_H = img.size
    # Target the ACTUAL subject, not a fixed point. Three weeks of live
    # thumbnails showed the old fixed upper-centre target landing on hat brims,
    # foreheads and empty backdrop — an arrow pointing at nothing is worse than
    # no arrow. _subject_point finds the head region from image detail.
    hx, hy = _subject_point(img)
    # Start from the emptier side so the arc crosses background, not the face.
    side = -1 if hx > THUMB_W * 0.5 else 1
    sx = min(THUMB_W - 40.0, max(40.0, hx + side * THUMB_W * 0.34))
    sy = max(30.0, hy - THUMB_H * 0.20)
    # STOP SHORT of the subject. The head estimate is approximate (it can land
    # on hair or a hat brim), and a bold arrow that lands ON the face damages
    # the very thing selling the click. Pulling the head back toward the start
    # makes the arrow GESTURE at the subject instead of covering it — and it
    # stays sensible even when the estimate is off.
    _dx, _dy = sx - hx, sy - hy
    _d = math.hypot(_dx, _dy) or 1.0
    _gap = THUMB_W * 0.11
    tx = hx + (_dx / _d) * _gap
    ty = hy + (_dy / _d) * _gap
    # One gentle arc bowing outward — simple to parse at a glance
    mx, my = (sx + tx) / 2, (sy + ty) / 2
    dx, dy = tx - sx, ty - sy
    dist = math.hypot(dx, dy) or 1
    ctrl_x = mx - (dy / dist) * dist * 0.35 * side
    ctrl_y = my + (dx / dist) * dist * 0.35 * side
    pts = []
    for i in range(33):
        t = i / 32
        bx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * ctrl_x + t ** 2 * tx
        by = (1 - t) ** 2 * sy + 2 * (1 - t) * t * ctrl_y + t ** 2 * ty
        pts.append((bx, by))
    pts[-1] = (tx, ty)

    layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ha = math.atan2(pts[-1][1] - pts[-5][1], pts[-1][0] - pts[-5][0])

    def head(size):
        w1 = (tx + size * math.cos(ha + math.radians(152)),
              ty + size * math.sin(ha + math.radians(152)))
        w2 = (tx + size * math.cos(ha - math.radians(152)),
              ty + size * math.sin(ha - math.radians(152)))
        return [pts[-1], w1, w2]

    # White outline pass (wider), then red pass on top → pops on any background
    d.line(pts, fill=(255, 255, 255, 255), width=stroke + 8, joint='curve')
    d.polygon(head(44), fill=(255, 255, 255, 255))
    d.line(pts, fill=color + (255,), width=stroke, joint='curve')
    d.polygon(head(34), fill=color + (255,))

    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    return Image.alpha_composite(img, layer).convert('RGB')


def _cover_crop(img: Image.Image, w: int, h: int, top_bias: float) -> Image.Image:
    """Scale-to-cover then crop to w x h, biasing the vertical window upward (faces)."""
    ow, oh = img.size
    scale = max(w / ow, h / oh)
    nw, nh = int(ow * scale), int(oh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = int((nh - h) * top_bias)
    return img.crop((left, top, left + w, top + h))


def _grade(img: Image.Image, greyscale: bool = False) -> Image.Image:
    """
    2026-07 REGRADE — measured against the reference channels' live thumbnails:
    they average saturation 13 and colour-cast ~0, i.e. clean NEUTRAL
    black-and-white with a wide tonal range. Our previous grade sepia-colorized
    every photo (measured saturation 128, warm cast +58), which made the whole
    channel grid read as one muddy yellow smear and is the single biggest visual
    gap vs the competitors.

    New behaviour:
      • Genuinely COLOUR originals keep their colour (our best-performing
        thumbnail was a real colour photo) — but the artificial warm tint is
        gone and any yellow cast is neutralised.
      • Everything else → clean neutral B&W: autocontrast to recover faded
        scans, a gentle S-curve for punch, mild sharpening.
      • NEVER adds a sepia/warm tint. `greyscale` now only forces B&W on a
        colour source; the tinting path is retired.
    """
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # A sepia/age-toned scan is monochrome wearing a tint — treat it as B&W, or
    # the muddy yellow look we set out to remove survives untouched.
    is_colour = not _is_low_saturation(img) and not _is_toned_monochrome(img)

    # 2026-08 VIBRANCY pass (owner: recent thumbnails "too dull" — CTR fell even
    # as watch time rose). The neutral regrade overshot into flat. Punch it up:
    if is_colour and not greyscale:
        # Real colour photo: neutralise the age cast, then push it VIVID —
        # rich saturation, bright, contrasty. Colour frames are the channel's
        # best performers; make them sing.
        img = _neutralise_cast(img)
        img = ImageOps.autocontrast(img, cutoff=(1, 1))
        img = ImageEnhance.Color(img).enhance(1.38)
        img = ImageEnhance.Contrast(img).enhance(1.20)
        img = ImageEnhance.Brightness(img).enhance(1.06)
    else:
        # B&W scan → DRAMATIC monochrome, not flat grey: hard autocontrast,
        # deep S-curve (rich blacks, luminous highlights), slight lift. This is
        # what the winners' B&W actually looks like — punchy, not passive.
        g = img.convert('L')
        g = ImageOps.autocontrast(g, cutoff=(2, 1))
        g = g.point(_SCURVE_DEEP)
        g = ImageEnhance.Brightness(g).enhance(1.05)
        img = g.convert('RGB')

    return ImageEnhance.Sharpness(img).enhance(1.35)


# Gentle S-curve: richer blacks and brighter highlights without clipping detail.
_SCURVE = [max(0, min(255, int(255 * (0.5 - 0.5 * math.cos(math.pi * (i / 255.0)) ** 1.0)
                              * 0.22 + i * 0.78))) for i in range(256)]
# Deep S-curve for the vibrancy grade: 40% curve weight — dramatic contrast,
# rich blacks, luminous highlights (still monotonic, no clipping plateaus).
_SCURVE_DEEP = [max(0, min(255, int(255 * (0.5 - 0.5 * math.cos(math.pi * (i / 255.0)))
                                   * 0.40 + i * 0.60))) for i in range(256)]


def _neutralise_cast(img: Image.Image) -> Image.Image:
    """Grey-world white balance — removes the yellow/orange cast typical of aged
    colour stock so colour thumbnails read clean rather than dingy."""
    stat = ImageStat.Stat(img)
    r, g, b = stat.mean
    grey = (r + g + b) / 3.0 or 1.0
    # Correct only partially (0.7) so the photo keeps its period character.
    def lut(mean):
        f = 1.0 + 0.7 * ((grey / (mean or 1.0)) - 1.0)
        return [max(0, min(255, int(i * f))) for i in range(256)]
    return Image.merge('RGB', [
        ch.point(lut(m)) for ch, m in zip(img.split(), (r, g, b))
    ])


def _apply_vignette(img: Image.Image) -> Image.Image:
    """
    Soft edge darkening to focus the eye inward.

    FIXED 2026-07: the previous implementation drew vertical edge lines and then
    horizontal edge lines into the SAME RGBA layer. ImageDraw replaces alpha
    rather than combining it, so the horizontal pass wiped out the vertical
    pass wherever they overlapped. Reproduced on flat grey: a hard 43-level
    seam at y=depth and y=h-depth, and corners no darker than edge midpoints —
    i.e. every thumbnail shipped with two full-width bands across it, which at
    grid size read as a half-loaded image.

    Now the two ramps are built as separate 8-bit masks and MULTIPLIED, giving a
    smooth, corner-weighted falloff with no seams.
    """
    w, h = img.size
    # mx 70 → 42 (2026-08 vibrancy pass): the heavy edge darkening was part of
    # why tiles read dull at grid size; keep just enough falloff to focus.
    depth, mx = min(200, w // 3), 42

    def ramp(n: int, size: int) -> List[int]:
        # 255 in the interior, easing down to (255-mx) at the very edge.
        out = [255] * size
        for i in range(min(n, size)):
            a = int(mx * (1 - i / float(n)) ** 2.2)
            out[i] = 255 - a
            out[size - 1 - i] = 255 - a
        return out

    col = ramp(depth, w)
    row = ramp(depth, h)
    hmask = Image.new('L', (w, h))
    hmask.putdata(col * h)                       # horizontal falloff
    vmask = Image.new('L', (w, h))
    vrow = []
    for y in range(h):
        vrow.extend([row[y]] * w)                # vertical falloff
    vmask.putdata(vrow)
    mask = ImageChops.multiply(hmask, vmask)     # corners get both → darkest

    black = Image.new('RGB', (w, h), (0, 0, 0))
    return Image.composite(img.convert('RGB'), black, mask)


def _apply_frame(img: Image.Image) -> Image.Image:
    """Thin warm-gold border + small AAP corner monogram (brand signature)."""
    if not getattr(config, 'THUMB_ENABLE_FRAME', True):
        return img
    w, h = img.size
    draw = ImageDraw.Draw(img)
    for i in range(6):
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=_GOLD)
    cx, cy, r = 64, 62, 34
    mono = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    md = ImageDraw.Draw(mono)
    md.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 90), outline=_GOLD + (220,), width=2)
    fm = _load_font(26)
    bb = md.textbbox((0, 0), "AAP", font=fm)
    md.text((cx - (bb[2] - bb[0]) / 2, cy - (bb[3] - bb[1]) / 2 - 3), "AAP", font=fm, fill=_GOLD + (235,))
    return Image.alpha_composite(img.convert('RGBA'), mono).convert('RGB')


def _draw_word(img: Image.Image, word: str, text_color: str) -> Image.Image:
    """Optional single elegant ALL-CAPS word low in the frame (off by default)."""
    w, h = img.size
    grad = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    gs = int(h * 0.55)
    for y in range(gs, h):
        a = int(190 * (((y - gs) / (h - gs)) ** 1.5))
        gd.line([(0, y), (w, y)], fill=(0, 0, 0, a))
    img = Image.alpha_composite(img.convert('RGBA'), grad).convert('RGB')
    draw = ImageDraw.Draw(img)
    word = word.upper().split('\n')[0]
    f = _load_font(74)
    bb = draw.textbbox((0, 0), word, font=f)
    x = (w - (bb[2] - bb[0])) // 2
    y = h - 74 - 50
    for off in [5, 4, 3, 2]:
        for dx, dy in [(-off, 0), (off, 0), (0, -off), (0, off),
                       (-off, -off), (off, off), (-off, off), (off, -off)]:
            draw.text((x + dx, y + dy), word, font=f, fill='black')
    draw.text((x, y), word, font=f, fill=text_color)
    return img


def create_thumbnail(image_path: str, output_path: str,
                     title_text: str = None, text_color: str = '#F4D67A') -> str:
    """
    Single FULL-FRAME subject thumbnail (the default since 2026-07: both
    reference channels run one subject filling the whole frame, face + figure
    visible — not split halves, not tight face crops). Feed it the ORIGINAL
    photo, not the pillarboxed video canvas, so the subject truly fills 1280x720.
    """
    THUMB_W, THUMB_H = 1280, 720
    with Image.open(image_path) as im:
        img = im.convert('RGB')
        ow, oh = img.size
        aspect = oh / max(ow, 1)
        if aspect >= 1.45:
            # Full-length pinup/gown shot: crop from just above the head so the
            # 16:9 window shows head-to-waist (face AND figure), never a
            # decapitated torso.
            bias = 0.05
        elif aspect >= 1.0:
            # Chest-up portrait: keep the whole head in frame (0.34 clipped
            # hairlines when the source is only slightly taller than wide).
            bias = 0.13
        else:
            bias = 0.40
        img = _cover_crop(img, THUMB_W, THUMB_H, bias)
        img = _grade(img, random.random() < getattr(config, 'THUMB_GREYSCALE_RATIO', 0.0))
        img = _apply_vignette(img)
        if getattr(config, 'THUMB_ENABLE_TEXT', False) and title_text:
            img = _draw_word(img, getattr(config, 'THUMB_TEXT_WORD', None) or title_text, text_color)
        img = _apply_frame(img)
        if getattr(config, 'THUMB_ENABLE_ARROW', False):
            img = _draw_curled_arrow(img)
        img.save(output_path, 'JPEG', quality=95)
    return output_path


def _frame_score(path: str) -> float:
    """
    Rank a thumbnail candidate by how much it looks like a clean PORTRAIT
    (a subject over a plainer background) rather than a cluttered environmental
    scene. Plain edge-variance was fooled by clutter — a bookshelf/office or a
    street scene has detail everywhere and scored HIGH, so the picker once put a
    library shot on the thumbnail. Instead we score SUBJECT-vs-BACKGROUND
    structure:
      • ratio  = central edge detail / surrounding edge detail
                 (a portrait's detail is concentrated on the face; a scene's is
                  spread across the whole frame)
      • smooth = fraction of the centre that is calm (skin / studio backdrop);
                 a face has a big smooth region, a bookshelf/street does not
      • exposure favours a well-lit mid-tone subject
    Validated to separate faces from hallway/street/magazine frames ~2×.
    Pillow-only (no OpenCV) so it runs on the slim Railway image.
    """
    from PIL import ImageFilter, ImageStat
    with Image.open(path) as im:
        g = im.convert('L')
        g.thumbnail((600, 600))
        w, h = g.size
        box = (int(w * 0.28), int(h * 0.10), int(w * 0.72), int(h * 0.92))
        edges = g.filter(ImageFilter.FIND_EDGES)
        center = g.crop(box)
        center_edges = center.filter(ImageFilter.FIND_EDGES)
        ce = ImageStat.Stat(center_edges).var[0]
        iv = ImageStat.Stat(edges.crop(box)).var[0]
        fv = ImageStat.Stat(edges).var[0]
        ai = (box[2] - box[0]) * (box[3] - box[1])
        af = w * h
        border = max(1.0, (fv * af - iv * ai) / max(1, af - ai))
        ratio = ce / border
        hist = center_edges.histogram()            # mode 'L' → 256 bins
        total = sum(hist) or 1
        smooth = sum(hist[:12]) / total            # calm (low-edge) fraction
        mean = ImageStat.Stat(center).mean[0]
        exposure = 1.0 - min(abs(mean - 130) / 130.0, 1.0)

        # smooth**2 used to be a straight multiplier, which REWARDED emptiness —
        # a near-blank frame scored highest, and that is how a "The Palm Beach
        # Story" title card (large calm areas of lettering on a calm ground) beat
        # real portraits onto a live thumbnail. Smoothness is now a bounded
        # bonus for clean backdrops, and a frame with almost no detail is
        # penalised rather than promoted.
        smooth_bonus = min(smooth, 0.80)
        detail = min(ce / 400.0, 1.0)              # real subject detail present?
        if detail < 0.05:                          # essentially featureless
            return 0.0
        return ratio * (0.35 + 0.65 * smooth_bonus) * detail * (0.5 + 0.5 * exposure)


def _pick_split_pair(paths: List[str], names: Optional[List[str]] = None) -> List[str]:
    """
    Pick the 2 candidate frames for the diptych.

    2026-08 (owner: "more seductive"): the ideal pair is one FIGURE shot
    (gown/swimsuit/full-length glamour) beside one FACE shot — the contrast is
    what makes the tile arresting; two similar close-ups read as filler. So:
    ads/posters/title cards are vetoed by CONTENT (the filename gate missed a
    scanned ad page, a poster and a title card that all shipped live), then the
    best figure-hinted frame takes one panel if one exists, and the best
    remaining DIFFERENT-subject frame takes the other.
    """
    scored = []
    for i, p in enumerate(paths[:8]):
        try:
            if _looks_like_print_matter(p):
                continue
            hint = (names[i] if names and i < len(names) else '') or ''
            key = ' '.join(hint.lower().split()[:2])  # subject fingerprint
            figure = bool(_FIGURE_HINT.search(hint))
            scored.append((_frame_score(p), p, key, figure))
        except Exception:
            continue
    if len(scored) < 2:
        # Not enough clean frames — fall back to the raw list rather than fail.
        return [p for _, p, _, _ in scored] or paths[:2]
    scored.sort(key=lambda t: t[0], reverse=True)

    figures = [s for s in scored if s[3]]
    if figures:
        first = figures[0]                       # best figure shot leads
        rest = [s for s in scored if s is not first]
    else:
        first = scored[0]
        rest = scored[1:]
    second = next((s for s in rest if not s[2] or s[2] != first[2]),
                  rest[0] if rest else first)
    return [first[1], second[1]]


def create_split_thumbnail(image_paths: List[str], output_path: str) -> str:
    """
    Old-World-Photos-style diptych: TWO real compilation frames split down the
    middle, each graded, with a thin gold center divider + the brand frame. No
    text — the seductive vintage faces carry the click.
    """
    THUMB_W, THUMB_H = 1280, 720
    half = THUMB_W // 2
    greyscale = random.random() < getattr(config, 'THUMB_GREYSCALE_RATIO', 0.0)
    canvas = Image.new('RGB', (THUMB_W, THUMB_H), (10, 8, 6))
    for i, p in enumerate(image_paths[:2]):
        with Image.open(p) as im:
            sub = im.convert('RGB')
            ow, oh = sub.size
            aspect = oh / max(ow, 1)
            # The panel is 640x720 (aspect 1.125), close to portrait, so tall
            # sources survive well — but a FULL-LENGTH figure shot still needs a
            # near-top crop or the gown becomes a headless torso. Head-safe
            # bias by source shape (mirrors create_thumbnail's fix).
            if aspect >= 1.60:
                bias = 0.04     # full-length: head at top, figure below
            elif aspect > 1.0:
                bias = 0.22     # portrait: whole head + shoulders
            else:
                bias = 0.42     # landscape: centre-ish
            sub = _cover_crop(sub, half, THUMB_H, bias)
            sub = _grade(sub, greyscale)
            canvas.paste(sub, (i * half, 0))
    canvas = _apply_vignette(canvas)
    # thin gold center divider
    ImageDraw.Draw(canvas).rectangle([half - 4, 0, half + 4, THUMB_H], fill=_GOLD)
    canvas = _apply_frame(canvas)
    if getattr(config, 'THUMB_ENABLE_ARROW', False):
        canvas = _draw_curled_arrow(canvas)
    canvas.save(output_path, 'JPEG', quality=95)
    return output_path


def generate_thumbnail_and_title(metadata_path: str) -> Dict:
    """Generate thumbnail + title from a video metadata file."""
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Title/packaging via Gemini, fall back to the shared builder
    gemini_result = None
    try:
        from gemini_generator import generate_with_gemini
        print("  Calling Gemini AI for title...")
        gemini_result = generate_with_gemini(metadata)
        if gemini_result:
            print(f"  Gemini title: {gemini_result['title'].encode('ascii', 'replace').decode()}")
        else:
            print("  Gemini returned no result, using fallback title")
    except Exception as e:
        print(f"  Gemini failed ({e}), using fallback title")

    if gemini_result:
        title = gemini_result['title']
        thumbnail_text = gemini_result.get('thumbnail_text', 'RARE')
        text_color = gemini_result.get('text_color', '#F4D67A')
    else:
        title = generate_title(metadata)
        thumbnail_text = random.choice(["RARE", "UNSEEN", "GOLDEN ERA", "RARE COLLECTION"])
        text_color = '#F4D67A'

    video_path = metadata.get('video_file', '')
    output_dir = os.path.dirname(video_path) or config.OUTPUT_FOLDER
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    thumbnail_path = os.path.join(output_dir, f"{base_name}_thumbnail.jpg")

    # Build the thumbnail from the video's OWN compilation photos (relevance).
    # DEFAULT since 2026-07: ONE full-frame subject built from the ORIGINAL
    # photo (verified: both reference channels run a single figure filling the
    # whole frame — not diptychs, not tight face crops). Candidates arrive
    # pre-ranked pinup/portrait/star-first from create_slideshow. Fall back to
    # the split diptych (canvases), then single-canvas, then curated pool.
    _with_paths = [img for img in metadata.get('images', [])
                   if img.get('local_path') and os.path.exists(img['local_path'])]
    video_imgs = [img['local_path'] for img in _with_paths]
    # Subject hints so the two diptych halves show different stars when possible
    video_hints = [(img.get('generated_caption') or img.get('image_filename') or '')
                   for img in _with_paths]
    # Original (un-pillarboxed) photos — the preferred thumbnail source.
    video_origs = [img['local_orig'] for img in _with_paths
                   if img.get('local_orig') and os.path.exists(img['local_orig'])]
    thumb_rendered = False

    # 1) SINGLE full-frame subject from the best ORIGINAL photo (default).
    if not getattr(config, 'THUMB_SPLIT', False) and video_origs:
        try:
            # Honour the upstream gating: prefer frames create_slideshow marked
            # thumb_eligible (a named leading lady, solo, not a title card /
            # trailer screenshot / scene). Only if none qualify do we fall back
            # to every persisted frame. _frame_score then picks the best-LOOKING
            # among the eligible ones — it ranks quality, not subject.
            eligible = [img['local_orig'] for img in _with_paths
                        if img.get('thumb_eligible')
                        and img.get('local_orig') and os.path.exists(img['local_orig'])]
            pool = eligible or video_origs
            print(f"  Thumbnail pool: {len(eligible)} eligible / {len(video_origs)} persisted"
                  f"{'' if eligible else ' — no leading-lady frame, using fallback pool'}")
            scored = []
            for p in pool[:8]:
                try:
                    scored.append((_frame_score(p), p))
                except Exception:
                    continue
            best = max(scored)[1] if scored else pool[0]
            create_thumbnail(best, thumbnail_path, title_text=thumbnail_text, text_color=text_color)
            print(f"  Full-frame thumbnail from original photo: {os.path.basename(best)}")
            thumb_rendered = True
        except Exception as e:
            print(f"  Full-frame thumbnail failed ({e}); falling back to split")

    # 2) Split diptych — the default. Built from the ORIGINAL photos (the video
    # canvas is pillarboxed, so the subject would render small), and restricted
    # to frames create_slideshow marked thumb_eligible (named leading lady,
    # solo, not a title card / trailer / scene).
    if not thumb_rendered:
        _elig = [img for img in _with_paths
                 if img.get('thumb_eligible') and img.get('local_orig')
                 and os.path.exists(img['local_orig'])]
        _src = _elig or [img for img in _with_paths
                         if img.get('local_orig') and os.path.exists(img['local_orig'])]
        split_paths = [img['local_orig'] for img in _src] or video_imgs
        split_hints = [(img.get('generated_caption') or img.get('image_filename') or '')
                       for img in _src] or video_hints
        print(f"  Diptych pool: {len(_elig)} eligible / {len(_with_paths)} persisted"
              f"{'' if _elig else ' — no leading-lady frame, using fallback pool'}")
    if not thumb_rendered and len(split_paths) >= 2:
        pair = _pick_split_pair(split_paths, names=split_hints)
        try:
            create_split_thumbnail(pair, thumbnail_path)
            print(f"  Split thumbnail from compilation frames: {[os.path.basename(p) for p in pair]}")
            thumb_rendered = True
        except Exception as e:
            print(f"  Split thumbnail failed ({e}); falling back to single frame")

    # 2b) Diptych wanted but only ONE gated frame survived. Render that frame
    # full-frame from its ORIGINAL rather than dropping to step 3, which takes
    # video_imgs[0] — an arbitrary, UNGATED, pillarboxed canvas. Skipping this
    # is how 2026-08-08 shipped a lone uniformed man and a halftone print scan
    # on a glamour channel: the leading-lady/print-matter gating was silently
    # discarded exactly when it had done its job and left a single winner.
    if not thumb_rendered and len(split_paths) == 1:
        try:
            create_thumbnail(split_paths[0], thumbnail_path,
                             title_text=thumbnail_text, text_color=text_color)
            print("  Full-frame thumbnail from the single gated original: "
                  f"{os.path.basename(split_paths[0])}")
            thumb_rendered = True
        except Exception as e:
            print(f"  Single gated-original thumbnail failed ({e}); falling back to canvas")

    # 3) Single real compilation frame (canvas).
    if not thumb_rendered and video_imgs:
        try:
            create_thumbnail(video_imgs[0], thumbnail_path, title_text=thumbnail_text, text_color=text_color)
            print(f"  Single thumbnail from compilation frame: {os.path.basename(video_imgs[0])}")
            thumb_rendered = True
        except Exception as e:
            print(f"  Single-frame thumbnail failed ({e}); falling back to curated pool")

    # 4) Curated-pool fallback (no usable video frames).
    if not thumb_rendered:
        portrait_image = get_curated_portrait()
        if portrait_image:
            try:
                create_thumbnail(portrait_image, thumbnail_path, title_text=thumbnail_text, text_color=text_color)
                _record_recent(portrait_image)
                print(f"  Thumbnail subject (curated fallback): {os.path.basename(portrait_image)}")
                thumb_rendered = True
            except Exception as e:
                print(f"  Curated thumbnail failed ({e})")
    if not thumb_rendered:
        print("  Warning: No image available for thumbnail")
        thumbnail_path = None

    names = extract_names_from_metadata(metadata)
    result = {
        'title': title,
        'thumbnail_path': thumbnail_path,
        'names_found': names,
        'source': gemini_result['source'] if gemini_result else 'template',
    }
    if gemini_result:
        if 'all_titles' in gemini_result:
            result['all_titles'] = gemini_result['all_titles']
        if 'gemini_tags' in gemini_result:
            result['gemini_tags'] = gemini_result['gemini_tags']

    result_path = metadata_path.replace('_metadata.json', '_youtube.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)

    print(f"\nGenerated YouTube assets:")
    print(f"  Title: {title.encode('ascii', 'replace').decode()}")
    print(f"  Thumbnail: {thumbnail_path}")
    print(f"  Source: {'Gemini AI' if gemini_result else 'Template'}")
    return result


if __name__ == "__main__":
    import argparse
    import glob

    parser = argparse.ArgumentParser(description='Generate YouTube thumbnail and title')
    parser.add_argument('metadata', nargs='?', help='Path to metadata JSON file')
    parser.add_argument('--latest', action='store_true', help='Use most recent video metadata')
    args = parser.parse_args()

    if args.latest or not args.metadata:
        files = glob.glob(os.path.join(config.OUTPUT_FOLDER, "*_metadata.json"))
        if files:
            args.metadata = max(files, key=os.path.getctime)
            print(f"Using latest: {args.metadata}")
        else:
            print("No metadata files found!")
            exit(1)

    result = generate_thumbnail_and_title(args.metadata)
    print(f"\nDone! Title: {result['title'].encode('ascii', 'replace').decode()}")
