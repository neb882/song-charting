"""extract.py LABEL: reads part C's arm charts (arms/<label>/<arm>.notes.chart: the takes alone f0-f3 and the built
splices) and the human charts (notes only, through score.py's scan/tracks_by_key/onsets); writes
<shm>/m8t/<label>.ext.json (guitar Expert onset times: each arm's on its chart clock, ms; each human chart's on
its input.wav clock, s, with score.py's span). Prints one line of counts."""
import json, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
sys.path.insert(0, str(ORCH / "eval/scorer")); sys.path.insert(0, str(ORCH))
import score as SC
from eval import stress as S
label = sys.argv[1]
st, sid, kept, cl = SONGS[label]
res = json.loads((PARTC / "arms" / f"{cl}.json").read_text())
song = next(s for s in S.built_songs(REFDIR[st]) if s["id"] == sid)
charts = [("primary", Path(song["folder"]))] + [(a["label"], Path(a["folder"])) for a in song.get("alts") or []
                                               if S.scorable(Path(a["folder"]))]
assert [c for c, _ in charts] == res["charts"], (label, res["charts"])
out = {"arms": {}, "humans": {}}
for arm, v in res["arms"].items():
    if "same_as" in v:
        continue
    tmp = Path(tempfile.mkdtemp(dir=str(SHM)))
    shutil.copy(PARTC / "arms" / cl / f"{arm}.notes.chart", tmp / "notes.chart")
    sc = SC.scan(str(tmp)); shutil.rmtree(tmp)
    cdel, _ = SC.chart_delay_ms(sc)
    tr = SC.tracks_by_key(sc).get(("guitar", "expert")) or []
    out["arms"][arm] = {"delay_ms": cdel, "ms": [o["t"] * 1000.0 for o in SC.onsets(tr, cdel, "guitar")]}
for lab, folder in charts:
    rsc = SC.scan(str(folder / "ref"))
    rdel, _ = SC.chart_delay_ms(rsc)
    rtr = SC.tracks_by_key(rsc)
    starts, ends = [], []
    for k, notes in rtr.items():
        starts.append(min(n["ms"] for n in notes)); ends.append(max(n["ms"] + (n.get("msLength") or 0) for n in notes))
    span = ((min(starts) + rdel) / 1000.0, (max(ends) + rdel) / 1000.0)
    tr = rtr.get(("guitar", "expert")) or []
    out["humans"][lab] = {"span": span, "t": [o["t"] for o in SC.onsets(tr, rdel, "guitar")]}
(SHM / f"{label}.ext.json").write_text(json.dumps(out))
print(label, {a: len(v["ms"]) for a, v in out["arms"].items()}, {h: len(v["t"]) for h, v in out["humans"].items()})
