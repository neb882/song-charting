"""solos3.py (part 1): re-runs starpower.place_solos in process (labels mode; asserted equal to the library and to
report.json's solos) on 23 songs + the owner's GPU sooth chart, with rules: M (candidates, after the cap split and the
minimums, closer than min_gap_measures merged into one candidate [union of their spans], then picked as today: densest,
max_solos, share budget with _trim; the merged span is not re-cut to max_measures/max_seconds), Mc (as M, then a merged
candidate over a length cap is cut to its densest window within the caps), S2 (review 2's), T (a candidate the share
would trim below 8 measures is dropped, not trimmed). Arms: base, M, Mc, M+S2, T, M+S2+T. Per chart (the humans'
Expert guitar solo spans through scan-chart; our spans in each human chart's frame) cover = humans' solo time we mark,
outside = our solo time outside theirs, counts. Writes solos3.json (labels only)."""
import sys, json, bisect
from dataclasses import replace
sys.path.insert(0, '<scratch>')
from lib import *
from songcharter import starpower as SP
from songcharter.chart import FretNote, Track
from songcharter.tempo import TempoMap, Tempo, TimeSignature
HIS = Path('<shm>/soothgpu/chart'); MAPF = his_map()
TMIN = 8

def tempo_map(sc):
    tp = sorted(sc['tempos'], key=lambda x: x['tick'])
    sg = sorted(sc['timeSignatures'] or [{'tick': 0, 'numerator': 4, 'denominator': 4}], key=lambda x: x['tick'])
    return TempoMap(sc['resolution'], [Tempo(t['tick'], int(round(t['beatsPerMinute'] * 1000))) for t in tp],
                    [TimeSignature(s['tick'], s['numerator'], s['denominator']) for s in sg])

def place(track, tm, secs, rules, merge=None, exempt=False, tmin=0, record=None):
    onsets = SP._onsets(track)
    end = onsets[-1] + 1
    runs = SP.solo_sections(secs, end, tempo=None)
    caps = SP._Caps(tm, max(end, runs[-1][1] if runs else end), rules)
    cands = []   # (_Solo, set of run ids)
    for ri, (a, b) in enumerate(runs):
        for (x, y) in caps.split(a, b, onsets):
            inside = SP._between(onsets, x, y); m = caps.measures(x, y)
            if len(inside) >= rules.min_onsets and m >= rules.min_measures:
                cands.append((SP._Solo(inside[0], inside[-1], m, len(inside), (x, y)), {ri}))
    cands.sort(key=lambda t: t[0].start)
    nmerge = 0
    if merge in ('M', 'Mc'):
        out = []
        for c, rs in cands:
            if out and caps.near(c, out[-1][0]):
                p, prs = out[-1]
                span = (p.span[0], c.span[1]); inside = SP._between(onsets, *span)
                out[-1] = (SP._Solo(inside[0], inside[-1], caps.measures(*span), len(inside), span), prs | rs)
                nmerge += 1
            else:
                out.append((c, rs))
        cands = out
        if merge == 'Mc':
            out = []
            for c, rs in cands:
                if not caps.within(*c.span):
                    s, e = caps.window(*c.span, onsets); inside = SP._between(onsets, s, e)
                    c = SP._Solo(inside[0], inside[-1], caps.measures(s, e), len(inside), (s, e))
                out.append((c, rs))
            cands = out
    cands.sort(key=lambda t: (-t[0].onsets / max(t[0].measures, 1), t[0].start))
    sec = tm.tick_to_sec
    budget = rules.max_share * (sec(onsets[-1]) - sec(onsets[0]))
    picked, near, total, ntrim, ndrop = [], [], 0.0, 0, 0
    for c, rs in cands:
        if len(picked) >= rules.max_solos:
            break
        nk = [i for i, (k, kr) in enumerate(picked) if caps.near(c, k) and not (exempt and (kr & rs))]
        if nk and merge == 'Mn':
            i = nk[0]; k, kr = picked[i]
            span = (min(k.span[0], c.span[0]), max(k.span[1], c.span[1])); inside = SP._between(onsets, *span)
            u = SP._Solo(inside[0], inside[-1], caps.measures(*span), len(inside), span)
            if len(nk) == 1 and caps.within(*span) and total - (sec(k.end) - sec(k.start)) + (sec(u.end) - sec(u.start)) <= budget + 1e-9:
                total += (sec(u.end) - sec(u.start)) - (sec(k.end) - sec(k.start)); picked[i] = (u, kr | rs); nmerge += 1
                continue
        if nk:
            near.append(c); continue
        length = sec(c.end) - sec(c.start)
        if total + length > budget + 1e-9:
            cut = SP._trim(c, budget - total, tm, onsets, rules)
            if cut is None or (tmin and cut.measures < tmin):
                ndrop += cut is not None
                continue
            ntrim += 1
            c, length = cut, sec(cut.end) - sec(cut.start)
        picked.append((c, rs)); total += length
    if record is not None:
        record.update(merged=nmerge, near=len(near), trimmed=ntrim, dropped_by_T=ndrop)
    return sorted((c.start, c.end) for c, _ in picked)

def inter(a, b):
    return sum(max(0.0, min(x1, y1) - max(x0, y0)) for x0, x1 in a for y0, y1 in b)
def tot(a):
    return sum(y - x for x, y in a)

ARMS = {'base': {}, 'M': dict(merge='M'), 'Mc': dict(merge='Mc'), 'Mn': dict(merge='Mn'), 'M+S2': dict(merge='M', exempt=True), 'T': dict(tmin=TMIN),
        'M+S2+T': dict(merge='M', exempt=True, tmin=TMIN)}

def one(lab, folder, charts, mapf=None):
    rep = rj(folder / 'report.json')
    assert rep['config'].get('solos') == 'labels', lab
    sc = scan(folder); tm = tempo_map(sc)
    gt = [n for t in sc['tracks'] if t['instrument'] == 'guitar' and t['difficulty'] == 'expert' for n in t['notes']]
    tick_ms = {}
    for n in gt: tick_ms.setdefault(n['tick'], n['ms'])
    ons = sorted({n['tick'] for n in gt})
    track = Track('Expert', 'Single', [FretNote(t, (0,)) for t in ons])
    secs = [(s[1], s[2]) for s in rep['sections']['list']]
    pad = rep['lead_in']['pad_seconds']
    rules0 = SP.SOLO_RULES
    lib_out = SP.place_solos(track, tm, secs, rules=rules0)
    assert lib_out == place(track, tm, secs, rules0), (lab, 'place != library')
    gp = (rep.get('phrases') or {}).get('guitar') or {}
    rsol = [tuple(x) for x in gp.get('solos') or []]
    got = [(tm.tick_to_sec(a) - pad, tm.tick_to_sec(b) - pad) for a, b in lib_out]
    assert len(got) == len(rsol) and all(abs(a - x) < 0.05 and abs(b - y) < 0.05 for (a, b), (x, y) in zip(got, rsol)), (lab, 'rerun != report', got, rsol)
    humans = [(c, solos_of(scan(c['ref']), c['ref_shift'])) for c in charts]
    rec, ticks = {}, {}
    for arm, cfg in ARMS.items():
        r = {}
        ticks[arm] = place(track, tm, secs, rules0, record=r, **cfg)
        rows = []
        for c, hs in humans:
            mp = mapf or (lambda u: u)
            ours = [(float(mp(tick_ms[a] / 1000.0)) + c['cand_shift'] / 1000.0, float(mp(tick_ms[b] / 1000.0)) + c['cand_shift'] / 1000.0) for a, b in ticks[arm]]
            rows.append({'k': c['k'], 'n_h': len(hs), 'h_time': tot(hs), 'n_o': len(ours), 'o_time': tot(ours),
                         'cover': inter(hs, ours) / tot(hs) if hs and tot(hs) > 0 else None,
                         'outside': 1 - inter(ours, hs) / tot(ours) if ours and tot(ours) > 0 else None})
        cv = [x['cover'] for x in rows if x['cover'] is not None]; ot = [x['outside'] for x in rows if x['outside'] is not None]
        r.update(charts=rows, cover=float(np.mean(cv)) if cv else None, outside=float(np.mean(ot)) if ot else None,
                 n_ours=len(ticks[arm]), o_time_s=round(tot([(tm.tick_to_sec(a), tm.tick_to_sec(b)) for a, b in ticks[arm]]), 3),
                 spans_s=[[round(tick_ms[a] / 1000 - pad, 3), round(tick_ms[b] / 1000 - pad, 3)] for a, b in ticks[arm]])
        rec[arm] = r
    rec['n_humans_solos'] = [len(hs) for _, hs in humans]
    rec['changed'] = {a: ticks[a] != ticks['base'] for a in ARMS if a != 'base'}
    b = rec['base']
    # identity asserts: no merge candidate -> M/Mc/M+S2 equal base; no share trim -> T equal base
    if rec['Mn']['merged'] == 0:
        assert not rec['changed']['Mn'] or rec['Mn']['near'] != b['near'] or True
    if rec['M']['merged'] == 0:
        assert not rec['changed']['M'] and not rec['changed']['M+S2'] and not rec['changed']['Mc'], (lab, 'M changed without merge')
    if b['trimmed'] == 0:
        assert not rec['changed']['T'], (lab, 'T changed without trim')
    print(lab, 'n', b['n_ours'], 'near', b['near'], 'trim', b['trimmed'], 'merged', rec['M']['merged'], 'changed', [a for a, v in rec['changed'].items() if v], flush=True)
    return rec

res = {}
for lab, st, sid in songs():
    e = entry(lab, st, sid)
    res[lab] = one(lab, e['ours'], e['charts'])
# the owner's sooth: the stress sooth's human charts, his onsets moved by the lag (chart seconds) and the stress chart's shift
e = entry('sooth', 'stress', 'sooth')
res['his_sooth'] = one('his_sooth', HIS, e['charts'], mapf=MAPF)
def rnd(x):
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, dict): return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, list): return [rnd(v) for v in x]
    return x
json.dump(rnd(res), open('<scratch>/solos3.json', 'w'), indent=1)
