"""p2_drift.py: part 2, drift or another edit. Reads a_align.py's per-window lags (score.py's align: 9 windows, and the
same function with 40) for two pairs per chart: ours (our song folder's mix against the chart's input.wav: the lag
part D used) and hum (an alternative chart's input.wav against the primary's: the humans' agreement). Per pair: a
Theil-Sen line lag = a + b*t through the windows with ncc >= 0.3 (40-window run), the residuals, and a class:
  constant: >= 80 % of the good windows within 20 ms of the line and the line moves < 20 ms over the span;
  drift:    the same fit, the line moving >= 20 ms over the span (slope in ppm);
  edit:     the good windows form 2 or more steps (lags constant within 20 ms in contiguous runs of >= 2 windows,
            covering >= 80 % of them), or >= 6 good windows scatter (neither a line nor steps);
  unclear:  fewer than 4 good windows (the audio does not match well enough to tell), or 4-5 that fit neither.
Then F1@50 (score.py's match/prf/n_cand_eff, Expert guitar) with the constant lag and with the lag line for the drift
pairs: our GPU m05 chart (part B) against each chart, part D's rate8 recall@100 again, and the humans' agreement
(alternative against primary) on every song. Writes <shm>/ceiling/p2.json (labels and numbers only)."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cl
from cl import S

TOL_MS, MIN_GOOD = 20.0, 4   # 20 ms: well-aligned charts jitter +-7-17 ms window to window (ncc side peaks)


def theil_sen(t, y):
    sl = [(y[j] - y[i]) / (t[j] - t[i]) for i in range(len(t)) for j in range(i + 1, len(t)) if t[j] != t[i]]
    b = float(np.median(sl)) if sl else 0.0
    return float(np.median(y - b * t)), b


def steps(t, y):
    """Contiguous runs (in time order) of lags within TOL_MS of the run's median; the share in runs of >= 2."""
    o = np.argsort(t); y = y[o]
    runs, cur = [], [y[0]]
    for v in y[1:]:
        if abs(v - np.median(cur)) <= TOL_MS: cur.append(v)
        else: runs.append(cur); cur = [v]
    runs.append(cur)
    big = [r for r in runs if len(r) >= 2]
    levels = []
    for r in big:
        m = float(np.median(r))
        if not levels or abs(m - levels[-1]) > TOL_MS: levels.append(m)
    return len(levels), sum(len(r) for r in big) / len(y), levels


def classify(al, span):
    w = [x for x in al["windows"] if x["peak_ncc"] >= 0.3]
    out = {"n_windows": len(al["windows"]), "n_good": len(w), "lag_ms": al["lag_ms"], "mad_ms": al["lag_mad_ms"]}
    if len(w) < 2:
        return {**out, "class": "unclear", "why": "under 2 good windows"}
    t = np.array([x["ref_time_s"] + 0.5 for x in w]); y = np.array([x["lag_ms"] for x in w])
    a, b = theil_sen(t, y)
    res = y - (a + b * t)
    within = float(np.mean(np.abs(res) <= TOL_MS))
    move = abs(b) * (span[1] - span[0])
    nlev, cover, levels = steps(t, y)
    out.update(a_ms=a, ppm=b * 1e3, move_ms=move, line_within=within, resid_mad_ms=float(np.median(np.abs(res))),
               step_levels=nlev, step_cover=cover, step_jumps_ms=[levels[i + 1] - levels[i] for i in range(len(levels) - 1)])
    if len(w) < MIN_GOOD:
        out["class"], out["why"] = "unclear", f"{len(w)} good windows"
    elif within >= 0.8:
        out["class"], out["why"] = ("drift", "a line") if move >= TOL_MS else ("constant", "flat")
    elif nlev >= 2 and cover >= 0.8:
        out["class"], out["why"] = "edit", f"{nlev} steps"
    elif len(w) >= 6:
        out["class"], out["why"] = "edit", "scatter"
    else:
        out["class"], out["why"] = "unclear", "4-5 good windows, neither line nor steps"
    return out


def to_ref(u, a_ms, b):
    """cand time u (s) -> ref time t, for lag(t) = a + b*t (ms, b per ms of ms): u = t + lag(t)."""
    return (np.asarray(u) - a_ms / 1000.0) / (1.0 + b)


def f1_50(rt, ct, span):
    lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
    ct = np.sort(ct[(ct >= lo) & (ct <= hi)])
    p = S.match(rt, ct, 0.050)
    return S.prf(len(p), len(rt), S.n_cand_eff(p, ct, span))["f1"]


def rate8(rt, ct, span):
    lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
    ct = np.sort(ct[(ct >= lo) & (ct <= hi)])
    p = S.match(rt, ct, 0.100)
    ws = S.window_scores(rt, ct, p, span, 30.0)["windows"]
    f = []
    for w in ws:
        ln = max(min(w["start_s"] + 30.0, span[1]) - w["start_s"], 1e-6)
        if w["n_ref"] / ln >= 8.0: f.append(w)
    return (sum(w["n_ref"] for w in f), sum(w["matched"] for w in f), sum(w["n_cand"] for w in f)) if f else None


def onset_t(notes, shift_ms):
    return np.array([o["t"] for o in S.onsets(notes, shift_ms, "guitar")])


def main():
    AL = json.loads((cl.SHM / "align.json").read_text())
    res = {}
    for label in cl.LABELS:
        ours_sc = cl.scan(cl.m05_folder(label))
        cdel, _ = S.chart_delay_ms(ours_sc)
        on = cl.gtrack(ours_sc)
        u_ours = onset_t(on, cdel)               # our song folder's time
        cs = cl.charts(label)
        prim = cs[0]
        psc = cl.scan(prim[1] / "ref"); pdel, pspan = cl.ref_span(psc)
        pnotes = cl.gtrack(psc)
        row = {}
        for k, folder in cs:
            A = AL[label][k]; span = A["span"]
            e = {"ours9": classify(A["ours9"], span), "ours40": classify(A["ours40"], span)}
            rsc = cl.scan(folder / "ref"); notes = cl.gtrack(rsc)
            c40 = e["ours40"]
            if notes:
                rt = onset_t(notes, A["ref_delay_ms"])
                lag = A["ours9"]["lag_ms"]
                ct_c = u_ours - lag / 1000.0
                e["f1_50_const"] = f1_50(rt, ct_c, span)
                e["rate8_const"] = rate8(rt, ct_c, span)
                if c40["class"] == "drift":
                    ct_l = to_ref(u_ours, c40["a_ms"], c40["ppm"] / 1e6)
                    e["f1_50_line"] = f1_50(rt, ct_l, span)
                    e["rate8_line"] = rate8(rt, ct_l, span)
            if k != "primary":
                h9, h40 = classify(A["hum9"], pspan), classify(A["hum40"], pspan)
                e["hum9"], e["hum40"] = h9, h40
                if notes and pnotes:
                    prt = onset_t(pnotes, pdel)
                    adel, _ = S.chart_delay_ms(rsc)
                    u = onset_t(notes, adel)                     # the alt's input.wav time
                    e["hum_f1_50_const"] = f1_50(prt, u - A["hum9"]["lag_ms"] / 1000.0, pspan)
                    if h40["class"] == "drift":
                        e["hum_f1_50_line"] = f1_50(prt, to_ref(u, h40["a_ms"], h40["ppm"] / 1e6), pspan)
            row[k] = e
        res[label] = row
        print(label, {k: (v["ours40"]["class"], v.get("hum40", {}).get("class")) for k, v in row.items()}, flush=True)
    (cl.SHM / "p2.json").write_text(json.dumps(res, default=float))


if __name__ == "__main__":
    main()
