"""c_starpower.py: Part C. Reads (through ../common.py) the v0.4.0 gate's charts (v040, v040-stress, v040-set20: notes.chart Expert guitar, its tempo map, its
section lines) and every human chart's guitar Expert (scan-chart parse: notes, star power phrases) with the alignment shifts as M7-01 B used. In process with
songcharter/starpower.py's own place_star_power (v0.4.0 checkout) on those notes and tempo map: today's rule, then the span counted at least at B BPM (B 100,
120: counted = min(max(span beats, span s x B/60), span s x 160/60), passed as `count`). Per song: phrases a minute (over the span of the Expert notes, as
score.phrase_rates) and the share of Expert onsets inside a phrase, for ours (today, B100, B120) and each human chart; the average BPM of the span; our phrase
notes inside a human phrase (mean over charts). Checks that our reproduction of today's placement equals the chart's own star power (count and tick match)
and, for songs not slow, that B=100 changes nothing (asserted). Writes C/c_result.json (3 decimals); prints one line per song."""
import json, sys, re
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent.parent))
import common as C
from songcharter import starpower as SP
from songcharter.chart import FretNote, Track, Chart
from songcharter.tempo import TempoMap, Tempo, TimeSignature
SLOW = {"creep", "lucretia", "sooth", "s02", "s04", "s13"}
HERE = Path(__file__).parent
def r3(x):
    if isinstance(x, float): return round(x, 3)
    if isinstance(x, dict): return {k: r3(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [r3(v) for v in x]
    return x
def tmap(rec):
    tempos = [Tempo(int(t["tick"]), int(round(t["beatsPerMinute"]*1000))) for t in rec["tempos"]]
    ts = [TimeSignature(int(t["tick"]), int(t["numerator"]), int(t["denominator"])) for t in rec["timeSignatures"]] or [TimeSignature(0, 4)]
    return TempoMap(int(rec["res"]), tempos, ts)
def sections(folder):
    out = []
    for l in open(Path(folder)/"notes.chart", encoding="utf-8"):
        m = re.match(r'\s*(\d+) = E "section ', l)
        if m: out.append(int(m.group(1)))
    return out
def phrases_for(rec, tm, secs, B):
    notes = [FretNote(o[3], tuple(o[1]) if o[1] != [-1] else (7,), int(o[5])) for o in rec["onsets"]]
    tr = Track("Expert", "Single", notes)
    onsets = sorted({n.tick for n in notes})
    beats = (onsets[-1]-onsets[0])/tm.resolution; seconds = tm.tick_to_sec(onsets[-1])-tm.tick_to_sec(onsets[0])
    k0 = round(min(beats, seconds*160/60)/40)
    if B is None:
        k = None; ph = SP.place_star_power(tr, tm, secs)
    else:
        counted = min(max(beats, seconds*B/60), seconds*160/60); k = round(counted/40)
        ph = SP.place_star_power(tr, tm, secs, count=k)
    return ph, dict(k_today=k0, k=k, span_s=seconds, span_beats=beats, avg_bpm=beats/seconds*60)
def inside(onset_ms, spans_ms):
    t = np.asarray(onset_ms); m = np.zeros(len(t), bool)
    for a, b in spans_ms: m |= (t >= a-1e-6) & (t < b-1e-6)
    return m
def rate(spans, notes_ms_len):
    a = min(n[0] for n in notes_ms_len); b = max(n[0]+n[1] for n in notes_ms_len)
    return len(spans)/((b-a)/60.0)   # spans in s, notes in s
res = {}
for lab, st, sid in C.songs()+[("test_song", "test", None)]:
    rec = C.build(lab, st, sid) if sid else C.build_test()
    og = rec["ours"]["parts"].get("guitar")
    if not og: continue
    tm = tmap(rec["ours"]); secs = sections(rec["ours_folder"]); shift = rec["ours"]["shift_ms"]/1000
    ons = og["onsets"]; ours_t = np.array([o[0] for o in ons])           # s, input timeline
    off = np.median([o[4]/1000 - tm.tick_to_sec(o[3]) for o in ons])      # scan ms vs map: constant
    notes_len = [(o[0], o[2]) for o in ons]
    out = {"slow": lab in SLOW, "notes": len(ons)}
    humans = {k: h for k, h in rec["humans"].items() if "guitar" in h["parts"] and h["parts"]["guitar"]["sp"]}
    def to_spans(ph): return [(tm.tick_to_sec(p.tick)+off+shift, tm.tick_to_sec(p.tick+p.length)+off+shift) for p in ph]
    ph0, info = phrases_for(og, tm, secs, None)
    # reproduction check against the chart's own star power
    chart_sp = sorted(x[2] for x in og["sp"]); mine = sorted(p.tick for p in ph0)
    out["repro"] = {"chart": len(chart_sp), "mine": len(mine), "same_ticks": chart_sp == mine}
    out["span"] = {k: v for k, v in info.items()}
    hum = {}
    for k, h in humans.items():
        g = h["parts"]["guitar"]; hs = [(x[0], x[1]) for x in g["sp"]]
        hn = [(o[0], o[2]) for o in g["onsets"]]; ht = np.array([o[0] for o in g["onsets"]])
        hum[k] = {"phrases": len(hs), "rate": rate(hs, hn), "share_in_phrase": float(inside(ht, hs).mean()), "spans": hs}
    out["humans"] = {k: {a: b for a, b in v.items() if a != "spans"} for k, v in hum.items()}
    out["human_rate_range"] = [min(v["rate"] for v in hum.values()), max(v["rate"] for v in hum.values())] if hum else None
    variants = {"today": ph0}
    for B in (100, 120): variants[f"B{B}"] = phrases_for(og, tm, secs, B)[0]
    out["ours"] = {}
    for name, ph in variants.items():
        sp = to_spans(ph); m = inside(ours_t, sp)
        d = {"phrases": len(ph), "rate": len(ph)/((max(a+b for a, b in notes_len)-min(a for a, _ in notes_len))/60.0), "share_in_phrase": float(m.mean()),
             "ticks": [p.tick for p in ph]}
        if hum:
            pn = ours_t[m]
            d["notes_in_phrases"] = int(m.sum())
            d["overlap_with_humans"] = float(np.mean([inside(pn, h["spans"]).mean() for h in hum.values()])) if len(pn) else None
            d["overlap_counts"] = [int(inside(pn, h["spans"]).sum()) for h in hum.values()]
        out["ours"][name] = d
    for B in ("B100", "B120"):
        out["ours"][B]["changed_vs_today"] = out["ours"][B]["ticks"] != out["ours"]["today"]["ticks"]
    if lab not in SLOW:
        assert not out["ours"]["B100"]["changed_vs_today"], f"{lab}: B100 changed a not-slow song (avg bpm {info['avg_bpm']:.1f})"
    res[lab] = out
    print(lab, "slow" if lab in SLOW else "", "bpm %.1f" % info["avg_bpm"], "repro", out["repro"], {n: (v["phrases"], round(v["rate"], 2)) for n, v in out["ours"].items()},
          "hum", out["human_rate_range"] and [round(x, 2) for x in out["human_rate_range"]], flush=True)
for v in res.values():
    for d in v["ours"].values(): d.pop("ticks", None)
json.dump(r3(res), open(HERE/"c_result.json", "w"), indent=1)
