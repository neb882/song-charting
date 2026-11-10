"""a_align.py: every alignment the two parts use, with score.py's align (fft xcorr of 1-s windows), per song and chart:
  ours9 / ours40: our song folder's audio, every file summed as score.py does (v0.5.0 golden; its tempo map equals part B's m05 chart's on all 23 songs) against the
                  chart's input.wav, score.py's 9 windows and a denser 40-window run (the same function, n_win=40);
  hum9 / hum40:   an alternative chart's input.wav against the primary's (score.py's humans' comparison).
Writes <shm>/ceiling/align.json (labels, chart keys and numbers only); prints one line per song."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cl

out = {}
p = cl.SHM / "align.json"
if p.exists():
    out = json.loads(p.read_text())
for label in cl.LABELS:
    if label in out:
        continue
    song = cl.our_folder(label)   # its audio files summed (score.py's cand mix)
    cs = cl.charts(label)
    prim = cs[0][1] / "input.wav"
    row = {}
    for k, folder in cs:
        rsc = cl.scan(folder / "ref")
        rdel, span = cl.ref_span(rsc)
        e = {"ref_delay_ms": rdel, "span": list(span)}
        for n in (9, 40):
            e[f"ours{n}"] = cl.align_cached(folder / "input.wav", song, n_win=n)
            if k != "primary":
                e[f"hum{n}"] = cl.align_cached(prim, folder / "input.wav", n_win=n)
        row[k] = e
    out[label] = row
    p.write_text(json.dumps(out))
    print(label, len(row), [round(v["ours9"]["lag_ms"]) for v in row.values()], flush=True)
