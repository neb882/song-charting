"""crepe.py: the M8 ML spike's tracker pass. Reads $M8_SHM/m8c/songs.pkl (clib.songs()) and each song's kept guitar
stem; at our Expert guitar onsets inside fast runs it runs torchcrepe (CPU, frame-wise weighted-argmax decoding, no
Viterbi smoothing, periodicity as the confidence) and writes $M8_SHM/m8c/pitch/<label>.json in pitch.py's layout:
  crepe   full model, 10 ms hop, the first spike's window [t + 10 ms, min(t + 80 ms, next - 5 ms)] (frame centres)
  crepel  full model, 10 ms hop, frames lying wholly inside the note: centres in [t + 32 ms, next - 32 ms]
          (at least the one frame nearest t + 32 ms)
  tiny    tiny model, 5 ms hop, the first spike's window
per onset the median MIDI pitch of the window's frames and the mean periodicity (`<t>_conf`); prints one line per
song (label, onsets, audio seconds tracked, CPU seconds per model)."""
import json
import os
import pickle
import sys
import time

import numpy as np
import librosa
import torch
import torchcrepe

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clib  # noqa: E402
from pitch_common import windows, segments  # noqa: E402

SR = 16000
FMIN, FMAX = 70.0, 1400.0
HALF = 512 / SR                     # half of CREPE's 1024-sample frame: 32 ms
SHM = os.environ['M8_SHM']
OUT = os.path.join(SHM, 'm8c', 'pitch')
MODELS = {'full': 160, 'tiny': 80}  # model: hop in samples (10 ms, 5 ms)


def track(x, model, hop):
    a = torch.tensor(x[None].astype(np.float32))
    with torch.no_grad():
        f0, per = torchcrepe.predict(a, SR, hop, FMIN, FMAX, model, decoder=torchcrepe.decode.weighted_argmax,
                                     return_periodicity=True, batch_size=1024, device='cpu', pad=True)
    return f0[0].numpy(), per[0].numpy()


def song(s, cpu):
    t = np.array([o['t'] for o in s['ours']])
    rid = clib.fast_runs(t)
    idx = np.where(rid >= 0)[0]
    y, _ = librosa.load(s['stem'], sr=SR, mono=True)
    a, b = windows(t)
    nxt = np.r_[t[1:], t[-1] + 1.0]
    la, lb = t + HALF, np.maximum(nxt - HALF, t + HALF)
    res = {k: np.full(len(idx), np.nan) for k in ('crepe', 'crepe_conf', 'crepel', 'crepel_conf', 'tiny', 'tiny_conf')}
    secs = 0.0
    for s0, s1 in segments(t, rid):
        i0, i1 = int(s0 * SR), min(len(y), int(s1 * SR))
        x = y[i0:i1]
        if len(x) < 4096:
            continue
        secs += len(x) / SR
        fr = {}
        for model, hop in MODELS.items():
            c0, w0 = time.process_time(), time.perf_counter()
            f0, per = track(x, model, hop)
            cpu[model] += time.process_time() - c0
            cpu[model + '_wall'] += time.perf_counter() - w0
            fr[model] = (s0 + np.arange(len(f0)) * hop / SR, librosa.hz_to_midi(np.maximum(f0, 1.0)), per)
        for n, i in enumerate(idx):
            if not (s0 <= t[i] <= s1):
                continue
            for key, model, lo, hi in (('crepe', 'full', a[i], b[i]), ('crepel', 'full', la[i], lb[i]),
                                       ('tiny', 'tiny', a[i], b[i])):
                tf, mp, per = fr[model]
                m = (tf >= lo - 1e-9) & (tf <= hi + 1e-9)
                if not m.any():
                    m = np.zeros(len(tf), bool)
                    m[int(np.argmin(np.abs(tf - lo)))] = True
                res[key][n] = float(np.median(mp[m]))
                res[key + '_conf'][n] = float(np.mean(per[m]))
    return {'label': s['label'], 'stem_kind': s['stem_kind'], 'idx': idx.tolist(), 'run': rid[idx].tolist(),
            'audio_s': round(secs, 3), 'clock': {},
            **{k: [None if not np.isfinite(v) else round(float(v), 3) for v in res[k]] for k in res}}


def main():
    torch.manual_seed(0)
    os.makedirs(OUT, exist_ok=True)
    ss = pickle.load(open(os.path.join(SHM, 'm8c', 'songs.pkl'), 'rb'))
    for s in ss:
        t = np.array([o['t'] for o in s['ours']])
        if (clib.fast_runs(t) < 0).all() or not s['stem']:
            continue
        p = os.path.join(OUT, s['label'] + '.json')
        if os.path.exists(p):
            continue
        cpu = {'full': 0.0, 'tiny': 0.0, 'full_wall': 0.0, 'tiny_wall': 0.0}
        r = song(s, cpu)
        r['cpu_s'] = {k: round(v, 3) for k, v in cpu.items()}
        json.dump(r, open(p, 'w'))
        print(s['label'], len(r['idx']), r['audio_s'], r['cpu_s'], flush=True)


if __name__ == '__main__':
    main()
