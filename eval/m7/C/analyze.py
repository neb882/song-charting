"""analyze.py: part C-c. Reads arms/<label>.json and arms/<label>.windows.json (this folder), the base arm's scores
(part A's <shm>/m7-Akeep/base/<set>/: stress_scores.json, scores/<id>.score.json; else this part's f0 arm) and the
humans' agreement (the base's stress_scores.json, else golden's gate3-new-stress and set20-main). Writes results.json
(numbers only, songs by label) and prints the report's tables as markdown."""
import json, sys
from pathlib import Path
import numpy as np
C = Path(__file__).resolve().parent
sys.path.insert(0, str(C)); sys.path.insert(0, "<shm>/m7/code-C")
from songs import SONGS, G
from eval import stress as S
AK = Path("<shm>/m7-Akeep/base")
MARGINS = {"m0": 0.0, "m02": 0.02, "m05": 0.05, "m10": 0.10}
rng = np.random.default_rng(20261107)

def stress_scores(st):
    p = AK / st / "stress_scores.json"
    if p.exists():
        return json.loads(p.read_text()), "A base"
    fb = {"stress": G / "gate3-new-stress/stress_scores.json", "set20": G / "set20-main/stress_scores.json"}[st]
    return json.loads(fb.read_text()), "golden fallback (" + fb.parent.name + ")"

SS = {st: stress_scores(st) for st in ("stress", "set20")}

def base_scores(label):
    st, sid, _ = SONGS[label]
    if st == "refs":
        p = AK / "refs" / "scores" / f"{sid}.score.json"
        if p.exists():
            g = S.comparison(json.loads(p.read_text()))["parts"]["guitar"]
            return {"primary": {"f1_50": g["f1_50"], "f1_100": g["f1_100"]}}, "A base"
        p = G / "v031" / "scores" / f"{sid}.score.json"   # the base's prior run (part A: guitar identical)
        if p.exists():
            g = S.comparison(json.loads(p.read_text()))["parts"]["guitar"]
            return {"primary": {"f1_50": g["f1_50"], "f1_100": g["f1_100"]}}, "prior run v031"
        return None, None
    d, src = SS[st]
    ours = d["songs"][sid]["ours"]
    return {lab: {"f1_50": c["parts"]["guitar"]["f1_50"], "f1_100": c["parts"]["guitar"]["f1_100"]}
            for lab, c in ours.items() if "guitar" in c["parts"]}, src

def humans(label):
    st, sid, _ = SONGS[label]
    if st == "refs":
        return None
    h = SS[st][0]["songs"][sid].get("humans") or {}
    v = [c["parts"]["guitar"]["f1_50"] for c in h.values() if "guitar" in c["parts"]]
    return round(float(np.mean(v)), 4) if v else None

def summ(scores):
    v50 = [s["f1_50"] for s in scores.values() if s]; v100 = [s["f1_100"] for s in scores.values() if s]
    return {"p50": scores["primary"]["f1_50"], "p100": scores["primary"]["f1_100"],
            "mean50": round(float(np.mean(v50)), 4), "mean100": round(float(np.mean(v100)), 4)}

def boot(a, b):
    d = np.array(a) - np.array(b)
    idx = rng.integers(0, len(d), (10000, len(d)))
    m = d[idx].mean(axis=1)
    return {"diff": round(float(d.mean()), 4), "ci": [round(float(np.percentile(m, 2.5)), 4),
                                                      round(float(np.percentile(m, 97.5)), 4)], "n": len(d)}

songs = {}
for label in SONGS:
    p = C / "arms" / f"{label}.json"
    if not p.exists():
        continue
    r = json.loads(p.read_text())
    arms = r["arms"]
    if not all(a in arms for a in ("m0", "m02", "m05", "m10", "f1", "f2", "f3")):
        continue
    res = {"set": SONGS[label][0], "charts": len(r["charts"]), "humans_f1_50": humans(label), "arms": {}}
    for a in list(MARGINS) + ["f0", "f1", "f2", "f3", "q0", "q05"]:
        if a not in arms:
            continue
        v = arms[a]; src = arms[v["same_as"]] if "same_as" in v else v
        res["arms"][a] = summ(src["scores"])
    b, bsrc = base_scores(label)
    if b is None and "f0" in res["arms"]:
        res["arms"]["one"] = dict(res["arms"]["f0"]); res["one_source"] = "f0 (this part)"
    elif b is not None:
        res["arms"]["one"] = summ(b); res["one_source"] = bsrc
    res["oracle_best"] = max((res["arms"][f]["mean50"], f) for f in ("f0", "f1", "f2", "f3") if f in res["arms"])
    wins = r["windows"]; wj = C / "arms" / f"{label}.windows.json"
    ww = json.loads(wj.read_text()) if wj.exists() else None
    picks = {a: (arms[arms[a]["same_as"]] if "same_as" in arms[a] else arms[a])["picks"] for a in list(MARGINS) + ["q0", "q05"]}
    res["built"] = [a for a in arms if "same_as" not in arms[a]]
    res["q_same_picks_as"] = {q: arms[q].get("same_picks_as") for q in ("q0", "q05")}
    res["windows"] = len(wins)
    res["switched"] = {a: sum(1 for k in pk if k != 0) for a, pk in picks.items()}
    res["seams"] = {a: sum(1 for x, y in zip(pk, pk[1:]) if x != y) for a, pk in picks.items()}
    res["differs_from_m05"] = {a: [i for i, (x, y) in enumerate(zip(pk, picks["m05"])) if x != y]
                               for a, pk in picks.items() if a != "m05"}
    if ww:
        det = []
        for i, w in enumerate(ww):
            if any(i in v for v in res["differs_from_m05"].values()) or any(picks[a][i] for a in picks):
                det.append({"i": i, "s": round(w["start"], 1), "len_s": None if w["end"] is None else round(w["end"] - w["start"], 1),
                            "human": w["human"], "take_onsets": w["take_onsets"], "matched": w["matched"],
                            "scores": w["scores"], "picks": {a: picks[a][i] for a in picks}})
        res["window_detail"] = det
        lose = []
        for i, w in enumerate(ww):
            if None in w["matched"]:
                continue
            best = max(w["matched"]); pk = picks["m0"][i]
            if w["matched"][pk] < best:
                lose.append({"i": i, "picked": pk, "matched": w["matched"], "human": w["human"],
                             "f1": w["f1"]})
        res["m0_loses_to_better_take"] = lose
        # the same by the window's F1 against the primary (more matched onsets can come with more extra notes)
        res["loses_by_f1"] = {a: sum(1 for i, w in enumerate(ww) if None not in w["f1"]
                                     and w["f1"][picks[a][i]] < max(w["f1"]) - 1e-9) for a in picks}
        res["loses_by_f1_0.05"] = {a: sum(1 for i, w in enumerate(ww) if None not in w["f1"]
                                          and w["f1"][picks[a][i]] < max(w["f1"]) - 0.05) for a in picks}
        res["windows_with_humans"] = sum(1 for w in ww if w["human"])
    songs[label] = res

def pool(keys, arm, measure="mean50"):
    return [songs[k]["arms"][arm][measure] for k in keys]

out = {"songs": songs, "pooled": {}}
left_out = [k for k, s in songs.items() if s["humans_f1_50"] is not None and s["humans_f1_50"] < 0.6]
groups = {"all": [k for k in songs if k not in left_out and "one" in songs[k]["arms"]]}
groups["without_refs"] = [k for k in groups["all"] if songs[k]["set"] != "refs"]
out["left_out_humans_under_0.6"] = left_out
for g, keys in groups.items():
    if not keys:
        continue
    pg = {"n": len(keys)}
    for meas in ("p50", "p100", "mean50", "mean100"):
        pg[meas] = {a: round(float(np.mean(pool(keys, a, meas))), 4) for a in list(MARGINS) + ["one", "q0", "q05"]}
        pg[meas]["oracle_best_take_per_song"] = round(float(np.mean([max(songs[k]["arms"][f][meas] for f in ("f0", "f1", "f2", "f3")) for k in keys])), 4)
        pg[meas]["oracle_mean_of_takes"] = round(float(np.mean([np.mean([songs[k]["arms"][f][meas] for f in ("f0", "f1", "f2", "f3") if f in songs[k]["arms"]]) for k in keys])), 4)
        pg[meas]["vs_m05"] = {a: boot(pool(keys, a, meas), pool(keys, "m05", meas)) for a in list(MARGINS) + ["one", "q0", "q05"] if a != "m05"}
        pg[meas]["vs_one"] = {a: boot(pool(keys, a, meas), pool(keys, "one", meas)) for a in list(MARGINS) + ["q0", "q05"]}
    out["pooled"][g] = pg
(C / "results.json").write_text(json.dumps(out, indent=1))

print("| song | charts | humans F1@50 | one | m0 | m02 | m05 | m10 | best take | windows | switched m0/m02/m05/m10 | seams m0/m02/m05/m10 |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for k, s in songs.items():
    a = s["arms"]
    f = lambda x: "—" if x not in a else f"{a[x]['p50']:.3f} / {a[x]['mean50']:.3f}"
    print(f"| {k} | {s['charts']} | {s['humans_f1_50'] if s['humans_f1_50'] is not None else '—'} | {f('one')} | {f('m0')} | {f('m02')} | {f('m05')} | {f('m10')} | "
          f"{s['oracle_best'][1]} {s['oracle_best'][0]:.3f} | {s['windows']} | {'/'.join(str(s['switched'][m]) for m in MARGINS)} | {'/'.join(str(s['seams'][m]) for m in MARGINS)} |")
print(json.dumps(out["pooled"], indent=1))
print("left out:", left_out)
