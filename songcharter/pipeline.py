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

  * **Metadata.** The file's tags as ffmpeg prints them (title, artist, album, genre, date, track), the caller's
    values on top, and defaults for what scan-chart requires: the file's name for the title, "Unknown" for the
    rest. scan-chart's own defaults ("Unknown Artist", ...) count as missing, so they are not used.
  * **Before any audio work** the inputs are checked (the file exists, the output folder holds nothing a build does
    not write) and so is every component the instruments need: a missing one fails with what to install or set,
    never a traceback. Where DESIGN.md has a fallback the stage takes it and says so: sections fall back to
    librosa when allin1 is absent or fails; device "auto" takes CUDA only when a CUDA kernel runs here (else every
    model runs on the CPU, for device.choose_device's reason), separation moves to the CPU when CUDA runs out of
    memory, and allin1, which runs in a Python of its own, uses CUDA when that Python has it and the CPU when not,
    even for device "cuda". Every move to the CPU is a **fallback**: recorded (stage, from, to, reason) in
    pipeline.json's `fallbacks` and ChartResult.fallbacks, and warned about, but for device "auto" on a machine with
    no NVIDIA GPU at all (recorded only): "auto" choosing the CPU, separation's fallback, allin1 on the CPU while
    torch here runs on CUDA, and a guitar take whose transcriber autochart ran on the CPU.
  * **GPU memory.** On CUDA, torch's cache is emptied after the separation and after the drums, and each stage
    that runs in this process records torch's own peak (`torch_peak_vram_mb`: reset as it begins).
  * **Solos** ("labels" by default): every section the sections engine names "Solo" (allin1's solo label), within
    starpower.place_solos's rules (16 Expert onsets, 4 measures, at most 3 a song); a list of section names
    (`--solos "Solo 1,Solo 2"`) puts them exactly there instead. Not "stems", the label confirmed by the stems
    (vocals quiet, guitar loud), which the solo evaluation (DESIGN.md 2.10) found rejecting the very solos the
    friend confirmed on the test song (vocals active in 0.561 and 0.863 of their frames; the test allows 0.25), so
    it placed none there. With fold-0 sections (allin1 on the CPU) "labels" covers all of Solo 2 and the first half
    of Solo 1 and adds one span nobody has confirmed; with the ensemble CUDA runs it covers Solo 2 only. On the six
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

The heavy stages are the methods of `Engines`, so tests stand in for them; importing this module loads no model.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from . import __version__
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
SOLO_MODES = ("stems", "labels", "off")  # assemble's solos modes; a list of section names is the other kind
DEFAULTS = {"artist": "Unknown", "album": "Unknown", "genre": "Unknown", "year": "Unknown", "charter": "songcharter"}
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
    4 beat 3; on the owner's GPU 4 takes cost 3.41x the guitar stage (+5.75 min a song), worth it. On a CPU each take
    after the first is one more transcription, 217 s for the 6:52 test song on the dev container (DESIGN.md 5, M3), so
    3 more would add about 11 min for that small gain. 2 takes are never the default (two cannot outvote each other),
    nor 3 (+0.006 to +0.0105 over 1, below 4)."""
    if asked is not None:
        return asked, f"{asked} asked for"
    if device == "cuda":
        return CUDA_TAKES, (f"the default on cuda: {CUDA_TAKES} takes spliced gave +0.013 Expert F1@50 over 1, for "
                            "3.41x the guitar stage's time")
    return 1, "the default on the cpu: 1 take (each one more is another transcription there, about 3.6 min for a 7-min song)"


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


def song_metadata(path: Path | str, tags: Mapping[str, str], overrides: Mapping[str, str | None]
                  ) -> tuple[dict[str, Any], dict[str, str]]:
    """assemble's metadata (name, artist, album, genre, year, charter, album_track when tagged) and where each
    value came from ("given", "tag <name>" or "default"). A blank value counts as not given."""
    meta: dict[str, Any] = {}
    origin: dict[str, str] = {}

    def clean(v) -> str:
        return " ".join(str(v).split()) if v is not None else ""

    for key, names in TAGS.items():
        given = clean(overrides.get(key)) if key in OVERRIDES else ""
        if given:
            meta[key], origin[key] = given, "given"
            continue
        tag = next((n for n in names if clean(tags.get(n))), None)
        if tag is None:
            continue
        value = clean(tags[tag])
        if key == "year":
            m = re.search(r"\b(1[0-9]{3}|2[0-9]{3})\b", value)
            value = m.group(1) if m else value
        if key == "album_track":
            m = re.match(r"\s*(\d+)", value)
            if not m:
                continue
            value = int(m.group(1))
        meta[key], origin[key] = value, f"tag {tag}"
    if "name" not in meta:
        meta["name"], origin["name"] = Path(path).stem, "file name"
    for key, value in DEFAULTS.items():
        if key not in meta:
            meta[key], origin[key] = value, "default"
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
               scratch: Path | None = None) -> list[Run]:
        """The takes in out/seed_<seed>/; autochart's scratch folder (its engine cache and jobs) is `scratch`, else
        out/work."""
        from .engines import autochart
        takes = autochart.generate(autochart.find_install(), audio, out, seeds, device=device, title=title,
                                   artist=artist, work=scratch)
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
          sampler: Callable[[], D.Sampler] | None = D.Sampler) -> ChartResult:
    """Chart the song file `audio` into the song folder `out` (the module docstring). Bad inputs and missing
    components raise (errors.InputError, errors.ToolError, OSError) before any audio work; a stage that fails for
    a reason the user can act on raises the same kinds, and any other exception is a bug; a build the gate fails
    does not raise: it is in <out>.failed and `ok` is False. `sampler` makes the memory sampler (device.Sampler;
    None: no sampling, as in tests)."""
    engines = engines or Engines()
    log = log or (lambda line: print(line, file=sys.stderr, flush=True))
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

    instruments = [i for i in INSTRUMENTS if i in options.instruments]
    # the quick engines first, so a failure there comes before the guitar's minutes
    order = ["decode", "separate"] + [i for i in ("drums", "bass") if i in instruments] + ["sections"]
    no_lyrics = engines.lyrics_missing() if options.lyrics is not None else None
    order += ["lyrics"] * (options.lyrics is not None and no_lyrics is None)
    order += ["guitar"] * ("guitar" in instruments) + ["assemble"]
    no_preview = engines.preview_missing() if options.preview else None
    order += ["preview"] * (options.preview and no_preview is None)
    stages: list[Stage] = []
    warnings: list[str] = []
    fallbacks: list[dict] = []
    report: dict[str, Any] = {"songcharter": __version__, "input": str(audio), "output": str(out), "work": str(work),
                              "scratch": None if scratch is None else str(scratch), "cache_key": key,
                              "options": {**{k: v for k, v in options.__dict__.items() if k not in ("work", "lyrics")},
                                          "instruments": instruments, "metadata": dict(options.metadata),
                                          "lyrics": options.lyrics is not None},   # whether given; never the text
                              "versions": {"python": platform.python_version(), "numpy": np.__version__,
                                           "platform": platform.platform()},
                              "stages": [], "fallbacks": fallbacks}
    smp = sampler() if sampler is not None else None

    def warn(text: str) -> None:
        warnings.append(text)
        log(f"songcharter: warning: {text}")

    def fallback(stage: str, frm: str, to: str, reason: str, *, warning: str | None = "") -> None:
        """Record a move to the CPU (or off the device asked for) and warn: `warning` is the line ("": "<stage>:
        <reason>"; None: recorded only)."""
        fallbacks.append({"stage": stage, "from": frm, "to": to, "reason": reason})
        if warning is not None:
            warn(warning or f"{stage}: {reason}")

    def on_gpu() -> str:
        return (report.get("device") or {}).get("chosen") or "cpu"   # the torch device, once it is chosen

    def begin(name: str, what: str) -> float:
        log(f"[{order.index(name) + 1}/{len(order)}] {name}: {what}")
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
        if options.lyrics is not None and no_lyrics is not None:
            warn(f"lyrics: not added ({no_lyrics})")
            report["lyrics"] = {"given": True, "added": False, "why": no_lyrics}
        parts, sections, stem_files, stem_folder, timed = _engine_stages(audio, work, scratch, options, engines, meta,
                                                                         begin, end, warn, fallback, report)
        if not parts:
            raise InputError(f"no instrument has notes ({', '.join(instruments)} all came out empty): nothing to "
                             "chart")
        cfg = {"_about": f"written by songcharter {__version__} chart for {audio.name}",
               "audio": str(work / "decode.wav"), "stems": stem_files, "beat_hints": None, "lead_in": 2.5,
               "parts": parts, "sections": sections,
               "solos": (options.solos if isinstance(options.solos, str) else list(options.solos))
               if any(p["instrument"] == "guitar" for p in parts) else "off",
               "levels": [d for d in DIFFICULTIES if d in options.levels],
               "metadata": meta, "output": str(out)}
        config = work / "assemble.json"
        config.write_text(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        t0 = begin("assemble", "grid, parts, tiers, phrases, sections, gate")
        result = assemble(load_config(config, out), lyrics=timed)
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
                           report.get("lyrics"))
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
                   begin, end, warn, fallback, record: dict
                   ) -> tuple[list[dict], str | None, dict[str, str], Path, Timed | None]:
    """Decode, separation and the engines: the assemble parts, the sections file, the stem files assemble reads,
    the folder of every stem (the preview's) and the timed lyrics (None without); `record` (pipeline.json) gets the
    device and why, the guitar takes chosen and why, and the lyrics' counts; `fallback` records each move to the
    CPU. The audio arrays live only here, so they are freed before assemble reads its own."""
    t0 = begin("decode", audio.name)
    mix, wav, same = _decode(audio, work)
    end("decode", t0, same, f"{mix.shape[1] / SAMPLE_RATE:.2f} s of audio in {wav.name}",
        {"samples": int(mix.shape[1])})

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
        # provider that failed to load), the other three would cost CPU minutes each
        probe = options.takes is None and n_takes > 1
        t0 = begin("guitar", f"autochart, {len(seeds)} take{'s' * (len(seeds) > 1)} (seed{'s' * (len(seeds) > 1)} "
                             f"{', '.join(map(str, seeds))}) on {gdev}" + (", the first alone first" if probe else ""))
        del mix, stems   # autochart reads decode.wav; the arrays are not needed again
        runs = engines.guitar(wav, work / "guitar", seeds[:1] if probe else seeds, gdev, meta["name"], meta["artist"],
                              scratch=scratch)
        moved = None
        if probe:
            used = (runs[0].info.get("devices") or {}).get("transcriber")  # not reported: taken as on CUDA
            if used not in (None, gdev):
                moved = used
                fallback("guitar", gdev, used, f"autochart's transcriber ran on {used}, not {gdev}, for the first take "
                         f"({runs[0].info.get('devices')}): that take is used alone")
                n_takes, seeds = 1, seeds[:1]
                why = f"{why}; but autochart's transcriber ran on {used} for the first take, so that take alone"
            else:
                runs += engines.guitar(wav, work / "guitar", seeds[1:], gdev, meta["name"], meta["artist"],
                                       scratch=scratch)
        for r in runs[1 if moved else 0:]:
            used = (r.info.get("devices") or {})
            if gdev == "cuda" and used and any(v == "cpu" for v in used.values()):
                text = f"autochart ran on the CPU ({used})"
                if used.get("transcriber") == "cpu":
                    fallback("guitar", "cuda", "cpu", f"take {r.path.parent.name}: {text}",
                             warning=f"guitar take {r.path.parent.name}: {text}")
                else:   # another of its stages only (its separation or beat map): warned, as the take is not moved
                    warn(f"guitar take {r.path.parent.name}: {text}")
        record["takes"] = {"asked": options.takes, "takes": n_takes, "auto": options.takes is None, "why": why,
                           "seeds": list(seeds), "transcriber_moved_to": moved}
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
        warn(f"lyrics: the alignment is unsure (median word score {conf.get('median')}): check the lyrics' timing")
    end("lyrics", t0, run.cached, f"{words} words, median word score {conf.get('median')}",
        {"words": words, "confidence_median": conf.get("median")})
    return Timed(run.lyrics, tuple(run.starts))


def summary(result: ChartResult) -> str:
    """What the pipeline adds to assemble's summary: the preview's overview and its flags, the work folder and its
    size (autochart's scratch folder's included, and named when it exists), then the stage times."""
    lines = []
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
