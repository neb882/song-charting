"""diag.py: reads the songs (clib) and <shm>/m8c/pitch/*.json; prints and writes diag.json: per tracker, on our
fast-run pairs matched to the primary chart where the human moves (up or down), the share the tracker's sign matches
(0.5 = no information), overall and for pitch steps of at least 1 and 3 semitones, plus our own sign accuracy."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import clib, analyze as A
out = {}
pool = {}
for s in clib.songs():
    p = os.path.join(A.PITCH, s['label'] + '.json')
    if not os.path.exists(p):
        continue
    P = json.load(open(p)); co = s['ours']; ro = s['humans'][0]['ons']
    rid = clib.fast_runs(np.array([o['t'] for o in co])); fp = A.fast_pairs(ro, co, rid)
    pos = {j: n for n, j in enumerate(P['idx'])}
    row = {}
    for t in A.TRACKERS + ('ours',):
        res = {'any': [], 'ge1': [], 'ge3': []}
        for j, ii in fp.items():
            h = A.hdir(ro, *ii)
            if h == 0:
                continue
            if t == 'ours':
                d = A.mlane(co[j]) - A.mlane(co[j - 1]); mag = 9
            else:
                a, b = P[t][pos[j - 1]], P[t][pos[j]]
                if a is None or b is None:
                    continue
                d = b - a; mag = abs(d)
            if d == 0:
                continue
            ok = int(np.sign(d) == h)
            res['any'].append(ok)
            if mag >= 1: res['ge1'].append(ok)
            if mag >= 3: res['ge3'].append(ok)
        row[t] = {k: (round(float(np.mean(v)), 3) if v else None, len(v)) for k, v in res.items()}
        for k, v in res.items():
            pool.setdefault(t, {}).setdefault(k, []).extend(v)
    out[s['label']] = row
    print(s['label'], row)
out['pooled_pairs'] = {t: {k: (round(float(np.mean(v)), 3) if v else None, len(v)) for k, v in d.items()} for t, d in pool.items()}
print('pooled', out['pooled_pairs'])
json.dump(out, open(os.path.join(HERE, 'diag.json'), 'w'), indent=1)
