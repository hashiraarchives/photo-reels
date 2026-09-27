"""
Competitor / own-channel research via the YouTube Data API (read-only).

    python scripts/yt_research.py own                 # AAP's recent uploads + stats
    python scripts/yt_research.py find "<name>"       # resolve a channel by name
    python scripts/yt_research.py channel <id> [N]    # last N uploads + stats, JSON dump
"""
import io
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault('GITHUB_ACTIONS', 'true')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import youtube_uploader as u  # noqa: E402

OUT = os.path.join(HERE, 'output', 'research')
os.makedirs(OUT, exist_ok=True)


def dur_s(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def uploads(yt, channel_id, n):
    ch = yt.channels().list(part='contentDetails,snippet,statistics,brandingSettings',
                            id=channel_id).execute()['items'][0]
    pl = ch['contentDetails']['relatedPlaylists']['uploads']
    ids, token = [], None
    while len(ids) < n:
        r = yt.playlistItems().list(part='contentDetails', playlistId=pl, maxResults=50,
                                    pageToken=token).execute()
        ids += [i['contentDetails']['videoId'] for i in r['items']]
        token = r.get('nextPageToken')
        if not token:
            break
    vids = []
    for i in range(0, min(len(ids), n), 50):
        r = yt.videos().list(part='snippet,statistics,contentDetails,status',
                             id=','.join(ids[i:i + 50])).execute()
        vids += r['items']
    return ch, vids


def row(v):
    st, sn = v.get('statistics', {}), v['snippet']
    pub = datetime.fromisoformat(sn['publishedAt'].replace('Z', '+00:00'))
    age_d = max((datetime.now(timezone.utc) - pub).total_seconds() / 86400, 0.01)
    views = int(st.get('viewCount', 0))
    return {
        'id': v['id'], 'published': sn['publishedAt'][:16], 'age_days': round(age_d, 1),
        'dur_s': dur_s(v['contentDetails']['duration']),
        'views': views, 'views_per_day': round(views / age_d, 1),
        'likes': int(st.get('likeCount', 0)), 'comments': int(st.get('commentCount', 0)),
        'title': sn['title'], 'description': sn.get('description', ''),
        'tags': sn.get('tags', []),
        'thumb': (sn.get('thumbnails', {}).get('maxres') or sn.get('thumbnails', {}).get('high') or {}).get('url'),
        'privacy': v.get('status', {}).get('privacyStatus'),
    }


def main():
    yt = u.get_authenticated_service()
    cmd = sys.argv[1]
    if cmd == 'find':
        r = yt.search().list(part='snippet', q=sys.argv[2], type='channel', maxResults=6).execute()
        for it in r['items']:
            cid = it['snippet']['channelId']
            c = yt.channels().list(part='statistics,snippet', id=cid).execute()['items'][0]
            s = c['statistics']
            print(f"{cid} | {c['snippet']['title']} | {c['snippet'].get('customUrl')} | "
                  f"subs {s.get('subscriberCount')} | videos {s.get('videoCount')} | views {s.get('viewCount')}")
        return
    if cmd == 'own':
        cid = yt.channels().list(part='id', mine=True).execute()['items'][0]['id']
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    else:
        cid = sys.argv[2]
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    ch, vids = uploads(yt, cid, n)
    rows = [row(v) for v in vids]
    name = ch['snippet'].get('customUrl') or cid
    with open(os.path.join(OUT, f"{name.strip('@')}.json"), 'w', encoding='utf-8') as f:
        json.dump({'channel': {'id': cid, 'title': ch['snippet']['title'],
                               'description': ch['snippet'].get('description'),
                               'keywords': ch.get('brandingSettings', {}).get('channel', {}).get('keywords'),
                               'stats': ch['statistics']}, 'videos': rows}, f, indent=1, ensure_ascii=False)
    s = ch['statistics']
    print(f"== {ch['snippet']['title']} ({name}) subs {s.get('subscriberCount')} "
          f"videos {s.get('videoCount')} views {s.get('viewCount')} | fetched {len(rows)}")
    for r in rows:
        kind = 'SHORT' if r['dur_s'] <= 60 else f"{r['dur_s'] // 60}m"
        print(f"{r['published']} {kind:>5} {r['views']:>8,}v {r['views_per_day']:>9,.0f}/d "
              f"{r['likes']:>5}L {r['comments']:>4}C {r['privacy'] or '':>8} | {r['title'][:70]}")


if __name__ == '__main__':
    main()
