"""pitch_common.py: the first spike's (eval/m8/contour/pitch.py) onset windows and fast-run audio segments, unchanged."""
import numpy as np

W0, W1 = 0.010, 0.080              # the pitch window after each onset: [t + 10 ms, min(t + 80 ms, next onset - 5 ms)]


def windows(t):
    nxt = np.r_[t[1:], t[-1] + 1.0]
    a = t + W0
    b = np.minimum(t + W1, nxt - 0.005)
    return a, np.maximum(b, a + 0.02)


def segments(t, rid, pad=0.3):
    seg = []
    for r in range(rid.max() + 1):
        tt = t[rid == r]
        seg.append([max(0.0, tt[0] - pad), tt[-1] + pad])
    seg.sort()
    out = [seg[0]]
    for s in seg[1:]:
        if s[0] <= out[-1][1]:
            out[-1][1] = max(out[-1][1], s[1])
        else:
            out.append(s)
    return out
