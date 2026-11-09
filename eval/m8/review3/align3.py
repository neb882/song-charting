"""align3.py (part 0): aligns the owner's GPU sooth chart (scan-chart notes only) to the stress set's sooth chart (our CPU
run of the stress file) by Expert guitar onset matching (review 2's align.py, coarse lag then median refine); checks
within 10 ms; also the owner's CPU chart of his file against his GPU chart (same file: lag expected 0). Writes align3.json."""
import sys, json
sys.path.insert(0, '<scratch>')
from lib import *
GPU = Path('<shm>/soothgpu/chart'); CPU1 = Path('$DEV/gpucheck040/sooth'); STR = G / 'v040-stress/sooth'
def ons(folder):
    return np.array([o['t'] for o in onsets(scan(folder), 'guitar', 0.0)])
def lag_of(tg, tc, lo=-8, hi=8):
    best = None
    for L in np.arange(lo, hi, 0.002):
        idx = np.searchsorted(tc, tg + L)
        d = np.minimum(np.abs(tc[np.clip(idx, 0, len(tc) - 1)] - (tg + L)), np.abs(tc[np.clip(idx - 1, 0, len(tc) - 1)] - (tg + L)))
        n = int((d <= 0.010).sum())
        if best is None or n > best[0]: best = (n, L)
    n, L = best
    dd = []
    for t in tg:
        j = np.searchsorted(tc, t + L)
        for k in (j - 1, j):
            if 0 <= k < len(tc) and abs(tc[k] - (t + L)) <= 0.05: dd.append(tc[k] - t)
    dd = np.array(dd); L2 = float(np.median(dd[np.abs(dd - L) < 0.02]))
    p10 = S.match(tg + L2, tc, 0.010); p50 = S.match(tg + L2, tc, 0.050)
    wins = []
    t2 = tg + L2
    for a in range(0, 560, 60):
        w = int(((t2 >= a) & (t2 < a + 60)).sum()); m = sum(1 for i, j in p10 if a <= t2[i] < a + 60)
        wins.append((a, w, m))
    return L2, len(p10), len(p50), wins
tg, tcpu, ts = ons(GPU), ons(CPU1), ons(STR)
out = {}
for name, a, b in (('gpu_vs_cpu_own', tg, tcpu), ('gpu_vs_stress', tg, ts)):
    L, n10, n50, wins = lag_of(a, b)
    out[name] = {'lag_s': round(L, 4), 'match10': n10, 'match50': n50, 'n_a': len(a), 'n_b': len(b), 'windows': wins}
    print(name, out[name])
for lab, f in (('gpu', GPU), ('cpu_own', CPU1), ('stress', STR)):
    r = rj(f / 'report.json'); print(lab, 'pad', r['lead_in']['pad_seconds'], 'dur', r['audio']['duration'], 'ends', ons(f)[-1] if True else '')
json.dump(out, open('<scratch>/align3.json', 'w'), indent=1)
