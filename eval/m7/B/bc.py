"""M7-01 B-c, solos. Reads the note cache (each chart's Expert guitar solos and onsets, tempo map), our report.json
(vocals stem level, sections, lead-in, phrases.guitar) and the kept vocals/guitar stems' levels; re-runs
starpower.place_solos in process at several max_share values. Prints a check line per song; writes bc.json."""
import json, sys, math
from dataclasses import replace
import numpy as np
from common import songs, build, report, levels
from songcharter import starpower as SP, assemble as AS
from songcharter.chart import FretNote, Track
from songcharter.tempo import TempoMap, Tempo, TimeSignature
OUT = sys.argv[1]
INSTR_DB = float(sys.argv[2]) if len(sys.argv) > 2 else None

def measures_of(rec, a_tick, length):
    res = rec['res']; sigs = sorted(rec['timeSignatures'] or [{'tick': 0, 'numerator': 4, 'denominator': 4}], key=lambda x: x['tick'])
    ts = next((x for x in reversed(sigs) if x['tick'] <= a_tick), sigs[0])
    return length / (ts['numerator'] * res * 4.0 / ts['denominator'])

def inter(a, b):
    tot = 0.0
    for x0, x1 in a:
        for y0, y1 in b:
            tot += max(0.0, min(x1, y1) - max(x0, y0))
    return tot

def total(a): return sum(y - x for x, y in a)

def tempo_map(rec):
    tp = sorted(rec['tempos'], key=lambda x: x['tick'])
    sigs = sorted(rec['timeSignatures'] or [{'tick': 0, 'numerator': 4, 'denominator': 4}], key=lambda x: x['tick'])
    return TempoMap(rec['res'], [Tempo(t['tick'], int(round(t['beatsPerMinute'] * 1000))) for t in tp],
                    [TimeSignature(s['tick'], s['numerator'], s['denominator']) for s in sigs])

res = {}
rows = []
for lab, st, sid in songs():
    c = build(lab, st, sid); rep = report(st, sid)
    voc = (rep.get('stems') or {}).get('vocals', {}).get('level_db')
    r = {'vocals_level_db': voc, 'humans': {}}
    for k, h in c['humans'].items():
        g = h['parts'].get('guitar')
        if not g or not g['onsets']: continue
        span = g['onsets'][-1][0] - g['onsets'][0][0]
        sol = [(s[0], s[1]) for s in g['solos']]
        r['humans'][k] = {'solos': [[round(measures_of(h, s[2], s[3]), 1), round(s[1] - s[0], 1)] for s in g['solos']],
                          'count': len(sol), 'share': round(total(sol) / span, 4), 'spans': sol}
    gp = (rep.get('phrases') or {}).get('guitar') or {}
    ours = [tuple(x) for x in gp.get('solos') or []]
    og = c['ours']['parts'].get('guitar')
    ospan = og['onsets'][-1][0] - og['onsets'][0][0]
    r['ours_report'] = {'count': len(ours), 'share': round(total(ours) / ospan, 4), 'details': gp.get('solo_details'),
                        'trimmed_by_share': len(gp.get('solos_trimmed_by_share') or []),
                        'skipped_by_share': len(gp.get('solos_skipped_by_share') or [])}
    # the in-process re-run
    tm = tempo_map(c['ours'])
    pad = rep['lead_in']['pad_seconds']
    lv = levels(st, sid, {'vocals', 'guitar', 'other'})
    lead = next((s for s in ('guitar', 'other') if s in lv), None)
    mode = rep['config'].get('solos')
    r['solos_mode'] = mode if isinstance(mode, str) else 'names'
    confirm = SP.stem_confirm(tm, pad, AS.LEVEL_FRAME_S, lv['vocals'], lv[lead] if lead else None) if mode == 'stems' else None
    assert mode in ('labels', 'stems'), mode
    secs = [(s[1], s[2]) for s in rep['sections']['list']]
    track = Track('Expert', 'Single', [FretNote(o[4], tuple(x for x in o[1] if x >= 0) or (7,)) for o in og['onsets']])
    def run(share, track=track, tm=tm, secs=secs, confirm=confirm, pad=pad):
        got = SP.place_solos(track, tm, secs, confirm=confirm, rules=replace(SP.SOLO_RULES, max_share=share))
        return [(tm.tick_to_sec(a) - pad, tm.tick_to_sec(b) - pad) for a, b in got]
    r['_run'] = run
    r['rerun_040'] = [[round(a, 3), round(b, 3)] for a, b in run(0.40)]
    r['secs_named_solo'] = sum(1 for _, n in secs if SP._SOLO.search(n))
    res[lab] = r
    same = len(r['rerun_040']) == len(ours) and all(abs(a - x) < 0.05 and abs(b - y) < 0.05 for (a, b), (x, y) in zip(r['rerun_040'], ours))
    print(lab, 'voc', voc, 'rerun==report', same, 'n', len(ours), r['rerun_040'][:1], ours[:1], flush=True)

allshares = [h['share'] for r in res.values() for h in r['humans'].values()]
cap = math.ceil(max(allshares) / 0.05 - 1e-9) * 0.05
def score(spans, r, ospan_):
    hs = [h for h in r['humans'].values()]
    cov = [inter(h['spans'], spans) / total(h['spans']) for h in hs if h['spans']]
    ins = [inter(spans, h['spans']) / total(spans) for h in hs] if spans else []
    return {'share': round(total(spans) / ospan_, 4), 'count': len(spans),
            'cover_human': round(float(np.mean(cov)), 4) if cov else None,
            'inside_human': round(float(np.mean(ins)), 4) if ins else None}
out = {'cap_from_humans': round(cap, 2), 'largest_human_share': max(allshares), 'instrumental_db': INSTR_DB, 'songs': {}}
for lab, st, sid in songs():
    r = res[lab]; run = r.pop('_run')
    c = build(lab, st, sid); og = c['ours']['parts']['guitar']; ospan = og['onsets'][-1][0] - og['onsets'][0][0]
    instr = INSTR_DB is not None and r['vocals_level_db'] is not None and r['vocals_level_db'] < INSTR_DB
    r['instrumental'] = instr
    r['arms'] = {'0.40': score(run(0.40), r, ospan), 'cap_%.2f' % cap: score(run(cap), r, ospan),
                 '0.75_instr': score(run(0.75 if instr else 0.40), r, ospan)}
    for h in r['humans'].values(): h['spans'] = [[round(a, 2), round(b, 2)] for a, b in h['spans']]
    out['songs'][lab] = r
json.dump(out, open(OUT, 'w'), indent=1)
