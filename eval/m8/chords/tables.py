"""tables.py: the tables and the bar's verdicts from measure.py's results.json (prereg.txt). Labels and numbers only.
Usage: python -I tables.py <results.json> <out tables.txt> <out summary.json>"""
import json, sys
import numpy as np
R = json.load(open(sys.argv[1]))["songs"]
LABELS = list(R)
F1_LOW = ("s02", "s04", "s06", "s12")
D19 = [l for l in LABELS if l not in F1_LOW]
VARS = [f"K{K}_{r}" for K in (2, 3, 4) for r in ("high", "low", "mode")]
PRIMARY = "K2_high"
out = []


def p(*a):
    out.append(" ".join(str(x) for x in a))


def boot(diffs, n=10000, seed=7):   # m2lib.boot
    d = np.array([x for x in diffs if x is not None], dtype=float)
    if len(d) == 0:
        return None
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return {"mean": round(float(d.mean()), 3), "lo": round(float(np.percentile(m, 2.5)), 3),
            "hi": round(float(np.percentile(m, 97.5)), 3), "n": int(len(d))}


def f3(x):
    return "  -  " if x is None else f"{x:.3f}"


def sel(label, arm, mode):
    ch = R[label]["arms"][arm]["charts"]
    if mode == "primary":
        return [ch["primary"]] if "primary" in ch else []
    return [c for c in ch.values() if c["well"]]


def avg(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def song_vals(label, arm, mode, var):
    cs = sel(label, arm, mode)
    if not cs:
        return None
    g = lambda f: avg([f(c) for c in cs])  # noqa: E731
    v = (lambda c: c["base"]) if var == "base" else (lambda c: c["variants"][var])
    return {"h_share": g(lambda c: c["human"]["chord_share"]), "h_cpo": g(lambda c: c["human"]["cpo"]),
            "share": g(lambda c: v(c)["chord_share"]), "exact50": g(lambda c: v(c)["exact50"]),
            "cpo": g(lambda c: v(c)["cpo"]), "prec": g(lambda c: v(c)["chord_prec"]),
            "f1": [v(c)["f1_50"] for c in cs], "exact100": g(lambda c: v(c)["exact100"])}


def bar(songs, arm, mode, var):
    rows = []
    for l in songs:
        b, v = song_vals(l, arm, mode, "base"), song_vals(l, arm, mode, var)
        if b is None:
            continue
        rows.append((l, b, v))
    ga = [abs(v["share"] - b["h_share"]) - abs(b["share"] - b["h_share"]) for _, b, v in rows]
    down, up = sum(x < -1e-9 for x in ga), sum(x > 1e-9 for x in ga)
    A = boot(ga)
    Bx = boot([(v["exact50"] - b["exact50"]) if None not in (v["exact50"], b["exact50"]) else None for _, b, v in rows])
    Cc = boot([abs(v["cpo"] - b["h_cpo"]) - abs(b["cpo"] - b["h_cpo"]) for _, b, v in rows])
    f1_same = all(x == y for _, b, v in rows for x, y in zip(b["f1"], v["f1"]))
    E = boot([(v["prec"] - b["prec"]) if None not in (v["prec"], b["prec"]) else None for _, b, v in rows])
    ok = {"a": down > up and A["hi"] < 0, "b": Bx["lo"] > -0.002, "c": Cc["hi"] < 0.002, "d": f1_same,
          "e": E is not None and E["mean"] > 0 and E["lo"] > 0}
    pooled = {"ours_base": round(avg([b["share"] for _, b, _ in rows]), 3),
              "ours_var": round(avg([v["share"] for _, _, v in rows]), 3),
              "human": round(avg([b["h_share"] for _, b, _ in rows]), 3),
              "within05_base": sum(abs(b["share"] - b["h_share"]) <= 0.05 for _, b, _ in rows),
              "within05_var": sum(abs(v["share"] - b["h_share"]) <= 0.05 for _, b, v in rows),
              "exact50_base": round(avg([b["exact50"] for _, b, _ in rows]), 3),
              "exact100_base": round(avg([b["exact100"] for _, b, _ in rows]), 3),
              "exact100_var": round(avg([v["exact100"] for _, _, v in rows]), 3),
              "cpo_base": round(avg([b["cpo"] for _, b, _ in rows]), 3),
              "cpo_var": round(avg([v["cpo"] for _, _, v in rows]), 3),
              "cpo_human": round(avg([b["h_cpo"] for _, b, _ in rows]), 3)}
    return {"n_songs": len(rows), "a": {"down": down, "up": up, "gap_change": A}, "b": Bx, "c": Cc, "d": f1_same,
            "e": E, "ok": ok, "pass": all(ok.values()), "pooled": pooled}


summary = {}
# ---------------------------------------------------------------- step 1
p("== Step 1: the splice's time base (m05 chord onsets) ==")
p("label      n_chords  within5ms  share5  within50  snap16/n  res_med_ms  res_p90_ms")
tot = [0, 0, 0, 0]
for l in LABELS:
    s = R[l]["arms"]["m05"]["step1"]
    tot = [tot[0] + s["n"], tot[1] + s["match5"], tot[2] + s["match50"], tot[3] + s["snap16"]]
    r = s.get("res_ms") or {}
    p(f"{l:20s} {s['n']:5d} {s['match5']:5d} {s['match5'] / max(s['n'], 1):.3f} {s['match50']:5d} "
      f"{s['snap16'] / max(s['n'], 1):.3f} {f3(r.get('median_signed'))} {f3(r.get('abs_p90'))}")
p(f"POOLED {tot[0]:,} chords: within 5 ms {tot[1] / tot[0]:.3f}; within 50 ms {tot[2] / tot[0]:.3f}; snap16 {tot[3] / tot[0]:.3f}")
summary["step1"] = {"n": tot[0], "share5": round(tot[1] / tot[0], 3), "share50": round(tot[2] / tot[0], 3),
                    "snap16": round(tot[3] / tot[0], 3)}


# ---------------------------------------------------------------- step 2: the table
def ktable(arm, songs, mode="primary"):
    pooled = {"chord": np.zeros((5, 4)), "single": np.zeros((5, 4))}
    per = {}
    for l in songs:
        cs = sel(l, arm, mode)
        if not cs:
            continue
        t = {k: np.sum([np.array(c["table"][k]) for c in cs], axis=0) for k in ("chord", "single")}
        per[l] = t
        for k in t:
            pooled[k] += t[k]
    return pooled, per


for arm in ("m05", "one"):
    for songs, nm in ((D19, "19 songs"), (LABELS, "all 23")):
        pooled, per = ktable(arm, songs)
        p(f"\n== Step 2 ({arm}, primaries, {nm}): our onsets by k = takes of 4 writing a chord within 50 ms ==")
        p("kind    k   n_ours  human_chord_within50  rate   matched  matched_human_chord  rate")
        for kind in ("chord", "single"):
            for k in range(5):
                n, hc, mt, mc = pooled[kind][k]
                p(f"{kind:7s} {k}  {int(n):6,d}  {int(hc):6,d}  {f3(hc / n if n else None)}  {int(mt):6,d}  {int(mc):6,d}  "
                  f"{f3(mc / mt if mt else None)}")
        summary.setdefault("table", {}).setdefault(arm, {})[nm] = {
            k: [[int(x) for x in row] for row in pooled[k]] for k in pooled}
        if nm == "all 23":
            p(f"per song ({arm}, primary): chords by k [n / human chord rate within 50 ms]; singles with k>=2 [n / rate]")
            for l, t in per.items():
                cells = " ".join(f"{int(t['chord'][k][0])}/{f3(t['chord'][k][1] / t['chord'][k][0]) if t['chord'][k][0] else '  -  '}"
                                 for k in range(5))
                s2 = t["single"][2:].sum(axis=0)
                hs = R[l]["arms"][arm]["charts"]["primary"]["human"]["chord_share"]
                os_ = R[l]["arms"][arm]["charts"]["primary"]["base"]["chord_share"]
                p(f"  {l:20s} ours {os_:.3f} human {hs:.3f} | {cells} | singles k>=2 {int(s2[0])}/{f3(s2[1] / s2[0]) if s2[0] else '  -  '}")

# ---------------------------------------------------------------- step 3/4: the variants against the bar
for arm in ("m05", "one"):
    summary.setdefault("bar", {})[arm] = {}
    for songs, nm in ((D19, "19"), (LABELS, "23")):
        for mode in ("primary", "well"):
            key = f"{nm}_{mode}"
            p(f"\n== Bar ({arm}, {nm} songs, {mode} charts) ==")
            p("variant   n  a:down/up gap_change[mean lo hi]  b:exact50[mean lo]  c:cpo_gap[mean hi]  d:F1same  "
              "e:prec[mean lo n]  share base->var (human)  within0.05 base->var  PASS")
            for var in [PRIMARY] + [v for v in VARS if v != PRIMARY]:
                b = bar(songs, arm, mode, var)
                summary["bar"][arm].setdefault(key, {})[var] = b
                A, Bx, Cc, E, P = b["a"]["gap_change"], b["b"], b["c"], b["e"], b["pooled"]
                fl = "".join(k.upper() if v else k for k, v in b["ok"].items())
                p(f"{var:8s} {b['n_songs']:2d}  {b['a']['down']:2d}/{b['a']['up']:2d} [{A['mean']:+.3f} {A['lo']:+.3f} {A['hi']:+.3f}]  "
                  f"[{Bx['mean']:+.3f} {Bx['lo']:+.3f}]  [{Cc['mean']:+.3f} {Cc['hi']:+.3f}]  {b['d']}  "
                  f"[{E['mean']:+.3f} {E['lo']:+.3f} {E['n']}]  {P['ours_base']:.3f}->{P['ours_var']:.3f} ({P['human']:.3f})  "
                  f"{P['within05_base']}->{P['within05_var']}  {'PASS' if b['pass'] else 'fail'} ({fl})")
            p(f"  base pooled: exact50 {b['pooled']['exact50_base']:.3f}, exact100 {b['pooled']['exact100_base']:.3f}, "
              f"cpo ours {b['pooled']['cpo_base']:.3f} human {b['pooled']['cpo_human']:.3f}")

# per-song for the primary variant (m05, primaries)
p(f"\n== Per song, m05, primaries, {PRIMARY}: chord share base -> var (human); exact50 base -> var; precision base -> var; demoted ==")
for l in LABELS:
    c = R[l]["arms"]["m05"]["charts"]["primary"]
    b, v = c["base"], c["variants"][PRIMARY]
    p(f"  {l:20s} {b['chord_share']:.3f} -> {v['chord_share']:.3f} ({c['human']['chord_share']:.3f})  "
      f"{f3(b['exact50'])} -> {f3(v['exact50'])}  {f3(b['chord_prec'])} -> {f3(v['chord_prec'])}  {v['demoted']}")
open(sys.argv[2], "w").write("\n".join(out) + "\n")
json.dump(summary, open(sys.argv[3], "w"), indent=1)
print("\n".join(out))
