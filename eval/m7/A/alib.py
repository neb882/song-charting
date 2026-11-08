"""alib.py: part A's shared loader. Reads an arm's kept build (<shm>/m7-Akeep/<arm>/<set>: songs/<label>/notes.chart,
report.min.json, scores/ or stress_scores/) and the human charts the scores point to (via scan_notes.cjs); prints nothing.
Songs are labelled: the references by their public ids, the stress set by its ids, the 20-song set s01-s13 (ids sorted)."""
import json, os, pickle, hashlib, re, sys, subprocess
from pathlib import Path
import numpy as np
sys.path.insert(0, '<wt>/orch/eval/scorer')
import score as S  # noqa: E402

KEEP = Path('<shm>/m7-Akeep')
CACHE = KEEP / 'scancache'
WORK = {'refs': '$DEV/golden/work', 'stress': '$DEV/golden/stress-work',
        'set20': '$DEV/golden/set20-work'}
os.environ.setdefault('SONGCHARTER_SCAN_CHART', '<wt>/base-main/tools/scan-chart/scan.cjs')


def scan(folder):
    folder = str(folder)
    st = max(os.stat(os.path.join(folder, f)).st_mtime for f in os.listdir(folder))
    key = hashlib.sha1(f'{folder}|{st}'.encode()).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f'{key}.pkl'
    if p.exists():
        return pickle.loads(p.read_bytes())
    sc = S.scan(folder)
    sc = {k: sc.get(k) for k in ('resolution', 'tempos', 'tracks', 'delay', 'chart_offset')}
    p.write_bytes(pickle.dumps(sc))
    return sc


def songs(arm_set_dir, set_name):
    """[{label, id, cand, octave, bpm, charts: [{k, ref, ref_shift, cand_shift}], humans: [{k, ref, cand, ...}]}]"""
    d = Path(arm_set_dir)
    out = []
    if set_name == 'refs':
        for f in sorted((d / 'scores').glob('*.score.json')):
            sid = f.name.split('.')[0]
            j = json.loads(f.read_text())
            out.append({'id': sid, 'label': sid, 'charts': [_chart('primary', j)], 'humans': []})
    else:
        files = sorted((d / 'stress_scores').glob('*.json'))
        ids = sorted({f.name.split('.')[0] for f in files})
        lab = {i: (f's{n + 1:02d}' if set_name == 'set20' else i) for n, i in enumerate(ids)}
        for sid in ids:
            charts, humans = [], []
            for f in files:
                parts = f.name.split('.')
                if parts[0] != sid:
                    continue
                j = json.loads(f.read_text())
                if parts[1] == 'ours':
                    charts.append(_chart(parts[2], j))
                else:
                    h = _chart(parts[2], j)
                    h['cand_dir'] = j['cand']
                    humans.append(h)
            charts.sort(key=lambda c: (c['k'] != 'primary', c['k']))
            humans.sort(key=lambda c: c['k'])
            out.append({'id': sid, 'label': lab[sid], 'charts': charts, 'humans': humans})
    for s in out:
        sd = d / 'songs' / s['label']
        s['cand'] = str(sd)
        rep = json.loads((sd / 'report.min.json').read_text())
        s['octave'] = (rep.get('grid') or {}).get('octave')
        s['bpm'] = (rep.get('grid') or {}).get('bpm_median')
        s['work'] = os.path.join(WORK[set_name], s['id'])
        s['set'] = set_name
    return out


def _chart(k, j):
    al = j['alignment']
    return {'k': k, 'ref': os.path.join(j['ref'], 'ref'), 'ref_shift': float(al['ref_delay_ms']), 'cand_shift': float(al['cand_total_shift_ms']),
            'span': tuple(j['ref_span_s'])}


def track(sc, ins, dif='expert'):
    for t in sc.get('tracks') or []:
        if t['instrument'] == ins and t['difficulty'] == dif and t['notes']:
            return t['notes']
    return None


def onsets(sc, ins, shift, span=None, dif='expert'):
    """score.py's onsets plus each onset's held length in ms (msLength) and the chart's own ms."""
    notes = track(sc, ins, dif)
    if notes is None:
        return None
    ons = S.onsets(notes, shift, ins)
    ms = {}
    for n in notes:
        ms[n['tick']] = max(ms.get(n['tick'], 0), n.get('msLength') or 0)
    tick_of = {}
    for n in notes:
        tick_of.setdefault(round((n['ms'] + shift) / 1000.0, 9), n['tick'])
    for o in ons:
        o['tick'] = tick_of[round(o['t'], 9)]
        o['len_ms'] = ms[o['tick']]
    if span is not None:
        lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
        ons = [o for o in ons if lo <= o['t'] <= hi]
    return ons


def pairs(ro, co, tol):
    return S.match(np.array([o['t'] for o in ro]), np.array([o['t'] for o in co]), tol)


def f1(ro, co, tol, span):
    p = pairs(ro, co, tol)
    ct = np.array([o['t'] for o in co])
    return S.prf(len(p), len(ro), S.n_cand_eff(p, ct, span))['f1']


def bpm_at(sc, ms):
    """The chart's tempo (BPM) at its own ms."""
    tem = sc.get('tempos') or []
    b = tem[0]['beatsPerMinute'] if tem else 120.0
    for t in tem:
        if t['msTime'] <= ms:
            b = t['beatsPerMinute']
        else:
            break
    return b


def state(o):
    return S.played_state(o)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def boot(diffs, n=10000, seed=7):
    """Paired bootstrap over songs: mean of per-song differences and its 95 % CI."""
    d = np.array([x for x in diffs if x is not None], dtype=float)
    if len(d) == 0:
        return None
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return {'mean': round(float(d.mean()), 4), 'lo': round(float(np.percentile(m, 2.5)), 4),
            'hi': round(float(np.percentile(m, 97.5)), 4), 'n': int(len(d))}
