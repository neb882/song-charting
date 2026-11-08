"""diag2.py: reads the songs (clib) and $M8_SHM/m8c/pitch/*.json; on our fast-run pairs matched to the primary chart
where the human moves, the tracker's sign accuracy (a) by the pair's confidence (the lower of the two periodicities)
quartile, pooled over songs; (b) octave-folded (the pitch change mapped into [-6, +6) semitones) per song and pooled;
(c) the size of the tracker's pitch steps (share >= 3, >= 7, >= 12 semitones). Writes diag2.json, prints it."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import clib, analyze as A
r3 = A.r3
out = {'per_song_fold': {}}
pool = {t: {'conf': [], 'ok': [], 'okf': [], 'mag': []} for t in A.TRACKERS}
for s in clib.songs():
    p = os.path.join(A.PITCH, s['label'] + '.json')
    if not os.path.exists(p):
        continue
    P = json.load(open(p)); co = s['ours']; ro = s['humans'][0]['ons']
    rid = clib.fast_runs(np.array([o['t'] for o in co])); fp = A.fast_pairs(ro, co, rid)
    pos = {j: n for n, j in enumerate(P['idx'])}
    row = {}
    for t in A.TRACKERS:
        okf = []
        for j, ii in fp.items():
            h = A.hdir(ro, *ii)
            a, b = P[t][pos[j - 1]], P[t][pos[j]]
            if a is None or b is None:
                continue
            d = b - a
            pool[t]['mag'].append(abs(d))
            if h == 0 or d == 0:
                continue
            f = (d + 6) % 12 - 6
            pool[t]['conf'].append(min(P[t + '_conf'][pos[j - 1]], P[t + '_conf'][pos[j]]))
            pool[t]['ok'].append(int(np.sign(d) == h))
            if abs(f) >= 0.5:
                okf.append(int(np.sign(f) == h)); pool[t]['okf'].append(int(np.sign(f) == h))
        row[t] = (r3(np.mean(okf)) if okf else None, len(okf))
    out['per_song_fold'][s['label']] = row
for t, d in pool.items():
    c, ok = np.array(d['conf']), np.array(d['ok'])
    q = np.percentile(c, [25, 50, 75])
    bins = np.digitize(c, q)
    m = np.array(d['mag'])
    out[t] = {'sign_by_conf_quartile': [(r3(ok[bins == k].mean()), int((bins == k).sum())) for k in range(4)],
              'conf_quartile_edges': [r3(x) for x in q],
              'sign_all': (r3(ok.mean()), len(ok)), 'sign_octave_folded': (r3(np.mean(d['okf'])), len(d['okf'])),
              'step_share_ge3_ge7_ge12': [r3((m >= k).mean()) for k in (3, 7, 12)], 'n_steps': len(m)}
json.dump(out, open(os.path.join(HERE, 'diag2.json'), 'w'), indent=1)
print(json.dumps(out))
