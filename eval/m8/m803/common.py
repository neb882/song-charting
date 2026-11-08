"""common.py (parts B and C): the 23 songs and the test song by label (the 20-song ids mapped to s01..s13 in process, never printed), today's charts (the v0.4.0
gate's runs v040, v040-stress, v040-set20) and the human charts through eval/scorer/score.py's scan (notes, tempo map, star power phrases only), as records
{ours, humans{primary, altK}} in the input.wav timeline with the shifts as eval/m7/B/common.py applied them. Caches records as JSON (labels only) in
<scratch>/cache. Reads the run folders' summary.json and score JSONs. Prints nothing. Needs SONGCHARTER_SCAN_CHART."""
import json, os, sys
from pathlib import Path
import numpy as np
os.environ.setdefault("SONGCHARTER_SCAN_CHART", "<wt>/base-main/tools/scan-chart/scan.cjs")
sys.path[:0] = ["<shm>/m8/code-cpu", "<shm>/m8/code-cpu/eval/scorer"]
import score as S  # noqa
G = Path("$DEV/golden"); DEV = Path("$DEV")
CACHE = Path(__file__).parent/"cache"; CACHE.mkdir(exist_ok=True)
PARTS = ("guitar", "bass", "drums")
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["troop", "sooth", "break", "pm2"]
def rj(p): return json.loads(Path(p).read_text())
def songs():
    out = [(i, "refs", i) for i in REFS] + [(i, "stress", i) for i in STRESS]
    s20 = sorted(s["id"] for s in rj(DEV/"eval-set20/stress/songs.json"))
    out += [("s%02d" % (k+1), "set20", sid) for k, sid in enumerate(s20)]
    return out
def paths(st, sid):
    if st == "refs":
        return dict(refdir=DEV/"eval/refs"/sid, run=G/"v040", score=G/"v040/scores"/f"{sid}.score.json", alts=[], human=None)
    refs = DEV/("eval/stress" if st == "stress" else "eval-set20/stress")
    song = next(s for s in rj(refs/"songs.json") if s["id"] == sid)
    alts = [(f"alt{k}", refs/sid/"alt"/a["md5"]) for k, a in enumerate(song.get("alts") or [], 1)]
    run = G/("v040-stress" if st == "stress" else "v040-set20")
    return dict(refdir=refs/sid, run=run, score=run/"stress_scores"/f"{sid}.ours.primary.json", alts=alts, human=run/"stress_scores")
def chart_rec(sc, shift_ms):
    tr = S.tracks_by_key(sc); ph = S.phrases_by_key(sc)
    rec = {"shift_ms": shift_ms, "res": sc.get("resolution"), "tempos": sc.get("tempos"), "timeSignatures": sc.get("timeSignatures"), "parts": {}}
    for p in PARTS:
        k = (p, "expert")
        if k not in tr: continue
        lm = S.DRUM_LANE if p == "drums" else S.GUITAR_LANE
        g = {}
        for n in tr[k]: g.setdefault(n["tick"], []).append(n)
        rows = []
        for tk in sorted(g, key=lambda t: g[t][0]["ms"]):
            ns = g[tk]; lanes = sorted({lm[n["type"]] for n in ns if n["type"] in lm})
            if not lanes: continue
            rows.append([round((ns[0]["ms"]+shift_ms)/1000, 4), lanes, round(max(n.get("msLength") or 0 for n in ns)/1000, 4), tk,
                         round(ns[0]["ms"], 3), max(n.get("length") or 0 for n in ns)])
        rows.sort(key=lambda r: r[0])
        sp = [[round((x["ms"]+shift_ms)/1000, 4), round((x["ms"]+x["msLength"]+shift_ms)/1000, 4), x["tick"], x["length"]] for x in ph[k]["starPower"]]
        rec["parts"][p] = {"onsets": rows, "sp": sp}
    return rec
def build(label, st, sid):
    out = CACHE/f"{label}.json"
    if out.exists(): return rj(out)
    P = paths(st, sid); osc = rj(P["score"]); al = osc["alignment"]
    rec = {"label": label, "set": st, "humans": {}}
    rec["humans"]["primary"] = chart_rec(S.scan(str(P["refdir"]/"ref")), al["ref_delay_ms"])
    for lab, af in P["alts"]:
        hj = P["human"]/f"{sid}.human.{lab}.json"
        if not hj.exists(): continue
        h = rj(hj); rec["humans"][lab] = chart_rec(S.scan(str(af/"ref")), h["alignment"]["cand_total_shift_ms"])
    summ = rj(P["run"]/"summary.json")["songs"][sid]; folder = P["run"]/summ["folder"]
    rec["ours"] = chart_rec(S.scan(str(folder)), al["cand_total_shift_ms"]); rec["ours_folder"] = str(folder)
    out.write_text(json.dumps(rec)); return rec
def build_test():
    out = CACHE/"test_song.json"
    if out.exists(): return rj(out)
    folder = G/"v040"/"test_song"
    rec = {"label": "test_song", "set": "test", "humans": {}, "ours": chart_rec(S.scan(str(folder)), 0.0), "ours_folder": str(folder)}
    out.write_text(json.dumps(rec)); return rec
