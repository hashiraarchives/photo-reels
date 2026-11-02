"""
The compounding loop (2026-10): measure every format, lean into what works.

Each upload is logged with its format (seed_data/upload_log.jsonl). Once a
video is a few days old the tuner measures it at the SAME AGE as every other
video -- views in its first 3 days, plus retention (average % viewed) when
YouTube Analytics is available -- relative to the channel's recent median
for that kind of video (short vs long-form). Formats ("arms") then get a
share of tomorrow's output by how well they have done:

  shorts     star / theme / timeline, and within themes each story theme
  long-form  theme day vs other days

Every arm keeps a floor share so nothing is ever starved of new data (a
format that was unlucky once gets more chances), and evidence is shrunk
toward "average" until an arm has several videos. A short that beats the
median 3x or more is a BREAKOUT: its star or theme is queued for follow-ups
for a week -- one hit lifting a channel is how small channels jump.

Output: seed_data/tuning.json, read by create_short / create_slideshow.
Read-only against YouTube.
"""
import json
import math
import os
from datetime import datetime, timedelta
from statistics import median
from typing import Dict, List, Optional

import config

LOG = os.path.join(config.DATA_FOLDER, 'upload_log.jsonl')
STATS_DIR = os.path.join(config.DATA_FOLDER, 'stats')
CACHE = os.path.join(config.DATA_FOLDER, 'analytics', 'first_days.json')
OUT = os.path.join(config.DATA_FOLDER, 'tuning.json')
AGE_DAYS = 3                 # compare every video on its first 3 days
LAG_DAYS = 2                 # analytics settle ~2 days after the fact
BREAKOUT = 3.0               # x the median
TEMPERATURE = 0.45           # lower = lean harder into winners
PRIOR_N = 3                  # shrink an arm's mean toward 0 with this many pseudo-videos
FLOOR = 0.08                 # minimum share per arm


def _load_log() -> List[Dict]:
    out = []
    try:
        with open(LOG, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
    except FileNotFoundError:
        pass
    return out


def _arm(rec: Dict) -> Optional[str]:
    if rec.get('kind') == 'short':
        fmt = rec.get('format') or ''
        if fmt == 'theme' and rec.get('theme'):
            return f"short:theme:{rec['theme']}"
        if fmt in ('star', 'timeline', 'theme'):
            return f"short:{fmt}"
        return None
    if rec.get('kind') == 'long':
        return f"long:theme:{rec['theme_key']}" if rec.get('theme_key') else (
            'long:star' if rec.get('star') else 'long:mixed')
    return None


def _published(rec: Dict) -> Optional[datetime]:
    for k in ('publish_at', 'uploaded'):
        try:
            return datetime.strptime(rec.get(k, '')[:16], '%Y-%m-%dT%H:%M')
        except ValueError:
            continue
    return None


def _cache() -> Dict:
    try:
        with open(CACHE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(c: Dict):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, 'w', encoding='utf-8') as f:
        f.write('{\n' + ',\n'.join(f'"{k}": {json.dumps(v)}' for k, v in sorted(c.items())) + '\n}\n')


def _first_days_from_analytics(ya, vid: str, pub: datetime) -> Optional[Dict]:
    start = pub.date()
    end = start + timedelta(days=AGE_DAYS - 1)
    r = ya.reports().query(ids='channel==MINE', startDate=start.isoformat(), endDate=end.isoformat(),
                           metrics='views,averageViewPercentage', dimensions='day',
                           filters=f'video=={vid}').execute()
    rows = r.get('rows', []) or []
    views = sum(int(x[1]) for x in rows)
    pct = [float(x[2]) for x in rows if x[2] is not None]
    return {'views': views, 'retention': round(sum(pct) / len(pct), 1) if pct else None, 'src': 'analytics'}


def _first_days_from_snapshots(vid: str, pub: datetime) -> Optional[Dict]:
    """Views in the stats snapshot taken closest to AGE_DAYS after publish."""
    best = None
    try:
        files = sorted(f for f in os.listdir(STATS_DIR) if f.endswith('.json'))
    except FileNotFoundError:
        return None
    for f in files:
        try:
            day = datetime.strptime(f[:10], '%Y-%m-%d')
        except ValueError:
            continue
        age = (day - pub).total_seconds() / 86400
        if not (AGE_DAYS - 0.75 <= age <= AGE_DAYS + 1.5):
            continue
        with open(os.path.join(STATS_DIR, f), encoding='utf-8') as fh:
            for row in json.load(fh):
                if row[0] == vid and (best is None or abs(age - AGE_DAYS) < best[0]):
                    best = (abs(age - AGE_DAYS), {'views': row[2], 'retention': None, 'src': 'snapshot'})
    return best[1] if best else None


def measure(log: List[Dict]) -> Dict[str, Dict]:
    """First-days views (+ retention) per logged video old enough to judge."""
    cache = _cache()
    ya = None
    try:
        import youtube_uploader as yu
        ya = yu.get_analytics_service()
    except Exception:
        ya = None
    now = datetime.utcnow()
    for rec in log:
        vid, pub = rec.get('id'), _published(rec)
        if not vid or not pub or vid in cache:
            continue
        if (now - pub).days < AGE_DAYS + (LAG_DAYS if ya else 0):
            continue
        res = None
        if ya is not None:
            try:
                res = _first_days_from_analytics(ya, vid, pub)
            except Exception as e:
                print(f"  tuner: analytics read failed for {vid}: {str(e)[:120]}")
        res = res or _first_days_from_snapshots(vid, pub)
        if res:
            cache[vid] = res
    _save_cache(cache)
    return cache


def _softmax(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    m = max(scores.values())
    ex = {k: math.exp((v - m) / TEMPERATURE) for k, v in scores.items()}
    tot = sum(ex.values())
    w = {k: v / tot for k, v in ex.items()}
    # floor, then renormalise
    w = {k: max(v, FLOOR) for k, v in w.items()}
    tot = sum(w.values())
    return {k: round(v / tot, 3) for k, v in w.items()}


def update() -> Dict:
    log = _load_log()
    measured = measure(log)
    cutoff = datetime.utcnow() - timedelta(days=45)
    samples: Dict[str, List[float]] = {}
    base: Dict[str, List[float]] = {'short': [], 'long': []}
    ret_base: Dict[str, List[float]] = {'short': [], 'long': []}
    rows = []
    for rec in log:
        m = measured.get(rec.get('id'))
        pub = _published(rec)
        if not m or not pub or pub < cutoff:
            continue
        kind = rec.get('kind')
        base.setdefault(kind, []).append(m['views'])
        if m.get('retention') is not None:
            ret_base.setdefault(kind, []).append(m['retention'])
        rows.append((rec, m))
    med = {k: (median(v) if v else 0) for k, v in base.items()}
    rmed = {k: (median(v) if v else None) for k, v in ret_base.items()}
    breakouts, report = [], []
    for rec, m in rows:
        kind, arm = rec.get('kind'), _arm(rec)
        if not arm or not med.get(kind):
            continue
        rel = math.log((m['views'] + 1) / (med[kind] + 1))
        if m.get('retention') is not None and rmed.get(kind):
            rel += 0.5 * math.log(m['retention'] / rmed[kind])      # watching > clicking
        samples.setdefault(arm, []).append(rel)
        if arm.startswith('short:theme:'):
            samples.setdefault('short:theme', []).append(rel)    # the kind as a whole
        if kind == 'short' and m['views'] >= BREAKOUT * med[kind]:
            breakouts.append({'id': rec['id'], 'title': rec.get('title', ''), 'views': m['views'],
                              'star': rec.get('star') or '', 'theme': rec.get('theme') or '',
                              'kind': rec.get('format') or '',
                              'until': (_published(rec) + timedelta(days=AGE_DAYS + 7)).strftime('%Y-%m-%d')})
    score = {a: sum(v) / (len(v) + PRIOR_N) for a, v in samples.items()}

    def arms(prefix, names):
        return {n: score.get(prefix + n, 0.0) for n in names}

    import history_data as hd
    kinds = _softmax(arms('short:', ['star', 'theme', 'timeline']))
    themes = _softmax(arms('short:theme:', [t['key'] for t in hd.THEMES]))
    # A breakout with no star or theme (a timeline reel) still says which KIND
    # of short is working right now: give that kind a 1.5x share for a week.
    live = [b for b in breakouts if b['until'] >= datetime.utcnow().strftime('%Y-%m-%d')]
    for k in {b.get('kind') for b in live}:       # once per kind, not per hit
        if k in kinds:
            kinds[k] *= 1.5
    if live:
        tot = sum(kinds.values())
        kinds = {k: round(v / tot, 3) for k, v in kinds.items()}
    long_theme = score.get('long:theme:couples', 0) * 0.5 + score.get('long:theme:beach', 0) * 0.5
    long_other = (score.get('long:star', 0) + score.get('long:mixed', 0)) / 2
    long_rate = round(min(0.7, max(0.2, 0.35 + 0.5 * (long_theme - long_other))), 2)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    breakouts = [b for b in breakouts if b['until'] >= today]

    for a in sorted(samples, key=lambda k: -score[k]):
        report.append(f"{a:<28} n={len(samples[a]):<3} score={score[a]:+.2f}")
    out = {'updated': today, 'n_measured': len(rows),
           'median_first_days_views': med, 'median_retention': rmed,
           'short_kind_weights': kinds, 'short_theme_weights': themes,
           'long_theme_rate': long_rate,
           'followups': breakouts[-6:], 'report': report}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"Tuner: {len(rows)} videos measured; shorts mix {kinds}; long theme rate {long_rate}"
          + (f"; breakouts {[b['title'][:30] for b in breakouts]}" if breakouts else ''))
    return out


def load() -> Dict:
    """Today's tuning, or {} (callers then use config defaults). A tuning
    file older than a week is ignored rather than trusted."""
    try:
        with open(OUT, encoding='utf-8') as f:
            t = json.load(f)
        if (datetime.utcnow() - datetime.strptime(t.get('updated', '2000-01-01'), '%Y-%m-%d')).days > 7:
            return {}
        if not t.get('n_measured'):
            return {}
        return t
    except Exception:
        return {}


if __name__ == '__main__':
    print(json.dumps(update(), indent=1))
