"""
AAP — 1-minute vertical SHORTS generator (primary format since 2026-08).

Why shorts: this channel's own history shows Shorts out-performing long-form
roughly 2:1 in every month they ran (Aug 2025 medians 912 vs 560; Sep 2025
1,262 vs 586), and they have been unused since.

Format, deliberately different from the long-form pipeline:
  • 1080x1920 vertical, ~55s (safely inside the 60s bar)
  • NO branded intro — a 16s logo is fatal to a scroll-stopping format
  • 11 photos, the first few faster, so something changes before a thumb swipes
  • continuous Ken Burns motion (a static photo reads as a dead video)
  • one bold star name burned in, because Shorts are watched fast and often muted
  • music starts mid-track where it already has energy, never on a slow intro
  • photos vetted by the existing free heuristics (leading-lady gate,
    print-matter veto, quality gate); Gemini vision scouting exists but is
    OFF by default because it costs one image request per photo
"""

import os
import re
import json
import random
import shutil
import subprocess
import tempfile
import asyncio
from datetime import datetime
from typing import List, Dict, Optional

from PIL import Image
import config
from scrape_descriptions import scrape_batch


# --------------------------------------------------------------------------
# Frame composition
# --------------------------------------------------------------------------
def compose_vertical_frame(src_path: str, out_path: str) -> bool:
    """
    Cover-crop a source photo to the vertical canvas and grade it.

    Our sources are tall studio portraits, so 9:16 fits them far better than
    16:9 ever did — but a full-length shot still needs a near-top crop or the
    subject becomes a headless torso. Reuses the thumbnail grade so Shorts,
    thumbnails and long-form all look like one channel.
    """
    try:
        from generate_thumbnail import _cover_crop, _grade
        W, H = config.SHORT_WIDTH, config.SHORT_HEIGHT
        with Image.open(src_path) as im:
            img = im.convert('RGB')
            ow, oh = img.size
            aspect = oh / max(ow, 1)
            if aspect >= 1.55:
                bias = 0.04          # full-length: keep the head, show the figure
            elif aspect > 1.0:
                bias = 0.16          # portrait: whole head + shoulders
            else:
                bias = 0.34          # landscape source: favour the upper third
            if getattr(config, 'SHORT_LAYOUT', 'fit') == 'fit':
                # The channel's best shorts (2025) showed the WHOLE photo,
                # centred on black: nothing cropped off, a formal montage.
                # 2026-10: a little lower and smaller, leaving a bar above for
                # the year ticker, inside a thin gold keyline like a mounted
                # vintage print.
                keyline = getattr(config, 'SHORT_KEYLINE', False)
                max_h = float(getattr(config, 'SHORT_PHOTO_MAX_H', 0.80))
                max_w = W - (64 if keyline else 0)
                scale = min(max_w / ow, (H * max_h) / oh)
                photo = _grade(img.resize((max(1, int(ow * scale)), max(1, int(oh * scale))),
                                          Image.LANCZOS))
                canvas = Image.new('RGB', (W, H), (0, 0, 0))
                top = int(H * 0.47 - photo.height / 2)
                top = max(int(H * 0.09), min(top, H - photo.height))
                left = (W - photo.width) // 2
                canvas.paste(photo, (left, top))
                if keyline:
                    from PIL import ImageDraw
                    d, g = ImageDraw.Draw(canvas), 12
                    d.rectangle([left - g, top - g, left + photo.width + g - 1,
                                 top + photo.height + g - 1], outline=(196, 164, 104), width=3)
                img = canvas
            else:
                img = _cover_crop(img, W, H, bias)
                img = _grade(img)
            img.save(out_path, 'JPEG', quality=94)
        return True
    except Exception as e:
        print(f"    frame composition failed: {e}")
        return False


def _esc(text: str) -> str:
    """Escape text for the ffmpeg drawtext filter."""
    return (text.replace('\\', r'\\').replace(':', r'\:')
                .replace("'", r"\'").replace('%', r'\%'))


# --- on-screen text blocks (hook, quote card) -------------------------------
# Text goes through drawtext's textfile= option, not text=: quotes are full of
# apostrophes, and ffmpeg's inline escaping can't carry a quote character
# inside a single-quoted filter argument (the old end-card prompts dodged this
# by banning apostrophes outright).
_BAND_TOP, _BAND_BOTTOM = 0.40, 0.70   # below the faces, above the Shorts UI
# fit layout leaves a black bar above the photo: the question sits there
_PROMPT_Y = 0.015 if getattr(config, 'SHORT_LAYOUT', 'fit') == 'fit' else 0.52


def _wrap(text: str, max_chars: int):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def _balanced(text: str, max_chars: int):
    """Wrap into as few lines as max_chars allows, then even the lines out and
    prefer breaking after a sentence ("No filters. No Botox. / No problem."
    rather than "No filters. No / Botox. No problem.")."""
    n = len(_wrap(text, max_chars))
    if n <= 1:
        return [text]
    best, best_cost = None, None
    for width in range(max(8, len(text) // n), max_chars + 1):
        lines = _wrap(text, width)
        if len(lines) != n:
            continue
        cost = max(map(len, lines)) - 6 * sum(l[-1:] in '.!?,;' for l in lines[:-1])
        if best_cost is None or cost < best_cost:
            best, best_cost = lines, cost
    return best or _wrap(text, max_chars)


def _fit(text: str, max_size: int, min_size: int, max_lines: int, width: int = 960):
    """Largest font size (<= max_size) at which `text` wraps into max_lines
    lines of ~960px. Sans glyphs average ~0.55em (DejaVu, the CI font, runs
    wider than Arial, so don't tighten this from a Windows preview)."""
    # First choice: break only at sentence/clause ends, giving up to ~12px of
    # size for it -- a natural break reads faster than a bigger awkward one.
    chunks = [c for c in re.split(r'(?<=[.!?,;])\s+', text) if c]
    if len(chunks) > 1:
        for size in range(max_size, max(min_size, max_size - 12) - 1, -4):
            cap = max(8, int(width / (0.55 * size)))
            if max(map(len, chunks)) > cap:
                continue
            lines, cur = [], ''
            for ch in chunks:
                if cur and len(cur) + 1 + len(ch) > cap:
                    lines.append(cur)
                    cur = ch
                else:
                    cur = f"{cur} {ch}".strip()
            lines.append(cur)
            if len(lines) <= max_lines:
                return size, lines
    for size in range(max_size, min_size - 1, -4):
        cap = max(8, int(width / (0.55 * size)))
        if len(_wrap(text, cap)) <= max_lines:
            return size, _balanced(text, cap)
    return min_size, _balanced(text, max(8, int(width / (0.55 * min_size))))


def _textfile(dirpath: str, text: str) -> str:
    fd, p = tempfile.mkstemp(suffix='.txt', dir=dirpath)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    return p.replace('\\', '/').replace(':', '\\:')


def _block_filter(block: dict, dirpath: str) -> str:
    """drawtext chain for a centred block: main lines (white on a dark plate)
    plus an optional gold subline, vertically centred in the safe band."""
    font = (block.get('font') or config.CAPTION_FONT_FILE).replace('\\', '/').replace(':', '\\:')
    H = config.SHORT_HEIGHT
    width = block.get('width', 960)
    size, lines = _fit(block['text'], block.get('size', 84), block.get('min_size', 56),
                       block.get('max_lines', 4), width)
    sub = block.get('sub', '')
    ssize, slines = _fit(sub, 56, 44, 2, width) if sub else (0, [])
    lh, slh = int(size * 1.28), int(ssize * 1.3)
    total = lh * len(lines) + (24 + slh * len(slines) if slines else 0)
    top_f, bot_f = block.get('band', (_BAND_TOP, _BAND_BOTTOM))
    y0 = int(H * (top_f + bot_f) / 2 - total / 2)
    y0 = max(int(H * top_f), min(y0, int(H * bot_f) - total))
    plate = (":box=1:boxcolor=black@0.5:boxborderw=18" if block.get('plate', True)
             else ":shadowcolor=black@0.85:shadowx=3:shadowy=3")
    out = ''
    # serif strokes are finer than sans: a sans-weight outline smears them
    bw = max(3, size // 14) if block.get('font') else max(5, size // 10)
    for i, ln in enumerate(lines):
        out += (f",drawtext=fontfile='{font}':textfile='{_textfile(dirpath, ln)}'"
                f":expansion=none:fontcolor=white:fontsize={size}"
                f":borderw={bw}:bordercolor=black@0.95"
                f"{plate}"
                f":x=(w-text_w)/2:y={y0 + i * lh}")
    for j, ln in enumerate(slines):
        out += (f",drawtext=fontfile='{font}':textfile='{_textfile(dirpath, ln)}'"
                f":expansion=none:fontcolor=0xFFD66B:fontsize={ssize}"
                f":borderw={max(4, ssize // 10)}:bordercolor=black@0.95"
                f":x=(w-text_w)/2:y={y0 + lh * len(lines) + 24 + j * slh}")
    return out



def _render_clip(frame_path: str, out_path: str, duration: float,
                 label: str, zoom_in: bool, prompt: tuple = (),
                 block: dict = None, ticker: tuple = ()) -> bool:
    """One Ken Burns clip with the star label burned in. `prompt` (headline,
    subline) adds the end-card comment question in the top third. `ticker`
    (year, era label) is the gold timeline marker in the bar above the photo."""
    W, H, FPS = config.SHORT_WIDTH, config.SHORT_HEIGHT, config.FPS
    frames = max(1, int(duration * FPS))
    # Upscale 2x before zoompan: zoompan is famously jittery when it steps
    # across a small source, and the extra pixels keep the motion smooth.
    if getattr(config, 'SHORT_KENBURNS', True):
        zmax = 1.06 if getattr(config, 'SHORT_LAYOUT', 'fit') == 'fit' else 1.15
        if getattr(config, 'SHORT_TICKER', False) and getattr(config, 'SHORT_LAYOUT', 'fit') == 'fit':
            zmax = 1.04     # a deeper zoom pushes the photo's top edge into the ticker
        step = (zmax - 1.0) / max(frames, 1)
        if zoom_in:
            z = f"min(zoom+{step:.6f},{zmax})"
        else:
            z = f"if(lte(zoom,1.0),{zmax},max(1.0,zoom-{step:.6f}))"
        motion = (f"scale={W*2}:{H*2},"
                  f"zoompan=z='{z}':d={frames}:x='iw/2-(iw/zoom/2)':"
                  f"y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}")
    else:
        motion = f"scale={W}:{H},fps={FPS}"

    vf = motion
    if getattr(config, 'SHORT_FILM_GRAIN', False):
        vf += ",noise=alls=6:allf=t"      # faint moving grain: an old print, not a JPEG
    if ticker:
        # Timeline marker: the year in gold serif, the era beneath in small
        # caps -- the viewer always knows where in history the photo sits.
        sfont = getattr(config, 'SERIF_FONT_FILE', config.CAPTION_FONT_FILE)
        sfont = sfont.replace('\\', '/').replace(':', '\\:')
        year, tag = (list(ticker) + [''])[:2]
        vf += (f",drawtext=fontfile='{sfont}':textfile='{_textfile(os.path.dirname(out_path), str(year))}'"
               f":expansion=none:fontcolor=0xE2C27A:fontsize=76:borderw=4:bordercolor=black@0.9"
               f":x=(w-text_w)/2:y=16")
        if tag:
            vf += (f",drawtext=fontfile='{sfont}':textfile='{_textfile(os.path.dirname(out_path), tag)}'"
                   f":expansion=none:fontcolor=white@0.92:fontsize=28:borderw=3:bordercolor=black@0.9"
                   f":x=(w-text_w)/2:y=98")
    if label:
        font = config.CAPTION_FONT_FILE.replace('\\', '/').replace(':', '\\:')
        # Lower third, large, white on a soft dark plate — legible at a glance
        # on a phone, which is the only way a Short is ever watched.
        # BIG. The audience is 65+ and this plays on a phone at arm's length —
        # the channel's better-performing past output used large, plainly
        # readable names. 110px on a 1080-wide canvas is ~10% of frame width,
        # with a heavy outline and a dark plate so it stays legible over any
        # photo. Long names shrink one step rather than overflow the frame.
        size = max(64, min(110, int(990 / (0.66 * max(len(label), 1)))))
        tf = _textfile(os.path.dirname(out_path), label)
        vf += (f",drawtext=fontfile='{font}':textfile='{tf}':expansion=none"
               f":fontcolor=white:fontsize={size}:borderw=9:bordercolor=black@0.95"
               f":box=1:boxcolor=black@0.45:boxborderw=26"
               f":shadowcolor=black@0.7:shadowx=4:shadowy=4"
               f":x=(w-text_w)/2:y=h*0.74")
    if block:
        vf += _block_filter(block, os.path.dirname(out_path))
    if prompt:
        # END-CARD QUESTION. Shorts loop, so the last seconds are what sits on
        # screen while a viewer decides whether to comment. A plain, warm
        # question in big type is the cheapest engagement lever there is for
        # this audience. Sits just above the name plate (y 0.80), over the torso:
        # the head-safe crop keeps faces in the top third, which text must not cover.
        font = config.CAPTION_FONT_FILE.replace('\\', '/').replace(':', '\\:')
        head, sub = (list(prompt) + [''])[:2]
        tdir = os.path.dirname(out_path)
        if getattr(config, 'SHORT_TICKER', False) and getattr(config, 'SHORT_LAYOUT', 'fit') == 'fit':
            # History layout: the question takes the ticker's place in the bar
            # above the photo, in the same serif (the photo starts lower now,
            # so the old two-line prompt ran into it).
            sfont = getattr(config, 'SERIF_FONT_FILE', config.CAPTION_FONT_FILE)
            sfont = sfont.replace('\\', '/').replace(':', '\\:')
            hs = max(46, min(64, int(980 / (0.55 * max(len(head), 1)))))
            vf += (f",drawtext=fontfile='{sfont}':textfile='{_textfile(tdir, head)}':expansion=none"
                   f":fontcolor=white:fontsize={hs}:borderw=4:bordercolor=black@0.9"
                   f":x=(w-text_w)/2:y=22")
            if sub:
                vf += (f",drawtext=fontfile='{sfont}':textfile='{_textfile(tdir, sub)}':expansion=none"
                       f":fontcolor=0xE2C27A:fontsize=34:borderw=3:bordercolor=black@0.9"
                       f":x=(w-text_w)/2:y={22 + hs + 14}")
            prompt = ()
    if prompt:
        # Bold sans runs ~0.6em per glyph: size to fit ~960px of the 1080 frame.
        hsize = max(56, min(84, int(960 / (0.6 * max(len(head), 1)))))
        ssize = max(44, min(62, int(960 / (0.6 * max(len(sub), 1)))))
        vf += (f",drawtext=fontfile='{font}':textfile='{_textfile(tdir, head)}':expansion=none"
               f":fontcolor=white:fontsize={hsize}:borderw=8:bordercolor=black@0.95"
               f":box=1:boxcolor=black@0.55:boxborderw=24"
               f":x=(w-text_w)/2:y=h*{_PROMPT_Y}")
        if sub:
            vf += (f",drawtext=fontfile='{font}':textfile='{_textfile(tdir, sub)}':expansion=none"
                   f":fontcolor=0xFFD66B:fontsize={ssize}:borderw=7:bordercolor=black@0.95"
                   f":x=(w-text_w)/2:y=h*{_PROMPT_Y}+{hsize + 58}")

    cmd = [config.FFMPEG_PATH, '-y', '-loop', '1', '-i', frame_path,
           '-t', f'{duration:.2f}', '-vf', vf,
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
           '-pix_fmt', 'yuv420p', '-r', str(FPS), '-an', out_path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    clip render failed: {r.stderr[-300:]}")
        return False
    return True


def _build_audio(total_duration: float, temp_dir: str) -> Optional[str]:
    """
    Music bed for the short.

    Starting a track at 0:00 means opening on its quiet intro — death for a
    format where the first second decides everything. We seek into the track
    where it already has energy, then fade in fast and out gently.
    """
    tracks = [p for p in config.AUDIO_FILES if os.path.exists(p)]
    if not tracks:
        print("    no music files found — rendering silent")
        return None
    # The channel's best shorts ran on "Soul and Mind - E's Jammy Jams";
    # weight toward it (and its sibling track) instead of a flat draw.
    weights = []
    for t in tracks:
        w = 1.0
        for key, wt in getattr(config, 'SHORT_MUSIC_WEIGHTS', {}).items():
            if key.lower() in os.path.basename(t).lower():
                w = float(wt)
                break
        weights.append(w)
    track = random.choices(tracks, weights=weights, k=1)[0]
    lo, hi = getattr(config, 'SHORT_MUSIC_START', (18, 45))
    # Clamp the seek to what the track can actually supply. Seeking past the end
    # makes ffmpeg emit an empty stream and the short ships SILENT — which is
    # exactly what happened on a test run when a shorter track was drawn.
    track_len = _probe_duration(track)
    headroom = track_len - total_duration - 0.5
    if headroom <= 0:
        offset = 0.0
        loop_args = ['-stream_loop', '-1']      # track shorter than the short
    else:
        offset = random.uniform(min(lo, headroom), min(hi, headroom))
        loop_args = []
    out = os.path.join(temp_dir, 'audio.m4a')
    # A short loops: a long fade-out tells the viewer it is over right as the
    # replay starts. Only a de-click fade at the very end (2026-10 audit).
    fade = 0.3
    fade_out_at = max(0.1, total_duration - fade)
    cmd = [config.FFMPEG_PATH, '-y'] + loop_args + ['-ss', f'{offset:.2f}', '-i', track,
           '-t', f'{total_duration:.2f}',
           '-af', (f"volume={config.MUSIC_VOLUME},"
                   f"afade=t=in:st=0:d=0.35,"
                   f"afade=t=out:st={fade_out_at:.2f}:d={fade}"),
           # -vn is essential: these mp3s carry embedded cover art, which ffmpeg
           # sees as a video stream and the m4a muxer then refuses to write
           # ("could not write header"), silently shipping a SILENT short.
           '-vn', '-c:a', 'aac', '-b:a', '192k', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    audio build failed: {r.stderr[-300:]}")
        return None
    print(f"    music: {os.path.basename(track)} from {offset:.0f}s "
          f"(track {track_len:.0f}s)")
    return out


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------
def generate_short(theme: Optional[str] = None) -> Optional[str]:
    """Build one vertical short. Returns the metadata path, or None on failure."""
    from create_slideshow import (select_unused_images, mark_images_used,
                                  download_with_browser, record_focus_star)
    from create_slideshow import _build_xfade_filter

    keep = getattr(config, 'SHORT_IMAGE_COUNT', 11)
    over = float(getattr(config, 'SHORT_OVERSELECT',
                         getattr(config, 'VISION_OVERSELECT', 1.9)))
    theme = theme or datetime.now().strftime("AAP_Short_%Y%m%d_%H%M")

    print("=" * 60)
    print(f"AAP SHORT — {theme}")
    print("=" * 60)

    # 1) Choose material (star-episode logic gives the short a subject)
    print("\n[1/6] Selecting photos...")
    curated_only = getattr(config, 'SHORT_CURATED_ONLY', True)
    pools = (config.GOLDMINE3_CSV,) if curated_only else None
    # Candidates run deeper than the download target: the download loop stops
    # at target_count successes, so spare rows cost nothing on a healthy pool
    # but keep a short from starving when many rows are rejected.
    cand = max(over, float(getattr(config, 'SHORT_CANDIDATE_MULT', 3.0)))
    if getattr(config, 'SHORT_CAPTION_STYLE', 'montage') == 'history':
        cand = max(cand, 3.5)
    star_min = int(getattr(config, 'SHORT_STAR_MIN_ROWS', 11))
    # Shorts recycle faster than long-form: their audience is mostly the
    # scrolling feed, not subscribers, so a photo returning after two weeks is
    # unseen by nearly everyone. At the 30-day window only 0 of 37 stars had
    # 11+ photos free after the first week of 5 videos/day; at 14 days, 30 do.
    reuse = int(getattr(config, 'SHORT_REUSE_DAYS', 14))
    # Owner call 2026-09-27: a short needn't be about one star -- a mixed
    # reel of many actresses is fine, and every clip gets its own fitting
    # wording (name, era line, quote). Star shorts still happen, just
    # occasionally, for variety.
    # HISTORY LENS (owner, 2026-10): every short walks forward through time.
    # Three kinds: a star "through the years", a themed story (WWII, the
    # talkies, the Oscar winners...) or a decade-by-decade timeline.
    history = getattr(config, 'SHORT_CAPTION_STYLE', 'montage') == 'history'
    if history:
        keep = int(getattr(config, 'SHORT_HISTORY_CLIPS', 12))
        # older scans fail the print-matter veto more often (a silent-era
        # theme lost 11 of 22 frames in testing): line up and fetch more
        over = max(over, 2.4)
    roll = random.random()
    star_rate = float(getattr(config, 'SHORT_STAR_RATE', 0.3))
    want_star = roll < star_rate
    story = None
    if history and not want_star and roll < star_rate + float(getattr(config, 'SHORT_THEME_RATE', 0.0)):
        story = _pick_short_theme(reuse, need=int(keep * 2.5))
    sel = dict(star_share=1.0, star_min_rows=star_min, reuse_days=reuse,
               for_shorts=True, star_episode=want_star)
    if story:
        sel['row_filter'] = _theme_row_filter(story)
        print(f"  THEMED SHORT: {story['key']}")
    rows = select_unused_images(int(keep * cand), pool_paths=pools, **sel)
    if len(rows) < keep and curated_only:
        print(f"  curated pool only yielded {len(rows)}; widening to all pools")
        rows = select_unused_images(int(keep * cand), **sel)
    if story and len(rows) < keep:
        print(f"  theme '{story['key']}' too thin ({len(rows)} rows); running as a timeline")
        story = None
        sel.pop('row_filter', None)
        rows = select_unused_images(int(keep * cand), pool_paths=pools, **sel)
    if len(rows) < 3:
        print("Error: not enough photos available")
        return None
    focus_star = next((r.get('focus_star') for r in rows if r.get('focus_star')), '')

    # 2) Captions (years / film titles feed the packaging)
    print("\n[2/6] Scraping captions...")
    rows = scrape_batch(rows, enhance=False)   # shorts show no captions

    # 3) Download
    print("\n[3/6] Downloading...")
    temp_dir = tempfile.mkdtemp(prefix="aap_short_")
    try:
        clips = asyncio.run(download_with_browser(rows, temp_dir,
                                                 target_count=int(keep * over)))
        spare = []          # clean frames ranked below the cut (timeline picks from them)
        min_clips = int(getattr(config, 'SHORT_MIN_CLIPS', 10))
        if len(clips) < min_clips:
            # A 20-second short with a generic title is worse than no short:
            # it teaches the algorithm the channel is thin. Fail loudly instead.
            print(f"Error: only {len(clips)} usable photos (need {min_clips})")
            mark_images_used([r for r in rows if r.get('quality_rejected')])
            return None  # (rejects are permanent; short_used untouched)

        # 4) VISION SCOUT — the model looks at each photo and drops the junk
        if getattr(config, 'VISION_SCOUT', True):
            print("\n[4/6] Vision scouting...")
            try:
                from gemini_generator import scout_images
                clips = scout_images(clips, keep=keep,
                                     min_score=float(getattr(config, 'VISION_MIN_SCORE', 6)))
            except Exception as e:
                print(f"  vision scouting unavailable ({e}); using best available")
                clips = clips[:keep]
        else:
            # FREE ranking stand-in for vision scouting: drop anything that
            # looks like print matter (ads/posters/title cards) and rank what
            # is left by the same subject-vs-background score the thumbnails
            # use, so damaged low-detail scans sink. Pillow only, no API cost.
            try:
                from generate_thumbnail import _frame_score, _looks_like_print_matter, _looks_like_line_art
                ranked = []
                for c in clips:
                    src = c.get('orig') or c.get('path')
                    if not src or not os.path.exists(src):
                        continue
                    try:
                        if _looks_like_print_matter(src) or _looks_like_line_art(src):
                            print(f"    skip (print matter): {os.path.basename(src)[:40]}")
                            continue
                        c['heur_score'] = _frame_score(src)
                    except Exception:
                        c['heur_score'] = 0.5
                    ranked.append(c)
                ranked.sort(key=lambda c: c.get('heur_score', 0.0), reverse=True)
                if focus_star:
                    # Star photos first. Ranking on image quality alone let
                    # other people's sharper photos crowd the star out, the
                    # purity check then dropped the name, and the short
                    # shipped as a generic mixed reel.
                    sl = focus_star.lower(); sn = sl.split()[-1]
                    is_star = lambda c: any(t in ((c.get('filename') or '') + ' ' + (c.get('caption') or '')
                                                  + ' ' + (c.get('category') or '')).lower() for t in (sl, sn))
                    star_c = [c for c in ranked if is_star(c)]
                    if len(star_c) >= int(getattr(config, 'SHORT_MIN_CLIPS', 10)):
                        ranked = star_c
                        print(f"  star-only short: {len(star_c)} {focus_star} frames")
                if len(ranked) >= max(3, keep // 2):
                    clips, spare = ranked[:keep], ranked[keep:]
                    print(f"  heuristic ranking: kept {len(clips)} of {len(ranked)} clean frames")
                else:
                    clips = clips[:keep]
            except Exception as e:
                print(f"  heuristic ranking unavailable ({e})")
                clips = clips[:keep]

        if not history:
            # Lead with the strongest image — the first second decides the swipe.
            # With vision scouting off (the default, for cost) 'portrait' is the
            # free proxy: a tall source is almost always a person rather than a
            # scene still, and it fills a 9:16 frame without heavy cropping.
            clips.sort(key=lambda c: (c.get('vision_score', 5.0),
                                      c.get('heur_score', 0.0),
                                      1 if c.get('portrait') else 0), reverse=True)
            lead, rest = clips[0], clips[1:]
            random.shuffle(rest)
            clips = [lead] + rest

        # A short burns ONE name on screen, so verify the frames really are
        # that person before labelling. A test short labelled a child Elizabeth
        # Taylor wardrobe test "GRETA GARBO" — the kind of error a viewer spots
        # instantly and never trusts again.
        if focus_star:
            star_l = focus_star.lower()
            # Match on category and surname too: curated filenames are often
            # reversed ("Annex - Garbo, Greta ..."), so a plain "greta garbo"
            # filename test under-counts and would drop a correct label.
            surname = star_l.split()[-1]
            def _is_star(c):
                blob = ((c.get('filename') or '') + ' ' + (c.get('caption') or '')
                        + ' ' + (c.get('category') or '')).lower()
                return star_l in blob or surname in blob
            n_star = sum(1 for c in clips if _is_star(c))
            purity = n_star / max(len(clips), 1)
            if purity < 0.9:
                print(f"  star purity only {purity:.0%} ({n_star}/{len(clips)}) — "
                      f"dropping the on-screen name rather than mislabel")
                focus_star = ''
            else:
                print(f"  star purity {purity:.0%} — labelling as {focus_star}")

        kind = 'star' if focus_star else ('theme' if story else 'timeline')
        if history:
            pool_all = clips + spare
            clips = _arrange_history(pool_all, kind, focus_star, story, keep)
            if len(clips) < min_clips and kind != 'timeline':
                # a theme or star that thinned out after download still makes
                # an honest timeline short from the same photos
                print(f"  {kind} short thinned to {len(clips)} photos; arranging as a timeline")
                kind, story, focus_star = 'timeline', None, ''
                clips = _arrange_history(pool_all, kind, '', None, keep)
            if len(clips) < min_clips:
                print(f"Error: only {len(clips)} usable photos after arranging (need {min_clips})")
                return None

        # 5) Render
        print(f"\n[5/6] Rendering {len(clips)} clips ({kind})...")
        hook_n = int(getattr(config, 'SHORT_HOOK_CLIPS', 3))
        hook_d = float(getattr(config, 'SHORT_HOOK_DURATION', 3.0))
        base_d = float(getattr(config, 'SHORT_IMAGE_DURATION', 5.0))
        prompts = list(getattr(config, 'SHORT_END_PROMPTS', ()))
        end_prompt = tuple(random.choice(prompts)) if prompts else ()
        last_i = len(clips) - 1

        # Every clip gets wording that FITS it: who is on screen (and when),
        # an era-matched one-liner or a real quote from that person, a humor
        # hook up front and the comment question at the end.
        if history:
            hook_n, hook_d = 1, float(getattr(config, 'SHORT_HISTORY_HOOK_DURATION', 4.0))
            base_d = float(getattr(config, 'SHORT_HISTORY_IMAGE_DURATION', 4.4))
            if len(clips) > 1:
                # fewer photos than planned: hold each a little longer so the
                # short still runs ~50s (capped: past ~5.4s a still drags)
                base_d = max(base_d, min(5.4, (52.0 - hook_d) / (len(clips) - 1)))
            plan = _plan_history(clips, kind, focus_star, story, last_i)
            end_prompt = plan.get('end_prompt') or end_prompt
        else:
            plan = _plan_wording(clips, focus_star, hook_n, last_i)
        plates, blocks, extra = plan['plates'], plan['blocks'], plan['extra_secs']
        tickers = plan.get('tickers', {})
        print(f"  hook: {plan['hook']!r} | quote: {plan['quote'][0] if plan['quote'] else None!r}"
              f" | captioned: {len(plan.get('captions') or blocks)}/{len(clips)}"
              f" | history lines: {len(plan.get('history_lines') or [])}")

        clip_paths, durations = [], []
        for i, c in enumerate(clips):
            src = c.get('orig') or c.get('path')
            if not src or not os.path.exists(src):
                continue
            frame = os.path.join(temp_dir, f"frame_{i:02d}.jpg")
            if not compose_vertical_frame(src, frame):
                continue
            d = (hook_d if i < hook_n else base_d) + extra.get(i, 0.0)
            out = os.path.join(temp_dir, f"clip_{i:02d}.mp4")
            if _render_clip(frame, out, d, plates.get(i, ''), zoom_in=(i % 2 == 0),
                            prompt=end_prompt if i == last_i else (),
                            block=blocks.get(i), ticker=tickers.get(i, ())):
                clip_paths.append(out)
                durations.append(d)
        if not clip_paths:
            print("Error: no clips rendered")
            return None

        # Stitch with quick crossfades (0.25s keeps the rhythm tight)
        os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)
        out_name = f"{theme}.mp4"
        out_path = os.path.join(config.OUTPUT_FOLDER, out_name)
        xfade = 0.25
        merged = os.path.join(temp_dir, "merged.mp4")
        fc, final_label = _build_xfade_filter(durations, xfade_dur=xfade)
        cmd = [config.FFMPEG_PATH, '-y']
        for p in clip_paths:
            cmd += ['-i', p]
        if len(clip_paths) > 1:
            cmd += ['-filter_complex', fc, '-map', f'[{final_label}]']
        cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                '-pix_fmt', 'yuv420p', merged]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print("  crossfade failed; falling back to plain concat")
            lst = os.path.join(temp_dir, 'list.txt')
            with open(lst, 'w', encoding='utf-8') as f:
                for p in clip_paths:
                    f.write(f"file '{p}'\n")
            subprocess.run([config.FFMPEG_PATH, '-y', '-f', 'concat', '-safe', '0',
                            '-i', lst, '-c', 'copy', merged],
                           capture_output=True, check=True)

        total = sum(durations) - xfade * max(0, len(durations) - 1)
        audio = _build_audio(total, temp_dir)
        if audio:
            subprocess.run([config.FFMPEG_PATH, '-y', '-i', merged, '-i', audio,
                            '-c:v', 'copy', '-c:a', 'aac', '-shortest', out_path],
                           capture_output=True, check=True)
        else:
            shutil.copy(merged, out_path)

        dur = _probe_duration(out_path)
        print(f"  rendered: {os.path.basename(out_path)}  {dur:.1f}s")
        if dur > 59.5:
            print(f"  WARNING: {dur:.1f}s exceeds the 60s Shorts bar")

        # 6) Metadata + packaging
        print("\n[6/6] Metadata...")
        used = [c for c in clips if (c.get('orig') or c.get('path'))]
        idxs = {c.get('index') for c in used}
        in_video = [r for i, r in enumerate(rows) if i in idxs] or rows[:len(used)]
        for r in in_video:
            r['downloaded'] = True
        # Rejected rows too: before this, a deleted Commons file was retried
        # (and failed) in every short of the same run.
        mark_images_used(in_video, column='short_used')
        mark_images_used([r for r in rows if r.get('quality_rejected')])
        if focus_star:
            record_focus_star(focus_star)

        meta_path = os.path.join(config.OUTPUT_FOLDER, out_name.replace('.mp4', '_metadata.json'))
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump({
                'video_file': out_path,
                'theme': theme,
                'is_short': True,
                'focus_star': focus_star,
                'short_kind': kind,
                'theme_key': story['key'] if story else '',
                'years': plan.get('years') or [],
                'eras': plan.get('eras') or [],
                'history_lines': plan.get('history_lines') or [],
                'hook': plan['hook'],
                'quote': list(plan['quote']) if plan['quote'] else None,
                'names': plan['names'],
                'captions': plan.get('captions', {}),
                'wit': plan['wit'],
                'image_count': len(clip_paths),
                'duration_seconds': dur,
                'timeline': [],
                'vision_scores': [c.get('vision_score') for c in used],
                'images': in_video,
                'created': datetime.now().isoformat(),
            }, f, indent=2, ensure_ascii=False)
        print(f"  metadata: {os.path.basename(meta_path)}")
        return meta_path

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _probe_duration(path: str) -> float:
    try:
        r = subprocess.run([config.FFPROBE_PATH, '-v', 'error', '-show_entries',
                            'format=duration', '-of',
                            'default=noprint_wrappers=1:nokey=1', path],
                           capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate one AAP vertical short")
    ap.add_argument('--theme', type=str, default=None)
    args = ap.parse_args()
    mp = generate_short(args.theme)
    print(f"\n{'OK: ' + mp if mp else 'FAILED'}")


# --- packaging picker --------------------------------------------------------
# Remembers recent hooks/quotes so a star who comes round again gets a
# different line, and the generic hooks rotate instead of repeating.
_PACK_LEDGER = os.path.join(config.DATA_FOLDER, 'packaging_recent.json')


def _clip_year(c: dict, name: Optional[str]) -> Optional[int]:
    import star_data as sd
    for field in ('filename', 'caption'):
        m = re.search(r'\b(18[89]\d|19[0-8]\d)\b', str(c.get(field) or ''))
        if m:
            y = int(m.group(1))
            if name and not sd.plausible_year(name, y):
                continue
            return y
    return None


def _smart_quotes(text: str) -> str:
    """Typographer's apostrophes: 'Love Goddess' gets an opening and a closing
    mark instead of two closing ones."""
    text = re.sub(r"(^|[\s(“])'", lambda m: m.group(1) + "‘", text)
    return text.replace("'", "’")


def _plan_wording(clips, focus_star: str, hook_n: int, last_i: int) -> dict:
    """Per-clip on-screen wording for one short.

    plates      {i: "RITA HAYWORTH · 1946"}  who/when, only when certain
    blocks      {i: text block}              hook, era one-liner or quote
    extra_secs  {i: seconds}                 longer hold for a long quote
    """
    import star_data as sd
    try:
        with open(_PACK_LEDGER, encoding='utf-8') as f:
            led = json.load(f)
    except Exception:
        led = {}
    recent_h = led.get('hooks', [])[-6:]
    recent_q = led.get('quotes', [])[-30:]
    recent_w = led.get('wit', [])[-20:]

    who, years, plates = {}, {}, {}
    for i, c in enumerate(clips):
        # A verified star short labels every frame with that star; a mixed
        # reel labels a frame only when its metadata names exactly one star.
        name = focus_star or sd.identify(c.get('filename'), c.get('category'), c.get('caption'))
        who[i] = name
        years[i] = _clip_year(c, name)
        if name:
            plates[i] = name.upper() + (f" \u00b7 {years[i]}" if years[i] else '')

    blocks, extra = {}, {}

    if getattr(config, 'SHORT_CAPTION_STYLE', 'montage') == 'montage':
        # FORMAL MONTAGE (owner, 2026-09-28, from the channel's own 2025 hits):
        # one calm, centred caption per photo -- name, year, a light detail --
        # white with a shadow, no plate, no jokes stacked on top. At most one
        # quote, used as that photo's detail. The caption carries the name,
        # so there is no separate lower-third plate.
        quote = None
        seed = random.randrange(1000)
        for i, c in enumerate(clips):
            name, q = who.get(i), None
            if (quote is None and name and 0 < i < last_i
                    and getattr(config, 'SHORT_QUOTE_CARDS', True)):
                fresh = [x for x in sd.quotes_for(name) if x[0] not in recent_q]
                if fresh and random.random() < 0.7:
                    q = random.choice(fresh)
                    quote = (q[0], q[1], name)
            text = sd.montage_caption(name, years.get(i), c.get('caption') or '',
                                      seed=seed + i, quote=q)
            if not text:
                continue
            blocks[i] = {'text': _smart_quotes(text), 'size': 64, 'min_size': 46,
                         'max_lines': 4, 'plate': False, 'band': (0.58, 0.76)}
            if q:
                extra[i] = max(0.0, min(2.0, len(text) / 14.0 - 4.6))
        led['quotes'] = (led.get('quotes', []) + ([quote[0]] if quote else []))[-100:]
        try:
            with open(_PACK_LEDGER, 'w', encoding='utf-8') as f:
                json.dump(led, f, indent=1, ensure_ascii=False)
        except Exception as e:
            print(f"  packaging ledger not saved: {e}")
        names = list(dict.fromkeys(n for n in who.values() if n))
        return {'plates': {}, 'blocks': blocks, 'extra_secs': extra,
                'hook': '', 'quote': quote, 'names': names, 'wit': [],
                'captions': {i: b['text'] for i, b in blocks.items()}}

    # 1) humor hook over the opening frames (first 2 clips)
    hook = ''
    if getattr(config, 'SHORT_HUMOR_HOOKS', True):
        opts = list(dict.fromkeys(sd.pick_hook(focus_star, k) for k in range(12)))
        hook = random.choice([h for h in opts if h not in recent_h] or opts)
        for i in range(min(2, last_i)):
            blocks[i] = {'text': hook, 'size': 88, 'min_size': 64, 'max_lines': 2}

    # 2) one real quote, on a frame of the person who said it
    quote = None
    if getattr(config, 'SHORT_QUOTE_CARDS', True):
        slots = [i for i in range(hook_n, last_i) if who.get(i) and sd.quotes_for(who[i])]
        random.shuffle(slots)
        slots.sort(key=lambda i: abs(i - last_i // 2))       # prefer mid-short
        for i in slots:
            qs = sd.quotes_for(who[i])
            fresh = [q for q in qs if q[0] not in recent_q]
            if not fresh:
                continue
            qtext, qsrc = random.choice(fresh)
            quote = (qtext, qsrc, who[i])
            blocks[i] = {'text': f"\u201c{qtext}\u201d".replace("'", "\u2019"),
                         'size': 76, 'min_size': 52, 'max_lines': 5,
                         'sub': f"\u2014 {who[i]}, {qsrc}".replace("'", "\u2019")}
            # ~12 characters a second for comfortable reading at this age
            extra[i] = max(0.0, min(3.0, len(qtext) / 12.0 - 4.0))
            break

    # 3) era-fitting one-liners on a few more frames, spaced out
    wit_used = []
    if getattr(config, 'SHORT_WIT_LINES', True):
        free = [i for i in range(hook_n, last_i) if i not in blocks
                and all(abs(i - j) > 1 for j in blocks if j >= hook_n)]
        for i in free[::3][:int(getattr(config, 'SHORT_WIT_PER_SHORT', 3))]:
            opts = [w for w in sd.wit_options(who.get(i), years.get(i))
                    if w not in recent_w and w not in wit_used]
            if not opts:
                continue
            # most fitting first: an era line when the frame's era is known
            line = opts[0] if years.get(i) and random.random() < 0.6 else random.choice(opts)
            wit_used.append(line)
            blocks[i] = {'text': line, 'size': 80, 'min_size': 60, 'max_lines': 2}

    led['hooks'] = (led.get('hooks', []) + ([hook] if hook else []))[-50:]
    led['quotes'] = (led.get('quotes', []) + ([quote[0]] if quote else []))[-100:]
    led['wit'] = (led.get('wit', []) + wit_used)[-60:]
    try:
        with open(_PACK_LEDGER, 'w', encoding='utf-8') as f:
            json.dump(led, f, indent=1, ensure_ascii=False)
    except Exception as e:
        print(f"  packaging ledger not saved: {e}")

    names = list(dict.fromkeys(n for n in who.values() if n))
    return {'plates': plates, 'blocks': blocks, 'extra_secs': extra,
            'hook': hook, 'quote': quote, 'names': names, 'wit': wit_used}


# =============================================================================
# HISTORY LENS (owner, 2026-10)
# =============================================================================
# A short is a small trip through time: a cold open on the strongest face with
# the short's promise, then the photos in chronological order under a gold year
# ticker, with a few "That year, ..." lines placing them in history. Facts come
# from history_data.py (well-documented events only) and star_data.py.
_YEAR_TXT = re.compile(r'\b(18[89]\d|19[0-8]\d)\b')
_JOINER = re.compile(r'\b(and|with)\b|&', re.I)


def _year_in(text: str) -> Optional[int]:
    m = _YEAR_TXT.search(text or '')
    return int(m.group(1)) if m else None


def _load_ledger() -> dict:
    try:
        with open(_PACK_LEDGER, encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_ledger(led: dict):
    try:
        with open(_PACK_LEDGER, 'w', encoding='utf-8') as f:
            json.dump(led, f, indent=1, ensure_ascii=False)
    except Exception as e:
        print(f"  packaging ledger not saved: {e}")


def _theme_row_filter(story: dict):
    """Row-level test for a themed short, from the filename/category alone
    (selection happens before anything is scraped or downloaded)."""
    import star_data as sd
    import history_data as hd

    def ok(r):
        fn, cat = r.get('image_filename') or '', r.get('source_category') or ''
        name = sd.identify(fn, cat)
        y = _year_in(fn + ' ' + cat)
        if name and y and not sd.plausible_year(name, y):
            y = None
        return hd.theme_admits(story, name, y)
    return ok


def _pick_short_theme(reuse: int, need: int) -> Optional[dict]:
    """A theme the curated pool can actually fill today, not one of the last
    few used. None when no theme has `need` rows free (the short then runs
    as a timeline)."""
    import history_data as hd
    from create_slideshow import _read_image_csv, _short_available, _passes_quality
    rows, _ = _read_image_csv(config.GOLDMINE3_CSV)
    rows = [r for r in rows if _short_available(r, reuse) and _passes_quality(r)]
    avail = {t['key']: sum(1 for r in rows if _theme_row_filter(t)(r)) for t in hd.THEMES}
    led = _load_ledger()
    story = hd.pick_theme(avail, need, led.get('themes', []))
    print(f"  theme supply (need {need}): {avail} -> {story['key'] if story else 'none'}")
    if story:
        led['themes'] = (led.get('themes', []) + [story['key']])[-30:]
        _save_ledger(led)
    return story


def _is_solo(c: dict) -> bool:
    """One person in frame, as far as the metadata can tell."""
    import star_data as sd
    fn, cap = c.get('filename') or '', c.get('caption') or ''
    if _JOINER.search(re.sub(r'\.(jpe?g|png|tiff?|webp)$', '', fn, flags=re.I)):
        return False
    if _JOINER.search(cap.split(' in "')[0]):
        return False
    return sd.identify(fn, c.get('category'), cap) is not None or not re.search(
        r'\b(cast|group|crowd|party|scene)\b', (fn + ' ' + cap).lower())


def _arrange_history(pool: List[dict], kind: str, focus_star: str,
                     story: Optional[dict], keep: int) -> List[dict]:
    """Order a short as a walk through time.

    clip 0      the strongest solo leading lady -- the cold open under the
                short's promise (also what a viewer sees first in the feed)
    clips 1..   chronological; a timeline short spreads them across eras
    clip 6      lands on the video's 50% mark, which YouTube uses as the
                Shorts thumbnail: it must be a named, solo, adult leading lady
                too (the 2026-10 audit found Ronald Colman as the thumbnail of
                "Most Beautiful Actresses in Rare Moments")
    """
    import star_data as sd
    import history_data as hd
    seen, cands = set(), []
    for c in pool:
        key = c.get('orig') or c.get('path')
        if not key or key in seen:
            continue
        seen.add(key)
        blob = ' '.join(str(c.get(k) or '') for k in ('filename', 'caption', 'category'))
        if kind == 'star':
            sl = focus_star.lower()
            if sl not in blob.lower() and sl.split()[-1] not in blob.lower():
                continue
            name = focus_star
        else:
            name = sd.identify(c.get('filename'), c.get('category'), c.get('caption'))
        raw = _year_in(str(c.get('date') or '')) or _year_in(blob)
        if sd.is_child_photo(blob + ' ' + str(c.get('date') or ''), name, raw):
            print(f"    skip (childhood photo): {(c.get('filename') or '')[:50]}")
            continue
        year = hd.photo_year(c, name)
        if story and not hd.theme_admits(story, name, year):
            continue
        c['_name'], c['_year'] = name, year
        c['_ay'] = year or hd.approx_year(c, name)
        c['_solo'] = _is_solo(c)
        cands.append(c)
    if not cands:
        return []
    star_male = kind == 'star' and sd.star_gender(focus_star) == 'm'

    def worthy(c):
        if not c['_solo']:
            return False
        if star_male:
            return True
        return bool(c['_name']) and sd.star_gender(c['_name']) == 'f'

    score = lambda c: (c.get('vision_score', 5.0), c.get('heur_score', 0.0))
    cands.sort(key=score, reverse=True)
    lead = next((c for c in cands if worthy(c)), cands[0])
    rest = [c for c in cands if c is not lead]
    if kind != 'star':
        # a timeline or theme is a parade of faces: at most two photos of
        # anyone (a test short drew Mary Pickford four times)
        seen_n: Dict[str, int] = {lead['_name']: 1} if lead['_name'] else {}
        capped = []
        for c in rest:
            if c['_name']:
                seen_n[c['_name']] = seen_n.get(c['_name'], 0) + 1
                if seen_n[c['_name']] > 2:
                    continue
            capped.append(c)
        rest = capped
    n = min(keep - 1, len(rest))
    ykey = lambda c: (c['_ay'] or 3000, -c.get('heur_score', 0.0))

    def pick(group: List[dict], k: int) -> List[dict]:
        if k <= 0:
            return []
        if kind != 'timeline':
            return sorted(group, key=score, reverse=True)[:k]
        # one per era per round, oldest era first, so a 12-photo short
        # covers the decades instead of twelve 1920s stills
        buckets: Dict[str, List[dict]] = {}
        for c in sorted(group, key=score, reverse=True):
            e = hd.era_for(c['_year']) if c['_year'] else None
            buckets.setdefault(e['key'] if e else '~', []).append(c)
        order = [e['key'] for e in hd.ERAS if e['key'] in buckets]
        got: List[dict] = []
        while len(got) < k and any(buckets[x] for x in order):
            for x in order:
                if buckets[x] and len(got) < k:
                    got.append(buckets[x].pop(0))
        return got + buckets.get('~', [])[:k - len(got)]

    # The 50% frame (final index 6) is chosen FIRST, then the timeline is
    # built around it -- earlier photos before, later after -- so the order
    # stays strictly chronological and the thumbnail is still a leading lady.
    pivot = min(5, n - 1)
    cands_p = [c for c in rest if worthy(c)]
    line: List[dict] = []
    if cands_p and pivot >= 0:
        def balance(p):
            b = sum(1 for x in rest if x is not p and ykey(x)[0] <= ykey(p)[0])
            a = len(rest) - 1 - b
            return (min(b, pivot) + min(a, n - 1 - pivot), score(p))
        p = max(cands_p, key=balance)
        others = [x for x in rest if x is not p]
        before = [x for x in others if ykey(x)[0] <= ykey(p)[0]]
        after = [x for x in others if ykey(x)[0] > ykey(p)[0]]
        nb = min(pivot, len(before))
        na = min(n - 1 - nb, len(after))
        nb = min(n - 1 - na, len(before))
        line = sorted(pick(before, nb), key=ykey) + [p] + sorted(pick(after, na), key=ykey)
        pivot = nb
    else:
        line = sorted(pick(rest, n), key=ykey)
    out = [lead] + line
    print("  timeline: " + ' '.join(str(c['_year'] or '?') for c in out[1:])
          + f" | lead: {lead['_name'] or '?'} | 50% frame: "
          + ((out[pivot + 1]['_name'] or '?') if 0 <= pivot < len(line) else '-'))
    return out


def _plan_history(clips: List[dict], kind: str, focus_star: str,
                  story: Optional[dict], last_i: int) -> dict:
    """Wording for a history short: a promise on the cold open, a year ticker
    on every dated photo, and per-photo captions that alternate between who
    (name, year, a light detail), when ("That year, ...") and one line of
    their own dialogue. Same return shape as _plan_wording, plus 'tickers'."""
    import star_data as sd
    import history_data as hd
    led = _load_ledger()
    recent_q = led.get('quotes', [])[-30:]
    recent_ev = led.get('events', [])[-16:]
    W = int(getattr(config, 'SHORT_CAPTION_WIDTH', 840))
    serif = getattr(config, 'SERIF_FONT_FILE', None)

    def block(text, size=60, min_size=44, max_lines=4):
        return {'text': _smart_quotes(text), 'size': size, 'min_size': min_size,
                'max_lines': max_lines, 'plate': False, 'band': (0.60, 0.80),
                'width': W, 'font': serif}

    names = {i: c.get('_name') for i, c in enumerate(clips)}
    years = {i: c.get('_year') for i, c in enumerate(clips)}
    dated = [years[i] for i in range(1, len(clips)) if years[i]]
    y0, y1 = (min(dated), max(dated)) if dated else (None, None)
    blocks, extra, tickers, captions = {}, {}, {}, {}

    # 1) the promise, over the cold open
    if story:
        hook = story['hook']
    elif kind == 'star':
        facts = sd.facts_for(focus_star)
        nick = next((f for f in facts if re.search(r"(?<=\s)'[^']+'", f)
                     and 'hairstyle' not in f), None)
        tag = nick or (facts[0] if facts else '')
        span = f"{focus_star}, {y0} to {y1}" if y0 and y1 and y1 - y0 >= 3 else focus_star
        hook = f"{span}. {tag}." if tag else f"{span}, through the years."
    elif y0 and y1 and y1 - y0 >= 15:
        hook = f"{y0} to {y1}: Hollywood glamour, decade by decade."
    elif y0 and y1:
        hook = f"Hollywood glamour, {y0} to {y1}."
    else:
        hook = "Hollywood glamour, decade by decade."
    blocks[0] = block(hook, size=70, min_size=52, max_lines=3)

    # 2) year ticker on dated photos (never backwards; the last clip's top
    #    bar belongs to the comment question)
    if getattr(config, 'SHORT_TICKER', True):
        prev = 0
        for i in range(1, last_i):
            y = years[i]
            if y and y >= prev:
                e = hd.era_for(y)
                tickers[i] = (str(y), e['tag'] if e else '')
                prev = y

    # 3) "That year, ..." lines: prefer the first photo of each new era,
    #    spaced out, never about the same star the event names
    want = int(getattr(config, 'SHORT_HISTORY_LINES', 3))
    slots, used_ev = [], set()
    def _event_for(i):
        y = years[i]
        if not y:
            return None
        for k in range(3):
            ev = hd.year_event(y, seed=k + i)
            if not ev or ev in used_ev:
                continue
            nm = names[i]
            if nm and nm.split()[-1].lower() in ev.lower():
                continue
            return ev
        return None
    eras = {i: (hd.era_for(years[i]) or {}).get('key') for i in range(len(clips))}
    order = sorted(range(1, last_i + 1),
                   key=lambda i: (0 if eras[i] and eras[i] != eras.get(i - 1) else 1,
                                  1 if (_event_for(i) or '') in recent_ev else 0, i))
    for i in order:
        if len(slots) >= want:
            break
        ev = _event_for(i)
        if ev and all(abs(i - j) > 1 for j, _ in slots):
            slots.append((i, ev))
            used_ev.add(ev)
    hist = dict(slots)

    # 4) one real line of dialogue, from the person on screen
    quote = None
    if getattr(config, 'SHORT_QUOTE_CARDS', True) and random.random() < 0.7:
        qslots = [i for i in range(1, last_i + 1) if names[i] and i not in hist]
        random.shuffle(qslots)
        for i in qslots:
            fresh = [q for q in sd.quotes_for(names[i]) if q[0] not in recent_q]
            if fresh:
                quote = (i,) + tuple(random.choice(fresh))
                break

    # 5) captions. A fact that retells one of the short's "That year" lines
    # ("Co-founded United Artists" next to "...founded United Artists") is
    # skipped: shared capitalised phrases mark the same story.
    ev_phrases = set()
    for _, ev in slots:
        ev_phrases |= set(re.findall(r"[A-Z][\w'-]+(?: [A-Z][\w'-]+)+", ev))
    retells = lambda f: any(ph in f for ph in ev_phrases)
    fact_n: Dict[str, int] = {}
    for i in range(1, len(clips)):
        c, name, y = clips[i], names[i], years[i]
        head = f"{name}, {y}." if name and y else (f"{name}." if name else '')
        if i in hist:
            ev = hist[i]
            text = f"{head} That year, {ev}." if head else f"In {y}, {ev}."
            extra[i] = 0.9
        elif quote and quote[0] == i:
            text = sd.montage_caption(name, y, quote=(quote[1], quote[2]))
            extra[i] = max(0.0, min(1.5, len(text) / 14.0 - 4.4))
        else:
            detail = None
            if name:
                k = fact_n.get(name, 0)
                pool = ([hd.theme_fact(story, name)] if story and hd.theme_fact(story, name)
                        else []) + [f for f in sd.facts_for(name)
                                    if f != (hd.theme_fact(story, name) if story else None)]
                pool = [f for f in pool if not retells(f)]
                if k < len(pool):
                    detail = pool[k]
                fact_n[name] = k + 1
            if detail:
                text = f"{head} {detail.rstrip('.')}."
            elif name:
                film = re.search(r'in "([^"]+)"', c.get('caption') or '')
                text = (f"{name} in {film.group(1)}, {y}." if film and y else head)
            else:
                text = sd.montage_caption(None, None, c.get('caption') or '')
        if text:
            blocks[i] = block(text)
            captions[i] = blocks[i]['text']

    if story:
        end_prompt = tuple(story['prompt'])
    else:
        opts = [tuple(p) for p in getattr(config, 'SHORT_HISTORY_PROMPTS', [])]
        fresh = [p for p in opts if p[0] not in led.get('prompts', [])[-2:]] or opts
        end_prompt = random.choice(fresh) if fresh else ()
    led['quotes'] = (led.get('quotes', []) + ([quote[1]] if quote else []))[-100:]
    led['events'] = (led.get('events', []) + [ev for _, ev in slots])[-60:]
    led['prompts'] = (led.get('prompts', []) + ([end_prompt[0]] if end_prompt else []))[-20:]
    _save_ledger(led)

    who = list(dict.fromkeys(n for n in names.values() if n))
    return {'plates': {}, 'blocks': blocks, 'extra_secs': extra, 'tickers': tickers,
            'hook': hook, 'quote': (quote[1], quote[2], names[quote[0]]) if quote else None,
            'names': who, 'wit': [], 'captions': {i: t for i, t in captions.items()},
            'history_lines': [[years[i], ev] for i, ev in slots],
            'years': [y0, y1] if y0 else [],
            'eras': [e['key'] for e in hd.eras_in(list(years.values()))],
            'end_prompt': end_prompt}
