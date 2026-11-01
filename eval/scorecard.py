"""Summarize every score in <data>/runs/<tool>/<song>.score.json as markdown tables.

usage: python -I scorecard.py <data dir>
"""
import glob
import json
import os
import re
import sys
from statistics import mean

DATA = sys.argv[1]
RUNS = os.path.join(DATA, "runs")


def runtime(tool, song):
    """(cpu seconds, wall seconds) from the run log, if the wrapper printed them."""
    try:
        text = open(os.path.join(RUNS, tool, f"{song}.log"), errors="replace").read()
    except OSError:
        return None, None
    cpu = re.findall(r"CPU seconds: ([0-9.]+)", text)
    wall = re.findall(r"wall incl\. lock wait: ([0-9.]+)s", text)
    return (float(cpu[-1]) if cpu else None), (float(wall[-1]) if wall else None)


def fmt(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


rows = []
for path in sorted(glob.glob(os.path.join(RUNS, "*", "*.score.json"))):
    tool = os.path.basename(os.path.dirname(path))
    song = os.path.basename(path)[: -len(".score.json")]
    d = json.load(open(path))
    cpu, wall = runtime(tool, song)
    span = (d.get("ref_span_s") or [0, 0])
    minutes = max((span[1] - span[0]) / 60, 1e-9)
    tm = d.get("tempo_map") or {}
    scan = d.get("cand_scan") or {}
    for key, t in (d.get("tracks") or {}).items():
        inst, diff = key.split("/")
        rows.append({
            "tool": tool, "song": song, "inst": inst, "diff": diff,
            "f1_50": t["onset_50ms"]["f1"], "f1_100": t["onset_100ms"]["f1"],
            "density": t["density_onsets_per_s"]["ratio_cand_ref"],
            "chord_ref": t.get("chord_share", {}).get("ref"), "chord_cand": t.get("chord_share", {}).get("cand"),
            "tap_cand": t.get("tap_share", {}).get("cand"),
            "dir": (t.get("lane_direction_agreement") or {}).get("value"),
            "dir_trivial": (t.get("lane_direction_agreement") or {}).get("trivial_always_same_would_get"),
            "timing_ms": (t.get("timing_err_ms_matched100") or {}).get("median"),
            "beat_f1": (tm.get("beat_f1_70ms") or {}).get("f1"),
            "tempo_markers": tm.get("cand_tempo_markers"), "ref_tempo_markers": tm.get("ref_tempo_markers"),
            "playable": scan.get("playable"), "issues": scan.get("n_chart_issues"),
            "issue_types": scan.get("chart_issues_by_type") or {},
            "cpu_per_min": (cpu / minutes) if cpu else None, "wall_per_min": (wall / minutes) if wall else None,
            "missing": d.get("ref_tracks_missing_in_cand") or [],
        })

if not rows:
    print("no scores yet")
    sys.exit(0)


def avg(rs, k):
    v = [r[k] for r in rs if r[k] is not None]
    return mean(v) if v else None


print("## Expert, averaged over the reference songs\n")
print("| tool | instrument | songs | F1 ±50 ms | F1 ±100 ms | density ×ref | chords cand/ref | taps | lane direction (trivial) | timing ms | beat F1 | tempo markers cand/ref | playable | issues/song | wall s per audio min |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for tool in sorted({r["tool"] for r in rows}):
    for inst in ("guitar", "bass", "drums"):
        rs = [r for r in rows if r["tool"] == tool and r["inst"] == inst and r["diff"] == "expert"]
        if not rs:
            continue
        print(f"| {tool} | {inst} | {len(rs)} | {fmt(avg(rs, 'f1_50'))} | {fmt(avg(rs, 'f1_100'))} | {fmt(avg(rs, 'density'))} | "
              f"{fmt(avg(rs, 'chord_cand'))}/{fmt(avg(rs, 'chord_ref'))} | {fmt(avg(rs, 'tap_cand'))} | "
              f"{fmt(avg(rs, 'dir'))} ({fmt(avg(rs, 'dir_trivial'))}) | {fmt(avg(rs, 'timing_ms'), 1)} | {fmt(avg(rs, 'beat_f1'))} | "
              f"{fmt(avg(rs, 'tempo_markers'), 0)}/{fmt(avg(rs, 'ref_tempo_markers'), 0)} | "
              f"{sum(1 for r in rs if r['playable'])}/{len(rs)} | {fmt(avg(rs, 'issues'), 0)} | {fmt(avg(rs, 'wall_per_min'), 0)} |")

print("\n## Lower difficulties (F1 ±50 ms / density ×ref)\n")
print("| tool | instrument | hard | medium | easy |")
print("|---|---|---|---|---|")
for tool in sorted({r["tool"] for r in rows}):
    for inst in ("guitar", "bass", "drums"):
        cells = []
        for diff in ("hard", "medium", "easy"):
            rs = [r for r in rows if r["tool"] == tool and r["inst"] == inst and r["diff"] == diff]
            cells.append(f"{fmt(avg(rs, 'f1_50'))} / {fmt(avg(rs, 'density'))}" if rs else "—")
        if any(c != "—" for c in cells):
            print(f"| {tool} | {inst} | " + " | ".join(cells) + " |")

print("\n## Per song (Expert)\n")
print("| tool | song | instrument | F1 ±50 | density | chords cand/ref | lane dir | beat F1 | tempo markers | issues | missing parts |")
print("|---|---|---|---|---|---|---|---|---|---|---|")
for r in sorted((r for r in rows if r["diff"] == "expert"), key=lambda r: (r["song"], r["inst"], r["tool"])):
    top = ", ".join(f"{k} {v}" for k, v in sorted(r["issue_types"].items(), key=lambda kv: -kv[1])[:2])
    print(f"| {r['tool']} | {r['song']} | {r['inst']} | {fmt(r['f1_50'])} | {fmt(r['density'])} | "
          f"{fmt(r['chord_cand'])}/{fmt(r['chord_ref'])} | {fmt(r['dir'])} | {fmt(r['beat_f1'])} | "
          f"{r['tempo_markers']}/{r['ref_tempo_markers']} | {r['issues']} ({top}) | {', '.join(r['missing']) or '—'} |")
