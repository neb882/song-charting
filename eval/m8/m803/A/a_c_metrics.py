"""a_c_metrics.py: reads A/chunks/LABEL_W{0,120,180,240}.json (a_c_run.py) and each kept folder's sections/segments.json (the whole run's beats, downbeats, bpm,
segments; labels only), scores per song and W: beat F1 and downbeat F1 at 70 ms against the whole run, bpm ratio, segment starts' F1 at 1 s (starts after the first,
which is always 0) pooled and per song, label agreement on matched starts, seconds, peak RSS (and the phase peaks). First the whole-song reproduction (W0 vs kept) for
the songs that have it. Writes A/a_c_metrics.json (3 decimals) and prints the bar's table per W."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE)); sys.path[:0] = ["<shm>/m8/code-cpu/eval/scorer"]
from songs_map import SONGS
import score as S
def prf(r, c, tol):
    r = np.sort(np.asarray(r, float)); c = np.sort(np.asarray(c, float)); pairs = S.match(r, c, tol); tp = len(pairs)
    p = tp/len(c) if len(c) else 0.0; q = tp/len(r) if len(r) else 0.0
    return (2*p*q/(p+q) if p+q else 0.0), tp, len(r), len(c), pairs
def r3(x):
    if isinstance(x, (float, np.floating)): return round(float(x), 3)
    if isinstance(x, dict): return {k: r3(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [r3(v) for v in x]
    return x
def starts(seg): return [s[0] for s in seg[1:]]
out = {"songs": {}, "W": {}}
for lab in SONGS:
    kp = SONGS[lab][1]/"sections/segments.json"
    if not kp.exists(): continue
    k = json.loads(kp.read_text()); d = {}
    for W in (0, 120, 180, 240):
        f = HERE/"chunks"/f"{lab}_W{W}.json"
        if not f.exists(): continue
        c = json.loads(f.read_text())
        bf, *_ = prf(k["beats"], c["beats"], 0.07); df, *_ = prf(k["downbeats"], c["downbeats"], 0.07)
        sf, tp, nr, nc, pairs = prf(starts(k["segments"]), starts(c["segments"]), 1.0)
        ks, cs = k["segments"][1:], c["segments"][1:]
        agree = [ks[i][2] == cs[j][2] for i, j in pairs]
        d[W] = {"beat_f1": bf, "downbeat_f1": df, "bpm_ratio": (c["bpm"]/k["bpm"]) if k["bpm"] and c["bpm"] else None, "bpm_whole": k["bpm"], "bpm_chunk": c["bpm"],
                "beats": [len(k["beats"]), len(c["beats"])], "seg_start_f1": sf, "seg_tp_nr_nc": [tp, nr, nc], "label_agree": (sum(agree)/len(agree)) if agree else None,
                "identical": k["beats"] == c["beats"] and k["downbeats"] == c["downbeats"] and k["segments"] == c["segments"], "windows": c.get("windows"),
                "seconds": c["seconds"], "vmhwm_mb": c["vmhwm_mb"], **{x: c.get(x) for x in c if x.startswith("vmhwm_after")}}
    out["songs"][lab] = d
def fails(v):
    return [m for m, ok in (("beat", v["beat_f1"] >= .99), ("down", v["downbeat_f1"] >= .98), ("bpm", abs((v["bpm_ratio"] or 0)-1) <= .01), ("seg", v["seg_start_f1"] >= .90)) if not ok]
for W in (120, 180, 240):
    labs = [l for l, d in out["songs"].items() if W in d]
    if not labs: continue
    tp = sum(out["songs"][l][W]["seg_tp_nr_nc"][0] for l in labs); nr = sum(out["songs"][l][W]["seg_tp_nr_nc"][1] for l in labs); nc = sum(out["songs"][l][W]["seg_tp_nr_nc"][2] for l in labs)
    pooled = 2*tp/(nr+nc) if nr+nc else None
    g = lambda key: [out["songs"][l][W][key] for l in labs]
    out["W"][W] = {"n_songs": len(labs), "min_beat_f1": min(g("beat_f1")), "min_downbeat_f1": min(g("downbeat_f1")), "max_abs_bpm_dev": max(abs(x-1) for x in g("bpm_ratio") if x),
        "seg_start_f1_pooled": pooled, "min_seg_start_f1": min(g("seg_start_f1")), "n_identical": sum(g("identical")),
        "fails": {l: fails(out["songs"][l][W]) for l in labs if fails(out["songs"][l][W])}}
out = json.loads(json.dumps(out, default=str)) if False else out
json.dump(r3({"songs": {l: {str(W): v for W, v in d.items()} for l, d in out["songs"].items()}, "W": {str(W): v for W, v in out["W"].items()}}), open(HERE/"a_c_metrics.json", "w"), indent=1)
for W, v in out["W"].items(): print(W, r3(v))
print("whole-song reproduction:", {l: d[0]["identical"] for l, d in out["songs"].items() if 0 in d})
