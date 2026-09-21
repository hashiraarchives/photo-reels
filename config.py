"""
AAP - Actress Actor and Pinups
Centralized Configuration Settings

Auto-detects Railway vs local Windows environment.
"""

import os

# === ENVIRONMENT DETECTION ===
IS_RAILWAY = os.environ.get('RAILWAY_ENVIRONMENT') is not None
# 2026-08: the pipeline runs on GITHUB ACTIONS now. Actions has no persistent
# volume, so mutable state (the goldmine CSVs' used-marks, the title/star
# ledgers) lives in the REPO and is committed back at the end of each run.
IS_GITHUB = os.environ.get('GITHUB_ACTIONS') == 'true'
_REPO = os.path.dirname(os.path.abspath(__file__))

# === PATHS ===
if IS_GITHUB:
    DATA_FOLDER = os.path.join(_REPO, "seed_data")
    ASSETS_FOLDER = os.path.join(_REPO, "assets")
    OUTPUT_FOLDER = os.path.join(_REPO, "output")
elif IS_RAILWAY:
    DATA_FOLDER = "/data"
    ASSETS_FOLDER = "/app/assets"
    OUTPUT_FOLDER = "/tmp/aap_output"
else:
    DATA_FOLDER = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop", "AAP Locked in")
    ASSETS_FOLDER = DATA_FOLDER
    OUTPUT_FOLDER = os.path.join(DATA_FOLDER, "videos")

LOGO_PATH = os.path.join(ASSETS_FOLDER, "channel logo.png")
INTRO_VIDEO_PATH = os.path.join(ASSETS_FOLDER, "intro.mp4")

# === GEMINI AI ===
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
# 2026-08: FLASH-LITE, the cheapest tier — cost is a real constraint here and
# the only job is short JSON packaging (titles/tags), which lite handles fine.
# Measured: 1.3s round trip, 20 tokens in / 9 out on a title call, so a day of
# output is a handful of thousands of tokens. Verified working against the live
# API (2.5-flash-lite is gone; 3.5-flash-lite is current).
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')

# === VISION IMAGE SCOUTING — OFF (cost) ===
# Gemini vision genuinely solves the junk-image problem (measured on real pool
# images: studio portrait 8, trailer frame 2, scene still 3 — discrimination the
# filename/edge heuristics never achieved). But it costs one image request PER
# PHOTO, i.e. ~14 requests per short and ~130 per long-form, which is by far the
# most expensive thing the pipeline could do. Owner decision: not worth it.
# The existing free heuristics (leading-lady gate, print-matter edge veto,
# quality gate) stay in force. Flip VISION_SCOUT=True to re-enable.
VISION_SCOUT = False
VISION_MIN_SCORE = 6         # keep >= this (0-10), only when scouting is on
VISION_OVERSELECT = 1.3      # download buffer for quality-gate rejects
# Shorts need a bigger buffer than long-form: the print-matter veto and frame
# ranking discard whole frames, and a short is only 13 of them, so losing 4
# visibly shortens the video (a test run fell from 56s to 46.5s).
SHORT_OVERSELECT = 1.9

# === SHORTS (primary format since 2026-08) ===
# The channel's own history: Shorts out-performed long-form ~2:1 in every month
# they ran (Aug 2025 medians 912 vs 560; Sep 2025 1,262 vs 586) and have been
# unused since. Vertical, fast, music-led.
SHORTS_PER_DAY = 4           # owner asked for 2-4; 4 once Actions minutes became free (public repo)
SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920
SHORT_IMAGE_COUNT = 13       # 3x3s + 10x5s - xfade overlap = ~56s
SHORT_IMAGE_DURATION = 5.0
SHORT_HOOK_CLIPS = 3         # first N images play faster to hook the scroll
SHORT_HOOK_DURATION = 3.0
SHORT_MUSIC_START = (18, 45) # random offset window so tracks don't all open alike
SHORT_KENBURNS = True
# A short needs only ~17 rows, so it can afford to take them all from the
# CURATED pool. The bulk pools are where damaged scans and scene stills live —
# a test short built from them led with an unglamorous, damaged street photo.
SHORT_CURATED_ONLY = True
LONGFORM_PER_DAY = 1         # keep one long-form for watch-time; 0 disables
LONGFORM_EVERY_N_DAYS = 1    # daily again: the repo is public, so runner minutes
                             # are free. Set 2 to halve long-form cost if it
                             # ever goes private again (scheduler COST GATE).
DOWNLOAD_WIDTH = 1920         # max px fetched from Commons (API-resolved; never upscaled)

# === CSV FILES ===
# goldmine3 = the curated, license-checked, real-portrait pool from harvest_goldmine3.py.
# It is listed FIRST so the cleaner portraits are drawn before the older (poster/scene-
# polluted) goldmine1/2 pools.
GOLDMINE3_CSV = os.path.join(DATA_FOLDER, "goldmine3_links.csv")
GOLDMINE_CSV = os.path.join(DATA_FOLDER, "goldmine_links.csv")
GOLDMINE2_CSV = os.path.join(DATA_FOLDER, "goldmine2_links.csv")

# === VIDEO SETTINGS ===
# 1080p since 2026-08 (owner call): 4K roughly quadrupled encode time for
# marginal visible gain on ~1000-3000px vintage scans, and the render budget
# is better spent on TWO videos per day than one 4K video.
WIDTH = 1920
HEIGHT = 1080
# Multiplier applied to all hardcoded pixel sizes (caption box/font, frame
# vignette, side text, logo overlay). 1.0 at 1080p baseline, 2.0 at 4K.
# Wrap every hardcoded px value with `int(N * config.SCALE)`.
SCALE = HEIGHT / 1080.0
FPS = 30
# 2026-07 relaunch: match the verified winning container of the reference
# channels (~100 photos @ ~12s = 20-22 min, music-only). Doubles watch-time
# per impression vs the old 45 @ 15s (~11 min) format; daily 4K encode load
# is unchanged because cadence dropped from 2 videos/day to 1.
IMAGE_DURATION = 12        # seconds per image (verified reference-channel pace)
LOGO_DURATION = 15         # seconds for intro video (intro.mp4)
VIDEO_LENGTH_MIN = 19      # minutes minimum
VIDEO_LENGTH_MAX = 22      # minutes maximum
IMAGES_PER_VIDEO = 100     # default (~20 min 12 sec total)

# === KEN BURNS EFFECT ===
ZOOM_MIN = 1.0
ZOOM_MAX = 1.15
PAN_MAX_PERCENT = 0.05     # 5% of frame

# === TEXT OVERLAY ===
FONT_SIZE = 48
FONT_COLOR = "white"
TEXT_BG_COLOR = "black"
TEXT_BG_OPACITY = 0.6
TEXT_POSITION = "bottom"
TEXT_FADE_DURATION = 0.5

# === AUDIO SETTINGS ===
MUSIC_VOLUME = 0.3         # 30% volume for background music
AUDIO_FADE_OUT = 2.0       # seconds to fade out at end

# === AUDIO FILES ===
AUDIO_FILES = [
    os.path.join(ASSETS_FOLDER, "Satin and Smoke (5) - Copy.mp3"),
    os.path.join(ASSETS_FOLDER, "Satin and Smoke (6).mp3"),
    os.path.join(ASSETS_FOLDER, "Satin and Smoke (7).mp3"),
    os.path.join(ASSETS_FOLDER, "Nighttime Stroll - E's Jammy Jams - Copy.mp3"),
    os.path.join(ASSETS_FOLDER, "Soul and Mind - E's Jammy Jams - Copy.mp3"),
    os.path.join(ASSETS_FOLDER, "Wish You'd Never Left - TrackTribe - Copy.mp3"),
]

# === FFMPEG ===
if IS_RAILWAY or IS_GITHUB:
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"
    # Regular (non-bold) DejaVu Sans — bold was too thick and chunky.
    CAPTION_FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
else:
    FFMPEG_PATH = r"C:\ffmpeg\ffmpeg-8.0-essentials_build\bin\ffmpeg.exe"
    FFPROBE_PATH = r"C:\ffmpeg\ffmpeg-8.0-essentials_build\bin\ffprobe.exe"
    CAPTION_FONT_FILE = r"C:\Windows\Fonts\arial.ttf"

# === YOUTUBE API ===
if IS_GITHUB:
    YOUTUBE_CREDENTIALS_FILE = os.path.join(_REPO, "client_secret.json")
    YOUTUBE_TOKEN_FILE = os.path.join(_REPO, "youtube_token.json")
elif IS_RAILWAY:
    YOUTUBE_CREDENTIALS_FILE = "/app/client_secret.json"
    YOUTUBE_TOKEN_FILE = "/data/youtube_token.json"
else:
    YOUTUBE_CREDENTIALS_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "ActressAutoShort", "client_secret.json")
    YOUTUBE_TOKEN_FILE = os.path.join(os.path.expanduser("~"), "Desktop", "ActressAutoShort", "youtube_token.json")

DEFAULT_CATEGORY_ID = "24"  # Entertainment
DEFAULT_PRIVACY = "private"  # scheduled publishing (private → auto-public at publishAt)
AAP_PLAYLIST_ID = "PLLulfiW_JfsuNgd5op8Bn2Qf5lKBrJqBg"  # "Actress Actor and Pinups" main playlist

# === SCHEDULING ===
UPLOAD_HOUR = 14           # 2 PM - good for 65+ audience
UPLOAD_MINUTE = 0
DAILY_VIDEO_COUNT = 2      # videos per day
SCHEDULE_TIMES = ["21:00", "03:00"]  # SGT - two runs per day

# === THUMBNAIL — CTR push (2026-07 revision 2; each is a kill-switch) ===
# Verified against the CURRENT thumbnails of both reference channels (fetched
# live via API): they run ONE full-frame pinup-era figure shot (face + figure
# visible, subject fills the frame) + a bold red arrow — NOT split diptychs,
# NOT face close-ups. Owner decision: "authentic pinup era" level (real
# 1940s-50s swimsuit/gown glamour), arrow ON but senior-friendly (bold, white
# outline). AAP CTR was 2-3% on the elegant-faces diptych; target is 7-10%.
THUMB_ENABLE_ARROW = True         # bold red arrow w/ white outline (both winners use one)
THUMB_ENABLE_TEXT = False         # on-thumbnail word + subtext OFF — image sells it.
THUMB_TEXT_WORD = None            # if THUMB_ENABLE_TEXT, force this single ALL-CAPS word (else rotate)
THUMB_GREYSCALE_RATIO = 0.0       # 0.0 = 100% warm color. Warm tones read better for 65+ eyes.
THUMB_ENABLE_FRAME = True         # thin warm-gold border + small corner monogram (brand signature)
THUMB_FACE_BIAS = 0.34            # vertical crop bias toward the upper third → larger face
# TRUE since 2026-07. Rendering all 25 curated bases through both crops showed
# the 16:9 single-frame crop clipping the top of the skull on ~60% of this pool
# (our sources are tall head-and-shoulders studio portraits, unlike the
# competitors' full-body 35mm frames). The diptych's 637x720 panels are
# portrait-shaped and keep head, shoulders and some figure - which is also the
# "face AND figure" look the owner asked for, and the split look they chose.
THUMB_SPLIT = True
THUMB_USE_VIDEO_LEAD = False      # (legacy) single-frame from the video; superseded
THUMB_RECENT_LEDGER = os.path.join(DATA_FOLDER, "thumb_recent.json")
# Recently-used TITLES. Three weeks of daily output re-converged on a handful of
# openers ("Remember How Beautiful They Were?" in 5 of 20 uploads) — the same
# near-identical-title pattern that preceded the May collapse. The generator
# reads this ledger and is forbidden from reusing a recent opening.
TITLE_RECENT_LEDGER = os.path.join(DATA_FOLDER, "title_recent.json")
TITLE_RECENT_AVOID = 25           # how many recent titles to consider "too soon"

# === STAR EPISODES (2026-07) ===
# Build most of each video from ONE star so the video is about someone, the
# title is searchable and the playlist coheres. Random selection meant every
# video held 60-90 unrelated people and could never be found by search.
STAR_EPISODES = True
STAR_RECENT_LEDGER = os.path.join(DATA_FOLDER, "star_recent.json")
THUMB_RECENT_AVOID = 20           # don't reuse the same base within this many uploads (feed freshness)

# === TITLES — Phase A ===
# Owner prefers GENERIC + DIRECT titles (e.g. "Legendary Hollywood Actresses in
# Stunning Rare Photos") over naming individual stars — matches the reference
# channels, which title collectively. Flip to True to allow star-named titles.
# ON since 2026-07 (star episodes). Own-channel data, controlled Feb-Apr window
# with the same era/production/thumbnail template on both groups: star-named
# titles ran n=95 median 380 / p90 1,612 vs generic hooks n=65 median 233 /
# p90 925 (+63% median). Every all-time best video is a single-star episode.
TITLE_ALLOW_STAR_NAMES = True
# OFF since 2026-07: on this channel's OWN data, in a controlled Feb-Apr window
# (same era, same production, same thumbnail template), emoji-prefixed titles
# ran median 149 views vs 380 for non-emoji. It was adopted as a "niche CTR
# signature" copied from competitors — our own numbers say it costs us.
TITLE_ALLOW_EMOJI = False
TITLE_BRAND_SUFFIX = "| Actress Actor and Pinups"  # appended ONLY when it fits (see gemini_generator)
TITLE_BRAND_SUFFIX_MAXLEN = 70    # append the suffix only if the total title stays within this
TITLE_MAX_LEN = 90                # hard cap (YouTube allows 100)

# === DESCRIPTION — Phase A ===
ENABLE_CHAPTERS = True            # build per-video chapters/timestamps (was generated but unused)

# === PHASE B — render/retention tuning (flag-gated; defaults = CURRENT behavior) ===
# Verified from the reference channels: ~12s/photo, ~20min, music-only (no per-photo
# narration). Owner's Phase B = keep ~45 photos, retune TIMING + INTRO (+ 65+ caption
# legibility + music polish), A/B'd against the current style. Ken Burns stays OFF
# (AAP's own data: zoom dropped avg view 3.0min -> 1.21min).
FAST_OPENING_CLIPS = 3            # first N images play shorter for early momentum (promoted from a local)
FAST_OPENING_DURATION = 10       # seconds for those opening clips (control default; was a local)
XFADE_DUR = 0.5                  # crossfade seconds (double-coupled to total_duration + chapter timeline)
INTRO_DURATION_OVERRIDE = None   # None = play the full branded intro.mp4 (current); set N to trim to N seconds
# Caption STYLE (now the channel standard: succinct text, large, pristine white
# with a bold black outline — like the prestige reference channels).
CAPTION_FONT_SCALE = 1.0         # extra multiplier on the (already enlarged) caption fonts
CAPTION_OUTLINE_RATIO = 0.085    # black outline thickness as a fraction of font size (0 = none)
CAPTION_BAR = False              # dark bar behind captions (False = clean outlined text, the new look)
CAPTION_BOX_OPACITY = 0.55       # bar darkness IF CAPTION_BAR is True
AUDIO_FADE_IN = 0.0              # gentle music fade-in at start (0.0 = current; only a fade-out existed)

# === A/B EXPERIMENT (Phase B) — RETIRED 2026-07 ===
# Superseded by the relaunch format change (12s/photo is now the baseline and
# --daily produces a single video, so there is no second slot to A/B against).
# Harness kept for possible future experiments.
AB_TESTING_ENABLE = False
AB_ARM = None                    # set at runtime per video ('control'|'variant'); used only for tagging
PHASE_B_VARIANT = {              # overrides applied to the VARIANT arm only (pacing + intro)
    'IMAGE_DURATION': 12,        # ~12s/photo, matching the verified channel pace (was 15)
    'FAST_OPENING_DURATION': 8,  # snappier open at the 12s base
    'INTRO_DURATION_OVERRIDE': 7,# a recognizable face lands ~7s in instead of ~15s
    'AUDIO_FADE_IN': 2.0,        # gentle music entrance under the intro
}                                # (captions are now a global standard, not an A/B variable)

# === IMAGE QUALITY GATE (2026-07: reject scans that look bad on the 4K canvas) ===
# Applied post-download in create_slideshow. Rejected rows are blacklisted
# (marked used) so the pool self-cleans; over-selection compensates.
IMG_MIN_LONG_EDGE = 1200   # px; reject smaller (upscales look soft at 4K). 0 = off
IMG_MAX_ASPECT = 2.4       # reject panoramas/strips/documents. 0 = off
IMG_MIN_SHARPNESS = 0      # edge-variance floor; 0 = OFF (grain fools the metric on
                           # vintage scans — calibration 2026-07; use only if needed)
SELECT_BUFFER = 1.3        # over-select rows so quality rejects still fill the video
# Recycle used rows after this many days. The PD pool is finite (goldmine3
# drained 1,300 -> ~32 usable in a month); used-forever marking starves the
# channel, and the reference channels recycle far more aggressively. Only
# DATE-stamped rows recycle; legacy 'TRUE' marks stay blocked.
IMG_REUSE_DAYS = 30         # was 60; halved 2026-09-22 when 4 shorts + 1 long-form a day (~210 photos) outran the pool

# === RATE LIMITING ===
WIKIMEDIA_DELAY = 2.5      # seconds between scrape requests
IMAGE_DOWNLOAD_DELAY = 3.0 # seconds between image downloads
MAX_RETRIES = 3            # retry failed downloads

# === TEMP FOLDER ===
TEMP_FOLDER = os.path.join(OUTPUT_FOLDER, "temp")

# Ensure output directories exist
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# PUBLISHING & ENGAGEMENT (2026-09 revival)
# ---------------------------------------------------------------------------
# Publish slots in US EASTERN time (DST-aware), not SGT. The audience is
# retired US men: mornings with coffee, lunch, mid-afternoon and the evening
# sit-down. The old SGT offsets had long-form going live at 3 AM Eastern.
PUBLISH_TZ = "America/New_York"
SHORT_SLOTS_ET = ["08:00", "12:00", "15:00", "20:00"]   # extra shorts step +3h
LONGFORM_SLOT_ET = "17:00"                               # evening TV viewing

# End-card question on each short's final clip (headline, subline). Warm,
# inviting, no assumptions about the viewer's age or the star's gender.
# Avoid apostrophes and colons: they are ffmpeg drawtext escape hazards.
SHORT_END_PROMPTS = [
    ("Your Hollywood crush?", "Tell us in the comments"),
    ("Your favorite star?", "Tell us in the comments"),
    ("Remember this era?", "Share a memory below"),
    ("First movie you saw?", "Tell us in the comments"),
    ("Who should we show next?", "Name a star below"),
]

# Add each upload to a per-star playlist ("Mary Pickford - Rare Photos") plus
# a format playlist. Binge paths keep viewers on the channel. Needs the
# youtube scope, which the current token has. Best-effort: never blocks upload.
AUTO_PLAYLISTS = True

# Post a warm question as the channel's first comment on every upload.
# Requires the youtube.force-ssl scope; skipped (logged once) until the token
# is re-authorised with it.
AUTO_FIRST_COMMENT = True

# Pool depth for shorts (2026-09-22). Minimum usable photos for a short to be
# published at all, and how many candidate rows to line up per short.
SHORT_MIN_CLIPS = 10
SHORT_CANDIDATE_MULT = 3.0
