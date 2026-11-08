"""M7-01 B-b, the bass. Reads the note cache, the kept folders' decode.wav and bass stem, and runs
songcharter.engines.bass's steps in process (onsets, leakage gate, pYIN, note pitches, map_lanes). Prints one line
per song (label, counts); writes bb.json (numbers only)."""
import json, sys, time
import numpy as np
from common import songs, build, paths, stems, CACHE
from stats import times, span_of, f1, near_any, humans_agree
from songcharter import audio as A
from songcharter.engines import bass as BE
OUT = sys.argv[1]
only = sys.argv[2:] or None
s = BE.Settings()

def singles(rec):
    return [o for o in rec['parts']['bass']['onsets']]

def repeat_flags(ons):
    """For each onset: a single note whose previous onset is a single note on the same lane."""
    f = [False]
    for a, b in zip(ons, ons[1:]):
        f.append(len(a[1]) == 1 and len(b[1]) == 1 and a[1][0] == b[1][0])
    return np.array(f)

def spread(ons):
    sg = [o[1][0] for o in ons if len(o[1]) == 1]
    c = np.bincount(np.array(sg) + 1, minlength=6) / max(len(sg), 1)   # index 0 = open
    return {'open': round(float(c[0]), 4), 'lanes': [round(float(x), 4) for x in c[1:]], 'largest': round(float(c.max()), 4)}

def contour(ro, co, tol=0.1):
    rt = np.array([o[0] for o in ro]); ct = np.array([o[0] for o in co])
    pairs = BE_match(rt, ct, tol)
    agree = n = 0
    for (i0, j0), (i1, j1) in zip(pairs, pairs[1:]):
        if i1 != i0 + 1: continue
        sr = np.sign(np.mean(ro[i1][1]) - np.mean(ro[i0][1])); sc = np.sign(np.mean(co[j1][1]) - np.mean(co[j0][1]))
        n += 1; agree += sr == sc
    return agree / n if n else None

from common import S
BE_match = S.match
res = json.load(open(OUT)) if only else {}
for lab, st, sid in songs():
    if only and lab not in only: continue
    c = build(lab, st, sid)
    if 'bass' not in c['ours']['parts']: continue
    hum = {k: h for k, h in c['humans'].items() if 'bass' in h['parts']}
    if not hum: continue
    t0 = time.time()
    kept = paths(st, sid)['kept']
    mix, _ = A.read_wav(kept / 'decode.wav'); bass, _ = A.read_wav(stems(st, sid)['bass'])
    x = np.asarray(bass, dtype=np.float32).mean(axis=0)
    env = BE.hfc_envelope(x, s)
    on = BE.pick_onsets(env, s)
    keep = BE.leakage_ok(on, BE.levels(bass), BE.levels(mix), s)
    et = on[keep]
    ft, midi = BE.pitch_track(x, s)
    dur = mix.shape[1] / BE.SAMPLE_RATE
    del mix, bass
    nexts = np.append(et[1:], dur)
    ep = BE.note_pitches(et, nexts, midi, s)
    el = BE.map_lanes(et, ep, s)
    en = (env - env.min()) / (env.max() - env.min() + 1e-9)
    fr = np.round(et * BE.SAMPLE_RATE / s.hop).astype(int)
    hfc = np.array([en[max(0, f - 2):f + 3].max() for f in fr])
    hfc_rank = np.argsort(np.argsort(hfc)) / max(len(hfc) - 1, 1)   # 0..1, 1 = the song's largest rise
    # held: the pitch track voiced on the previous note's pitch through the onset (+-50 ms)
    held = np.zeros(len(et), bool); samep = np.zeros(len(et), bool); chg = np.zeros(len(et), bool)
    for i in range(1, len(et)):
        if not (np.isfinite(ep[i]) and np.isfinite(ep[i - 1])): continue
        d = abs(ep[i] - ep[i - 1])
        samep[i] = d < 0.5; chg[i] = d >= 1.0
        if samep[i]:
            a, b = BE._frame(et[i] - 0.05, s), BE._frame(et[i] + 0.05, s)
            seg = midi[a:b]
            held[i] = len(seg) > 0 and np.all(np.isfinite(seg)) and np.all(np.abs(seg - ep[i - 1]) < 0.5)
    samelane = np.r_[False, el[1:] == el[:-1]]
    ours = singles(c['ours'])
    otimes = np.array([o[0] for o in ours])
    # engine note -> our chart onset (nearest within 40 ms)
    idx = np.searchsorted(otimes, et)
    e2o = np.full(len(et), -1)
    for k, t in enumerate(et):
        best = None
        for j in (idx[k] - 1, idx[k]):
            if 0 <= j < len(otimes) and abs(otimes[j] - t) <= 0.04 and (best is None or abs(otimes[j] - t) < abs(otimes[best] - t)):
                best = j
        if best is not None: e2o[k] = best
    rep = repeat_flags(ours)
    htimes = {k: times(h, 'bass') for k, h in hum.items()}
    spans = {k: span_of(h, 'bass') for k, h in hum.items()}
    near = near_any(otimes, list(htimes.values()))
    pr = hum.get('primary') or next(iter(hum.values()))
    psp = span_of(pr, 'bass'); pt = times(pr, 'bass')
    n_ours_in = int(((otimes >= psp[0] - .1) & (otimes <= psp[1] + .1)).sum())
    base_f1 = {k: f1(htimes[k], otimes, spans[k]) for k in hum}
    r = {'seconds': None, 'humans_f1_agree': humans_agree(c, 'bass'),
         'ours': {'repeat_share': round(float(rep[1:].mean()), 4), **spread(ours)},
         'humans': {k: {'repeat_share': round(float(repeat_flags(h['parts']['bass']['onsets'])[1:].mean()), 4),
                        **spread(h['parts']['bass']['onsets'])} for k, h in hum.items()},
         'notes_ratio_primary': round(n_ours_in / len(pt), 4),
         'repeat_match50': round(float(near[rep].mean()), 4) if rep.any() else None,
         'other_match50': round(float(near[~rep].mean()), 4),
         'f1_50': float(np.mean(list(base_f1.values()))),
         'engine': {'notes': int(len(et)), 'chart_mapped': int((e2o >= 0).sum())}}
    # our same-lane consecutive pairs, by the engine's pitches
    cls = {'same_pitch': 0, 'changed_ge1': 0, 'between': 0, 'unknown': 0}
    held_n = 0; hfc_held = []
    for k in range(1, len(et)):
        if e2o[k] < 0 or e2o[k - 1] < 0 or e2o[k] != e2o[k - 1] + 1 or not rep[e2o[k]]: continue
        if not (np.isfinite(ep[k]) and np.isfinite(ep[k - 1])): cls['unknown'] += 1
        elif samep[k]:
            cls['same_pitch'] += 1; held_n += held[k]
            if held[k]: hfc_held.append(float(hfc_rank[k]))
        elif chg[k]: cls['changed_ge1'] += 1
        else: cls['between'] += 1
    r['our_repeats_by_pitch'] = cls
    r['same_pitch_repeats_held'] = int(held_n)
    r['held_hfc_rank_p50'] = round(float(np.median(hfc_held)), 3) if hfc_held else None
    r['pitch_changes_ge1'] = int(chg.sum())
    r['pitch_changes_keep_lane_share'] = round(float((chg & samelane).sum() / chg.sum()), 4) if chg.any() else None
    # (a) the gate on held notes
    ga = {}
    for X in (0, 10, 25, 50):
        drop_e = held & (hfc_rank < 1 - X / 100.0)
        drop_o = sorted({int(e2o[k]) for k in np.flatnonzero(drop_e) if e2o[k] >= 0})
        m = np.zeros(len(ours), bool); m[drop_o] = True
        kept_o = [o for o, d in zip(ours, m) if not d]
        kt = otimes[~m]
        nf = {k: f1(htimes[k], kt, spans[k]) for k in hum}
        ga[str(X)] = {'removed': int(m.sum()), 'precision': round(float((m & ~near).sum() / m.sum()), 4) if m.sum() else None,
                      'f1_change': round(float(np.mean([nf[k] - base_f1[k] for k in hum])), 4),
                      'repeat_share_after': round(float(repeat_flags(kept_o)[1:].mean()), 4)}
    r['gate_a'] = ga
    # (b) the map: a pitch change of a semitone or more always changes the lane
    nl = el.copy()
    for i in range(1, len(et)):
        if chg[i] and nl[i] == nl[i - 1]:
            step = int(np.sign(ep[i] - ep[i - 1]))
            cand = nl[i - 1] + step
            if not 0 <= cand <= 4: cand = nl[i - 1] - step if False else nl[i]   # at the edge: no room, keep
            nl[i] = cand
    newo = [list(o) for o in ours]
    for k in range(len(et)):
        j = e2o[k]
        if j >= 0 and len(newo[j][1]) == 1 and newo[j][1][0] >= 0:
            newo[j][1] = [int(np.clip(newo[j][1][0] + (nl[k] - el[k]), 0, 4))]
    cb = {k: contour(h['parts']['bass']['onsets'], ours) for k, h in hum.items()}
    ca = {k: contour(h['parts']['bass']['onsets'], newo) for k, h in hum.items()}
    vb = [v for v in cb.values() if v is not None]; va = [v for v in ca.values() if v is not None]
    r['map_b'] = {'lanes_changed': int(sum(1 for a, b in zip(ours, newo) if a[1] != b[1])),
                  'contour_before': round(float(np.mean(vb)), 4) if vb else None,
                  'contour_after': round(float(np.mean(va)), 4) if va else None,
                  'repeat_share_after': round(float(repeat_flags(newo)[1:].mean()), 4)}
    r['seconds'] = round(time.time() - t0, 1)
    res[lab] = r
    json.dump(res, open(OUT, 'w'), indent=1)
    print(lab, r['seconds'], r['ours']['repeat_share'], cls, flush=True)
