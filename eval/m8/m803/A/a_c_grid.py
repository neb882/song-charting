"""a_c_grid.py [labels]: A-c's grid. Per song, in process with the v0.4.0 checkout's beatgrid/assemble functions (M7-09's route, eval/m7/m709/measure.py): the kept folder's
assemble.json and stems (drums, then guitar or other as the second), the first grid (beatgrid.beat_grid), then the octave pass from allin1's beats: halving
(assemble._halving_pass: halving_test, second pass from allin1's beats, the evidence guard) when today's report says octave 1 or 0.5, the doubled route for octave 2
(second_pass, and allin1_start when its tempo check finds a missed change, as assemble._octave_pass; the density test itself does not read allin1 and is taken from
today's report), then beatgrid.with_downbeats on allin1's downbeats. Variants: the whole run (kept segments.json) and each chunked W (A/chunks). Per variant: the octave
decision, the grid's beat F1 and downbeat F1 at 70 ms against each human chart (primary, mean over charts) and against the whole run's grid. Writes A/grid/LABEL.json
(3 decimals); prints one line per song."""
import json, sys, math
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
sys.path[:0] = ["<shm>/m8/code-cpu", str(HERE), str(HERE.parent)]
import common as C
from songs_map import SONGS
from songcharter import assemble as AS, beatgrid as BG, audio as A
from songcharter.errors import InputError
S = C.S; TOL = S.BEAT_TOL
def r3(x):
    if isinstance(x, (float, np.floating)): return round(float(x), 3) if math.isfinite(x) else None
    if isinstance(x, dict): return {k: r3(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [r3(v) for v in x]
    if isinstance(x, np.integer): return int(x)
    return x
def f1(ref, cand, span=None):
    ref, cand = np.sort(ref), np.sort(cand)
    if not len(ref): return None
    pairs = S.match(ref, cand, TOL); nc = S.n_cand_eff(pairs, cand, span) if span else len(cand)
    return S.prf(len(pairs), len(ref), nc)["f1"]
labels = [a for a in sys.argv[1:] if not a.startswith("-")]
if not labels:
    labs = [l for l, *_ in C.songs()]; labels = [l for l in labs if (HERE/"chunks"/f"{l}_W240.json").exists() and (HERE/"chunks"/f"{l}_W120.json").exists() and (HERE/"chunks"/f"{l}_W180.json").exists()]
for lab in labels:
    out = HERE/"grid"/f"{lab}.json"
    if out.exists(): continue
    st, sid = next((s, i) for l, s, i in C.songs() if l == lab)
    rec = C.build(lab, st, sid); P = C.paths(st, sid); osc = C.rj(P["score"]); rep = C.rj(Path(rec["ours_folder"])/"report.json")
    kept = SONGS[lab][1]; cfg = AS.load_config(kept/"assemble.json"); sr = AS.SAMPLE_RATE
    src = "drums"; sd = next(p for p in sorted((kept/"stems").glob("*/")) if (p/"info.json").is_file())
    stems = {n: A.read_wav(sd/f"{n}.wav")[0] for n in cfg.stems if n in ("drums", "guitar", "other")}
    sec = next((n for n in AS.STEMS_FOR["guitar"] if n in stems and n != src), None)
    grid_audio, second_stem = stems[src], stems[sec] if sec else None
    duration = rep["audio"]["duration"]; features = BG.onset_features(grid_audio, sr)
    first = BG.beat_grid(grid_audio, sr, duration=duration, bpm=cfg.bpm, first_beat=cfg.first_beat, mode=cfg.grid_mode, secondary=second_stem, features=features)
    def second_pass(bpm, bpm_range, start=None, half_beat=True, line_test=False):
        return BG.beat_grid(grid_audio, sr, duration=duration, bpm=bpm, mode=cfg.grid_mode, secondary=second_stem, features=features, bpm_range=bpm_range, half_beat=half_beat,
                            keep_line=True, start=start, line_test=line_test)
    today_oct = rep["grid"]["octave"]; rules = AS.OCTAVE_RULES; lo, hi = BG.BPM_RANGE
    T = rep["lead_in"]["pad_seconds"] + osc["alignment"]["cand_total_shift_ms"]/1000.0
    hum = {}
    for k, h in rec["humans"].items():
        if not h.get("tempos"): continue
        sp = [o[0] for p in h["parts"].values() for o in p["onsets"]]
        if not sp: continue
        span = tuple(osc["ref_span_s"]) if k == "primary" else (min(sp)-0.1, max(sp)+0.1)
        sc = {"resolution": h["res"], "tempos": h["tempos"], "timeSignatures": h["timeSignatures"]}
        hum[k] = dict(span=span, beats=S.beat_times(sc, span[0], span[1], h["shift_ms"]), down=S.downbeat_times(sc, span[0], span[1], h["shift_ms"]))
    variants = {}
    kj = json.loads((kept/"sections/segments.json").read_text()); variants["whole"] = kj
    for W in (120, 180, 240):
        f = HERE/"chunks"/f"{lab}_W{W}.json"
        if f.exists(): variants[f"W{W}"] = json.loads(f.read_text())
    res = {"label": lab, "today_octave_report": today_oct, "first_bpm": first.bpm, "variants": {}}; grids = {}
    for name, v in variants.items():
        beats = np.asarray(v["beats"]); dbs = np.asarray(v["downbeats"]); info = {}
        if today_oct in (1, 0.5):
            stats = {"reason": "m8-03"}
            g, octv, stats, reason, warn = AS._halving_pass(first, stats, second_pass, beats, duration, rules)
            h = stats["halving"]; info = {"halve_test": bool(h["halve"]), "allin1_bpm": h.get("allin1_bpm"), "rate_ratio": h.get("rate_ratio"), "kept": h.get("kept"), "evidence_ratio": h.get("evidence_ratio")}
        else:
            second = second_pass(2*first.stats["click"]["bpm"], (2*lo, 2*hi)); octv = 2; src2 = "line"; g = second
            missed = second.stats.get("tempo_check") or []
            if missed:
                start, record = AS.allin1_start(beats, second.bpm, duration)
                if start is not None:
                    try: g = second_pass(2*first.stats["click"]["bpm"], (2*lo, 2*hi), start=start); src2 = "allin1"
                    except InputError: pass
            s1 = first.stats["evidence"]["confident_share"]; s2 = g.stats["evidence"]["confident_share"]
            if not (s1 > 0 and s2/s1 >= rules.evidence_min): g, octv = first, 1
            info = {"second_start": src2, "missed_windows": len(missed)}
        g = BG.with_downbeats(g, dbs)
        grids[name] = g; bt = g.beats + T; dt = g.beats[g.downbeats] + T
        m = {"octave": octv, "n_beats": int(len(g.beats)), "bpm": g.bpm, **info}
        m["beat_f1"] = {k: f1(h["beats"], bt[(bt >= h["span"][0]-TOL) & (bt <= h["span"][1]+TOL)], h["span"]) for k, h in hum.items()}
        m["downbeat_f1"] = {k: f1(h["down"], dt[(dt >= h["span"][0]-TOL) & (dt <= h["span"][1]+TOL)], h["span"]) for k, h in hum.items()}
        m["beat_f1_humans_mean"] = float(np.mean([x for x in m["beat_f1"].values() if x is not None])) if hum else None
        m["downbeat_f1_humans_mean"] = float(np.mean([x for x in m["downbeat_f1"].values() if x is not None])) if hum else None
        res["variants"][name] = m
        print(lab, name, "oct", octv, info, "beatF1h", m["beat_f1_humans_mean"] and round(m["beat_f1_humans_mean"], 3), "dbF1h", m["downbeat_f1_humans_mean"] and round(m["downbeat_f1_humans_mean"], 3), flush=True)
    w = grids["whole"]
    for name, g in grids.items():
        m = res["variants"][name]
        m["grid_beat_f1_vs_whole"] = f1(w.beats, g.beats); m["grid_downbeat_f1_vs_whole"] = f1(w.beats[w.downbeats], g.beats[g.downbeats])
        m["octave_same_as_whole"] = m["octave"] == res["variants"]["whole"]["octave"]
    # calibration: the whole variant's octave against today's report
    res["whole_octave_matches_report"] = res["variants"]["whole"]["octave"] == today_oct
    json.dump(r3(res), open(out, "w"), indent=1)
