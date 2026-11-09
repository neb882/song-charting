"""c_report.py: reads <shm>/m8/m2/c_raw.json (c_analyze.py) and C/cf_m05.json (cf_contour.py, if there); writes
C/C.json (per song and pooled, floats to 3 decimals; labels only) and prints part C's tables (markdown)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m2lib as L
from m2lib import r3, boot, mean

import os
raw = json.loads((L.SHM / "c_raw.json").read_text())
CH = os.environ.get("C_CHARTS", "all")   # "all" (the order's rule) or "aligned": charts whose alignment to our audio
AL = L.alignment()                       # score.py calls good (more than half the windows at ncc 0.3, lag MAD under 2 ms)


def okc(label, k):
    return CH == "all" or (AL[label][k]["good_windows"] > 4.5 and AL[label][k]["lag_mad_ms"] < 2.0)
SONGS = [s for s in L.LABELS if s in raw]
ARMS = ("m05", "cpu_m05", "cpu_one")
AN = {"m05": "GPU m05", "cpu_m05": "CPU m05", "cpu_one": "CPU one"}
OUT = {"songs": {}, "pooled": {}}


def sv(label, arm, f):
    """A song's value: the mean over its charts of f(chart row) (None rows skipped)."""
    ch = raw[label]["arms"][arm]["charts"]
    return mean([f(c) for k, c in ch.items() if okc(label, k)])


def hv(label, key):
    h = raw[label]["humans"]
    return mean([x.get(key) for k, x in h.items() if okc(label, k)]) if h else None


def pool(cand, base=None, hum=None, songs=None):
    """{scope: mean (and diff vs base with CI)}; scopes all / without the references / without humans under 0.6."""
    songs = songs or SONGS
    out = {}
    scopes = {"all": songs, "no_refs": [s for s in songs if s not in L.REFS],
              "humans>=0.6": [s for s in songs if hum is None or hum.get(s) is None or hum[s] >= 0.6]}
    for sc, ss in scopes.items():
        ss = [s for s in ss if cand.get(s) is not None and (base is None or base.get(s) is not None)]
        d = {"mean": r3(np.mean([cand[s] for s in ss])) if ss else None, "n": len(ss)}
        if base is not None and ss:
            d["diff"] = boot([cand[s] - base[s] for s in ss])
            diffs = {s: cand[s] - base[s] for s in ss}
            w = min(diffs, key=diffs.get)
            d["worst"] = [w, r3(diffs[w])]
        out[sc] = d
    return out


def cell(p, sc="all"):
    d = p[sc]
    if d["mean"] is None: return "-"
    s = f"{d['mean']:.3f}"
    if "diff" in d and d["diff"]:
        x = d["diff"]; s += f" ({x['mean']:+.3f} [{x['lo']:+.3f}, {x['hi']:+.3f}])"
    return s + f" n={d['n']}"


def f3(x):
    return "-" if x is None else f"{x:.3f}"


def table_pooled(title, rows):
    print(f"\n{title}\n\n| | all songs | without the references | without humans under 0.6 |\n|---|---|---|---|")
    for name, p in rows:
        print(f"| {name} | {cell(p)} | {cell(p, 'no_refs')} | {cell(p, 'humans>=0.6')} |")


# ---------------- C-a
hum_state = {s: hv(s, "state") for s in SONGS}
print("## C-a. The HOPO rule (Expert guitar, state agreement at 100 ms, song mean over its charts)")
for arm in ARMS:
    st = {r: {s: sv(s, arm, lambda c, r=r: (c.get("state") or {}).get(r)) for s in SONGS}
          for r in ("base", "V1", "V2", "R1", "R2", "R2_all", "T1", "T2")}
    OUT["songs"].setdefault(arm, {})["state"] = {r: {s: r3(v) for s, v in d.items()} for r, d in st.items()}
    if arm == "m05":
        print("\n| song | octave | charts | forced (today) | source | natural | R1 | R2 fast runs (changed) | R2 all | humans | HOPO share forced / source / natural / humans |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for s in SONGS:
            A = raw[s]["arms"][arm]
            hs = lambda v: sv(s, arm, lambda c: c["hopo_share"][v])
            print(f"| {s} | {A['octave']} | {len(A['charts'])} | {f3(st['base'][s])} | {f3(st['V1'][s])} | {f3(st['V2'][s])} | {f3(st['R1'][s])} | "
                  f"{f3(st['R2'][s])} ({sum(c.get('r2_changed', 0) for c in A['charts'].values())}) | {f3(st['R2_all'][s])} | {f3(hum_state[s])} | "
                  f"{f3(hs('base'))} / {f3(hs('V1'))} / {f3(hs('V2'))} / {f3(sv(s, arm, lambda c: c['hopo_share_human']))} |")
    P = {r: pool(st[r], None if r == "base" else st["base"], hum_state) for r in st}
    OUT["pooled"].setdefault(arm, {})["state"] = P
    table_pooled(f"**{AN[arm]}**: state agreement (difference from today's \"forced\", paired bootstrap over songs)",
                 [("forced (today)", P["base"]), ("source", P["V1"]), ("natural", P["V2"]), ("R1 octave rule", P["R1"]),
                  ("R2 no forced strums in fast runs", P["R2"]), ("R2 everywhere (M7-01's R2)", P["R2_all"])])
    # confusion by engine flag
    tot = {}
    for s in SONGS:
        for c in raw[s]["arms"][arm]["charts"].values():
            for k, d in (c.get("by_engine_flag") or {}).items():
                t = tot.setdefault(k, {"n": 0, "human_strum": 0, "human_hopo": 0, "human_tap": 0})
                for x in t: t[x] += d[x]
    OUT["pooled"][arm]["by_engine_flag"] = tot
    print(f"\n{AN[arm]}: our notes by the engine's flag (matched at 100 ms, all charts summed): " + "; ".join(
        f"{k} {d['n']}: humans strum {d['human_strum'] / d['n']:.3f}, HOPO {d['human_hopo'] / d['n']:.3f}, tap {d['human_tap'] / d['n']:.3f}"
        for k, d in sorted(tot.items()) if d["n"]))
    # per-song tap precision under each mode (the bar's "tap precision not lower")
    for r in ("V1", "V2"):
        tp = {s: sv(s, arm, lambda c, r=r: c["taps"][r]["precision"]) for s in SONGS}
        tb = {s: sv(s, arm, lambda c: c["taps"]["base"]["precision"]) for s in SONGS}
        OUT["pooled"][arm][f"tap_precision_{r}"] = pool(tp, tb)

# ---------------- C-b
print("\n## C-b. Taps (Expert guitar)")
for arm in ARMS:
    g = lambda f: {s: sv(s, arm, f) for s in SONGS}
    T = {"share_ours": g(lambda c: c["taps"]["base"]["share"]), "share_human": g(lambda c: c["taps"]["human_share"]),
         "precision": g(lambda c: c["taps"]["base"]["precision"]), "recall": g(lambda c: c["taps"]["recall"]),
         "T2_precision": g(lambda c: c["taps"]["T2_precision"]),
         "n_ours": g(lambda c: c["taps"]["base"]["n"]), "n_human": g(lambda c: c["taps"]["human_n"])}
    st = OUT["songs"][arm]["state"]
    OUT["songs"][arm]["taps"] = {k: {s: r3(v) for s, v in d.items()} for k, d in T.items()}
    if arm == "m05":
        print("\n| song | tap share ours | humans | our taps | human taps | precision | recall | T0 (today) | T1 no taps | T2 taps only in fast runs | T2 precision |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for s in SONGS:
            print(f"| {s} | {f3(T['share_ours'][s])} | {f3(T['share_human'][s])} | {T['n_ours'][s]:.0f} | {T['n_human'][s]:.0f} | {f3(T['precision'][s])} | "
                  f"{f3(T['recall'][s])} | {f3(st['base'][s])} | {f3(st['T1'][s])} | {f3(st['T2'][s])} | {f3(T['T2_precision'][s])} |")
    base = {s: st["base"][s] for s in SONGS}
    P = {"T1": pool({s: st["T1"][s] for s in SONGS}, base, hum_state), "T2": pool({s: st["T2"][s] for s in SONGS}, base, hum_state),
         "precision": pool(T["precision"]), "recall": pool(T["recall"]), "T2_precision": pool(T["T2_precision"]),
         "share_ours": pool(T["share_ours"]), "share_human": pool(T["share_human"])}
    OUT["pooled"][arm]["taps"] = P
    table_pooled(f"**{AN[arm]}**: taps", [("T0 today", OUT["pooled"][arm]["state"]["base"]), ("T1 no taps", P["T1"]),
                                          ("T2 taps only in fast runs", P["T2"]), ("tap precision", P["precision"]),
                                          ("tap recall", P["recall"]), ("T2's tap precision", P["T2_precision"]),
                                          ("tap share ours", P["share_ours"]), ("tap share humans", P["share_human"])])

# ---------------- C-c
print("\n## C-c. Guitar sustains (Expert): the floor caps")
print(f"\nThe slow songs (the order's list, grid under 100 BPM): {', '.join(L.SLOW)}; our grid's median BPM per arm in C.json.")
hum_sus = {s: hv(s, "sus_agree") for s in SONGS}
for arm in ARMS:
    g = lambda f: {s: sv(s, arm, f) for s in SONGS}
    sa = {v: g(lambda c, v=v: c["sus_agree"][v]) for v in ("base", "V1", "V2", "V3")}
    ss = {v: g(lambda c, v=v: c["sus_share"][v]) for v in ("base", "V1", "V2", "V3")}
    dr = {v: g(lambda c, v=v: c["human_sus_dropped"][v]) for v in ("base", "V1", "V2", "V3")}
    hsh = g(lambda c: c["sus_share_human"])
    OUT["songs"][arm]["sustain"] = {"agree": {v: {s: r3(x) for s, x in d.items()} for v, d in sa.items()},
                                    "share": {v: {s: r3(x) for s, x in d.items()} for v, d in ss.items()},
                                    "human_dropped": {v: {s: r3(x) for s, x in d.items()} for v, d in dr.items()},
                                    "share_human": {s: r3(x) for s, x in hsh.items()},
                                    "bpm": {s: r3(raw[s]["arms"][arm]["bpm"]) for s in SONGS}}
    if arm == "m05":
        print("\n| song | BPM | sustain share today / 300 / 400 / 500 / humans | agreement today / 300 / 400 / 500 / humans | humans' sustains dropped today / 300 / 400 / 500 |")
        print("|---|---|---|---|---|")
        for s in SONGS:
            j = lambda d: " / ".join(f3(d[v][s]) for v in ("base", "V1", "V2", "V3"))
            print(f"| {s}{' (slow)' if s in L.SLOW else ''} | {raw[s]['arms'][arm]['bpm']:.1f} | {j(ss)} / {f3(hsh[s])} | {j(sa)} / {f3(hum_sus[s])} | {j(dr)} |")
    P = {}
    for v, nm in (("V1", "cap 300"), ("V2", "cap 400"), ("V3", "cap 500")):
        P[v] = {"slow": pool(sa[v], sa["base"], hum_sus, [s for s in SONGS if s in L.SLOW]),
                "other": pool(sa[v], sa["base"], hum_sus, [s for s in SONGS if s not in L.SLOW]),
                "all": pool(sa[v], sa["base"], hum_sus)}
    OUT["pooled"][arm]["sustain"] = P
    print(f"\n**{AN[arm]}**: per-note sustain agreement, today {cell(pool(sa['base']))}")
    print("\n| cap | slow songs | other songs (worst) | all songs | share ours (all) | humans' sustains dropped (all) |\n|---|---|---|---|---|---|")
    for v, nm in (("V1", "300 ms"), ("V2", "400 ms"), ("V3", "500 ms")):
        print(f"| {nm} | {cell(P[v]['slow'])} | {cell(P[v]['other'])} worst {P[v]['other']['all'].get('worst')} | {cell(P[v]['all'])} | "
              f"{cell(pool(ss[v]))} | {cell(pool(dr[v]))} |")
    print(f"| today | | | | {cell(pool(ss['base']))} | {cell(pool(dr['base']))} |")

# ---------------- C-d
print("\n## C-d. Open notes (Expert guitar)")
for arm in ARMS:
    g = lambda f: {s: sv(s, arm, f) for s in SONGS}
    op = {s: raw[s]["arms"][arm]["charts"]["primary"]["opens"]["n_ours"] if "primary" in raw[s]["arms"][arm]["charts"] else 0 for s in SONGS}
    with_open = [s for s in SONGS if op[s] > 0]
    ex = {r: g(lambda c, r=r: c["lanes"][r]["exact"]) for r in ("o0", "o1", "o2", "o3")}
    ct = {r: g(lambda c, r=r: c["lanes"][r]["contour"]) for r in ("o0", "o1", "o2", "o3")}
    O = {k: g(lambda c, k=k: c["opens"][k]) for k in ("share_ours", "run_ours", "share_human", "run_human", "precision", "recall", "n_ours")}
    OUT["songs"][arm]["opens"] = {"with_open": with_open, **{k: {s: r3(x) for s, x in d.items()} for k, d in O.items()},
                                  "exact": {r: {s: r3(x) for s, x in d.items()} for r, d in ex.items()},
                                  "contour": {r: {s: r3(x) for s, x in d.items()} for r, d in ct.items()}}
    if arm == "m05" or arm == "cpu_m05":
        print(f"\n**{AN[arm]}**: {len(with_open)} songs with opens in our chart: {', '.join(with_open) or 'none'}\n")
        print("| song | open share ours (n, longest run) | humans: share (longest run) each chart | precision@50 | recall@50 | exact o0 / o1 / o2 / o3 | contour o0 / o1 / o2 / o3 |")
        print("|---|---|---|---|---|---|---|")
        for s in with_open:
            A = raw[s]["arms"][arm]["charts"]
            pr = A["primary"]["opens"]
            hc = ", ".join(f"{c['opens']['share_human']:.3f} ({c['opens']['run_human']})" for c in A.values())
            print(f"| {s} | {pr['share_ours']:.3f} ({pr['n_ours']}, {pr['run_ours']}) | {hc} | {f3(O['precision'][s])} | {f3(O['recall'][s])} | "
                  f"{' / '.join(f3(ex[r][s]) for r in ('o0', 'o1', 'o2', 'o3'))} | {' / '.join(f3(ct[r][s]) for r in ('o0', 'o1', 'o2', 'o3'))} |")
    hx, hc_ = {s: hv(s, "exact") for s in SONGS}, {s: hv(s, "contour") for s in SONGS}
    P = {"n_songs_with_opens": len(with_open)}
    for r in ("o1", "o2", "o3"):
        P[r] = {"exact": pool(ex[r], ex["o0"], hx, with_open), "contour": pool(ct[r], ct["o0"], hc_, with_open),
                "exact_all23": pool(ex[r], ex["o0"], hx), "contour_all23": pool(ct[r], ct["o0"], hc_),
                "songs_exact_down": [s for s in with_open if ex[r][s] is not None and ex[r][s] < ex["o0"][s] - 1e-9],
                "songs_contour_down": [s for s in with_open if ct[r][s] is not None and ct[r][s] < ct["o0"][s] - 1e-9]}
    P["precision"], P["recall"] = pool(O["precision"], songs=with_open) if with_open else None, pool(O["recall"], songs=with_open) if with_open else None
    P["share_ours_all23"] = pool(O["share_ours"])
    OUT["pooled"][arm]["opens"] = P
    if with_open:
        table_pooled(f"**{AN[arm]}**, over the {len(with_open)} songs with our opens: exact lanes / contour at 100 ms, each rule minus o0 (today)",
                     [("exact o0", pool(ex["o0"], None, hx, with_open))] +
                     [(f"exact {r}", P[r]["exact"]) for r in ("o1", "o2", "o3")] +
                     [("contour o0", pool(ct["o0"], None, hc_, with_open))] +
                     [(f"contour {r}", P[r]["contour"]) for r in ("o1", "o2", "o3")] +
                     [("open precision@50", P["precision"]), ("open recall@50", P["recall"])])
        for r in ("o1", "o2", "o3"):
            print(f"- {r}: songs with exact lanes down: {P[r]['songs_exact_down'] or 'none'}; contour down: {P[r]['songs_contour_down'] or 'none'}")
    else:
        print(f"\n**{AN[arm]}**: no song has opens in our chart; open share pooled {cell(P['share_ours_all23'])}")

# ---------------- C-e
print("\n## C-e. Same-fret repeats (Expert guitar)")
for arm in ARMS:
    rp = {s: raw[s]["arms"][arm].get("repeats") for s in SONGS}
    hs = raw
    hrep = {s: mean([x["repeat_share"] for x in raw[s]["human_stats"].values()]) for s in SONGS}
    hfr = {s: mean([x["fast_repeat_share"] for x in raw[s]["human_stats"].values()]) for s in SONGS}
    OUT["songs"][arm]["repeats"] = {s: {k: (r3(v) if not isinstance(v, dict) else {n: {a: r3(b) for a, b in d.items()} for n, d in v.items()})
                                        for k, v in (rp[s] or {}).items()} | {"human_repeat_share": r3(hrep[s]), "human_fast_repeat_share": r3(hfr[s])}
                                    for s in SONGS}
    if arm == "m05":
        print("\n| song | repeat share ours / humans | in fast runs ours / humans | repeats | matched@50 repeats / other notes |\n|---|---|---|---|---|")
        for s in SONGS:
            r = rp[s]
            print(f"| {s} | {f3(r['repeat_share'])} / {f3(hrep[s])} | {f3(r['fast_repeat_share'])} / {f3(hfr[s])} | {r['n_repeats']} | {f3(r['match50_repeats'])} / {f3(r['match50_other'])} |")
    names = list(next(iter(rp.values()))["rules"])
    P = {"repeat_share": pool({s: rp[s]["repeat_share"] for s in SONGS}), "human_repeat_share": pool(hrep),
         "fast_repeat_share": pool({s: rp[s]["fast_repeat_share"] for s in SONGS}), "human_fast_repeat_share": pool(hfr),
         "match50_repeats": pool({s: rp[s]["match50_repeats"] for s in SONGS}), "match50_other": pool({s: rp[s]["match50_other"] for s in SONGS}),
         "rules": {}}
    for n in names:
        R = {s: rp[s]["rules"].get(n) for s in SONGS}
        rem = sum(R[s]["removed"] for s in SONGS if R[s])
        prec_pool = sum((R[s]["precision"] or 0) * R[s]["removed"] for s in SONGS if R[s]) / rem if rem else None
        f1c = {s: R[s]["f1_50_change"] for s in SONGS if R[s]}
        hr = {s: R[s]["human_removed_share"] for s in SONGS if R[s]}
        P["rules"][n] = {"removed": rem, "precision_note_pooled": r3(prec_pool),
                         "precision_song_mean": pool({s: R[s]["precision"] for s in SONGS if R[s]})["all"]["mean"],
                         "f1_50_change": boot(list(f1c.values())), "worst_f1_song": [min(f1c, key=f1c.get), r3(min(f1c.values()))],
                         "songs_f1_down_0.005": [s for s, v in f1c.items() if v < -0.005],
                         "max_human_removed": [max(hr, key=hr.get), r3(max(hr.values()))]}
    OUT["pooled"][arm]["repeats"] = P
    print(f"\n**{AN[arm]}**: repeat share ours {cell(P['repeat_share'])}, humans {cell(P['human_repeat_share'])}; in fast runs ours "
          f"{cell(P['fast_repeat_share'])}, humans {cell(P['human_fast_repeat_share'])}; matched@50 repeats {cell(P['match50_repeats'])}, other {cell(P['match50_other'])}")
    print("\n| rule | removed | precision (note-pooled / song mean) | F1@50 change [CI] | worst song | songs down > 0.005 | most human notes removed (song) |\n|---|---|---|---|---|---|---|")
    for n, d in P["rules"].items():
        x = d["f1_50_change"]
        print(f"| {n} | {d['removed']} | {f3(d['precision_note_pooled'])} / {f3(d['precision_song_mean'])} | {x['mean']:+.3f} [{x['lo']:+.3f}, {x['hi']:+.3f}] | "
              f"{d['worst_f1_song'][0]} {d['worst_f1_song'][1]:+.3f} | {len(d['songs_f1_down_0.005'])} | {d['max_human_removed'][0]} {d['max_human_removed'][1]:.3f} |")

# the humans' own agreement, per song
OUT["humans"] = {s: {k: r3(hv(s, k)) for k in ("state", "sus_agree", "f1_50", "exact", "contour")} for s in SONGS}
OUT["checks"] = {"variant_onset_mismatch": {arm: sum(c["variant_onset_mismatch"] for s in SONGS for c in raw[s]["arms"][arm]["charts"].values()) for arm in ARMS}}
print("\nHumans' own agreement (alts against the primary, mean): " + "; ".join(f"{s} state {f3(hv(s, 'state'))} sus {f3(hv(s, 'sus_agree'))} exact {f3(hv(s, 'exact'))} contour {f3(hv(s, 'contour'))}" for s in SONGS if raw[s]["humans"]))
print("\nChecks:", OUT["checks"])


def rd(x):
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, dict): return {k: rd(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [rd(v) for v in x]
    return x


(HERE.parent / ("C.json" if CH == "all" else "C_aligned.json")).write_text(json.dumps(rd(OUT), indent=1))
