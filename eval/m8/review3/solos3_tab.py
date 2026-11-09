"""solos3_tab.py: reads solos3.json; prints per-song table (n, cover, outside; spans of changed arms) and the bar per arm."""
import json, numpy as np
R = json.load(open('<scratch>/solos3.json')); A = ['M', 'Mc', 'Mn', 'M+S2', 'T', 'M+S2+T']
f = lambda x: '-' if x is None else '%.3f' % x
for lab, r in R.items():
    if not any(r['changed'].values()): continue
    b = r['base']
    print(lab, 'humans', r['n_humans_solos'], '| base n', b['n_ours'], 'cov', f(b['cover']), 'out', f(b['outside']), 'time', b['o_time_s'], b['spans_s'])
    for a in A:
        if r['changed'][a]:
            x = r[a]; print('   ', a, 'n', x['n_ours'], 'cov', f(x['cover']), 'out', f(x['outside']), 'time', x['o_time_s'], x['spans_s'])
print()
for a in A:
    ch = [l for l, r in R.items() if r['changed'][a]]
    ok = [l for l in ch if R[l]['base']['cover'] is not None]
    dc = {l: R[l][a]['cover'] - R[l]['base']['cover'] for l in ok}
    do = {l: R[l][a]['outside'] - R[l]['base']['outside'] for l in ok if R[l][a]['outside'] is not None and R[l]['base']['outside'] is not None}
    mc, mo = (np.mean(list(dc.values())) if dc else 0), (np.mean(list(do.values())) if do else 0)
    fall = [l for l, v in dc.items() if v < -0.02]
    print(a, 'changed', ch, '| mean d cover %.3f, mean d outside %.3f (n=%d) | falls > .02: %s | bar: %s' % (mc, mo, len(dc), fall,
          'PASS' if dc and mc > 0 and mo < mc / 2 and not fall else 'FAIL'))
    print('   per song d cover/outside:', {l: (round(dc[l], 3), round(do.get(l, float('nan')), 3)) for l in dc})
