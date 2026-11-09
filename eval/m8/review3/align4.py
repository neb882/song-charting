"""align4.py: corrected alignment (the onset-only lag of align3.py was a 16th (0.2 s) off: charts' onsets are 16th-periodic).
Audio lag windows (audlag3.json: his song.ogg time = stress decode time + lag_ms) -> linear fit lag(t); expressed as
stress chart seconds = his chart seconds + a + b*(his chart seconds), checked by matching the two charts' Expert guitar
onsets within 10 / 50 ms at that map. Writes align4.json."""
import sys, json
sys.path.insert(0, '<scratch>')
from lib import *
A = json.load(open('<scratch>/audlag3.json'))
pad_h, pad_s = 3.154807, 3.179773
x = np.array([w['ref_time_s'] for w in A['windows']]); y = np.array([w['lag_ms'] for w in A['windows']]) / 1000   # stress input s -> his ogg lag
b, a0 = np.polyfit(x, y, 1)      # lag_ms(t_s_in) = a0 + b t_s_in
print('fit lag at 0 s %.4f slope %.6f s/s; resid mad ms %.1f' % (a0, b, 1000 * np.median(abs(y - (a0 + b * x)))))
# his ogg time u = s_in + a0 + b s_in -> s_in = (u - a0)/(1+b); his chart sec = u; stress chart sec = s_in + pad_s
def to_stress_chart(u): return (u - a0) / (1 + b) + pad_s
tg = np.array([o['t'] for o in onsets(scan(Path('<shm>/soothgpu/chart')), 'guitar', 0.0)]); ts = np.array([o['t'] for o in onsets(scan(G / 'v040-stress/sooth'), 'guitar', 0.0)])
m = to_stress_chart(tg)
for tol in (0.010, 0.050):
    p = S.match(m, ts, tol); print('match', tol, len(p), 'of', len(tg))
d = []
for t in m:
    j = np.argmin(abs(ts - t))
    if abs(ts[j] - t) < 0.1: d.append((t, ts[j] - t))
d = np.array(d)
for lo in range(0, 540, 60):
    q = d[(d[:, 0] >= lo) & (d[:, 0] < lo + 60)]; print(lo, len(q), round(float(np.median(q[:, 1])) * 1000, 1) if len(q) else None)
print('his chart 500 s ->', round(float(to_stress_chart(500)), 3), 'lag chart-s', round(float(to_stress_chart(500) - 500), 3))
# refine: the onset residuals (within 50 ms) fitted linearly in time, added to the audio map (the audio windows' own scatter is 11 ms)
dd = d[abs(d[:, 1]) < 0.05]; rb, ra = np.polyfit(dd[:, 0], dd[:, 1], 1)
def to_stress_chart2(u):
    v = to_stress_chart(u); return v + ra + rb * v
m2 = to_stress_chart2(tg)
print('refined: residual fit at 0 s %.4f slope %.6f' % (ra, rb))
for tol in (0.010, 0.050):
    p = S.match(m2, ts, tol); print('refined match', tol, len(p), 'of', len(tg))
for lo in range(0, 540, 60):
    q = [(t, ts[np.argmin(abs(ts - t))] - t) for t in m2[(m2 >= lo) & (m2 < lo + 60)]]; q = np.array([v for t, v in q if abs(v) < 0.1])
    print(lo, len(q), round(float(np.median(q)) * 1000, 1) if len(q) else None)
print('refined: his chart 500 s -> lag chart-s', round(float(to_stress_chart2(500) - 500), 3), ' at 0:', round(float(to_stress_chart2(0)), 3))
m = m2
json.dump({'a0': a0, 'b': b, 'pad_h': pad_h, 'pad_s': pad_s, 'resid_a': ra, 'resid_b': rb, 'lag_at_0_chart_s': float(to_stress_chart2(0)), 'lag_at_500_chart_s': float(to_stress_chart2(500) - 500), 'match10': len(S.match(m, ts, 0.01)), 'match50': len(S.match(m, ts, 0.05)), 'n_his': len(tg)}, open('<scratch>/align4.json', 'w'), indent=1)
