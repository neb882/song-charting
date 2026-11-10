"""lib.py: M8-11's shared loader and metrics. Reads the human charts of the stress set's sooth (primary, and alt1 for a
side line) only through main's eval/scorer/score.py scan (scan-chart), and a candidate chart folder. Metrics follow
M8-02 part D (eval/m8/m802/D/scripts/d_density.py): 30-s windows over the human chart's span (score.py's
window_scores, matches at 100 ms counted in the human onset's window); a window is fast when the human chart plays 8 or
more notes a second over it ("rate8"). Prints nothing."""
import json, os, sys
from pathlib import Path
import numpy as np

W811 = Path(__file__).resolve().parent.parent
CODE = W811 / "code"                    # git archive of main (cac4c2b): songcharter/ and eval/
sys.path.insert(0, str(CODE))
os.environ.setdefault("SONGCHARTER_SCAN_CHART", "<checkout>/tools/scan-chart/scan.cjs")
from eval import stress as ST          # noqa: E402
from eval.scorer import score as S     # noqa: E402

REFS = Path(os.environ.get("EVAL_DATA", "$DEV/eval")) / "stress"
WIN = 30.0
FAST = 8.0
ARMS = ("base", "hot", "dense5", "dense6")
SEEDS = (20260609, 101, 202, 303)
TAKES = W811 / "data" / "sooth"


def song():
    return next(s for s in ST.built_songs(REFS) if s["id"] == "sooth")


def charts():
    s = song()
    return [("primary", Path(s["folder"]))] + [(a["label"], Path(a["folder"])) for a in s.get("alts") or []
                                               if ST.scorable(Path(a["folder"]))]


def gtrack(sc):
    for t in sc.get("tracks") or []:
        if t["instrument"] == "guitar" and t["difficulty"] == "expert" and t["notes"]:
            return t["notes"]
    return []


def human(folder):
    """Expert guitar onsets of a human chart in its input.wav's frame, and the span over all its tracks (score.py)."""
    sc = S.scan(str(folder / "ref"))
    rdel, _ = S.chart_delay_ms(sc)
    starts, ends = [], []
    for (ins, dif), notes in S.tracks_by_key(sc).items():
        starts.append(min(n["ms"] for n in notes)); ends.append(max(n["ms"] + (n.get("msLength") or 0) for n in notes))
    span = ((min(starts) + rdel) / 1000.0, (max(ends) + rdel) / 1000.0)
    return S.onsets(gtrack(sc), rdel, "guitar"), span


def cand(folder, lag_ms, span):
    sc = S.scan(str(folder))
    cdel, _ = S.chart_delay_ms(sc)
    ons = S.onsets(gtrack(sc), cdel - lag_ms, "guitar")
    lo, hi = span[0] - S.SPAN_MARGIN, span[1] + S.SPAN_MARGIN
    return [o for o in ons if lo <= o["t"] <= hi], sc


def chordy(o):
    return len(set(o["lanes"])) > 1


def score(ro, co, span):
    """Per window and aggregated: fast / other / song (recall@100, F1@100, notes ratio, 1-s peaks, chord share)."""
    rt, ct = np.array([o["t"] for o in ro]), np.array([o["t"] for o in co])
    p = S.match(rt, ct, 0.100)
    ws = S.window_scores(rt, ct, p, span, WIN)["windows"]
    wins = []
    for w in ws:
        a = w["start_s"]; b = min(a + WIN, span[1]); ln = max(b - a, 1e-6)
        hr = rt[(rt >= a) & (rt < b + 1e-9)]; cr = ct[(ct >= a) & (ct < b + 1e-9)]
        hc = [o for o in ro if a <= o["t"] < b + 1e-9]; cc = [o for o in co if a <= o["t"] < b + 1e-9]
        wins.append({"start": a, "len": round(ln, 3), "n_h": w["n_ref"], "n_c": w["n_cand"], "m": w["matched"],
                     "f1": w["f1"], "rate_h": w["n_ref"] / ln, "fast": w["n_ref"] / ln >= FAST,
                     "peak_h": S.density_peak(hr)[0], "peak_c": S.density_peak(cr)[0],
                     "ch_h": sum(map(chordy, hc)), "ch_c": sum(map(chordy, cc))})

    def agg(sel):
        nh = sum(w["n_h"] for w in sel); nc = sum(w["n_c"] for w in sel); m = sum(w["m"] for w in sel)
        if not nh:
            return None
        return {"windows": len(sel), "n_h": nh, "n_c": nc, "m": m, "recall": m / nh, "f1": 2 * m / (nh + nc),
                "ratio": nc / nh, "peak_c": float(np.mean([w["peak_c"] for w in sel])),
                "peak_h": float(np.mean([w["peak_h"] for w in sel])),
                "chord_c": sum(w["ch_c"] for w in sel) / max(1, nc), "chord_h": sum(w["ch_h"] for w in sel) / nh}
    out = {"windows": wins, "fast": agg([w for w in wins if w["fast"]]), "other": agg([w for w in wins if not w["fast"]]),
           "song": agg(wins)}
    out["song"]["peak1s_c"] = S.density_peak(ct[(ct >= span[0]) & (ct <= span[1])])[0]
    out["song"]["peak1s_h"] = S.density_peak(rt)[0]
    # score.py's own song F1@100 (n_cand_eff), as a check on the window sums
    out["song"]["f1_scorepy"] = S.prf(len(p), len(rt), S.n_cand_eff(p, ct, span))["f1"]
    out["song"]["f1_50"] = S.prf(len(S.match(rt, ct, 0.05)), len(rt), S.n_cand_eff(S.match(rt, ct, 0.05), ct, span))["f1"]
    return out


def summary(take_dir):
    d = json.loads((take_dir / "autochart_run" / "summary.json").read_text())
    r = d["runs"][0]
    return {"seed": d["seed"], "T": d["temperature"], "speed": d["knobs"]["speed"], "tokens": r["nTokens"],
            "gen_s": r["generationSeconds"], "wall_s": r["wallSeconds"], "transcriber": r["devices"]["transcriber"],
            "cached": r["cachedStages"], "input_sha_ok": None, "duration": r["audioDuration"], "inputSha256": d["inputSha256"]}
