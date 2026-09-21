"""
AAP - Actress Actor and Pinups
First-Run Data Seeder for Railway

Copies initial CSVs from /app/seed_data/ to /data/ (Railway Volume) if they
don't exist yet. For goldmine image CSVs that DO exist on the volume, MERGES
in any new rows from the shipped copy (by image_url) while preserving the
volume's 'used' tracking — so pool top-ups committed to the repo actually
reach production instead of being silently skipped.

Also seeds youtube_token.json from YOUTUBE_TOKEN_JSON env var.
"""

import csv
import os
import shutil


def merge_goldmine(src: str, dst: str) -> int:
    """Append rows from src whose image_url isn't already in dst. Preserves
    dst rows untouched (including 'used' marks). Returns rows added."""
    with open(dst, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        dst_rows = list(reader)
        dst_fields = list(reader.fieldnames or [])
    existing = {r.get('image_url') for r in dst_rows}
    with open(src, encoding='utf-8') as f:
        new_rows = [r for r in csv.DictReader(f)
                    if r.get('image_url') and r['image_url'] not in existing]
    if not new_rows:
        return 0
    # Union of columns (e.g. volume copy may have gained a 'used' column)
    fields = dst_fields + [k for k in new_rows[0].keys() if k not in dst_fields]
    with open(dst, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in dst_rows + new_rows:
            w.writerow({k: r.get(k, '') for k in fields})
    return len(new_rows)


def unlock_legacy_used(path: str, as_of_date: str) -> int:
    """Convert undated legacy used='TRUE' marks to a date so the recycling
    cooldown applies to them. Returns rows converted."""
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    n = 0
    for r in rows:
        if (r.get('used') or '').strip().upper() == 'TRUE':
            r['used'] = as_of_date
            n += 1
    if n:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, '') for k in fields})
    return n


# On GITHUB ACTIONS the repo IS the data store, so there is nothing to seed —
# only the YouTube token has to be materialised from the secret.
if os.environ.get('GITHUB_ACTIONS') == 'true':
    tok = os.environ.get('YOUTUBE_TOKEN_JSON')
    if tok:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'youtube_token.json'), 'w') as f:
            f.write(tok)
        print("Wrote youtube_token.json from secret")
    else:
        print("ERROR: YOUTUBE_TOKEN_JSON secret is not set")
    print("Seed complete (GitHub Actions: repo is the data store).")

# Only run on Railway
elif os.environ.get('RAILWAY_ENVIRONMENT'):
    SEED_DIR = "/app/seed_data"
    DATA_DIR = "/data"

    os.makedirs(DATA_DIR, exist_ok=True)

    # Seed CSVs
    if os.path.isdir(SEED_DIR):
        for filename in os.listdir(SEED_DIR):
            src = os.path.join(SEED_DIR, filename)
            dst = os.path.join(DATA_DIR, filename)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)
                print(f"Seeded {filename} to {DATA_DIR}")
            elif filename.startswith('goldmine') and filename.endswith('.csv'):
                try:
                    added = merge_goldmine(src, dst)
                    print(f"Merged {filename}: +{added} new rows (used-marks preserved)")
                except Exception as e:
                    print(f"Merge failed for {filename} ({e}); volume copy left untouched")
                # ONE-TIME MIGRATION (2026-08): goldmine3 is the curated star-
                # dense pool and it drained to ~32 usable rows, leaving the
                # channel building videos from silent-film scene stills. Its
                # legacy 'TRUE' used-marks carry no date, which blocks them
                # from the IMG_REUSE_DAYS recycling forever. Backdate them to
                # 2026-06-01 (their bulk-usage era) so the curated portraits
                # re-enter rotation now. Idempotent: 'TRUE' disappears after
                # the first pass. goldmine1/2 legacy marks stay blocked.
                if filename == 'goldmine3_links.csv':
                    try:
                        n = unlock_legacy_used(dst, '2026-06-01')
                        if n:
                            print(f"Unlocked {n} legacy-used goldmine3 rows for recycling")
                    except Exception as e:
                        print(f"Legacy unlock failed ({e}); continuing")
            else:
                print(f"Skipping {filename} (already exists on volume)")
    else:
        print(f"No seed_data directory found at {SEED_DIR}")

    # Always write YouTube token from env var (ensures latest token is used)
    token_path = os.path.join(DATA_DIR, "youtube_token.json")
    token_json = os.environ.get('YOUTUBE_TOKEN_JSON')
    if token_json:
        with open(token_path, 'w') as f:
            f.write(token_json)
        print(f"Wrote youtube_token.json from env var")
    else:
        print("Warning: No YOUTUBE_TOKEN_JSON env var set")

    print("Seed complete.")
else:
    print("Not on Railway, skipping seed.")
