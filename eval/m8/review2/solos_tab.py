"""solos_tab.py: reads solos.json; prints the per-song table of the base and the arms, and the bar's pooled lines."""
import json, numpy as np
R = json.load(open('solos.json'))
f = lambda x: '-' if x is None else '%.3f' % x
print('song | humans solos per chart | arm: n_ours cover outside (changed)')
for lab, r in R.items():
    if r['base']['split_runs'] == 0 and not any(r['changed'].values()):
        continue
    print(lab, r['n_humans_solos'], ' | base', r['base']['n_ours'], f(r['base']['cover']), f(r['base']['outside']), '| near', r['base']['near'], r['base']['near_measures'], 'm', r['base']['near_onsets'], 'on')
    for a in ('S1', 'S2', 'S3', 'S3b'):
        x = r[a]
        print('   ', a, x['n_ours'], f(x['cover']), f(x['outside']), 'CHANGED' if r['changed'][a] else 'same', x['spans_s'] if r['changed'][a] else '')
print()
for a in ('S1', 'S2', 'S3', 'S3b'):
    ch = [l for l, r in R.items() if r['changed'][a]]
    dc = [(R[l][a]['cover'] - R[l]['base']['cover']) for l in ch if R[l][a]['cover'] is not None and R[l]['base']['cover'] is not None]
    do = [(R[l][a]['outside'] - R[l]['base']['outside']) for l in ch if R[l][a]['outside'] is not None and R[l]['base']['outside'] is not None]
    fall = [l for l in ch if R[l][a]['cover'] is not None and R[l]['base']['cover'] is not None and R[l][a]['cover'] < R[l]['base']['cover'] - 1e-9]
    print(a, 'changed', ch, '| mean d cover (songs with humans solos) %.3f n=%d | mean d outside %.3f n=%d | cover falls: %s' % (np.mean(dc) if dc else 0, len(dc), np.mean(do) if do else 0, len(do), fall))
    # all-23 pooled
    cb = [r['base']['cover'] for r in R.values() if r['base']['cover'] is not None]
    ca = [r[a]['cover'] for r in R.values() if r['base']['cover'] is not None]
    ob = [r['base']['outside'] for r in R.values() if r['base']['outside'] is not None]
    oa = [r[a]['outside'] for r in R.values() if r['base']['outside'] is not None]
    print('   pooled over songs: cover %.3f -> %.3f (n=%d); outside %.3f -> %.3f (n=%d)' % (np.mean(cb), np.mean(ca), len(cb), np.mean(ob), np.mean(oa), len(ob)))
