"""align.py: the alignment parts C and D use, computed as score.py does (fft xcorr of 1-s windows): per song, the lag
of our song.ogg (one hard-linked copy shared by every arm of the song) against each human chart's input.wav, the
chart's delay and the ref span over all its tracks. Reads <shm>/m8/keep/_audio/<label>/song.ogg and the human
charts (eval refs, notes only via scan-chart); writes <shm>/m8/m2/align.json (kept in RAM: it holds the charts'
folder paths) and prints one line per song (label, chart count, lags in ms rounded)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m2lib as L
from m2lib import S

out = {}
p = L.SHM / "align.json"
if p.exists():
    out = json.loads(p.read_text())
for label in L.LABELS:
    if label in out:
        continue
    c = S.try_decode(str(L.KEEP / "_audio" / label / "song.ogg"), [])
    row = {}
    for k, folder in L.charts(label):
        rsc = L.scan(folder / "ref")
        x = S.try_decode(str(folder / "input.wav"), [])
        r = S.align(x, c)
        rdel, _ = S.chart_delay_ms(rsc)
        starts, ends = [], []
        for (ins, dif), notes in S.tracks_by_key(rsc).items():
            starts.append(min(n["ms"] for n in notes)); ends.append(max(n["ms"] + (n.get("msLength") or 0) for n in notes))
        span = [(min(starts) + rdel) / 1000.0, (max(ends) + rdel) / 1000.0]
        row[k] = {"folder": str(folder), "lag_ms": r["lag_ms"], "lag_mad_ms": r["lag_mad_ms"],
                  "good_windows": r["windows_peak_ge_0.3"], "ref_delay_ms": rdel, "span": span}
    out[label] = row
    p.write_text(json.dumps(out))
    print(label, len(row), [round(v["lag_ms"]) for v in row.values()], flush=True)
