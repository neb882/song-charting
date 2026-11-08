"""M7-01 B-b2, ntl diagnostic: for our chart's same-lane runs (6+ onsets, gaps <= 110 ms) on the owner's ballad, how
many onsets pass each of the rule's tests (all onsets pitched, same pitch within 0.5 st, pitch track voiced on it
throughout). Reads ntl's work folder and our chart; writes bb2_ntl_diag.json (counts only)."""
import json, sys
import numpy as np
sys.argv = [sys.argv[0], 'x'] + sys.argv[1:]
from bb2 import engine, S, rj, BE, s
import pathlib
W = pathlib.Path('<shm>/ntl/work'); song = '$DEV/gpucheck030/cpu4/song'
pad = rj(song + '/report.json')['lead_in']['pad_seconds']
tr = S.tracks_by_key(S.scan(song))[('bass', 'expert')]
ons = [[o['t'], sorted(set(o['lanes']))] for o in S.onsets(tr, -pad * 1000, 'bass')]
et, ep, midi = engine(W / 'decode.wav', next(sorted((W / 'stems').glob('*/bass.wav')).__iter__()))
ot = np.array([o[0] for o in ons]); idx = np.searchsorted(et, ot); pit = np.full(len(ot), np.nan)
for k, t in enumerate(ot):
    for j in (idx[k] - 1, idx[k]):
        if 0 <= j < len(et) and abs(et[j] - t) <= 0.04: pit[k] = ep[j]
c = {'runs': 0, 'run_onsets': 0, 'all_pitched': 0, 'same_pitch': 0, 'voiced_through': 0, 'voiced_share_p50': None,
     'engine_onsets': int(len(et)), 'chart_onsets_with_engine_pitch': int(np.isfinite(pit).sum())}
vs = []
i = 0
while i < len(ons):
    j = i
    while j + 1 < len(ons) and len(ons[i][1]) == 1 and ons[j + 1][1] == ons[i][1] and ot[j + 1] - ot[j] <= 0.110: j += 1
    n = j - i + 1
    if n >= 6:
        c['runs'] += 1; c['run_onsets'] += n
        p = pit[i:j + 1]
        if np.all(np.isfinite(p)):
            c['all_pitched'] += n
            if np.all(np.abs(p - p[0]) < 0.5):
                c['same_pitch'] += n
                seg = midi[BE._frame(ot[i], s):BE._frame(ot[j], s) + 1]
                ok = np.isfinite(seg) & (np.abs(seg - p[0]) < 0.5)
                vs.append(float(ok.mean()))
                if ok.all(): c['voiced_through'] += n
    i = j + 1
c['voiced_share_p50'] = round(float(np.median(vs)), 3) if vs else None
json.dump(c, open(pathlib.Path(__file__).parent / 'bb2_ntl_diag.json', 'w'), indent=1); print(c)
