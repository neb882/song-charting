"""Median offset (ms) between reference chart notes and audio onsets detected in input.wav.
positive = audio onsets come AFTER the chart notes.
usage: python -I offset_check.py <refs/id dir> [instrument]"""
import sys, os, json
import numpy as np, soundfile as sf, librosa
HOP = 64
def onsets(wav):
    y, sr = sf.read(wav, dtype='float32', always_2d=True); y = y.mean(1)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP, n_fft=1024, n_mels=64)
    on = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=HOP, units='time', backtrack=False,
                                    pre_max=int(0.03*sr/HOP), post_max=int(0.03*sr/HOP), pre_avg=int(0.1*sr/HOP),
                                    post_avg=int(0.1*sr/HOP), wait=int(0.03*sr/HOP), delta=0.07)
    return on, env, sr
def note_times(ref_notes, inst, pads=None):
    d = json.load(open(ref_notes)); delay = 0.0
    ini = os.path.join(os.path.dirname(ref_notes), 'ref', 'song.ini')
    for line in open(ini, encoding='utf-8', errors='replace'):
        k, _, v = line.partition('=')
        if k.strip().lower() == 'delay' and v.strip():
            try: delay = float(v)
            except ValueError: pass
    for t in d['tracks']:
        if t['instrument'] == inst and t['difficulty'] == 'expert' and t['notes']:
            ms = sorted({n['ms'] for n in t['notes'] if pads is None or n['type'] in pads})
            return (np.array(ms) + delay) / 1000.0, delay
    return None, delay
def main(refdir, inst=None):
    on, env, sr = onsets(os.path.join(refdir, 'input.wav'))
    res = {}
    order = [inst] if inst else ['drums', 'guitar']
    for ins in order:
        pads = ('kick', 'redDrum') if ins == 'drums' else None
        t, delay = note_times(os.path.join(refdir, 'ref_notes.json'), ins, pads)
        if t is None or len(t) < 2 or len(on) < 2: continue   # no such part (a package with only a rhythm or 6-fret part)
        idx = np.clip(np.searchsorted(on, t), 1, len(on) - 1)
        near = np.where(np.abs(on[idx] - t) < np.abs(on[idx - 1] - t), on[idx], on[idx - 1])
        dev = (near - t) * 1000
        m = np.abs(dev) <= 80
        if not m.any(): continue
        # click-train cross-correlation against the onset envelope (lags +-150 ms)
        fr = np.round(t * sr / HOP).astype(int); fr = fr[(fr > 200) & (fr < len(env) - 200)]
        e = (env - env.mean()) / (env.std() + 1e-9)
        lags = np.arange(-int(0.15*sr/HOP), int(0.15*sr/HOP) + 1)
        xc = np.array([e[fr + L].mean() for L in lags])
        k = int(np.argmax(xc)); lag = float(lags[k])
        if 0 < k < len(lags) - 1:
            a, b, c = xc[k-1], xc[k], xc[k+1]; den = a - 2*b + c
            if den != 0: lag += 0.5 * (a - c) / den
        res[ins] = dict(notes_used=int(len(t)), pads=pads, matched_within_80ms=int(m.sum()),
                        median_offset_ms=round(float(np.median(dev[m])), 1),
                        iqr_ms=[round(float(np.percentile(dev[m], 25)), 1), round(float(np.percentile(dev[m], 75)), 1)],
                        envelope_xcorr_offset_ms=round(lag * HOP / sr * 1000, 1), delay_applied_ms=delay)
        # drift check: median offset in each third of the song
        thirds = np.array_split(np.where(m)[0], 3)
        res[ins]['median_offset_by_third_ms'] = [round(float(np.median(dev[i])), 1) for i in thirds if len(i)]
    print(json.dumps(res, default=float))
    return res
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
