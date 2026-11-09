"""b_tables.py: part B's pooled figures and tables. Reads B/arms/<label>.json (built arms' F1 per chart) and
B/part_b_eval.json (b_analyze.py: the evaluator's picks and scores). Writes B/part_b.json (pooled figures, 3 decimals)
and B/part_b.md (tables); prints nothing. Labels only.
Usage: python3 -I b_tables.py <m8-02 folder>"""
import json, sys
from pathlib import Path
import numpy as np
M = Path(sys.argv[1])
EV = json.loads((M / "B" / "part_b_eval.json").read_text())["songs"]
LABELS = list(EV)
ARMS = {l: json.loads((M / "B" / "arms" / f"{l}.json").read_text()) for l in LABELS}
LEFT_OUT = ["s02", "s04", "s06", "s12"]
ALIGNED = json.loads((M / "B" / "aligned.json").read_text())   # aligned.py
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
R3 = lambda x: None if x is None else round(float(x), 3)
GROUPS = {"pooled19": [l for l in LABELS if l not in LEFT_OUT],
          "pooled_no_refs13": [l for l in LABELS if l not in LEFT_OUT and l not in REFS],
          "all23": LABELS}


def boot(d, seed=20261109):
    d = np.array(d, float)
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (10000, len(d)))].mean(axis=1)
    return {"diff": R3(d.mean()), "lo": R3(np.percentile(m, 2.5)), "hi": R3(np.percentile(m, 97.5)), "n": len(d),
            "worst": R3(d.min()), "down_gt_0.01": int((d < -0.01).sum()), "up_gt_0.01": int((d > 0.01).sum())}


def built(l, arm, key, meas):
    a = ARMS[l]["arms"]
    v = a[a[arm]["same_as"]] if "same_as" in a[arm] else a[arm]
    sc = v["scores"]
    if meas == "p":
        return sc["primary"][key]
    if meas == "meanA":   # the well-aligned charts only
        return float(np.mean([x[key] for c, x in sc.items() if x and ALIGNED[l][c]["ok"]]))
    return float(np.mean([x[key] for x in sc.values() if x]))


BUILT = ["one", "m0", "m02", "m05", "m10", "f0", "f1", "f2", "f3", "q05", "cpu_one", "cpu_m05", "cf0", "cf1", "cf2", "cf3"]
PAIRS = [(a, "m05") for a in ("m0", "m02", "m10", "q05", "f0", "f1", "f2", "f3", "one")] + \
        [("m05", "cpu_m05"), ("one", "cpu_one"), ("cpu_m05", "cpu_one")]
out = {"built": {}, "evaluator": {}, "per_song": {}}
for g, labs in GROUPS.items():
    out["built"][g] = {}
    for key in ("f1_50", "f1_100"):
        for meas in ("p", "mean", "meanA"):
            k = f"{meas}_{key}"
            out["built"][g][k] = {"mean": {a: R3(np.mean([built(l, a, key, meas) for l in labs])) for a in BUILT},
                                  "diff": {f"{a}-{b}": boot([built(l, a, key, meas) - built(l, b, key, meas) for l in labs])
                                           for a, b in PAIRS}}
    out["built"][g]["best_take_p_f1_50"] = R3(np.mean([max(built(l, f"f{k}", "f1_50", "p") for k in range(4)) for l in labs]))
    out["built"][g]["cpu_best_take_p_f1_50"] = R3(np.mean([max(built(l, f"cf{k}", "f1_50", "p") for k in range(4)) for l in labs]))
    # the evaluator (steps 4-5): every pick rule against a_m05 (today's picks through the same evaluator)
    out["evaluator"][g] = {}
    for meas in ("p50", "mean50", "mean50_aligned", "cpu_p50", "cpu_mean50", "cpu_mean50_aligned"):
        rules = list(EV[labs[0]][meas])
        e = {"mean": {r: R3(np.mean([EV[l][meas][r] for l in labs])) for r in rules}, "vs_a_m05": {}}
        for r in rules:
            if r != "a_m05":
                e["vs_a_m05"][r] = boot([EV[l][meas][r] - EV[l][meas]["a_m05"] for l in labs])
        e["best_take_per_song"] = R3(np.mean([max(EV[l][meas][f"take{k}"] for k in range(4)) for l in labs]))
        out["evaluator"][g][meas] = e
    out["evaluator"][g]["loses_by_0.05"] = {r: sum(EV[l]["loses_by_0.05"][r] for l in labs) for r in EV[labs[0]]["loses_by_0.05"]}
    out["evaluator"][g]["switched"] = {r: sum(EV[l]["switched"][r] for l in labs) for r in EV[labs[0]]["switched"]}
    out["evaluator"][g]["windows"] = sum(EV[l]["windows"] for l in labs)
for l in LABELS:
    a = ARMS[l]
    out["per_song"][l] = {"route_check": a.get("route_check"), "kept_unchanged": all(v for k, v in a.items() if k.startswith("kept_unchanged")),
                          "humans_f1_50": EV[l]["humans_f1_50"], "left_out": l in LEFT_OUT,
                          "p_f1_50": {x: R3(built(l, x, "f1_50", "p")) for x in BUILT},
                          "mean_f1_50": {x: R3(built(l, x, "f1_50", "mean")) for x in BUILT},
                          "same_as": {x: a["arms"][x]["same_as"] for x in a["arms"] if "same_as" in a["arms"][x]},
                          "switched_built": {x: sum(1 for k in (a["arms"][x].get("picks") or []) if k) for x in ("m0", "m02", "m05", "m10", "q05", "cpu_m05")},
                          "evaluator_vs_built_max_abs": EV[l]["evaluator_vs_built_max_abs"],
                          "calib_err_max": R3(max(c["abs_err_sum"] for c in EV[l]["calibration_gpu"].values())),
                          "eval_p50": {r: EV[l]["p50"][r] for r in ("a_m05", "L1_p06", "D1", "c_m05", "oracle_window")}}
(M / "B" / "part_b.json").write_text(json.dumps(out, indent=1))

# ---- Markdown
f = lambda x: "-" if x is None else f"{x:.3f}"
d = lambda b: f"{b['diff']:+.3f} [{b['lo']:+.3f}, {b['hi']:+.3f}] worst {b['worst']:+.3f}, down/up {b['down_gt_0.01']}/{b['up_gt_0.01']}"
L = []
for g in GROUPS:
    B = out["built"][g]
    L += [f"\n**Built arms, {g}** (F1@50 / F1@100 against the primary; mean over charts F1@50):\n",
          "| arm | primary F1@50 | primary F1@100 | mean F1@50 | mean F1@50, well-aligned charts |", "|---|---|---|---|---|"]
    for a in BUILT:
        L.append(f"| {a} | {f(B['p_f1_50']['mean'][a])} | {f(B['p_f1_100']['mean'][a])} | {f(B['mean_f1_50']['mean'][a])} | {f(B['meanA_f1_50']['mean'][a])} |")
    L.append(f"| best GPU take per song | {f(B['best_take_p_f1_50'])} | | |")
    L.append(f"| best CPU take per song | {f(B['cpu_best_take_p_f1_50'])} | | |")
    L += ["", "| difference | primary F1@50 [95 % CI] | primary F1@100 | mean F1@50 | mean F1@50, well-aligned |", "|---|---|---|---|---|"]
    for a, b in PAIRS:
        k = f"{a}-{b}"
        L.append(f"| {k} | {d(B['p_f1_50']['diff'][k])} | {B['p_f1_100']['diff'][k]['diff']:+.3f} [{B['p_f1_100']['diff'][k]['lo']:+.3f}, {B['p_f1_100']['diff'][k]['hi']:+.3f}] | {d(B['mean_f1_50']['diff'][k])} | {d(B['meanA_f1_50']['diff'][k])} |")
    E = out["evaluator"][g]
    L += [f"\n**The take scores and the candidates (evaluator), {g}** ({E['windows']} windows; vs a_m05 = today's picks "
          "through the same evaluator):\n",
          "| rule | primary F1@50 | vs a_m05 [95 % CI] | mean F1@50 vs a_m05 | well-aligned mean vs a_m05 | switched | >0.05 below best |", "|---|---|---|---|---|---|---|"]
    for r in E["p50"]["mean"]:
        v = E["p50"]["vs_a_m05"].get(r); vm = E["mean50"]["vs_a_m05"].get(r)
        vms = "%+.3f" % vm["diff"] if vm else "-"
        va = E["mean50_aligned"]["vs_a_m05"].get(r); vas = "%+.3f [%+.3f, %+.3f]" % (va["diff"], va["lo"], va["hi"]) if va else "-"
        L.append(f"| {r} | {f(E['p50']['mean'][r])} | {d(v) if v else '-'} | {vms} | {vas} | {E['switched'][r]} | {E['loses_by_0.05'][r]} |")
    L += [f"\n**CPU takes (evaluator), {g}** (the models fit on GPU windows):\n", "| rule | primary F1@50 | vs a_m05 (cpu) |", "|---|---|---|"]
    for r in E["cpu_p50"]["mean"]:
        v = E["cpu_p50"]["vs_a_m05"].get(r)
        L.append(f"| {r} | {f(E['cpu_p50']['mean'][r])} | {d(v) if v else '-'} |")
L += ["\n**Per song** (primary F1@50, built; humans' own agreement; evaluator's error against the built m05):\n",
      "| song | humans | one | m05 | m0 | q05 | best take | cpu_one | cpu_m05 | m05 switched | eval L1_p06 - a_m05 | eval D1 - a_m05 | eval err |",
      "|" + "---|" * 13]
for l, s in out["per_song"].items():
    p, e = s["p_f1_50"], s["eval_p50"]
    L.append(f"| {l}{' (out)' if s['left_out'] else ''} | {f(s['humans_f1_50'])} | {f(p['one'])} | {f(p['m05'])} | {f(p['m0'])} | {f(p['q05'])} | "
             f"{f(max(p[f'f{k}'] for k in range(4)))} | {f(p['cpu_one'])} | {f(p['cpu_m05'])} | {s['switched_built']['m05']} | "
             f"{e['L1_p06'] - e['a_m05']:+.3f} | {e['D1'] - e['a_m05']:+.3f} | {f(s['evaluator_vs_built_max_abs']['m05'])} |")
(M / "B" / "part_b.md").write_text("\n".join(L) + "\n")
