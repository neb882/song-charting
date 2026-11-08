"""M7-01 part B helpers: F1@50 per chart, humans' agreement, nearest-onset tests, the paired bootstrap. Reads the
cache common.py writes; prints nothing."""
import numpy as np
from common import S

def times(rec, part):
    p = rec['parts'].get(part)
    return np.array([o[0] for o in p['onsets']]) if p else None

def span_of(rec, part):
    """A chart's span as score.py makes it (every part's first note .. last note end, +-0 here; margin in f1)."""
    st, en = [], []
    for p in rec['parts'].values():
        if p['onsets']:
            st.append(p['onsets'][0][0]); en.append(max(o[0] + o[3] for o in p['onsets']))
    return (min(st), max(en))

def f1(rt, ct, span, tol=0.05):
    lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
    ct = np.sort(ct[(ct >= lo) & (ct <= hi)])
    pairs = S.match(np.sort(rt), ct, tol)
    return S.prf(len(pairs), len(rt), S.n_cand_eff(pairs, ct, span))['f1']

def humans_agree(cache, part, tol=0.05):
    """Mean F1@50 of each other chart against the primary (None if one chart only or part missing)."""
    pr = cache['humans']['primary']
    rt = times(pr, part)
    if rt is None: return None
    v = [f1(rt, times(h, part), span_of(pr, part), tol) for k, h in cache['humans'].items()
         if k != 'primary' and times(h, part) is not None]
    return float(np.mean(v)) if v else None

def near_any(t, others, tol=0.05):
    """For each time in t, whether any array in others has an onset within tol."""
    out = np.zeros(len(t), bool)
    for o in others:
        if o is None or not len(o): continue
        o = np.sort(o)
        i = np.searchsorted(o, t)
        d = np.full(len(t), np.inf)
        ok = i < len(o); d[ok] = np.abs(o[i[ok]] - t[ok])
        ok = i > 0; d[ok] = np.minimum(d[ok], np.abs(o[i[ok] - 1] - t[ok]))
        out |= d <= tol
    return out

def boot(diffs, n=10000, seed=1):
    d = np.asarray([x for x in diffs if x is not None], float)
    if not len(d): return None
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return [round(float(d.mean()), 3), round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3), len(d)]
