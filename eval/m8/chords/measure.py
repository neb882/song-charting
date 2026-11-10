"""measure.py: the guitar's chord share against the 4 GPU takes' agreement (advisor finding 1; prereg.txt beside).

Reuses M8-02's loader (m8-02/C/scripts/m2lib.py) and alignment (align.py, run in process with its audio pointed at the
v0.4.0 golden folder's song.ogg, whose tempo map and lead-in equal the m05/one arms' charts: checked before). Reads the
arms' charts (m8-02/B/charts/<arm>/<label>.notes.chart, copied to <shm>/chords/charts), part B's window picks
(B/arms/<label>.json), the zip's 4 GPU takes (notes only, scan-chart) and the humans through the scorer's scan.
Writes <out>/results.json (labels only, 3 decimals). Prints labels and counts only.
Usage: python -I measure.py <out dir>"""
import json, os, runpy, shutil, sys
from pathlib import Path
CODE = Path("<shm>/chords/code")
M8 = Path("<scratchpad>/m8")
M802 = M8 / "m8-02"
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(M802 / "C" / "scripts"))
import numpy as np        # noqa: E402
import m2lib as L         # noqa: E402
S = L.S
SH = Path("<shm>/chords")
L.SHM = SH
L.KEEP = SH / "keep"
OUT = Path(sys.argv[1])
G = L.G
ZIP = M802 / "zip" / "gpu_results" / "takes"
SEEDS = (20260609, 101, 202, 303)
GOLD = {"refs": G / "v040f", "stress": G / "v040f-stress", "set20": G / "v040-set20"}
TOL = 0.05


def gpu_dir(label):
    st = L.SONGS[label][0]
    return ZIP / label if st == "refs" else ZIP / st / label


def gold_dir(label):
    st, sid, _ = L.SONGS[label]
    return GOLD[st] / sid


# ---------------------------------------------------------------- setup: charts and audio in shm, then align.py
for label in L.LABELS:
    for arm in ("m05", "one"):
        d = SH / "charts" / arm / label
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(M802 / "B" / "charts" / arm / f"{label}.notes.chart", d / "notes.chart")
    a = L.KEEP / "_audio" / label
    a.mkdir(parents=True, exist_ok=True)
    if not (a / "song.ogg").exists():
        os.symlink(gold_dir(label) / "song.ogg", a / "song.ogg")
runpy.run_path(str(M802 / "C" / "scripts" / "align.py"), run_name="__main__")
AL = L.alignment()


def well(label, k):
    a = AL[label][k]
    return a["good_windows"] > 4.5 and a["lag_mad_ms"] < 2.0


def chord(o):
    return len(set(o["lanes"])) > 1


# lanes-drums part 1 (eval/m8/lanes-drums/measure.py), copied
def shape(o):
    return frozenset(o['lanes'])


def runs(ons):
    out = []
    for o in ons:
        s = shape(o)
        if out and out[-1][0] == s:
            out[-1][1] += 1
            out[-1][3] = o['t']
        else:
            out.append([s, 1, o['t'], o['t']])
    return out


def cpo(ons):
    return (len(runs(ons)) - 1) / len(ons) if ons else None


def near_any(ts, t, tol):
    if not len(ts):
        return False
    k = np.searchsorted(ts, t)
    return any(0 <= q < len(ts) and abs(ts[q] - t) <= tol + 1e-9 for q in (k - 1, k))


def nearest(ons_t, t, tol):
    if not len(ons_t):
        return None
    k = np.searchsorted(ons_t, t)
    best = None
    for q in (k - 1, k):
        if 0 <= q < len(ons_t) and abs(ons_t[q] - t) <= tol + 1e-9 and (best is None or abs(ons_t[q] - t) < abs(ons_t[best] - t)):
            best = q
    return best


VARIANTS = [(K, r) for K in (2, 3, 4) for r in ("high", "low", "mode")]
PRIMARY = (2, "high")


def vname(v):
    return f"K{v[0]}_{v[1]}"


def reduce_lane(o, rule):
    ls = sorted(set(o["lanes"]))
    if rule == "low":
        return ls[0]
    if rule == "high":
        return ls[-1]
    cnt = o["_lane_votes"]
    return max(ls, key=lambda l: (cnt.get(l, 0), l))


def apply(co, v):
    K, rule = v
    return [dict(o, lanes=[reduce_lane(o, rule)]) if chord(o) and o["_k"] < K else o for o in co]


def metrics(ro, co, span):
    p = L.pairs(ro, co, TOL)
    ex = [frozenset(ro[i]["lanes"]) == frozenset(co[j]["lanes"]) for i, j in p]
    hct = np.array([o["t"] for o in ro if chord(o)])
    oc = [o for o in co if chord(o)]
    m100 = S.track_metrics(ro, co, "guitar", span, False, False)
    return {"n_ours": len(co), "chord_share": sum(map(chord, co)) / len(co) if co else None,
            "exact50": float(np.mean(ex)) if ex else None, "exact100": m100["exact_lane_agreement"]["value"],
            "cpo": cpo(co), "f1_50": L.f1(ro, co, TOL, span),
            "chord_prec": (sum(near_any(hct, o["t"], TOL) for o in oc) / len(oc)) if oc else None, "n_chords": len(oc)}


res = {"songs": {}}
if os.environ.get("ONLY"):
    L.LABELS = os.environ["ONLY"].split(",")
for label in L.LABELS:
    gd = gold_dir(label)
    pad = json.loads((gd / "report.json").read_text())["lead_in"]["pad_seconds"]
    takes = []
    for s in SEEDS:
        sc = L.scan(gpu_dir(label) / f"seed_{s}")
        ons = S.onsets(L.gtrack(sc), S.chart_delay_ms(sc)[0], "guitar")
        takes.append((np.array([o["t"] for o in ons]), ons))
    takes_ch = [np.array([o["t"] for o in ons if chord(o)]) for _, ons in takes]
    union = np.sort(np.concatenate([t for t, _ in takes]))
    windows = json.loads((M802 / "B" / "arms" / f"{label}.json").read_text())["arms"]["m05"]["takes"]["windows"]
    song = {"pad": pad, "arms": {}}
    for arm in ("m05", "one"):
        folder = SH / "charts" / arm / label
        sc = L.scan(folder)
        cdel = S.chart_delay_ms(sc)[0]
        full = L._ons(sc, cdel)                                  # chart clock (s), with ticks
        ct = np.array([o["t"] for o in full])
        # d: chart clock minus the takes' clock
        d0 = pad
        diffs = []
        for t in ct:
            q = nearest(union, t - d0, 0.03)
            if q is not None:
                diffs.append(t - d0 - union[q])
        d = d0 + float(np.median(diffs))
        offset = pad - d
        # step 1: each chord onset against the take its window used, within 5 ms
        bounds = [w["start"] + offset for w in windows]
        s1 = {"n": 0, "match5": 0, "match5_chord": 0, "match50": 0, "snap16": 0}
        res_ms = []
        res_t = sc["resolution"]
        tps = sorted(sc["tempos"], key=lambda x: x["tick"])

        def sec_to_tick(t):   # chart-clock seconds -> fractional tick (the chart's tempo map)
            ms = t * 1000 - cdel
            k = max([i for i, x in enumerate(tps) if x["msTime"] <= ms] or [0])
            x = tps[k]
            return x["tick"] + (ms - x["msTime"]) * x["beatsPerMinute"] * res_t / 60000.0
        info = {}
        for o in full:
            u = o["t"] - d
            kk = sum(near_any(tc, u, TOL) for tc in takes_ch)
            votes = {}
            for tt, ons in takes:
                q = nearest(tt, u, TOL)
                if q is not None:
                    for l in set(ons[q]["lanes"]):
                        votes[l] = votes.get(l, 0) + 1
            info[o["tick"]] = (kk, votes)
            if chord(o):
                if arm == "m05":
                    def win(x):
                        return max([i for i, b in enumerate(bounds) if b <= x] or [0])
                    cand = {windows[win(x)]["pick"] for x in (u - 0.1, u, u + 0.1)}
                else:
                    cand = {0}
                s1["n"] += 1
                m5 = [(p, q) for p in cand for q in [nearest(takes[p][0], u, 0.005)] if q is not None]
                s1["match5"] += bool(m5)
                s1["match5_chord"] += any(chord(takes[p][1][q]) for p, q in m5)
                m50 = [(p, q) for p in cand for q in [nearest(takes[p][0], u, TOL)] if q is not None]
                s1["match50"] += bool(m50)
                if m50:
                    p_, q_ = min(m50, key=lambda x: abs(takes[x[0]][0][x[1]] - u))
                    tu = takes[p_][0][q_]
                    res_ms.append((o["t"] - d - tu) * 1000)
                    # the take's onset snapped to the chart's grid: the chart's tick within half a 16th (res/8) of it
                    s1["snap16"] += abs(o["tick"] - sec_to_tick(tu + d)) <= res_t / 8 + 1
        if res_ms:
            r = np.abs(res_ms)
            s1["res_ms"] = {"median_signed": float(np.median(res_ms)), "abs_p50": float(np.percentile(r, 50)),
                            "abs_p90": float(np.percentile(r, 90)), "abs_max": float(r.max())}
        A = {"d_minus_pad_ms": -offset * 1000, "step1": s1, "charts": {}}
        # the table on the whole chart (no human): our onsets by k
        A["by_k_all"] = {"chords": [sum(1 for o in full if chord(o) and info[o["tick"]][0] == k) for k in range(5)],
                         "singles": [sum(1 for o in full if not chord(o) and info[o["tick"]][0] == k) for k in range(5)]}
        for kname, _f in L.charts(label):
            ro, span = L.human(label, kname)
            if not ro:
                continue
            co = L.ours(folder, label, kname, span)
            for o in co:
                o["_k"], o["_lane_votes"] = info[o["tick"]]
            hct = np.array([o["t"] for o in ro if chord(o)])
            p = L.pairs(ro, co, TOL)
            pm = {j: i for i, j in p}
            tab = {"chord": [[0, 0, 0, 0] for _ in range(5)], "single": [[0, 0, 0, 0] for _ in range(5)]}
            # per k: [n, human chord within 50 ms, matched to a human onset, matched human onset is a chord]
            for j, o in enumerate(co):
                row = tab["chord" if chord(o) else "single"][o["_k"]]
                row[0] += 1
                row[1] += near_any(hct, o["t"], TOL)
                if j in pm:
                    row[2] += 1
                    row[3] += chord(ro[pm[j]])
            C = {"well": well(label, kname), "human": {"chord_share": sum(map(chord, ro)) / len(ro), "cpo": cpo(ro),
                                                         "n": len(ro)},
                 "table": tab, "base": metrics(ro, co, span)}
            C["variants"] = {}
            for v in VARIANTS:
                cv = apply(co, v)
                C["variants"][vname(v)] = dict(metrics(ro, cv, span), demoted=sum(1 for a, b in zip(co, cv) if a is not b))
            A["charts"][kname] = C
        song["arms"][arm] = A
    res["songs"][label] = song
    a = song["arms"]["m05"]
    print(label, "charts", len(a["charts"]), "step1", a["step1"]["match5"], "/", a["step1"]["n"], flush=True)


def rd(x):
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return round(float(x), 3)
    if isinstance(x, dict):
        return {k: rd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rd(v) for v in x]
    return x


OUT.mkdir(parents=True, exist_ok=True)
(OUT / "results.json").write_text(json.dumps(rd(res), indent=1))
