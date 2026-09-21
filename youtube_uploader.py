"""
AAP - Actress Actor and Pinups
YouTube Video Uploader

Uploads videos to YouTube using the Data API v3 with OAuth 2.0 authentication.
Generates optimized titles, descriptions, and tags for the 65+ audience.
"""

import os
import random
import sys
import json
import re
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import config

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_OK = True
except ImportError:
    # Degrade instead of killing the process at import. Title/description/chapter
    # generation (and tests) must still work without the upload libs; only the
    # actual upload path needs them, and it checks GOOGLE_LIBS_OK below.
    GOOGLE_LIBS_OK = False
    Credentials = InstalledAppFlow = Request = build = MediaFileUpload = None
    HttpError = Exception


# OAuth 2.0 scopes for YouTube upload
SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube']


def get_authenticated_service():
    """
    Authenticate with YouTube API using OAuth 2.0.
    Returns authenticated YouTube service object.

    On Railway: seeds token from YOUTUBE_TOKEN_JSON env var on first run,
    then uses the volume-persisted token file. Never opens a browser.
    """
    if not GOOGLE_LIBS_OK:
        print("Error: Google API libraries not installed; cannot authenticate or upload.")
        return None

    credentials = None

    # Railway: always write token from env var (ensures latest token is used)
    if config.IS_RAILWAY:
        token_json = os.environ.get('YOUTUBE_TOKEN_JSON')
        if token_json:
            os.makedirs(os.path.dirname(config.YOUTUBE_TOKEN_FILE), exist_ok=True)
            with open(config.YOUTUBE_TOKEN_FILE, 'w') as f:
                f.write(token_json)
        elif not os.path.exists(config.YOUTUBE_TOKEN_FILE):
            print("Error: No YOUTUBE_TOKEN_JSON env var and no token file on volume")
            return None

    # Load existing token if available
    if os.path.exists(config.YOUTUBE_TOKEN_FILE):
        try:
            credentials = Credentials.from_authorized_user_file(
                config.YOUTUBE_TOKEN_FILE, SCOPES
            )
        except Exception as e:
            print(f"Error loading token: {e}")

    # Refresh or get new credentials
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except Exception:
                credentials = None

        if not credentials:
            # On Railway / GitHub Actions there is no browser: run_local_server
            # would wait for one until the job timed out. Bail out instead.
            if config.IS_RAILWAY or getattr(config, 'IS_GITHUB', False):
                print("Error: YouTube token is invalid/missing on Railway and cannot re-authenticate.")
                print("Re-generate the token locally and update the YOUTUBE_TOKEN_JSON env var.")
                return None

            if not os.path.exists(config.YOUTUBE_CREDENTIALS_FILE):
                print(f"Error: {config.YOUTUBE_CREDENTIALS_FILE} not found!")
                print("Please download OAuth credentials from Google Cloud Console.")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                config.YOUTUBE_CREDENTIALS_FILE, SCOPES
            )
            credentials = flow.run_local_server(port=0)

        # Save credentials for next run
        with open(config.YOUTUBE_TOKEN_FILE, 'w') as token:
            token.write(credentials.to_json())

    return build('youtube', 'v3', credentials=credentials)


# Curated set of classic Hollywood stars used to disambiguate person names from
# movie titles and other capitalized phrases when parsing Wikimedia metadata.
KNOWN_STARS = {
    'marilyn monroe', 'audrey hepburn', 'grace kelly', 'elizabeth taylor',
    'rita hayworth', 'ava gardner', 'bette davis', 'joan crawford',
    'ginger rogers', 'katharine hepburn', 'vivien leigh', 'ingrid bergman',
    'sophia loren', 'brigitte bardot', 'lauren bacall', 'gene tierney',
    'veronica lake', 'lana turner', 'dorothy lamour', 'hedy lamarr',
    'clark gable', 'humphrey bogart', 'cary grant', 'james stewart',
    'marlon brando', 'john wayne', 'gregory peck', 'rock hudson',
    'paul newman', 'james dean', 'kirk douglas', 'burt lancaster',
    'errol flynn', 'gary cooper', 'spencer tracy', 'orson welles',
    'dolores rio', 'carole lombard', 'jean harlow', 'mae west',
    'barbara stanwyck', 'claudette colbert', 'irene dunne', 'myrna loy',
    'raquel welch', 'natalie wood', 'jane russell', 'jayne mansfield',
    'rita moreno', 'kim novak', 'doris day', 'shirley temple',
    'judy garland', 'fred astaire', 'gene kelly', 'frank sinatra',
    'dean martin', 'sammy davis', 'tony curtis', 'jack lemmon',
    'steve mcqueen', 'sean connery', 'peter o\'toole', 'richard burton',
    'bettie page', 'teresa wright', 'glenda farrell', 'mary miles minter',
    'bebe daniels', 'boris karloff',
}

# The channel's audience is overwhelmingly men 65+ who came for glamorous
# ACTRESSES. Three weeks of live thumbnails showed ~44% led with a man or a
# couple (Kirk Douglas, Orson Welles, men in suits) — an avoidable click loss.
# Thumbnail subject selection requires a match in this set; the VIDEOS still
# feature everyone in KNOWN_STARS.
LEADING_LADIES = {
    'marilyn monroe', 'audrey hepburn', 'grace kelly', 'elizabeth taylor',
    'rita hayworth', 'ava gardner', 'bette davis', 'joan crawford',
    'ginger rogers', 'katharine hepburn', 'vivien leigh', 'ingrid bergman',
    'sophia loren', 'brigitte bardot', 'lauren bacall', 'gene tierney',
    'veronica lake', 'lana turner', 'dorothy lamour', 'hedy lamarr',
    'dolores rio', 'carole lombard', 'jean harlow', 'mae west',
    'barbara stanwyck', 'claudette colbert', 'irene dunne', 'myrna loy',
    'raquel welch', 'natalie wood', 'jane russell', 'jayne mansfield',
    'rita moreno', 'kim novak', 'doris day', 'judy garland',
    'bettie page', 'teresa wright', 'glenda farrell', 'mary miles minter',
    'bebe daniels', 'greta garbo', 'marlene dietrich', 'louise brooks',
    'clara bow', 'lillian gish', 'mary pickford', 'betty grable',
    'norma shearer', 'gloria swanson', 'olivia de havilland', 'joan fontaine',
    'loretta young', 'paulette goddard', 'ann sheridan', 'susan hayward',
    'esther williams', 'cyd charisse', 'linda darnell', 'jeanne crain',
    'kay francis', 'jean arthur', 'rosalind russell', 'donna reed',
    'deborah kerr', 'janet leigh', 'anne baxter', 'maureen o\'hara',
    'anita ekberg', 'gina lollobrigida', 'debbie reynolds',
    # 'shirley temple' deliberately excluded: her photos in this pool are her
    # child-star era, which is off-brand for a glamour channel (a test short
    # titled itself "Shirley Temple in 1937").
    'constance bennett', 'miriam hopkins', 'sylvia sidney', 'alice faye',
    'betty hutton', 'eleanor powell', 'joan bennett',
}

# Movie titles and other capitalized phrases that the old name-extraction regex
# kept misclassifying as person names — they polluted tags ("ebb tide") and the
# extracted "names_found" list ("The Affairs", "Eyed Jacks", "His Wife").
NON_NAME_PHRASES = {
    'the affairs', 'the man', 'the woman', 'the boy', 'the girl', 'the world',
    'the bride', 'the wife', 'the husband', 'the mother', 'the father',
    'the king', 'the queen', 'the saint', 'the rainmaker', 'the midshipman',
    'the bonded', 'the ordeal', 'the enemy', 'the grasp', 'the amateur',
    'the phantom', 'the little', 'the man who', 'the moth',
    'his wife', 'her husband', 'his life',
    'ebb tide', 'top gun', 'kingofkings',
    'eyed jacks', 'one-eyed jacks', 'man proof', 'foolish wives',
    'becky sharp', 'uncle tom', 'silent film', 'sound film',
    'film still', 'movie still', 'press photo', 'publicity photo',
    'paramount pictures', 'warner bros', 'metro goldwyn',
    'universal pictures', 'columbia pictures', 'rko radio',
    'twentieth century', 'united artists', 'argentinean magazine',
    'film actor', 'film actress', 'new york', 'los angeles',
    'united states', 'motion picture', 'rialto theate',
}


def _looks_like_movie_title(phrase: str) -> bool:
    """True if a capitalized phrase is more likely a movie/place than a person."""
    p = phrase.strip().lower()
    if p in NON_NAME_PHRASES:
        return True
    # Phrases starting with articles/prepositions are almost always titles
    first_word = p.split(' ', 1)[0]
    if first_word in {'the', 'a', 'an', 'of', 'for', 'from', 'in', 'with', 'between'}:
        return True
    return False


def extract_subject_from_metadata(metadata: Dict) -> str:
    """
    Extract the main person/subject from video metadata.

    Strategy: prefer names from KNOWN_STARS (highest confidence). Only fall back
    to regex matches if they pass the movie-title filter — otherwise we end up
    tagging videos with movie names like "Ebb Tide" or "The Affairs", which
    pollute YouTube search relevance.
    """
    star_counts: Dict[str, int] = {}
    candidate_counts: Dict[str, int] = {}

    for image in metadata.get('images', []):
        title = image.get('title', '') or ''
        caption = image.get('generated_caption', '') or ''

        for text in [title, caption]:
            text_lower = text.lower()
            for star in KNOWN_STARS:
                if star in text_lower:
                    proper = ' '.join(w.capitalize() for w in star.split())
                    star_counts[proper] = star_counts.get(proper, 0) + 1

            for match in re.findall(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b', text):
                if not _looks_like_movie_title(match):
                    candidate_counts[match] = candidate_counts.get(match, 0) + 1

    if star_counts:
        return max(star_counts, key=star_counts.get)
    if candidate_counts:
        # Require ≥2 mentions to avoid one-off filename quirks becoming the subject
        repeated = {n: c for n, c in candidate_counts.items() if c >= 2}
        if repeated:
            return max(repeated, key=repeated.get)
    return "Classic Hollywood Stars"


_YEAR_RE = re.compile(r'\b(18[5-9]\d|19[0-8]\d)\b')


def _video_seed(metadata: Dict) -> int:
    """
    A stable integer derived from THIS video's content (theme + file + image set),
    so the two videos generated in the same cron run never collide on the same
    fallback title/description variant (a duplicate-content signal that hurts reach).
    """
    src = (str(metadata.get('theme', '')) + '|' + str(metadata.get('video_file', '')) + '|'
           + '|'.join(sorted((img.get('image_filename') or '')
                             for img in metadata.get('images', [])[:12])))
    return int(hashlib.md5(src.encode('utf-8', 'ignore')).hexdigest(), 16)


def extract_top_stars(metadata: Dict, n: int = 3) -> List[tuple]:
    """Return up to n (ProperName, count) of the most-featured KNOWN_STARS, most first."""
    counts: Dict[str, int] = {}
    for image in metadata.get('images', []):
        text = ((image.get('title') or '') + ' ' + (image.get('generated_caption') or '')).lower()
        for star in KNOWN_STARS:
            if star in text:
                proper = ' '.join(w.capitalize() for w in star.split())
                counts[proper] = counts.get(proper, 0) + 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]


def extract_decade_range(metadata: Dict) -> str:
    """Derive a varied decade label like '(1930s-1960s)' from caption/filename years."""
    years = []
    for image in metadata.get('images', []):
        for field in ('generated_caption', 'title', 'image_filename', 'date'):
            m = _YEAR_RE.search(str(image.get(field) or ''))
            if m:
                years.append(int(m.group(1)))
                break
    if not years:
        return "(1930s-1960s)"
    lo_d, hi_d = (min(years) // 10) * 10, (max(years) // 10) * 10
    return f"({lo_d}s)" if lo_d == hi_d else f"({lo_d}s-{hi_d}s)"


def dominant_star(metadata: Dict):
    """(lead_name or None, [top names]). 'dominant' = lead star fills a real share of the video.

    A star EPISODE states its subject explicitly via metadata['focus_star'];
    trust that first. The old count-based gate required >= 0.22 * image_count
    photos of one star, i.e. 22 photos at IMAGES_PER_VIDEO=100, which random
    selection essentially never produced - so star naming was permanently off.
    """
    focus = (metadata.get('focus_star') or '').strip()
    if focus:
        others = [n for n, _ in extract_top_stars(metadata, n=3) if n != focus]
        return focus, [focus] + others[:2]
    tops = extract_top_stars(metadata, n=3)
    if not tops:
        return None, []
    image_count = metadata.get('image_count', len(metadata.get('images', []))) or 1
    lead, count = tops[0]
    names = [t[0] for t in tops]
    if count >= max(3, int(0.22 * image_count)):
        return lead, names
    return None, names


def _title_key(title: str) -> str:
    """
    Collision key for a title: its opening words, normalised. Two titles with
    the same opening read as the same video in a subscriber's feed.

    Digits are stripped before keying, because the only thing separating
    "From Private Archives: 92 Rare Photos..." from "From Private Archives:
    Classic Hollywood..." is the photo count — to a scrolling viewer those are
    the same title.
    """
    t = re.sub(r'[^a-z ]', ' ', (title or '').lower())   # drops digits too
    t = re.sub(r'^(the|a|an|these|those)\s+', '', t.strip())
    return ' '.join(t.split()[:3])


def load_recent_titles() -> List[str]:
    """Recently published titles (persisted on the Railway volume)."""
    try:
        with open(config.TITLE_RECENT_LEDGER, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def record_title(title: str):
    """Append a title to the recent ledger (best-effort, never fatal)."""
    try:
        ledger = load_recent_titles()
        ledger.append(title)
        path = config.TITLE_RECENT_LEDGER
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(ledger[-200:], f, ensure_ascii=False)
    except Exception as e:
        print(f"  Could not update title ledger: {e}")


def _title_words(title: str) -> List[str]:
    return re.sub(r'[^a-z ]', ' ', (title or '').lower()).split()


def _title_shingles(title: str, n: int = 5) -> set:
    """Contiguous n-word phrases, so we also catch templates that repeat in the
    TAIL rather than the opening (e.g. '...They Never Meant for Public Eyes',
    which appeared with several different openings in the same fortnight)."""
    w = _title_words(title)
    return {' '.join(w[i:i + n]) for i in range(len(w) - n + 1)}


def is_title_too_similar(title: str) -> bool:
    """True if this title reuses a recent title's opening or a distinctive phrase."""
    avoid_n = getattr(config, 'TITLE_RECENT_AVOID', 25)
    recent = load_recent_titles()[-avoid_n:]
    if not recent:
        return False
    key = _title_key(title)
    if key and any(_title_key(t) == key for t in recent):
        return True
    shingles = _title_shingles(title)
    if not shingles:
        return False
    return any(shingles & _title_shingles(t) for t in recent)


def finalize_title(title: str, allow_emoji: bool = False, emoji_on: bool = False) -> str:
    """Apply the optional leading star emoji + conditional brand suffix + hard length cap."""
    title = title.strip()
    suffix = getattr(config, 'TITLE_BRAND_SUFFIX', '')
    budget = getattr(config, 'TITLE_BRAND_SUFFIX_MAXLEN', 70)
    if suffix and 'actress actor and pinups' not in title.lower():
        if len(f"{title} {suffix}") <= budget:
            title = f"{title} {suffix}"
    if allow_emoji and emoji_on and not title[:1] in ('⭐', '\U0001f31f'):
        title = f"⭐ {title}"
    max_len = getattr(config, 'TITLE_MAX_LEN', 90)
    if len(title) > max_len:
        title = title[:max_len - 1].rstrip(' ,.;:-—') + '…'
    return title


def build_fallback_title(metadata: Dict) -> str:
    """
    Fallback title (Gemini-unavailable path). CURIOSITY-HOOK house style — the
    numbered-collection + never-meant-to-be-seen framing proven by the reference
    channels AND this channel's own best months (Mar-Apr 2026). One hook per
    title, varied structure. Names a star only if TITLE_ALLOW_STAR_NAMES is on.
    """
    decade = extract_decade_range(metadata)
    lead, names = dominant_star(metadata)
    allow_names = getattr(config, 'TITLE_ALLOW_STAR_NAMES', False)
    count = metadata.get('image_count', len(metadata.get('images', []))) or \
        getattr(config, 'IMAGES_PER_VIDEO', 100)

    # Generic (no-focus-star) fallbacks. Counts never LEAD (own data: count-led
    # titles ran median 142 vs 332); the decade anchor supplies specificity.
    templates = [
        f"What Hollywood's Most Beautiful Women Looked Like Off Camera {decade}",
        f"The Golden Age Photos Collectors Hunt For {decade}",
        f"When the Studio Cameras Kept Rolling - Candid Frames {decade}",
        f"Hollywood's Most Daring Looks {decade} - Photos That Still Turn Heads",
        f"Caught Off Guard: Unfiltered Photos of Golden Age Stars {decade}",
        f"Hidden for Decades: Rare Old Hollywood Photos {decade}",
        f"The Glamour Shots That Made {decade} Hollywood Unforgettable",
        f"Faces the Studios Made Famous - {count} Rare Photos {decade}",
    ]
    star_templates: List[str] = []
    if lead and allow_names:
        # Star episode: the searchable NAME leads. Generic hooks are the weaker
        # register on this channel's own data (median 233 vs 380). These are
        # tried BEFORE the generic set - simply prepending them was not enough,
        # because the seeded rotation below would skip straight past them.
        star_templates = [
            f"What {names[0]} Looked Like Off Camera {decade}",
            f"{names[0]}'s Most Daring Looks - Photos That Still Turn Heads",
            f"The {names[0]} Photos Collectors Hunt For {decade}",
            f"When {names[0]} Stopped Posing - Candid Frames {decade}",
            f"{names[0]} at the Height of Her Fame {decade}",
            f"The {names[0]} Photos the Studios Kept Quiet",
            f"{names[0]}: The Photos They Never Meant You to See",
        ]
    # Prefer templates that fit cleanly (leave room for the optional emoji),
    # so the title never gets ellipsized mid-phrase.
    seed = _video_seed(metadata)

    def _rotate(pool: List[str]) -> List[str]:
        fit = [t for t in pool if len(t) <= 86] or pool
        return [fit[(seed + i) % len(fit)] for i in range(len(fit))] if fit else []

    # Star titles first (when this is a star episode), generic only as backup.
    ordered = _rotate(star_templates) + _rotate(templates)
    title = next((t for t in ordered if not is_title_too_similar(t)), ordered[0])
    return finalize_title(
        title,
        allow_emoji=getattr(config, 'TITLE_ALLOW_EMOJI', True),
        emoji_on=(seed % 2 == 0),
    )


def generate_title(metadata: Dict) -> str:
    """Fallback title generator (Gemini-unavailable path)."""
    return build_fallback_title(metadata)


def _resolve_star(caption: str) -> Optional[str]:
    """Return the proper-cased KNOWN_STAR named in the caption, else None."""
    cl = (caption or '').lower()
    for star in KNOWN_STARS:
        if star in cl:
            return ' '.join(w.capitalize() for w in star.split())
    return None


def _chapter_label(caption: str) -> Optional[str]:
    """
    Chapter label like 'Ava Gardner (1946)'. Built ONLY from a recognized
    KNOWN_STAR — raw Wikimedia captions otherwise yield garbage labels ('Still',
    film titles, truncated names like 'George' from 'George C. Scott') that erode
    trust with a fact-savvy audience. Returns None when no known star is present,
    so the caller skips that entry rather than shipping a bad chapter.
    """
    star = _resolve_star(caption)
    if not star:
        return None
    ym = _YEAR_RE.search(caption or '')
    return f"{star} ({ym.group(1)})" if ym else star


def build_chapters(metadata: Dict) -> List[str]:
    """
    Build YouTube chapters from the real per-clip timeline recorded by
    create_slideshow (metadata['timeline']). Only emits clean, star-anchored
    chapters (never guesses, never garbage) and never repeats the same star
    back-to-back. YouTube rules: first line 0:00, >=3 chapters, each >=10s
    apart, strictly increasing. Returns [] if fewer than ~3 clean chapters.
    """
    if not getattr(config, 'ENABLE_CHAPTERS', True):
        return []
    timeline = metadata.get('timeline') or []
    if not timeline:
        return []
    MIN_GAP = 25  # seconds between chapters
    chosen = []
    last = -999
    for entry in timeline:
        start = int(entry.get('start', 0))
        if start < last + MIN_GAP:
            continue
        label = _chapter_label(entry.get('caption'))
        if not label:
            continue
        if chosen and chosen[-1][1].split(' (')[0] == label.split(' (')[0]:
            continue  # don't list the same star twice in a row
        chosen.append((start, label))
        last = start
        if len(chosen) >= 12:
            break
    if len(chosen) < 2:
        return []
    lines = []
    if chosen[0][0] > 0:
        lines.append("0:00 Introduction")
    for start, label in chosen:
        lines.append(f"{start // 60}:{start % 60:02d} {label}")
    return lines if len(lines) >= 3 else []


# Owner-provided evergreen channel block (replaces the old boilerplate + the
# Wikimedia attribution line). Used verbatim as the description footer.
CHANNEL_EVERGREEN = """🎬 Welcome to Actress, Actor, and Pinups
Step into the golden age of Hollywood — where glamour, mystery, and timeless beauty defined an era.

Travel back in time through a stunning archive of vintage actresses, legendary actors, and iconic pinup stars, captured in rare high-quality photos from the 1900s to the 1970s. From the silent film era to the golden age of cinema, we bring forgotten legends and classic icons back to life — in both original black-and-white and beautifully colorized photo restorations.

✨ What You'll Discover on This Channel:
📸 Rare portraits and candid behind-the-scenes photos
🎞️ Colorized classics of Hollywood's golden generation
📸 Iconic pinup photography from the 1940s–1960s
🎞️ Forgotten stars and the fascinating stories behind them
📸 Curated slideshows and reels set to nostalgic soundtracks

Whether you're a fan of Old Hollywood glamour, a lover of retro photography, or drawn to the nostalgia of vintage beauty, this channel is your personal time machine to the most elegant decades in film history.

💫 Subscribe for Daily Vintage Content Featuring:
👑 Marilyn Monroe • Audrey Hepburn • Grace Kelly • James Dean
👑 Brigitte Bardot • Bettie Page • Elizabeth Taylor • Cary Grant
👑 Rita Hayworth • Sophia Loren • Jane Russell • and many more

📸 New videos every day | Curated with passion | 100% Authentic Vintage Vibes
🔗 Explore the archive: https://www.youtube.com/@actressactorandpinups

#OldHollywood #VintageActresses #PinupGirls #ClassicCinema #RetroPhotography #ColorizedPhotos #HollywoodHistory #FilmIcons #MarilynMonroe #TimelessBeauty #VintageVibes #GoldenAgeOfHollywood #Actress #Actor #Pinups"""


def build_description(metadata: Dict, title: str = "") -> str:
    """
    Description in the style of the reference channels (pulled live 2026-08):
    a warm personal hook, then emoji-headed SEO paragraphs where the keywords
    (rare photos, vintage photographs, classic Hollywood, golden age glamour,
    historic, cinematic) are woven into NATURAL prose — not a keyword list.
    NO timestamps (owner request). Evergreen channel block as the footer.
    Sections rotate on the video seed so no two descriptions read identical.
    """
    stars = extract_top_stars(metadata, n=3)
    decade = extract_decade_range(metadata)
    image_count = metadata.get('image_count', len(metadata.get('images', [])))
    focus = (metadata.get('focus_star') or '').strip()
    seed = _video_seed(metadata)

    names = ', '.join(n for n, _ in stars) if stars else "classic Hollywood's most beautiful stars"
    lead_name = focus or (stars[0][0] if stars else "Old Hollywood")

    # — Hook: personal, nostalgic, restates the promise (first lines = search snippet)
    hooks = [
        (f"There's something about these old photographs that stops you mid-scroll — "
         f"the gowns, the lighting, the way {lead_name} could hold a room with one glance. "
         f"This collection of rare vintage photos {decade} is one of those finds."),
        (f"Some photographs don't age — they ripen. These {image_count} rare vintage "
         f"photographs of {names} {decade} carry the glamour, the mystery and the "
         f"quiet confidence of Hollywood's golden age."),
        (f"Step back into a world of studio lights and satin gowns. {lead_name} and the "
         f"legends of the golden age, captured in {image_count} rare photos most fans "
         f"have never seen — restored and presented in cinematic quality."),
    ]

    # — Emoji-headed SEO sections (competitor pattern), rotated for variety
    sec_glamour = [
        ("✨ Golden Age Glamour, Frame by Frame\n"
         f"Studio portraits, publicity stills and candid moments of {names} — "
         "authentic vintage photography from the era when Hollywood invented glamour. "
         "Every gown, every wave of hair, every perfectly lit close-up is a piece of "
         "cinematic history."),
        ("✨ The Faces That Defined an Era\n"
         f"From silent-screen beauties to Technicolor icons, these classic Hollywood "
         f"photographs celebrate {names} at the height of their fame — rare glamour "
         "photos, timeless beauty, and the unmistakable style of old Hollywood."),
    ][seed % 2]
    sec_rare = [
        ("📸 Rare & Historic Photographs\n"
         f"Drawn from archives, studio collections and private albums, these rare "
         f"historical photos {decade} preserve moments the public rarely saw — "
         "unseen portraits, behind-the-scenes frames, and vintage images restored "
         "with care for today's screens."),
        ("📸 Preserved From the Archives\n"
         f"Each of these {image_count} vintage photographs was chosen for its rarity "
         "and beauty — authentic archival photography documenting the golden age of "
         "cinema, the stars, the fashion and the atmosphere of a vanished Hollywood."),
    ][(seed // 2) % 2]
    sec_nostalgia = (
        "🎬 A Nostalgic Journey Through Classic Cinema\n"
        "Sit back, relax and let the music carry you through decades of movie history — "
        "old Hollywood nostalgia, retro photography and the timeless elegance of the "
        "silver screen, in one cinematic slideshow."
    )

    # A question right under the hook (still above the "...more" fold) turns a
    # passive viewer into a commenter; comments are the strongest signal a
    # small channel can earn.
    question = "💬 " + build_first_comment(focus, seed=seed)

    parts = [
        hooks[seed % 3], "",
        question, "",
        sec_glamour, "",
        sec_rare, "",
        sec_nostalgia, "",
        "━━━━━━━━━━━━━━━━━━━━━━", "",
        CHANNEL_EVERGREEN,
    ]
    return "\n".join(parts)


def generate_tags(metadata: Dict, gemini_tags: List[str] = None) -> List[str]:
    """
    Generate tags for the video.

    Uses the proven core tags from tags.md (~90%) plus a few contextual
    Gemini-suggested tags (~10%) for variety.
    """
    # Owner-confirmed best-performing tag set (these are doing well). Brand first,
    # then the high-value vintage/old-photo terms, rarity + curiosity angles last.
    # Trimmed to YouTube's 500-char limit (chars + 2 per multi-word tag for quotes + commas).
    # Distinctive / curiosity / rarity tags first so they survive the 500-char trim;
    # near-duplicate generic terms last (those drop first if budget is tight).
    core_tags = [
        "actress actor and pinups",
        "rare photos", "rare vintage photos", "unseen photos",
        "glamour photos", "vintage beauty", "vintage actresses",
        "old hollywood", "vintage hollywood", "classic hollywood", "hollywood golden age",
        "golden age", "classic cinema", "black and white photography", "retro photography",
        "historical photos", "nostalgia", "vintage photos", "old photos",
        "old vintage photos", "vintage photo", "vintage images",
        "old photographs", "old photos from the past",
    ]

    # PER-VIDEO SIGNAL. Previously ~26 of 29 tags were byte-identical across all
    # 1,096 uploads, so tags told YouTube nothing about any individual video.
    # A star episode front-loads that star's name variants, which is the only
    # part of the tag set that actually differs video to video.
    focus = (metadata.get('focus_star') or '').strip()
    if focus:
        f = focus.lower()
        last = f.split()[-1]
        for t in (f"{f} rare photos", f"{f} photos", last, f):
            if t not in core_tags:
                core_tags.insert(0, t)

    # Add subject name at the front if found
    subject = extract_subject_from_metadata(metadata)
    if subject and subject != "Classic Hollywood Stars":
        core_tags.insert(0, subject.lower())

    # Stamp the A/B arm (Phase B) near the front so it survives the 500-char trim —
    # lets the owner tell variant vs control videos apart in YouTube Studio.
    arm = getattr(config, 'AB_ARM', None)
    if arm:
        core_tags.insert(0, f"exp_phaseb_{arm}")

    # De-duplicate, preserving order (the focus star can arrive via two paths).
    _seen = set()
    core_tags = [t for t in core_tags if not (t in _seen or _seen.add(t))]

    # Mix in Gemini-suggested contextual tags for variety
    if gemini_tags:
        for tag in gemini_tags[:3]:
            tag_clean = tag.lower().strip().lstrip('#')
            if tag_clean and tag_clean not in core_tags:
                core_tags.append(tag_clean)

    # YouTube tag limit: 500 chars total.
    # Multi-word tags get +2 for quotes, plus 1 comma between each tag.
    def _yt_char_count(tags):
        total = 0
        for t in tags:
            total += len(t)
            if ' ' in t:
                total += 2  # YouTube wraps multi-word tags in quotes
        total += max(0, len(tags) - 1)  # commas between tags
        return total

    final_tags = []
    for tag in core_tags:
        candidate = final_tags + [tag]
        if _yt_char_count(candidate) > 495:
            break
        final_tags.append(tag)

    return final_tags


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    category_id: str = config.DEFAULT_CATEGORY_ID,
    privacy: str = config.DEFAULT_PRIVACY,
    schedule_time: Optional[datetime] = None,
    thumbnail_path: Optional[str] = None,
    star: str = '',
    is_short: bool = False,
) -> Optional[str]:
    """
    Upload a video to YouTube.

    Args:
        video_path: Path to the MP4 file
        title: Video title
        description: Video description
        tags: List of tags
        category_id: YouTube category ID (24 = Entertainment)
        privacy: "public", "private", or "unlisted"
        schedule_time: Optional UTC datetime to schedule publish (forces private)
        thumbnail_path: Optional path to thumbnail image

    Returns:
        Video ID if successful, None otherwise
    """
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return None

    youtube = get_authenticated_service()
    if not youtube:
        return None

    # If scheduling, force privacy to private
    effective_privacy = privacy
    if schedule_time:
        effective_privacy = 'private'

    # Prepare video metadata
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category_id,
        },
        'status': {
            'privacyStatus': effective_privacy,
            'selfDeclaredMadeForKids': False,
        }
    }

    # Set scheduled publish time (must be UTC ISO 8601)
    if schedule_time:
        publish_str = schedule_time.strftime('%Y-%m-%dT%H:%M:%S.0Z')
        body['status']['publishAt'] = publish_str
        print(f"Scheduled publish: {publish_str}")

    # Create media upload
    media = MediaFileUpload(
        video_path,
        mimetype='video/mp4',
        resumable=True,
        chunksize=1024*1024  # 1MB chunks
    )

    try:
        print(f"Uploading: {title.encode('ascii', 'replace').decode()}")
        print(f"File: {video_path}")
        print(f"Privacy: {effective_privacy}")
        print(f"Tags ({len(tags)}): {sum(len(t) for t in tags)} chars = {tags}")

        # Execute upload
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  Upload progress: {int(status.progress() * 100)}%")

        video_id = response['id']
        print(f"\nUpload successful!")
        print(f"Video ID: {video_id}")
        print(f"URL: https://www.youtube.com/watch?v={video_id}")

        # Record the published title so tomorrow's generator won't reuse its
        # opening. Only recorded on a SUCCESSFUL upload, so a failed run never
        # burns a title.
        record_title(title)

        # Upload thumbnail if provided
        if thumbnail_path and os.path.exists(thumbnail_path):
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
                ).execute()
                print(f"Thumbnail uploaded: {thumbnail_path}")
            except HttpError as e:
                print(f"Warning: Thumbnail upload failed: {e}")

        # Add to "Actress Actor and Pinups" playlist
        add_to_playlist(youtube, video_id, config.AAP_PLAYLIST_ID)

        # Binge paths + a conversation starter. Best-effort by construction:
        # the video is already up, so nothing here may turn it into a failure.
        try:
            engage_after_upload(youtube, video_id, star=star, is_short=is_short)
        except Exception as e:
            print(f"Engagement step skipped: {type(e).__name__}: {e}")

        return video_id

    except HttpError as e:
        print(f"YouTube API error: {e}")
        return None
    except Exception as e:
        print(f"Upload error: {e}")
        return None


def upload_from_metadata(metadata_path: str, privacy: str = None,
                         schedule_time: Optional[datetime] = None) -> Optional[str]:
    """
    Upload a video using its metadata JSON file.
    Uses Gemini-generated title/description from _youtube.json if available.

    Args:
        metadata_path: Path to the _metadata.json file
        privacy: Override privacy setting
        schedule_time: Optional UTC datetime for scheduled publishing

    Returns:
        Video ID if successful
    """
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    video_path = metadata.get('video_file')
    if not video_path or not os.path.exists(video_path):
        print(f"Error: Video file not found in metadata")
        return None

    # Check for Gemini-generated YouTube assets
    youtube_json_path = metadata_path.replace('_metadata.json', '_youtube.json')
    thumbnail_path = None

    gemini_tags = None
    if os.path.exists(youtube_json_path):
        with open(youtube_json_path, 'r', encoding='utf-8') as f:
            youtube_data = json.load(f)
        title = youtube_data.get('title') or generate_title(metadata)
        thumbnail_path = youtube_data.get('thumbnail_path')
        gemini_tags = youtube_data.get('gemini_tags')
        source = youtube_data.get('source', 'unknown')
        source_label = 'Gemini' if source == 'gemini' else f'fallback template ({source})'
        print(f"Title source: {source_label} — {title.encode('ascii', 'replace').decode()}")
    else:
        title = generate_title(metadata)

    # Per-video description: unique first lines + accurate chapters + hashtags
    description = build_description(metadata, title)

    tags = generate_tags(metadata, gemini_tags=gemini_tags)

    return upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        privacy=privacy or config.DEFAULT_PRIVACY,
        schedule_time=schedule_time,
        thumbnail_path=thumbnail_path,
        star=(metadata.get('focus_star') or '').strip()
    )


def add_to_playlist(youtube, video_id: str, playlist_id: str) -> bool:
    """Add a video to a playlist."""
    try:
        youtube.playlistItems().insert(
            part='snippet',
            body={
                'snippet': {
                    'playlistId': playlist_id,
                    'resourceId': {
                        'kind': 'youtube#video',
                        'videoId': video_id
                    }
                }
            }
        ).execute()
        print(f"Added to playlist: {playlist_id}")
        return True
    except HttpError as e:
        print(f"Error adding to playlist: {e}")
        return False


# ---------------------------------------------------------------------------
# ENGAGEMENT (2026-09 revival): per-star playlists + a warm first comment
# ---------------------------------------------------------------------------
# Playlist IDs are cached in seed_data/ (committed back by the workflow) so a
# lookup costs nothing; on a cache miss we search the channel's own playlists
# before creating one, so a lost cache can never spawn duplicates.
_PLAYLIST_CACHE = os.path.join(config.DATA_FOLDER, 'playlists.json')
SHORTS_PLAYLIST_TITLE = "Old Hollywood in 60 Seconds"
_COMMENT_SCOPE_MISSING = False      # set once per run on a 403, then skipped


def _load_playlist_cache() -> Dict[str, str]:
    try:
        with open(_PLAYLIST_CACHE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_playlist_cache(cache: Dict[str, str]):
    try:
        with open(_PLAYLIST_CACHE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=1, sort_keys=True)
    except Exception as e:
        print(f"Playlist cache not saved: {e}")


def ensure_playlist(youtube, title: str, description: str) -> Optional[str]:
    """Return the ID of the channel's playlist called `title`, creating it
    (public) if it does not exist."""
    cache = _load_playlist_cache()
    if title in cache:
        return cache[title]
    try:
        token = None
        while True:
            resp = youtube.playlists().list(part='snippet', mine=True,
                                            maxResults=50, pageToken=token).execute()
            for pl in resp.get('items', []):
                cache.setdefault(pl['snippet']['title'], pl['id'])
            token = resp.get('nextPageToken')
            if not token:
                break
        if title not in cache:
            pl = youtube.playlists().insert(part='snippet,status', body={
                'snippet': {'title': title[:150], 'description': description[:4900]},
                'status': {'privacyStatus': 'public'},
            }).execute()
            cache[title] = pl['id']
            print(f"Created playlist: {title}")
        _save_playlist_cache(cache)
        return cache[title]
    except HttpError as e:
        print(f"Playlist lookup/create failed: {e}")
        return None


def _star_playlist_title(star: str) -> str:
    return f"{star} - Rare Vintage Photos"


_COMMENT_QUESTIONS_STAR = [
    "Which {star} film is your favorite? We read every comment.",
    "Did you ever see {star} on the big screen - at a matinee, a drive-in, or on the late show? Tell us about it.",
    "{star} or someone else - who was the most beautiful star of the golden age? Make your case below.",
    "What is the first thing you think of when you hear the name {star}?",
]
_COMMENT_QUESTIONS_ANY = [
    "What was the first movie you ever saw in a theater - and who took you?",
    "Which star should we feature next? Drop a name and we will dig through the archives.",
    "Who was YOUR Hollywood crush growing up? No wrong answers here.",
    "They really don't make them like this anymore. Which classic film would you watch again tonight?",
]


def build_first_comment(star: str, seed: int = 0) -> str:
    rng = random.Random(seed or None)
    if star and rng.random() < 0.6:
        return rng.choice(_COMMENT_QUESTIONS_STAR).format(star=star)
    return rng.choice(_COMMENT_QUESTIONS_ANY)


def post_first_comment(youtube, video_id: str, text: str) -> bool:
    """Post the channel's own opening comment. Needs youtube.force-ssl; if the
    token lacks it we learn that from the first 403 and stop trying."""
    global _COMMENT_SCOPE_MISSING
    if _COMMENT_SCOPE_MISSING or not getattr(config, 'AUTO_FIRST_COMMENT', True):
        return False
    try:
        youtube.commentThreads().insert(part='snippet', body={'snippet': {
            'videoId': video_id,
            'topLevelComment': {'snippet': {'textOriginal': text}},
        }}).execute()
        print(f"First comment posted: {text}")
        return True
    except HttpError as e:
        if getattr(e, 'resp', None) is not None and e.resp.status == 403:
            _COMMENT_SCOPE_MISSING = True
            print("First comment skipped: token lacks youtube.force-ssl scope "
                  "(re-authorise once to enable). Not retrying this run.")
        else:
            print(f"First comment failed: {e}")
        return False


def engage_after_upload(youtube, video_id: str, star: str = '', is_short: bool = False):
    if getattr(config, 'AUTO_PLAYLISTS', True):
        if star:
            pid = ensure_playlist(
                youtube, _star_playlist_title(star),
                f"Rare, restored photographs of {star} from Hollywood's golden age. "
                f"New additions every week.")
            if pid:
                add_to_playlist(youtube, video_id, pid)
        if is_short:
            pid = ensure_playlist(
                youtube, SHORTS_PLAYLIST_TITLE,
                "One quiet minute of classic Hollywood glamour at a time. "
                "Rare vintage photographs of the golden age's greatest stars.")
            if pid:
                add_to_playlist(youtube, video_id, pid)
    post_first_comment(youtube, video_id,
                       build_first_comment(star, seed=sum(map(ord, video_id))))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='AAP YouTube Uploader')
    parser.add_argument('video', nargs='?', help='Path to video file or metadata JSON')
    parser.add_argument('--title', type=str, help='Custom title')
    parser.add_argument('--privacy', type=str, choices=['public', 'private', 'unlisted'],
                        default=config.DEFAULT_PRIVACY, help='Privacy setting')
    parser.add_argument('--test', action='store_true', help='Test mode: upload as unlisted')
    parser.add_argument('--auth-only', action='store_true', help='Only authenticate, do not upload')

    args = parser.parse_args()

    if args.auth_only:
        print("Authenticating with YouTube...")
        youtube = get_authenticated_service()
        if youtube:
            print("Authentication successful!")
            # Test by getting channel info
            try:
                response = youtube.channels().list(part='snippet', mine=True).execute()
                if response['items']:
                    channel = response['items'][0]['snippet']
                    print(f"Logged in as: {channel['title']}")
            except Exception as e:
                print(f"Could not get channel info: {e}")
        else:
            print("Authentication failed!")
        sys.exit(0)

    if not args.video:
        # Find most recent video in output folder
        import glob
        videos = glob.glob(os.path.join(config.OUTPUT_FOLDER, "*.mp4"))
        if videos:
            args.video = max(videos, key=os.path.getctime)
            print(f"Using most recent video: {args.video}")
        else:
            print("No video specified and none found in output folder.")
            parser.print_help()
            sys.exit(1)

    privacy = 'unlisted' if args.test else args.privacy

    # Check if it's a metadata file or video file
    if args.video.endswith('_metadata.json'):
        video_id = upload_from_metadata(args.video, privacy=privacy)
    else:
        # Try to find corresponding metadata
        metadata_path = args.video.replace('.mp4', '_metadata.json')
        if os.path.exists(metadata_path):
            video_id = upload_from_metadata(metadata_path, privacy=privacy)
        else:
            # Upload with default metadata
            title = args.title or f"Classic Hollywood - {datetime.now().strftime('%Y-%m-%d')}"
            description = "Vintage Hollywood photographs from the Golden Age of Cinema."
            tags = generate_tags({})

            video_id = upload_video(
                video_path=args.video,
                title=title,
                description=description,
                tags=tags,
                privacy=privacy
            )

    if video_id:
        print(f"\nSuccess! Video uploaded: https://www.youtube.com/watch?v={video_id}")
    else:
        print("\nUpload failed.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# SHORTS packaging (2026-08) — different rules from long-form
# ---------------------------------------------------------------------------
# A Short is consumed in a scroll: the title is read in under a second, often
# after the video already started playing. So it is SHORT, leads with the
# searchable name, and carries #Shorts so YouTube shelves it correctly.
_SHORT_HOOKS = [
    "{star} in {year}",
    "{star} — the photo they kept quiet",
    "{star} at the absolute peak",
    "Remember {star}? (rare photos)",
    "They don't make stars like {star} anymore",
    "{star} - pure old Hollywood class",
    "If you remember {star}, watch this",
    "{star}, before the studio polish",
    "Nobody talks about this {star} photo",
    "{star} stopped the room",
    "What {star} really looked like",
    "{star}: {year}, unretouched",
]
_SHORT_GENERIC = [
    "Old Hollywood glamour you've never seen",
    "The Golden Age looked like this",
    "Hollywood's most beautiful faces",
    "Rare glamour from the Golden Age",
]


def build_short_title(metadata: Dict) -> str:
    """Punchy vertical-format title. <= ~70 chars including the tag."""
    star = (metadata.get('focus_star') or '').strip()
    if not star:
        tops = extract_top_stars(metadata, n=1)
        star = tops[0][0] if tops else ''
    decade = extract_decade_range(metadata).strip('()')
    year = ''
    for img in metadata.get('images', []):
        m = _YEAR_RE.search(str(img.get('generated_caption') or ''))
        if m:
            year = m.group(1)
            break
    seed = _video_seed(metadata)

    if star:
        pool = [h for h in _SHORT_HOOKS if '{year}' not in h or year]
        ordered = [pool[(seed + i) % len(pool)] for i in range(len(pool))]
        for tmpl in ordered:
            cand = tmpl.format(star=star, year=year or decade)
            if not is_title_too_similar(cand):
                break
        else:
            cand = ordered[0].format(star=star, year=year or decade)
    else:
        pool = _SHORT_GENERIC
        cand = pool[seed % len(pool)]

    title = f"{cand} #Shorts"
    return title[:99]


def build_short_description(metadata: Dict) -> str:
    """Compact, keyword-rich description with the hashtags Shorts rely on."""
    star = (metadata.get('focus_star') or '').strip()
    decade = extract_decade_range(metadata)
    who = star or "classic Hollywood's most beautiful stars"
    tag_star = ('#' + star.replace(' ', '').replace("'", '')) if star else ''
    question = build_first_comment(star, seed=_video_seed(metadata))
    lines = [
        f"✨ Rare vintage photographs of {who} {decade} — restored glamour from "
        f"the golden age of Hollywood.",
        "",
        f"💬 {question}",
        "",
        "🎞️ A quiet minute of old Hollywood for everyone who still loves the "
        "classics. New rare photos every day — subscribe so you never miss one.",
        "",
        f"#Shorts #OldHollywood #VintagePhotos #ClassicHollywood #GoldenAge "
        f"#Glamour #RarePhotos #Nostalgia {tag_star}".strip(),
    ]
    return "\n".join(lines)


def generate_short_tags(metadata: Dict) -> List[str]:
    """Tag set for a short: star names first, then the evergreen niche terms."""
    tags = []
    star = (metadata.get('focus_star') or '').strip().lower()
    if star:
        tags += [star, f"{star} photos", star.split()[-1]]
    tags += ["shorts", "old hollywood", "vintage photos", "classic hollywood",
             "golden age", "glamour photos", "vintage actresses",
             "rare photos", "nostalgia", "black and white photography",
             "actress actor and pinups"]
    seen = set()
    return [t for t in tags if not (t in seen or seen.add(t))]
