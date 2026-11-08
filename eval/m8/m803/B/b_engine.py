"""b_engine.py [labels]: reads each kept folder's decode.wav and bass stem (v0.4.0 engines/bass.py steps in process: hfc_envelope, pick_onsets, leakage_ok, pitch_track,
note_pitches, as eval/m7/B/bb.py did) and caches the engine onset times, their pitches and the pYIN pitch track (MIDI, NaN unvoiced) per song label in B/cache/LABEL.npz.
Prints one line of counts per song (labels only)."""
import sys, time
from pathlib import Path
import numpy as np
sys.path[:0] = ["<shm>/m8/code-cpu", str(Path(__file__).parent.parent/"A")]
from songs_map import SONGS
from songcharter import audio as A
from songcharter.engines import bass as BE
s = BE.Settings(); HERE = Path(__file__).parent
labels = sys.argv[1:] or [l for l in SONGS if l != "test_song"]
for lab in labels:
    out = HERE/"cache"/f"{lab}.npz"
    if out.exists(): continue
    kept = SONGS[lab][1]; t0 = time.time()
    d = next(p for p in sorted((kept/"stems").glob("*/")) if (p/"info.json").is_file())
    mix, _ = A.read_wav(kept/"decode.wav"); bass, _ = A.read_wav(d/"bass.wav")
    x = np.asarray(bass, dtype=np.float32).mean(axis=0)
    on = BE.pick_onsets(BE.hfc_envelope(x, s), s)
    et = on[BE.leakage_ok(on, BE.levels(bass), BE.levels(mix), s)]
    _, midi = BE.pitch_track(x, s)
    ep = BE.note_pitches(et, np.append(et[1:], mix.shape[1]/BE.SAMPLE_RATE), midi, s)
    np.savez(out, et=et, ep=ep, midi=midi)
    print(lab, len(et), int(np.isfinite(ep).sum()), round(time.time()-t0, 1), flush=True)
