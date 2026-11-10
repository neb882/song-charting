"""tables.py: the prereg's tables from results.json (labels only). Usage: python -I tables.py <results.json> <out.json>
Prints the tables (labels and 3-decimal numbers)."""
import json, sys
import numpy as np
R = json.loads(open(sys.argv[1]).read())["songs"]
F1_LOW = ("s02", "s04", "s06", "s12")
KEYS = ["allin1.relaxed", "allin1.strict", "events.relaxed", "events.strict"]
MEAS = ["f1", "lane_pos", "lane_time"]


def boot(d, n=10000, seed=7):
    d = np.array([x for x in d if x is not None], float)
    if not len(d):
        return None
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return {"mean": round(float(d.mean()), 3), "lo": round(float(np.percentile(m, 2.5)), 3),
            "hi": round(float(np.percentile(m, 97.5)), 3), "n": int(len(d))}


def v(song, who, key, m):
    x = (song["human"] if who == "human" else song["arms"].get(who, {})).get(key, {})
    return x.get(m) if x.get("n_pairs") else None


arms = sorted({a for s in R.values() for a in s["arms"]})
out = {}
for key in KEYS:
    out[key] = {}
    print(f"\n=== sections {key}")
    for m in MEAS:
        T = {}
        for setname, labels in (("all23", list(R)), ("bar19", [l for l in R if l not in F1_LOW])):
            row = {}
            comps = [("m05", "one")] + [(a, "human") for a in arms] + ([("cpu", "one")] if "cpu" in arms else [])
            for a, b in comps:
                d = [None if v(R[l], a, key, m) is None or v(R[l], b, key, m) is None
                     else v(R[l], a, key, m) - v(R[l], b, key, m) for l in labels]
                row[f"{a}-{b}"] = boot(d)
            for a in arms + ["human"]:
                xs = [v(R[l], a, key, m) for l in labels]
                xs = [x for x in xs if x is not None]
                row[f"mean_{a}"] = round(float(np.mean(xs)), 3) if xs else None
            T[setname] = row
            print(m, setname, json.dumps(row))
        out[key][m] = T
    # per song
    print(f"--- per song ({key}): pairs | f1 {' '.join(arms)} human | lane_pos {' '.join(arms)} human | well")
    ps = {}
    for l, s in R.items():
        o = s["arms"]["one"][key]
        ps[l] = {"pairs": o["pairs"], "n_pairs_scored": {a: s["arms"][a][key].get("n_pairs") for a in arms} | {
            "human": s["human"][key].get("n_pairs")},
                 **{f"{m}_{w}": v(s, w, key, m) for m in MEAS for w in arms + ["human"]}, "well": s["well"]}
        f = lambda x: "  -  " if x is None else f"{x:.3f}"
        print(f"{l:22s} {o['pairs']:4d} | " + " ".join(f(ps[l][f'f1_{w}']) for w in arms + ["human"]) + " | "
              + " ".join(f(ps[l][f'lane_pos_{w}']) for w in arms + ["human"]) + f" | {s['well']}")
    out[key]["per_song"] = ps
open(sys.argv[2], "w").write(json.dumps(out, indent=1))
