"""aligned.py: score.py's alignment test of each human chart's input.wav against our arms' song.ogg (one per song,
<shm>/m8/keep/_audio/<label>/song.ogg): a chart is well aligned with 5 or more of 9 windows at ncc >= 0.3 and a
lag MAD under 2 ms (M2's criterion). Reads B/arms/<label>.json for the chart labels; writes B/aligned.json
({label: {chart: {good_windows, mad_ms, ok}}}); prints a count. Usage: python -I aligned.py <m8-02 folder>"""
import json, sys
from pathlib import Path
M = Path(sys.argv[1])
sys.path.insert(0, "<shm>/m8/code")
from eval.scorer import score as SC   # noqa: E402
from eval import stress as S          # noqa: E402
DEV = Path("$DEV")
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
SET20 = sorted(s["id"] for s in json.loads((DEV / "eval-set20/stress/songs.json").read_text()))
SONGS = {**{s: ("refs", s) for s in REFS}, **{s: ("stress", s) for s in STRESS},
         **{f"s{i:02d}": ("set20", s) for i, s in enumerate(SET20, 1)}}
REFDIR = {"refs": DEV / "eval/refs", "stress": DEV / "eval/stress", "set20": DEV / "eval-set20/stress"}
out = {}
for label, (st, sid) in SONGS.items():
    song = next(s for s in S.built_songs(REFDIR[st]) if s["id"] == sid)
    charts = [("primary", Path(song["folder"]))] + [(a["label"], Path(a["folder"])) for a in song.get("alts") or []
                                                   if S.scorable(Path(a["folder"]))]
    c = SC.decode(f"<shm>/m8/keep/_audio/{label}/song.ogg")
    out[label] = {}
    for lab, folder in charts:
        r = SC.align(SC.decode(str(folder / "input.wav")), c, max_shift_s=30.0)
        out[label][lab] = {"good_windows": r["windows_peak_ge_0.3"], "mad_ms": round(r["lag_mad_ms"], 3),
                           "ok": r["windows_peak_ge_0.3"] >= 5 and r["lag_mad_ms"] < 2.0}
(M / "B" / "aligned.json").write_text(json.dumps(out, indent=1))
bad = {l: [c for c, v in d.items() if not v["ok"]] for l, d in out.items()}
print(sum(len(d) for d in out.values()), "charts;", sum(len(v) for v in bad.values()), "badly aligned:", {l: v for l, v in bad.items() if v})
