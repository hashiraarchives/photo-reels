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


def _fit(text: str, max_size: int, min_size: int, max_lines: int):
    """Largest font size (<= max_size) at which `text` wraps into max_lines
    lines of ~960px. Sans glyphs average ~0.55em (DejaVu, the CI font, runs
    wider than Arial, so don't tighten this from a Windows preview)."""
    # First choice: break only at sentence/clause ends, giving up to ~12px of
    # size for it -- a natural break reads faster than a bigger awkward one.
    chunks = [c for c in re.split(r'(?<=[.!?,;])\s+', text) if c]
    if len(chunks) > 1:
        for size in range(max_size, max(min_size, max_size - 12) - 1, -4):
            cap = max(8, int(960 / (0.55 * size)))
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
        cap = max(8, int(960 / (0.55 * size)))
        if len(_wrap(text, cap)) <= max_lines:
            return size, _balanced(text, cap)
    return min_size, _balanced(text, max(8, int(960 / (0.55 * min_size))))


def _textfile(dirpath: str, text: str) -> str:
    fd, p = tempfile.mkstemp(suffix='.txt', dir=dirpath)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(text)
    return p.replace('\\', '/').replace(':', '\\:')


def _block_filter(block: dict, dirpath: str) -> str:
    """drawtext chain for a centred block: main lines (white on a dark plate)
    plus an optional gold subline, vertically centred in the safe band."""
    font = config.CAPTION_FONT_FILE.replace('\\', '/').replace(':', '\\:')
    H = config.SHORT_HEIGHT
    size, lines = _fit(block['text'], block.get('size', 84), block.get('min_size', 56),
                       block.get('max_lines', 4))
    sub = block.get('sub', '')
    ssize, slines = _fit(sub, 56, 44, 2) if sub else (0, [])
    lh, slh = int(size * 1.28), int(ssize * 1.3)
    total = lh * len(lines) + (24 + slh * len(slines) if slines else 0)
    y0 = int(H * (_BAND_TOP + _BAND_BOTTOM) / 2 - total / 2)
    y0 = max(int(H * _BAND_TOP), min(y0, int(H * _BAND_BOTTOM) - total))
    out = ''
    for i, ln in enumerate(lines):
        out += (f",drawtext=fontfile='{font}':textfile='{_textfile(dirpath, ln)}'"
                f":expansion=none:fontcolor=white:fontsize={size}"
                f":borderw={max(5, size // 10)}:bordercolor=black@0.95"
                f":box=1:boxcolor=black@0.5:boxborderw=18"
                f":x=(w-text_w)/2:y={y0 + i * lh}")
    for j, ln in enumerate(slines):
        out += (f",drawtext=fontfile='{font}':textfile='{_textfile(dirpath, ln)}'"
                f":expansion=none:fontcolor=0xFFD66B:fontsize={ssize}"
                f":borderw={max(4, ssize // 10)}:bordercolor=black@0.95"
                f":x=(w-text_w)/2:y={y0 + lh * len(lines) + 24 + j * slh}")
    return out



def _render_clip(frame_path: str, out_path: str, duration: float,
                 label: str, zoom_in: bool, prompt: tuple = (),
                 block: dict = None) -> bool:
    """One Ken Burns clip with the star label burned in. `prompt` (headline,
    subline) adds the end-card comment question in the top third."""
    W, H, FPS = config.SHORT_WIDTH, config.SHORT_HEIGHT, config.FPS
    frames = max(1, int(duration * FPS))
    # Upscale 2x before zoompan: zoompan is famously jittery when it steps
    # across a small source, and the extra pixels keep the motion smooth.
    if getattr(config, 'SHORT_KENBURNS', True):
        if zoom_in:
            z = "min(zoom+0.0009,1.15)"
        else:
            z = "if(lte(zoom,1.0),1.15,max(1.0,zoom-0.0009))"
        motion = (f"scale={W*2}:{H*2},"
                  f"zoompan=z='{z}':d={frames}:x='iw/2-(iw/zoom/2)':"
                  f"y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}")
    else:
        motion = f"scale={W}:{H},fps={FPS}"

    vf = motion
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
        # Bold sans runs ~0.6em per glyph: size to fit ~960px of the 1080 frame.
        hsize = max(56, min(84, int(960 / (0.6 * max(len(head), 1)))))
        ssize = max(44, min(62, int(960 / (0.6 * max(len(sub), 1)))))
        vf += (f",drawtext=fontfile='{font}':text='{_esc(head)}'"
               f":fontcolor=white:fontsize={hsize}:borderw=8:bordercolor=black@0.95"
               f":box=1:boxcolor=black@0.55:boxborderw=24"
               f":x=(w-text_w)/2:y=h*0.52")
        if sub:
            vf += (f",drawtext=fontfile='{font}':text='{_esc(sub)}'"
                   f":fontcolor=0xFFD66B:fontsize={ssize}:borderw=7:bordercolor=black@0.95"
                   f":x=(w-text_w)/2:y=h*0.52+{hsize + 58}")

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
    track = random.choice(tracks)
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
    fade_out_at = max(0.1, total_duration - 1.6)
    cmd = [config.FFMPEG_PATH, '-y'] + loop_args + ['-ss', f'{offset:.2f}', '-i', track,
           '-t', f'{total_duration:.2f}',
           '-af', (f"volume={config.MUSIC_VOLUME},"
                   f"afade=t=in:st=0:d=0.35,"
                   f"afade=t=out:st={fade_out_at:.2f}:d=1.6"),
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
    want_star = random.random() < float(getattr(config, 'SHORT_STAR_RATE', 0.3))
    sel = dict(star_share=1.0, star_min_rows=star_min, reuse_days=reuse,
               for_shorts=True, star_episode=want_star)
    rows = select_unused_images(int(keep * cand), pool_paths=pools, **sel)
    if len(rows) < keep and curated_only:
        print(f"  curated pool only yielded {len(rows)}; widening to all pools")
        rows = select_unused_images(int(keep * cand), **sel)
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
                    clips = ranked[:keep]
                    print(f"  heuristic ranking: kept {len(clips)} of {len(ranked)} clean frames")
                else:
                    clips = clips[:keep]
            except Exception as e:
                print(f"  heuristic ranking unavailable ({e})")
                clips = clips[:keep]

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

        # 5) Render
        print(f"\n[5/6] Rendering {len(clips)} clips...")
        hook_n = int(getattr(config, 'SHORT_HOOK_CLIPS', 3))
        hook_d = float(getattr(config, 'SHORT_HOOK_DURATION', 3.0))
        base_d = float(getattr(config, 'SHORT_IMAGE_DURATION', 5.0))
        prompts = list(getattr(config, 'SHORT_END_PROMPTS', ()))
        end_prompt = tuple(random.choice(prompts)) if prompts else ()
        last_i = len(clips) - 1

        # Every clip gets wording that FITS it: who is on screen (and when),
        # an era-matched one-liner or a real quote from that person, a humor
        # hook up front and the comment question at the end.
        plan = _plan_wording(clips, focus_star, hook_n, last_i)
        plates, blocks, extra = plan['plates'], plan['blocks'], plan['extra_secs']
        print(f"  hook: {plan['hook']!r} | quote: {plan['quote'][0] if plan['quote'] else None!r}"
              f" | named clips: {sum(1 for v in plates.values() if v)}/{len(clips)}")

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
                            block=blocks.get(i)):
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
                'hook': plan['hook'],
                'quote': list(plan['quote']) if plan['quote'] else None,
                'names': plan['names'],
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
