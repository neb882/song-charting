"""a_b_arrays.py LABEL: reads the kept folder's decode.wav and six stem WAVs (v0.4.0 code's audio.read_wav), builds sections.allin1_input as the pipeline does,
and prints/writes A/arrays_LABEL.json: VmRSS delta (MiB) of each array the parent holds while allin1 runs (mix, six stems, the folded 'other' sum, the int16 payload,
payload.astype('<i2'), .tobytes()), the song seconds, MiB/min of audio per array, and the seconds to read them all again from the work folder."""
import sys, json, time, gc
from pathlib import Path
import numpy as np
sys.path[:0] = ["<shm>/m8/code-cpu", str(Path(__file__).parent)]
from songs_map import SONGS
from songcharter import audio as A
from songcharter.engines import sections as SE
label = sys.argv[1]; kept = SONGS[label][1]
def rss():
    for l in open("/proc/self/status"):
        if l.startswith("VmRSS"): return int(l.split()[1])/1024
base = rss(); out = {"label": label}
t0 = time.time(); mix, sr = A.read_wav(kept/"decode.wav"); t_mix = time.time()-t0
dur = mix.shape[1]/sr; out["duration_s"] = round(dur, 3); r1 = rss(); out["mix_mib"] = r1-base
d = next(p for p in sorted((kept/"stems").glob("*/")) if (p/"info.json").is_file())
t0 = time.time(); stems = {}
for n in ("bass", "drums", "guitar", "other", "piano", "vocals"): stems[n] = A.read_wav(d/f"{n}.wav")[0]
t_st = time.time()-t0; r2 = rss(); out["stems6_mib"] = r2-r1
fold = SE.fold_stems(stems); r3 = rss(); out["fold_other_mib"] = r3-r2
pay = SE.allin1_input(stems); r4 = rss(); out["payload_int16_mib"] = r4-r3
a = pay.astype("<i2"); r5 = rss(); out["astype_copy_mib"] = r5-r4
b = a.tobytes(); r6 = rss(); out["tobytes_copy_mib"] = r6-r5
out["baseline_mib"] = base; out["total_mib"] = r6-base
mins = dur/60
out["per_min_mib"] = {k: round(out[k]/mins, 3) for k in ("mix_mib","stems6_mib","fold_other_mib","payload_int16_mib","astype_copy_mib","tobytes_copy_mib","total_mib")}
out["read_seconds"] = {"mix": round(t_mix,3), "six_stems": round(t_st,3), "all": round(t_mix+t_st,3)}
def rnd(o):
    if isinstance(o, float): return round(o, 3)
    if isinstance(o, dict): return {k: rnd(v) for k, v in o.items()}
    return o
out = rnd(out); json.dump(out, open(Path(__file__).parent/f"arrays_{label}.json", "w"), indent=1); print(out)
