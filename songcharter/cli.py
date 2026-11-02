"""The command line: `songcharter assemble <config.json> [--out DIR]`.

Exit status:
  0  the song folder passed the gate and is in the output folder;
  1  the build failed the gate: it is in <output>.failed for inspection (see its report.json), and the output folder
     keeps what it held;
  2  the build could not run: the config, an input or the environment is bad, or song.ogg came out of sync (nothing
     is written);
  3  an internal error, a bug (the traceback is printed).
"""
from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from . import __version__


def _summary(result) -> str:
    r = result.report
    g, tmap = r["grid"], r["tempo_map"]
    lines = [f"song folder: {result.folder}",
             f"grid: {g['mode']} ({g['mode_reason']}), {g['beats']} beats, median {g['bpm_median']:.3f} BPM, "
             f"downbeat phase {g['downbeat_phase']} (margin {g['downbeat_margin']:.2f})",
             f"tempo map: {tmap['markers']} markers, largest error {tmap['max_error_ms']:.2f} ms; "
             f"lead-in {r['lead_in']['pad_seconds']:.3f} s"]
    for key, p in r["parts"].items():
        o = p["offset"]
        removed = (p.get("trimmed") or {}).get("onsets", {}).get("expert", [])
        trimmed = (f"; {len(removed)} Expert onsets trimmed where the {p['trimmed']['stem']} stem is silent "
                   f"({', '.join(f'{t:.2f}' for t in removed[:4])}{', ...' if len(removed) > 4 else ''} s)"
                   if removed else "")
        lines.append(f"part {key}: offset {o['applied'] * 1000:+.1f} ms ({o['mode']}, measured "
                     f"{o['measured'] * 1000:+.1f} ms, concentration {o['concentration']:.2f}){trimmed}")
    for inst, levels in r["tracks"].items():
        counts = " / ".join(f"{levels[d]['onsets']}" for d in ("expert", "hard", "medium", "easy") if d in levels)
        ex = levels.get("expert", {})
        extra = f", {ex.get('fills', 0)} fills" if inst == "drums" else ""
        lines.append(f"{inst}: onsets E/H/M/Ez {counts}; {ex.get('star_power', 0)} star power{extra}, "
                     f"rating {r['ratings'].get(inst)}")
    lines.append(f"sections: {r['sections']['count']} ({r['sections']['source']})")
    lines.append(r["sync"]["summary"])
    gate = r["gate"]
    scan = gate.get("scan_chart") or {}
    if scan.get("ran"):
        how = (f"scan-chart {scan['version']}: {'playable' if scan['playable'] else 'NOT playable'}, "
               f"{scan['chart_issues']} chart issues")
    else:
        how = f"scan-chart not run: {scan.get('reason', 'unknown')}"
    lines.append(f"gate: {'OK' if gate['ok'] else 'FAILED'} ({gate['errors']} errors, {gate['warnings']} warnings; "
                 f"{how})")
    if not gate["ok"]:
        lines.append(f"  the build is in {result.folder} for inspection; {r['config']['output']} was left as it was")
    warned = {k[8:]: n for k, n in gate["by_kind"].items() if k.startswith("warning:")}
    if warned:
        lines.append("  warnings by kind: " + ", ".join(f"{k} {n}" for k, n in warned.items()))
    for i in result.issues:
        if i.error:
            where = " ".join(x for x in (i.instrument, i.difficulty) if x)
            at = f" at {i.time:.3f} s" if i.time is not None else ""
            lines.append(f"  error {i.kind} {where}{at}: {i.message}")
    for w in r["warnings"]:
        lines.append(f"  warning: {w}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    # a song name or path the console's code page cannot show (cp1252 when Windows redirects stdout) must not turn
    # a finished build into a crash; stderr already escapes such characters
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(prog="songcharter", description="Make Clone Hero charts from audio.")
    parser.add_argument("--version", action="version", version=f"songcharter {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="command")
    p = sub.add_parser("assemble", help="build a song folder from a config (our grid, tool parts, our scaffolding)",
                       description="Build a Clone Hero song folder from a JSON config: our beat grid and tempo map, "
                                   "each part taken from an existing chart and re-timed onto it, our difficulties, "
                                   "star power, fills and sections, then the gate. Writes notes.chart, song.ini, "
                                   "song.ogg and report.json into the output folder (into <output>.failed when "
                                   "the gate fails).")
    p.add_argument("config", type=Path, help="the JSON config (relative paths in it are relative to the file)")
    p.add_argument("--out", type=Path, help="the song folder to write (overrides the config's 'output')")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    from .assemble import assemble, load_config  # numpy and the pipeline load only when needed
    try:
        cfg = load_config(args.config, args.out.resolve() if args.out else None)
        result = assemble(cfg)
    except (ValueError, OSError, RuntimeError) as e:  # bad input, a missing tool, song.ogg out of sync
        print(f"songcharter: error: {e}", file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001  a bug: not to be mistaken for a bad input or a failed gate
        traceback.print_exc()
        print("songcharter: internal error (a bug, please report it with the traceback above)", file=sys.stderr)
        return 3
    print(_summary(result))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
