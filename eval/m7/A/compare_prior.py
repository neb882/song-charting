"""compare_prior.py: the rebuilt base arm against today's earlier runs (arm "prior", mkprior.sh: v031, gate3-final-stress,
set20-main), track by track. Reads both arms' notes.chart (scan_notes.cjs); writes ../base_vs_prior.json and prints, per
instrument and level, how many songs are identical (every note's tick, type, length and flags) and the differing labels."""
import json, os
from pathlib import Path
import alib

res = {}
for st in ('refs', 'stress', 'set20'):
    b, p = alib.KEEP / 'base' / st / 'songs', alib.KEEP / 'prior' / st / 'songs'
    if not b.exists():
        continue
    for lab in sorted(os.listdir(b)):
        if not (p / lab).exists():
            continue
        sb, sp = alib.scan(b / lab), alib.scan(p / lab)
        tb = {(t['instrument'], t['difficulty']): t['notes'] for t in sb['tracks']}
        tp = {(t['instrument'], t['difficulty']): t['notes'] for t in sp['tracks']}
        key = lambda ns: sorted((n['tick'], n['type'], n.get('length'), tuple(sorted(n['flags']))) for n in ns)
        r = {'tempo_same': [(t['tick'], round(t['beatsPerMinute'], 3)) for t in sb['tempos']] ==
                           [(t['tick'], round(t['beatsPerMinute'], 3)) for t in sp['tempos']]}
        for k in sorted(set(tb) | set(tp)):
            a, c = tb.get(k), tp.get(k)
            if a is None or c is None:
                r['/'.join(k)] = 'missing in ' + ('base' if a is None else 'prior')
                continue
            ka, kc = key(a), key(c)
            same = ka == kc
            r['/'.join(k)] = 'same' if same else {'n_base': len(ka), 'n_prior': len(kc),
                                                  'common': len(set(ka) & set(kc))}
        res[lab] = r
out = Path(__file__).resolve().parent.parent / 'base_vs_prior.json'
out.write_text(json.dumps(res, indent=1))
keys = sorted({k for r in res.values() for k in r if k != 'tempo_same'})
print('tempo map same:', sum(r['tempo_same'] for r in res.values()), 'of', len(res),
      [l for l, r in res.items() if not r['tempo_same']])
for k in keys:
    diff = [l for l, r in res.items() if r.get(k) != 'same']
    print(k, 'same', len(res) - len(diff), 'differ', diff)
