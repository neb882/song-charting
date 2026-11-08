"""analyze.py: the M8 take-score measurement. Reads <shm>/m8t/<label>.ext.json and .stem.npz (extract.py,
stems.py), part C's arms/<label>.json (each window's recorded take scores and the built arms' picks and scores) and
results.json (the humans' agreement, the songs left out). Per song: calibrates each human chart's shift so the four
lone takes' F1@50 reproduce part C's, splices onsets window by window with each score's picks, scores the splice
against every chart with score.py's onset F1@50 (match, span, n_cand_eff); writes results.json (numbers only,
songs by label) and prints tables.md."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *
sys.path.insert(0, str(ORCH))
from songcharter.assemble import silent_onsets, LEVEL_FRAME_S
TOL, SPAN_MARGIN = 0.05, 0.100
rng = np.random.default_rng(20261108)
R3 = lambda x: None if x is None else round(float(x), 3)
PC = json.loads((PARTC / "results.json").read_text())

def match(r, c, tol=TOL):
    pairs, j, n = [], 0, len(c)
    for i, t in enumerate(r):
        while j < n and c[j] < t - tol: j += 1
        if j < n and c[j] <= t + tol: pairs.append((i, j)); j += 1
    return pairs

def f1_vs(h, cand):
    """score.py's onset_50ms F1 of sorted candidate times against one human chart."""
    lo, hi = h["span"][0] - SPAN_MARGIN, h["span"][1] + SPAN_MARGIN
    co = [t for t in cand if lo <= t <= hi]
    pr = match(h["t"], co); mj = {j for _, j in pr}
    nc = len(mj) + sum(1 for j, t in enumerate(co) if j not in mj and h["span"][0] <= t <= h["span"][1])
    m, nr = len(pr), len(h["t"])
    p = m / nc if nc else 0.0; r = m / nr if nr else 0.0
    return round(2 * p * r / (p + r), 4) if p + r else 0.0

def win_f1(a, b, tol=TOL):
    if not len(a) and not len(b): return 1.0
    return 2 * len(match(a, b, tol)) / (len(a) + len(b))

def calibrate(h, takes_ms, target, coarse=None):
    """The shift (ms) for which the lone takes' F1@50 against h reproduce part C's (target: per take)."""
    ht = np.array(h["t"]) * 1000.0
    t0 = np.array(takes_ms[0]); diffs = []
    for x in t0:
        lo, hi = np.searchsorted(ht, x - 30000), np.searchsorted(ht, x + 30000)
        diffs.append(ht[lo:hi] - x)
    diffs = np.concatenate(diffs)
    hist, edges = np.histogram(diffs, bins=np.arange(-30000, 30001, 5))
    sm = np.convolve(hist, np.ones(21), "same")
    if coarse is None:   # the primary: the peak of the onset-difference histogram
        coarse = edges[int(np.argmax(sm))] + 2.5
    grid = []
    for s in np.arange(coarse - 80, coarse + 80, 0.5):
        f = [f1_vs(h, [(x + s) / 1000.0 for x in t]) for t in takes_ms]
        grid.append((round(sum(abs(a - b) for a, b in zip(f, target)), 4), float(s), f))
    err = min(g[0] for g in grid)
    good = [g for g in grid if g[0] == err]   # the middle of the shifts that reach the least error
    _, s, f = good[len(good) // 2]
    return s, err, f

songs, LOG, ALLW = {}, [], []
for label, (st, sid, kept, cl) in SONGS.items():
    if len(sys.argv) > 1 and label not in sys.argv[1:]: continue
    ext = json.loads((SHM / f"{label}.ext.json").read_text())
    stem = np.load(SHM / f"{label}.stem.npz")
    res = json.loads((PARTC / "arms" / f"{cl}.json").read_text())
    arms = res["arms"]; real = lambda a: arms[arms[a]["same_as"]] if "same_as" in arms[a] else arms[a]
    wins = res["windows"]; charts = res["charts"]
    nm = lambda a: arms[a].get("same_as", a)
    lone = [ext["arms"][nm(f"f{k}")]["ms"] for k in range(4)]
    shift, cal = {}, {}
    lagp = SHM / f"{label}.lag.json"
    lags = json.loads(lagp.read_text()) if lagp.exists() else {"primary": 0.0}
    for c in charts:   # the primary first; an alt's coarse shift is the primary's less its audio lag (audiolag.py)
        co = None if c == "primary" else shift["primary"] - lags[c]
        tgt = [real(f"f{k}")["scores"][c]["f1_50"] for k in range(4)]
        s, err, f = calibrate(ext["humans"][c], lone, tgt, co)
        shift[c] = s; cal[c] = {"shift_ms": round(s, 1), "abs_err_sum": err}
    sp = shift["primary"]
    take_t = [np.array([(x + sp) / 1000.0 for x in t]) for t in lone]   # the takes' clock (input seconds)
    H = ext["humans"]
    def score(cand_take_t):
        return {c: f1_vs(H[c], sorted(t + (shift[c] - sp) / 1000.0 for t in cand_take_t)) for c in charts}
    bounds = [(w["start"], np.inf if w["end"] is None else w["end"]) for w in wins]
    cut = lambda t, a, b: t[(t >= a) & (t < b)]
    def splice(picks):
        return [x for (a, b), k in zip(bounds, picks) for x in cut(take_t[k], a, b)]
    # --- per window features
    env, tenv, pk, pks, lv = stem["env"], stem["t_env"], stem["peaks"], stem["peak_s"], stem["levels"]
    hp = np.array(H["primary"]["t"])
    t0 = take_t[0]; j = np.clip(np.searchsorted(pk, t0), 1, len(pk) - 1)
    near = np.where(np.abs(pk[j] - t0) < np.abs(pk[j - 1] - t0), pk[j], pk[j - 1]) - t0
    poff = float(np.median(near[np.abs(near) < 0.1]))   # the stem peaks' lag behind the kept take's onsets
    W = []
    for i, (a, b) in enumerate(bounds):
        sel = (tenv >= a) & (tenv < b)
        med = float(np.median(env[sel])) if sel.any() else 0.0
        strong = pk[(pk >= a) & (pk < b) & (pks > med)]
        pkc = pk - poff; strong2 = pkc[(pkc >= a) & (pkc < b) & (pks > med)]   # the peaks moved back by that lag
        hw = cut(hp, a, b)
        row = {"n": [], "b": [], "b_p": [], "b_r": [], "silent": [], "f1h": [], "mh": [], "extra": [], "extra_ev": [], "b2": [], "extra_ev2": []}
        on0 = cut(take_t[0], a, b)
        for k in range(4):
            on = cut(take_t[k], a, b)
            m = len(match(on, strong))
            row["n"].append(len(on))
            row["b"].append(1.0 if not len(on) and not len(strong) else 2 * m / (len(on) + len(strong)))
            m2 = len(match(on, strong2))
            row["b2"].append(1.0 if not len(on) and not len(strong2) else 2 * m2 / (len(on) + len(strong2)))
            row["b_p"].append(m / len(on) if len(on) else None); row["b_r"].append(m / len(strong) if len(strong) else None)
            row["silent"].append(len(silent_onsets(list(on), lv, LEVEL_FRAME_S)))
            hm = hw + (shift["primary"] - sp) / 1000.0
            row["f1h"].append(win_f1(list(hm), list(on))); row["mh"].append(len(match(list(hm), list(on))))
            mj = {j for _, j in match(list(on0), list(on))}
            ex = [x for j, x in enumerate(on) if j not in mj]
            row["extra"].append(len(ex)); row["extra_ev"].append(len(match(ex, list(strong))))
            row["extra_ev2"].append(len(match(ex, list(strong2))))
        row["a"] = list(wins[i]["scores"])
        row["c"] = list(real("q0")["takes"]["windows"][i]["scores"])
        row["human"] = len(hw)
        W.append(row)
    def pick_by(key, margin, fn=None):
        out = []
        for r in W:
            s = fn(r) if fn else r[key]
            best = max(range(4), key=lambda k: (s[k], -k))
            out.append(best if s[best] > s[0] + margin else 0)
        return out
    def pick_e(thr, ev="extra_ev"):
        out = []
        for r in W:
            ok = [k for k in range(1, 4) if r["n"][k] > r["n"][0] and r["extra"][k]
                  and r[ev][k] / r["extra"][k] >= thr]
            out.append(max(ok, key=lambda k: (r["n"][k], -k)) if ok else 0)
        return out
    P = {}
    for m, ms in ((0.0, "0"), (0.02, "02"), (0.05, "05")):
        P[f"a_m{ms}"] = pick_by("a", m)
        P[f"b_m{ms}"] = pick_by("b", m)
        P[f"c_m{ms}"] = pick_by("c", m)
        P[f"d_m{ms}"] = pick_by(None, m, lambda r: [0.5 * x + 0.5 * y for x, y in zip(r["a"], r["b"])])
        P[f"b2_m{ms}"] = pick_by("b2", m)
        P[f"d2_m{ms}"] = pick_by(None, m, lambda r: [0.5 * x + 0.5 * y for x, y in zip(r["a"], r["b2"])])
    P["e_t50"] = pick_e(0.5); P["e_t70"] = pick_e(0.7)
    P["e2_t50"] = pick_e(0.5, "extra_ev2"); P["e2_t70"] = pick_e(0.7, "extra_ev2")
    P["oracle_window"] = [max(range(4), key=lambda k: (r["f1h"][k], -k)) for r in W]
    for k in range(4): P[f"take{k}"] = [k] * len(W)
    # the built arms' own picks (the pipeline compares unrounded scores; the recorded ones are rounded to 4 places)
    tie = {p: sum(x != y for x, y in zip(P[p], arms[a]["picks"])) for p, a in
           (("a_m0", "m0"), ("a_m02", "m02"), ("a_m05", "m05"), ("c_m0", "q0"), ("c_m05", "q05"))}
    for p, a in (("a_m0", "m0"), ("a_m02", "m02"), ("a_m05", "m05"), ("c_m0", "q0"), ("c_m05", "q05")):
        P[p] = list(arms[a]["picks"])
    sc = {p: score(splice(pk_)) for p, pk_ in P.items()}
    # check: the built arms' own charts through this evaluator, and their onset splices, against part C's scores
    chk = {}
    for a in ("m0", "m05", "q0", "q05"):
        built = score([np.array([(x + sp) / 1000.0 for x in ext["arms"][nm(a)]["ms"]])][0])
        rec = {c: real(a)["scores"][c]["f1_50"] for c in charts}
        chk[a] = {"built_vs_recorded_max_abs": R3(max(abs(built[c] - rec[c]) for c in charts)),
                  "splice_vs_recorded_mean": R3(np.mean([sc[{"m0": "a_m0", "m05": "a_m05", "q0": "c_m0", "q05": "c_m05"}[a]][c] - rec[c] for c in charts]))}
    loses = {p: sum(1 for r, k in zip(W, pk_) if r["f1h"][k] < max(r["f1h"]) - 0.05) for p, pk_ in P.items()}
    songs[label] = {"rounding_pick_differences": tie, "set": st, "charts": len(charts), "windows": len(W), "calibration": cal, "check": chk,
                    "humans_f1_50": PC["songs"][cl]["humans_f1_50"], "left_out": cl in PC["left_out_humans_under_0.6"],
                    "p50": {p: R3(v["primary"]) for p, v in sc.items()},
                    "mean50": {p: R3(np.mean(list(v.values()))) for p, v in sc.items()},
                    "recorded": {a: {"p50": R3(real(a)["scores"]["primary"]["f1_50"]),
                                     "mean50": R3(np.mean([real(a)["scores"][c]["f1_50"] for c in charts]))}
                                 for a in ("m0", "m05", "q0", "q05", "f0", "f1", "f2", "f3")},
                    "switched": {p: sum(1 for k in pk_ if k) for p, pk_ in P.items()},
                    "loses_by_f1_0.05": loses,
                    "b_precision_median": R3(np.median([x for r in W for x in r["b_p"] if x is not None])),
                    "b_recall_median": R3(np.median([x for r in W for x in r["b_r"] if x is not None])),
                    "silent_share": R3(sum(sum(r["silent"]) for r in W) / max(1, sum(sum(r["n"]) for r in W)))}
    for r in W:
        r["song"] = label; r["left_out"] = songs[label]["left_out"]
        r["d"] = [0.5 * x + 0.5 * y for x, y in zip(r["a"], r["b"])]
        r["d2"] = [0.5 * x + 0.5 * y for x, y in zip(r["a"], r["b2"])]
    ALLW.extend(W)
    # timing of the stem peaks: median signed offset from each take-0 onset to its nearest peak (within 100 ms)
    t0 = take_t[0]; j = np.clip(np.searchsorted(pk, t0), 1, len(pk) - 1)
    near = np.where(np.abs(pk[j] - t0) < np.abs(pk[j - 1] - t0), pk[j], pk[j - 1]) - t0
    songs[label]["peak_offset_ms_median"] = R3(1000 * np.median(near[np.abs(near) < 0.1]))
    LOG.append(label)

def boot(a, b):
    d = np.array(a) - np.array(b); idx = rng.integers(0, len(d), (10000, len(d))); m = d[idx].mean(axis=1)
    return {"diff": R3(d.mean()), "ci": [R3(np.percentile(m, 2.5)), R3(np.percentile(m, 97.5))], "n": len(d),
            "worst": R3(d.min()), "down_gt_0.01": int((d < -0.01).sum()), "up_gt_0.01": int((d > 0.01).sum())}

PICKS = list(next(iter(songs.values()))["p50"])
keys = [k for k, s in songs.items() if not s["left_out"]]
out = {"songs": songs, "pooled": {}, "left_out": [k for k in songs if songs[k]["left_out"]]}
for meas in ("p50", "mean50"):
    pg = {"n": len(keys), "mean": {}, "vs_today_a_m05": {}}
    for p in PICKS:
        pg["mean"][p] = R3(np.mean([songs[k][meas][p] for k in keys]))
        if p != "a_m05":
            pg["vs_today_a_m05"][p] = boot([songs[k][meas][p] for k in keys], [songs[k][meas]["a_m05"] for k in keys])
    pg["mean"]["best_take_per_song"] = R3(np.mean([max(songs[k][meas][f"take{j}"] for j in range(4)) for k in keys]))
    pg["mean"]["recorded_today_m05"] = R3(np.mean([songs[k]["recorded"]["m05"][meas] for k in keys]))
    pg["loses_by_f1_0.05_total"] = {p: sum(songs[k]["loses_by_f1_0.05"][p] for k in keys) for p in PICKS}
    out["pooled"][meas] = pg
# does a score order two takes in a window as the primary does? (pairs of takes whose window F1 against the primary
# differs by more than 0.05, windows with human notes, pooled songs only)
conc = {}
for key in ("a", "b", "c", "d", "b2", "d2", "n"):
    agree = tot = 0
    for r in ALLW:
        if r["left_out"] or not r["human"]: continue
        for i in range(4):
            for j in range(i + 1, 4):
                dh = r["f1h"][i] - r["f1h"][j]
                if abs(dh) <= 0.05: continue
                ds = r[key][i] - r[key][j]
                if ds == 0: continue
                tot += 1; agree += (ds > 0) == (dh > 0)
    conc[key] = {"pairs": tot, "same_order_share": R3(agree / tot if tot else None)}
out["pairwise_concordance_with_primary"] = conc
def rnd(x):   # every saved float to 3 decimals
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, dict): return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [rnd(v) for v in x]
    return x
out = rnd(out); songs = out["songs"]
(OUT / "results.json").write_text(json.dumps(out, indent=1))

# ---- tables.md
L = ["# M8 spike 3: take scores against the humans (tables)", "",
     f"Songs pooled: {len(keys)} (left out, humans under 0.6: {', '.join(out['left_out'])}). F1@50 guitar Expert, "
     "the onset splice (see results.json); today = a_m05.", ""]
for meas in ("p50", "mean50"):
    pg = out["pooled"][meas]
    L += [f"## Pooled {meas} ({'against the primary' if meas == 'p50' else 'mean over every chart'})", "",
          "| pick rule | pooled | vs today | 95 % CI | worst song | songs down >0.01 / up >0.01 | windows >0.05 below best |", "|---|---|---|---|---|---|---|"]
    for p in PICKS:
        v = pg["vs_today_a_m05"].get(p)
        L.append(f"| {p} | {pg['mean'][p]:.3f} | " + ("—" if v is None else f"{v['diff']:+.3f} | [{v['ci'][0]:+.3f}, {v['ci'][1]:+.3f}] | {v['worst']:+.3f} | {v['down_gt_0.01']} / {v['up_gt_0.01']}") + ("| — | — | — " if v is None else "") + f" | {pg['loses_by_f1_0.05_total'][p]} |")
    L += [f"| best take per song | {pg['mean']['best_take_per_song']:.3f} | | | | | |",
          f"| today as built (part C) | {pg['mean']['recorded_today_m05']:.3f} | | | | | |", ""]
L += ["## Per song, p50 (against the primary)", "",
      "| song | set | charts | humans | today a_m05 | a_m0 | b_m0 | b_m02 | c_m0 | d_m0 | d_m02 | e_t50 | best take | oracle window | windows | shift err | built-vs-recorded |",
      "|" + "---|" * 17]
for k, s in songs.items():
    p = s["p50"]; bt = max(p[f"take{j}"] for j in range(4))
    L.append(f"| {k}{' (out)' if s['left_out'] else ''} | {s['set']} | {s['charts']} | {s['humans_f1_50'] if s['humans_f1_50'] is not None else '—'} | {p['a_m05']:.3f} | "
             + " | ".join(f"{p[x] - p['a_m05']:+.3f}" for x in ("a_m0", "b_m0", "b_m02", "c_m0", "d_m0", "d_m02", "e_t50"))
             + f" | {bt:.3f} | {p['oracle_window']:.3f} | {s['windows']} | {max(c['abs_err_sum'] for c in s['calibration'].values()):.3f} | "
             + f"{max(v['built_vs_recorded_max_abs'] for v in s['check'].values()):.3f} |")
L += ["", "## Per song, mean50 (every chart)", "", "| song | today a_m05 | a_m0 | b_m0 | b_m02 | c_m0 | d_m0 | d_m02 | e_t50 | best take |", "|" + "---|" * 10]
for k, s in songs.items():
    p = s["mean50"]; bt = max(p[f"take{j}"] for j in range(4))
    L.append(f"| {k}{' (out)' if s['left_out'] else ''} | {p['a_m05']:.3f} | " + " | ".join(f"{p[x] - p['a_m05']:+.3f}" for x in ("a_m0", "b_m0", "b_m02", "c_m0", "d_m0", "d_m02", "e_t50")) + f" | {bt:.3f} |")
L += ["", "## Stem evidence per song", "", "| song | b precision (median window) | b recall (median window) | silent share of take onsets |", "|---|---|---|---|"]
for k, s in songs.items():
    L.append(f"| {k} | {s['b_precision_median']} | {s['b_recall_median']} | {s['silent_share']} |")
L += ["", "## Does the score order two takes as the primary does?", "",
      "Pairs of takes in one window whose F1 against the primary differs by more than 0.05 (pooled songs, windows with human notes; ties in the score skipped). n = more onsets.", "",
      "| score | pairs | same order |", "|---|---|---|"]
for k, v in conc.items():
    L.append(f"| {k} | {v['pairs']} | {v['same_order_share']} |")
L += ["", "Median offset of the nearest stem peak from each kept-take onset (ms, within 100 ms): " +
      ", ".join(f"{k} {s['peak_offset_ms_median']}" for k, s in songs.items())]
txt = "\n".join(L) + "\n"
(OUT / "tables.md").write_text(txt); print(txt)
