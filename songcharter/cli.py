"""The command line:

    songcharter chart <song file> --out DIR [--work DIR] [--instruments guitar,bass,drums]
                      [--levels expert|all|expert,hard,...] [--solos labels|stems|off|"NAME,NAME"] [--takes N]
                      [--device auto|cpu|cuda] [--no-cpu-retry] [--threads N] [--no-preview] [--lyrics FILE]
                      [--stems] [--one-audio]
                      [--album-art FILE] [--background FILE] [--title ...] [--artist ...] [--album ...] [--year ...]
                      [--genre ...] [--events]
    songcharter assemble <config.json> [--out DIR]
    songcharter doctor [--json PATH] [--quick]
    songcharter ui [--port N] [--no-browser] [--from-shortcut]
    songcharter diagnostics --out PATH
    songcharter listen <song folder> [--part guitar|bass|drums] [--difficulty expert|hard|medium|easy]
                       [--out FILE] [--tones-only]

`chart` runs the whole pipeline on one song file (pipeline.py): decode, separation, the engines, then assemble's
build and gate, then the preview of the built folder; progress goes to stderr, a line per stage with its time, and
the summary to stdout. `assemble`
builds a song folder from a config that names existing charts. `doctor` (device.py) checks where a chart would run
and what it needs: a line per item (WSL and Windows, the GPU, torch's device and the guitar's, memory, disk, the
components), then the problems and notes, and `doctor: OK` or `doctor: N problems`; --json writes the report
(doctor.json) too, and --quick skips the CUDA matmul, autochart's CUDA provider check and allin1's probe. `ui`
(ui/server.py) serves the local page on 127.0.0.1 and opens it in the browser. `diagnostics` (diagnostics.py) writes
the zip to send when something went wrong: logs, settings and the reports, never audio; it prints the zip's path, and
in WSL also its Windows path. `listen` (listen.py) renders one part and level of a built song folder as
sound over the song (or alone), so a wrong, late or missing note can be heard: an OGG (or a WAV) written where
--out says, by default <folder name>-<part>-<level>.ogg in the current folder, never inside the song folder.

`chart --events` also writes the run's events (pipeline.py's module docstring) to stderr, each as one line
`@@songcharter <json>` (ASCII), for the UI's job (ui/jobs.py); then, after the summary, `result` {"ok", "exit",
"folder", "work", "preview" (the work folder's preview/, or null when no preview ran), "stems" (the stems folder,
or null without --stems), "summary" (stdout's text)},
or, before exit 2, 3 or 130, `error` {"kind", "message"}: kind "input" for an errors.InputError or an OSError,
"tool" for an errors.ToolError (or another errors.SongcharterError), "bug" (exit 3), "interrupted" (130). Without
--events nothing of this is written.

--lyrics FILE: the song's lyrics as a text file (UTF-8, or Windows' ANSI code page 1252), a line per phrase and a
blank line between sections; they are timed to the vocal stem and written into the chart (pipeline.py, 3b). Without
the aligner (pip install songcharter[lyrics]) the chart is made without them, with a warning.

--album-art FILE and --background FILE: a JPEG, PNG or WebP image (at most 20 MB and 64 megapixels) for the song
folder's album.jpg (512x512, centre-cropped; without it, the song file's own picture when it has one) and
background.jpg (scaled down to fit 1920x1080), re-encoded with no metadata (art.py). Clone Hero shows the background
when Settings > Gameplay > Use Song Backgrounds is on.

--solos takes a mode (labels, the default: every section named Solo; pipeline.py says why) or the names of the
sections to make solos, as one argument with the names separated by
commas: a name with a space needs quotes around the whole list, in a POSIX shell, cmd.exe and PowerShell alike
(--solos "Solo 1,Solo 2"; unquoted, the shell splits the list at its spaces). A name cannot hold a comma, and
a name that is a mode word (stems, labels, off) is taken as the mode. The names are the build's own sections (the
summary's warnings list them when a name matches none).

Exit status of `doctor`: 0 no problem, 1 problems (listed), 2 bad usage or the report could not be written, 3 a bug.
Exit status of `diagnostics`: 0 written, 2 it could not be written, 3 a bug.
Exit status of `listen`: 0 written; 2 a bad input (no such folder, part or level in the chart, no song.ogg,
an output inside the song folder) or ffmpeg failing; 3 a bug.

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
EVENT_PREFIX = "@@songcharter "   # chart --events: each event line on stderr starts with it (ui/jobs.py reads them)


def _event(event: dict) -> None:
    """chart --events: one event as one ASCII line on stderr."""
    sys.stderr.write(EVENT_PREFIX + json.dumps(event, ensure_ascii=True, default=str) + "\n")
    sys.stderr.flush()


def _error_kind(e: BaseException) -> str:
    """chart --events: an exit-2 error's kind, "input" (errors.InputError, OSError) or "tool" (errors.ToolError and
    any other errors.SongcharterError)."""
    return "input" if isinstance(e, (InputError, OSError)) else "tool"


def _summary(result) -> str:
    r = result.report
    g, tmap = r["grid"], r["tempo_map"]
    lines = [f"song folder: {result.folder}",
             f"grid: {g['mode']} ({g['mode_reason']}), {g['beats']} beats, median {g['bpm_median']:.3f} BPM, "
             f"downbeat phase {g['downbeat_phase']} from {g.get('downbeat_source', 'kick')} (margin "
             f"{g['downbeat_margin']:.2f})",
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


def _diagnostics(args) -> int:
    """`songcharter diagnostics --out PATH`: the bundle of $SONGCHARTER_HOME (the UI's home) and the cache."""
    from . import clonehero, diagnostics
    from .ui import home
    out = args.out.expanduser().absolute()
    try:
        path = diagnostics.bundle(home(), out)
    except KeyboardInterrupt:
        print("songcharter: interrupted", file=sys.stderr)
        return 130
    except OSError as e:
        print(f"songcharter: error: cannot write {out}: {e}", file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        print("songcharter: internal error (a bug, please report it with the traceback above)", file=sys.stderr)
        return 3
    print(f"diagnostics: {path}")
    winpath = clonehero.windows_path(path)
    if winpath:
        print(f"in Windows: {winpath}")
    print("It holds logs and settings, no audio.")
    return 0


def _listen(args) -> int:
    """`songcharter listen`: the render's line, its path and, in WSL, its Windows path."""
    from . import listen
    from .clonehero import windows_path
    folder = args.folder.expanduser()
    try:
        out = listen.output_path(folder, args.out, args.part, args.difficulty)
        rendered = listen.render(folder, args.part, args.difficulty, tones_only=args.tones_only)
        listen.write(rendered.audio, out)
    except KeyboardInterrupt:
        print("songcharter: interrupted", file=sys.stderr)
        return 130
    except (SongcharterError, OSError) as e:
        print(f"songcharter: error: {e}", file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001  a bug
        traceback.print_exc()
        print("songcharter: internal error (a bug, please report it with the traceback above)", file=sys.stderr)
        return 3
    print(listen.summary(rendered))
    print(out)
    winpath = windows_path(out)
    if winpath:
        print(f"in Windows: {winpath}")
    return 0


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
                                   "quick. Writes notes.chart, song.ini, the audio (guitar.ogg, bass.ogg and "
                                   "drums.ogg for the parts charted and song.ogg the rest, so Clone Hero mutes a "
                                   "part on a missed note; one song.ogg with --one-audio) and report.json, and "
                                   "album.jpg and background.jpg when there are pictures, into the output folder "
                                   "(into <output>.failed when the gate fails); with --stems also the six separated "
                                   "instruments as FLAC into \"<output> (stems)\" beside it.")
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
                        "(default: 1 on every device; 4 is the page's \"Best chart\": slower, and only sometimes "
                        "better)")
    c.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto",
                   help="where the models run (default: auto, CUDA when available)")
    c.add_argument("--no-cpu-retry", action="store_true",
                   help="end the chart when a guitar take fails on CUDA (by default the first such take is run again "
                        "on the CPU, about one more transcription, and the chart goes on)")
    c.add_argument("--threads", type=int, metavar="N", help="CPU threads for the models (default: theirs)")
    c.add_argument("--lyrics", type=Path, metavar="FILE",
                   help="the song's lyrics as a text file, a line per phrase: timed to the vocal stem and written into "
                        "the chart (needs songcharter[lyrics]; without it the chart is made without them)")
    c.add_argument("--album-art", type=Path, metavar="FILE",
                   help="an image (JPEG, PNG or WebP) for the album art, album.jpg: centre-cropped to 512x512 (default: "
                        "the song file's own picture, when it has one)")
    c.add_argument("--background", type=Path, metavar="FILE",
                   help="an image (JPEG, PNG or WebP) for the song's background in Clone Hero, background.jpg: scaled "
                        "down to fit 1920x1080 (Clone Hero shows it with Settings > Gameplay > Use Song Backgrounds)")
    c.add_argument("--no-preview", action="store_true",
                   help="no preview (by default the overview and pages of the built folder go into the work "
                        "folder's preview/ when matplotlib and librosa are installed)")
    c.add_argument("--stems", action="store_true",
                   help="also save the six separated instruments (drums, bass, guitar, piano, vocals, other) as 24-bit "
                        "FLAC at 44.1 kHz, lined up with the song file (no lead-in), into a folder of their own beside "
                        "the song folder, named after it with \" (stems)\"; about 190 MB for a 4-minute song")
    c.add_argument("--one-audio", action="store_true",
                   help="one song.ogg instead of a file per part charted (guitar.ogg, bass.ogg, drums.ogg, and "
                        "song.ogg the rest): the music does not drop out on a missed note")
    for flag, key in (("--title", "name"), ("--artist", "artist"), ("--album", "album"), ("--year", "year"),
                      ("--genre", "genre")):
        c.add_argument(flag, dest=f"meta_{key}", metavar="TEXT",
                       help=f"song.ini's {key} (default: the file's tag, else a placeholder)")
    c.add_argument("--events", action="store_true",
                   help="also write the run's events to stderr, a line '@@songcharter <json>' each (for the UI)")
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
    u = sub.add_parser("ui", help="the local page: drop a song, choose the options, watch it chart",
                       description="Serve songcharter's page on 127.0.0.1 (the first free port from 8765) and open it "
                                   "in the browser (in WSL, the Windows browser). One chart runs at a time, as a "
                                   "child process; the page shows its progress and can cancel it. Stops on Ctrl+C or "
                                   "when its window closes. When it is running already, opens its page and exits.")
    u.add_argument("--port", type=int, metavar="N", help="this port only (default: the first free from 8765 to 8784)")
    u.add_argument("--no-browser", action="store_true", help="print the page's address, open no browser")
    u.add_argument("--from-shortcut", action="store_true",
                   help="started by the Start-menu shortcut (noted in the log)")
    g = sub.add_parser("diagnostics", help="write a zip of the logs and settings to send when something went wrong",
                       description="Write one zip that explains what happened: doctor.json and a fresh quick check, "
                                   "the install's runtime.json, the page's settings and Clone Hero folder, the newest "
                                   "logs, and the reports of the newest work folders. It never holds audio, stems, "
                                   "charts or pictures.")
    g.add_argument("--out", type=Path, required=True, metavar="PATH", help="the zip to write")
    lp = sub.add_parser("listen", help="hear a chart: one part and level as tones over the song",
                       description="Render one part and level of a built song folder (notes.chart, song.ini, "
                                   "song.ogg) as sound over the song, so a wrong, late, missing or extra note can be "
                                   "heard: guitar and bass a tone per lane (green lowest to orange highest, an open "
                                   "note lower still), HOPOs and taps softer than strums, sustains held; drums a "
                                   "thump for the kick, a noise burst for the snare, pitched toms and high noise "
                                   "for the cymbals. The song plays 12 dB down under them.")
    lp.add_argument("folder", type=Path, help="the song folder (as songcharter chart wrote it)")
    lp.add_argument("--part", choices=("guitar", "bass", "drums"), default="guitar", help="default: guitar")
    lp.add_argument("--difficulty", choices=DIFFICULTIES, default="expert", help="default: expert")
    lp.add_argument("--out", type=Path, metavar="FILE",
                   help="the file to write, .ogg or .wav (default: <folder name>-<part>-<level>.ogg in the current "
                        "folder; a folder: that name in it); never inside the song folder")
    lp.add_argument("--tones-only", action="store_true", help="the tones alone, without the song")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "ui":
        from .ui import server
        return server.main(port=args.port, browser=not args.no_browser, from_shortcut=args.from_shortcut)
    if args.command == "diagnostics":
        return _diagnostics(args)
    if args.command == "listen":
        return _listen(args)
    events = args.command == "chart" and args.events

    def failed(code: int, kind: str, message: str) -> int:
        if events:
            _event({"event": "error", "kind": kind, "message": message})
        return code

    try:
        if args.command == "chart":
            from . import pipeline  # numpy and the pipeline load only when needed
            meta = {k[5:]: v for k, v in vars(args).items() if k.startswith("meta_") and v is not None}
            instruments = pipeline.INSTRUMENTS if args.instruments is None else args.instruments
            lyrics = read_lyrics(args.lyrics) if args.lyrics is not None else None
            options = pipeline.Options(instruments=instruments, takes=args.takes, device=args.device,
                                       threads=args.threads, work=args.work, metadata=meta, levels=args.levels,
                                       solos=args.solos, preview=not args.no_preview, lyrics=lyrics,
                                       album_art=args.album_art, background=args.background,
                                       cpu_retry=not args.no_cpu_retry, stems=args.stems, one_audio=args.one_audio)
            done = pipeline.chart(args.song, args.out, options, events=_event if events else None)
            result, extra = done.assembled, pipeline.summary(done)
        else:
            from .assemble import assemble, load_config
            cfg = load_config(args.config, args.out.resolve() if args.out else None)
            result, extra = assemble(cfg), None
    except (SongcharterError, OSError) as e:  # a bad input, a missing or failing tool, song.ogg out of sync
        print(f"songcharter: error: {e}", file=sys.stderr)
        return failed(2, _error_kind(e), str(e))
    except KeyboardInterrupt:
        print("songcharter: interrupted", file=sys.stderr)
        return failed(130, "interrupted", "interrupted")
    except Exception as e:  # noqa: BLE001  a bug: not to be mistaken for a bad input or a failed gate
        traceback.print_exc()
        print("songcharter: internal error (a bug, please report it with the traceback above)", file=sys.stderr)
        return failed(3, "bug", f"{type(e).__name__}: {e}")
    text = _summary(result)
    print(text)
    if extra:
        print(extra)
    code = 0 if result.ok else 1
    if events:
        sys.stdout.flush()   # the summary before the result in a stream that merges the two
        _event({"event": "result", "ok": result.ok, "exit": code, "folder": str(result.folder), "work": str(done.work),
                "preview": str(done.work / "preview") if done.preview else None,
                "stems": str(done.stems) if done.stems is not None else None,
                "summary": text + (f"\n{extra}" if extra else "")})
    return code


if __name__ == "__main__":
    sys.exit(main())
