"""analyze.py: M8-11 steps 3-4. Reads out/raw.json and out/pipe/*.json; per arm and stage (raw, pipe) the mean and
range over its 4 takes of every measure (fast windows, other windows, song); arm minus base by an exact permutation
test over the 70 ways to split 8 takes 4/4 (two-sided, on the difference of means); the smallest detectable
difference from the within-arm spread; per 30-s window the same, for the bar's "no window down by more than 0.02";
and a timing-bias check (the F1@50 shift that maximises each take's score, -100..+100 ms in 5-ms steps). Writes
out/analysis.json and prints the report's tables (markdown)."""
import itertools, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib as L
from lib import S

OUT = L.W811 / "out"
raw = json.loads((OUT / "raw.json").read_text())
STAGES = {"raw": {k: v for k, v in raw["takes"].items()}, "pipe": {}}
for arm in L.ARMS:
    for seed in L.SEEDS:
        p = OUT / "pipe" / f"{arm}_{seed}.json"
        if p.exists():
            STAGES["pipe"][f"{arm}/{seed}"] = json.loads(p.read_text())
MEAS = [("fast", "recall"), ("fast", "f1"), ("fast", "ratio"), ("fast", "peak_c"), ("fast", "chord_c"),
        ("other", "recall"), ("other", "f1"), ("other", "ratio"), ("song", "recall"), ("song", "f1"), ("song", "f1_50"),
        ("song", "ratio"), ("song", "peak1s_c"), ("song", "chord_c")]


def vals(stage, arm, part, m):
    return [STAGES[stage][f"{arm}/{s}"][part][m] for s in L.SEEDS if f"{arm}/{s}" in STAGES[stage]]


def perm(a, b):
    """Exact two-sided permutation p of mean(a) - mean(b) over every split of the pooled takes."""
    a, b = list(a), list(b); pool = a + b; n = len(a); obs = np.mean(a) - np.mean(b); c = t = 0
    for idx in itertools.combinations(range(len(pool)), n):
        x = [pool[i] for i in idx]; y = [pool[i] for i in range(len(pool)) if i not in idx]
        t += 1; c += abs(np.mean(x) - np.mean(y)) >= abs(obs) - 1e-12
    return c / t, t


def mdd(sd, n=4):
    """Smallest true difference of means a 4-vs-4 two-sided test at 5 % finds half the time (t 6 df: 2.447) and
    80 % of the time (+0.906), from the pooled within-arm SD."""
    se = sd * np.sqrt(2 / n)
    return 2.447 * se, (2.447 + 0.906) * se


res = {"arms": {}, "vs_base": {}, "windows": {}, "bias": {}, "noise": {}}
for stage in STAGES:
    if not STAGES[stage]:
        continue
    A = res["arms"][stage] = {}
    for arm in L.ARMS:
        A[arm] = {f"{p}.{m}": {"mean": float(np.mean(v)), "min": float(min(v)), "max": float(max(v)), "n": len(v),
                               "sd": float(np.std(v, ddof=1)) if len(v) > 1 else None}
                  for p, m in MEAS if (v := vals(stage, arm, p, m))}
    V = res["vs_base"][stage] = {}
    N = res["noise"][stage] = {}
    for p, m in MEAS:
        sds = [A[a][f"{p}.{m}"]["sd"] for a in L.ARMS if A[a].get(f"{p}.{m}", {}).get("sd") is not None]
        sd = float(np.sqrt(np.mean(np.square(sds)))) if sds else None
        N[f"{p}.{m}"] = {"pooled_sd": sd, "mdd50": mdd(sd)[0] if sd else None, "mdd80": mdd(sd)[1] if sd else None}
    for arm in L.ARMS[1:]:
        V[arm] = {}
        for p, m in MEAS:
            a, b = vals(stage, arm, p, m), vals(stage, "base", p, m)
            if len(a) >= 2 and len(b) >= 2:
                pv, nsplit = perm(a, b)
                V[arm][f"{p}.{m}"] = {"diff": float(np.mean(a) - np.mean(b)), "p": pv, "splits": nsplit}
    # per window F1@100
    takes = STAGES[stage]
    k0 = next(iter(takes))
    nw = len(takes[k0]["windows"])
    Wd = res["windows"][stage] = {"start": [w["start"] for w in takes[k0]["windows"]],
                                   "fast": [w["fast"] for w in takes[k0]["windows"]],
                                   "n_h": [w["n_h"] for w in takes[k0]["windows"]], "arms": {}}
    F = {arm: np.array([[takes[f"{arm}/{s}"]["windows"][i]["f1"] or 0.0 for i in range(nw)] for s in L.SEEDS
                        if f"{arm}/{s}" in takes]) for arm in L.ARMS}
    for arm in L.ARMS:
        Wd["arms"][arm] = {"mean": F[arm].mean(0).tolist(), "sd": F[arm].std(0, ddof=1).tolist() if len(F[arm]) > 1 else None}
    wsd = np.sqrt(np.mean([F[a].std(0, ddof=1) ** 2 for a in L.ARMS if len(F[a]) > 1], axis=0))
    Wd["pooled_sd"] = wsd.tolist(); Wd["mdd50"] = (2.447 * wsd * np.sqrt(2 / 4)).tolist()
    for arm in L.ARMS[1:]:
        if len(F[arm]) < 2:
            continue
        d = F[arm].mean(0) - F["base"].mean(0)
        ps = [perm(F[arm][:, i], F["base"][:, i])[0] for i in range(nw)]
        Wd["arms"][arm]["diff"] = d.tolist(); Wd["arms"][arm]["p"] = ps
        Wd["arms"][arm]["n_down_002"] = int((d < -0.02).sum())
        Wd["arms"][arm]["n_down_002_p05"] = int(((d < -0.02) & (np.array(ps) < 0.05)).sum())
        Wd["arms"][arm]["worst"] = float(d.min())

# timing bias: best F1@50 shift per take (raw: lag 0; pipe: the output's audio lag)
(k, prim), = [c for c in L.charts() if c[0] == "primary"]
ro, span = L.human(prim)
rt = np.array([o["t"] for o in ro])
for stage in STAGES:
    B = res["bias"][stage] = {}
    for key, r in STAGES[stage].items():
        arm, seed = key.split("/")
        folder = (L.TAKES / arm / f"seed_{seed}") if stage == "raw" else (L.W811 / "pipe" / f"{arm}_{seed}")
        lag = 0.0 if stage == "raw" else r["pipe"]["lag_ms"]
        co, _ = L.cand(folder, lag, span)
        ct0 = np.array([o["t"] for o in co])
        best = {}
        for sh in range(-100, 101, 5):
            ct = ct0 + sh / 1000.0; p = S.match(rt, ct, 0.05)
            best[sh] = S.prf(len(p), len(rt), S.n_cand_eff(p, ct, span))["f1"]
        bs = max(best, key=best.get)
        ct = ct0 + bs / 1000.0
        sc = L.score(ro, [dict(o, t=t) for o, t in zip(co, ct)], span)
        B[key] = {"best_shift_ms": bs, "f1_50_at_0": best[0], "f1_50_best": best[bs],
                  "fast_recall_shifted": sc["fast"]["recall"], "fast_f1_shifted": sc["fast"]["f1"],
                  "song_f1_shifted": sc["song"]["f1"]}
(OUT / "analysis.json").write_text(json.dumps(res, indent=1))

# ---- tables
f3 = lambda x: "-" if x is None else f"{x:.3f}"
hum = STAGES["raw"][k0 if False else next(iter(STAGES["raw"]))]
print("\nHumans (primary): fast windows %d, notes %d; peak (mean over fast windows) %.1f; song 1-s peak %d; chord share fast %.3f, song %.3f"
      % (hum["fast"]["windows"], hum["fast"]["n_h"], hum["fast"]["peak_h"], hum["song"]["peak1s_h"], hum["fast"]["chord_h"],
         hum["song"]["chord_h"]))
print("other windows %d (%d notes); song notes %d" % (hum["other"]["windows"], hum["other"]["n_h"], hum["song"]["n_h"]))
for stage in res["arms"]:
    A = res["arms"][stage]
    print(f"\n**{stage}**: mean [min, max] over the arm's takes (n per arm: {A['base']['fast.f1']['n']})\n")
    print("| measure | " + " | ".join(L.ARMS) + " |")
    print("|---|" + "---|" * len(L.ARMS))
    for p, m in MEAS:
        key = f"{p}.{m}"
        print(f"| {key} | " + " | ".join(f"{A[a][key]['mean']:.3f} [{A[a][key]['min']:.3f}, {A[a][key]['max']:.3f}]"
                                       for a in L.ARMS) + " |")
    print(f"\n{stage}, arm minus base (exact permutation p, {list(res['vs_base'][stage]['hot'].values())[0]['splits']} splits); "
          "pooled within-arm SD; smallest detectable difference (50 % / 80 % power)\n")
    print("| measure | hot | dense5 | dense6 | pooled SD | MDD 50 % / 80 % |")
    print("|---|---|---|---|---|---|")
    for p, m in MEAS:
        key = f"{p}.{m}"; n = res["noise"][stage][key]
        print(f"| {key} | " + " | ".join(f"{res['vs_base'][stage][a][key]['diff']:+.3f} (p {res['vs_base'][stage][a][key]['p']:.2f})"
                                       for a in L.ARMS[1:]) + f" | {f3(n['pooled_sd'])} | {f3(n['mdd50'])} / {f3(n['mdd80'])} |")
    Wd = res["windows"][stage]
    print(f"\n{stage}, per 30-s window F1@100: base mean, arm minus base, pooled SD, MDD50\n")
    print("| window start s | fast | human notes | base | hot | dense5 | dense6 | pooled SD | MDD50 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for i, st in enumerate(Wd["start"]):
        print(f"| {st:.0f} | {'yes' if Wd['fast'][i] else ''} | {Wd['n_h'][i]} | {Wd['arms']['base']['mean'][i]:.3f} | " +
              " | ".join(f"{Wd['arms'][a]['diff'][i]:+.3f}" for a in L.ARMS[1:]) +
              f" | {Wd['pooled_sd'][i]:.3f} | {Wd['mdd50'][i]:.3f} |")
    print("\n" + "; ".join(f"{a}: windows down > 0.02: {Wd['arms'][a]['n_down_002']} (of them p < 0.05: "
                           f"{Wd['arms'][a]['n_down_002_p05']}), worst {Wd['arms'][a]['worst']:+.3f}" for a in L.ARMS[1:]))
    print(f"median window MDD50 {np.median(Wd['mdd50']):.3f}, min {min(Wd['mdd50']):.3f}")
print("\n**Cost** (summary.json): tokens, generation s, wall s: mean [min, max]\n")
for arm in L.ARMS:
    sm = [STAGES["raw"][f"{arm}/{s}"]["summary"] for s in L.SEEDS]
    q = lambda k: f"{np.mean([x[k] for x in sm]):.0f} [{min(x[k] for x in sm):.0f}, {max(x[k] for x in sm):.0f}]"
    print(f"- {arm}: tokens {q('tokens')}; generation s {q('gen_s')}; wall s {q('wall_s')}; transcriber "
          f"{sorted(set(x['transcriber'] for x in sm))}; T {sm[0]['T']}, speed {sm[0]['speed']}")
print("\n**Timing bias** (best F1@50 shift, ms; F1@50 at 0 -> at best; fast recall@100 shifted)\n")
for stage in res["bias"]:
    for arm in L.ARMS:
        b = [res["bias"][stage][f"{arm}/{s}"] for s in L.SEEDS if f"{arm}/{s}" in res["bias"][stage]]
        if b:
            print(f"- {stage} {arm}: shifts {[x['best_shift_ms'] for x in b]}; F1@50 {np.mean([x['f1_50_at_0'] for x in b]):.3f} -> "
                  f"{np.mean([x['f1_50_best'] for x in b]):.3f}; fast recall@100 shifted {np.mean([x['fast_recall_shifted'] for x in b]):.3f}, "
                  f"fast F1@100 shifted {np.mean([x['fast_f1_shifted'] for x in b]):.3f}")
