"""M7-01 B-a, notes over a silent stem. Reads the note cache, the kept stems' levels (assemble.frame_levels) and our
report.json (silent_onsets, sections, drum section loudness). Prints a check line per song; writes ba.json."""
import json, sys
import numpy as np
from common import songs, build, levels, report, CACHE
from stats import times, span_of, f1, humans_agree, near_any, boot
from songcharter import assemble as AS
OUT = sys.argv[1]
FS = AS.LEVEL_FRAME_S; W = AS.SILENT_WINDOW
DS = (25.0, 30.0, 35.0)

def silent_mask(t, lv, d):
    floor = float(np.percentile(lv, 95)) - d
    m = np.zeros(len(t), bool)
    for k, x in enumerate(t):
        i, j = max(0, int((x + W[0]) / FS)), int((x + W[1]) / FS) + 1
        seg = lv[i:j]
        m[k] = (not len(seg)) or seg.max() < floor
    return m

def stretch_mask(t, lv, d, min_s=1.0):
    """Silent onsets whose window sits inside a run of frames all under the floor lasting at least min_s."""
    floor = float(np.percentile(lv, 95)) - d
    q = lv < floor
    run_len = np.zeros(len(q)); 
    # length of the run each frame belongs to
    k = 0
    while k < len(q):
        if q[k]:
            j = k
            while j < len(q) and q[j]: j += 1
            run_len[k:j] = (j - k) * FS; k = j
        else: k += 1
    m = silent_mask(t, lv, d)
    for n, x in enumerate(t):
        if m[n]:
            i = max(0, int((x + W[0]) / FS)); i = min(i, len(q) - 1)
            m[n] = run_len[i] >= min_s
    return m

STEM = {'guitar': ('guitar', 'other'), 'bass': ('bass',), 'drums': ('drums',)}
res = {}
for lab, st, sid in songs():
    c = build(lab, st, sid); rep = report(st, sid)
    lvs = levels(st, sid, {'guitar', 'other', 'bass', 'drums'})
    song = {}
    for part in ('guitar', 'bass', 'drums'):
        stem = next((s for s in STEM[part] if s in lvs), None)
        ours = times(c['ours'], part)
        if stem is None or ours is None: continue
        lv = lvs[stem]
        hum = {k: times(h, part) for k, h in c['humans'].items() if times(h, part) is not None}
        if not hum: continue
        spans = {k: span_of(c['humans'][k], part) for k in hum}
        r = {'stem': stem, 'n_ours': len(ours), 'humans_f1_agree': humans_agree(c, part),
             'n_human': {k: len(v) for k, v in hum.items()}}
        rp = (rep.get('parts') or {}).get(part, {}).get('silent_onsets') or {}
        r['report_silent_count'] = rp.get('count')
        r['check_ours25'] = int(silent_mask(ours, lv, 25.0).sum())
        base_f1 = {k: f1(hum[k], ours, spans[k]) for k in hum}
        r['f1_50'] = float(np.mean(list(base_f1.values())))
        hn_any = near_any(ours, list(hum.values()))
        for d in DS:
            key = '%d' % d
            hs = {k: silent_mask(v, lv, d) for k, v in hum.items()}
            r['human_silent_' + key] = {k: [int(m.sum()), round(float(m.mean()), 4)] for k, m in hs.items()}
            for rule, fn in (('i', silent_mask), ('ii', stretch_mask)):
                m = fn(ours, lv, d)
                hm = {k: fn(v, lv, d) for k, v in hum.items()}
                kept = ours[~m]
                nf = {k: f1(hum[k], kept, spans[k]) for k in hum}
                r[f'rule_{rule}_{key}'] = {
                    'removed': int(m.sum()), 'removed_share': round(float(m.mean()), 4),
                    'removed_no_human': int((m & ~hn_any).sum()),
                    'precision': round(float((m & ~hn_any).sum() / m.sum()), 4) if m.sum() else None,
                    'human_removed': {k: [int(x.sum()), round(float(x.mean()), 4)] for k, x in hm.items()},
                    'human_removed_max_share': round(max(float(x.mean()) for x in hm.values()), 4),
                    'f1_after': float(np.mean(list(nf.values()))),
                    'f1_change': round(float(np.mean([nf[k] - base_f1[k] for k in hum])), 4)}
        song[part] = r
    # drums in quiet sections: our section list and the drum stem's loudness per section (report.json)
    secs = (rep.get('sections') or {}).get('list') or []
    loud = rep.get('drum_section_loudness_db') or []
    if secs and len(loud) == len(secs) and 'drums' in song:
        starts = [s[0] for s in secs] + [rep['audio']['duration']]
        med = float(np.median(loud))
        ours = times(c['ours'], 'drums')
        hum = {k: times(h, 'drums') for k, h in c['humans'].items() if times(h, 'drums') is not None}
        rows = []
        for n, ld in enumerate(loud):
            a, b = starts[n], starts[n + 1]
            o = ours[(ours >= a) & (ours < b)]
            fs, dens = [], []
            for k, h in hum.items():
                hh = h[(h >= a) & (h < b)]
                if len(hh) or len(o):
                    fs.append(f1(hh, o, (a, b)) if len(hh) else 0.0)
                dens.append(len(hh) / max(b - a, 1e-6))
            rows.append({'start': round(a, 2), 'end': round(b, 2), 'loud_db': ld, 'rel_db': round(ld - med, 2),
                         'quiet': ld - med <= -10.0, 'ours_per_s': round(len(o) / max(b - a, 1e-6), 3),
                         'human_per_s': round(float(np.mean(dens)), 3), 'f1_50': round(float(np.mean(fs)), 4) if fs else None})
        song['drum_sections'] = rows
    res[lab] = song
    print(lab, {p: (song[p]['report_silent_count'], song[p]['check_ours25']) for p in ('guitar', 'bass', 'drums') if p in song}, flush=True)
json.dump(res, open(OUT, 'w'), indent=1)
