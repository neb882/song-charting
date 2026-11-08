"""windows.py LABEL: per splice window of one song, each take's onsets and its human-matched onsets (one to one at
50 ms, score.py's match) against the primary human chart, from the oracle arms' charts (arms/<label>/f<k>.notes.chart,
take k alone through the pipeline) on input seconds (score.py's shift for each arm, from its score JSON in
<shm>/m7/C-arms/<label>/scores). Reads the primary's notes through score.py's scan only. Writes
arms/<label>.windows.json (numbers only); prints nothing."""
import json, shutil, sys, tempfile
from pathlib import Path
C = Path(__file__).resolve().parent
sys.path.insert(0, str(C)); sys.path.insert(0, "<shm>/m7/code-C/eval/scorer")
import score as SC
from songs import SONGS
label = sys.argv[1]
st, sid, kept = SONGS[label]
refs = {"refs": Path("$DEV/eval/refs"), "stress": Path("$DEV/eval/stress"),
        "set20": Path("$DEV/eval-set20/stress")}[st]
res = json.loads((C / "arms" / f"{label}.json").read_text())
wins = res["windows"]

def guitar(sc, shift):
    tr = SC.tracks_by_key(sc).get(("guitar", "expert")) or []
    return [o["t"] for o in SC.onsets(tr, shift, "guitar")]

rsc = SC.scan(str(refs / sid / "ref"))
rdel, _ = SC.chart_delay_ms(rsc)
human = guitar(rsc, rdel)
takes = []
for k in range(4):
    arm = f"f{k}"
    if arm not in res["arms"]:
        takes.append(None); continue
    al = json.loads(Path(f"<shm>/m7/C-arms/{label}/scores/{arm}.primary.json").read_text())["alignment"]
    tmp = Path(tempfile.mkdtemp(dir="<shm>/m7"))
    shutil.copy(C / "arms" / label / f"{arm}.notes.chart", tmp / "notes.chart")
    sc = SC.scan(str(tmp)); shutil.rmtree(tmp)
    takes.append(guitar(sc, al["cand_total_shift_ms"]))
out = []
for w in wins:
    a, b = w["start"], w["end"] if w["end"] is not None else 1e9
    h = [t for t in human if a <= t < b]
    row = {"start": a, "end": w["end"], "human": len(h), "scores": w["scores"], "onsets": w["onsets"],
           "take_onsets": [], "matched": [], "f1": []}
    for t in takes:
        if t is None:
            row["take_onsets"].append(None); row["matched"].append(None); row["f1"].append(None); continue
        c = [x for x in t if a <= x < b]
        m = len(SC.match(h, c, 0.05))
        row["take_onsets"].append(len(c)); row["matched"].append(m)
        row["f1"].append(1.0 if not h and not c else round(2 * m / (len(h) + len(c)), 4))
    out.append(row)
(C / "arms" / f"{label}.windows.json").write_text(json.dumps(out, indent=1))
