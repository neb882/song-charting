"""intro.py (part 3): reads the GPU pm2 chart and the CPU pm2 chart (Expert guitar notes through lib.scan), align.json,
and pm2's five human charts' Expert guitar notes/states; in the GPU chart's first 25 s (chart seconds) compares the
state agreement of the chart as written (M7-02's rule), with every note of the tap region made a tap (the source take is
not on this machine: 'all tap' stands for every source tap kept), and the CPU chart over the same stretch of input
time; writes intro.json; prints the numbers."""
import sys, json
from collections import Counter
sys.path.insert(0, '<scratch>')
from lib import *
al = rj('align.json'); L = al['lag_s'] * 1000
gsc = scan('<shm>/pm2gpu/chart'); e = entry('pm2', 'stress', 'pm2'); osc = scan(e['ours'])
rg = rj('<shm>/pm2gpu/chart/report.json')
go = onsets(gsc, 'guitar', 0.0)
win = [o for o in go if o['t'] <= 25.0]
print('GPU onsets in the first 25 s', len(win), 'states', dict(Counter(state(o) for o in win)))
taps = [o for o in win if state(o) == 'tap']
print('tap-flagged', len(taps), 'first/last tap at', round(taps[0]['t'], 2), round(taps[-1]['t'], 2))
# the tap region of the report's claim: the intro 3.4 - 22.6 s
reg = [o for o in win if 3.3 <= o['t'] <= 22.7]
print('onsets in 3.3-22.7 s', len(reg), 'states', dict(Counter(state(o) for o in reg)))
# fast-run structure of the region (M7-02: runs of 8+ each <=0.125 s apart)
t = np.array([o['t'] for o in go]); fr = np.zeros(len(t), bool); i = 0
while i < len(t):
    j = i
    while j + 1 < len(t) and t[j + 1] - t[j] <= 0.125 + 1e-9: j += 1
    if j - i + 1 >= 8: fr[i:j + 1] = True
    i = j + 1
gaps = np.diff([o['t'] for o in reg]); print('gaps in region: share <=0.125 s', round(float((gaps <= 0.125 + 1e-9).mean()), 3), 'median', round(float(np.median(gaps)), 3), 'fast-run notes in region', int(sum(fr[k] for k, o in enumerate(go) if 3.3 <= o['t'] <= 22.7)))
def all_tap(o): return 'tap'
def st_hopo(os_):
    return [('hopo' if 3.3 <= o['t'] <= 22.7 else state(o)) for o in os_]
def st_all(os_):
    return [('tap' if 3.3 <= o['t'] <= 22.7 else state(o)) for o in os_]
out = {'n_win': len(win), 'n_region': len(reg), 'states_written': dict(Counter(state(o) for o in reg)), 'charts': {}}
for c in e['charts']:
    ro_all = onsets(scan(c['ref']), 'guitar', c['ref_shift'])
    sh = L + c['cand_shift']
    lo, hi = 0.0 + sh / 1000, 25.0 + sh / 1000   # the window in the humans' frame
    ro = [o for o in ro_all if lo - 0.1 <= o['t'] <= hi + 0.1]
    gw = [o for o in onsets(gsc, 'guitar', sh) if lo <= o['t'] <= hi]
    cw = [o for o in onsets(osc, 'guitar', c['cand_shift']) if lo <= o['t'] <= hi]
    row = {'human_onsets': len(ro), 'human_states': dict(Counter(state(o) for o in ro)), 'gpu_onsets': len(gw), 'cpu_onsets': len(cw)}
    for name, co, sts in (('gpu_written', gw, [state(o) for o in gw]), ('gpu_all_tap', gw, st_all([dict(o, t=o['t'] - sh / 1000) for o in gw])),
                          ('gpu_region_all_hopo', gw, st_hopo([dict(o, t=o['t'] - sh / 1000) for o in gw])), ('cpu', cw, [state(o) for o in cw])):
        if sts is None: continue
        p = pairs(ro, co)
        n = len(p); same = sum(1 for i, j in p if state(ro[i]) == sts[j])
        row[name] = {'matched': n, 'agree': round(same / n, 4) if n else None, 'states': dict(Counter(sts)),
                     'confusion_h/o': dict(Counter(f'{state(ro[i])}/{sts[j]}' for i, j in p))}
    # the same agreement restricted to the tap region (human frame)
    rlo, rhi = lo + 3.3, lo + 22.7
    for name in ('gpu_written', 'gpu_all_tap'):
        pass
    out['charts'][c['k']] = row
    print(c['k'], 'human onsets', row['human_onsets'], row['human_states'], '| gpu', row['gpu_onsets'], 'cpu', row['cpu_onsets'])
    for name in ('gpu_written', 'gpu_all_tap', 'gpu_region_all_hopo', 'cpu'):
        print('    ', name, 'matched', row[name]['matched'], 'agree', row[name]['agree'], row[name]['states'])
ag = {n: float(np.mean([r[n]['agree'] for r in out['charts'].values() if r[n]['agree'] is not None])) for n in ('gpu_written', 'gpu_all_tap', 'gpu_region_all_hopo', 'cpu')}
out['mean_agree'] = {k: round(v, 4) for k, v in ag.items()}
print('mean over charts', out['mean_agree'])
json.dump(out, open('intro.json', 'w'), indent=1)
