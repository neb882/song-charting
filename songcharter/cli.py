"""The command line:

    songcharter chart <song file> --out DIR [--work DIR] [--instruments guitar,bass,drums]
                      [--levels expert|all|expert,hard,...] [--solos labels|stems|off|"NAME,NAME"] [--takes N]
                      [--device auto|cpu|cuda] [--threads N] [--no-preview] [--lyrics FILE] [--title ...]
                      [--artist ...] [--album ...] [--year ...] [--genre ...]
    songcharter assemble <config.json> [--out DIR]
    songcharter doctor [--json PATH] [--quick]

`chart` runs the whole pipeline on one song file (pipeline.py): decode, separation, the engines, then assemble's
build and gate, then the preview of the built folder; progress goes to stderr, a line per stage with its time, and
the summary to stdout. `assemble`
builds a song folder from a config that names existing charts. `doctor` (device.py) checks where a chart would run
and what it needs: a line per item (WSL and Windows, the GPU, torch's device and the guitar's, memory, disk, the
components), then the problems and notes, and `doctor: OK` or `doctor: N problems`; --json writes the report
(doctor.json) too, and --quick skips the CUDA matmul, autochart's CUDA provider check and allin1's probe.

--lyrics FILE: the song's lyrics as a text file (UTF-8, or Windows' ANSI code page 1252), a line per phrase and a
blank line between sections; they are timed to the vocal stem and written into the chart (pipeline.py, 3b). Without
the aligner (pip install songcharter[lyrics]) the chart is made without them, with a warning.

--solos takes a mode (labels, the default: every section named Solo; pipeline.py says why) or the names of the
sections to make solos, as one argument with the names separated by
commas: a name with a space needs quotes around the whole list, in a POSIX shell, cmd.exe and PowerShell alike
(--solos "Solo 1,Solo 2"; unquoted, the shell splits the list at its spaces). A name cannot hold a comma, and
a name that is a mode word (stems, labels, off) is taken as the mode. The names are the build's own sections (the
summary's warnings list them when a name matches none).

Exit status of `doctor`: 0 no problem, 1 problems (listed), 2 bad usage or the report could not be written, 3 a bug.

Exit status (`chart` and `assemble`):
  0  the song folder passed the gate and is in the output folder;
  1  the build failed the gate: it is in <output>.failed for inspection (see its report.json), and the output folder
     keeps what it held;
  2  the build could not run: the config, an input or the environment is bad (a missing component is named with
     its fix), a component failed, or song.ogg came out of sync (nothing is written): an errors.SongcharterError
     or an OSError, printed as one line;
  3  an internal error, a bug: any other exception, numpy's and torch's included (the traceback is printed, and
     for `chart` also kept in the work folder's pipeline.json);
  130  interrupted (Ctrl+C) before the build was in place: the output folder keeps what it held. For `chart` a
       Ctrl+C during the preview or the pruning after the build stops only that stage, which is warned about, and
       the exit status is 0 or 1 as the gate says, with the summary.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from . import __version__
from .errors import InputError, SongcharterError
from .timed import DIFFICULTIES

LEVEL_ABBREVIATIONS = {"expert": "E", "hard": "H", "medium": "M", "easy": "Ez"}


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
        cut = (p.get("clipped") or {}).get("levels", {}).get("expert", {})
        clipped = (f"; at the end of the audio {cut['onsets_dropped']} Expert onsets dropped, "
                   f"{cut['sustains_clipped']} sustains clipped, {cut['sustains_removed']} removed"
                   if any(cut.values()) else "")
        lines.append(f"part {key}: offset {o['applied'] * 1000:+.1f} ms ({o['mode']}, measured "
                     f"{o['measured'] * 1000:+.1f} ms, concentration {o['concentration']:.2f}){trimmed}{clipped}")
    for inst, levels in r["tracks"].items():
        written = [d for d in DIFFICULTIES if d in levels]
        counts = " / ".join(f"{levels[d]['onsets']}" for d in written)
        ex = levels.get("expert", {})
        extra = f", {ex.get('fills', 0)} fills" if inst == "drums" else ""
        if inst == "guitar":  # the solo trackers, where they went (or that there are none)
            solos = (r.get("phrases", {}).get(inst) or {}).get("solos") or []
            extra = (f", {len(solos)} solo{'s' * (len(solos) > 1)} "
                     f"({', '.join(f'{a:.1f}-{b:.1f}' for a, b in solos)} s)" if solos else ", no solo")
        lines.append(f"{inst}: onsets {'/'.join(LEVEL_ABBREVIATIONS[d] for d in written)} {counts}; "
                     f"{ex.get('star_power', 0)} star power{extra}, rating {r['ratings'].get(inst)}")
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


def _instruments(text: str) -> tuple[str, ...]:
    return tuple(x.strip().lower() for x in text.split(",") if x.strip())


def _solos(text: str) -> str | tuple[str, ...]:
    """--solos: a mode (stems, labels, off, any case), else section names separated by commas, each kept as written
    but for runs of spaces (one argument: quote it when a name holds a space)."""
    mode = text.strip().lower()
    if mode in ("stems", "labels", "off"):
        return mode
    return tuple(" ".join(x.split()) for x in text.split(",") if x.strip())


def read_lyrics(path: Path) -> str:
    """The text of a lyrics file: UTF-8 (a byte-order mark allowed, UTF-16 too), else code page 1252. Errors name the
    file, never its contents."""
    try:
        data = Path(path).expanduser().read_bytes()
    except OSError as e:
        raise InputError(f"cannot read the lyrics file {path} ({e.strerror or type(e).__name__})") from None
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            raise InputError(f"the lyrics file {path} is not UTF-16 text") from None
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise InputError(f"the lyrics file {path} is not UTF-8 or Windows-1252 text")


def _levels(text: str) -> tuple[str, ...]:
    """--levels: "all", or a comma-separated list of difficulties (checked by pipeline.Options)."""
    words = _instruments(text)
    return DIFFICULTIES if words == ("all",) else words


def _doctor(args) -> int:
    """`songcharter doctor`: the report's lines and the verdict on stdout, the report into --json."""
    from . import device
    try:
        report = device.report(full=not args.quick)
    except KeyboardInterrupt:
        print("songcharter: interrupted", file=sys.stderr)
        return 130
    except Exception:  # noqa: BLE001  a bug: the checks themselves never raise for a missing component
        traceback.print_exc()
        print("songcharter: internal error (a bug, please report it with the traceback above)", file=sys.stderr)
        return 3
    for line in device.summary(report):
        print(line)
    if args.json:
        path = args.json.expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_name(path.name + ".part")
            part.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
            os.replace(part, path)
        except OSError as e:
            print(f"songcharter: error: cannot write {path}: {e}", file=sys.stderr)
            return 2
    n = len(report["problems"])
    print("doctor: OK" if report["ok"] else f"doctor: {n} problem{'s' * (n != 1)}")
    return 0 if report["ok"] else 1


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
    c = sub.add_parser("chart", help="chart a song file: separation, the engines, our scaffolding and the gate",
                       description="Chart one song file (MP3 or anything ffmpeg reads) into a Clone Hero song "
                                   "folder: one decode, one stem separation, the drums, bass, guitar and "
                                   "sections engines, then our grid, tiers, star power, fills and sections, and "
                                   "the gate. Every stage caches its work in the work folder, so a re-run is "
                                   "quick. Writes notes.chart, song.ini, song.ogg and report.json into the output "
                                   "folder (into <output>.failed when the gate fails).")
    c.add_argument("song", type=Path, help="the song file")
    c.add_argument("--out", type=Path, required=True, help="the song folder to write")
    c.add_argument("--work", type=Path, help="the work folder for the decode, stems and engine outputs (default: "
                                             "one per song in the per-user cache, %%LOCALAPPDATA%%\\songcharter\\work "
                                             "on Windows, $XDG_CACHE_HOME/songcharter/work (else ~/.cache/"
                                             "songcharter/work) elsewhere, or $SONGCHARTER_CACHE/work; the least "
                                             "recently used go past 5 GB, $SONGCHARTER_CACHE_GB)")
    c.add_argument("--instruments", type=_instruments, default=None, metavar="LIST",
                   help="comma-separated parts to chart (default: guitar,bass,drums)")
    c.add_argument("--levels", type=_levels, default=("expert",), metavar="LIST",
                   help="the difficulties to write: expert (default), all, or a comma-separated list that includes "
                        "expert, such as expert,hard (the others are reduced from Expert)")
    c.add_argument("--solos", type=_solos, default="labels", metavar="MODE|NAMES",
                   help="where the guitar solos go: labels (default: the sections named Solo), stems (only those "
                        "where the vocals stem is quiet and the guitar loud), off, or the solo sections' names, comma-"
                        "separated and quoted as one argument when a name holds a space: --solos \"Solo 1,Solo 2\" "
                        "(names as the build's sections are called; anything but labels and off needs the guitar "
                        "charted)")
    c.add_argument("--takes", type=int, default=None, metavar="N",
                   help="guitar takes, spliced by agreement: 1, or 3 or more, each about one more autochart run "
                        "(default: 4 when the guitar runs on CUDA, 1 on the CPU)")
    c.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto",
                   help="where the models run (default: auto, CUDA when available)")
    c.add_argument("--threads", type=int, metavar="N", help="CPU threads for the models (default: theirs)")
    c.add_argument("--lyrics", type=Path, metavar="FILE",
                   help="the song's lyrics as a text file, a line per phrase: timed to the vocal stem and written into "
                        "the chart (needs songcharter[lyrics]; without it the chart is made without them)")
    c.add_argument("--no-preview", action="store_true",
                   help="no preview (by default the overview and pages of the built folder go into the work "
                        "folder's preview/ when matplotlib and librosa are installed)")
    for flag, key in (("--title", "name"), ("--artist", "artist"), ("--album", "album"), ("--year", "year"),
                      ("--genre", "genre")):
        c.add_argument(flag, dest=f"meta_{key}", metavar="TEXT",
                       help=f"song.ini's {key} (default: the file's tag, else a placeholder)")
    p = sub.add_parser("assemble", help="build a song folder from a config (our grid, tool parts, our scaffolding)",
                       description="Build a Clone Hero song folder from a JSON config: our beat grid and tempo map, "
                                   "each part taken from an existing chart and re-timed onto it, our difficulties, "
                                   "star power, fills and sections, then the gate. Writes notes.chart, song.ini, "
                                   "song.ogg and report.json into the output folder (into <output>.failed when "
                                   "the gate fails).")
    p.add_argument("config", type=Path, help="the JSON config (relative paths in it are relative to the file)")
    p.add_argument("--out", type=Path, help="the song folder to write (overrides the config's 'output')")
    d = sub.add_parser("doctor", help="check where a chart would run (GPU, CUDA, WSL, memory, disk) and what it needs",
                       description="Check the machine for charting: WSL and the Windows side (in WSL), the GPU, "
                                   "torch's device and the guitar's (autochart's CUDA provider), memory, free disk "
                                   "and every component, with the reason for any CPU fallback. Exit 0 with no "
                                   "problem, 1 with problems.")
    d.add_argument("--json", type=Path, metavar="PATH", help="also write the report there (doctor.json)")
    d.add_argument("--quick", action="store_true",
                   help="skip the CUDA matmul, autochart's CUDA provider check and allin1's probe")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "doctor":
        return _doctor(args)
    try:
        if args.command == "chart":
            from . import pipeline  # numpy and the pipeline load only when needed
            meta = {k[5:]: v for k, v in vars(args).items() if k.startswith("meta_") and v is not None}
            instruments = pipeline.INSTRUMENTS if args.instruments is None else args.instruments
            lyrics = read_lyrics(args.lyrics) if args.lyrics is not None else None
            options = pipeline.Options(instruments=instruments, takes=args.takes, device=args.device,
                                       threads=args.threads, work=args.work, metadata=meta, levels=args.levels,
                                       solos=args.solos, preview=not args.no_preview, lyrics=lyrics)
            done = pipeline.chart(args.song, args.out, options)
            result, extra = done.assembled, pipeline.summary(done)
        else:
            from .assemble import assemble, load_config
            cfg = load_config(args.config, args.out.resolve() if args.out else None)
            result, extra = assemble(cfg), None
    except (SongcharterError, OSError) as e:  # a bad input, a missing or failing tool, song.ogg out of sync
        print(f"songcharter: error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("songcharter: interrupted", file=sys.stderr)
        return 130
    except Exception:  # noqa: BLE001  a bug: not to be mistaken for a bad input or a failed gate
        traceback.print_exc()
        print("songcharter: internal error (a bug, please report it with the traceback above)", file=sys.stderr)
        return 3
    print(_summary(result))
    if extra:
        print(extra)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
