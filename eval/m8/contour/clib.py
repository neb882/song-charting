"""clib.py: the M8 contour spike's shared loader. Reads main's kept runs (our Expert guitar from the run folder's
notes.chart; the human charts the scores point to, notes only, through score.py's scan_notes.cjs reader) and finds the
kept guitar stem; prints nothing. Songs are labelled by their public ids (references, stress set) or s01-s13."""
import glob
import json
import os
import pickle
import hashlib
import sys

import numpy as np

sys.path.insert(0, '<wt>/orch/eval/scorer')
os.environ.setdefault('SONGCHARTER_SCAN_CHART', '<checkout>/tools/scan-chart/scan.cjs')
import score as S  # noqa: E402

G = '$DEV/golden'
CACHE = '<shm>/m8c/scan'
SETS = {  # set: (run with our charts, run whose stress_scores hold the alt charts' alignment, kept work folder)
    'refs': (f'{G}/v031', None, f'{G}/work'),
    'stress': (f'{G}/gate3-final-stress', f'{G}/gate3-new-stress', f'{G}/stress-work'),
    'set20': (f'{G}/set20-main', f'{G}/set20-main', f'{G}/set20-work'),
}
TOL = 0.050


def scan(folder):
    st = max(os.stat(os.path.join(folder, f)).st_mtime for f in os.listdir(folder))
    key = hashlib.sha1(f'{folder}|{st}'.encode()).hexdigest()
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, key + '.pkl')
    if os.path.exists(p):
        return pickle.load(open(p, 'rb'))
    sc = S.scan(folder)
    sc = {'tracks': [t for t in sc.get('tracks') or [] if t['instrument'] == 'guitar' and t['difficulty'] == 'expert']}
    pickle.dump(sc, open(p, 'wb'))
    return sc


def gonsets(folder, shift, span=None):
    for t in scan(folder)['tracks']:
        if t['notes']:
            ons = S.onsets(t['notes'], shift, 'guitar')
            if span is not None:
                lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
                ons = [o for o in ons if lo <= o['t'] <= hi]
            return ons
    return None


def stem(work):
    for name in ('guitar', 'other'):
        c = sorted(glob.glob(os.path.join(work, 'stems', '*', name + '.wav')), key=os.path.getmtime)
        if c:
            return c[-1], name
    return None, None


def songs():
    """[{label, set, ours: onsets (primary frame), span, humans: [{k, ons}] primary first, stem, stem_kind}]"""
    out = []
    for set_name, (run, altrun, work) in SETS.items():
        prim = sorted(glob.glob(f'{run}/scores/*.score.json'))
        ids = [os.path.basename(f).split('.')[0] for f in prim]
        lab = {i: (f's{n + 1:02d}' if set_name == 'set20' else i) for n, i in enumerate(sorted(ids))}
        for sid, f in zip(ids, prim):
            j = json.load(open(f))
            al = j['alignment']
            span = tuple(j['ref_span_s'])
            ours = gonsets(os.path.join(run, sid), al['cand_total_shift_ms'], span)
            hp = gonsets(os.path.join(j['ref'], 'ref'), al['ref_delay_ms'])
            if not ours or not hp:
                continue
            humans = [{'k': 'primary', 'ons': hp}]
            if altrun:
                for hf in sorted(glob.glob(f'{altrun}/stress_scores/{sid}.human.*.json')):
                    hj = json.load(open(hf))
                    k = os.path.basename(hf).split('.')[2]
                    ho = gonsets(hj['cand'], hj['alignment']['cand_total_shift_ms'])
                    if ho:
                        humans.append({'k': k, 'ons': ho})
            wav, kind = stem(os.path.join(work, sid))
            ge = j['tracks'].get('guitar/expert') or {}
            out.append({'label': lab[sid], 'set': set_name, 'ours': ours, 'span': span, 'humans': humans,
                        'stem': wav, 'stem_kind': kind,
                        'score_py': {'contour': (ge.get('lane_direction_agreement') or {}).get('value'),
                                     'exact': (ge.get('exact_lane_agreement') or {}).get('value'),
                                     'f1_50': (ge.get('onset_50ms') or {}).get('f1')}})
    return out


def fast_runs(t, per_s=8, min_n=8):
    """M7-01 A-e's definition: run ids per onset (-1 outside), runs of >= min_n onsets each <= 1/per_s s apart."""
    n, rid, i, r = len(t), -np.ones(len(t), int), 0, 0
    while i < n:
        j = i
        while j + 1 < n and t[j + 1] - t[j] <= 1.0 / per_s + 1e-9:
            j += 1
        if j - i + 1 >= min_n:
            rid[i:j + 1] = r
            r += 1
        i = j + 1
    return rid


def mlane(o):
    return float(np.mean(o['lanes']))


def boot(diffs, n=10000, seed=7):
    d = np.array([x for x in diffs if x is not None], dtype=float)
    if len(d) == 0:
        return None
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return {'mean': round(float(d.mean()), 3), 'lo': round(float(np.percentile(m, 2.5)), 3),
            'hi': round(float(np.percentile(m, 97.5)), 3), 'n': int(len(d))}
