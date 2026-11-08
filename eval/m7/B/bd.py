"""M7-01 B-d, drumless stretches. Reads our report.json (grid.stats.secondary.stretches: the straight-line warnings),
the note cache's tempo maps (ours and each human chart's beat lines via score.beat_times), the kept folder's allin1
beats (sections/segments.json) and its bass and guitar (or other) stems; beat-tracks (librosa) the bass stem's onset
envelope and the guitar stem's band under 350 Hz. Prints one line per song; writes bd.json (numbers only)."""
import json, sys
import numpy as np
import librosa
from common import songs, build, report, paths, stems, S, rj
OUT = sys.argv[1]
TOL = S.BEAT_TOL
SR = 22050; HOP = 512

def beats_of(rec, t0, t1):
    return S.beat_times({'resolution': rec['res'], 'tempos': rec['tempos']}, t0, t1, rec['shift_ms'])

def bf1(ref, cand):
    if not len(ref) and not len(cand): return None
    pairs = S.match(np.sort(ref), np.sort(cand), TOL)
    return S.prf(len(pairs), len(ref), len(cand))['f1']

def inside(t, iv):
    m = np.zeros(len(t), bool)
    for a, b in iv: m |= (t >= a) & (t <= b)
    return m

def to_octave(x, ob):
    """A beat list moved to our grid's octave in the stretch: midpoints added when ours is about twice as fast,
    every other beat (the phase nearer our beats) when about half; unchanged otherwise."""
    if len(x) < 3 or len(ob) < 3: return x
    q = np.median(np.diff(x)) / np.median(np.diff(ob))
    if 1.6 < q < 2.4:
        return np.sort(np.r_[x, (x[1:] + x[:-1]) / 2])
    if 0.4 < q < 0.6:
        a, b = x[0::2], x[1::2]
        return a if len(S.match(ob, a, TOL)) >= len(S.match(ob, b, TOL)) else b
    return x

def track(env, bpm):
    _, b = librosa.beat.beat_track(onset_envelope=env, sr=SR, hop_length=HOP, start_bpm=bpm, units='time', trim=False)
    return np.asarray(b)

res = {}
for lab, st, sid in songs():
    rep = report(st, sid); c = build(lab, st, sid)
    strs = [s for s in rep['grid']['stats'].get('secondary', {}).get('stretches', []) if s[2] >= 16 and s[3] < 0.5]
    dur = rep['audio']['duration']
    r = {'octave': rep['grid']['octave'], 'n_stretches': len(strs),
         'seconds': round(sum(s[1] - s[0] for s in strs), 1), 'share': round(sum(s[1] - s[0] for s in strs) / dur, 4),
         'stretches': []}
    ours = beats_of(c['ours'], -10, dur + 10)
    hb = {}
    for k, h in c['humans'].items():
        if not h.get('tempos'): continue
        sp = [o[0] for p in h['parts'].values() for o in p['onsets']]
        if not sp: continue
        hb[k] = (beats_of(h, min(sp) - 0.1, max(sp) + 0.1), (min(sp), max(sp)))
    r['whole_song_f1'] = {k: bf1(b, ours[(ours >= s0 - .1) & (ours <= s1 + .1)]) for k, (b, (s0, s1)) in hb.items()}
    if strs:
        kept = paths(st, sid)['kept']
        al = np.asarray(rj(kept / 'sections/segments.json')['beats'], float)
        stm = stems(st, sid)
        yb, _ = librosa.load(str(stm['bass']), sr=SR, mono=True)
        eb = librosa.onset.onset_strength(y=yb, sr=SR, hop_length=HOP); del yb
        gname = 'guitar' if 'guitar' in stm else 'other'
        yg, _ = librosa.load(str(stm[gname]), sr=SR, mono=True)
        eg = librosa.onset.onset_strength(y=yg, sr=SR, hop_length=HOP, fmax=350.0, n_mels=32); del yg
        iv = [(s[0], s[1]) for s in strs]
        for s in strs:
            a, b = s[0], s[1]
            ob = ours[(ours >= a) & (ours <= b)]
            bpm = 60.0 / np.median(np.diff(ob)) if len(ob) > 2 else 120.0
            cb = track(eb, bpm); cg = track(eg, bpm)
            row = {'t0': round(a, 1), 't1': round(b, 1), 'beats': s[2], 'timed': s[3], 'our_bpm': round(bpm, 1), 'charts': {}}
            for k, (hbt, (s0, s1)) in hb.items():
                hin = hbt[(hbt >= a) & (hbt <= b)]
                if not len(hin):
                    row['charts'][k] = None   # no human beat lines here
                    continue
                cut = lambda x: x[(x >= a - TOL) & (x <= b + TOL)]
                row['charts'][k] = {'ours': bf1(hin, cut(ours)), 'allin1': bf1(hin, cut(al)),
                                    'allin1_oct': bf1(hin, to_octave(cut(al), ob)), 'bass_env_oct': bf1(hin, to_octave(cut(cb), ob)),
                                    'guitar_low_oct': bf1(hin, to_octave(cut(cg), ob)), 'bass_env': bf1(hin, cut(cb)),
                                    'guitar_low': bf1(hin, cut(cg))}
            vals = [v for v in row['charts'].values() if v]
            row['mean'] = {m: round(float(np.mean([v[m] for v in vals])), 4) for m in vals[0]} if vals else None
            r['stretches'].append(row)
        # the rest of the song: our beats outside the stretches
        rest = {}
        for k, (hbt, (s0, s1)) in hb.items():
            m = ~inside(hbt, iv); oc = ours[(ours >= s0 - .1) & (ours <= s1 + .1) & ~inside(ours, iv)]
            rest[k] = bf1(hbt[m], oc)
        r['rest_f1'] = rest
    res[lab] = r
    print(lab, r['n_stretches'], [x['mean'] for x in r['stretches']], flush=True)
json.dump(res, open(OUT, 'w'), indent=1)
