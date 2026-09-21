"""
AAP - Actress Actor and Pinups
Gemini AI Title & Packaging Generator

Uses Google Gemini to generate:
- 3 title options in the new CTR style (emotional/curiosity hook, varied decade,
  names the dominant star when one carries the video, NO forced brand suffix),
  then picks the one whose hook lands in the first ~50 chars.
- A short optional thumbnail word (used only if on-thumbnail text is enabled).
- Niche tags for the video.

Title style modeled on the successful same-niche channels (@yapaknews /
@OldWorldPhotos): curiosity + nostalgia over keyword-stuffing, kept dignified
and advertiser-safe for the 65+ audience.
"""

import os
import sys
import json
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger('AAP-Gemini')

# Matches emoji / pictographs (incl. ⭐ U+2B50 and 🌟 U+1F31F) for normalization.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF️✨]",
    flags=re.UNICODE,
)


def generate_with_gemini(metadata: Dict) -> Optional[Dict]:
    """
    Call Gemini to generate YouTube title options, a thumbnail word, and tags.

    Returns dict with 'title', 'all_titles', 'thumbnail_text', 'text_color',
    'gemini_tags', 'source' — or None if Gemini fails (caller falls back to
    youtube_uploader.build_fallback_title, which follows the same rules).
    """
    try:
        from google import genai
        import config
        from youtube_uploader import (
            extract_top_stars, dominant_star, extract_decade_range, finalize_title,
            _video_seed,
        )
    except ImportError as e:
        logger.error(f"Dependency missing for Gemini generation: {e}")
        return None

    api_key = getattr(config, 'GEMINI_API_KEY', None)
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        return None

    image_count = metadata.get('image_count', len(metadata.get('images', [])))
    decade = extract_decade_range(metadata)
    lead, names = dominant_star(metadata)
    allow_names = getattr(config, 'TITLE_ALLOW_STAR_NAMES', True)
    allow_emoji = getattr(config, 'TITLE_ALLOW_EMOJI', True)

    if lead and allow_names:
        if len(names) >= 3:
            who = f"{names[0]}, {names[1]} & {names[2]}"
        elif len(names) == 2:
            who = f"{names[0]} & {names[1]}"
        else:
            who = names[0]
        subject_line = f"Dominant star(s): {who}."
        star_rule = (
            f"- You MAY lead ONE title with {who} (e.g. \"{who}: Rare Hollywood Photos\"); "
            f"keep the other two GENERIC/collective."
        )
    else:
        subject_line = "Mixed classic Hollywood stars — keep every title GENERIC/collective."
        star_rule = (
            "- Do NOT name a specific person. Use collective subjects: "
            "\"Hollywood Actresses\", \"Old Hollywood Stars\", \"Classic Hollywood Beauties\"."
        )

    emoji_rule = (
        "- You MAY start exactly ONE of the three titles with a single \"⭐ \" "
        "(star emoji) — never more than one emoji, never elsewhere in the title."
        if allow_emoji else
        "- Do NOT use any emoji."
    )

    # Rotate the lead hook family per video (content-seeded) so consecutive
    # days open with structurally different titles — anti-template variation.
    # Five families proved too few: three weeks of daily output re-converged on
    # a handful of openers (one appeared in 5 of 20 uploads), reproducing the
    # near-identical-title pattern that preceded the May collapse. More families
    # PLUS a hard ban on recently-used openings (below) keeps the feed varied.
    hook_families = ["NEVER-MEANT", "CAUGHT-OFF-GUARD", "SURFACED",
                     "PRIVATE-ARCHIVE", "MEMORY", "TIME-ALMOST-LOST",
                     "BEFORE-THEY-WERE-FAMOUS", "WHAT-THE-CAMERA-CAUGHT",
                     "THE-WOMAN-BEHIND", "ONE-NIGHT-ONLY"]
    hook_family = hook_families[_video_seed(metadata) % len(hook_families)]

    # Feed the recent-title ledger back into the prompt as a banned list.
    try:
        from youtube_uploader import load_recent_titles
        recent = load_recent_titles()[-getattr(config, 'TITLE_RECENT_AVOID', 25):]
    except Exception:
        recent = []
    recent_block = ("\n".join(f"  - {t}" for t in recent[-12:])
                    if recent else "  (none yet)")

    # SPECIFIC MATERIAL for the title to anchor on. "Photos from 1901" is
    # generic; "What New York smelled like in 1901" gives a reason to click —
    # and the specifics must be TRUE, so we hand Gemini the real captions
    # (they carry years, film titles, places) instead of letting it invent.
    caption_lines = []
    for img_ in metadata.get('images', [])[:60]:
        cap = (img_.get('generated_caption') or '').strip()
        if cap and len(caption_lines) < 10 and cap not in caption_lines:
            caption_lines.append(cap)
    caption_block = ("\n".join(f"  - {c[:110]}" for c in caption_lines)
                     if caption_lines else "  (none)")

    # STAR EPISODE: most of the video is one person, so the title should say so.
    # A searchable name is what lets the video be found at all; on this channel's
    # own data star-named titles ran +63% median views over generic hooks.
    focus = (metadata.get('focus_star') or '').strip()
    if focus:
        star_directive = (
            f"**STAR EPISODE — this video is mostly {focus}.** Put \"{focus}\" in EVERY title, "
            f"ideally at or near the FRONT (people search the name). Example shapes: "
            f"\"{focus}: Rare Photos You Have Never Seen ({decade})\", "
            f"\"The {focus} Photos the Studios Kept Quiet\", "
            f"\"Remembering {focus} — Rare Portraits ({decade})\". "
            f"Do NOT write a generic 'Old Hollywood stars' title for this video. "
            f"Name ONLY {focus} — do NOT list co-stars or other names alongside them. "
            f"A title like \"{focus}, Someone Else & A Third Star: Rare Photos\" is a FAILURE: "
            f"it splits the search signal and promises a mixed-star video this is not."
        )
    else:
        star_directive = ""

    prompt = f"""**ROLE:** You are the YouTube packaging strategist for "Actress Actor and Pinups", a channel of rare vintage Hollywood glamour & pinup photographs. The audience is mostly US men aged 65+ who love classic-Hollywood nostalgia. Maximize click-through with WARM, DIGNIFIED curiosity — not lurid clickbait.

**THIS VIDEO:** {image_count} rare vintage photos. Decade range: {decade}. {subject_line}
{star_directive}

**TASK:** Return a JSON object with exactly these fields: "titles" (array of 3 strings), "thumbnail_text" (string), "text_color" (string), "gemini_tags" (array of 2-3 strings).

**REAL CAPTIONS FROM THIS VIDEO** (your source of TRUE specifics — years, film titles, places):
{caption_block}

**TITLE RULES (3 titles, each a DIFFERENT angle):**
- THE CURIOSITY-GAP FORMULA: SPECIFICITY x WITHHELD PAYOFF. "Photos from the 1940s" is dead;
  "What Rita Hayworth Looked Like the Year Gilda Made Her Immortal (1946)" gives a reason to click.
  Every title MUST contain at least ONE specific anchor taken from the captions above — an exact year,
  a film title, a place, an age, an event. Never invent facts: if the captions don't support it, don't claim it.
- The GAP: promise a visual payoff the viewer can only get by clicking. Formulas that work:
  * WHAT-SHE-LOOKED-LIKE: "What {{star}} Looked Like Off Camera in {{year}}" / "…Before the Studio Polish"
  * THE-YEAR: "{{star}} in {{year}} — the Year Everything Changed" / "…at the Height of Her Fame"
  * DARING: "{{star}}'s Most Daring Looks of the {{decade}} — Photos That Still Turn Heads"
  * COLLECTORS: "The {{star}} Photos Collectors Hunt For ({{decade}})"
  * OFF-GUARD: "When {{star}} Stopped Posing — Candid Frames From {{year}}"
  * FORBIDDEN (use sparingly): "…the Studio Never Released", "…Never Meant for Public Eyes"
- SEDUCTIVE register, advertiser-safe: "daring", "sultry", "dazzling", "the dress that stopped a set",
  "curves the censors watched" — glamour and allure, never explicit words, never body-part terms.
- Do NOT open a title with the photo count (own data: count-led titles ran median 142 vs 332).
  A count may appear late in the title.
- Include the decade range {decade} or a specific year at the END of at least ONE title.
- 45-75 characters. The hook must land in the first ~50 (that is all mobile shows).
- Today's PRIMARY structural family is "{hook_family}" — use its energy for title 1, then two DIFFERENT
  structures for titles 2 and 3. NEVER produce two titles with the same opening words.

**DO NOT REUSE THESE RECENT TITLES OR THEIR OPENINGS** (this channel published them in the last few weeks;
repeating an opening makes the feed look like one video posted over and over, which has previously
suppressed this channel's reach):
{recent_block}
Every title you return MUST open with a different first-three-words than every line above.
{star_rule}
{emoji_rule}
- Do NOT append the channel name or any "| ..." brand suffix — handled automatically.
- ADVERTISER-SAFE line: allure through glamour, style and period detail — BANNED words: naked, nude,
  sexy, hot, sexually explicit, leaked, "you won't believe", shocking. Do NOT stack adjectives
  ("Breathtaking Timeless Stunning…") — one strong specific beats three weak adjectives.
- Make the three titles STRUCTURALLY different from each other: different opening words, different
  formula, different clause order.

**OTHER FIELDS:**
- "thumbnail_text": ONE or TWO words, ALL CAPS, elegant archive vibe (e.g. "RARE", "UNSEEN", "GOLDEN ERA", "RARE COLLECTION"). Used only if on-thumbnail text is enabled.
- "text_color": "#F4D67A"
- "gemini_tags": 2-3 niche search tags specific to this video's content.

**IMPORTANT:** Respond with ONLY valid JSON. No markdown, no code fences, no commentary."""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=getattr(config, 'GEMINI_MODEL', 'gemini-3.7-flash'),
            contents=prompt,
        )

        text = response.text.strip()
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
        text = text.replace('\r\n', '\\n').replace('\r', '\\n')
        text = re.sub(r'(?<=": ")(.*?)(?="[,\}])', lambda m: m.group(0).replace('\n', '\\n'),
                      text, flags=re.DOTALL)

        result = json.loads(text)

        titles = [t.strip() for t in result.get('titles', []) if isinstance(t, str) and t.strip()]
        if not titles:
            logger.warning("Gemini returned no titles")
            return None

        # Pick the title that best delivers the curiosity gap, THEN fits the CTR
        # window. Length alone is not enough: on 2026-08-04 the length-only scorer
        # picked "Lana Turner, Clark Gable & Audrey Hepburn: Rare Studio Portraits"
        # (64 chars — near-perfect on length, zero gap) over its siblings on a
        # Lana Turner star day. Three names split the search signal, and "Rare
        # Studio Portraits" withholds nothing. Rank on substance first.
        def _score(t: str):
            in_band = 1 if 45 <= len(t) <= 82 else 0

            # A hard specific the viewer can only cash in by clicking. An exact
            # year beats a decade range beats nothing.
            if re.search(r'\b1[89]\d{2}\b', t):
                anchor = 2
            elif re.search(r'\b1[89]\d0s\b', t):
                anchor = 1
            else:
                anchor = 0

            penalty = 0
            # Flat name-list: "A, B & C: ...". Match against KNOWN_STARS rather
            # than a capitalised-bigram regex — title case is normal in a title,
            # so the regex read "the Year She Stopped Posing" as two names and
            # punished a perfectly good gap title.
            low = t.lower()
            listed = sorted({s for s in _known_stars() if s in low}, key=low.index)
            if len(listed) > 1:
                penalty -= 2
            # On a star day, any name that is not the focus star dilutes it.
            if focus:
                others = [n for n in listed if n != focus.lower()]
                penalty -= len(others)
                if focus.lower() not in low[:len(focus) + 14]:
                    penalty -= 1
            # Generic tail with nothing withheld ("...Rare Studio Portraits").
            if re.search(r'(rare|classic|vintage|stunning)\s+(studio\s+|hollywood\s+)?'
                         r'(photos|portraits|pictures|images|photographs)\s*$', t, re.I):
                penalty -= 2

            return (anchor + penalty, in_band, -abs(len(t) - 62))

        # ENFORCE freshness in code — the prompt asks for it, but a model that
        # drifts back to a favourite opener is exactly how this channel ended up
        # with the same title five times in twenty uploads. Prefer candidates
        # whose opening hasn't been used recently; only if ALL three collide do
        # we accept the best-scoring one.
        try:
            from youtube_uploader import is_title_too_similar
            fresh = [t for t in titles if not is_title_too_similar(t)]
        except Exception:
            fresh = titles
        if fresh:
            best_title = max(fresh, key=_score)
        else:
            best_title = max(titles, key=_score)
            logger.warning("All Gemini titles repeated a recent opening; using best-scoring anyway")
        # Normalize emoji: keep at most ONE leading star, strip any stray emoji
        # Gemini may have sprinkled elsewhere; then apply suffix + length cap.
        had_star = best_title.lstrip()[:1] in ('⭐', '🌟')
        best_title = _EMOJI_RE.sub('', best_title).strip()
        best_title = finalize_title(best_title, allow_emoji=allow_emoji,
                                    emoji_on=(allow_emoji and had_star))

        return {
            'title': best_title,
            'all_titles': titles,
            'thumbnail_text': (result.get('thumbnail_text') or "RARE").strip(),
            'text_color': result.get('text_color', '#F4D67A'),
            'gemini_tags': result.get('gemini_tags', []),
            'source': 'gemini',
        }

    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return None


_KNOWN_STARS_CACHE = None


def _known_stars() -> set:
    """Lowercase star names, imported lazily to avoid an import cycle."""
    global _KNOWN_STARS_CACHE
    if _KNOWN_STARS_CACHE is None:
        try:
            from youtube_uploader import KNOWN_STARS
            _KNOWN_STARS_CACHE = set(KNOWN_STARS)
        except Exception:
            _KNOWN_STARS_CACHE = set()
    return _KNOWN_STARS_CACHE


def _extract_names(metadata: Dict) -> list:
    """Extract celebrity names from metadata images, filtering out movie titles."""
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

    sorted_names = sorted(name_counts.items(), key=lambda x: x[1], reverse=True)
    return [name for name, count in sorted_names[:5]]


def _extract_descriptions(metadata: Dict) -> list:
    """Extract image descriptions/captions from metadata."""
    descriptions = []
    for img in metadata.get('images', []):
        caption = img.get('generated_caption', '')
        title = img.get('title', '')
        text = caption or title
        if text and len(text) > 5:
            descriptions.append(text[:100])
    return descriptions[:10]


def test_gemini():
    """Test Gemini with sample metadata."""
    sample_metadata = {
        'theme': 'Classic_Hollywood',
        'image_count': 45,
        'images': [
            {'title': 'Marilyn Monroe portrait 1953',
             'generated_caption': 'Marilyn Monroe in a glamorous studio portrait, 1953'},
            {'title': 'Ava Gardner 1946',
             'generated_caption': 'Ava Gardner in a Paramount studio portrait, 1946'},
            {'title': 'Rita Hayworth 1945',
             'generated_caption': 'Rita Hayworth in a glamour portrait, 1945'},
        ],
    }
    result = generate_with_gemini(sample_metadata)
    if result:
        print("SUCCESS! Gemini returned:")
        print(f"  Title: {result['title'].encode('ascii', 'replace').decode()}")
        print(f"  All titles: {[t.encode('ascii', 'replace').decode() for t in result['all_titles']]}")
        print(f"  Thumbnail text: {result['thumbnail_text']}")
        print(f"  Gemini tags: {result.get('gemini_tags', [])}")
        return True
    print("FAILED: Gemini returned no result")
    return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Gemini AI Title Generator')
    parser.add_argument('--test', action='store_true', help='Test with sample data')
    parser.add_argument('metadata', nargs='?', help='Path to _metadata.json file')
    args = parser.parse_args()

    if args.test:
        sys.exit(0 if test_gemini() else 1)

    if args.metadata:
        with open(args.metadata, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        result = generate_with_gemini(metadata)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Gemini generation failed")
            sys.exit(1)
    else:
        parser.print_help()


# ---------------------------------------------------------------------------
# VISION SCOUTING (2026-08) — let the model LOOK at the photo
# ---------------------------------------------------------------------------
# Every heuristic gate we shipped (filename denylists, print-matter edge veto,
# portrait-aspect checks, leading-lady name matching) still let title cards,
# trailer frames, scene stills, couples and childhood photos onto the channel.
# Measured on real pool images, Gemini vision scored a studio portrait 8, a
# trailer frame 2 and a scene still 3 — the discrimination the heuristics never
# achieved. Failures degrade OPEN (image kept) so a Gemini outage never empties
# a video.
_VISION_PROMPT = """You are curating photos for a vintage-Hollywood glamour YouTube Short aimed at US men 65+.
Rate THIS image 0-10 on how well it would hold a viewer and earn a click.

Score HIGH (8-10): a single glamorous ACTRESS, clear beautiful face, studio-portrait or pin-up quality, striking.
Score MID (4-7): a real photo of a person but weaker - group, male subject, awkward crop, soft focus.
Score LOW (0-3): NOT a usable glamour photo - movie title card, text/poster/advertisement, film scene still,
  crowd, damaged/illegible scan, child, or no clear human subject.

Return ONLY JSON: {"score": <0-10>, "subject": "<who/what, few words>", "is_solo_woman": true/false, "reason": "<8 words max>"}"""


def score_image_with_vision(image_path: str) -> Optional[Dict]:
    """Score ONE image. Returns {'score','subject','is_solo_woman','reason'} or None."""
    try:
        from google import genai
        from google.genai import types
        import config
    except ImportError:
        return None
    api_key = getattr(config, 'GEMINI_API_KEY', None)
    if not api_key:
        return None
    try:
        with open(image_path, 'rb') as f:
            data = f.read()
        if len(data) > 18 * 1024 * 1024:      # keep the request sane
            return None
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=getattr(config, 'GEMINI_MODEL', 'gemini-3.7-flash'),
            contents=[types.Part.from_bytes(data=data, mime_type='image/jpeg'),
                      _VISION_PROMPT])
        txt = (resp.text or '').strip()
        txt = re.sub(r'^```(?:json)?\s*', '', txt)
        txt = re.sub(r'\s*```$', '', txt).strip()
        out = json.loads(txt)
        out['score'] = float(out.get('score', 0))
        return out
    except Exception as e:
        logger.warning(f"Vision scoring failed for {os.path.basename(image_path)}: {e}")
        return None


def scout_images(clips: List[Dict], keep: int, min_score: float = 6.0) -> List[Dict]:
    """
    Score every downloaded clip with vision and return the best `keep`.

    `clips` are the dicts from create_slideshow's download step (they carry
    'orig' = the original photo). Clips that score below `min_score` are
    dropped; if too few survive, the highest scorers are kept anyway so a
    video is never starved. Unscored clips (API failure) get a neutral 5.0 and
    sort below confirmed-good ones without being eliminated.
    """
    scored = []
    for c in clips:
        path = c.get('orig') or c.get('path')
        res = score_image_with_vision(path) if path else None
        c['vision'] = res
        c['vision_score'] = res['score'] if res else 5.0
        scored.append(c)
        if res:
            logger.info(f"  vision {res['score']:.0f}/10  {res.get('subject','?')[:34]}"
                        f"  [{os.path.basename(path)[:34]}]")
    scored.sort(key=lambda c: c['vision_score'], reverse=True)
    good = [c for c in scored if c['vision_score'] >= min_score]
    if len(good) >= keep:
        chosen = good[:keep]
    else:
        chosen = scored[:keep]       # never starve the video
        logger.warning(f"Only {len(good)} images cleared vision score {min_score}; "
                       f"padding to {len(chosen)} with the next best")
    logger.info(f"Vision scout: kept {len(chosen)} of {len(scored)} "
                f"(mean score {sum(c['vision_score'] for c in chosen)/max(len(chosen),1):.1f})")
    return chosen
