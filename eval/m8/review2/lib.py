"""lib.py: shared loader for the three checks. Reads the v040 runs' summary.json and score JSONs (alignments), our
charts and the human charts through eval/scorer/score.py's scan (notes, tempo map, solo sections only; a pickle cache
in this folder's cache/ keyed by label); prints nothing. Labels only: refs by public ids, stress by ids, set20 s01-s13."""
import json, os, sys, pickle, hashlib
from pathlib import Path
import numpy as np
os.environ.setdefault('SONGCHARTER_SCAN_CHART', '<wt>/base-main/tools/scan-chart/scan.cjs')
sys.path[:0] = ['<wt>/orch', '<wt>/orch/eval/scorer']
import score as S  # noqa
HERE = Path(__file__).resolve().parent
CACHE = HERE / 'cache'; CACHE.mkdir(exist_ok=True)
G = Path('$DEV/golden'); DEV = Path('$DEV')
REFS = ['all_the_small_things', 'creep', 'drunk_drivers', 'kimochi_warui', 'lucretia', 'take_me_out']
STRESS = ['break', 'pm2', 'sooth', 'troop']
H_TOL = 0.1
rj = lambda p: json.loads(Path(p).read_text())

def scan(folder):
    folder = str(folder)
    st = max(os.stat(os.path.join(folder, f)).st_mtime for f in os.listdir(folder))
    p = CACHE / (hashlib.sha1(f'{folder}|{st}'.encode()).hexdigest() + '.pkl')
    if p.exists():
        return pickle.loads(p.read_bytes())
    sc = S.scan(folder)
    p.write_bytes(pickle.dumps(sc))
    return sc

def songs():
    """[(label, set, id)]"""
    s20 = sorted(s['id'] for s in rj(DEV / 'eval-set20/stress/songs.json'))
    return [(i, 'refs', i) for i in REFS] + [(i, 'stress', i) for i in STRESS] + \
           [('s%02d' % (k + 1), 'set20', sid) for k, sid in enumerate(s20)]

RUN = {'refs': G / 'v040', 'stress': G / 'v040-stress', 'set20': G / 'v040-set20'}

def entry(label, st, sid):
    """{'ours': our chart folder, 'charts': [{k, ref, ref_shift, cand_shift, span}], 'humans': [{k, ref, cand, cand_shift, span}], 'pri': primary's alignment}"""
    run = RUN[st]; ours = run / sid
    out = {'ours': ours, 'charts': [], 'humans': []}
    if st == 'refs':
        files = [(run / 'scores' / f'{sid}.score.json', 'primary', 'ours')]
    else:
        files = []
        for f in sorted((run / 'stress_scores').glob(f'{sid}.*.json')):
            parts = f.name.split('.')
            files.append((f, parts[2], parts[1]))
    for f, k, kind in files:
        j = rj(f); al = j['alignment']
        c = {'k': k, 'ref': os.path.join(j['ref'], 'ref'), 'ref_shift': float(al['ref_delay_ms']),
             'cand_shift': float(al['cand_total_shift_ms']), 'span': tuple(j['ref_span_s']), 'lag': float(al['lag_ms'])}
        if kind == 'ours':
            out['charts'].append(c)
        else:
            c['cand'] = j['cand']
            out['humans'].append(c)
    out['charts'].sort(key=lambda c: (c['k'] != 'primary', c['k']))
    out['humans'].sort(key=lambda c: c['k'])
    return out

def onsets(sc, ins, shift, span=None, dif='expert'):
    notes = None
    for t in sc.get('tracks') or []:
        if t['instrument'] == ins and t['difficulty'] == dif and t['notes']:
            notes = t['notes']
    if notes is None:
        return None
    ons = S.onsets(notes, shift, ins)
    tick_of = {}
    for n in notes:
        tick_of.setdefault(round((n['ms'] + shift) / 1000.0, 9), n['tick'])
    for o in ons:
        o['tick'] = tick_of[round(o['t'], 9)]
    if span is not None:
        lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
        ons = [o for o in ons if lo <= o['t'] <= hi]
    return ons

state = S.played_state
def pairs(ro, co, tol=H_TOL):
    return S.match(np.array([o['t'] for o in ro]), np.array([o['t'] for o in co]), tol)
def is_chord(o):
    return len(set(o['lanes'])) > 1

def solos_of(sc, shift_ms, dif='expert'):
    ph = S.phrases_by_key(sc).get(('guitar', dif)) or {'solos': []}
    return [((x['ms'] + shift_ms) / 1000.0, (x['ms'] + x['msLength'] + shift_ms) / 1000.0) for x in ph['solos']]

def boot(diffs, n=10000, seed=7):
    d = np.array([x for x in diffs if x is not None], dtype=float)
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return {'mean': round(float(d.mean()), 4), 'lo': round(float(np.percentile(m, 2.5)), 4),
            'hi': round(float(np.percentile(m, 97.5)), 4), 'n': int(len(d))}
