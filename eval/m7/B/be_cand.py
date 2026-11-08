"""M7-01 B-e candidates, scored on today's charts without a build. Reads what be.py reads; writes be_cand.json.
K(N): in our runs of 4+ kicks at gaps of a 16th or less whose rate is at least N kicks a second, every second kick
(the 2nd, 4th, ... of the run) is removed; K2x: the run's double-kick (Expert+) kicks removed instead. An onset left
with no note is gone. Measures: kicks removed, removal precision (no human kick within 50 ms), drums onset F1@50
change and kick F1@50 change (mean over the charts), per song. Prints one line per song."""
import json, sys
import numpy as np
from be import Chart, scan, kicks, TOL
from common import songs, build, paths, rj, S
from stats import f1, near_any

def kick_runs(c):
    kt = [(t, k) for k, t in zip(c.ticks, c.t) if any(n['type'] == 'kick' for n in c.g[k])]
    runs, i, s = [], 0, c.res / 4 + 1
    while i < len(kt):
        j = i
        while j + 1 < len(kt) and kt[j + 1][1] - kt[j][1] <= s: j += 1
        if j - i + 1 >= 4: runs.append(kt[i:j + 1])
        i = j + 1
    return runs

def apply(c, drop_kick_ticks, drop_2x_ticks=()):
    on, kt = [], []
    for k, t in zip(c.ticks, c.t):
        ns = [n for n in c.g[k] if not (n['type'] == 'kick' and (k in drop_kick_ticks or (k in drop_2x_ticks and 'doubleKick' in n['flags'])))]
        if ns: on.append(t)
        if any(n['type'] == 'kick' for n in ns): kt.append(t)
    return np.array(on), np.array(kt)

res = {}
for lab, st, sid in songs():
    c = build(lab, st, sid); P = paths(st, sid)
    hum = {k: h for k, h in c['humans'].items() if 'drums' in h['parts']}
    if not hum: continue
    folder = P['run'] / rj(P['run'] / 'summary.json')['songs'][sid]['folder']
    ours = Chart(scan(folder), c['ours']['shift_ms'])
    alts = dict(P['alts'])
    H = {k: Chart(scan((P['refdir'] if k == 'primary' else alts[k]) / 'ref'), h['shift_ms']) for k, h in hum.items()}
    hk = {k: np.array([t for kk, t in zip(h.ticks, h.t) if any(n['type'] == 'kick' for n in h.g[kk])]) for k, h in H.items()}
    sp = {k: (h.t[0], h.t[-1]) for k, h in H.items()}
    on0, kt0 = apply(ours, set())
    base = {k: (f1(H[k].t, on0, sp[k]), f1(hk[k], kt0, sp[k])) for k in H}
    runs = kick_runs(ours)
    r = {}
    for name, N in (('K8', 8), ('K10', 10), ('K12', 12), ('K2x', 0)):
        drop, drop2 = set(), set()
        for run in runs:
            rate = (len(run) - 1) / max(run[-1][0] - run[0][0], 1e-6)
            if rate < N: continue
            if name == 'K2x': drop2 |= {k for _, k in run}
            else: drop |= {k for _, k in run[1::2]}
        on, kt = apply(ours, drop, drop2)
        removed = np.array(sorted(set(kt0) - set(kt)))
        prec = float((~near_any(removed, list(hk.values()), TOL)).mean()) if len(removed) else None
        r[name] = {'kicks_removed': len(removed), 'precision': prec,
                   'onset_f1_change': float(np.mean([f1(H[k].t, on, sp[k]) - base[k][0] for k in H])),
                   'kick_f1_change': float(np.mean([f1(hk[k], kt, sp[k]) - base[k][1] for k in H])),
                   'kicks_per_s_after': len(kt) / (sp[next(iter(H))][1] - sp[next(iter(H))][0])}
    r['onset_f1'] = float(np.mean([b[0] for b in base.values()])); r['kick_f1'] = float(np.mean([b[1] for b in base.values()]))
    r['humans_onset_agree'] = float(np.mean([f1(H['primary'].t, H[k].t, sp['primary']) for k in H if k != 'primary'])) if 'primary' in H and len(H) > 1 else None
    res[lab] = r
    print(lab, {k: (v['kicks_removed'], v['precision'] and round(v['precision'], 2), round(v['onset_f1_change'], 4)) for k, v in r.items() if isinstance(v, dict)}, flush=True)
json.dump(res, open(sys.argv[1], 'w'), indent=1)
