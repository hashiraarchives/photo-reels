"""
One-off cleanup: unlist the May-2026+ templated-flood videos.

The May-July 2026 uploads (near-identical templated slideshows, 2/day) match
YouTube's "inauthentic content" enforcement profile and coincide with the
channel-wide distribution collapse. Per official guidance we UNLIST (never
delete) so watch-time/engagement history is preserved while the videos drop
out of browse/search and the channel page.

Selection: publishedAt >= CUTOFF, privacyStatus == public, views < VIEW_FLOOR.
The view floor protects the handful of flood-era videos that found an
audience (e.g. the 1,498-view May 11 video).

Usage:
    python unlist_flood.py            # dry run - prints what WOULD be unlisted
    python unlist_flood.py --execute  # actually unlists

Idempotent/resumable: only public videos are touched, so a re-run after a
quota cut-off (videos.update costs 50 units; ~130 updates ~= 6.5k of the 10k
daily quota) simply picks up where it left off.
"""

import sys
import argparse

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

CUTOFF = "2026-05-01T00:00:00Z"   # start of the templated-flood era
VIEW_FLOOR = 300                  # keep flood-era videos that beat this public
TOKEN_FILE = "youtube_token.json"


def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def collect_candidates(yt):
    """All public uploads from CUTOFF onward with views < VIEW_FLOOR."""
    uploads = yt.channels().list(part="contentDetails", mine=True).execute()[
        "items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids, tok = [], None
    while True:
        pl = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                     maxResults=50, pageToken=tok).execute()
        video_ids += [i["contentDetails"]["videoId"] for i in pl["items"]]
        tok = pl.get("nextPageToken")
        if not tok:
            break

    candidates, kept = [], []
    for i in range(0, len(video_ids), 50):
        vr = yt.videos().list(part="snippet,statistics,status",
                              id=",".join(video_ids[i:i + 50])).execute()
        for v in vr["items"]:
            pub = v["snippet"].get("publishedAt", "")
            if pub < CUTOFF:
                continue
            if v["status"].get("privacyStatus") != "public":
                continue
            views = int(v["statistics"].get("viewCount", 0))
            row = {"id": v["id"], "pub": pub, "views": views,
                   "title": v["snippet"].get("title", ""),
                   "status": v["status"]}
            (kept if views >= VIEW_FLOOR else candidates).append(row)
    candidates.sort(key=lambda r: r["pub"])
    kept.sort(key=lambda r: r["views"], reverse=True)
    return candidates, kept


def unlist(yt, row):
    """Flip privacyStatus to unlisted, preserving the other status fields."""
    status = dict(row["status"])
    status["privacyStatus"] = "unlisted"
    # publishAt only valid on private videos; drop if present
    status.pop("publishAt", None)
    yt.videos().update(part="status",
                       body={"id": row["id"], "status": status}).execute()


def main():
    ap = argparse.ArgumentParser(description="Unlist the May-2026+ flood videos")
    ap.add_argument("--execute", action="store_true",
                    help="Actually unlist (default is dry run)")
    args = ap.parse_args()

    yt = get_service()
    candidates, kept = collect_candidates(yt)

    def clean(s):
        return s.encode("ascii", "replace").decode()

    print(f"Public videos published >= {CUTOFF[:10]} with < {VIEW_FLOOR} views: "
          f"{len(candidates)}")
    print(f"{'date':10s}  {'views':>6s}  title")
    for r in candidates:
        print(f"{r['pub'][:10]}  {r['views']:6d}  {clean(r['title'])[:70]}")

    if kept:
        print(f"\nKept public (>= {VIEW_FLOOR} views): {len(kept)}")
        for r in kept:
            print(f"  {r['pub'][:10]}  {r['views']:6d}  {clean(r['title'])[:66]}")

    if not args.execute:
        print("\nDRY RUN - nothing changed. Re-run with --execute to unlist.")
        return

    print(f"\nUnlisting {len(candidates)} videos...")
    done = 0
    for r in candidates:
        try:
            unlist(yt, r)
            done += 1
            print(f"  [{done}/{len(candidates)}] unlisted {r['id']} "
                  f"({r['pub'][:10]}, {r['views']} views)")
        except Exception as e:
            print(f"  FAILED {r['id']}: {e}")
            print("  (If this is a quota error, re-run tomorrow - "
                  "the script resumes automatically.)")
            sys.exit(1)
    print(f"Done: {done} videos unlisted.")


if __name__ == "__main__":
    main()
