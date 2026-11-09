"""warp_score.py REF CAND BASE_SHIFT_MS LABEL: score a candidate chart made from another master of the reference's
song. The candidate's Expert guitar, bass and drums onsets (at the scorer's base shift) are matched to the reference's
in 30-s windows (best extra shift in -600..+600 ms, 1 ms steps, counting matches within 25 ms); a Theil-Sen line
through the windows' shifts maps candidate time to reference time; then the scorer's own track metrics and a beat F1
at 70 ms on the mapped times. Prints numbers only."""
import json, sys
import numpy as np
sys.path.insert(0, '<wt>/orch/eval/scorer')
import score as S

ref, cand, base, label = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
rsc = S.scan(ref + '/ref'); csc = S.scan(S.find_chart_folder(cand)[0])
rtr, ctr = S.tracks_by_key(rsc), S.tracks_by_key(csc)
rdel, _ = S.chart_delay_ms(rsc)
starts = [min(n['ms'] for n in v) for v in rtr.values()]; ends = [max(n['ms'] + (n.get('msLength') or 0) for n in v) for v in rtr.values()]
span = ((min(starts) + rdel) / 1000, (max(ends) + rdel) / 1000)
parts = [p for p in ('guitar', 'bass', 'drums') if (p, 'expert') in rtr and (p, 'expert') in ctr]
R = {p: S.onsets(rtr[(p, 'expert')], rdel, p) for p in parts}
C = {p: S.onsets(ctr[(p, 'expert')], base, p) for p in parts}
rt = np.sort(np.concatenate([[o['t'] for o in R[p]] for p in parts]))
ct = np.sort(np.concatenate([[o['t'] for o in C[p]] for p in parts]))
shifts = np.arange(-0.600, 0.6005, 0.001)
cent, best, margin = [], [], []
for w0 in np.arange(span[0], span[1] - 15, 30.0):
    r = rt[(rt >= w0) & (rt < w0 + 30)]
    if len(r) < 40:
        continue
    scores = []
    for d in shifts:
        c = ct + d; c = c[(c >= w0 - 0.05) & (c < w0 + 30.05)]
        scores.append(len(S.match(list(r), list(c), 0.025)))
    scores = np.array(scores); i = int(scores.argmax())
    far = scores[np.abs(shifts - shifts[i]) > 0.04]
    cent.append(w0 + 15); best.append(shifts[i]); margin.append(int(scores[i] - (far.max() if len(far) else 0)))
cent, best = np.array(cent), np.array(best)
sl = [(best[j] - best[i]) / (cent[j] - cent[i]) for i in range(len(cent)) for j in range(i + 1, len(cent))]
a = float(np.median(sl)); b = float(np.median(best - a * cent))
resid = best - (a * cent + b)
warp = lambda t: t + a * t + b
out = {'label': label, 'base_shift_ms': base, 'windows': len(cent), 'speed_ppm': round(a * 1e6, 1),
       'offset_ms_at_0': round(b * 1000, 1), 'resid_ms_max': round(float(np.abs(resid).max()) * 1000, 1),
       'window_margins': margin, 'parts': {}}
lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
for p in parts:
    co = []
    for o in S.onsets(ctr[(p, 'expert')], base, p):
        o = dict(o); o['t'] = warp(o['t'])
        if lo <= o['t'] <= hi: co.append(o)
    tm = S.track_metrics(R[p], co, p, span, rsc.get('drumType') == 1, csc.get('drumType') == 1)
    out['parts'][p] = {k: tm[k] for k in ('onset_50ms', 'onset_100ms')}
    for k in ('lane_direction_agreement', 'exact_lane_agreement', 'state_agreement'):
        if k in tm: out['parts'][p][k] = tm[k]
rb = S.beat_times(rsc, span[0], span[1], rdel)
cb = [warp(t) for t in S.beat_times(csc, span[0] - 5, span[1] + 5, base)]
cb = [t for t in cb if span[0] - 0.07 <= t <= span[1] + 0.07]
out['beat_f1_70ms'] = S.prf(len(S.match(list(rb), cb, 0.070)), len(rb), len(cb))['f1']
print(json.dumps(out))
