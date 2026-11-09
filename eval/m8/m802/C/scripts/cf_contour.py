"""cf_contour.py ARM [pitch|analyze]: M8-02 C-f, the contour spike (main's eval/m8/contour: pitch.py's trackers and
analyze.py's song_rows, imported read-only) on an arm's charts (GPU m05 by default). 'pitch' runs pYIN, a CQT peak and
a harmonic-summed CQT peak at our Expert guitar onsets in fast runs on the kept guitar stem and writes
<shm>/m8/m2/pitch/<arm>/<label>.json; 'analyze' measures the direction agreement (ours, each tracker, pyin_step1)
on fast-run pairs matched at 50 ms to consecutive human notes, the re-lane by each (one lane per step, clamped) and
score.py's whole-song contour and exact lanes before and after, and writes C/cf_<arm>.json (labels and numbers only).
Prints one line per song."""
import json, os, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import m2lib as L
sys.path.insert(0, "<shm>/m8/code/eval/scorer")
sys.path.insert(0, "<wt>/orch/eval/m8/contour")
import clib, pitch, analyze as AN  # noqa: E402  (main's spike scripts, read only)
from m2lib import r3, boot

arm, what = sys.argv[1], sys.argv[2]
PD = L.SHM / "pitch" / arm


def song(label):
    A = L.alignment()[label]
    ro, span = L.human(label, "primary")
    co = L.ours(L.arm_dir(arm, label), label, "primary", span)
    humans = [{"k": "primary", "ons": ro}]
    for k, _ in L.charts(label)[1:]:
        ho = L.human_as_cand(label, k)
        if ho: humans.append({"k": k, "ons": ho})
    wav, kind = clib.stem(str(L.SONGS[label][2]))
    m = L.S.track_metrics(ro, co, "guitar", span, False, False)
    return {"label": label, "set": L.SONGS[label][0], "ours": co, "span": span, "humans": humans, "stem": wav,
            "stem_kind": kind, "score_py": {"contour": m["lane_direction_agreement"]["value"],
                                            "exact": m["exact_lane_agreement"]["value"], "f1_50": m["onset_50ms"]["f1"]}}


if what == "pitch":
    PD.mkdir(parents=True, exist_ok=True)
    for label in L.LABELS:
        p = PD / f"{label}.json"
        if p.exists(): continue
        s = song(label)
        t = np.array([o["t"] for o in s["ours"]])
        if (clib.fast_runs(t) < 0).all() or not s["stem"]:
            print(label, "no fast run", flush=True); continue
        t0 = time.time()
        r = pitch.song(s)
        p.write_text(json.dumps(r))
        print(label, len(r["idx"]), round(time.time() - t0, 1), flush=True)
else:
    rows = []
    for label in L.LABELS:
        p = PD / f"{label}.json"
        if not p.exists(): continue
        r = AN.song_rows(song(label), json.loads(p.read_text()))
        if r["charts"][0]["n_pairs"]:
            rows.append(r)
        print(label, r["n_fast_onsets"], r["charts"][0]["n_pairs"], flush=True)
    pooled = {}
    for scope, get in (("primary", lambda r, f: f(r["charts"][0])), ("all_charts", AN.mean_over_charts)):
        P = pooled[scope] = {}
        base = [get(r, lambda c: c.get("agree_ours")) for r in rows]
        P["ours"], P["n_songs"] = r3(np.mean(base)), len(rows)
        for v in AN.VARIANTS:
            vals = [get(r, lambda c, v=v: c.get("agree_" + v)) for r in rows]
            P["agree_" + v] = {"mean": r3(np.mean(vals)), "vs_ours": boot([a - b for a, b in zip(vals, base)]),
                               "songs_up_0.10": sum(a - b >= 0.10 for a, b in zip(vals, base))}
            st = [get(r, lambda c, v=v: c["sub_" + v]["tracker"]) for r in rows]
            so = [get(r, lambda c, v=v: c["sub_" + v]["ours"]) for r in rows]
            ok = [(a, b) for a, b in zip(st, so) if a is not None and b is not None]
            P["sub_" + v] = {"n_songs": len(ok), "tracker": r3(np.mean([a for a, _ in ok])) if ok else None,
                             "ours": r3(np.mean([b for _, b in ok])) if ok else None, "diff": boot([a - b for a, b in ok])}
            R = {}
            for m in ("contour_fast50", "contour100", "exact100", "exact_fast50", "f1_50"):
                b0 = [get(r, lambda c, m=m: c["today"][m]) for r in rows]
                b1 = [get(r, lambda c, m=m, v=v: c["relane"][v][m]) for r in rows]
                ok = [(a, b) for a, b in zip(b1, b0) if a is not None and b is not None]
                R[m] = {"today": r3(np.mean([b for _, b in ok])), "relane": r3(np.mean([a for a, _ in ok])),
                        "diff": boot([a - b for a, b in ok]), "worst_song_diff": r3(min(a - b for a, b in ok))}
            P["relane_" + v] = R
        ce = [r["ceiling_mean"] for r in rows if r["ceiling_mean"] is not None]
        P["ceiling"] = {"mean": r3(np.mean(ce)) if ce else None, "n_songs": len(ce)}
    out = HERE.parent / f"cf_{arm}.json"
    out.write_text(json.dumps({"arm": arm, "rows": rows, "pooled": pooled}, indent=1))
    print("wrote", out.name)
