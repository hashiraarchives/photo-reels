"""
AAP - Actress Actor and Pinups
Automated Pipeline Scheduler

Orchestrates the full automation pipeline:
1. Generate video (with Gemini AI titles)
2. Upload to YouTube
3. Repeat on schedule (2x daily at 9 PM and 3 AM SGT)

Can run as a continuous daemon or execute once.
"""

import os
import json
import sys
import time
import random
import logging
import subprocess
import shutil
from datetime import datetime, timedelta
from typing import Optional
import config

# Set up logging — Railway captures stdout natively, skip FileHandler there
log_handlers = [logging.StreamHandler()]
if not config.IS_RAILWAY:
    log_handlers.append(logging.FileHandler(os.path.join(config.OUTPUT_FOLDER, 'scheduler.log')))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger('AAP-Scheduler')

# === A/B experiment harness (Phase B) ===
# create_video / _wrap_caption / the audio step all read their config values at CALL
# time, so mutating config between videos cleanly switches arms within one --daily run.
_AB_BASELINE = {}


def apply_ab_arm(arm: str):
    """Apply an A/B arm to config in-place for the next video to be generated.
    arm='variant' applies config.PHASE_B_VARIANT overrides; 'control' restores baseline.
    The arm is also stamped on the upload as an exp_phaseb_<arm> tag."""
    global _AB_BASELINE
    config.AB_ARM = arm
    variant = getattr(config, 'PHASE_B_VARIANT', {}) or {}
    if arm == 'variant':
        for k, v in variant.items():
            if k not in _AB_BASELINE:
                _AB_BASELINE[k] = getattr(config, k, None)
            setattr(config, k, v)
        logger.info(f"A/B arm = VARIANT; overrides applied: {variant}")
    else:
        for k, v in _AB_BASELINE.items():
            setattr(config, k, v)
        logger.info("A/B arm = CONTROL (current settings)")

# Theme pool for automatic rotation
THEME_POOL = [
    "Classic_Hollywood_Glamour",
    "Golden_Age_Beauties",
    "Vintage_Hollywood_Stars",
    "Old_Hollywood_Icons",
    "Retro_Cinema_Legends",
    "Hollywood_Golden_Era",
    "Classic_Film_Stars",
    "Vintage_Starlets",
    "Silver_Screen_Legends",
    "Hollywood_Nostalgia",
    "Timeless_Hollywood",
    "Classic_Cinema_Beauty",
    "Old_Hollywood_Charm",
    "Golden_Age_Glamour",
    "Vintage_Movie_Stars",
    "Hollywood_Heritage",
    "Classic_Star_Portraits",
    "Retro_Hollywood_Magic",
    "Silver_Screen_Beauty",
    "Vintage_Hollywood_Gems",
]

# Track used themes to avoid repeats
_used_themes = []


def get_next_theme() -> str:
    """Get next theme from rotation pool, avoiding recent repeats."""
    global _used_themes

    available = [t for t in THEME_POOL if t not in _used_themes]
    if not available:
        _used_themes = []
        available = THEME_POOL.copy()

    theme = random.choice(available)
    _used_themes.append(theme)

    # Keep only last 10 used
    if len(_used_themes) > 10:
        _used_themes = _used_themes[-10:]

    # Append date for uniqueness
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    return f"{theme}_{date_str}"


def run_pipeline(upload: bool = True, privacy: str = None, theme: str = None,
                 schedule_time=None) -> bool:
    """
    Run the full video generation and upload pipeline.

    Args:
        upload: Whether to upload to YouTube after generation
        privacy: Privacy setting for upload ('public', 'private', 'unlisted')
        theme: Optional theme name (auto-rotated if not provided)
        schedule_time: Optional UTC datetime for scheduled YouTube publishing

    Returns:
        True if successful, False otherwise
    """
    if not theme:
        theme = get_next_theme()

    logger.info("=" * 60)
    logger.info(f"Starting AAP Pipeline - Theme: {theme}")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if schedule_time:
        logger.info(f"Scheduled publish (UTC): {schedule_time}")
    logger.info("=" * 60)

    try:
        # Step 1: Generate video
        logger.info("[1/2] Generating video...")
        from create_slideshow import generate_video

        video_path = generate_video(theme=theme)

        if not video_path:
            logger.error("Video generation failed!")
            return False

        logger.info(f"Video created: {video_path}")

        # Step 2: Upload to YouTube
        if upload:
            logger.info("[2/2] Uploading to YouTube...")
            from youtube_uploader import upload_from_metadata

            metadata_path = video_path.replace('.mp4', '_metadata.json')

            if os.path.exists(metadata_path):
                video_id = upload_from_metadata(
                    metadata_path,
                    privacy=privacy or config.DEFAULT_PRIVACY,
                    schedule_time=schedule_time
                )

                if video_id:
                    logger.info(f"Upload successful! Video ID: {video_id}")
                    logger.info(f"URL: https://www.youtube.com/watch?v={video_id}")
                else:
                    logger.error("Upload failed!")
                    return False
            else:
                logger.warning("Metadata file not found, skipping upload")
        else:
            logger.info("[2/2] Skipping upload (disabled)")

        logger.info("Pipeline completed successfully!")
        return True

    except Exception as e:
        logger.exception(f"Pipeline error: {e}")
        return False


def run_short_pipeline(upload: bool = True, privacy: str = None,
                       schedule_time=None) -> bool:
    """
    Generate ONE vertical short and upload it.

    Kept separate from run_pipeline because a Short is a different product:
    vertical, no branded intro, its own punchy packaging, and no thumbnail
    upload (YouTube uses a video frame for Shorts, so a 16:9 thumbnail would
    only be wasted work).
    """
    try:
        from create_short import generate_short
        import youtube_uploader as yu
    except ImportError as e:
        logger.error(f"Cannot run shorts pipeline: {e}")
        return False

    meta_path = generate_short()
    if not meta_path:
        logger.error("Short generation failed")
        return False

    if not upload:
        logger.info(f"Short generated (upload skipped): {meta_path}")
        return True

    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        title = yu.build_short_title(metadata)
        description = yu.build_short_description(metadata)
        tags = yu.generate_short_tags(metadata)
        logger.info(f"Short title: {title}")

        video_id = yu.upload_video(
            video_path=metadata['video_file'],
            title=title,
            description=description,
            tags=tags,
            privacy=privacy or config.DEFAULT_PRIVACY,
            schedule_time=schedule_time,
            star=(metadata.get('focus_star') or '').strip(),
            is_short=True,
        )
        if video_id:
            logger.info(f"Short uploaded: https://youtube.com/shorts/{video_id}")
            return True
        logger.error("Short upload failed")
        return False
    except Exception as e:
        logger.error(f"Short upload error: {e}")
        return False


def run_with_retry(upload: bool = True, privacy: str = None,
                   max_retries: int = 2, retry_delay: int = 300,
                   schedule_time=None) -> bool:
    """
    Run pipeline with retry logic.

    Args:
        upload: Whether to upload to YouTube
        privacy: Privacy setting
        max_retries: Max number of retries on failure
        retry_delay: Seconds to wait between retries
        schedule_time: Optional UTC datetime for scheduled publishing

    Returns:
        True if any attempt succeeded
    """
    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.info(f"Retry {attempt}/{max_retries} after {retry_delay}s delay...")
            time.sleep(retry_delay)

        success = run_pipeline(upload=upload, privacy=privacy, schedule_time=schedule_time)

        if success:
            return True

        logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed")

    logger.error(f"All {max_retries + 1} attempts failed!")
    return False


def calculate_next_run() -> datetime:
    """
    Calculate the next scheduled run time from SCHEDULE_TIMES.
    Returns the soonest upcoming scheduled time.
    """
    now = datetime.now()
    schedule_times = getattr(config, 'SCHEDULE_TIMES', ["21:00", "03:00"])

    candidates = []
    for time_str in schedule_times:
        hour, minute = map(int, time_str.split(':'))

        # Today's run
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If already past, schedule for tomorrow
        if candidate <= now:
            candidate += timedelta(days=1)

        candidates.append(candidate)

    # Return the soonest
    return min(candidates)


def run_scheduled():
    """Run the pipeline on a dual daily schedule with retry logic."""
    schedule_times = getattr(config, 'SCHEDULE_TIMES', ["21:00", "03:00"])

    logger.info("Starting scheduled mode")
    logger.info(f"Scheduled times (SGT): {', '.join(schedule_times)}")
    logger.info(f"Videos per day: {config.DAILY_VIDEO_COUNT}")

    # Stats tracking
    total_runs = 0
    successful_runs = 0

    while True:
        next_run = calculate_next_run()
        wait_seconds = (next_run - datetime.now()).total_seconds()

        logger.info(f"Next run scheduled for: {next_run.strftime('%Y-%m-%d %H:%M')}")
        logger.info(f"Waiting {wait_seconds/3600:.1f} hours...")

        # Wait until next scheduled time
        time.sleep(max(0, wait_seconds))

        # Run the pipeline with retry
        logger.info("Scheduled run starting...")
        total_runs += 1
        success = run_with_retry(upload=True, max_retries=2, retry_delay=300)

        if success:
            successful_runs += 1
            logger.info("Scheduled run completed successfully")
        else:
            logger.error("Scheduled run failed after all retries")

        # Log summary
        logger.info(f"Stats: {successful_runs}/{total_runs} successful runs")

        # Small delay before calculating next run
        time.sleep(60)


def check_prerequisites() -> bool:
    """Check that all required files and tools are available."""
    issues = []

    # Check FFmpeg. A bare command name ("ffmpeg", as used on Railway AND on
    # GitHub Actions) lives on PATH, not on the filesystem, so os.path.exists is
    # simply the wrong test for it — that mismatch failed the first Actions run.
    # Decide by the value, not by which host we happen to be on.
    if os.path.dirname(config.FFMPEG_PATH):
        if not os.path.exists(config.FFMPEG_PATH):
            issues.append(f"FFmpeg not found at: {config.FFMPEG_PATH}")
    elif shutil.which(config.FFMPEG_PATH) is None:
        issues.append(f"FFmpeg not found on PATH: {config.FFMPEG_PATH}")

    # Check CSV files
    if not os.path.exists(config.GOLDMINE_CSV):
        issues.append(f"Primary CSV not found: {config.GOLDMINE_CSV}")

    # Check audio files
    audio_found = sum(1 for f in config.AUDIO_FILES if os.path.exists(f))
    if audio_found == 0:
        issues.append("No audio files found!")

    # Check logo
    if not os.path.exists(config.LOGO_PATH):
        issues.append(f"Logo not found: {config.LOGO_PATH}")

    # Check YouTube credentials (warning only)
    if not os.path.exists(config.YOUTUBE_CREDENTIALS_FILE):
        logger.warning(f"YouTube credentials not found: {config.YOUTUBE_CREDENTIALS_FILE}")
        logger.warning("Upload functionality will not work until credentials are added.")

    # Check Gemini API key (warning only)
    gemini_key = getattr(config, 'GEMINI_API_KEY', None)
    if not gemini_key:
        logger.warning("GEMINI_API_KEY not set - will use template titles/descriptions")

    if issues:
        for issue in issues:
            logger.error(f"Prerequisite check failed: {issue}")
        return False

    logger.info("All prerequisites satisfied")
    return True


def print_status():
    """Print current system status."""
    print("\n" + "=" * 60)
    print("AAP SCHEDULER STATUS")
    print("=" * 60)

    # Schedule info
    schedule_times = getattr(config, 'SCHEDULE_TIMES', ["21:00", "03:00"])
    print(f"Schedule: {', '.join(schedule_times)} SGT ({config.DAILY_VIDEO_COUNT} videos/day)")
    next_run = calculate_next_run()
    print(f"Next run: {next_run.strftime('%Y-%m-%d %H:%M')}")

    # Count available images
    try:
        import csv
        with open(config.GOLDMINE_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            unused = sum(1 for r in rows if r.get('used', '').upper() != 'TRUE')
            print(f"Goldmine 1: {unused}/{len(rows)} images available")
    except Exception as e:
        print(f"Goldmine 1: Error reading ({e})")

    try:
        import csv
        with open(config.GOLDMINE2_CSV, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
            print(f"Goldmine 2: {len(rows)} images available")
    except Exception as e:
        print(f"Goldmine 2: Error reading ({e})")

    # Count audio files
    audio_count = sum(1 for f in config.AUDIO_FILES if os.path.exists(f))
    print(f"Audio tracks: {audio_count}/{len(config.AUDIO_FILES)}")

    # Check output folder
    try:
        import glob
        videos = glob.glob(os.path.join(config.OUTPUT_FOLDER, "*.mp4"))
        print(f"Generated videos: {len(videos)}")
    except:
        print("Generated videos: Unknown")

    # Check YouTube auth
    if os.path.exists(config.YOUTUBE_TOKEN_FILE):
        print("YouTube: Authenticated")
    elif os.path.exists(config.YOUTUBE_CREDENTIALS_FILE):
        print("YouTube: Credentials present, not authenticated")
    else:
        print("YouTube: No credentials")

    # Check Gemini
    gemini_key = getattr(config, 'GEMINI_API_KEY', None)
    if gemini_key:
        print("Gemini AI: Configured")
    else:
        print("Gemini AI: Not configured (using template titles)")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    import argparse
    from datetime import timezone

    parser = argparse.ArgumentParser(description='AAP Automation Scheduler')
    parser.add_argument('--once', action='store_true',
                        help='Run pipeline once and exit')
    parser.add_argument('--shorts', type=int, default=None, metavar='N',
                        help='Generate N vertical shorts and exit')
    parser.add_argument('--daily', action='store_true',
                        help='Generate 2 videos, upload as private scheduled for 9 PM + 3 AM SGT')
    parser.add_argument('--no-upload', action='store_true',
                        help='Generate video but skip upload')
    parser.add_argument('--privacy', type=str, choices=['public', 'private', 'unlisted'],
                        help='Privacy setting for upload')
    parser.add_argument('--theme', type=str, default=None,
                        help='Theme name (auto-rotated if not set)')
    parser.add_argument('--status', action='store_true',
                        help='Show system status and exit')
    parser.add_argument('--check', action='store_true',
                        help='Check prerequisites and exit')

    args = parser.parse_args()

    # Kill switch: set env var PIPELINE_PAUSED=1 (on Railway) to pause the daily
    # cron without a redeploy. Removing the var resumes immediately on next run.
    # Status/check are allowed through so the pause can be inspected.
    if os.environ.get("PIPELINE_PAUSED", "").strip().lower() in ("1", "true", "yes", "on") \
            and not (args.status or args.check):
        logger.warning("PIPELINE_PAUSED is set - skipping run. No videos generated or uploaded.")
        print("PIPELINE_PAUSED is set - pipeline is paused. Exiting without generating/uploading.")
        sys.exit(0)

    if args.status:
        print_status()
        sys.exit(0)

    if args.check:
        if check_prerequisites():
            print("All prerequisites satisfied!")
            sys.exit(0)
        else:
            print("Prerequisites check failed!")
            sys.exit(1)

    # Check prerequisites before running
    if not check_prerequisites():
        logger.error("Cannot start - prerequisites not met")
        sys.exit(1)

    if args.shorts is not None:
        sgt = timezone(timedelta(hours=8))
        now_sgt = datetime.now(sgt)
        base = datetime(now_sgt.year, now_sgt.month, now_sgt.day, 21, 0, 0, tzinfo=sgt)
        if base <= now_sgt:
            base += timedelta(days=1)
        ok = 0
        for i in range(args.shorts):
            pub = base + timedelta(hours=4 * i)
            logger.info(f"--- SHORT {i + 1} of {args.shorts} ---")
            if run_short_pipeline(
                    upload=not args.no_upload,
                    privacy=args.privacy or 'private',
                    schedule_time=pub.astimezone(timezone.utc).replace(tzinfo=None)):
                ok += 1
        logger.info(f"Shorts complete: {ok}/{args.shorts}")
        sys.exit(0 if ok == args.shorts else 1)

    if args.daily:
        # 2026-07 relaunch cadence: ONE video per day (both reference channels
        # post exactly 1/day; AAP's former 2/day near-identical uploads matched
        # YouTube's mass-produced/"inauthentic content" demotion profile).
        # Upload private, scheduled for 9 PM SGT (= 9 AM ET, US-morning for the
        # 65+ audience) — gives a ~15h owner review window from the 6 AM cron.
        # 2026-08 SHORTS PIVOT. The channel's own history has Shorts beating
        # long-form ~2:1 in every month they ran, so Shorts are now the primary
        # output: SHORTS_PER_DAY of them, published across the US day, plus
        # LONGFORM_PER_DAY long videos to keep watch-time (the one metric that
        # was improving). Set LONGFORM_PER_DAY = 0 to go shorts-only.
        sgt = timezone(timedelta(hours=8))
        now_sgt = datetime.now(sgt)
        today = now_sgt.date()

        n_shorts = max(0, int(getattr(config, 'SHORTS_PER_DAY', 3)))
        n_long = max(0, int(getattr(config, 'LONGFORM_PER_DAY', 1)))

        # COST GATE (2026-09). GitHub Actions bills private-repo minutes past
        # 2000/mo, and one long-form render is ~50 min of ffmpeg on a runner —
        # 1500 min/mo on its own, i.e. the whole free allowance for the format
        # the channel has *de*prioritised. Run it every Nth day instead, keyed
        # on the ordinal date so the cadence survives across runs with no state.
        every_n = max(1, int(getattr(config, 'LONGFORM_EVERY_N_DAYS', 1)))
        if n_long and every_n > 1 and today.toordinal() % every_n != 0:
            logger.info(f"Long-form skipped today (cadence: 1 in {every_n} days)")
            n_long = 0

        # Publish slots are defined in US Eastern (DST-aware): the audience is
        # retired US men. Everything lands on the NEXT Eastern day, which keeps
        # every slot in the future whenever the daily cron runs, and leaves an
        # owner review window while uploads are still private.
        try:
            from zoneinfo import ZoneInfo
            pub_tz = ZoneInfo(getattr(config, 'PUBLISH_TZ', 'America/New_York'))
        except Exception:
            pub_tz = timezone(timedelta(hours=-4))       # EDT fallback (no tzdata)
        pub_day = datetime.now(pub_tz).date() + timedelta(days=1)

        def _slot(hhmm: str, extra_hours: int = 0) -> datetime:
            h, m = (int(x) for x in hhmm.split(':'))
            local = datetime(pub_day.year, pub_day.month, pub_day.day, h, m,
                             tzinfo=pub_tz) + timedelta(hours=extra_hours)
            return local.astimezone(sgt)

        short_slots = list(getattr(config, 'SHORT_SLOTS_ET', ["08:00", "12:00", "15:00", "20:00"]))
        def short_pub(i: int) -> datetime:
            if i < len(short_slots):
                return _slot(short_slots[i])
            return _slot(short_slots[-1], extra_hours=3 * (i - len(short_slots) + 1))
        long_slot = getattr(config, 'LONGFORM_SLOT_ET', "17:00")

        # One batch per publish day. A manual dispatch plus the nightly cron
        # would otherwise both target the same Eastern day and stack ten
        # videos on it. FORCE_DAILY=1 overrides (e.g. to refill after a crash).
        ledger_path = os.path.join(config.DATA_FOLDER, 'daily_ledger.json')
        try:
            with open(ledger_path, encoding='utf-8') as f:
                last_day = json.load(f).get('last_pub_day')
        except Exception:
            last_day = None
        if last_day == pub_day.isoformat() and os.environ.get('FORCE_DAILY') != '1':
            logger.info(f"Publish day {pub_day} already has its batch; nothing to do.")
            sys.exit(0)

        logger.info("=" * 60)
        logger.info(f"=== DAILY MODE: {n_shorts} shorts + {n_long} long-form ===")
        logger.info("=" * 60)

        ok_short = 0
        for i in range(n_shorts):
            pub = short_pub(i)
            logger.info(f"--- SHORT {i + 1} of {n_shorts} "
                        f"(publish {pub.strftime('%m-%d %H:%M')} SGT) ---")
            if run_short_pipeline(
                    upload=True, privacy='private',
                    schedule_time=pub.astimezone(timezone.utc).replace(tzinfo=None)):
                ok_short += 1
            else:
                logger.warning(f"Short {i + 1} failed; continuing")

        ok_long = 0
        for i in range(n_long):
            pub = _slot(long_slot, extra_hours=24 * i)
            logger.info(f"--- LONG-FORM {i + 1} of {n_long} "
                        f"(publish {pub.strftime('%m-%d %H:%M')} SGT) ---")
            if run_with_retry(
                    upload=True, privacy='private', max_retries=2, retry_delay=300,
                    schedule_time=pub.astimezone(timezone.utc).replace(tzinfo=None)):
                ok_long += 1
            else:
                logger.warning(f"Long-form {i + 1} failed; continuing")

        if ok_short or ok_long:
            with open(ledger_path, 'w', encoding='utf-8') as f:
                json.dump({'last_pub_day': pub_day.isoformat(),
                           'shorts': ok_short, 'longform': ok_long}, f)

        logger.info(f"Daily run complete: {ok_short}/{n_shorts} shorts, "
                    f"{ok_long}/{n_long} long-form")
        # Fail the job on ANY miss. Exiting 0 when one video succeeded is how
        # five weeks of "0/3 shorts" stayed a green check. A red run makes
        # GitHub email the owner; pool state is still persisted (if: always()).
        sys.exit(0 if (ok_short == n_shorts and ok_long == n_long) else 1)

    elif args.once:
        # Run once and exit (with retry)
        success = run_with_retry(
            upload=not args.no_upload,
            privacy=args.privacy,
            max_retries=2,
            retry_delay=300
        )
        sys.exit(0 if success else 1)
    else:
        # Run on dual schedule
        try:
            run_scheduled()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            sys.exit(0)
