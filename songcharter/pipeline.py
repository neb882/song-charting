"""The Goal 2 pipeline: one song file in, a gated Clone Hero song folder out (DESIGN.md 1, M3).

    result = chart("song.mp3", "out/Song")    # `songcharter chart song.mp3 --out out/Song`
    result.ok, result.folder                  # the gate's verdict; out/Song, or out/Song.failed when it failed

  1. **Decode** the file once (audio.decode, gapless) and write the decode as a float32 WAV into the work folder.
     It is autochart's input and assemble's audio, so every stage reads the same samples.
  2. **Separate** once: htdemucs_6s, seeded (separate.py), its stems cached in work/stems/<key>/.
  3. **Engines**, each writing a folder of its own in the work folder, which is also its cache: drums from ADTOF
     (engines/adtof.py), bass from the rule engine (engines/bass.py), sections from allin1 or its librosa fallback
     (engines/sections.py), and guitar from autochart's engine (engines/autochart.py), one take per seed: the
     engine's default seed and, for `takes` > 1, seeds 101, 202, ... for the others, which assemble splices
     section by section (takes.py). By default 4 takes when the guitar stage runs on CUDA and 1 on the CPU
     (`guitar_takes`). An engine that charts no note leaves its part out (DESIGN.md 2, absent parts).
  3b. **Lyrics** (`lyrics`: the text a person gives, else none): aligned to the vocal stem (engines/lyrics.py,
     DESIGN.md 2.15), its own folder work/lyrics/ the cache. Torch or torchaudio missing, the weights out of reach
     or an alignment that fails leaves the lyrics out with a warning: lyrics never fail a chart. The text goes to
     assemble in memory, never into a file: only the chart holds it, and pipeline.json counts it (`lyrics`).
  4. **Assemble** from a config written into the work folder (work/assemble.json): our beat grid and tempo map, the
     parts quantized onto it, star power, fills, solos and sections, then the gate (assemble.py). Only Expert is
     written by default (`levels`: the friend plays Expert, and asks for the others when he wants them); the lower
     tiers are reduced from it when asked for. Solos go on every section named "Solo" (`solos` "labels", below).
     The result and its exit codes are `songcharter assemble`'s.
  5. **Preview** (preview.py) of the folder assemble wrote, the song folder or its .failed, into work/preview/
     (overview.png, page_NN.png), judged against the work folder's stems, when matplotlib and librosa import. It
     only informs: absent libraries or a preview that fails give one warning, never another exit code, and so does
     a Ctrl+C while it runs or while the cache is pruned after it (the build is in place by then: the run ends as
     the gate says, with its summary).

  * **Art** (art.py, M4-11): album.jpg from the album art a person gives (`album_art`), else from the song file's
    embedded cover picture, and background.jpg from the background image a person gives (`background`), made before
    any audio work into work/art/ and copied into the song folder by assemble: nothing else in the chart changes. A
    given image that is not a JPEG, PNG or WebP, or is over its limits, is an InputError then; an embedded picture
    that fails is a warning. pipeline.json's and report.json's `art` say what was added and where it came from
    ("embedded", "given", or None), with no path of the person's (the options record whether each was given).
  * **Metadata.** The file's tags as ffmpeg prints them (title, artist, album, genre, date, track), the caller's
    values on top, and defaults for what scan-chart requires. With no artist tag, a file named "Artist - Title"
    (`from_file_name`: a hyphen, en dash or em dash with a space on each side, after an optional track number)
    gives the artist and the title, where the caller and the tags give none; otherwise the file's name is the
    title. The album's placeholder is "<the song's name> - (Single)" (Encore's rule for a single), "Unknown" the
    artist's, genre's and year's. scan-chart's own defaults ("Unknown Artist", ...) count as missing, so they are
    not used.
  * **A song too short or silent** (under MIN_SONG_S, or its peak under MIN_PEAK_DBFS) is refused right after the
    decode, before the separation, with an InputError that says which (`check_song`): the engines have nothing to
    work on there, and the librosa sections fallback raised on such songs.
  * **Before any audio work** the inputs are checked (the file exists, the output folder holds nothing a build does
    not write) and so is every component the instruments need: a missing one fails with what to install or set,
    never a traceback. Where DESIGN.md has a fallback the stage takes it and says so: sections fall back to
    librosa when allin1 is absent or fails; device "auto" takes CUDA only when a CUDA kernel runs here (else every
    model runs on the CPU, for device.choose_device's reason), separation moves to the CPU when CUDA runs out of
    memory, and allin1, which runs in a Python of its own, uses CUDA when that Python has it and the CPU when not,
    even for device "cuda". Every move to the CPU is a **fallback**: recorded (stage, from, to, reason) in
    pipeline.json's `fallbacks` and ChartResult.fallbacks, and warned about, but for device "auto" on a machine with
    no NVIDIA GPU at all (recorded only): "auto" choosing the CPU, separation's fallback, allin1 on the CPU while
    torch here runs on CUDA, a guitar take whose transcriber autochart ran on the CPU, and a guitar take run again
    on the CPU after its CUDA run failed.
  * **A guitar take that fails on CUDA** (each take is a call of its own) is run again on the CPU, once a chart
    (`CPU_RETRIES`, `cpu_retry`, M5-05): when the engine failed inside (the driver's FAILED line "engine failed
    (exit <int>)", as a GPU short of memory gives: `failure`'s "engine"), that seed runs again with device "cpu"
    into the same folder, is recorded as a fallback with a warning, and the takes after it go back to CUDA. Its take
    on the CPU is not reused by a later chart on CUDA (autochart's cache takes a take only when its transcriber ran
    on the device asked for), so that chart runs it on CUDA again. Not retried: an engine killed by a signal
    ("exit null SIGKILL": memory, where the CPU would not help), the driver's own kills (its wall-clock timeout, no
    decoder progress, the token cap) and failures (models missing, ...), which are not the GPU's, a timeout of
    autochart.generate's, an exit 0 with no take, a second CUDA failure in the same chart, and any failure with
    `cpu_retry` off: those end the chart with a ToolError that says first what to try or what failed
    (`take_failed`), and so does a retry that fails, on the CPU; the takes that finished stay in the cache for the
    next run. When the first take
    of the CUDA default is the one retried, it is used alone, as when autochart moved it to the CPU by itself.
  * **GPU memory.** On CUDA, torch's cache is emptied after the separation and after the drums, and each stage
    that runs in this process records torch's own peak (`torch_peak_vram_mb`: reset as it begins).
  * **Solos** ("labels" by default): every section the sections engine names "Solo" (allin1's solo label), within
    starpower.place_solos's rules (16 Expert onsets and 4 measures; a run over 56 measures or 100 s gives its
    densest window; at most 4 a song, 4 measures apart, together at most 0.40 of it); a list of section names
    (`--solos "Solo 1,Solo 2"`) puts them exactly there instead. Not "stems", the label confirmed by the stems
    (vocals quiet, guitar loud), which the solo evaluation (DESIGN.md 2.10) found rejecting the very solos the
    friend confirmed on the test song (vocals active in 0.561 and 0.863 of their frames; the test allows 0.25), so
    it placed none there. With fold-0 sections (what allin1 runs on either device, M6-10) "labels" covers all of
    Solo 2 and the first half of Solo 1 and adds one span nobody has confirmed; with the ensemble (a model asked
    for, which CUDA ran before M6-10) it covers Solo 2 only. On the six
    references both find 1 of the 2 human solos (Lucretia's; Kimochi Warui's is called a chorus), and "labels"
    makes 2 false solos to the stems' 1 with fold 0, 4 to 1 with the ensemble (one extra false tracker every six
    songs, or about every two). The friend asked for solo trackers, and a missed solo costs him one where a false
    one costs a tracker he can ignore. Solos are guitar solos: a mode other than "labels" or "off", or names,
    without the guitar charted is refused, as more than one take is.
  * **Errors.** What the user can act on (a bad input or option, a missing or failing component) raises an
    errors.InputError or errors.ToolError, or an OSError; anything else is a bug. Either way pipeline.json keeps
    the error and its traceback.
  * **The work folder** is <cache>/work/<name>-<key> in the per-user cache (cache.py: %LOCALAPPDATA%\\songcharter
    on Windows, $XDG_CACHE_HOME/songcharter (else ~/.cache/songcharter) elsewhere, or $SONGCHARTER_CACHE), keyed
    by the song file's SHA-256, so the same file reuses it whatever the output; autochart's own scratch folder sits
    apart in <cache>/ac/<key[:8]>, which keeps the files of its deep cache under Windows' 260 characters (not its
    staging files: cache.py). `work` (--work) puts the work folder anywhere, with the scratch folder inside it as
    before. After each run that finishes, the least recently used work folders in the cache go until they fit in
    5 GB (cache.prune); the summary gives the work folder and its size, and autochart's scratch folder when the
    run made one.
  * **Re-runs.** The decode is rewritten only when the samples change; separation and every engine reuse their
    caches, so a re-run with the same file and options costs the decode, the cache checks and the build.
  * **Report.** work/pipeline.json: the options, the metadata and where each value came from, the device and why
    (`device`), every stage's wall time, cache use, device and fallback, the process's peak RSS after each stage
    (where the OS reports it) and, for the sections, the peak allin1's runner reports for itself; the fallbacks;
    and per stage the whole system's memory as a sampler thread saw it (device.Sampler: every second
    `min_available_ram_mb` and `max_swap_used_mb`, every two seconds `max_gpu_used_mb` when nvidia-smi exists;
    children included), for the peak-memory checks on a 16 GB PC (M4-08).
    Progress goes to `log` (stderr on the command line), a line when a stage starts and one when it ends.
  * **Events** (`events`, for the UI: `songcharter chart --events`, M4-04): a dict per step, its kind in "event":
    `plan` {"stages"} once the stages are known; `stage_start` {"stage", "index", "count", "detail"} (index from 1,
    as the log's [k/n]); `take` {"index", "count", "seed"} before each guitar take that runs (not one its cache
    answers; index from 1 among the stage's takes, so the CUDA default's four takes count 1 to 4 of 4), and again
    with "device": "cpu" and the same index before a take's run again on the CPU; `fallback` {"stage", "from", "to", "reason"} for every record in `fallbacks`, also those only
    recorded; `warning` {"text"} for every warning; `stage_end` {"stage", "seconds", "cached", "detail"}. A stage
    that stops (an error, or the preview failing) sends no `stage_end`.

The heavy stages are the methods of `Engines`, so tests stand in for them; importing this module loads no model.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from . import __version__
from . import art as ART
from . import audio as A
from . import cache
from . import device as D
from .assemble import AssembleResult, assemble, check_output, failed_folder, load_config
from .errors import InputError, ToolError
from .importers import read_song
from .lyrics import Timed, parse as parse_lyrics
from .timed import DIFFICULTIES, INSTRUMENTS

SAMPLE_RATE = A.SAMPLE_RATE
STEMS = ("drums", "bass", "guitar", "other", "vocals")   # the stems assemble reads (piano only reaches allin1)
EXTRA_SEED_STEP = 101    # takes after the first use seeds 101, 202, 303, ... (the v1 chart's seeds)
CUDA_TAKES = 4           # guitar takes by default when the guitar stage runs on CUDA (guitar_takes); 1 on the CPU
CPU_RETRIES = 1          # guitar takes a chart runs again on the CPU after their CUDA run failed (cpu_retry)
REASON_CHARS = 120       # at most this much of the engine's error line goes into a retry's reason (engine_line)
GUITAR_END_GAP_S = 10.0  # a continued guitar take whose last note is this long before its stem stops playing, and
                         # whose continuation stopped short, ends early (stitch_lines' "ends at" warning)
PLAYING_DB = -15.0       # a stem's frame within this of its P95 level is playing (preview.GAP_DB)
SOLO_MODES = ("stems", "labels", "off")  # assemble's solos modes; a list of section names is the other kind
# the placeholders for what no tag or caller gives ({name}: the song's name, as resolved); the album's is Encore's
# song.ini rule for a single (docs/reports/charting-conventions.md, section 8), instead of "Unknown"
DEFAULTS = {"artist": "Unknown", "album": "{name} - (Single)", "genre": "Unknown", "year": "Unknown",
            "charter": "songcharter"}
# "Artist - Title" in a file's name (from_file_name): the separator, a hyphen, en dash or em dash with a space on each
# side, or at the start with a space after ("- Title": a blank artist); a track number before the artist, one to three
# digits followed by a dot, a space or a separator
NAME_SEPARATOR = re.compile(r"(?:(?<= )|^)[-\u2013\u2014](?= )")
TRACK_NUMBER = re.compile(r"[0-9]{1,3}")               # before a separator: "01 - Artist - Title"
TRACK_PREFIX = re.compile(r"^[0-9]{1,3}(?:\. ?| )")   # or before the artist: "01. Artist", "1.Artist", "01 Artist"
MIN_SONG_S = 10.0        # a song shorter than this is refused after the decode (check_song)
MIN_PEAK_DBFS = -60.0    # and so is one whose peak is under this: silence
# the tags each song.ini value is read from, first found wins (ffmpeg's names, lower-cased)
TAGS = {"name": ("title",), "artist": ("artist", "album_artist", "albumartist"), "album": ("album",),
        "genre": ("genre",), "year": ("date", "year", "originaldate"), "album_track": ("track", "tracknumber")}
OVERRIDES = ("name", "artist", "album", "genre", "year")


@dataclass(frozen=True)
class Options:
    instruments: tuple[str, ...] = INSTRUMENTS   # which parts to chart: guitar, bass, drums
    takes: int | None = None                     # guitar takes: 1, or 3 and more (a splice needs three runs); None:
                                                 # 4 when the guitar stage runs on CUDA, else 1 (guitar_takes)
    device: str = "auto"                         # "auto" (CUDA when a CUDA kernel runs here), "cpu" or "cuda"
    threads: int | None = None                   # torch's threads here and in allin1 (None: their defaults)
    work: Path | None = None                     # the work folder (None: one per song in the cache, cache.py)
    metadata: Mapping[str, str] = field(default_factory=dict)  # name, artist, album, genre, year: over the tags
    solos: str | tuple[str, ...] = "labels"      # assemble's solos: "labels" (sections named Solo: the module
                                                 # docstring), "stems" (those with vocals quiet, guitar loud), "off",
                                                 # or the names of the solo sections; all but "labels" and "off" need
                                                 # the guitar among the instruments
    levels: tuple[str, ...] = ("expert",)        # the difficulties written: Expert, and any of hard, medium, easy
    preview: bool = True                         # the preview of the built folder into work/preview/ (preview.py)
    lyrics: str | None = None                    # the song's lyrics as text, a line per phrase, to time and write
                                                 # into the chart (None: no lyrics); never into any report
    album_art: Path | str | None = None          # an image for album.jpg, over the song file's own picture (art.py)
    background: Path | str | None = None         # an image for background.jpg, Clone Hero's song background
    cpu_retry: bool = True                       # a guitar take whose CUDA run failed is run again on the CPU, once
                                                 # a chart (the module docstring); the page has no control for it

    def check(self) -> None:
        if not self.instruments:
            raise InputError("no instruments to chart")
        unknown = [i for i in self.instruments if i not in INSTRUMENTS]
        if unknown or len(set(self.instruments)) != len(self.instruments):
            raise InputError(f"instruments are {', '.join(INSTRUMENTS)}, each once, not {', '.join(self.instruments)}")
        if self.takes is not None and (isinstance(self.takes, bool) or not isinstance(self.takes, int)
                                       or self.takes < 1 or self.takes == 2):
            raise InputError(f"takes is 1, or 3 or more (takes are spliced by agreement, and two cannot outvote "
                             f"each other), not {self.takes!r}")
        if self.takes is not None and self.takes > 1 and "guitar" not in self.instruments:
            raise InputError("takes are guitar takes: chart the guitar too, or leave takes at 1")
        if self.device not in ("auto", "cpu", "cuda"):
            raise InputError(f"device is auto, cpu or cuda, not {self.device!r}")
        if not isinstance(self.preview, bool):
            raise InputError(f"preview is true or false, not {self.preview!r}")
        if not isinstance(self.cpu_retry, bool):
            raise InputError(f"cpu_retry is true or false, not {self.cpu_retry!r}")
        if self.threads is not None and (isinstance(self.threads, bool) or not isinstance(self.threads, int)
                                         or self.threads < 1):
            raise InputError(f"threads must be a whole number of at least 1, not {self.threads!r}")
        levels = self.levels
        if (isinstance(levels, str) or not isinstance(levels, (tuple, list)) or "expert" not in levels
                or any(d not in DIFFICULTIES for d in levels) or len(set(levels)) != len(levels)):
            shown = ", ".join(map(str, levels)) if isinstance(levels, (tuple, list)) else repr(levels)
            raise InputError(f"levels are {', '.join(DIFFICULTIES)}, each once and expert among them (the others are "
                             f"reduced from it), not {shown or 'none'}")
        solos = self.solos
        if isinstance(solos, str) and solos not in SOLO_MODES or not isinstance(solos, (str, tuple, list)):
            raise InputError(f"solos is {', '.join(map(repr, SOLO_MODES))} or a list of section names, not {solos!r}")
        if not isinstance(solos, str) and (not solos or any(not isinstance(n, str) or not n.strip() for n in solos)):
            raise InputError(f"solos as section names needs one name or more, none of them blank, not {solos!r}")
        if solos not in ("labels", "off") and "guitar" not in self.instruments:  # the default stays silent
            raise InputError("solos are guitar solos: chart the guitar too, or leave solos at labels")
        unknown = sorted(set(self.metadata) - set(OVERRIDES))
        if unknown:
            raise InputError(f"unknown metadata key(s): {', '.join(unknown)} (known: {', '.join(OVERRIDES)})")
        if self.lyrics is not None:
            if not isinstance(self.lyrics, str):
                raise InputError(f"lyrics is a text or None, not a {type(self.lyrics).__name__}")
            if not parse_lyrics(self.lyrics).syllables:
                raise InputError("the lyrics hold no word to time")
        for key in ("album_art", "background"):
            value = getattr(self, key)
            if value is not None and (not isinstance(value, (str, Path)) or not str(value).strip()):
                raise InputError(f"{key} is an image file's path or None, not {value!r}")


@dataclass(frozen=True)
class Run:
    """One engine run: the file assemble reads, whether the engine's cache answered, and what it reports."""
    path: Path
    cached: bool
    info: dict


@dataclass
class Stage:
    name: str
    seconds: float
    cached: bool
    detail: str
    info: dict = field(default_factory=dict)


@dataclass
class ChartResult:
    assembled: AssembleResult
    stages: list[Stage]
    work: Path
    config: Path                 # the assemble config written into the work folder
    metadata: dict
    warnings: list[str]
    preview: dict | None = None  # what the preview wrote and flagged (Engines.preview); None when it did not run
    scratch: Path | None = None  # autochart's scratch folder when it is not inside the work folder (cache.py)
    work_bytes: int = 0          # the work folder's size after the run, its scratch folder's included
    fallbacks: list[dict] = field(default_factory=list)  # every move to the CPU: {"stage", "from", "to", "reason"}
    lyrics: dict | None = None   # pipeline.json's `lyrics` (counts and confidence only); None when none were given
    art: dict = field(default_factory=dict)   # pipeline.json's `art`: {"album_art", "background"} (art.prepare)

    @property
    def ok(self) -> bool:
        return self.assembled.ok

    @property
    def folder(self) -> Path:
        return self.assembled.folder


def guitar_takes(asked: int | None, device: str) -> tuple[int, str]:
    """How many guitar takes to run, and why: the number asked for, on any device; by default CUDA_TAKES (4) when
    the guitar stage runs on CUDA (`device`: "cuda" or "cpu", the device resolved for it) and 1 otherwise.

    The evidence behind the default (the takes experiment, DESIGN.md 2.7): 4 takes spliced by agreement gave +0.013
    Expert F1@50 over 1 take on 5 reference songs (Lucretia apart: our grid misses its beats), mostly precision, and
    4 beat 3. Their cost on the owner's RTX 5070: 3.41x the guitar stage over the takes experiment's seven songs
    (+5.75 min a song), and 3.9x for the 6:52 test song in the GPU smoke test through the real install (854 s for 4
    takes against about 219 s for one, +10.6 min); kept as the default at the release gate (M4-08 times the friend's
    4070). On a CPU each take after the first is one more transcription, 217 s for the test song on the dev container
    (DESIGN.md 5, M3), so 3 more would add about 11 min for that small gain. 2 takes are never the default (two
    cannot outvote each other), nor 3 (+0.006 to +0.0105 over 1, below 4)."""
    if asked is not None:
        return asked, f"{asked} asked for"
    if device == "cuda":
        return CUDA_TAKES, (f"the default on cuda: {CUDA_TAKES} takes spliced gave +0.013 Expert F1@50 over 1, for "
                            "3.9x the guitar stage's time (the GPU smoke test on an RTX 5070: 854 s for the 6:52 "
                            "test song, about 219 s for 1 take)")
    return 1, "the default on the cpu: 1 take (each one more is another transcription there, about 3.6 min for a 7-min song)"


AUTOCHART_EXIT = re.compile(r"autochart seed \d+ failed \(exit (-?\d+)\)")   # engines/autochart.py's ToolError


ERROR_WORDS = re.compile(r"error|fail", re.IGNORECASE)   # an engine line that reports the failure (engine_line)


def autochart_exit(error: BaseException) -> int:
    """autochart's exit code in its ToolError's first line (engines/autochart.py stays as it is), 0 when it gives
    none: a timeout, or another error."""
    m = AUTOCHART_EXIT.match(str(error))
    return int(m.group(1)) if m else 0


def engine_line(error: BaseException) -> str:
    """The engine's first error line in autochart's ToolError, for a CPU retry's reason: of the driver's last stderr
    lines it quotes (after its first line), the first that names an error or a failure, else the first of them, else
    the exit code; at most REASON_CHARS characters (cut with "...")."""
    first, _, rest = str(error).partition("\n")
    lines = [x.strip() for x in rest.splitlines() if x.strip()]
    line = next((x for x in lines if ERROR_WORDS.search(x)), lines[0] if lines else None)
    if line is None:
        code = autochart_exit(error)
        line = f"exit {code}" if code else first.strip()
    return line if len(line) <= REASON_CHARS else line[:REASON_CHARS - 3].rstrip() + "..."


# ac_headless.cjs's last word on a failed run, `log("FAILED: " + message)` before its exit 1, and the message of an
# engine (its child) that failed: "<difficulty>: engine failed (exit <code>[ <signal>]) <stage> <error>", the code
# null when a signal killed it
DRIVER_FAILED = re.compile(r"^\[autochart\] FAILED: (.+?)\s*$", re.MULTILINE)
ENGINE_FAILED = re.compile(r"[\w-]+: engine failed \(exit (?:(-?\d+)|null (SIG[A-Z0-9]+))\)")


def failure(error: BaseException) -> tuple[str, int, str]:
    """How a guitar take failed, from autochart's ToolError (engines/autochart.py and the driver stay as they are):
    (kind, signal number, the driver's FAILED line). The driver exits 1 whatever failed, so its FAILED line in the
    quoted stderr decides first (the last one there):
      "engine"  "engine failed (exit <int>) ...": the engine failed inside, as a GPU short of memory mid-take does
                (gpu_failed; the one failure run again on the CPU);
      "signal"  "engine failed (exit null SIG...)": the engine was killed, SIGKILL most likely by the kernel's OOM
                killer at WSL's memory limit (stopped; never run again);
      "driver"  any other: the driver's own kill (its wall-clock timeout, "no decoder progress", the token cap) or
                failure (models missing, takes without one beat map, ffmpeg; driver_failed: not a GPU failure,
                never run again).
    With no FAILED line there (the 8 lines quoted cut it off, or the driver itself was killed) the exit code decides
    as in v0.1: positive "engine", negative "signal". ("", 0, "") for the rest, a timeout of autochart.generate's
    own or an exit 0 with no summary, whose message stays autochart's."""
    text = str(error)
    lines = DRIVER_FAILED.findall(text) if AUTOCHART_EXIT.match(text) else []
    if lines:
        m = ENGINE_FAILED.match(lines[-1])
        if m and m.group(1) is not None:
            return "engine", 0, lines[-1]
        if m and m.group(2) in signal.Signals.__members__:
            return "signal", int(signal.Signals[m.group(2)]), lines[-1]
        return "driver", 0, lines[-1]
    code = autochart_exit(error)
    return ("engine", 0, "") if code > 0 else ("signal", -code, "") if code < 0 else ("", 0, "")


def take_failed(index: int | None, count: int | None, error: BaseException, device: str = "cuda",
                retried: bool = False) -> ToolError | None:
    """The error for a guitar take that failed, `index` of `count` (None when no take was running), on CUDA or, run
    again there after its CUDA run failed, on the CPU (`device`), by how it failed (`failure`): the engine failing
    inside gives gpu_failed on CUDA (`retried`: a take of this chart was run again on the CPU already) and
    retry_failed on the CPU; the engine killed by a signal, stopped; the driver's own failure, driver_failed. None
    for the rest, a timeout or an exit 0 with no summary, whose message stays autochart's own. A chart on the CPU
    does not call it: there autochart's message stays its own."""
    kind, signum, line = failure(error)
    if kind == "engine":
        return gpu_failed(index, count, error, retried) if device == "cuda" else retry_failed(index, count, error)
    if kind == "signal":
        return stopped(index, count, signum, error, device)
    if kind == "driver":
        return driver_failed(index, count, line, error, device)
    return None


def _take_clauses(index: int | None, count: int | None) -> tuple[str, str, str]:
    """take_failed's shared clauses: where (" in take k of n"), what is kept, and the Guitar takes 1 advice. Each
    holds for the next chart of the same file: a take's take.json is written once it finishes, so the takes that
    finished are kept and only the rest run again, and Guitar takes 1 reuses the first take when it finished on CUDA.
    "Kept" is left out for take 1, and the takes-1 advice when one take was asked for."""
    where = f" in take {index} of {count}" if index else ""
    kept = "; the takes that finished are kept" if index and index > 1 else ""
    one = "" if count == 1 else ", or set Guitar takes to 1 (it uses the first take if that one finished)"
    return where, kept, one


def gpu_failed(index: int | None, count: int | None, error: BaseException, retried: bool = False) -> ToolError:
    """A take whose engine failed on CUDA (take_failed) and is not run again on the CPU: what to do, in the page's
    words, then autochart's own lines; `retried`: because one take of this chart was run again on the CPU already
    (CPU_RETRIES), which it says. Device CPU makes the guitar's take again on the CPU (and the sections, whose cache
    key holds the device)."""
    where, kept, one = _take_clauses(index, count)
    again = " (one take was already run again on the CPU)" if retried else ""
    return ToolError(f"The guitar's GPU run failed{where}{again}{kept}. Close programs that use the GPU (games, Clone "
                     f"Hero, video) and chart it again{one}. If it fails again, set Device to CPU.\n\n{error}")


def retry_failed(index: int | None, count: int | None, error: BaseException) -> ToolError:
    """A take whose engine failed on CUDA and failed again when run again on the CPU (take_failed): the GPU's advice,
    without Device CPU (it just failed there too), then autochart's own lines of the CPU run."""
    where, kept, one = _take_clauses(index, count)
    return ToolError(f"The guitar's run failed{where} on the GPU and again on the CPU{kept}. Close programs that use "
                     f"the GPU (games, Clone Hero, video) and chart it again{one}.\n\n{error}")


def driver_failed(index: int | None, count: int | None, line: str, error: BaseException,
                  device: str = "cuda") -> ToolError:
    """A take whose driver failed by itself (take_failed; failure's "driver": its timeout, its stall or token kill,
    models missing, ...): not the GPU's doing, so no GPU advice: the driver's own line as the reason (at most
    REASON_CHARS characters; the CPU's run named for a take run again on the CPU), then autochart's own lines."""
    where, kept, _ = _take_clauses(index, count)
    run = "CPU run" if device == "cpu" else "run"
    why = line if len(line) <= REASON_CHARS else line[:REASON_CHARS - 3].rstrip() + "..."
    return ToolError(f"The guitar's {run} failed{where} ({why}){kept}.\n\n{error}")


def stopped(index: int | None, count: int | None, signum: int, error: BaseException,
            device: str = "cuda") -> ToolError:
    """A take whose engine was killed by signal `signum` (take_failed): that it was stopped (the CPU's run named, for
    a take run again on the CPU: `device`), and, for SIGKILL, that this usually means WSL ran out of memory (memory,
    not the GPU: Device CPU would not help), then what helps."""
    where, kept, one = _take_clauses(index, count)
    try:
        name = signal.Signals(signum).name
    except ValueError:
        name = "an unknown signal"
    why = ", which usually means WSL ran out of memory" if signum == 9 else ""   # SIGKILL (not on Windows)
    run = "CPU run" if device == "cpu" else "run"
    return ToolError(f"The guitar's {run} was stopped{where} (signal {signum}, {name}){why}{kept}. Close other "
                     f"programs (browsers, games, Clone Hero) and chart it again{one}.\n\n{error}")


def _mmss(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def playing_until(path: Path | str) -> float | None:
    """Where a stem (a WAV) stops playing: the end of its last 0.1-s frame within PLAYING_DB of its P95 level, as
    preview.py's gaps judge playing; None for a stem that cannot be read or is silent."""
    try:
        y, rate = A.read_wav(path)
    except (OSError, RuntimeError, ValueError):
        return None
    hop = max(1, rate // 10)
    n = y.shape[1] // hop
    if n == 0:
        return None
    frames = y.mean(axis=0)[:n * hop].reshape(n, hop)
    rms = np.sqrt(np.einsum("ij,ij->i", frames, frames) / hop)
    if not np.any(rms > 0):
        return None
    db = 20 * np.log10(np.maximum(rms, 1e-10))
    on = np.flatnonzero(db >= np.percentile(db, 95) + PLAYING_DB)
    return float((on[-1] + 1) * hop / rate) if on.size else None


def stitch_lines(seed: int, info: dict, song_s: float, playing: Callable[[], float | None]
                 ) -> tuple[list[str], list[str]]:
    """The log lines and warnings for a guitar take the engine cut short and autochart.generate continued (its
    summary's `stitch` record in `info`, engines/autochart.continue_take): a line per piece; the budget's warning
    (where the whole-song run stopped, why, in how many pieces the rest was transcribed and to where); and, when the
    continuation stopped short (a piece cut short again that advanced under ADVANCE_S, or the last of MAX_PIECES)
    and its last note is GUITAR_END_GAP_S or more before the guitar stem stops playing (`playing()`, called only
    then), where the guitar ends. Nothing for a take with no piece (no note at all)."""
    stitch = info.get("stitch") or {}
    pieces = stitch.get("pieces") or []
    if not pieces:
        return [], []
    run = (info.get("runs") or [{}])[0]
    why = (f"{run.get('nTokens')} tokens" if stitch.get("cut_short") == "tokens" else
           f"{run.get('nBeats')} beats" if stitch.get("cut_short") == "beats" else str(stitch.get("cut_short")))
    last = stitch.get("last_note_s") or 0.0
    lines = [f"guitar take seed {seed}: piece {k} of {len(pieces)}: audio from {_mmss(p['start_s'])}, kept from "
             f"{_mmss(p['keep_from_s'])}, last note at {_mmss(p['last_note_s'])} ({p.get('nTokens')} tokens, "
             f"{p.get('nBeats')} beats, {p.get('seconds') or 0:.0f} s" + (", cut short again)" if p.get("cut_short")
                                                                         else ")")
             for k, p in enumerate(pieces, 1)]
    warnings = [f"guitar take seed {seed}: the engine's budget ran out at {_mmss(stitch.get('cut_at_s') or 0.0)} of "
                f"{_mmss(song_s)} ({why}); the rest was transcribed in {len(pieces)} more "
                f"piece{'s' * (len(pieces) > 1)}, to {_mmss(last)}"]
    if stitch.get("ended") in ("stalled", "max_pieces"):
        end = playing()
        if end is not None and last <= end - GUITAR_END_GAP_S:
            warnings.append(f"guitar take seed {seed}: the guitar ends at {_mmss(last)} (the engine found nothing "
                            "after that): check the end of the chart")
    return lines, warnings


def take_seeds(takes: int) -> tuple[int, ...]:
    """The guitar takes' seeds: autochart's default seed, then 101, 202, ..."""
    from .engines.autochart import DEFAULT_SEED
    return (DEFAULT_SEED,) + tuple(EXTRA_SEED_STEP * k for k in range(1, takes))


# ------------------------------------------------------------------------------------------------ metadata

def parse_ffmetadata(text: str) -> dict[str, str]:
    """The global key=value pairs of ffmpeg's ffmetadata output (keys lower-cased; `\\` escapes =, ;, #, \\ and a
    newline), up to the first [SECTION]."""
    out: dict[str, str] = {}
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith("[") and line.rstrip().endswith("]"):
            break
        if not line or line[0] in ";#":
            continue
        while line.endswith("\\") and not line.endswith("\\\\") and i < len(lines):  # an escaped newline
            line = line[:-1] + "\n" + lines[i]
            i += 1
        key, value, escaped, seen = [], [], False, False
        for ch in line:
            if escaped:
                (value if seen else key).append(ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "=" and not seen:
                seen = True
            else:
                (value if seen else key).append(ch)
        k = "".join(key).strip().lower()
        if seen and k and k not in out:
            out[k] = "".join(value).strip()
    return out


def read_tags(path: Path | str, ffmpeg: str | None = None) -> dict[str, str]:
    """The file's tags: the container's, then its first audio stream's (Ogg keeps its comments there). A file
    ffmpeg cannot read gives none (its decode reports that)."""
    exe = ffmpeg or A.ffmpeg_exe()
    tags: dict[str, str] = {}
    for where in ("0", "0:s:a:0"):
        cmd = [exe, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(path), "-map_metadata", where,
               "-vn", "-an", "-sn", "-dn", "-f", "ffmetadata", "pipe:1"]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            continue
        for k, v in parse_ffmetadata(proc.stdout.decode("utf-8", "replace")).items():
            tags.setdefault(k, v)
    return tags


def _clean(v) -> str:
    """A value with its runs of white space as one space and none at either end ("" for None)."""
    return " ".join(str(v).split()) if v is not None else ""


def from_file_name(stem: str) -> dict[str, str]:
    """The artist and the title a file's stem gives when it reads "[<track number><sep>]<artist><sep><title>" (the
    module docstring; <sep> NAME_SEPARATOR): {"artist": the part before the first separator, "name": the part after
    the last one}, so "Artist - Album - Title" gives the artist and the title. A track number is one to three digits
    followed by a dot, a space or a separator ("01 - Artist - Title", "01. Artist - Title"); a number before the
    only separator is the artist ("311 - Amber"). A part blank after trimming is left out, so "- Title" gives the
    title alone; no separator: {}."""
    parts = [p.strip() for p in NAME_SEPARATOR.split(_clean(stem))]
    if len(parts) < 2:
        return {}
    first = TRACK_PREFIX.sub("", parts[0]).strip()
    if len(parts) > 2 and (TRACK_NUMBER.fullmatch(parts[0]) or not first):
        parts = parts[1:]   # a track number, then a separator: "01 - Artist - Title", "01. - Artist - Title"
    else:
        parts[0] = first
    return {key: value for key, value in (("artist", parts[0]), ("name", parts[-1])) if value}


def song_metadata(path: Path | str, tags: Mapping[str, str], overrides: Mapping[str, str | None]
                  ) -> tuple[dict[str, Any], dict[str, str]]:
    """assemble's metadata (name, artist, album, genre, year, charter, album_track when tagged) and where each
    value came from ("given", "tag <name>", "file name" or "default"). A blank value counts as not given. With no
    artist tag, the file's name gives the artist and the title the caller and the tags do not (`from_file_name`);
    else, or without a separator in it, the file's stem is the title, as before."""
    meta: dict[str, Any] = {}
    origin: dict[str, str] = {}

    for key, names in TAGS.items():
        given = _clean(overrides.get(key)) if key in OVERRIDES else ""
        if given:
            meta[key], origin[key] = given, "given"
            continue
        tag = next((n for n in names if _clean(tags.get(n))), None)
        if tag is None:
            continue
        value = _clean(tags[tag])
        if key == "year":
            m = re.search(r"\b(1[0-9]{3}|2[0-9]{3})\b", value)
            value = m.group(1) if m else value
        if key == "album_track":
            m = re.match(r"\s*(\d+)", value)
            if not m:
                continue
            value = int(m.group(1))
        meta[key], origin[key] = value, f"tag {tag}"
    tagged_artist = any(_clean(tags.get(n)) for n in TAGS["artist"])
    for key, value in ({} if tagged_artist else from_file_name(Path(path).stem)).items():
        if key not in meta:
            meta[key], origin[key] = value, "file name"
    if "name" not in meta:
        meta["name"], origin["name"] = Path(path).stem, "file name"
    for key, value in DEFAULTS.items():
        if key not in meta:
            meta[key], origin[key] = value.format(name=meta["name"]), "default"
    return meta, origin


# ------------------------------------------------------------------------------------------------ engines

def _has(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


class Engines:
    """The heavy stages, one method each; tests stand in for them. Each imports its engine when it runs."""

    def missing(self, options: Options) -> list[str]:
        """What the options need that is not installed, each with the fix."""
        problems = []
        try:
            A.ffmpeg_exe()
        except RuntimeError as e:
            problems.append(str(e))
        if not (_has("torch") and _has("demucs")):
            problems.append("stem separation needs torch and demucs: pip install songcharter[separate]")
        if "bass" in options.instruments and not _has("librosa"):
            problems.append("the bass engine needs librosa: pip install songcharter[bass]")
        if not _has("librosa"):  # even with allin1: its fallback, for when allin1 fails
            problems.append("sections need librosa (the fallback when allin1 is absent or fails): pip install "
                            "songcharter[sections]")
        if "guitar" in options.instruments:
            from .engines.autochart import find_install
            try:
                find_install()
            except FileNotFoundError as e:
                detail = str(e).removeprefix("autochart engine not ready: ")
                problems.append(f"the guitar needs autochart's engine ({detail}): set SONGCHARTER_AUTOCHART to its "
                                "install, or leave the guitar out with --instruments bass,drums")
        if options.device == "cuda" and _has("torch"):
            import torch

            from .separate import cuda_works
            works, why = cuda_works()
            if not works:
                problems.append(f"device cuda asked for, but torch {torch.__version__} here has no "
                                f"{'CUDA' if why is None else f'working CUDA ({why})'}: use --device auto or cpu")
        return problems

    def device(self, asked: str) -> tuple[str, str | None, str | None]:
        """The torch device the options mean, why it is the CPU (device.choose_device's sentence, else None), and
        the CUDA error when torch here has CUDA that did not run (else None): "auto" is CUDA only when a CUDA kernel
        runs (separate.cuda_works)."""
        return tuple(D.choose(asked))

    def free_gpu(self, device: str) -> None:
        """Empty torch's CUDA cache (between the stages that use it)."""
        if device == "cuda":
            import torch
            torch.cuda.empty_cache()

    def vram_reset(self, device: str) -> None:
        if device == "cuda":
            import torch
            torch.cuda.reset_peak_memory_stats()

    def vram_peak_mb(self, device: str) -> float | None:
        """torch's peak CUDA memory in this process since vram_reset, in MB; None off CUDA."""
        if device != "cuda":
            return None
        import torch
        return round(torch.cuda.max_memory_allocated() / 2 ** 20, 1)

    def threads(self, n: int | None) -> None:
        if n is not None:
            import torch
            torch.set_num_threads(n)

    def separate(self, mix: np.ndarray, cache_dir: Path, device: str) -> tuple[dict[str, np.ndarray], Path, dict]:
        """The stems, the folder holding them as <stem>.wav, and the separation's info."""
        from dataclasses import asdict

        from .separate import separate
        stems, info = separate(mix, device=device, cache_dir=cache_dir)
        return stems, cache_dir / info.key, asdict(info)

    def drums(self, mix: np.ndarray, drums: np.ndarray, out: Path, device: str) -> Run:
        from .engines import adtof as engine
        r = engine.generate(mix, drums, out, device=device)
        return Run(r.chart, r.cached, r.info)

    def bass(self, mix: np.ndarray, bass: np.ndarray, out: Path) -> Run:
        from .engines import bass as engine
        r = engine.generate(mix, bass, out)
        return Run(r.chart, r.cached, r.info)

    def sections(self, mix: np.ndarray, stems: Mapping[str, np.ndarray], out: Path, device: str,
                 threads: int | None) -> Run:
        from .engines.sections import Settings, find_sections
        r = find_sections(mix, stems, out, Settings(device=device, threads=threads))
        return Run(r.path, r.cached, r.info)

    def lyrics_missing(self) -> str | None:
        """Why the lyrics aligner cannot run here (torch or torchaudio missing), else None."""
        from .engines import lyrics as engine
        return engine.missing()

    def lyrics(self, vocals: np.ndarray, text: str, out: Path, device: str):
        """The text aligned to the vocal stem (engines/lyrics.align's Result); engines.lyrics.Unavailable when the
        aligner cannot run."""
        from .engines import lyrics as engine
        return engine.align(text, vocals, out, engine.Settings(device="cuda" if device == "cuda" else "cpu"))

    def preview_missing(self) -> str | None:
        """Why the preview cannot run here (matplotlib or librosa does not import), else None."""
        try:
            import librosa  # noqa: F401
            import matplotlib  # noqa: F401
        except Exception as e:  # noqa: BLE001  absent, or broken on import: either way no preview
            return f"{type(e).__name__}: {e}"
        return None

    def preview(self, folder: Path, out: Path, stems: Mapping[str, Path]) -> dict:
        """preview.py's overview and pages of the song folder `folder` in `out` (an earlier run's PNGs there go
        first), judged against `stems` (stem name -> WAV, input seconds; the lead-in pad from its report.json): what
        it wrote, flagged and remarked."""
        from . import preview as PV
        pv = PV.load(folder, stems=dict(stems))
        out.mkdir(parents=True, exist_ok=True)
        for old in [out / "overview.png", *out.glob("page_*.png")]:
            old.unlink(missing_ok=True)
        found = PV.render_overview(pv, out / "overview.png")
        pages = PV.render_pages(pv, out)
        kinds: dict[str, int] = {}
        for f in found:
            kinds[f.kind] = kinds.get(f.kind, 0) + 1
        return {"folder": str(folder), "overview": str(out / "overview.png"), "pages": [str(x) for x in pages],
                "stems": dict(pv.stems), "flags": [str(f) for f in found], "flags_by_kind": kinds,
                "remarks": PV.remarks(pv)}

    def guitar(self, audio: Path, out: Path, seeds: Sequence[int], device: str, title: str, artist: str,
               scratch: Path | None = None, on_take: Callable[[int, int, int], None] | None = None) -> list[Run]:
        """The takes in out/seed_<seed>/; autochart's scratch folder (its engine cache and jobs) is `scratch`, else
        out/work. `on_take` is autochart.generate's: (index from 1, count, seed) before each take that runs."""
        from .engines import autochart
        takes = autochart.generate(autochart.find_install(), audio, out, seeds, device=device, title=title,
                                   artist=artist, work=scratch, on_take=on_take)
        return [Run(t.chart, t.cached, {**t.summary, "seconds": t.seconds, "devices": t.devices}) for t in takes]


# ------------------------------------------------------------------------------------------------ the pipeline

def _peak_rss_mb() -> dict[str, float] | None:
    """Peak resident memory so far of this process, in MB; None where the OS does not report it (Windows). Not of
    its children: a child's ru_maxrss starts from its parent's peak at the time it was spawned, so RUSAGE_CHILDREN
    is never below this process's own size and cannot tell a small child from a large one. Children that report
    their own peak (allin1's runner) are recorded with their stage."""
    try:
        import resource
    except ImportError:
        return None
    scale = 1 if sys.platform == "darwin" else 1024   # ru_maxrss: bytes on macOS, KB elsewhere
    return {"self": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale / 2 ** 20, 1)}


def _expert_onsets(path: Path, instrument: str) -> int:
    """Onsets in the Expert part of the instrument in an engine's chart (0 when it has none)."""
    part = read_song(path).parts.get((instrument, "expert"))
    return len({n.time for n in part.notes}) if part else 0


def check_song(name: str, mix: np.ndarray) -> None:
    """An InputError for a decode too short to chart (under MIN_SONG_S) or silent (its peak under MIN_PEAK_DBFS),
    naming the file (`name`) and which it is."""
    seconds = mix.shape[-1] / SAMPLE_RATE
    if seconds < MIN_SONG_S:
        raise InputError(f"{name} is {seconds:.2f} s long: songcharter charts songs of {MIN_SONG_S:g} s or more")
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak < 10 ** (MIN_PEAK_DBFS / 20):
        level = "every sample is 0" if peak == 0 else (f"its peak is {20 * np.log10(peak):.1f} dBFS, under "
                                                      f"{MIN_PEAK_DBFS:g} dBFS")
        raise InputError(f"{name} is silent ({level}): there is nothing to chart")


def _decode(audio: Path, work: Path) -> tuple[np.ndarray, Path, bool]:
    """The decode, and work/decode.wav holding it (rewritten only when the samples differ from the last run's)."""
    mix = A.decode(audio, SAMPLE_RATE)
    key = hashlib.sha256(np.ascontiguousarray(mix, dtype="<f4").tobytes()).hexdigest()
    wav, meta = work / "decode.wav", work / "decode.json"
    try:
        old = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    if old.get("key") == key and wav.is_file() and wav.stat().st_size == old.get("bytes"):
        return mix, wav, True
    meta.unlink(missing_ok=True)
    part = work / "decode.part.wav"
    A.write_wav(mix, part, SAMPLE_RATE)
    os.replace(part, wav)
    meta.write_text(json.dumps({"source": str(audio), "key": key, "samples": int(mix.shape[1]),
                                "sample_rate": SAMPLE_RATE, "bytes": wav.stat().st_size}, indent=1),
                    encoding="utf-8")
    return mix, wav, False


def _transcriber(run: Run) -> str | None:
    """The device autochart's transcriber ran on for a guitar take, from its summary (None: not reported)."""
    return (run.info.get("devices") or {}).get("transcriber")


def _distinct_takes(runs: list[Run], warn: Callable[[str], None]) -> list[Run]:
    """The guitar takes without one whose Expert notes repeat an earlier take's (assemble refuses such a take:
    it always agrees with its twin); fewer than three distinct takes cannot be spliced, so then the first alone."""
    if len(runs) == 1:
        return runs
    kept, seen = [], []
    for r in runs:
        part = read_song(r.path).parts.get(("guitar", "expert"))
        notes = part.notes if part else []
        if any(notes == s for s in seen):
            warn(f"guitar take {r.path.parent.name} repeats an earlier take's notes: left out")
            continue
        kept.append(r)
        seen.append(notes)
    if len(kept) < 3:
        warn(f"only {len(kept)} distinct guitar takes: the first is used alone")
        return kept[:1]
    return kept


def chart(audio: Path | str, out: Path | str, options: Options = Options(), *, engines: Engines | None = None,
          log: Callable[[str], None] | None = None,
          sampler: Callable[[], D.Sampler] | None = D.Sampler,
          events: Callable[[dict], None] | None = None) -> ChartResult:
    """Chart the song file `audio` into the song folder `out` (the module docstring). Bad inputs and missing
    components raise (errors.InputError, errors.ToolError, OSError) before any audio work; a stage that fails for
    a reason the user can act on raises the same kinds, and any other exception is a bug; a build the gate fails
    does not raise: it is in <out>.failed and `ok` is False. `sampler` makes the memory sampler (device.Sampler;
    None: no sampling, as in tests). `events` gets the run's events (the module docstring)."""
    engines = engines or Engines()
    log = log or (lambda line: print(line, file=sys.stderr, flush=True))
    emit = events or (lambda event: None)
    options.check()
    audio, out = Path(audio).expanduser().resolve(), Path(out).expanduser().resolve()
    if not audio.is_file():
        raise FileNotFoundError(f"the song file {audio} does not exist" if not audio.exists()
                                else f"{audio} is not a file")
    root, budget = cache.cache_root().expanduser().resolve(), cache.budget_bytes()
    if options.work:   # the person's folder: autochart's scratch inside it, as before, and never pruned
        work, scratch, key = Path(options.work).expanduser().resolve(), None, None
    else:
        key = cache.file_key(audio)
        work, scratch = cache.work_folder(root, audio.stem, key), cache.scratch_folder(root, key)
    if work == out or out in work.parents or work in out.parents:
        raise InputError(f"the work folder {work} and the output {out} must be apart, neither inside the other")
    check_output(out)
    check_output(failed_folder(out))
    problems = engines.missing(options)
    if problems:
        raise ToolError("cannot chart: " + "; ".join(problems))
    pictures = ART.prepare(audio, options.album_art, options.background)   # a bad given image: before any audio work

    instruments = [i for i in INSTRUMENTS if i in options.instruments]
    # the quick engines first, so a failure there comes before the guitar's minutes
    order = ["decode", "separate"] + [i for i in ("drums", "bass") if i in instruments] + ["sections"]
    no_lyrics = engines.lyrics_missing() if options.lyrics is not None else None
    order += ["lyrics"] * (options.lyrics is not None and no_lyrics is None)
    order += ["guitar"] * ("guitar" in instruments) + ["assemble"]
    no_preview = engines.preview_missing() if options.preview else None
    order += ["preview"] * (options.preview and no_preview is None)
    emit({"event": "plan", "stages": list(order)})
    stages: list[Stage] = []
    warnings: list[str] = []
    fallbacks: list[dict] = []
    report: dict[str, Any] = {"songcharter": __version__, "input": str(audio), "output": str(out), "work": str(work),
                              "scratch": None if scratch is None else str(scratch), "cache_key": key,
                              "options": {**{k: v for k, v in options.__dict__.items() if k not in ("work", "lyrics")},
                                          "instruments": instruments, "metadata": dict(options.metadata),
                                          "lyrics": options.lyrics is not None,    # whether given; never the text
                                          "album_art": options.album_art is not None,   # whether given; no path
                                          "background": options.background is not None},
                              "art": pictures.record,
                              "versions": {"python": platform.python_version(), "numpy": np.__version__,
                                           "platform": platform.platform()},
                              "stages": [], "fallbacks": fallbacks}
    smp = sampler() if sampler is not None else None

    def warn(text: str) -> None:
        warnings.append(text)
        log(f"songcharter: warning: {text}")
        emit({"event": "warning", "text": text})

    def fallback(stage: str, frm: str, to: str, reason: str, *, warning: str | None = "") -> None:
        """Record a move to the CPU (or off the device asked for) and warn: `warning` is the line ("": "<stage>:
        <reason>"; None: recorded only)."""
        fallbacks.append({"stage": stage, "from": frm, "to": to, "reason": reason})
        emit({"event": "fallback", **fallbacks[-1]})
        if warning is not None:
            warn(warning or f"{stage}: {reason}")

    def on_gpu() -> str:
        return (report.get("device") or {}).get("chosen") or "cpu"   # the torch device, once it is chosen

    def begin(name: str, what: str) -> float:
        log(f"[{order.index(name) + 1}/{len(order)}] {name}: {what}")
        emit({"event": "stage_start", "stage": name, "index": order.index(name) + 1, "count": len(order),
              "detail": what})
        if smp is not None:
            smp.begin(name)
        if name != "guitar":   # a child process of its own: torch's peak here says nothing about it
            engines.vram_reset(on_gpu())
        return time.perf_counter()  # wall times are reported only; nothing depends on them

    def end(name: str, t0: float, cached: bool, detail: str, info: dict | None = None) -> Stage:
        s = Stage(name, round(time.perf_counter() - t0, 2), cached, detail, info or {})
        stages.append(s)
        memory = {} if name == "guitar" else {"torch_peak_vram_mb": engines.vram_peak_mb(on_gpu())}
        if smp is not None:
            memory.update(smp.end(name))
        report["stages"].append({"stage": s.name, "seconds": s.seconds, "cached": s.cached, "detail": s.detail,
                                 **s.info, "peak_rss_mb": _peak_rss_mb(), **memory})
        log(f"[{order.index(name) + 1}/{len(order)}] {name}: {detail}{' (cached)' if cached else ''}, "
            f"{s.seconds:.1f} s")
        emit({"event": "stage_end", "stage": name, "seconds": s.seconds, "cached": cached, "detail": detail})
        return s

    work.mkdir(parents=True, exist_ok=True)
    old = cache.read_marker(work)
    if options.work is None:   # a folder a --work run has used stays pinned
        cache.mark(work, audio, key, scratch, pinned=bool(old and old.get("pinned")))
    elif old is not None:      # a cache folder a --work run uses is the person's from now on; its scratch stays its
        cache.mark(work, audio, old.get("key"), Path(old["scratch"]) if old.get("scratch") else None, pinned=True)
    try:
        if smp is not None:
            smp.start()
        tags = read_tags(audio)
        meta, origin = song_metadata(audio, tags, options.metadata)
        report["metadata"], report["metadata_from"], report["tags"] = meta, origin, tags
        images = ART.write(pictures, work / "art")
        for text in pictures.warnings:
            warn(text)
        if options.lyrics is not None and no_lyrics is not None:
            warn(f"lyrics: not added ({no_lyrics})")
            report["lyrics"] = {"given": True, "added": False, "why": no_lyrics}
        parts, sections, stem_files, stem_folder, timed = _engine_stages(audio, work, scratch, options, engines, meta,
                                                                         begin, end, warn, fallback, report, emit,
                                                                         log)
        if not parts:
            raise InputError(f"no instrument has notes ({', '.join(instruments)} all came out empty): nothing to "
                             "chart")
        cfg = {"_about": f"written by songcharter {__version__} chart for {audio.name}",
               "audio": str(work / "decode.wav"), "stems": stem_files, "beat_hints": None, "lead_in": 2.5,
               "parts": parts, "sections": sections,
               "solos": (options.solos if isinstance(options.solos, str) else list(options.solos))
               if any(p["instrument"] == "guitar" for p in parts) else "off",
               "levels": [d for d in DIFFICULTIES if d in options.levels],
               "metadata": meta, "output": str(out),
               **{key: str(images[name]) for key, name in (("album_art", ART.ALBUM), ("background", ART.BACKGROUND))
                  if name in images}}
        config = work / "assemble.json"
        config.write_text(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        t0 = begin("assemble", "grid, parts, tiers, phrases, sections, gate")
        result = assemble(load_config(config, out), lyrics=timed, art=pictures.record)
        g = result.report["gate"]
        if timed is not None:
            report["lyrics"]["chart"] = result.report.get("lyrics")
        end("assemble", t0, False, f"gate {'OK' if result.ok else 'FAILED'} ({g['errors']} errors, "
            f"{g['warnings']} warnings), {result.folder}", {"ok": result.ok, "folder": str(result.folder)})
        report["assemble"] = {"config": str(config), "ok": result.ok, "folder": str(result.folder)}
        preview = None
        if "preview" in order:
            t0 = begin("preview", f"overview and pages of {result.folder.name} in {work / 'preview'}")
            try:
                preview = engines.preview(result.folder, work / "preview",
                                          {p.stem: p for p in sorted(stem_folder.glob("*.wav"))})
            except Exception as e:  # noqa: BLE001  the preview only informs: it never fails a chart
                warn(f"no preview: it failed ({type(e).__name__}: {e})")
                report["preview"] = {"ok": False, "error": f"{type(e).__name__}: {e}",
                                     "traceback": traceback.format_exc()}
            except KeyboardInterrupt:  # Ctrl+C: the build is in place already, so only the preview stops
                warn("no preview: interrupted")
                report["preview"] = {"ok": False, "skipped": "interrupted"}
            else:
                end("preview", t0, False, f"{preview['overview']} and {len(preview['pages'])} pages, "
                    f"{len(preview['flags'])} flags")
                report["preview"] = {"ok": True, **preview}
        elif options.preview:
            warn(f"no preview: it needs matplotlib and librosa ({no_preview}): pip install songcharter[preview]")
            report["preview"] = {"ok": False, "skipped": no_preview}
        else:
            report["preview"] = {"ok": False, "skipped": "turned off"}
        try:
            report["cache"] = cache.prune(root, budget, keep=[work], warn=warn)
        except OSError as e:  # the cache folder itself unreadable: the run is done all the same
            warn(f"the cache in {root} was not pruned ({type(e).__name__}: {e})")
        except KeyboardInterrupt:  # Ctrl+C: the build is in place; what a deletion left in the trash goes next time
            warn(f"the cache in {root} was not pruned (interrupted)")
        size = cache.tree_size(work) + (cache.tree_size(scratch) if scratch is not None else 0)
        report["work_bytes"] = size
        return ChartResult(result, stages, work, config, meta, warnings, preview, scratch, size, fallbacks,
                           report.get("lyrics"), pictures.record)
    except BaseException as e:
        report["error"] = f"{type(e).__name__}: {e}"
        report["traceback"] = traceback.format_exc()
        raise
    finally:
        if smp is not None:
            smp.stop()
        report["warnings"] = warnings
        report["total_seconds"] = round(sum(s.seconds for s in stages), 2)
        report["peak_rss_mb"] = _peak_rss_mb()
        (work / "pipeline.json").write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str) + "\n",
                                            encoding="utf-8")


def _engine_stages(audio: Path, work: Path, scratch: Path | None, options: Options, engines: Engines, meta: dict,
                   begin, end, warn, fallback, record: dict, emit: Callable[[dict], None],
                   log: Callable[[str], None] = lambda line: None
                   ) -> tuple[list[dict], str | None, dict[str, str], Path, Timed | None]:
    """Decode, separation and the engines: the assemble parts, the sections file, the stem files assemble reads,
    the folder of every stem (the preview's) and the timed lyrics (None without); `record` (pipeline.json) gets the
    device and why, the guitar takes chosen and why, each take's continuation, and the lyrics' counts; `fallback`
    records each move to the CPU; `emit` gets a `take` event before each guitar take that runs; `log` gets a line
    per piece of a guitar take that was continued. The audio arrays live only here, so they are freed before
    assemble reads its own."""
    t0 = begin("decode", audio.name)
    mix, wav, same = _decode(audio, work)
    end("decode", t0, same, f"{mix.shape[1] / SAMPLE_RATE:.2f} s of audio in {wav.name}",
        {"samples": int(mix.shape[1])})
    check_song(audio.name, mix)   # before the separation: a song too short or silent stops here

    device, why, cuda_error = engines.device(options.device)
    record["device"] = {"asked": options.device, "chosen": device, "reason": why}
    if options.device == "auto" and device == "cpu":   # no GPU at all: recorded, but nothing to warn about
        fallback("device", "cuda", "cpu", why, warning=None if why in (None, D.NO_GPU) else
                 f"CUDA does not run here ({cuda_error or why}): the models run on the CPU")
    engines.threads(options.threads)
    t0 = begin("separate", f"htdemucs_6s on {device}")
    stems, folder, info = engines.separate(mix, work / "stems", device)
    moved = info.get("fallback")
    if moved:
        fallback("separate", device, info.get("device") or "cpu", moved, warning=f"separation: {moved}")
    end("separate", t0, bool(info.get("cached")), f"{len(stems)} stems on {info.get('device', device)}",
        {"device": info.get("device"), "fallback": moved, "cuda_error": cuda_error, "key": info.get("key")})
    engines.free_gpu(device)
    stem_files = {s: str(folder / f"{s}.wav") for s in STEMS if s in stems}

    parts: list[dict] = []

    def take(instrument: str, run: Run, part: dict) -> int:
        n = _expert_onsets(run.path, instrument)
        if n == 0:
            warn(f"{instrument}: the engine found no notes (is the {instrument} silent?): the part is left out")
        else:
            parts.append(part)
        return n

    if "drums" in options.instruments:
        t0 = begin("drums", f"ADTOF on {device}")
        run = engines.drums(mix, stems["drums"], work / "drums", device)
        n = take("drums", run, {"instrument": "drums", "source": str(run.path)})
        end("drums", t0, run.cached, f"{n} Expert onsets", {"onsets": n})
        engines.free_gpu(device)
    if "bass" in options.instruments:
        t0 = begin("bass", "rule engine (HFC onsets, pYIN pitch)")
        run = engines.bass(mix, stems["bass"], work / "bass")
        n = take("bass", run, {"instrument": "bass", "source": str(run.path), "hopo": "forced"})
        end("bass", t0, run.cached, f"{n} Expert onsets", {"onsets": n})

    t0 = begin("sections", "allin1 when it is installed, else the librosa fallback")
    # allin1 runs in a Python of its own, whose CUDA missing() did not check: for "cuda" it is asked for "auto"
    # (CUDA when that Python has it, else the CPU), as the guitar stage leaves the CPU fallback to autochart
    run = engines.sections(mix, stems, work / "sections", "auto" if options.device == "cuda" else options.device,
                           options.threads)
    backend = run.info.get("backend", "?")
    how, child = backend, None
    if backend == "allin1":
        a = run.info.get("allin1") or {}
        how = f"allin1 {a.get('model', '')} on {a.get('device', '?')}".replace("  ", " ")
        child = None if run.cached else a.get("peak_rss_mb")  # a hit ran only the probe
        if a.get("fallback"):
            fallback("sections", "cuda", a.get("device") or "cpu", a["fallback"], warning=f"sections: {a['fallback']}")
        elif device == "cuda" and a.get("device") != "cuda":   # asked for, or "auto" found CUDA here
            fallback("sections", "cuda", a.get("device") or "cpu", "allin1 ran on the CPU (its Python has no working "
                     "CUDA)")
    elif run.info.get("why"):
        warn(f"sections: the librosa fallback ({run.info['why']})")
    n_seg = run.info.get("segments")
    end("sections", t0, run.cached, f"{how}, {n_seg} segments", {"backend": backend, "segments": n_seg,
                                                                  "child_peak_rss_mb": child})
    sections = str(run.path)
    timed = _lyrics_stage(options, engines, stems, work, device, begin, end, warn, fallback, record)
    if options.lyrics is not None:
        engines.free_gpu(device)

    if "guitar" in options.instruments:
        gdev = "cuda" if device == "cuda" else "cpu"
        n_takes, why = guitar_takes(options.takes, gdev)
        seeds = take_seeds(n_takes)
        # the CUDA default first runs one take alone: when autochart moved its transcriber off CUDA by itself (a
        # provider that failed to load), the other three would cost CPU minutes each; when its CUDA run failed and
        # it was run again on the CPU, the others could fail there too, with the one retry spent. Every take is a
        # call of its own (run_take), so that a take that fails on CUDA can be run again alone.
        probe = options.takes is None and n_takes > 1
        t0 = begin("guitar", f"autochart, {len(seeds)} take{'s' * (len(seeds) > 1)} (seed{'s' * (len(seeds) > 1)} "
                             f"{', '.join(map(str, seeds))}) on {gdev}" + (", the first alone first" if probe else ""))
        song_s = mix.shape[1] / SAMPLE_RATE
        del mix, stems   # autochart reads decode.wav; the arrays are not needed again

        retried: list[int] = []   # the seeds run again on the CPU after their CUDA run failed (at most CPU_RETRIES)

        def run_take(k: int) -> Run:
            """Take k (from 0) of `seeds`, a call of its own, whose `take` event is numbered among the stage's seeds
            (a take its cache answers sends none). On CUDA a failure inside the engine runs the take again on the
            CPU, once a chart (`cpu_retry`, the module docstring); any other failure, and the retry's own, says
            what to do (take_failed); on a CPU chart a failure stays autochart's."""
            seed, index, count = seeds[k], k + 1, len(seeds)

            def call(on: str) -> Run:
                def heard(_index: int, _count: int, seed: int) -> None:   # autochart's 1 of 1: this take's place
                    emit({"event": "take", "index": index, "count": count, "seed": seed,
                          **({"device": on} if on != gdev else {})})
                return engines.guitar(wav, work / "guitar", [seed], on, meta["name"], meta["artist"],
                                      scratch=scratch, on_take=heard)[0]

            try:
                return call(gdev)
            except ToolError as e:
                if gdev != "cuda":
                    raise
                if not (failure(e)[0] == "engine" and options.cpu_retry and len(retried) < CPU_RETRIES):
                    told = take_failed(index, count, e, retried=bool(retried))
                    if told is None:
                        raise
                    raise told from e
                failed = e
            line = engine_line(failed)
            retried.append(seed)
            fallback("guitar", "cuda", "cpu", f"take seed_{seed}: the CUDA run failed ({line}); run again on the CPU",
                     warning=f"guitar take seed {seed}: the GPU run failed ({line}): run again on the CPU, about one "
                             "transcription's time")
            try:
                return call("cpu")
            except ToolError as e:
                told = take_failed(index, count, e, "cpu")
                if told is None:
                    raise
                raise told from e

        runs = [run_take(0)]
        moved = None
        if probe and (retried or _transcriber(runs[0]) not in (None, gdev)):   # none reported: taken as on CUDA
            moved = "cpu" if retried else _transcriber(runs[0])
            if retried:   # its CUDA run failed: more takes there could fail too, with the retry spent
                warn(f"guitar: the first take was run again on the CPU (its GPU run failed): that take is used alone, "
                     f"not {n_takes - 1} more on the GPU")
                why = f"{why}; but the first take was run again on the CPU (its GPU run failed), so that take alone"
            else:
                fallback("guitar", gdev, moved, f"autochart's transcriber ran on {moved}, not {gdev}, for the first "
                         f"take ({runs[0].info.get('devices')}): that take is used alone")
                why = f"{why}; but autochart's transcriber ran on {moved} for the first take, so that take alone"
            n_takes, seeds = 1, seeds[:1]
        else:
            runs += [run_take(k) for k in range(1, len(seeds))]
        for seed, r in zip(seeds, runs, strict=True):
            used = (r.info.get("devices") or {})
            if (moved and seed == seeds[0]) or seed in retried:   # recorded already
                continue
            if gdev == "cuda" and used and any(v == "cpu" for v in used.values()):
                text = f"autochart ran on the CPU ({used})"
                if used.get("transcriber") == "cpu":
                    fallback("guitar", "cuda", "cpu", f"take {r.path.parent.name}: {text}",
                             warning=f"guitar take {r.path.parent.name}: {text}")
                else:   # another of its stages only (its separation or beat map): warned, as the take is not moved
                    warn(f"guitar take {r.path.parent.name}: {text}")
        heard: list[float | None] = []   # where the guitar stem stops playing, read once if a warning needs it

        def playing() -> float | None:
            if not heard:
                heard.append(playing_until(stem_files["guitar"]) if "guitar" in stem_files else None)
            return heard[0]

        stitches = [r.info.get("stitch") or {} for r in runs]
        for seed, r in zip(seeds, runs, strict=True):   # a take the engine cut short, continued in pieces
            lines, told = stitch_lines(seed, r.info, song_s, playing)
            for line in lines:
                log(line)
            for text in told:
                warn(text)
        record["takes"] = {"asked": options.takes, "takes": n_takes, "auto": options.takes is None, "why": why,
                           "seeds": list(seeds), "transcriber_moved_to": moved,
                           "devices": [_transcriber(r) for r in runs], "cpu_retries": list(retried),
                           "cut_short": [st.get("cut_short") for st in stitches],
                           "pieces": [len(st.get("pieces") or []) for st in stitches],
                           "last_note_s": [st.get("last_note_s") for st in stitches]}
        runs = _distinct_takes(runs, warn)
        n = _expert_onsets(runs[0].path, "guitar")
        part = {"instrument": "guitar", "source": str(runs[0].path), "hopo": "forced"}
        if len(runs) > 1:
            part["takes"] = [str(r.path) for r in runs[1:]]
        take("guitar", runs[0], part)
        end("guitar", t0, all(r.cached for r in runs), f"{len(runs)} take{'s' * (len(runs) > 1)}, {n} Expert onsets "
            "in the first", {"seeds": list(seeds), "takes": [str(r.path) for r in runs], "onsets": n,
                             "chosen": record["takes"]})
    parts.sort(key=lambda p: INSTRUMENTS.index(p["instrument"]))
    return parts, sections, stem_files, folder, timed


def _lyrics_stage(options: Options, engines: Engines, stems: Mapping[str, np.ndarray], work: Path, device: str,
                  begin, end, warn, fallback, record: dict) -> Timed | None:
    """The lyrics aligned to the vocal stem (the module docstring, 3b), or None: not given, the aligner missing (the
    pipeline has warned), or the alignment unavailable or failing (warned here). record["lyrics"] gets the counts,
    the confidence and the timings; no word. A failure records its type and where it happened, never its message,
    which could quote the text."""
    if options.lyrics is None or record.get("lyrics", {}).get("added") is False:
        return None
    from .engines.lyrics import Unavailable
    words = parse_lyrics(options.lyrics).words
    t0 = begin("lyrics", f"{words} words aligned to the vocal stem on {device}")
    entry: dict[str, Any] = {"given": True, "added": False, "words": words}
    record["lyrics"] = entry
    if "vocals" not in stems:
        entry["why"] = "no vocal stem"
        warn("lyrics: not added (the separation gave no vocal stem)")
        end("lyrics", t0, False, "not added: no vocal stem")
        return None
    try:
        run = engines.lyrics(stems["vocals"], options.lyrics, work / "lyrics", device)
    except Unavailable as e:
        entry["why"] = str(e)
        warn(f"lyrics: not added ({e})")
        end("lyrics", t0, False, "not added: the aligner is unavailable")
        return None
    except Exception as e:  # noqa: BLE001  the lyrics never fail a chart; the message could quote the text
        entry.update(why=f"the aligner failed: {type(e).__name__}", error=type(e).__name__,
                     where=[f"{Path(f.filename).name}:{f.lineno} {f.name}" for f in traceback.extract_tb(e.__traceback__)])
        warn(f"lyrics: not added ({entry['why']})")
        end("lyrics", t0, False, f"not added: {type(e).__name__}")
        return None
    info = run.info
    counts, conf = info.get("counts", {}), info.get("confidence", {})
    used = info.get("device", device)
    if used != device:
        fallback("lyrics", device, used, f"the aligner ran on {used}")
    entry.update(added=True, cached=run.cached, syllables=counts.get("syllables"), lines=counts.get("lines"),
                 unspelled_words=counts.get("unspelled_words"), markup_dropped=counts.get("markup_dropped"),
                 method=info.get("method", {}).get("name"), device=used, confidence=conf,
                 timings_s=info.get("timings_s"))
    if conf.get("low"):
        warn(f"lyrics: the alignment is unsure ({conf.get('why')}): check the lyrics' timing")
    end("lyrics", t0, run.cached, f"{words} words, median word score {conf.get('median')}",
        {"words": words, "confidence_median": conf.get("median")})
    return Timed(run.lyrics, tuple(run.starts))


def summary(result: ChartResult) -> str:
    """What the pipeline adds to assemble's summary: the art added (when any was), the preview's overview and its
    flags, the lyrics, the work folder and its size (autochart's scratch folder's included, and named when it
    exists), then the stage times."""
    lines = []
    added = [f"{r['file']} ({'the song file' if r['from'] == 'embedded' else r['from']})"
             for r in (result.art.get("album_art"), result.art.get("background")) if r and r.get("added")]
    if added:
        lines.append(f"art: {', '.join(added)}")
    if result.preview:
        kinds = ", ".join(f"{k} {n}" for k, n in result.preview["flags_by_kind"].items())
        lines.append(f"preview: {result.preview['overview']} and {len(result.preview['pages'])} pages "
                     f"({f'flagged: {kinds}' if kinds else 'nothing flagged'})")
    ly = result.lyrics
    if ly is not None:
        if ly.get("added"):
            c = ly.get("chart") or {}
            lines.append(f"lyrics: {ly.get('words')} words in {c.get('phrases')} phrases, median word score "
                         f"{(ly.get('confidence') or {}).get('median')}")
        else:
            lines.append(f"lyrics: not added ({ly.get('why')})")
    made = result.scratch is not None and result.scratch.is_dir()  # not made by a run without the guitar
    scratch = f"; autochart's scratch folder {result.scratch}" if made else ""
    lines.append(f"work folder: {result.work} ({cache.size_text(result.work_bytes)}{scratch})")
    total = sum(s.seconds for s in result.stages)
    lines.append("stages: " + ", ".join(f"{s.name} {s.seconds:.1f} s{' (cached)' if s.cached else ''}"
                                        for s in result.stages) + f"; total {total:.1f} s")
    return "\n".join(lines)
