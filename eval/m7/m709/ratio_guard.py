"""M7-09 extra guard (not in the brief's list; a variant of 'tempo_check at the first grid's fold'): reads
<shm>/m709/out/<label>.npz (measure.py's first-grid and candidate beats); per 20-s window every 5 s, the first
grid's median beat rate over the candidate's; flags windows outside 2 +- 10 %. Prints the flagged windows per song and
grid; writes ratio_guard.json next to this script."""
import json
from pathlib import Path
import numpy as np
OUT = Path('<shm>/m709/out'); HERE = Path(__file__).parent
res = {}
for l in ('sooth', 's02', 's04', 'ntl', 'owner_sim'):
    z = np.load(OUT / f'{l}.npz')
    fb = z['first']
    res[l] = {}
    for n in ('today', 'a0', 'b', 'c'):
        cb = z[f'{n}_beats']
        flags = []
        for t0 in np.arange(0, cb[-1] - 20, 5.0):
            f = fb[(fb >= t0) & (fb < t0 + 20)]; c = cb[(cb >= t0) & (cb < t0 + 20)]
            if len(f) < 4 or len(c) < 4:
                continue
            q = np.median(np.diff(c)) / np.median(np.diff(f))
            if abs(q / 2 - 1) > 0.10:
                flags.append([float(t0), float(t0 + 20), round(float(q), 3)])
        res[l][n] = flags
        print(l, n, len(flags), [f'{a:.0f}-{b:.0f}s x{q}' for a, b, q in flags][:8])
(HERE / 'ratio_guard.json').write_text(json.dumps(res, indent=1))
