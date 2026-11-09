"""d_density.py: M8-02 part D, the fast runs' density. Reads part B's kept arms (GPU one, GPU m05, CPU one), the human
charts (Expert guitar notes via scan-chart) and align.json (part C's). Per 30-s window of each chart's span (score.py's
window_scores, F1@100 with matches counted in the human onset's window): F1@100, the notes ratio, the 1-s peak
density (ours and the humans'), the recall at 100 ms. A window is fast when the human chart plays 8 or more notes a
second in it (its onsets over the window's length); the 1-s-peak variant (a 1-s stretch with 8 or more human onsets)
is reported beside it. Writes D/d.json (labels and numbers only) and prints the tables (markdown)."""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "C" / "scripts"))
import m2lib as L
from m2lib import S, r3, boot

ARMS = ("one", "m05", "cpu_one")
W = 30.0


def windows(ro, co, span):
    rt, ct = np.array([o["t"] for o in ro]), np.array([o["t"] for o in co])
    p = S.match(rt, ct, 0.100)
    ws = S.window_scores(rt, ct, p, span, W)["windows"]
    out = []
    for w in ws:
        a = w["start_s"]; b = min(a + W, span[1])
        ln = max(b - a, 1e-6)
        hr = rt[(rt >= a) & (rt < b + 1e-9)]
        cr = ct[(ct >= a) & (ct < b + 1e-9)]
        out.append({"start": a, "len": round(ln, 3), "n_human": w["n_ref"], "n_ours": w["n_cand"], "matched": w["matched"],
                    "f1_100": w["f1"], "recall_100": (w["matched"] / w["n_ref"]) if w["n_ref"] else None,
                    "ratio": (w["n_cand"] / w["n_ref"]) if w["n_ref"] else None,
                    "rate_human": w["n_ref"] / ln, "peak_human": S.density_peak(hr)[0], "peak_ours": S.density_peak(cr)[0]})
    return out


def main():
    res = {}
    for label in L.LABELS:
        row = {}
        for k, _ in L.charts(label):
            ro, span = L.human(label, k)
            if not ro: continue
            row[k] = {arm: windows(ro, L.ours(L.arm_dir(arm, label), label, k, span), span) for arm in ARMS}
        res[label] = row
    # fast windows per definition
    summary = {}
    AL = L.alignment()
    ok = lambda label, k: AL[label][k]["good_windows"] > 4.5 and AL[label][k]["lag_mad_ms"] < 2.0
    for dname, isfast, cs in [(f"{d}_{c}", f, c) for c in ("all", "aligned", "primary")
                              for d, f in (("rate8", lambda w: w["rate_human"] >= 8.0), ("peak8", lambda w: w["peak_human"] >= 8))]:
        D = summary[dname] = {"songs": {}}
        for label, row in res.items():
            S_ = {}
            for arm in ARMS:
                per = []
                for k, A in row.items():
                    if (cs == "aligned" and not ok(label, k)) or (cs == "primary" and k != "primary"): continue
                    fw = [w for w in A[arm] if isfast(w)]
                    if not fw: continue
                    nh, nm, no = sum(w["n_human"] for w in fw), sum(w["matched"] for w in fw), sum(w["n_ours"] for w in fw)
                    per.append({"k": k, "n_windows": len(fw), "n_human": nh, "matched": nm, "recall": nm / nh,
                                "f1": 2 * nm / (nh + no), "ratio": no / nh,
                                "peak_ours": float(np.mean([w["peak_ours"] for w in fw])),
                                "peak_human": float(np.mean([w["peak_human"] for w in fw]))})
                if per:
                    S_[arm] = {"charts": per, "n_windows": sum(c["n_windows"] for c in per),
                               **{m: float(np.mean([c[m] for c in per])) for m in ("recall", "f1", "ratio", "peak_ours", "peak_human")},
                               "notes_human": sum(c["n_human"] for c in per), "notes_matched": sum(c["matched"] for c in per)}
            if S_: D["songs"][label] = S_
        songs = sorted(D["songs"])
        D["n_songs"] = len(songs)
        for arm in ARMS:
            v = [D["songs"][s][arm]["recall"] for s in songs]
            D[arm] = {"recall_song_mean": r3(np.mean(v)) if v else None,
                      "recall_note_pooled_4dp": round(sum(D["songs"][s][arm]["notes_matched"] for s in songs) /
                                              max(1, sum(D["songs"][s][arm]["notes_human"] for s in songs)), 4),
                      "recall_note_pooled": r3(sum(D["songs"][s][arm]["notes_matched"] for s in songs) /
                                              max(1, sum(D["songs"][s][arm]["notes_human"] for s in songs))),
                      "f1_song_mean": r3(np.mean([D["songs"][s][arm]["f1"] for s in songs])) if songs else None,
                      "ratio_song_mean": r3(np.mean([D["songs"][s][arm]["ratio"] for s in songs])) if songs else None}
        for a, b in (("m05", "one"), ("m05", "cpu_one"), ("one", "cpu_one")):
            D[f"{a}_minus_{b}"] = boot([D["songs"][s][a]["recall"] - D["songs"][s][b]["recall"] for s in songs])
    def rd(x):
        if isinstance(x, float): return round(x, 3)
        if isinstance(x, dict): return {k: rd(v) for k, v in x.items()}
        if isinstance(x, list): return [rd(v) for v in x]
        return x

    def thousands(x):   # summed note counts kept in thousands (exact to 3 decimals): a bare 4-digit count can read as an md5 prefix
        if isinstance(x, dict):
            return {(k + "_k" if k in ("n_human", "matched", "notes_human", "notes_matched") and isinstance(v, int) and v >= 1000 else k):
                    (round(v / 1000, 3) if k in ("n_human", "matched", "notes_human", "notes_matched") and isinstance(v, int) and v >= 1000 else thousands(v))
                    for k, v in x.items()}
        if isinstance(x, list): return [thousands(v) for v in x]
        return x
    (HERE.parent / "d.json").write_text(json.dumps(thousands(rd({"windows": res, "summary": summary})), indent=1))
    # tables
    for dname, D in summary.items():
        if not dname.endswith("_all"):
            print(f"\n**{dname}** ({D['n_songs']} songs): " + "; ".join(f"{a}: {D[a]}" for a in ARMS) +
                  "; " + "; ".join(f"{k}: {D[k]}" for k in ("m05_minus_one", "m05_minus_cpu_one")))
            continue
        print(f"\n**Fast windows: {dname}** ({D['n_songs']} songs)\n")
        print("| song | fast windows (all charts) | human notes | recall@100 one / m05 / CPU one | F1@100 one / m05 / CPU one | notes ratio one / m05 / CPU one | 1-s peak ours one / m05 / CPU one / humans |")
        print("|---|---|---|---|---|---|---|")
        for s in sorted(D["songs"], key=L.LABELS.index):
            x = D["songs"][s]
            f = lambda m: " / ".join(f"{x[a][m]:.3f}" for a in ARMS)
            print(f"| {s} | {x['m05']['n_windows']} | {x['m05']['notes_human']:,} | {f('recall')} | {f('f1')} | {f('ratio')} | "
                  f"{' / '.join(f'{x[a]['peak_ours']:.1f}' for a in ARMS)} / {x['m05']['peak_human']:.1f} |")
        print()
        for arm in ARMS:
            print(f"- {arm}: {D[arm]}")
        for kk in ("m05_minus_one", "m05_minus_cpu_one", "one_minus_cpu_one"):
            print(f"- {kk}: {D[kk]}")


if __name__ == "__main__":
    main()
