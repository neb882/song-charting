"""tail3.py (part 2): the tail's tempo on the owner's GPU sooth chart against the stress set's sooth human charts.
Frames: his chart seconds + lag (align3.json) + the stress score's cand_total_shift = the human chart's frame (as solos3).
Window = his file's last 60 s (input seconds 484.833-544.833, + pad). Beat times through score.beat_times (every
quarter-note tick of the tempo map). Ours today = his chart's beats; H = inside the first-tempo span (report: input
500-535 s) keep every other beat, the first kept being the beat nearest (last beat before the span + the period before
it) so the halved grid's own period is carried through (no human data used); H_alt = the other parity. Beat F1 at 70 ms
as the scorer's tempo_metrics (matching, n_cand_eff over the window as span). Prints; writes tail3.json."""
import sys, json
sys.path.insert(0, '<scratch>')
from lib import *
HIS = Path('<shm>/soothgpu/chart'); MAPF = his_map()
rep = rj(HIS / 'report.json'); pad = rep['lead_in']['pad_seconds']; dur = rep['audio']['duration']
span_in = rep['grid']['octave_stats']['halving']['first_tempo']['spans'][0]
sc = scan(HIS); e = entry('sooth', 'stress', 'sooth'); BT = S.BEAT_TOL
W = (pad + dur - 60, pad + dur); SP_ = (pad + span_in[0], pad + span_in[1])
def f1(rb, cb, span):
    pairs = S.match(rb, cb, BT)
    return S.prf(len(pairs), len(rb), S.n_cand_eff(pairs, cb, span))
def per(b):
    return round(float(np.median(np.diff(b))), 3) if len(b) > 2 else None
def bpm(b):
    p = per(b); return None if p is None else round(60 / p, 1)
def H(b, parity=None):
    """b: his beats (his chart seconds). keep every other beat inside SP_."""
    b = np.asarray(b); inn = (b >= SP_[0]) & (b < SP_[1]); idx = np.flatnonzero(inn)
    before = b[:idx[0]]; prev_p = before[-1] - before[-2]
    target = before[-1] + prev_p
    first = idx[0] + (0 if abs(b[idx[0]] - target) <= abs(b[idx[0] + 1] - target) else 1)
    if parity is not None: first = idx[0] + parity
    keep = [i for i in range(len(b)) if not inn[i] or ((i - first) % 2 == 0 and i >= first)]
    return b[keep]
def H2(b, parity=None, maxp=0.6):
    """H on the doubled stretch only: inside the span, the beats whose interval to the next is under maxp s (the grid at
    ~160 BPM and the ramp's fast half); keep every other from the group's start, parity by continuity (the first kept is
    the beat nearer the last slow beat + that beat's own preceding period), or forced."""
    b = np.asarray(b); inn = (b >= SP_[0]) & (b < SP_[1]); gap = np.append(np.diff(b), 9.0)
    dbl = inn & (gap < maxp); idx = np.flatnonzero(dbl); i0 = idx[0]
    prev_p = b[i0] - b[i0 - 1]; target = b[i0 - 1] + 2 * prev_p if False else b[i0 - 1] + prev_p
    first = i0 + (0 if abs(b[i0] - target) <= abs(b[i0 + 1] - target) else 1) if parity is None else i0 + parity
    keep = [i for i in range(len(b)) if not dbl[i] or ((i - first) % 2 == 0 and i >= first)]
    return b[keep]
def H3(b, maxp=0.6):
    """H on the doubled stretch with the halved grid's own period carried through: from the last beat before the doubled
    stretch (b0, preceding period P), the lattice b0 + n*P; each doubled-stretch beat is kept when it is the nearest beat to
    a lattice point (one beat per point). No human data."""
    b = np.asarray(b); inn = (b >= SP_[0]) & (b < SP_[1]); gap = np.append(np.diff(b), 9.0)
    dbl = inn & (gap < maxp); idx = np.flatnonzero(dbl); i0, i1 = idx[0], idx[-1]
    b0, P = b[i0 - 1], b[i0 - 1] - b[i0 - 2]
    keep_d = set(); n = 1
    while b0 + n * P <= b[i1] + P / 2:
        j = i0 + int(np.argmin(abs(b[i0:i1 + 1] - (b0 + n * P)))); keep_d.add(j); n += 1
    keep = [i for i in range(len(b)) if not dbl[i] or i in keep_d]
    return b[keep]
out = {'his_pad': pad, 'dur': dur, 'span_in': span_in}
his_all = S.beat_times(sc, 0, pad + dur + 3, 0.0)
print('his chart beats', len(his_all), 'last', round(his_all[-1], 2), 'span chart s', SP_, 'W', W)
ours_sub = his_all[(his_all >= SP_[0]) & (his_all < SP_[1])]
h_all = H(his_all); h_alt = H(his_all, 1 - int(round((h_all[h_all >= SP_[0]][0] - his_all[his_all >= SP_[0]][0]) / (his_all[his_all >= SP_[0]][1] - his_all[his_all >= SP_[0]][0]))))
h2 = H2(his_all); h2a = H2(his_all, 1 - int(round((h2[h2 >= SP_[0]][0] - his_all[his_all >= SP_[0]][0]) / 0.375)) if False else 1)
print('ours in span: n', len(ours_sub), 'period', per(ours_sub), 'bpm', bpm(ours_sub))
Hs = h_all[(h_all >= SP_[0]) & (h_all < SP_[1])]; print('H in span: n', len(Hs), 'period', per(Hs), 'bpm', bpm(Hs))
before = his_all[(his_all >= SP_[0] - 60) & (his_all < SP_[0])]; print('ours the 60 s before span: bpm', bpm(before))
rows = []
for c in e['charts']:
    cs = c['cand_shift'] / 1000.0
    rsc = scan(c['ref']); lo, hi = float(MAPF(W[0])) + cs, float(MAPF(W[1])) + cs
    lo, hi = max(lo, c['span'][0]), min(hi, c['span'][1])
    rb = S.beat_times(rsc, lo, hi, c['ref_shift'])
    r = {'k': c['k'], 'win_s_in_his_chart': [round(lo, 2), round(hi, 2)], 'n_ref_beats': len(rb), 'ref_bpm_window': bpm(rb)}
    if len(rb) < 4:
        rows.append(r); print(r); continue
    sp0, sp1 = float(MAPF(SP_[0])) + cs, float(MAPF(SP_[1])) + cs
    sub = rb[(rb >= sp0) & (rb < sp1)]
    r['ref_bpm_in_span'] = bpm(sub); r['ref_n_in_span'] = len(sub)
    for name, b in (('today', his_all), ('H', h_all), ('H_alt', h_alt), ('H2', h2), ('H3', H3(his_all)), ('H2_alt', H2(his_all, 1 - (0 if np.array_equal(h2, H2(his_all, 0)) else 1)))):
        cb = MAPF(b) + cs; cb = cb[(cb >= lo - BT) & (cb <= hi + BT)]
        r[name] = f1(rb, cb, (lo, hi))['f1']
        s2 = (b >= SP_[0]) & (b < SP_[1]); inspan = MAPF(b[s2]) + cs
        rs = rb[(rb >= sp0) & (rb < sp1)]
        r[name + '_inspan'] = f1(rs, inspan, (sp0, sp1))['f1'] if len(rs) else None
        r[name + '_n_beats_window'] = int(len(cb))
    r['tempo_markers_ref_last'] = [round(t['beatsPerMinute'], 1) for t in sorted(rsc['tempos'], key=lambda x: x['tick'])[-3:]]
    rows.append(r); print(r)
out['rows'] = rows
# the stress set's sooth chart (ours): its tail, numbers only
sch = G / 'v040-stress/sooth'; rs_ = rj(sch / 'report.json'); ss = scan(sch); sb = S.beat_times(ss, 0, rs_['audio']['duration'] + rs_['lead_in']['pad_seconds'] + 3, 0.0)
hs = rs_['grid']['octave_stats']['halving']
out['stress'] = {'dur': rs_['audio']['duration'], 'pad': rs_['lead_in']['pad_seconds'], 'beats': len(sb), 'last_beat': round(float(sb[-1]), 2),
                 'bpm_last60': bpm(sb[sb > sb[-1] - 60]), 'allin1_beats': hs['allin1_beats'], 'bpm_max': rs_['tempo_map']['bpm_max'], 'first_tempo': hs['first_tempo']['spans'],
                 'n_windows_ratio_near1': len(hs['first_tempo']['windows']), 'his_beats': len(his_all), 'his_last_beat': round(float(his_all[-1]), 2),
                 'his_allin1_beats': rep['grid']['octave_stats']['halving']['allin1_beats'], 'his_bpm_last60': bpm(his_all[his_all > W[0]]), 'his_median_bpm_500_535': bpm(his_all[(his_all > SP_[0]) & (his_all < SP_[1])]), 'stress_bpm_500_535': bpm(sb[(sb > 500 + rs_['lead_in']['pad_seconds']) & (sb < 535 + rs_['lead_in']['pad_seconds'])])}
print(out['stress'])
# tempo marker series of his chart past 480 s (bpm)
tp = sorted(sc['tempos'], key=lambda x: x['tick']); print('his tempo markers after 470 s (chart s, bpm):', [(round(t['msTime'] / 1000, 1), round(t['beatsPerMinute'], 1)) for t in tp if t['msTime'] / 1000 > 470])
json.dump(out, open('<scratch>/tail3.json', 'w'), indent=1, default=float)
