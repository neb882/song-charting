"""c_analyze.py: M8-02 part C's numbers, C-a to C-e (Expert guitar). Reads part B's kept arms (GPU m05, CPU m05, CPU
one), part C's variant builds (V1 hopo source + floor cap 300 ms, V2 natural + 400 ms, V3 forced + 500 ms), the human
charts (notes, states and sustains via scan-chart; never text or events), align.json and the kept guitar stems (C-e's
stem test). Writes <shm>/m8/m2/c_raw.json (per song, arm and chart; labels only) and prints one line per song."""
import glob, json, os, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m2lib as L
from m2lib import S, pairs, f1, state, mean, r3, fast_runs

ARMS = ("m05", "cpu_m05", "cpu_one")
VARS = ("base", "V1", "V2", "V3")
CAP = {"base": None, "V1": 300.0, "V2": 400.0, "V3": 500.0}
GAPS, PCTS = (150, 200, 250), (25, 50)
TOL = 0.100


def floor_ms(beat_ms, v):
    c = CAP[v]
    return max(200.0, 0.75 * beat_ms if c is None else min(0.75 * beat_ms, c))


def bpm_at(sc, ms):
    tem = sc.get("tempos") or []
    b = tem[0]["beatsPerMinute"] if tem else 120.0
    for t in tem:
        if t["msTime"] <= ms: b = t["beatsPerMinute"]
        else: break
    return b


def held(o):
    return o["len_ticks"] > 0


def agree(ro, sts, p):
    return sum(1 for i, j in p if state(ro[i]) == sts[j]) / len(p) if p else None


def is_open(o):
    return -1 in o["lanes"]


def repeats(co):
    return [i for i in range(1, len(co)) if len(co[i]["lanes"]) == 1 and len(co[i - 1]["lanes"]) == 1
            and co[i]["lanes"] == co[i - 1]["lanes"]]


def longest_open(co):
    run = best = 0
    for o in co:
        run = run + 1 if is_open(o) else 0; best = max(best, run)
    return best


def tapstates(co, sts, rule):
    if rule == "T0": return list(sts)
    if rule == "T1": return [("hopo" if s == "tap" else s) for s in sts]
    fr = fast_runs([o["t"] for o in co]) >= 0
    return [("hopo" if (s == "tap" and not fr[k]) else s) for k, s in enumerate(sts)]


def open_rule(co, rule):
    """o0 today; o1 every open to green; o2 every open to the lane of the nearest fretted onset before it (its lowest
    lane), else after it; o3 an open kept only in a run of 3 or more consecutive open onsets, the others as o2."""
    if rule == "o0": return co
    op = [is_open(o) for o in co]
    keep = [False] * len(co)
    if rule == "o3":
        i = 0
        while i < len(co):
            j = i
            while j < len(co) and op[j]: j += 1
            if j - i >= 3:
                for k in range(i, j): keep[k] = True
            i = max(j, i + 1)
    out, last = [], None
    nxt = [None] * len(co); n_ = None
    for k in range(len(co) - 1, -1, -1):
        nxt[k] = n_
        if not op[k]: n_ = min(co[k]["lanes"])
    for k, o in enumerate(co):
        if op[k] and not keep[k]:
            if rule == "o1": lanes = sorted({0 if l == -1 else l for l in o["lanes"]})
            else:
                tgt = last if last is not None else (nxt[k] if nxt[k] is not None else 0)
                lanes = sorted({tgt if l == -1 else l for l in o["lanes"]})
            out.append(dict(o, lanes=lanes))
        else:
            out.append(o)
        if not op[k]: last = min(o["lanes"])
    return out


def lanes_m(ro, co, span):
    m = S.track_metrics(ro, co, "guitar", span, False, False)
    return m["exact_lane_agreement"]["value"], m["lane_direction_agreement"]["value"]


def near(ts, t, tol):
    if not len(ts): return False
    k = np.searchsorted(ts, t)
    return any(0 <= q < len(ts) and abs(ts[q] - t) <= tol + 1e-9 for q in (k - 1, k))


def stem_env(work):
    import librosa
    c = sorted(glob.glob(os.path.join(work, "stems", "*", "guitar.wav")), key=os.path.getmtime)
    if not c: return None
    y, sr = librosa.load(c[-1], sr=22050, mono=True)
    return librosa.onset.onset_strength(y=y, sr=sr, hop_length=512), sr / 512.0


def env_at(env, fps, t):
    a, b = int(round(t * fps)), int(round((t + 0.06) * fps))
    a, b = max(0, min(len(env) - 1, a)), max(0, min(len(env) - 1, b))
    return float(env[a:b + 1].max())


def chart_row(label, arm, k, octave, base_sc):
    ro, span = L.human(label, k)
    if not ro: return {}
    cos = {v: L.ours(L.arm_dir(arm, label, None if v == "base" else v), label, k, span) for v in VARS}
    co = cos["base"]
    bt = [o["t"] for o in co]
    mism = sum(0 if (len(cos[v]) == len(co) and np.allclose([o["t"] for o in cos[v]], bt, atol=1e-3)
                     and all(a["lanes"] == b["lanes"] for a, b in zip(cos[v], co))) else 1 for v in VARS)
    R = {"n_human": len(ro), "n_ours": len(co), "variant_onset_mismatch": mism}
    if mism: return R
    p = pairs(ro, co, TOL)
    sts = {v: [state(o) for o in cos[v]] for v in VARS}
    fr = fast_runs(bt) >= 0
    # C-a
    R["state"] = {v: agree(ro, sts[v], p) for v in ("base", "V1", "V2")}
    R["state"]["R1"] = R["state"]["V1"] if (octave or 1) != 1 else R["state"]["base"]
    fs = [(sb == "strum" and sn == "hopo") for sb, sn in zip(sts["V1"], sts["V2"])]   # the engine's forced strums
    r2 = [("hopo" if (fs[j] and sts["base"][j] == "strum" and fr[j]) else s) for j, s in enumerate(sts["base"])]
    r2a = [("hopo" if (fs[j] and sts["base"][j] == "strum") else s) for j, s in enumerate(sts["base"])]
    R["state"]["R2"], R["state"]["R2_all"] = agree(ro, r2, p), agree(ro, r2a, p)
    R["r2_changed"] = sum(1 for a, b in zip(r2, sts["base"]) if a != b)
    cls = {}
    for i, j in p:
        a1, a2 = sts["V1"][j], sts["V2"][j]
        kk = "tap" if "tap" in (a1, a2) else "forced_strum" if (a1, a2) == ("strum", "hopo") else \
            "forced_hopo" if (a1, a2) == ("hopo", "strum") else "unforced"
        d = cls.setdefault(kk, {"n": 0, "human_strum": 0, "human_hopo": 0, "human_tap": 0})
        d["n"] += 1; d["human_" + state(ro[i])] += 1
    R["by_engine_flag"] = cls
    R["hopo_share"] = {v: sum(1 for s in sts[v] if s == "hopo") / len(co) for v in ("base", "V1", "V2")}
    R["hopo_share_human"] = sum(1 for o in ro if state(o) == "hopo") / len(ro)
    # C-b
    pm, pi = {j: i for i, j in p}, dict(p)
    R["taps"] = {}
    for v in ("base", "V1", "V2"):
        ot = [j for j in range(len(co)) if sts[v][j] == "tap"]
        R["taps"][v] = {"n": len(ot), "share": len(ot) / len(co),
                        "precision": (sum(1 for j in ot if j in pm and state(ro[pm[j]]) == "tap") / len(ot)) if ot else None}
    ht = [i for i in range(len(ro)) if state(ro[i]) == "tap"]
    R["taps"]["human_n"], R["taps"]["human_share"] = len(ht), len(ht) / len(ro)
    R["taps"]["recall"] = (sum(1 for i in ht if i in pi and sts["base"][pi[i]] == "tap") / len(ht)) if ht else None
    for T in ("T0", "T1", "T2"):
        R["state"][T] = agree(ro, tapstates(co, sts["base"], T), p)
    t2 = tapstates(co, sts["base"], "T2")
    ot2 = [j for j in range(len(co)) if t2[j] == "tap"]
    R["taps"]["T2_precision"] = (sum(1 for j in ot2 if j in pm and state(ro[pm[j]]) == "tap") / len(ot2)) if ot2 else None
    # C-c
    R["sus_share"] = {v: sum(1 for o in cos[v] if held(o)) / len(co) for v in VARS}
    R["sus_agree"] = {v: (sum(1 for i, j in p if held(ro[i]) == held(cos[v][j])) / len(p)) if p else None for v in VARS}
    R["sus_share_human"] = sum(1 for o in ro if held(o)) / len(ro)
    hs = [o for o in ro if held(o)]
    a = L.alignment()[label][k]
    cshift = S.chart_delay_ms(base_sc)[0] - a["lag_ms"]
    drop = {v: 0 for v in VARS}
    for o in hs:
        ob = bpm_at(base_sc, o["t"] * 1000 - cshift)
        for v in VARS:
            drop[v] += o["len_ms"] < floor_ms(60000.0 / ob, v) - 1e-6
    R["human_sus_dropped"] = {v: (drop[v] / len(hs)) if hs else None for v in VARS}
    # C-d
    rt_open = np.array([o["t"] for o in ro if is_open(o)])
    ours_open = [o for o in co if is_open(o)]
    ct_open = np.array([o["t"] for o in ours_open])
    R["opens"] = {"n_ours": len(ours_open), "share_ours": len(ours_open) / len(co), "run_ours": longest_open(co),
                  "n_human": int(len(rt_open)), "share_human": len(rt_open) / len(ro), "run_human": longest_open(ro),
                  "precision": (sum(near(rt_open, o["t"], 0.05) for o in ours_open) / len(ours_open)) if ours_open else None,
                  "recall": (sum(near(ct_open, t, 0.05) for t in rt_open) / len(rt_open)) if len(rt_open) else None}
    R["lanes"] = {}
    for rule in ("o0", "o1", "o2", "o3"):
        ex, ct = lanes_m(ro, open_rule(co, rule), span)
        R["lanes"][rule] = {"exact": ex, "contour": ct}
    R["f1_50"] = f1(ro, co, 0.05, span)
    R["_ro"], R["_co"], R["_span"] = ro, co, span
    return R


def human_rows(label):
    """Each alt chart against the primary, as a candidate in the primary's frame."""
    ks = [k for k, _ in L.charts(label)]
    if len(ks) < 2: return {}
    ro, span = L.human(label, "primary")
    out = {}
    for k in ks[1:]:
        ho = L.human_as_cand(label, k)
        if not ho: continue
        p = pairs(ro, ho, TOL)
        rep = set(repeats(ho)); fr = fast_runs([o["t"] for o in ho]) >= 0
        ex, ct = lanes_m(ro, ho, span)
        out[k] = {"state": agree(ro, [state(o) for o in ho], p),
                  "sus_agree": (sum(1 for i, j in p if held(ro[i]) == held(ho[j])) / len(p)) if p else None,
                  "f1_50": f1(ro, ho, 0.05, span), "exact": ex, "contour": ct}
    return out


def human_stats(label):
    out = {}
    for k, _ in L.charts(label):
        ro, _ = L.human(label, k)
        if not ro: continue
        rep = set(repeats(ro)); fr = fast_runs([o["t"] for o in ro]) >= 0
        out[k] = {"repeat_share": len(rep) / len(ro), "n_fast": int(fr.sum()),
                  "fast_repeat_share": (sum(1 for i in rep if fr[i]) / fr.sum()) if fr.sum() else None,
                  "open_share": sum(is_open(o) for o in ro) / len(ro), "open_run": longest_open(ro),
                  "tap_share": sum(state(o) == "tap" for o in ro) / len(ro),
                  "sus_share": sum(held(o) for o in ro) / len(ro)}
    return out


def repeat_rules(label, charts, env):
    ks = list(charts)
    co = charts[ks[0]]["_co"]
    rep = repeats(co); reps = set(rep)
    fr = fast_runs([o["t"] for o in co]) >= 0
    out = {"repeat_share": len(rep) / len(co), "n_repeats": len(rep), "n_fast": int(fr.sum()),
           "fast_repeat_share": (sum(1 for i in rep if fr[i]) / fr.sum()) if fr.sum() else None}
    any_match, near50 = {}, {}
    for k in ks:
        ro, cok = charts[k]["_ro"], charts[k]["_co"]
        rt = np.array([o["t"] for o in ro])
        for i, j in pairs(ro, cok, 0.05): any_match[cok[j]["tick"]] = True
        for o in cok:
            if near(rt, o["t"], 0.05): near50[o["tick"]] = True
    out["match50_repeats"] = (sum(1 for i in rep if any_match.get(co[i]["tick"])) / len(rep)) if rep else None
    oth = [i for i in range(len(co)) if i not in reps]
    out["match50_other"] = (sum(1 for i in oth if any_match.get(co[i]["tick"])) / len(oth)) if oth else None
    cands = {}
    val = None
    if env is not None:
        e, fps = env
        val = {i: env_at(e, fps, co[i]["t"]) for i in range(len(co))}
        allv = np.array(list(val.values()))
    for G in GAPS:
        cands[f"gap{G}"] = [i for i in rep if 1000 * (co[i]["t"] - co[i - 1]["t"]) >= G - 1e-6]
        for pc in PCTS:
            if val is not None:
                thr = float(np.percentile(allv, pc))
                cands[f"gap{G}_stem_p{pc}"] = [i for i in cands[f"gap{G}"] if val[i] < thr]
    f1b = {k: f1(charts[k]["_ro"], charts[k]["_co"], 0.05, charts[k]["_span"]) for k in ks}
    out["f1_50_before"] = mean(f1b.values())
    Rr = {}
    for name, rem in cands.items():
        rt_ = {co[i]["tick"] for i in rem}
        after, hum_removed = {}, {}
        for k in ks:
            ro, cok = charts[k]["_ro"], charts[k]["_co"]
            after[k] = f1(ro, [o for o in cok if o["tick"] not in rt_], 0.05, charts[k]["_span"])
            hum_removed[k] = sum(1 for i, j in pairs(ro, cok, 0.05) if cok[j]["tick"] in rt_) / len(ro)
        Rr[name] = {"removed": len(rem),
                    "precision": (sum(1 for i in rem if not near50.get(co[i]["tick"])) / len(rem)) if rem else None,
                    "f1_50_change": mean(after.values()) - out["f1_50_before"],
                    "human_removed_share": mean(hum_removed.values()),
                    "human_removed_share_max": max(hum_removed.values())}
    out["rules"] = Rr
    return out


def main():
    outp = L.SHM / "c_raw.json"
    res = json.loads(outp.read_text()) if outp.exists() else {}
    only = sys.argv[1:] or L.LABELS
    for label in only:
        if label in res: continue
        if not all((L.arm_dir(a, label, v) / "notes.chart").is_file() for a in ARMS for v in ("V1", "V2", "V3")):
            print(label, "variants not built yet", flush=True); continue
        env = stem_env(str(L.SONGS[label][2]))
        row = {"arms": {}, "humans": human_rows(label), "human_stats": human_stats(label),
               "charts": [k for k, _ in L.charts(label)]}
        for arm in ARMS:
            d = L.arm_dir(arm, label)
            rep = json.loads((d / "report.json").read_text())
            octave, bpm = rep["grid"].get("octave"), rep["grid"].get("bpm_median")
            base_sc = L.scan(d)
            ch = {k: chart_row(label, arm, k, octave, base_sc) for k, _ in L.charts(label)}
            ch = {k: v for k, v in ch.items() if v.get("n_human")}
            A = {"octave": octave, "bpm": bpm, "charts": ch}
            if all(not v["variant_onset_mismatch"] for v in ch.values()):
                A["repeats"] = repeat_rules(label, ch, env)
            for v in ch.values():
                for x in ("_ro", "_co", "_span"): v.pop(x, None)
            row["arms"][arm] = A
        res[label] = row
        outp.write_text(json.dumps(res))
        print(label, {a: sum(c["variant_onset_mismatch"] for c in v["charts"].values()) for a, v in row["arms"].items()}, flush=True)


if __name__ == "__main__":
    main()
