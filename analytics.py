"""
YouTube Analytics collection (2026-10 compounding loop).

Once the channel token carries yt-analytics.readonly (scripts/reauth_youtube.py),
this pulls per-video watch metrics for recent uploads into
seed_data/analytics/YYYY-MM-DD.json. The tuner reads them; nothing here
writes to YouTube. Without the scope it does nothing and says so.

Metrics: views, engaged views where available, minutes watched, average view
duration, average percentage viewed (retention), likes, comments, shares,
subscribers gained.
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List

import config

OUT_DIR = os.path.join(config.DATA_FOLDER, 'analytics')
_METRICS = ('views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,'
            'likes,comments,shares,subscribersGained')


def recent_video_ids(n: int = 150) -> List[str]:
    """Newest first, from the title history the uploader maintains."""
    try:
        from youtube_uploader import load_title_history
        return [vid for vid, _ in load_title_history()[:n]]
    except Exception:
        return []


def fetch(video_ids: List[str]) -> Dict[str, Dict]:
    import youtube_uploader as yu
    ya = yu.get_analytics_service()
    if ya is None:
        print("Analytics: token lacks yt-analytics.readonly -- skipped "
              "(run scripts/reauth_youtube.py once)")
        return {}
    end = datetime.utcnow().date()
    start = end - timedelta(days=120)
    out: Dict[str, Dict] = {}
    names = _METRICS.split(',')
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        try:
            r = ya.reports().query(ids='channel==MINE', startDate=start.isoformat(),
                                   endDate=end.isoformat(), metrics=_METRICS,
                                   dimensions='video', filters='video==' + ','.join(chunk),
                                   maxResults=50).execute()
        except Exception as e:
            msg = str(e)
            if 'accessNotConfigured' in msg or 'has not been used' in msg or 'disabled' in msg:
                print("Analytics: the YouTube Analytics API is not enabled for this Google "
                      "Cloud project -- enable 'YouTube Analytics API' in the Cloud Console")
            else:
                print(f"Analytics query failed: {msg[:200]}")
            return out
        cols = [h['name'] for h in r.get('columnHeaders', [])]
        for row in r.get('rows', []) or []:
            rec = dict(zip(cols, row))
            vid = rec.pop('video', None)
            if vid:
                out[vid] = {k: rec.get(k) for k in names}
    return out


def collect() -> str:
    """Fetch and save today's per-video metrics. Returns the file path or ''."""
    data = fetch(recent_video_ids())
    if not data:
        return ''
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, datetime.utcnow().strftime('%Y-%m-%d') + '.json')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('{\n' + ',\n'.join(f'"{k}": {json.dumps(v)}' for k, v in data.items()) + '\n}\n')
    print(f"Analytics: {len(data)} videos -> {os.path.basename(path)}")
    return path


def latest() -> Dict[str, Dict]:
    try:
        files = sorted(f for f in os.listdir(OUT_DIR) if f.endswith('.json'))
        with open(os.path.join(OUT_DIR, files[-1]), encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


if __name__ == '__main__':
    print(collect() or 'nothing collected')
