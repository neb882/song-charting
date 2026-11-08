"""pitch.py: reads <shm>/m8c/songs.pkl (clib.songs()) and each song's kept guitar stem; at our Expert guitar onsets
inside fast runs it runs three trackers (pYIN, a CQT peak, a harmonic-summed CQT peak) and writes
<shm>/m8c/pitch/<label>.json (per onset: pitch in MIDI numbers and a confidence) plus a stem clock check; prints
one line per song (label, onsets, seconds)."""
import json
import os
import pickle
import sys
import time

import numpy as np
import librosa

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clib  # noqa: E402

SR = 22050
FMIN, FMAX = 70.0, 1400.0          # guitar: low E2 82 Hz (drop tunings a little lower) up to the 24th fret of high E
HOP_P = 220                        # pYIN hop 10 ms, frame 2048 (as the bass engine), fmin 70 needs 630 samples
HOP_C, BPO, NB = 128, 36, 180      # CQT: 5.8 ms hop, 1/3 semitone bins, five octaves from E2
CQ_F0 = librosa.note_to_hz('E2')
W0, W1 = 0.010, 0.080              # the pitch window after each onset: [t + 10 ms, min(t + 80 ms, next onset - 5 ms)]
OUT = '<shm>/m8c/pitch'


def windows(t):
    nxt = np.r_[t[1:], t[-1] + 1.0]
    a = t + W0
    b = np.minimum(t + W1, nxt - 0.005)
    return a, np.maximum(b, a + 0.02)


def segments(t, rid, pad=0.3):
    seg = []
    for r in range(rid.max() + 1):
        tt = t[rid == r]
        seg.append([max(0.0, tt[0] - pad), tt[-1] + pad])
    seg.sort()
    out = [seg[0]]
    for s in seg[1:]:
        if s[0] <= out[-1][1]:
            out[-1][1] = max(out[-1][1], s[1])
        else:
            out.append(s)
    return out


def song(s):
    t = np.array([o['t'] for o in s['ours']])
    rid = clib.fast_runs(t)
    idx = np.where(rid >= 0)[0]
    y, _ = librosa.load(s['stem'], sr=SR, mono=True)
    a, b = windows(t)
    res = {k: np.full(len(idx), np.nan) for k in ('pyin', 'pyin_conf', 'cqt', 'cqt_conf', 'hs', 'hs_conf')}
    # harmonic offsets in bins for the harmonic sum
    hb = [int(round(BPO * np.log2(h))) for h in (1, 2, 3, 4)]
    hw = [1.0, 0.8, 0.64, 0.51]
    for s0, s1 in segments(t, rid):
        i0, i1 = int(s0 * SR), min(len(y), int(s1 * SR))
        x = y[i0:i1]
        if len(x) < 4096:
            continue
        f0, vf, vp = librosa.pyin(x, fmin=FMIN, fmax=FMAX, sr=SR, frame_length=2048, hop_length=HOP_P)
        tp = s0 + np.arange(len(f0)) * HOP_P / SR
        C = np.abs(librosa.cqt(x, sr=SR, hop_length=HOP_C, fmin=CQ_F0, n_bins=NB, bins_per_octave=BPO))
        tc = s0 + np.arange(C.shape[1]) * HOP_C / SR
        for n, i in enumerate(idx):
            if not (s0 <= t[i] <= s1):
                continue
            m = (tp >= a[i]) & (tp <= b[i])
            if m.any():
                res['pyin_conf'][n] = float(np.mean(vp[m]))
                v = m & vf & np.isfinite(f0)
                if v.any():
                    res['pyin'][n] = float(np.median(librosa.hz_to_midi(f0[v])))
            m = (tc >= a[i]) & (tc <= b[i])
            if m.any():
                spec = C[:, m].mean(axis=1)
                k = int(np.argmax(spec))
                res['cqt'][n] = float(librosa.hz_to_midi(CQ_F0) + k * 12.0 / BPO)
                res['cqt_conf'][n] = float(spec[k] / (spec.mean() + 1e-12))
                hs = np.zeros(NB)
                for off, w in zip(hb, hw):
                    hs[:NB - off] += w * spec[off:]
                k = int(np.argmax(hs))
                res['hs'][n] = float(librosa.hz_to_midi(CQ_F0) + k * 12.0 / BPO)
                res['hs_conf'][n] = float(hs[k] / (hs.mean() + 1e-12))
    # the stem's clock: mean onset strength at our fast-run onsets shifted by d ms (peak 25-50 ms after = aligned)
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=256)
    fps = SR / 256

    def at(tt):
        k = np.clip(np.round(tt * fps).astype(int), 0, len(env) - 1)
        return float(env[k].mean())
    clock = {str(d): round(at(t[idx] + d / 1000.0), 3) for d in (-100, -50, -25, 0, 25, 50, 75, 100)}
    return {'label': s['label'], 'stem_kind': s['stem_kind'], 'idx': idx.tolist(), 'run': rid[idx].tolist(),
            'clock': clock, **{k: [None if not np.isfinite(v) else round(float(v), 3) for v in res[k]] for k in res}}


def main():
    os.makedirs(OUT, exist_ok=True)
    ss = pickle.load(open('<shm>/m8c/songs.pkl', 'rb'))
    for s in ss:
        t = np.array([o['t'] for o in s['ours']])
        if (clib.fast_runs(t) < 0).all() or not s['stem']:
            continue
        p = os.path.join(OUT, s['label'] + '.json')
        if os.path.exists(p):
            continue
        t0 = time.time()
        r = song(s)
        json.dump(r, open(p, 'w'))
        print(s['label'], len(r['idx']), round(time.time() - t0, 1), flush=True)


if __name__ == '__main__':
    main()
