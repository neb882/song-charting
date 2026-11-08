"""M7-01 B-b2, the bass run rule. Reads the note cache, the kept decode.wav and bass stem, runs engines/bass.py's
onset and pYIN steps in process (as bb.py). Rule R(L, G): L or more consecutive same-lane single bass onsets of our
chart, each G s or less after the one before, whose engine pitches are all within 0.5 st of the run's first and with
the pitch track voiced within 0.5 st of it over every frame from the first onset to the last, become one note (the
first; the rest removed). Writes bb2.json; prints one line per song. With `--ntl`: the owner's ballad (no human chart),
from its work folder and our chart there; only the merge counts."""
import json, sys
import numpy as np
from common import songs, build, paths, stems, S, rj
from stats import times, span_of, f1, near_any
from songcharter import audio as A
from songcharter.engines import bass as BE
s = BE.Settings()
RULES = [(L, G) for L in (4, 6, 8) for G in (0.110, 0.150)]

def engine(mix_path, bass_path):
    mix, _ = A.read_wav(mix_path); bass, _ = A.read_wav(bass_path)
    x = np.asarray(bass, dtype=np.float32).mean(axis=0)
    on = BE.pick_onsets(BE.hfc_envelope(x, s), s)
    et = on[BE.leakage_ok(on, BE.levels(bass), BE.levels(mix), s)]
    _, midi = BE.pitch_track(x, s)
    ep = BE.note_pitches(et, np.append(et[1:], mix.shape[1] / BE.SAMPLE_RATE), midi, s)
    return et, ep, midi

def runs_removed(ons, et, ep, midi, L, G):
    """Indices of our onsets the rule removes."""
    ot = np.array([o[0] for o in ons])
    idx = np.searchsorted(et, ot)
    pit = np.full(len(ot), np.nan)
    for k, t in enumerate(ot):
        for j in (idx[k] - 1, idx[k]):
            if 0 <= j < len(et) and abs(et[j] - t) <= 0.04: pit[k] = ep[j]
    out = []
    i = 0
    single = [len(o[1]) == 1 for o in ons]
    while i < len(ons):
        j = i
        while (j + 1 < len(ons) and single[i] and single[j + 1] and ons[j + 1][1] == ons[i][1]
               and ot[j + 1] - ot[j] <= G + 1e-9):
            j += 1
        n = j - i + 1
        if n >= L and np.all(np.isfinite(pit[i:j + 1])) and np.all(np.abs(pit[i:j + 1] - pit[i]) < 0.5):
            seg = midi[BE._frame(ot[i], s):BE._frame(ot[j], s) + 1]
            if len(seg) and np.all(np.isfinite(seg)) and np.all(np.abs(seg - pit[i]) < 0.5):
                out += list(range(i + 1, j + 1))
        i = j + 1
    return out

def rep_share(ons):
    f = [len(a[1]) == 1 and len(b[1]) == 1 and a[1][0] == b[1][0] for a, b in zip(ons, ons[1:])]
    return float(np.mean(f)) if f else 0.0

if sys.argv[1] == '--ntl':
    W = __import__('pathlib').Path('<shm>/ntl/work'); song = '$DEV/gpucheck030/cpu4/song'
    pad = rj(song + '/report.json')['lead_in']['pad_seconds']
    sc = S.scan(song); tr = S.tracks_by_key(sc)[('bass', 'expert')]
    ons = [[o['t'], sorted(set(o['lanes']))] for o in S.onsets(tr, -pad * 1000, 'bass')]
    bstem = next(p for p in sorted((W / 'stems').glob('*/bass.wav')))
    et, ep, midi = engine(W / 'decode.wav', bstem)
    gaps = np.diff([o[0] for o in ons])
    out = {'notes': len(ons), 'repeat_share': rep_share(ons), 'gaps_le_110ms': int((gaps <= 0.11).sum()),
           'merged': {'L%d_G%d' % (L, G * 1000): len(runs_removed(ons, et, ep, midi, L, G)) for L, G in RULES}}
    json.dump(out, open(sys.argv[2], 'w'), indent=1); print(out); sys.exit()

OUT = sys.argv[1]; res = {}
for lab, st, sid in songs():
    c = build(lab, st, sid)
    if 'bass' not in c['ours']['parts']: continue
    hum = {k: h for k, h in c['humans'].items() if 'bass' in h['parts']}
    if not hum: continue
    et, ep, midi = engine(paths(st, sid)['kept'] / 'decode.wav', stems(st, sid)['bass'])
    ons = [[o[0], o[1]] for o in c['ours']['parts']['bass']['onsets']]
    ot = np.array([o[0] for o in ons])
    ht = {k: times(h, 'bass') for k, h in hum.items()}; sp = {k: span_of(h, 'bass') for k, h in hum.items()}
    base = {k: f1(ht[k], ot, sp[k]) for k in hum}
    near = near_any(ot, list(ht.values()))
    r = {'repeat_share': rep_share(ons), 'humans_repeat': float(np.mean([rep_share(h['parts']['bass']['onsets']) for h in hum.values()])), 'rules': {}}
    for L, G in RULES:
        rm = runs_removed(ons, et, ep, midi, L, G)
        m = np.zeros(len(ons), bool); m[rm] = True
        kept = [o for o, x in zip(ons, m) if not x]
        r['rules']['L%d_G%d' % (L, G * 1000)] = {
            'removed': int(m.sum()), 'removed_no_human': int((m & ~near).sum()),
            'precision': float((m & ~near).sum() / m.sum()) if m.sum() else None,
            'f1_change': float(np.mean([f1(ht[k], ot[~m], sp[k]) - base[k] for k in hum])),
            'repeat_share_after': rep_share(kept)}
    res[lab] = r
    json.dump(res, open(OUT, 'w'), indent=1)
    print(lab, {k: (v['removed'], v['precision'] and round(v['precision'], 2)) for k, v in r['rules'].items()}, flush=True)
