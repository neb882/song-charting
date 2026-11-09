"""b_analyze.py: M8-02 part B's numbers. Reads B/arms/<label>.json (build_b.py: every built arm's F1@50 / F1@100 per
chart, picks, window scores), <shm>/m8/charts/<arm>/<label>.notes.chart (our arms' charts), each kept folder's
guitar stem (librosa onset strength, assemble.frame_levels) and the human charts (notes only, through score.py's
scan/tracks_by_key/onsets). Steps 4 and 5 use the takescore spike's onset-splice evaluator (eval/m8/takescore/
analyze.py: each chart's shift calibrated so the lone takes reproduce their built F1@50). L1 and D1 as fixed in
B/prereg.txt, leave one song out. Writes B/part_b_eval.json (labels only, 3 decimals); prints progress lines (labels).
Usage: SONGCHARTER_SCAN_CHART=<scan.cjs> python -I b_analyze.py <m8-02 folder>"""
import json, os, sys, shutil, tempfile
from pathlib import Path
import numpy as np
M = Path(sys.argv[1])
sys.path.insert(0, "<shm>/m8/code")
from eval.scorer import score as SC                                  # noqa: E402
from eval import stress as S                                         # noqa: E402
from songcharter.assemble import silent_onsets, frame_levels, LEVEL_FRAME_S   # noqa: E402
import librosa                                                       # noqa: E402
DEV = Path("$DEV"); G = DEV / "golden"
CH = Path("<shm>/m8/charts"); AN = Path("<shm>/m8/an"); AN.mkdir(parents=True, exist_ok=True)
REFS = ["all_the_small_things", "creep", "drunk_drivers", "kimochi_warui", "lucretia", "take_me_out"]
STRESS = ["break", "pm2", "sooth", "troop"]
SET20 = sorted(s["id"] for s in json.loads((DEV / "eval-set20/stress/songs.json").read_text()))
SONGS = {}
for s in REFS: SONGS[s] = ("refs", s, G / "work" / s)
for s in STRESS: SONGS[s] = ("stress", s, G / "stress-work" / s)
for i, s in enumerate(SET20, 1): SONGS[f"s{i:02d}"] = ("set20", s, G / "set20-work" / s)
REFDIR = {"refs": DEV / "eval/refs", "stress": DEV / "eval/stress", "set20": DEV / "eval-set20/stress"}
LEFT_OUT = ["s02", "s04", "s06", "s12"]   # humans agree under 0.6 on guitar F1@50 (the order)
TOL, SPAN_MARGIN = 0.05, 0.100
R3 = lambda x: None if x is None else round(float(x), 3)
ONLY = sys.argv[2:] or list(SONGS)
ALIGNED = json.loads((M / "B" / "aligned.json").read_text())   # aligned.py: score.py's alignment test per chart


def match(r, c, tol=TOL):
    pairs, j, n = [], 0, len(c)
    for i, t in enumerate(r):
        while j < n and c[j] < t - tol: j += 1
        if j < n and c[j] <= t + tol: pairs.append((i, j)); j += 1
    return pairs


def f1_vs(h, cand):
    lo, hi = h["span"][0] - SPAN_MARGIN, h["span"][1] + SPAN_MARGIN
    co = [t for t in cand if lo <= t <= hi]
    pr = match(h["t"], co); mj = {j for _, j in pr}
    nc = len(mj) + sum(1 for j, t in enumerate(co) if j not in mj and h["span"][0] <= t <= h["span"][1])
    m, nr = len(pr), len(h["t"])
    p = m / nc if nc else 0.0; r = m / nr if nr else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def win_f1(a, b):
    if not len(a) and not len(b): return 1.0
    return 2 * len(match(list(a), list(b))) / (len(a) + len(b))


def chart_onsets(path):
    tmp = Path(tempfile.mkdtemp(dir=str(AN)))
    shutil.copy(path, tmp / "notes.chart")
    sc = SC.scan(str(tmp)); shutil.rmtree(tmp)
    d, _ = SC.chart_delay_ms(sc)
    tr = SC.tracks_by_key(sc).get(("guitar", "expert")) or []
    ons = SC.onsets(tr, d, "guitar")
    return np.array([o["t"] * 1000.0 for o in ons]), [sorted(set(o["lanes"])) for o in ons]


def calibrate(h, takes_ms, target, coarse=None):   # the spike's
    ht = np.array(h["t"]) * 1000.0
    t0 = np.array(takes_ms[0]); diffs = []
    for x in t0:
        lo, hi = np.searchsorted(ht, x - 30000), np.searchsorted(ht, x + 30000)
        diffs.append(ht[lo:hi] - x)
    diffs = np.concatenate(diffs)
    hist, edges = np.histogram(diffs, bins=np.arange(-30000, 30001, 5))
    sm = np.convolve(hist, np.ones(21), "same")
    if coarse is None:
        coarse = edges[int(np.argmax(sm))] + 2.5
    grid = []
    for s in np.arange(coarse - 80, coarse + 80, 0.5):
        f = [f1_vs(h, [(x + s) / 1000.0 for x in t]) for t in takes_ms]
        grid.append((round(sum(abs(a - b) for a, b in zip(f, target)), 4), float(s), f))
    err = min(g[0] for g in grid)
    good = [g for g in grid if g[0] == err]
    _, s, f = good[len(good) // 2]
    return s, err


def stem(label, kept):
    p = AN / f"{label}.stem.npz"
    if not p.exists():
        wav = next((kept / "stems").glob("*/guitar.wav"))
        y, sr = librosa.load(str(wav), sr=22050, mono=True)
        env = librosa.onset.onset_strength(y=y, sr=22050, hop_length=512)
        pk = librosa.util.peak_pick(env, pre_max=3, post_max=3, pre_avg=3, post_avg=3, delta=0.0, wait=1)
        t_env = librosa.frames_to_time(np.arange(len(env)), sr=22050, hop_length=512)
        y44, sr44 = librosa.load(str(wav), sr=None, mono=False)
        np.savez(p, env=env, t_env=t_env, peaks=t_env[pk], peak_s=env[pk], levels=frame_levels(y44, sr44))
    return np.load(p)


def one_device(label, res, H, charts, lone_arms, win_arm, st):
    """The evaluator and the per-window rows for one device's four lone takes."""
    arms = res["arms"]
    real = lambda a: arms[arms[a]["same_as"]] if "same_as" in arms[a] else arms[a]
    lone = [chart_onsets(CH / a / f"{label}.notes.chart") for a in lone_arms]
    lone_ms = [x[0] for x in lone]
    shift, cal = {}, {}
    lags = {"primary": 0.0}
    for c in charts:
        co = None if c == "primary" else shift["primary"] - lag_of(label, c)
        tgt = [real(a)["scores"][c]["f1_50"] for a in lone_arms]
        s, err = calibrate(H[c], lone_ms, tgt, co)
        shift[c] = s; cal[c] = {"shift_ms": R3(s), "abs_err_sum": R3(err)}
    sp = shift["primary"]
    take_t = [(t + sp) / 1000.0 for t in lone_ms]
    wins = real(win_arm)["takes"]["windows"]
    bounds = [(w["start"], np.inf if w["end"] is None else w["end"]) for w in wins]

    def score(picks):
        cand = np.concatenate([take_t[k][(take_t[k] >= a) & (take_t[k] < b)] for (a, b), k in zip(bounds, picks)])
        return {c: f1_vs(H[c], sorted(cand + (shift[c] - sp) / 1000.0)) for c in charts}
    env, tenv, pk, pks, lv = st["env"], st["t_env"], st["peaks"], st["peak_s"], st["levels"]
    t0 = take_t[0]; j = np.clip(np.searchsorted(pk, t0), 1, len(pk) - 1)
    near = np.where(np.abs(pk[j] - t0) < np.abs(pk[j - 1] - t0), pk[j], pk[j - 1]) - t0
    poff = float(np.median(near[np.abs(near) < 0.1]))
    pkc = pk - poff
    W = []
    for i, (a, b) in enumerate(bounds):
        sel = (tenv >= a) & (tenv < b)
        med = float(np.median(env[sel])) if sel.any() else 0.0
        strong = pkc[(pkc >= a) & (pkc < b) & (pks > med)]
        dur = (min(b, take_t[0][-1] + 1.0) if np.isinf(b) else b) - a
        hum = {c: np.array([t - (shift[c] - sp) / 1000.0 for t in H[c]["t"]]) for c in charts}
        hum = {c: v[(v >= a) & (v < b)] for c, v in hum.items()}
        row = {"n": [], "b2_p": [], "b2_r": [], "b2": [], "silent": [], "chord": [], "open": [], "rep": [], "tgt": [],
               "extra": [], "extra_ev2": [], "f1h": []}
        on0 = take_t[0][(take_t[0] >= a) & (take_t[0] < b)]
        for k in range(4):
            sk = (take_t[k] >= a) & (take_t[k] < b)
            on = take_t[k][sk]; lanes = [lone[k][1][x] for x in np.nonzero(sk)[0]]
            n = len(on); m2 = len(match(list(on), list(strong)))
            row["n"].append(n)
            row["b2"].append(1.0 if not n and not len(strong) else 2 * m2 / (n + len(strong)))
            row["b2_p"].append(m2 / n if n else 0.0); row["b2_r"].append(m2 / len(strong) if len(strong) else 0.0)
            row["silent"].append(len(silent_onsets(list(on), lv, LEVEL_FRAME_S)) / n if n else 0.0)
            row["chord"].append(sum(len(x) > 1 for x in lanes) / n if n else 0.0)
            row["open"].append(sum(-1 in x for x in lanes) / n if n else 0.0)
            row["rep"].append(sum(1 for q in range(1, n) if len(lanes[q]) == 1 and lanes[q] == lanes[q - 1]) / n if n else 0.0)
            row["tgt"].append(float(np.mean([win_f1(hum[c], on) for c in charts])))
            row["f1h"].append(win_f1(hum["primary"], on))
            mj = {jj for _, jj in match(list(on0), list(on))}
            ex = [x for jj, x in enumerate(on) if jj not in mj]
            row["extra"].append(len(ex)); row["extra_ev2"].append(len(match(ex, list(strong))))
        row["a"] = list(wins[i]["scores"])
        row["strong"] = len(strong); row["dur"] = dur
        row["human"] = float(np.mean([len(hum[c]) for c in charts]))
        W.append(row)
    return {"score": score, "W": W, "cal": cal, "wins": wins, "peak_lag_ms": R3(1000 * poff)}


LAGS = {}


def lag_of(label, c):
    return LAGS[label][c]


def pick_by(W, key, margin, fn=None):
    out = []
    for r in W:
        s = fn(r) if fn else r[key]
        best = max(range(4), key=lambda k: (s[k], -k))
        out.append(best if s[best] > s[0] + margin else 0)
    return out


def pick_e(W, thr):
    out = []
    for r in W:
        ok = [k for k in range(1, 4) if r["n"][k] > r["n"][0] and r["extra"][k] and r["extra_ev2"][k] / r["extra"][k] >= thr]
        out.append(max(ok, key=lambda k: (r["n"][k], -k)) if ok else 0)
    return out


def feats(r, rho):
    med = float(np.median(r["n"])) or 1.0
    pred = rho * r["strong"]
    return np.array([[r["a"][k], r["b2_p"][k], r["b2_r"][k], r["n"][k] / med if med else 1.0, r["silent"][k],
                      r["chord"][k], r["open"][k], r["rep"][k], abs(np.log((r["n"][k] + 1) / (pred + 1)))] for k in range(4)])


def fit_l1(rows, rho, lam=1.0):
    X, y = [], []
    for r in rows:
        if not r["human"]: continue
        F = feats(r, rho)
        for i in range(4):
            for j in range(4):
                if i == j or abs(r["tgt"][i] - r["tgt"][j]) < 1e-12: continue
                X.append(F[i] - F[j]); y.append(1.0 if r["tgt"][i] > r["tgt"][j] else 0.0)
    X, y = np.array(X), np.array(y)
    sd = X.std(axis=0); sd[sd == 0] = 1.0
    Xs = X / sd
    w = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-Xs @ w))
        g = Xs.T @ (p - y) + lam * w
        Hm = (Xs * (p * (1 - p))[:, None]).T @ Xs + lam * np.eye(len(w))
        step = np.linalg.solve(Hm, g); w -= step
        if np.abs(step).max() < 1e-8: break
    return w / sd


def pick_l1(W, w, rho, p):
    out = []
    for r in W:
        F = feats(r, rho)
        pr = [1 / (1 + np.exp(-(F[k] - F[0]) @ w)) for k in range(4)]
        ok = [k for k in range(1, 4) if pr[k] > p]
        out.append(max(ok, key=lambda k: (pr[k], -k)) if ok else 0)
    return out


def rho_of(rows):
    s = sum(r["strong"] for r in rows)
    return sum(r["human"] for r in rows) / s if s else 1.0


def pick_d1(W, rho):
    out = []
    for r in W:
        pred = rho * r["strong"]
        d = [abs(r["n"][k] - pred) for k in range(4)]
        best = min(range(4), key=lambda k: (d[k], k))
        out.append(best if best and d[best] < 0.9 * d[0] else 0)
    return out


# ------------------------------------------------------------------ per song: extract
DATA = {}
for label in ONLY:
    st_, sid, kept = SONGS[label]
    res = json.loads((M / "B" / "arms" / f"{label}.json").read_text())
    song = next(s for s in S.built_songs(REFDIR[st_]) if s["id"] == sid)
    charts = [("primary", Path(song["folder"]))] + [(a["label"], Path(a["folder"])) for a in song.get("alts") or []
                                                   if S.scorable(Path(a["folder"]))]
    assert [c for c, _ in charts] == res["charts"]
    H, LAGS[label] = {}, {"primary": 0.0}
    prim_audio = None
    for lab, folder in charts:
        rsc = SC.scan(str(folder / "ref"))
        rdel, _ = SC.chart_delay_ms(rsc)
        rtr = SC.tracks_by_key(rsc)
        st0 = [min(n["ms"] for n in v) for v in rtr.values()]; en0 = [max(n["ms"] + (n.get("msLength") or 0) for n in v) for v in rtr.values()]
        H[lab] = {"span": ((min(st0) + rdel) / 1000.0, (max(en0) + rdel) / 1000.0),
                  "t": [o["t"] for o in SC.onsets(rtr.get(("guitar", "expert")) or [], rdel, "guitar")]}
        if lab == "primary":
            prim_audio = SC.decode(str(folder / "input.wav"))
        else:
            LAGS[label][lab] = SC.align(SC.decode(str(folder / "input.wav")), prim_audio, max_shift_s=30.0)["lag_ms"]
    stm = stem(label, kept)
    gpu = one_device(label, res, H, res["charts"], ["f0", "f1", "f2", "f3"], "m05", stm)
    cpu = one_device(label, res, H, res["charts"], ["cf0", "cf1", "cf2", "cf3"], "cpu_m05", stm)
    # c: q's score (q05's recorded window scores)
    for r, w in zip(gpu["W"], res["arms"]["q05"]["takes"]["windows"]):
        r["c"] = list(w["scores"])
    # the humans' own agreement: each alt against the primary (F1@50 on the calibrated clocks), mean
    sp = gpu["cal"]["primary"]["shift_ms"]
    agr = [f1_vs(H["primary"], sorted(np.array(H[c]["t"]) - (gpu["cal"][c]["shift_ms"] - sp) / 1000.0)) for c in res["charts"][1:]]
    DATA[label] = {"res": res, "gpu": gpu, "cpu": cpu, "charts": res["charts"], "set": st_,
                   "humans_f1_50": R3(np.mean(agr)) if agr else None}
    print(label, "extracted", flush=True)

# ------------------------------------------------------------------ picks and scores
OUT = {"songs": {}, "prereg": (M / "B" / "prereg.txt").read_text().splitlines()[0]}
for label, D in DATA.items():
    gW, cW = D["gpu"]["W"], D["cpu"]["W"]
    train = [r for l2, D2 in DATA.items() if l2 != label for r in D2["gpu"]["W"]]
    rho = rho_of(train)
    w = fit_l1(train, rho)
    arms = D["res"]["arms"]
    real = lambda a: arms[arms[a]["same_as"]] if "same_as" in arms[a] else arms[a]
    P = {}
    for m, ms in ((0.0, "0"), (0.02, "02"), (0.05, "05")):
        P[f"a_m{ms}"] = pick_by(gW, "a", m)
        P[f"b2_m{ms}"] = pick_by(gW, "b2", m)
        P[f"c_m{ms}"] = pick_by(gW, "c", m)
        P[f"d2_m{ms}"] = pick_by(gW, None, m, lambda r: [0.5 * x + 0.5 * y for x, y in zip(r["a"], r["b2"])])
    P["e2_t50"] = pick_e(gW, 0.5); P["e2_t70"] = pick_e(gW, 0.7)
    for p in (0.5, 0.6, 0.7):
        P[f"L1_p{int(p * 10):02d}"] = pick_l1(gW, w, rho, p)
    P["D1"] = pick_d1(gW, rho)
    P["oracle_window"] = [max(range(4), key=lambda k: (r["tgt"][k], -k)) for r in gW]
    for k in range(4): P[f"take{k}"] = [k] * len(gW)
    P["a_m05"] = list(arms["m05"]["picks"]); P["c_m05"] = list(arms["q05"]["picks"])
    sc = {p: D["gpu"]["score"](pk) for p, pk in P.items()}
    PC_ = {"a_m05": list(arms["cpu_m05"]["picks"]), "L1_p06": pick_l1(cW, w, rho, 0.6), "L1_p05": pick_l1(cW, w, rho, 0.5),
           "L1_p07": pick_l1(cW, w, rho, 0.7), "D1": pick_d1(cW, rho),
           "oracle_window": [max(range(4), key=lambda k: (r["tgt"][k], -k)) for r in cW]}
    for k in range(4): PC_[f"take{k}"] = [k] * len(cW)
    csc = {p: D["cpu"]["score"](pk) for p, pk in PC_.items()}
    ch = D["charts"]
    loses = {p: sum(1 for r, k in zip(gW, pk) if r["tgt"][k] < max(r["tgt"]) - 0.05) for p, pk in P.items()}
    chk = {a: R3(max(abs(sc[p][c] - real(a)["scores"][c]["f1_50"]) for c in ch)) for p, a in (("a_m05", "m05"), ("c_m05", "q05"))}
    chk["cpu_m05"] = R3(max(abs(csc["a_m05"][c] - arms["cpu_m05"]["scores"][c]["f1_50"]) for c in ch))
    OUT["songs"][label] = {
        "set": D["set"], "charts": len(ch), "windows": len(gW), "humans_f1_50": D["humans_f1_50"],
        "left_out": label in LEFT_OUT, "calibration_gpu": D["gpu"]["cal"], "calibration_cpu": D["cpu"]["cal"],
        "evaluator_vs_built_max_abs": chk, "rho": R3(rho), "l1_w": [R3(x) for x in w],
        "p50": {p: R3(v["primary"]) for p, v in sc.items()}, "mean50": {p: R3(np.mean(list(v.values()))) for p, v in sc.items()},
        "mean50_aligned": {p: R3(np.mean([x for c, x in v.items() if ALIGNED[label][c]["ok"]])) for p, v in sc.items()},
        "cpu_mean50_aligned": {p: R3(np.mean([x for c, x in v.items() if ALIGNED[label][c]["ok"]])) for p, v in csc.items()},
        "cpu_p50": {p: R3(v["primary"]) for p, v in csc.items()}, "cpu_mean50": {p: R3(np.mean(list(v.values()))) for p, v in csc.items()},
        "switched": {p: sum(1 for k in pk if k) for p, pk in P.items()},
        "cpu_switched": {p: sum(1 for k in pk if k) for p, pk in PC_.items()},
        "loses_by_0.05": loses, "picks": P}
    print(label, "scored", flush=True)


def rnd(x):
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, dict): return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [rnd(v) for v in x]
    return x
(M / "B" / "part_b_eval.json").write_text(json.dumps(rnd(OUT), indent=1))
