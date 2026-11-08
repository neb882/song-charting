"""align.py (part 3, step 1): reads the GPU pm2 chart (scan-chart notes only) and the CPU pm2 chart + the two reports'
lead-in and audio length; finds the lag between the two charts' Expert guitar onsets and checks it by matching
onsets within 10 ms; writes align.json; prints the numbers."""
import sys, json
sys.path.insert(0, '<scratch>')
from lib import *
gpu = Path('<shm>/pm2gpu/chart'); cpu = G / 'v040-stress/pm2'
rg, rc = rj(gpu / 'report.json'), rj(cpu / 'report.json')
sg, sc = scan(gpu), scan(cpu)
print('pad_s gpu/cpu', rg['lead_in']['pad_seconds'], rc['lead_in']['pad_seconds'], 'dur', rg['audio']['duration'], rc['audio']['duration'])
print('delay/offset gpu', sg.get('delay'), sg.get('chart_offset'), 'cpu', sc.get('delay'), sc.get('chart_offset'))
og = onsets(sg, 'guitar', 0.0); oc = onsets(sc, 'guitar', 0.0)
tg = np.array([o['t'] for o in og]); tc = np.array([o['t'] for o in oc])
print('n onsets', len(tg), len(tc), 'ends', tg[-1], tc[-1])
# histogram of nearest differences (chart seconds, gpu -> cpu)
best = None
for L in np.arange(-6, 6, 0.002):
    idx = np.searchsorted(tc, tg + L)
    d = np.minimum(np.abs(tc[np.clip(idx, 0, len(tc) - 1)] - (tg + L)), np.abs(tc[np.clip(idx - 1, 0, len(tc) - 1)] - (tg + L)))
    n = int((d <= 0.010).sum())
    if best is None or n > best[0]:
        best = (n, L)
n, L = best
print('coarse best lag s', round(L, 3), 'matches<=10ms', n, 'of', len(tg))
# refine on the matched differences
def diffs(L):
    out = []
    for t in tg:
        j = np.searchsorted(tc, t + L)
        for k in (j - 1, j):
            if 0 <= k < len(tc) and abs(tc[k] - (t + L)) <= 0.05:
                out.append(tc[k] - t)
    return np.array(out)
d = diffs(L); L2 = float(np.median(d[np.abs(d - L) < 0.02]))
p10 = S.match(tg + L2, tc, 0.010); p50 = S.match(tg + L2, tc, 0.050)
print('refined lag s %.4f' % L2, 'match 10ms', len(p10), '50ms', len(p50), 'of', len(tg), 'cpu', len(tc))
# by section of the song: matches per 60 s window
tg2 = tg + L2
for a in range(0, 440, 60):
    m = [(i, j) for i, j in p10 if a <= tg2[i] < a + 60]; w = int(((tg2 >= a) & (tg2 < a + 60)).sum())
    print(' window', a, 'gpu onsets', w, 'matched10', len(m))
json.dump({'lag_s': round(L2, 4), 'match10': len(p10), 'match50': len(p50), 'n_gpu': len(tg), 'n_cpu': len(tc)}, open('align.json', 'w'))
