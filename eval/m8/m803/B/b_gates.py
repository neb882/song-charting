"""b_gates.py: Part B. Reads ../common.py's records (today's v0.4.0 bass Expert chart, every human bass chart) and B/cache/*.npz (b_engine.py: engine onsets, their
pitches, pYIN track). Per onset of our bass chart: matched engine onset (within 40 ms), the voiced share of pYIN frames 20-150 ms after it, whether the engine gave it
a pitch, whether it is in a same-lane run (L 4 or 6, gaps at most G 110 or 150 ms), whether the previous onset's note is voiced through this onset (held), whether a human
note (any chart) is within 50 ms. Candidates: g1 (no voiced frame in the window), g2 = g1 inside a run (4 configs), g3 = g2 and held (4 configs). Per candidate: removed, songs
touched, precision, bass F1@50 change per song (mean over human charts) and pooled with a paired bootstrap CI over songs (s06, s08, s10 out), songs and references down
by more than 0.01, human notes removed per song (removed onsets with a human note within 50 ms / human notes, mean over charts), repeat share after against the humans'.
Writes B/b_result.json (3 decimals); prints a summary table. ntl is skipped (its work folder is gone)."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent.parent))
import common as C

S = C.S
HERE = Path(__file__).parent
PITCH_HOP_S = None
from songcharter.engines import bass as BE
s = BE.Settings(); STEP = s.pitch_hop/s.pitch_rate
EXCLUDE_POOL = {"s06", "s08", "s10"}
NOBASS = {"drunk_drivers", "break"}
def r3(x):
    if isinstance(x, (float, np.floating)): return round(float(x), 3)
    if isinstance(x, dict): return {k: r3(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [r3(v) for v in x]
    return x
def times(rec, part="bass"): return np.array([o[0] for o in rec["parts"][part]["onsets"]])
def span_of(rec):
    st, en = [], []
    for p in rec["parts"].values():
        if p["onsets"]: st.append(p["onsets"][0][0]); en.append(max(o[0]+o[2] for o in p["onsets"]))
    return (min(st), max(en))
def f1(rt, ct, span, tol=0.05):
    lo, hi = span[0]-S.SPAN_MARGIN, span[1]+S.SPAN_MARGIN
    ct = np.sort(ct[(ct >= lo) & (ct <= hi)]); pairs = S.match(np.sort(rt), ct, tol)
    return S.prf(len(pairs), len(rt), S.n_cand_eff(pairs, ct, span))["f1"]
def near(t, other, tol=0.05):
    o = np.sort(other); i = np.searchsorted(o, t); d = np.full(len(t), np.inf)
    ok = i < len(o); d[ok] = np.abs(o[i[ok]]-t[ok]); ok = i > 0; d[ok] = np.minimum(d[ok], np.abs(o[i[ok]-1]-t[ok])); return d <= tol
def rep_share(ons):
    f = [len(a[1]) == 1 and len(b[1]) == 1 and a[1][0] == b[1][0] for a, b in zip(ons, ons[1:])]
    return float(np.mean(f)) if f else 0.0
def boot(d, n=10000, seed=1):
    d = np.asarray(d, float); rng = np.random.default_rng(seed); m = d[rng.integers(0, len(d), (n, len(d)))].mean(axis=1)
    return [float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)), len(d)]
RUNS = [(L, G) for L in (4, 6) for G in (110, 150)]
feat = {}
for lab, st, sid in C.songs():
    if lab in NOBASS: continue
    rec = C.build(lab, st, sid)
    hum = {k: h for k, h in rec["humans"].items() if "bass" in h["parts"]}
    if not hum or "bass" not in rec["ours"]["parts"]: continue
    z = np.load(HERE/"cache"/f"{lab}.npz"); et, ep, midi = z["et"], z["ep"], z["midi"]
    ons = rec["ours"]["parts"]["bass"]["onsets"]; ot = np.array([o[0] for o in ons]); n = len(ons)
    idx = np.searchsorted(et, ot); e2o = np.full(n, -1)
    for k, t in enumerate(ot):
        best = None
        for j in (idx[k]-1, idx[k]):
            if 0 <= j < len(et) and abs(et[j]-ot[k]) <= 0.04 and (best is None or abs(et[j]-ot[k]) < abs(et[best]-ot[k])): best = j
        e2o[k] = -1 if best is None else best
    tt = np.where(e2o >= 0, et[np.maximum(e2o, 0)], ot)          # the onset's time: the engine's when matched
    has_pitch = np.array([e2o[k] >= 0 and np.isfinite(ep[e2o[k]]) for k in range(n)])
    voiced_share = np.zeros(n); nfr = np.zeros(n, int)
    for k in range(n):
        a, b = BE._frame(tt[k]+0.020, s), BE._frame(tt[k]+0.150, s)
        seg = midi[a:b+1]; nfr[k] = len(seg); voiced_share[k] = np.isfinite(seg).mean() if len(seg) else 0.0
    held = np.zeros(n, bool)
    for k in range(1, n):
        a, b = BE._frame(tt[k-1], s), BE._frame(tt[k], s); seg = midi[a:b+1]
        held[k] = len(seg) > 0 and bool(np.all(np.isfinite(seg)))
    single = [len(o[1]) == 1 for o in ons]
    inrun = {}
    for L, G in RUNS:
        m = np.zeros(n, bool); i = 0
        while i < n:
            j = i
            while j+1 < n and single[i] and single[j+1] and ons[j+1][1] == ons[i][1] and ot[j+1]-ot[j] <= G/1000+1e-9: j += 1
            if j-i+1 >= L: m[i:j+1] = True
            i = j+1
        inrun[(L, G)] = m
    ht = {k: times(h) for k, h in hum.items()}; sp = {k: span_of(h) for k, h in hum.items()}
    isnear = np.zeros(n, bool)
    for k in hum: isnear |= near(ot, ht[k])
    base = {k: f1(ht[k], ot, sp[k]) for k in hum}
    feat[lab] = dict(ons=ons, ot=ot, hum=hum, ht=ht, sp=sp, near=isnear, base=base, voiced_share=voiced_share, has_pitch=has_pitch, held=held, inrun=inrun,
                     matched=int((e2o >= 0).sum()), nfr_min=int(nfr.min()))
CANDS = {"g1": lambda F: F["voiced_share"] == 0}
for L, G in RUNS:
    CANDS[f"g2_L{L}_G{G}"] = (lambda L, G: (lambda F: (F["voiced_share"] == 0) & F["inrun"][(L, G)]))(L, G)
    CANDS[f"g3_L{L}_G{G}"] = (lambda L, G: (lambda F: (F["voiced_share"] == 0) & F["inrun"][(L, G)] & F["held"]))(L, G)
res = {"candidates": {}, "songs": {}}
for lab, F in feat.items():
    ons = F["ons"]; res["songs"][lab] = {"onsets": len(ons), "engine_matched": F["matched"], "no_voiced_share": float((F["voiced_share"] == 0).mean()),
        "no_engine_pitch_share": float((~F["has_pitch"]).mean()), "repeat_share": rep_share(ons),
        "humans_repeat_share": float(np.mean([rep_share(h["parts"]["bass"]["onsets"]) for h in F["hum"].values()])),
        "human_notes_primary": int(len(F["ht"].get("primary", next(iter(F["ht"].values())))))}
for name, fn in CANDS.items():
    per = {}; tot_rm = tot_np = 0
    for lab, F in feat.items():
        m = fn(F); rm = int(m.sum()); ot = F["ot"]; keep = ~m
        d = {"removed": rm, "removed_no_human": int((m & ~F["near"]).sum())}
        d["f1_change"] = float(np.mean([f1(F["ht"][k], ot[keep], F["sp"][k]) - F["base"][k] for k in F["hum"]])) if rm else 0.0
        hn = []
        for k, h in F["hum"].items():
            hm = near(F["ht"][k], ot[m]) if rm else np.zeros(len(F["ht"][k]), bool)
            hn.append(float(hm.mean()))
        d["human_notes_removed_share"] = float(np.mean(hn)); d["human_notes_removed_share_max_chart"] = float(max(hn))
        d["repeat_share_after"] = rep_share([o for o, x in zip(F["ons"], m) if not x]); d["repeat_share_before"] = res["songs"][lab]["repeat_share"]
        d["humans_repeat_share"] = res["songs"][lab]["humans_repeat_share"]
        per[lab] = d; tot_rm += rm; tot_np += d["removed_no_human"]
    pool = [per[l]["f1_change"] for l in per if l not in EXCLUDE_POOL]
    pool_all = [per[l]["f1_change"] for l in per]
    refs = [l for l in per if l in C.REFS]
    res["candidates"][name] = {"removed": tot_rm, "songs_touched": sum(1 for d in per.values() if d["removed"]), "precision": (tot_np/tot_rm) if tot_rm else None,
        "f1_change_pooled_mean_ci95_n": boot(pool), "f1_change_all_songs_mean_ci95_n": boot(pool_all),
        "songs_down_gt_0.01": {l: d["f1_change"] for l, d in per.items() if d["f1_change"] < -0.01},
        "refs_down_gt_0.01": {l: per[l]["f1_change"] for l in refs if per[l]["f1_change"] < -0.01},
        "max_human_removed_share": max(d["human_notes_removed_share"] for d in per.values()),
        "songs_human_removed_ge_0.5pct": [l for l, d in per.items() if d["human_notes_removed_share"] >= 0.005],
        "repeat_share_after_mean": float(np.mean([d["repeat_share_after"] for d in per.values()])),
        "repeat_share_before_mean": float(np.mean([d["repeat_share_before"] for d in per.values()])),
        "humans_repeat_share_mean": float(np.mean([d["humans_repeat_share"] for d in per.values()])), "per_song": per}
res["notes"] = {"songs": sorted(feat), "pool_excludes": sorted(EXCLUDE_POOL), "ntl": "skipped: its work folder is gone", "STEP_s": STEP}
json.dump(r3(res), open(HERE/"b_result.json", "w"), indent=1)
for name, c in r3(res["candidates"]).items():
    print(name, "removed", c["removed"], "songs", c["songs_touched"], "prec", c["precision"], "dF1", c["f1_change_pooled_mean_ci95_n"], "down", c["songs_down_gt_0.01"], "maxHumRm", c["max_human_removed_share"])
