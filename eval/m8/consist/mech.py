"""mech.py: the mechanism test (orchestrator's follow-up). Splits the primary pairs (allin1.relaxed) by whether m05's
two instances came from the same take, from M8-02 part B's window picks (B/arms/<label>.json, arms.m05.takes.windows:
start/end in input seconds (end None = to the end), pick 0-3; chart time = input + lead-in pad, as the sections). An instance's takes = the picks
of the windows overlapping its compared span [start, start + L beats) by more than 0.5 s. same = both instances wholly
from one and the same take; diff = otherwise. Per group: m05 minus one per song, pooled over pairs, and the paired
bootstrap over songs. Usage: python -I mech.py <results.json with rows> <out.json>. Prints labels and numbers."""
import json, sys
from pathlib import Path
import numpy as np
M8 = Path("<scratchpad>/m8")
sys.path.insert(0, "<shm>/consist/code")
sys.path.insert(0, str(M8 / "m8-02" / "C" / "scripts"))
import m2lib as L  # noqa: E402
GOLD = {"refs": L.G / "v040f", "stress": L.G / "v040f-stress", "set20": L.G / "v040-set20"}
KEY = "allin1.relaxed"
F1_LOW = ("s02", "s04", "s06", "s12")
R = json.loads(open(sys.argv[1]).read())["songs"]


def takes_of(win, pad, s0, s1):
    return {w["pick"] for w in win if min(s1, (1e9 if w["end"] is None else w["end"]) + pad) - max(s0, w["start"] + pad) > 0.5}


out = {"songs": {}}
pooled = {"same": [], "diff": []}
for label, song in R.items():
    st, sid, _ = L.SONGS[label]
    pad = json.loads((GOLD[st] / sid / "report.json").read_text())["lead_in"]["pad_seconds"]
    win = json.loads((M8 / "m8-02" / "B" / "arms" / f"{label}.json").read_text())["arms"]["m05"]["takes"]["windows"]
    m, o = song["arms"]["m05"][KEY], song["arms"]["one"][KEY]
    if not m.get("rows"):
        continue
    ofi = {(r[0], r[1]): r for r in o["rows"]}
    inst = m["inst_s"]
    g = {"same": [], "diff": []}
    for i, j, f, lp, _ in m["rows"]:
        if (i, j) not in ofi:
            continue
        L_ = min(inst[i][2], inst[j][2])
        spans = []
        for k in (i, j):
            s0, s1, b = inst[k]
            spans.append(takes_of(win, pad, s0, s0 + (s1 - s0) * L_ / b))
        grp = "same" if len(spans[0]) == 1 and spans[0] == spans[1] else "diff"
        g[grp].append((f - ofi[(i, j)][2], lp - ofi[(i, j)][3]))
    out["songs"][label] = {k: {"n": len(v), "f1": float(np.mean([x[0] for x in v])) if v else None,
                               "lane_pos": float(np.mean([x[1] for x in v])) if v else None} for k, v in g.items()}
    for k in g:
        pooled[k] += g[k]
out["pooled"] = {k: {"n": len(v), "f1": float(np.mean([x[0] for x in v])), "lane_pos": float(np.mean([x[1] for x in v]))}
                 for k, v in pooled.items()}
for setname, labels in (("all23", list(out["songs"])), ("bar19", [l for l in out["songs"] if l not in F1_LOW])):
    for k in ("same", "diff"):
        for meas in ("f1", "lane_pos"):
            out[f"boot_{setname}_{k}_{meas}"] = L.boot([out["songs"][l][k][meas] for l in labels])
    # songs with both groups: diff minus same, per song
    both = [l for l in labels if out["songs"][l]["same"]["n"] and out["songs"][l]["diff"]["n"]]
    out[f"boot_{setname}_diff_minus_same_f1"] = L.boot([out["songs"][l]["diff"]["f1"] - out["songs"][l]["same"]["f1"]
                                                         for l in both])


def rd(x):
    if isinstance(x, float):
        return round(x, 3)
    if isinstance(x, dict):
        return {k: rd(v) for k, v in x.items()}
    return x


out = rd(out)
Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
f = lambda x: "  -   " if x is None else f"{x:+.3f}"
print("song                   n_same f1_same lane_same | n_diff f1_diff lane_diff   (m05 minus one)")
for l, s in out["songs"].items():
    print(f"{l:22s} {s['same']['n']:5d} {f(s['same']['f1'])} {f(s['same']['lane_pos'])} | {s['diff']['n']:5d} "
          f"{f(s['diff']['f1'])} {f(s['diff']['lane_pos'])}")
print("pooled", json.dumps(out["pooled"]))
for k, v in out.items():
    if k.startswith("boot_"):
        print(k, json.dumps(v))
