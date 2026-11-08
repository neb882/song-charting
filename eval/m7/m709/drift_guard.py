"""M7-09 guard 2: reads report.json of every song in $DEV/golden/{v031,gate3-final-stress,set20-main} (grid
drift_ms, bpm_median, octave, tempo_check only); prints per song label (ref0-ref6 sorted ids, stress labels, s01-s13)
drift p95 against two beats and whether a warning at p95 > k beats would fire, k in 1, 2, 3, 4; writes drift_guard.json."""
import json, sys
from pathlib import Path
G = Path('$DEV/golden')
s20 = sorted(json.loads((G / 'set20-main/summary.json').read_text())['songs'])
rows = []
for d in ('v031', 'gate3-final-stress', 'set20-main'):
    sm = json.loads((G / d / 'summary.json').read_text())['songs']
    for sid in sorted(sm):
        r = json.loads((G / d / sm[sid]['folder'] / 'report.json').read_text())['grid']
        lab = ('s%02d' % (s20.index(sid) + 1)) if d == 'set20-main' else (
            sid if d == 'gate3-final-stress' else 'ref%d' % sorted(sm).index(sid))
        beat_ms = 60000.0 / r['bpm_median']
        p95 = r['drift_ms']['p95_abs']
        rows.append({'run': d, 'label': lab, 'octave': r['octave'], 'bpm_median': round(r['bpm_median'], 3),
                     'drift_p95_ms': p95, 'p95_beats': round(p95 / beat_ms, 3),
                     'fires': {k: p95 > k * beat_ms for k in (1, 2, 3, 4)},
                     'tempo_check_n': len(r['stats'].get('tempo_check') or [])})
for r in rows:
    print(r['label'], r['octave'], r['p95_beats'], r['fires'][2])
print('fires at 2 beats:', sum(r['fires'][2] for r in rows), 'of', len(rows))
json.dump(rows, open(sys.argv[1], 'w'), indent=1)
