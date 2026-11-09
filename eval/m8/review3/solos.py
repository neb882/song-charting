"""solos.py (part 1): reads the v040 runs' charts, report.json (sections, lead-in, phrases.guitar) and the human charts'
Expert guitar solo spans (scan-chart through lib.scan); re-runs starpower.place_solos and four variants in process
(S1/S2 remainder exempt from the gap rule, counting / not counting toward max_solos; S3 max_measures 128; S3b also
max_seconds 200); writes solos.json (labels only); prints one check line per song."""
import sys, json, bisect
from dataclasses import replace
sys.path.insert(0, '<scratch>')
from lib import *
from songcharter import starpower as SP
from songcharter.chart import FretNote, Track
from songcharter.tempo import TempoMap, Tempo, TimeSignature

def tempo_map(sc):
    tp = sorted(sc['tempos'], key=lambda x: x['tick'])
    sg = sorted(sc['timeSignatures'] or [{'tick': 0, 'numerator': 4, 'denominator': 4}], key=lambda x: x['tick'])
    return TempoMap(sc['resolution'], [Tempo(t['tick'], int(round(t['beatsPerMinute'] * 1000))) for t in tp],
                    [TimeSignature(s['tick'], s['numerator'], s['denominator']) for s in sg])

def place(track, tm, secs, rules, exempt=False, count_remainder=True, record=None):
    """starpower.place_solos (names=None, confirm=None) with: exempt: a candidate is not 'near' a kept solo of its own
    run (its siblings from the cap's split); count_remainder False: a kept solo whose run already had a kept one does
    not count toward max_solos. exempt False and count True is the library's own rule (asserted by the caller)."""
    onsets = SP._onsets(track)
    caps = SP._Caps(tm, onsets[-1], rules)
    end = onsets[-1] + 1
    runs = SP.solo_sections(secs, end, tempo=None)
    caps = SP._Caps(tm, max(end, runs[-1][1] if runs else end), rules)
    cands, nsplit = [], 0
    for ri, (a, b) in enumerate(runs):
        pieces = caps.split(a, b, onsets)
        nsplit += len(pieces) > 1
        for (x, y) in pieces:
            inside = SP._between(onsets, x, y); m = caps.measures(x, y)
            if len(inside) >= rules.min_onsets and m >= rules.min_measures:
                cands.append((SP._Solo(inside[0], inside[-1], m, len(inside), (x, y)), ri))
    cands.sort(key=lambda t: (-t[0].onsets / max(t[0].measures, 1), t[0].start))
    sec = tm.tick_to_sec
    budget = rules.max_share * (sec(onsets[-1]) - sec(onsets[0]))
    picked, near, total, counted = [], [], 0.0, 0
    for c, ri in cands:
        if counted >= rules.max_solos:
            break
        if any(caps.near(c, k) for k, kr in picked if not (exempt and kr == ri)):
            near.append(c); continue
        length = sec(c.end) - sec(c.start)
        if total + length > budget + 1e-9:
            cut = SP._trim(c, budget - total, tm, onsets, rules)
            if cut is None:
                continue
            c, length = cut, sec(cut.end) - sec(cut.start)
        rem = any(kr == ri for k, kr in picked)
        picked.append((c, ri)); total += length
        if count_remainder or not rem:
            counted += 1
    if record is not None:
        record.update(split_runs=nsplit, near=len(near), near_measures=sum(c.measures for c in near),
                      near_onsets=sum(c.onsets for c in near))
    return sorted((c.start, c.end) for c, _ in picked)

def inter(a, b):
    return sum(max(0.0, min(x1, y1) - max(x0, y0)) for x0, x1 in a for y0, y1 in b)
def tot(a):
    return sum(y - x for x, y in a)

ARMS = {'base': dict(), 'S1': dict(exempt=True, count_remainder=True), 'S2': dict(exempt=True, count_remainder=False),
        'S3': dict(rules=dict(max_measures=128)), 'S3b': dict(rules=dict(max_measures=128, max_seconds=200.0))}

res = {}
for lab, st, sid in songs():
    e = entry(lab, st, sid)
    rep = rj(e['ours'] / 'report.json')
    assert rep['config'].get('solos') == 'labels', lab
    sc = scan(e['ours']); tm = tempo_map(sc)
    gt = [n for t in sc['tracks'] if t['instrument'] == 'guitar' and t['difficulty'] == 'expert' for n in t['notes']]
    tick_ms = {}
    for n in gt:
        tick_ms.setdefault(n['tick'], n['ms'])
    ons = sorted({n['tick'] for n in gt})
    track = Track('Expert', 'Single', [FretNote(t, (0,)) for t in ons])
    secs = [(s[1], s[2]) for s in rep['sections']['list']]
    gp = (rep.get('phrases') or {}).get('guitar') or {}
    pad = rep['lead_in']['pad_seconds']
    base_rules = SP.SOLO_RULES
    # check against the library and the report (report's solos are input seconds = chart seconds - pad)
    lib_out = SP.place_solos(track, tm, secs, rules=base_rules)
    mine = place(track, tm, secs, base_rules)
    assert lib_out == mine, (lab, 'place != library')
    rsol = [tuple(x) for x in gp.get('solos') or []]
    got = [(tm.tick_to_sec(a) - pad, tm.tick_to_sec(b) - pad) for a, b in lib_out]
    ok = len(got) == len(rsol) and all(abs(a - x) < 0.05 and abs(b - y) < 0.05 for (a, b), (x, y) in zip(got, rsol))
    assert ok, (lab, 'rerun != report', got[:2], rsol[:2])
    rec = {}
    arm_ticks = {}
    for arm, cfg in ARMS.items():
        rules = replace(base_rules, **cfg.get('rules', {}))
        r = {}
        arm_ticks[arm] = place(track, tm, secs, rules, cfg.get('exempt', False), cfg.get('count_remainder', True), r)
        rec[arm] = r
    # spans per chart frame
    humans = []
    for c in e['charts']:
        hs = solos_of(scan(c['ref']), c['ref_shift'])
        humans.append((c, hs))
    ospan_ref = None
    for arm, tk in arm_ticks.items():
        rows = []
        for c, hs in humans:
            ours = [((tick_ms[a] + c['cand_shift']) / 1000.0, (tick_ms[b] + c['cand_shift']) / 1000.0) for a, b in tk]
            rows.append({'k': c['k'], 'n_h': len(hs), 'h_time': tot(hs), 'n_o': len(ours), 'o_time': tot(ours),
                         'cover': inter(hs, ours) / tot(hs) if hs and tot(hs) > 0 else None,
                         'outside': 1 - inter(ours, hs) / tot(ours) if ours and tot(ours) > 0 else None})
        rec[arm]['charts'] = rows
        rec[arm]['ticks'] = tk
        cv = [x['cover'] for x in rows if x['cover'] is not None]; ot = [x['outside'] for x in rows if x['outside'] is not None]
        rec[arm]['cover'] = float(np.mean(cv)) if cv else None
        rec[arm]['outside'] = float(np.mean(ot)) if ot else None
        rec[arm]['n_ours'] = len(tk)
        rec[arm]['spans_s'] = [[round(tick_ms[a] / 1000 - pad + 0, 3), round(tick_ms[b] / 1000 - pad, 3)] for a, b in tk]
    rec['n_humans_solos'] = [len(hs) for _, hs in humans]
    rec['changed'] = {a: rec[a]['ticks'] != rec['base']['ticks'] for a in ARMS if a != 'base'}
    # split-free songs: every arm identical (S1/S2/S3 only act on split or gapped runs)
    for a in ('S1', 'S2'):
        if rec['base']['split_runs'] == 0 or rec['base']['near'] == 0:
            assert not rec['changed'][a], (lab, a, 'changed without a split/gap')
    if rec['base']['split_runs'] == 0:
        assert not rec['changed']['S3'] and not rec['changed']['S3b'], (lab, 'S3 changed without a split')
    res[lab] = rec
    print(lab, 'ok n', rec['base']['n_ours'], 'split', rec['base']['split_runs'], 'near', rec['base']['near'],
          'changed', [a for a, v in rec['changed'].items() if v], flush=True)
def rnd(x):
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, dict): return {k: rnd(v) for k, v in x.items() if k != 'ticks'}
    if isinstance(x, list): return [rnd(v) for v in x]
    return x
json.dump(rnd(res), open('solos.json', 'w'), indent=1)
