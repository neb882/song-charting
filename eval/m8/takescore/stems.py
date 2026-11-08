"""stems.py LABEL...: reads each kept folder's guitar stem (stems/<key>/guitar.wav); writes <shm>/m8t/<label>.stem.npz:
librosa onset strength (sr 22050, hop 512) and its peaks (local maxima over +-3 frames, librosa.util.peak_pick with
delta 0), plus the stem's frame levels (assemble.frame_levels, for assemble.silent_onsets). Prints one line per song."""
import sys
from pathlib import Path
import numpy as np, librosa
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
sys.path.insert(0, str(ORCH))
from songcharter.assemble import frame_levels
SR, HOP = 22050, 512
for label in sys.argv[1:]:
    st, sid, kept, _ = SONGS[label]
    wav = next((kept / "stems").glob("*/guitar.wav"))
    y, sr = librosa.load(str(wav), sr=SR, mono=True)
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    pk = librosa.util.peak_pick(env, pre_max=3, post_max=3, pre_avg=3, post_avg=3, delta=0.0, wait=1)
    t_env = librosa.frames_to_time(np.arange(len(env)), sr=SR, hop_length=HOP)
    y44, sr44 = librosa.load(str(wav), sr=None, mono=False)
    lv = frame_levels(y44, sr44)
    np.savez(SHM / f"{label}.stem.npz", env=env, t_env=t_env, peaks=t_env[pk], peak_s=env[pk], levels=lv)
    print(label, len(env), len(pk), len(lv), flush=True)
