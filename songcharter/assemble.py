"""Assembling a song: our own beat grid and tempo map, the best existing chart per instrument re-timed onto it, our
own difficulties, star power, fills and sections, and a Clone Hero folder that is checked before it is accepted.

`assemble(config)` runs the whole build from one config (a JSON file for `songcharter assemble`):

  0. **Inputs.** `check_inputs`: every file the config names exists, the sections file reads, the output folder holds
     only files this tool writes (a background.* only when the earlier build's report.json says it added it: else it
     is the person's, M5-12); then every part's source and takes are read (step 3's import), all before any audio
     work.
  1. **Audio.** One gapless decode of the input (audio.decode), the time reference for everything. Stems (WAV or
     FLAC at 44.1 kHz, separated from that decode) are read as they are and checked against it: the median lag over
     windows that correlate (>= 0.15) must be within 2 samples; stems quieter than -30 dB against the mix are not
     checked (the critique's rule). A failure warns.
  2. **Grid.** beatgrid.beat_grid on the drum stem (or the mix), with the optional bpm / first-beat hints and mode
     override. Beats the drums leave without evidence (a guitar-only intro) follow a second stem's onsets where they
     hold a clear 8th/16th phase (`grid_secondary`: by default the guitar stem, else "other"; none when the grid
     comes from the mix). A window whose tempo the grid does not follow (stats["tempo_check"]), and a stretch of 16
     or more beats that neither the drums nor the second stem time, are warned about. plan_lead_in puts silence in
     front so tick 0 is a measure line, and TempoMap.from_beats builds the map (3 ms). From here every input second
     t sits at t + pad_seconds on the map, and every stage is given the pad: the notes, the sections, the solo test
     and the audio all move by it together. Then the sections (allin1's segments, or an imported chart's; DESIGN.md
     2.5: under 4 measures merged, an allin1 segment over 16 split into parts of about 8), built here because a
     part's takes are spliced by them.
  3. **Parts.** Each part is read with importers.read_song (a .chart, a .mid or a song folder, with its song.ini)
     plus its `time_shift`. Its constant offset against our grid is measured on its Expert part
     (quantize.estimate_offset) and removed when trusted ("auto"), or set by hand. A part with `takes` (other runs
     of the same tool on the same audio; a take with the same Expert notes as another run is refused) gets its
     Expert spliced from all of them, section by section, by the takes' agreement (takes.splice, DESIGN.md 2.7),
     on windows at the section starts moved by that offset: the takes share the source's clock. Then quantize_part
     puts every taken difficulty on our grid. HOPOs: by default only the states the source forced are kept and the
     rest follow the natural rule on our grid (`HOPO_RULES`). The tools' own star power, fills and solos are
     dropped: ours replace them. Onsets before the part's own stem first plays or after it last plays are removed
     from every taken level (`active_span`, DESIGN.md 2.8: no notes after the stem stops; a part's `trim_silence`
     turns it off); an onset elsewhere where the stem is silent is only reported. Last, every taken level ends inside
     the audio (`clip_to_audio`): a note starting in song.ogg's last CLIP_MARGIN_S or after its end is dropped, a
     sustain running past that point is cut there, and one cut below its level's shortest sustain becomes a plain
     note (counted in report.json's `clipped`). The lower levels are reduced from the clipped Expert, so no written
     track has a note or a sustain end after the audio (the gate's noteAfterAudio).
  4. **Chart.** Star power, fills and (opt-in, or on the sections named in `solos`) solos on Expert
     (starpower.place_phrases); only the difficulties in `levels` are written. Then Hard, Medium and
     Easy, each reduced from the level above (reduce.py; with take_difficulties "all" the source's own levels, any
     missing one reduced from the level above), then every level's phrases fitted to its own notes
     (starpower.fit_chart). Easy drums get the drum stem's loudness per section. reduce.check_reductions and
     starpower.check_phrases run per instrument.
  5. **Folder.** package.build_song_folder writes notes.chart, song.ini (difficulty ratings from DESIGN.md 2.12,
     the preview at the first chorus) and song.ogg into a staging folder beside the output, and refuses a song.ogg
     more than a sample out of sync. The config's `album_art` and `background` images, when it names them, are copied
     in as album<ext> and background<ext> (the pipeline makes them: art.py); they change nothing else.
  6. **Gate** (`verify_folder`, DESIGN.md 2.13). scan-chart itself (`node tools/scan-chart/scan.cjs <folder>
     --notes`) must find the folder playable with no chart, metadata or folder issue but noAlbumArt, and its parsed
     notes must match the chart we built (`self_check`: onsets, times within 1 ms, lanes, HOPO, tap and cymbal
     states, sustains and phrases). The same self-check runs on notes.chart read back with importers.read_chart,
     and the read-back chart must pass scan-chart's chart rules as re-implemented here (`scan_rules`) with Encore's
     stricter numbers: first note at 2 s or later, sustains of 200 ms or more, sustain gaps of 60 ms or more.
     song.ini must hold the metadata scan-chart requires and a rating for every charted instrument, and the folder no
     other chart, ini or audio file. Without node or tools/scan-chart's node_modules, the re-implementation stands
     in for scan-chart and the gate warns that scan-chart was not run.
  * **Lyrics** (optional: `assemble(config, lyrics=...)`, the text with each syllable's start, which the pipeline
     aligns; never in the config, whose copy goes into report.json): each syllable is quantized onto the grid (on
     a doubled grid one slot level coarser, its 8ths: lyric_rules) and the phrases are written as phrase_start,
     lyric and phrase_end events in [Events] (lyrics.place, DESIGN.md 2.15). The gate reads them back from
     notes.chart (every event as written) and has scan-chart find them. report.json counts them and records the
     slots; it never holds a word.
  * **Art** (optional: `assemble(config, art=...)`, the pipeline's record of where its album art and background came
     from, art.prepare's): report.json's `art` says, for each, whether it was added, its file, and where it came from
     ("embedded", "given", or "config" when only the config named it).
  7. **Report.** report.json in the folder: the grid's stats, per-part offsets and what quantizing and trimming did,
     note counts per difficulty, phrases (and the share of drum fills that end on a crash), sections, ratings, the
     sync check, the gate (with scan-chart's verdict) and every warning. Times in the report are seconds of the
     input audio unless a key says otherwise.

The output folder is replaced only by a build that passes the gate. A build the gate fails goes to
`<output>.failed` for inspection, and `<output>` keeps what it held; a build that raises (bad input, song.ogg out of
sync) leaves both as they were.

The config (JSON; relative paths are relative to the config file, keys starting with "_" are ignored):

    {"audio": "input.wav",
     "stems": {"drums": "drums.wav", "bass": "bass.wav", "other": "other.wav", "vocals": "vocals.wav"},
     "beat_hints": {"bpm": 142.0009, "first_beat": 0.050},   (or null)
     "grid_mode": null,                                       ("free" or "click" overrides the choice)
     "grid_octave": "auto",                                   (1 or 2 forces the octave pass's choice)
     "grid_secondary": null,                                  (a stem name, "mix" or "none"; null: guitar, other)
     "lead_in": 2.5,
     "parts": [{"instrument": "guitar", "source": "autochart/notes.chart"},
               {"instrument": "drums", "source": "strum/notes.mid", "time_shift": 0.0697, "offset": "auto",
                "take_difficulties": "expert", "hopo": "forced", "trim_silence": true},
               {"instrument": "bass", "source": "run1/notes.chart", "takes": ["run2/notes.chart", "run3/notes.chart"]}],
     "sections": "allin1.json",                               (or "from:<part name>", or null)
     "solos": "off",                                          ("labels": every "Solo" section, the pipeline's
                                                               default; "stems": those the vocals and guitar stems
                                                               confirm; or a list of section names: ["Solo 1"])
     "levels": ["expert", "hard", "medium", "easy"],          (the difficulties written; Expert always)
     "album_art": "album.jpg", "background": "background.jpg",  (optional: .png, .jpg or .jpeg, copied as they are)
     "metadata": {"name": "...", "artist": "...", "album": "...", "genre": "...", "year": "2014",
                  "album_track": 2, "charter": "songcharter"},  (album, genre and year required; charter defaults)
     "output": "out/song"}
"""
from __future__ import annotations

import bisect
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

import numpy as np

from . import audio as A
from . import lyrics as L
from .beatgrid import (BPM_RANGE, FREE_SHARE, ONSET_TO_BEAT_MS, BeatGrid, OnsetFeatures, beat_grid, local_beats,
                       onset_features)
from .chart import DRUM_ACTIVATION, OPEN, STAR_POWER, Chart, DrumHit, FretNote, SongInfo, Track
from .errors import InputError, ToolError
from .importers import _chart_sections, _decode, read_chart, read_song
from .package import PackageResult, build_song_folder
from .quantize import (RULES, TRACK_DIFFICULTY, TRACK_INSTRUMENT, QuantizeReport, QuantizeRules, estimate_offset,
                       quantize_part, sustain_kept)
from .reduce import LEVELS, Issue, check_reductions, hopo_states, reduce_level
from .sections import read_allin1, sections_from_chart, sections_from_segments
from .starpower import check_phrases, fill_crash_share, fit_chart, place_phrases, stem_confirm
from .takes import splice
from .tempo import LeadIn, TempoMap, plan_lead_in
from .timed import DIFFICULTIES, INSTRUMENTS, TimedHit, TimedNote, TimedPart, TimedSong, TimedSpan

SAMPLE_RATE = A.SAMPLE_RATE
TEMPO_TOLERANCE = 0.003    # largest tempo-map error against the grid's beats (beatgrid's hand-off)
STEM_MAX_LAG = 2.0         # samples: a stem lines up with the mix when its median lag is within this ...
STEM_MIN_CORRELATION = 0.15  # ... over the windows that correlate at least this well,
STEM_QUIET_DB = -30.0      # and it is checked only when it is at least this loud against the mix
LEVEL_FRAME_S = 0.1        # frame of the stem levels (solo test, drum loudness)
MODE_MARGIN = 0.10         # a confident share this close to beatgrid's free/click threshold is warned about
GRID_LINE_BEATS = 16       # a stretch of this many beats that neither the drums nor the second stem time is warned
                           # about (under half of it timed)
SILENT_DB = 25.0           # a note where its stem stays this far below its P95 is in silence (a warning; Demucs
                           # stems leak at about 30-37 dB below their P95 where the instrument is silent)
SILENT_WINDOW = (-0.05, 0.20)  # seconds around an onset in which its stem must reach that level
TRIM_DB = 30.0             # onsets before the stem's first frame this loud against its P95, or after its last, are
                           # removed: the top of the leakage floor, so a quiet intro or fade-out keeps its notes
SECTION_MIN_MEASURES = 4   # DESIGN.md 2.5: sections under 4 measures merge,
SECTION_SPLIT_OVER = 16    # and an allin1 segment over 16 measures splits
SECTION_SPLIT_INTO = 8     # into parts of about 8
LEAD_S = 2.0               # Encore: no note in the first 2 s (scan-chart's smallLeadingSilence is 1 s)
SUSTAIN_MIN_MS = 200.0     # Encore's shortest sustain (scan-chart's babySustain: 100 ms)
SUSTAIN_GAP_MS = 60.0      # Encore's sustain gap (scan-chart's badSustainGap: 40 ms)
SCAN_BABY_SUSTAIN_MS = 100.0
SCAN_SUSTAIN_GAP_MS = 40.0
SCAN_BROKEN_NOTE_MS = 15.0
SELF_CHECK_S = 0.001       # read-back times must match ours this closely
# a note ends this long before song.ogg does (clip_to_audio). The gate's noteAfterAudio (scan_rules; our rule, as
# scan-chart 8.0.1 never measures the audio) fails a track whose last onset or sustain end, read back from
# notes.chart, lies after song.ogg's length in samples (the decode plus the lead-in pad) over 44.1 kHz. The read-back
# times may differ from ours by up to SELF_CHECK_S before the self-check fails the build anyway, so a note that ends
# SELF_CHECK_S before that length by our tempo map cannot trip the rule
CLIP_MARGIN_S = SELF_CHECK_S
# scan-chart 8.0.1 as DESIGN.md 2.13 runs it; $SONGCHARTER_SCAN_CHART names another scan.cjs
SCAN_CHART = Path(__file__).resolve().parent.parent / "tools" / "scan-chart" / "scan.cjs"
SCAN_CHART_TIMEOUT_S = 600.0
SCAN_ALLOWED = {"noAlbumArt"}  # the folder issue the gate accepts
# what a build writes: an output folder holding anything else is not replaced (it may be Clone Hero's Songs folder)
OUTPUT_FILES = {"notes.chart", "song.ini", "song.ogg", "album.png", "album.jpg", "album.jpeg", "background.png",
                "background.jpg", "background.jpeg", "report.json"}
# a background is ours only when the earlier build's report.json says it wrote it (`_ours`): v0.1 wrote none, so one
# in a folder it made is the person's, which a build refuses to replace, as v0.1 did (M5-12)
BACKGROUNDS = {"background.png", "background.jpg", "background.jpeg"}
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")   # album art and backgrounds as Clone Hero reads them
_HARMLESS_FILES = {"thumbs.db", "desktop.ini"}  # and names starting with "."; left where they are
FAILED_SUFFIX = ".failed"  # a build the gate fails goes to <output>.failed

CHART_INSTRUMENT = TRACK_INSTRUMENT                      # guitar -> Single, ...
PART_INSTRUMENT = {v: k for k, v in TRACK_INSTRUMENT.items()}  # Single -> guitar, ...
LEVEL_KEY = {v: k for k, v in TRACK_DIFFICULTY.items()}  # Expert -> expert, ...
STEMS_FOR = {"guitar": ("guitar", "other"), "bass": ("bass",), "drums": ("drums",)}  # a part's own stem
INI_REQUIRED = ("name", "artist", "album", "genre", "year", "charter")  # scan-chart's requiredProperties
INI_DIFF_KEY = {"Single": "diff_guitar", "DoubleBass": "diff_bass", "Drums": "diff_drums"}
# how a part's HOPO and strum states come across (quantize.QuantizeRules): "forced" keeps what the source's charter
# forced and lets the natural rule work on our grid, so a natural HOPO that only a wrong source tempo map made (8th
# notes on a half-tempo map) does not become a forced one; "source" reproduces every played state
HOPO_RULES = {"forced": replace(RULES, forced_only=True), "source": RULES,
              "natural": replace(RULES, source_hopo=False)}
# a source's ladder is its own: these reduction rules only warn on levels imported with take_difficulties "all"
_SOURCE_LADDER_KINDS = {"notNested", "ladder", "share", "hardNotThinned"}


# ------------------------------------------------------------------------------------------------ config

@dataclass(frozen=True)
class PartConfig:
    instrument: str                     # guitar, bass or drums: the part it becomes
    source: Path                        # a .chart, a .mid or a song folder (read with its folder's song.ini)
    source_instrument: str | None = None  # the source's part to take (default: instrument)
    time_shift: float = 0.0             # seconds added to every source time (a tool that trimmed the audio)
    offset: float | str = "auto"        # "auto": measured against our grid, removed when trusted; or seconds
    take_difficulties: str = "expert"   # "expert": Expert only, the rest reduced from it; "all": import every level
    hopo: str = "forced"                # "forced": keep the states the source forced, the rest natural on our grid;
                                        # "source": how the source plays every note; "natural": our grid's only
    name: str | None = None             # how `sections: "from:<name>"` names it (default: instrument)
    trim_silence: bool = True           # remove onsets before its stem first plays and after it last plays
    takes: tuple[Path, ...] = ()        # other runs of the same tool on the same audio: Expert is spliced from
                                        # all of them by their agreement (takes.py; with take_difficulties "expert")

    @property
    def key(self) -> str:
        return self.name or self.instrument

    @property
    def from_instrument(self) -> str:
        return self.source_instrument or self.instrument


@dataclass
class AssembleConfig:
    audio: Path
    output: Path
    parts: list[PartConfig]
    metadata: dict[str, Any]                       # SongInfo fields: name, artist, album, genre, year, ...
    stems: dict[str, Path] = field(default_factory=dict)
    bpm: float | None = None                       # beat hints for the start grid
    first_beat: float | None = None
    grid_mode: str | None = None                   # "free" or "click" overrides beat_grid's choice
    grid_octave: str | int = "auto"                # "auto": doubled when the notes are too dense for the grid
                                                   # (grid_octave, DESIGN.md 2.3); 1 or 2 forces it
    grid_source: str | None = None                 # a stem name or "mix" (default: the drum stem, else the mix)
    grid_secondary: str | None = None              # the stem drumless beats follow: a stem name, "mix", or "" for
                                                   # none (default: the guitar stem, else other; none from the mix)
    lead_in: float = 2.5                          # the first beat lands at least this late in song.ogg
    tempo_tolerance: float = TEMPO_TOLERANCE
    sections: str | None = None                    # an allin1 JSON, "from:<part name>", or None
    solos: str | tuple[str, ...] = "off"           # "off", "stems" (vocals quiet, lead loud), "labels", or the
                                                   # names of the sections that are solos (a person's choice)
    levels: tuple[str, ...] = DIFFICULTIES         # the difficulties written (Expert always; the rest reduced)
    album_art: Path | None = None                  # copied in as album<ext>
    background: Path | None = None                 # copied in as background<ext> (Clone Hero's song background)
    quality: float = 7.0                           # song.ogg Vorbis quality


_CONFIG_KEYS = {"audio", "output", "parts", "metadata", "stems", "beat_hints", "grid_mode", "grid_octave",
                "grid_source", "grid_secondary", "lead_in", "tempo_tolerance", "sections", "solos", "levels", "album_art",
                "background", "quality"}
_PART_KEYS = {f.name for f in fields(PartConfig)}
_METADATA_KEYS = {"name", "artist", "album", "genre", "year", "charter", "album_track", "preview_start_ms",
                  "loading_phrase"}


def _keys(d: dict, allowed: set[str], where: str) -> dict:
    if not isinstance(d, dict):
        raise InputError(f"{where} must be an object")
    d = {k: v for k, v in d.items() if not str(k).startswith("_")}
    unknown = sorted(set(d) - allowed)
    if unknown:
        raise InputError(f"unknown key(s) in {where}: {', '.join(unknown)}")
    return d


def _number(v, what: str, *, low: float | None = None, above: float | None = None, high: float | None = None,
            integer: bool = False) -> Any:
    """A JSON number (a bool is not one) in range, as a float (or an int with `integer`)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or (integer and v != int(v)):
        raise InputError(f"{what} must be {'a whole number' if integer else 'a number'}, not {v!r}")
    bounds = []
    if low is not None and v < low:
        bounds.append(f"at least {low}")
    if above is not None and v <= above:
        bounds.append(f"above {above}")
    if high is not None and v > high:
        bounds.append(f"at most {high}")
    if bounds:
        raise InputError(f"{what} must be {' and '.join(bounds)}, not {v!r}")
    return int(v) if integer else float(v)


def _string(v, what: str, optional: bool = False) -> str | None:
    """A non-empty JSON string (or null, when optional)."""
    if v is None and optional:
        return None
    if not isinstance(v, str) or not v.strip():
        raise InputError(f"{what} must be {'a string or null' if optional else 'a non-empty string'}, not {v!r}")
    return v


def _solos(v) -> str | tuple[str, ...]:
    """The solos setting: a mode name (lower case) or a non-empty list of section names (kept as written)."""
    if isinstance(v, list):
        if not v:
            raise InputError("solos as a list needs at least one section name")
        return tuple(_string(x, f"solos[{i}]") for i, x in enumerate(v))
    return _string(v, "solos").lower()


def _levels(v) -> tuple[str, ...]:
    """The difficulties to write, in DIFFICULTIES order; Expert is required (the others are reduced from it)."""
    if not isinstance(v, list) or not v:
        raise InputError(f"levels must be a non-empty list of difficulties, not {v!r}")
    names = [_string(x, f"levels[{i}]").lower() for i, x in enumerate(v)]
    bad = sorted(set(names) - set(DIFFICULTIES))
    if bad:
        raise InputError(f"levels: unknown difficulty {', '.join(bad)} (difficulties are {', '.join(DIFFICULTIES)})")
    if "expert" not in names:
        raise InputError("levels must include expert (the other levels are reduced from it)")
    return tuple(d for d in DIFFICULTIES if d in names)


def parse_config(data: dict, base: Path | str = ".", output: Path | str | None = None) -> AssembleConfig:
    """An AssembleConfig from the JSON object; relative paths are taken from `base`. `output` overrides the
    config's output folder (the CLI's --out). Every value is type- and range-checked here (an InputError naming the
    key); whether the files exist is `check_inputs`'s job."""
    base = Path(base)
    d = _keys(data, _CONFIG_KEYS, "the config")

    def path(p, what: str, optional: bool = False) -> Path | None:
        p = _string(p, what, optional)
        if p is None:
            return None
        p = Path(p).expanduser()
        return p if p.is_absolute() else base / p

    for key in ("audio", "parts", "metadata"):
        if key not in d:
            raise InputError(f"the config needs '{key}'")
    if output is None and "output" not in d:
        raise InputError("the config needs 'output' (or pass --out)")
    if not isinstance(d["parts"], list):
        raise InputError("parts must be a list of objects")
    parts = []
    for i, p in enumerate(d["parts"]):
        where = f"parts[{i}]"
        p = _keys(p, _PART_KEYS, where)
        if "instrument" not in p or "source" not in p:
            raise InputError(f"{where} needs 'instrument' and 'source'")
        offset = p.get("offset", "auto")
        if isinstance(offset, str) and offset.strip().lower() == "auto":
            offset = "auto"
        elif isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset):
            raise InputError(f"{where}.offset must be 'auto' or a number of seconds, not {offset!r}")
        takes = p.get("takes", [])
        if not isinstance(takes, list):
            raise InputError(f"{where}.takes must be a list of paths, not {takes!r}")
        if not isinstance(p.get("trim_silence", True), bool):
            raise InputError(f"{where}.trim_silence must be true or false, not {p['trim_silence']!r}")
        source_instrument = _string(p.get("source_instrument"), f"{where}.source_instrument", True)
        part = PartConfig(instrument=_string(p["instrument"], f"{where}.instrument").lower(),
                          source=path(p["source"], f"{where}.source"),
                          source_instrument=source_instrument.lower() if source_instrument else None,
                          time_shift=_number(p.get("time_shift", 0.0), f"{where}.time_shift"),
                          offset=offset if offset == "auto" else float(offset),
                          take_difficulties=_string(p.get("take_difficulties", "expert"),
                                                    f"{where}.take_difficulties").lower(),
                          hopo=_string(p.get("hopo", "forced"), f"{where}.hopo").lower(),
                          name=_string(p.get("name"), f"{where}.name", True),
                          trim_silence=p.get("trim_silence", True),
                          takes=tuple(path(t, f"{where}.takes[{j}]") for j, t in enumerate(takes)))
        if part.instrument not in INSTRUMENTS or part.from_instrument not in INSTRUMENTS:
            raise InputError(f"parts[{i}]: instruments are {', '.join(INSTRUMENTS)}")
        if (part.instrument == "drums") != (part.from_instrument == "drums"):
            raise InputError(f"parts[{i}]: drums come only from drums, and 5-fret parts only from 5-fret parts")
        if part.take_difficulties not in ("expert", "all"):
            raise InputError(f"parts[{i}]: take_difficulties is 'expert' or 'all'")
        if part.hopo not in HOPO_RULES:
            raise InputError(f"parts[{i}]: hopo is {', '.join(repr(k) for k in HOPO_RULES)}")
        if part.takes and part.take_difficulties != "expert":
            raise InputError(f"parts[{i}]: takes splice Expert only, so they need take_difficulties 'expert'")
        if len(part.takes) == 1:
            raise InputError(f"parts[{i}]: takes need at least two more runs (three in all) to agree on anything")
        runs = [part.source, *part.takes]  # a run listed twice always agrees with itself and outvotes the rest
        again = next((r for j, r in enumerate(runs) if r.resolve() in [q.resolve() for q in runs[:j]]), None)
        if again is not None:
            raise InputError(f"parts[{i}]: {again} is listed twice: the source and its takes must be different runs")
        parts.append(part)
    if not parts:
        raise InputError("the config has no parts")
    for attr in ("instrument", "key"):
        seen = [getattr(p, attr) for p in parts]
        dup = sorted({x for x in seen if seen.count(x) > 1})
        if dup:
            raise InputError(f"more than one part with {attr} {', '.join(dup)}")
    meta = _keys(d["metadata"], _METADATA_KEYS, "metadata")
    meta.setdefault("charter", "songcharter")
    for key in INI_REQUIRED:  # scan-chart's required song.ini values (missingValue)
        if meta.get(key) is None or meta.get(key) == "":
            raise InputError(f"metadata needs '{key}' (scan-chart requires it in song.ini)")
        if key == "year" and isinstance(meta[key], int) and not isinstance(meta[key], bool):
            meta[key] = str(meta[key])
        _string(meta[key], f"metadata.{key}")
    _string(meta.get("loading_phrase"), "metadata.loading_phrase", True)
    for key in ("album_track", "preview_start_ms"):  # scan-chart's integer values (invalidValue)
        if meta.get(key) is not None:
            meta[key] = _number(meta[key], f"metadata.{key}", low=0, integer=True)
    hints = d.get("beat_hints") or {}
    hints = _keys(hints, {"bpm", "first_beat"}, "beat_hints")
    bpm, first_beat = hints.get("bpm"), hints.get("first_beat")
    stems = d.get("stems") or {}
    if not isinstance(stems, dict):
        raise InputError("stems must be an object of stem name: path")

    def opt(key, default=None, **bounds):
        v = d.get(key, default)
        return None if v is None else _number(v, key, **bounds)

    octave = d.get("grid_octave", "auto")
    if isinstance(octave, str) and octave.strip().lower() == "auto":
        octave = "auto"
    elif isinstance(octave, bool) or not isinstance(octave, int) or octave not in (1, 2):
        raise InputError(f"grid_octave is 'auto', 1 or 2, not {octave!r}")
    secondary = _string(d.get("grid_secondary"), "grid_secondary", True)
    if secondary is not None and secondary.strip().lower() == "none":
        secondary = ""  # no second stem: drumless beats follow the line
    cfg = AssembleConfig(
        audio=path(d["audio"], "audio"), output=path(str(output) if output is not None else d["output"], "output"),
        parts=parts, metadata=meta, stems={str(k): path(v, f"stems.{k}") for k, v in stems.items()},
        bpm=None if bpm is None else _number(bpm, "beat_hints.bpm", above=0),
        first_beat=None if first_beat is None else _number(first_beat, "beat_hints.first_beat", low=0),
        grid_mode=d.get("grid_mode"), grid_octave=octave,
        grid_source=_string(d.get("grid_source"), "grid_source", True),
        grid_secondary=secondary, lead_in=opt("lead_in", 2.5, low=LEAD_S),
        tempo_tolerance=opt("tempo_tolerance", TEMPO_TOLERANCE, above=0),
        sections=_string(d.get("sections"), "sections", True), solos=_solos(d.get("solos", "off")),
        levels=_levels(d.get("levels", list(DIFFICULTIES))),
        album_art=path(d.get("album_art"), "album_art", True), background=path(d.get("background"), "background", True),
        quality=opt("quality", 7.0, low=0, high=10))
    for key in ("album_art", "background"):
        image = getattr(cfg, key)
        if image is not None and image.suffix.lower() not in IMAGE_SUFFIXES:
            raise InputError(f"{key} {image} is not a .png or .jpg")
    if cfg.grid_mode not in (None, "free", "click"):
        raise InputError("grid_mode is 'free', 'click' or null")
    if cfg.grid_source is not None and cfg.grid_source != "mix" and cfg.grid_source not in cfg.stems:
        raise InputError(f"grid_source {cfg.grid_source!r} is not 'mix' or one of the stems")
    if cfg.grid_secondary and cfg.grid_secondary != "mix" and cfg.grid_secondary not in cfg.stems:
        raise InputError(f"grid_secondary {cfg.grid_secondary!r} is not 'mix', 'none' or one of the stems")
    if isinstance(cfg.solos, str) and cfg.solos not in ("off", "stems", "labels"):
        raise InputError("solos is 'off', 'stems', 'labels' or a list of section names")
    if cfg.sections is not None and str(cfg.sections).startswith("from:"):
        if cfg.sections[5:] not in {p.key for p in parts}:
            raise InputError(f"sections {cfg.sections!r}: no part is named {cfg.sections[5:]!r}")
    elif cfg.sections is not None:
        cfg.sections = str(path(cfg.sections, "sections"))
    out = cfg.output.resolve()
    for p in parts:
        for what, src in [("source", p.source)] + [("take", t) for t in p.takes]:
            if out == (src.parent if src.suffix.lower() in (".chart", ".mid") else src).resolve():
                raise InputError(f"the output folder {cfg.output} holds part {p.key}'s {what}: it would be "
                                 "overwritten")
    return cfg


def load_config(path, output: Path | str | None = None) -> AssembleConfig:
    """The config in a JSON file (UTF-8, with or without a BOM); its relative paths are relative to the file."""
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except ValueError as e:  # not JSON, or not UTF-8
        raise InputError(f"{p} is not a JSON config: {e}") from e
    return parse_config(data, p.resolve().parent, output)


def _read_sections(path) -> list:
    """allin1's segments, a file that is not an allin1 result being a bad input."""
    try:
        return read_allin1(path)
    except (KeyError, TypeError, IndexError, ValueError) as e:
        raise InputError(f"sections {path}: not an allin1 result ({type(e).__name__}: {e})") from e


def failed_folder(output: Path) -> Path:
    """Where a build the gate fails is written: <output>.failed beside the output folder."""
    return output.with_name(output.name + FAILED_SUFFIX)


def _ours(folder: Path) -> set[str]:
    """The names (lower case) an earlier build in `folder` may have left there: OUTPUT_FILES but the backgrounds, and
    the background its report.json's `art` says it added, while the file there still has the size it recorded (a
    picture the person put in its place under the same name is theirs). A background nothing recorded is the
    person's."""
    names = OUTPUT_FILES - BACKGROUNDS
    try:
        record = json.loads((folder / "report.json").read_text(encoding="utf-8"))["art"]["background"]
        name = str(record.get("file")).lower()
        if record.get("added") is True and name in BACKGROUNDS:
            size = record.get("bytes")
            there = [p for p in folder.iterdir() if p.is_file() and p.name.lower() == name]
            if not isinstance(size, int) or all(p.stat().st_size == size for p in there):
                names |= {name}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):   # no record, or not one of ours
        pass
    return names


def _foreign(folder: Path) -> list[str]:
    """What an existing output folder holds that a build does not write (OS clutter such as Thumbs.db aside), or
    that no earlier build there wrote (a background.* of the person's: `_ours`)."""
    if not folder.is_dir():
        return []
    ours = _ours(folder) | _HARMLESS_FILES
    return sorted(p.name for p in folder.iterdir()
                  if not (p.is_file() and (p.name.lower() in ours or p.name.startswith("."))))


def check_inputs(cfg: AssembleConfig) -> None:
    """Raise before any work is done when a file the config names is missing, the sections file is not an allin1
    result, or the output folder (or <output>.failed) holds anything a build does not write: a build replaces what
    is there, and the folder given might be Clone Hero's Songs folder."""
    named = [("audio", cfg.audio)] + [(f"stem {k}", p) for k, p in sorted(cfg.stems.items())]
    named += [(f"part {p.key}'s source", p.source) for p in cfg.parts]
    named += [(f"part {p.key}'s take", t) for p in cfg.parts for t in p.takes]
    if cfg.sections is not None and not cfg.sections.startswith("from:"):
        named.append(("sections", Path(cfg.sections)))
    named += [(key, getattr(cfg, key)) for key in ("album_art", "background") if getattr(cfg, key) is not None]
    missing = [f"{what} {p}" for what, p in named if not p.exists()]
    if missing:
        raise FileNotFoundError(f"not found: {'; '.join(missing)}")
    for what, p in named:
        if not p.is_file() and not what.startswith("part "):  # a part's source may be a song folder
            raise InputError(f"{what} {p} is not a file")
    if cfg.sections is not None and not cfg.sections.startswith("from:"):
        _read_sections(cfg.sections)
    for folder in (cfg.output, failed_folder(cfg.output)):
        check_output(folder)


def check_output(folder: Path) -> None:
    """Raise when `folder` (an output, or its .failed) is a file or holds anything a build does not write."""
    folder = Path(folder)
    if folder.exists() and not folder.is_dir():
        raise InputError(f"the output {folder} is a file, not a folder")
    other = _foreign(folder)
    if other:
        raise InputError(f"{folder} holds what a build does not write ({', '.join(other[:5])}"
                         f"{', ...' if len(other) > 5 else ''}): give a new or empty folder as the output")


# ------------------------------------------------------------------------------------------------ result

@dataclass(frozen=True)
class GateIssue:
    """A problem found by the checks or the gate. Errors fail the build; warnings are reported."""
    instrument: str | None   # guitar, bass, drums; None for the whole chart or folder
    difficulty: str | None   # expert .. easy
    kind: str                # scan-chart's issue name where it has one, else ours
    message: str
    time: float | None = None  # seconds of input audio
    error: bool = True


@dataclass
class AssembleResult:
    folder: Path
    chart: Chart
    report: dict
    grid: BeatGrid
    lead: LeadIn
    package: PackageResult
    issues: list[GateIssue]

    @property
    def ok(self) -> bool:
        return not any(i.error for i in self.issues)


# ------------------------------------------------------------------------------------------------ audio helpers

def stem_alignment(mix: np.ndarray, stem: np.ndarray, sample_rate: int = SAMPLE_RATE) -> dict:
    """Whether a stem lines up with the mix: median lag (samples, + = stem late) over the windows where the stem
    correlates with the mix, and the stem's level against the mix (dB)."""
    rms = lambda x: float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))  # noqa: E731
    level = 20 * math.log10(max(rms(stem), 1e-12) / max(rms(mix), 1e-12))
    out = {"level_db": round(level, 2), "length_difference": int(stem.shape[-1] - mix.shape[-1])}
    if level < STEM_QUIET_DB:
        return {**out, "checked": False, "ok": True, "reason": f"quieter than {STEM_QUIET_DB:.0f} dB: not checked"}
    windows = A.measure_offset(mix, stem, sample_rate)
    good = [lag for _, lag, corr in windows if corr >= STEM_MIN_CORRELATION]
    if not good:
        return {**out, "checked": True, "ok": False, "windows": len(windows),
                "reason": f"no window correlates at {STEM_MIN_CORRELATION} or more"}
    lag = float(np.median(good))
    return {**out, "checked": True, "ok": abs(lag) <= STEM_MAX_LAG, "lag_samples": round(lag, 3),
            "windows": len(good), "correlation_median": round(float(np.median([c for *_, c in windows])), 3)}


def frame_levels(audio: np.ndarray, sample_rate: int = SAMPLE_RATE, frame_s: float = LEVEL_FRAME_S) -> np.ndarray:
    """RMS level (dB) of each frame of frame_s seconds from the audio's start, channels mixed."""
    x = audio.mean(axis=0) if audio.ndim == 2 else audio
    w = max(1, int(round(frame_s * sample_rate)))
    n = len(x) // w
    p = np.mean(np.square(x[:n * w].astype(np.float64).reshape(n, w)), axis=1)
    return 10 * np.log10(p + 1e-12)


def section_loudness(levels: np.ndarray, frame_s: float, sections: list[tuple[int, str]], tempo: TempoMap,
                     pad_seconds: float, duration: float) -> list[float]:
    """Mean power (dB) of `levels` over each section, the last running to `duration` (input seconds)."""
    starts = [tempo.tick_to_sec(t) - pad_seconds for t, _ in sections]
    out = []
    for a, b in zip(starts, starts[1:] + [duration]):
        i = max(0, int(a / frame_s))
        seg = levels[i:max(int(b / frame_s), i + 1)]
        out.append(round(float(10 * np.log10(np.mean(10 ** (seg / 10)))), 2) if len(seg) else -120.0)
    return out


def silent_onsets(times, levels: np.ndarray, frame_s: float, floor_db: float = SILENT_DB,
                  window: tuple[float, float] = SILENT_WINDOW) -> list[float]:
    """The onsets (input seconds) around which the stem never comes within floor_db of its P95 level."""
    floor = float(np.percentile(levels, 95)) - floor_db
    out = []
    for t in times:
        i, j = max(0, int((t + window[0]) / frame_s)), int((t + window[1]) / frame_s) + 1
        seg = levels[i:j]
        if not len(seg) or seg.max() < floor:
            out.append(round(float(t), 3))
    return out


def active_span(levels: np.ndarray, frame_s: float = LEVEL_FRAME_S, floor_db: float = TRIM_DB,
                window: tuple[float, float] = SILENT_WINDOW) -> tuple[float, float] | None:
    """The onsets (input seconds, [start, end)) that the stem's playing can explain: an onset before `start` has
    its whole window before the stem's first frame within floor_db of its P95, one at or after `end` its whole
    window after the last such frame (the silent_onsets test at the song's two edges). None for an empty stem."""
    if not len(levels):
        return None
    loud = np.flatnonzero(levels >= float(np.percentile(levels, 95)) - floor_db)
    return float(loud[0] * frame_s - window[1]), float((loud[-1] + 1) * frame_s - window[0])


def trim_silent_edges(tracks: dict[str, Track], levels: np.ndarray, tempo: TempoMap, pad: float,
                      frame_s: float = LEVEL_FRAME_S) -> tuple[dict[str, Track], dict[str, list[float]]]:
    """Every level of a part without the onsets outside its stem's active_span (DESIGN.md 2.8: no notes after the
    stem stops): a tool's notes in the silence before the instrument comes in or after it stops. The rule depends on
    time only, so levels nested before stay nested. Nothing is trimmed when Expert would lose every note (the stem
    is not this part's). Returns the tracks and the removed onsets (input seconds) per level that lost any."""
    span = active_span(levels, frame_s)
    if span is None:
        return tracks, {}
    out, removed = {}, {}
    for d, tr in tracks.items():
        inside = {k: span[0] <= tempo.tick_to_sec(k) - pad < span[1] for k in {n.tick for n in tr.notes}}
        gone = sorted(k for k, ok in inside.items() if not ok)
        out[d] = replace(tr, notes=[n for n in tr.notes if inside[n.tick]]) if gone else tr
        if gone:
            removed[d] = [_in_s(tempo, k, pad) for k in gone]
    if "expert" in out and not out["expert"].notes:
        return tracks, {}
    return out, removed


def last_tick_by(tempo: TempoMap, limit: float) -> int:
    """The last tick at or before `limit` seconds of the map."""
    k = math.floor(tempo.sec_to_tick(limit))
    while k > 0 and tempo.tick_to_sec(k) > limit:
        k -= 1
    while tempo.tick_to_sec(k + 1) <= limit:
        k += 1
    return k


def clip_to_audio(tracks: dict[str, Track], tempo: TempoMap, audio_end: float, margin: float = CLIP_MARGIN_S
                  ) -> tuple[dict[str, Track], dict[str, dict[str, int]]]:
    """Every level of a part ending inside the audio: no onset and no sustain end after `audio_end` - `margin`
    (seconds of the map: song.ogg's length). A note starting later is dropped; a sustain running later ends on the
    last tick before that, unless that leaves it shorter than its level's shortest sustain (quantize.sustain_kept:
    max(200 ms, 0.75 beat) on Expert and Hard, 1 and 2 beats on Medium and Easy), when the note keeps no sustain.
    Returns the tracks and, per level, the onsets dropped and the sustains clipped and removed."""
    last = last_tick_by(tempo, audio_end - margin)
    out, counts = {}, {}
    for d, tr in tracks.items():
        dropped = {n.tick for n in tr.notes if n.tick > last}
        notes, clipped, removed = [], 0, 0
        for n in tr.notes:
            if n.tick > last:
                continue
            if isinstance(n, FretNote) and n.length > 0 and n.tick + n.length > last:
                if sustain_kept(tempo, n.tick, last, d):
                    n, clipped = replace(n, length=last - n.tick), clipped + 1
                else:
                    n, removed = replace(n, length=0), removed + 1
            notes.append(n)
        out[d] = replace(tr, notes=notes) if dropped or clipped or removed else tr
        counts[d] = {"onsets_dropped": len(dropped), "sustains_clipped": clipped, "sustains_removed": removed}
    return out, counts


# ------------------------------------------------------------------------------------------------ the grid's octave

# DESIGN.md 2.3, the octave pass (doubling only): a grid whose 1/16 slots cannot hold the notes is an octave too slow
OCTAVE_SHORT = 0.75        # an interval between onsets is short under this share of a 1/16 of its beat: the ones
                           # the quantizer would merge, move or drop (its `separate` is 0.75 slot)
OCTAVE_SHARE = 0.35        # the grid doubles when this share of the intervals, pooled over the parts, is short
                           # (0.199 the most on a right grid, 0.527 and 0.623 at half tempo: the eleven songs of
                           # DESIGN.md 2.3; M5-01's 0.35 kept over the midpoint 0.32, nearer the right grids) ...
OCTAVE_MAX_BPM = 300.0     # ... and the doubled tempo is at most Magma's 300 BPM ...
OCTAVE_MIN_ONSETS = 200    # ... and the parts have this many distinct onsets in all
BACKBEAT_WINDOW_S = 0.035  # the backbeat ratio, recorded but not a test (M5-11: 0.19 on a song at half tempo,
                           # 0.172 on a right grid): the snare band's peak within this of a beat line or a midpoint
BACKBEAT_MIN_BEATS = 16    # confident beats the backbeat ratio needs (fewer: none)
DOUBLED_BASS_SLOTS = (2, 0)  # straight and triplet slots per beat for the bass on a doubled grid: its 8ths only,
                             # so its scattered onsets get the first grid's 16ths. No triplet slots (M6-02, DESIGN.md
                             # 2.6): its 8ths 40-50 ms off read as triplets there, and the humans chart these basses
                             # in straight 8ths and 16ths (0 and 0.4 % triplets on the two songs' primaries)
DOUBLED_LYRIC_SLOTS = (2, 3)  # the doubled grid's 8ths and their triplets for the lyrics (lyric_rules, DESIGN.md
                              # 2.15; the triplets are the first grid's 16th-note triplets): the aligner's word starts
                              # run up to 75 ms early on a fast song, which the doubled grid's 16ths (75 ms at 200
                              # BPM) put a 1/16 before the human's, where the first grid's 16ths put them on it
OCTAVE_EVIDENCE_MIN = 0.7  # the doubled grid is kept when its confident share is at least this times the first's
                           # (PROVISIONAL, M5-01's open question: 0.5 is no evidence between the first grid's beats)


@dataclass(frozen=True)
class OctaveRules:
    short: float = OCTAVE_SHORT
    share: float = OCTAVE_SHARE
    max_bpm: float = OCTAVE_MAX_BPM
    min_onsets: int = OCTAVE_MIN_ONSETS
    window_s: float = BACKBEAT_WINDOW_S
    min_beats: int = BACKBEAT_MIN_BEATS
    evidence_min: float = OCTAVE_EVIDENCE_MIN


OCTAVE_RULES = OctaveRules()


def short_intervals(onsets, beats: np.ndarray, short: float = OCTAVE_SHORT) -> tuple[int, int]:
    """(short, intervals): the intervals between consecutive distinct onsets, and how many are shorter than `short`
    of a 1/16 of the beat the earlier onset falls in (the first or last beat's outside the grid)."""
    t = np.unique(np.asarray(onsets, dtype=np.float64))
    b = np.asarray(beats, dtype=np.float64)
    if len(t) < 2 or len(b) < 2:
        return 0, max(len(t) - 1, 0)
    j = np.clip(np.searchsorted(b, t[:-1], "right") - 1, 0, len(b) - 2)
    ibi = b[j + 1] - b[j]
    return int(np.sum(np.diff(t) < short * ibi / 4)), int(len(t) - 1)


def backbeat_ratio(features: OnsetFeatures, beats: np.ndarray, window_s: float = BACKBEAT_WINDOW_S,
                   min_beats: int = BACKBEAT_MIN_BEATS, onset_to_beat_ms: float = ONSET_TO_BEAT_MS
                   ) -> tuple[float | None, int]:
    """(ratio, beats used): the snare band's peak power within +-window_s of each beat's midpoint (its 8th line)
    over that of the beat line, as medians over the beats with confident drum evidence (beatgrid.local_beats). The
    band powers are read at the beats' onset times (the beats minus onset_to_beat_ms), where beatgrid's bar phase
    reads them. Over 1: the snare lands between the grid's beats (a grid at half the pulse); under 1: on them. None
    with fewer than min_beats confident beats."""
    u = np.asarray(beats, dtype=np.float64) - onset_to_beat_ms / 1000.0
    if len(u) < 2:
        return None, 0
    fps, snare = features.fps, features.snare
    hw = int(round(window_s * fps))

    def peak(t: np.ndarray) -> np.ndarray:
        c = np.round(t * fps).astype(int)
        return np.array([snare[max(0, i - hw):max(0, min(len(snare), i + hw + 1))].max(initial=0.0) for i in c])

    use = local_beats(features, u).confident[:-1]
    if use.sum() < min_beats:
        return None, int(use.sum())
    lines, mids = peak(u[:-1][use]), peak(0.5 * (u[:-1] + u[1:])[use])
    return float(np.median(mids) / max(float(np.median(lines)), 1e-12)), int(use.sum())


def grid_octave(onsets_by_part: dict[str, Any], beats: np.ndarray, features: OnsetFeatures | None,
                rules: OctaveRules = OCTAVE_RULES) -> tuple[int, dict]:
    """(octave, stats): 2 when the grid is an octave too slow for the notes, else 1 (DESIGN.md 2.3; halving is not
    built). onsets_by_part: each charted part's distinct Expert onset times (input seconds, before quantizing);
    beats: the grid's beats (input seconds); features: the drum stem's OnsetFeatures, None without drums.

    The density test: per part, the share of intervals between onsets shorter than `rules.short` of a 1/16 of
    their beat (short_intervals), pooled weighted by the parts' onset counts. The octave is 2 when the pooled share
    is at least `rules.share`, the grid's median tempo doubled is at most `rules.max_bpm` and the parts have at least
    `rules.min_onsets` onsets; stats["reason"] says which test decided. The backbeat ratio (backbeat_ratio; None
    without drums or with too few confident beats) is recorded in the stats (and a doubling's reason) but decides
    nothing (M5-11: a song at half tempo with its snare on the first grid's lines has a ratio as low as a right
    grid's)."""
    parts, n_all, weighted = {}, 0, 0.0
    for name, times in onsets_by_part.items():
        n = len(np.unique(np.asarray(times, dtype=np.float64)))
        short, intervals = short_intervals(times, beats, rules.short)
        share = short / intervals if intervals else 0.0
        parts[name] = {"onsets": n, "intervals": intervals, "short": short, "share": round(share, 4)}
        n_all += n
        weighted += n * share
    pooled = weighted / n_all if n_all else 0.0
    ratio, used = backbeat_ratio(features, beats, rules.window_s, rules.min_beats) if features is not None \
        else (None, 0)
    bpm = 60.0 / float(np.median(np.diff(beats))) if len(beats) > 1 else 0.0
    why_not = []
    if pooled < rules.share:
        why_not.append(f"{pooled:.1%} of intervals under {rules.short} of a 16th (under {rules.share:.1%})")
    if 2 * bpm > rules.max_bpm:
        why_not.append(f"{2 * bpm:.1f} BPM doubled is over {rules.max_bpm:.0f}")
    if n_all < rules.min_onsets:
        why_not.append(f"{n_all} onsets (under {rules.min_onsets})")
    octave = 1 if why_not else 2
    backbeat = "no drums" if features is None else ("too few confident beats" if ratio is None
                                                    else f"backbeat {ratio:.2f}")
    reason = "; ".join(why_not) if why_not else (
        f"{pooled:.1%} of intervals under {rules.short} of a 16th (at least {rules.share:.1%}), {backbeat}")
    stats = {"octave": octave, "reason": reason, "parts": parts, "onsets": n_all, "pooled_share": round(pooled, 4),
             "backbeat_ratio": None if ratio is None else round(ratio, 4), "backbeat_beats": used,
             "bpm": round(bpm, 4), "thresholds": {"short": rules.short, "share": rules.share,
                                                  "max_bpm": rules.max_bpm, "min_onsets": rules.min_onsets}}
    return octave, stats


# ------------------------------------------------------------------------------------------------ ratings

def _window_nps(times: np.ndarray, w: float) -> float:
    best, j = 0, 0
    for i in range(len(times)):
        while times[i] - times[j] >= w:
            j += 1
        best = max(best, i - j + 1)
    return best / w


def difficulty_rating(track: Track, tempo: TempoMap) -> tuple[int, dict]:
    """The song.ini rating (0-6) of an Expert track, DESIGN.md 2.12's linear models on its onsets: notes per second
    (average, and the busiest 1 s and 10 s), and on 5-fret guitar the shares of onsets that move lanes, are HOPOs
    or taps, and are chords. Returns (rating, features)."""
    ticks = sorted({n.tick for n in track.notes})
    if len(ticks) < 2:
        return 0, {}
    t = np.array([tempo.tick_to_sec(k) for k in ticks])
    dur = max(t[-1] - t[0], 1e-9)
    f = {"avg_nps": len(t) / dur, "max_nps_1s": _window_nps(t, 1.0), "max_nps_10s": _window_nps(t, 10.0)}
    if track.is_drums:
        value = -0.63 + 0.325 * f["avg_nps"] + 0.178 * f["max_nps_1s"]
    elif track.instrument == "DoubleBass":
        value = -0.79 + 0.343 * f["avg_nps"] + 0.306 * f["max_nps_1s"]
    else:
        frets: dict[int, set] = {}
        for n in track.notes:
            frets.setdefault(n.tick, set()).update(n.frets)
        top = [max((x for x in frets[k] if x != OPEN), default=-1) for k in ticks]
        states = hopo_states(track.notes, tempo.resolution)
        f["move"] = float(np.mean(np.diff(top) != 0))
        f["hopo"] = float(np.mean([states[k] for k in ticks]))
        f["chord"] = float(np.mean([len(frets[k] - {OPEN}) >= 2 for k in ticks]))
        value = (-2.49 + 0.278 * f["avg_nps"] + 0.105 * f["max_nps_1s"] + 0.268 * f["max_nps_10s"]
                 + 2.04 * f["move"] + 2.01 * f["hopo"] + 0.73 * f["chord"])
    f = {k: round(v, 4) for k, v in f.items()}
    f["value"] = round(value, 3)
    return int(np.clip(round(value), 0, 6)), f


# ------------------------------------------------------------------------------------------------ gate

def _onset_groups(part: TimedPart) -> list[tuple[float, list]]:
    """A read-back part's onsets: (time, notes at it), in time order."""
    groups: dict[float, list] = {}
    for n in part.notes:
        groups.setdefault(n.time, []).append(n)
    return sorted(groups.items())


def _inside(times: list[float], a: float, b: float) -> bool:
    """Whether any onset lies in the half-open span [a, b) (a zero-length span holds the note on its start)."""
    return any(a - 1e-9 <= t < (b if b > a + 1e-9 else a + 1e-6) - 1e-9 for t in times)


def scan_rules(song: TimedSong, pad_seconds: float = 0.0, audio_end: float | None = None,
               tempo: TempoMap | None = None) -> list[GateIssue]:
    """scan-chart's chart issues (its findChartIssues), and Encore's stricter numbers, on a chart as read back.

    song: the read-back chart, times on the chart's (padded) timeline; issue times are given in input seconds
    (minus pad_seconds). audio_end: song.ogg's length on that timeline; a track whose last onset or sustain end lies
    after it is an error (noteAfterAudio: our own rule, as scan-chart 8.0.1 never measures the audio; assemble clips
    every track to stay CLIP_MARGIN_S inside it, clip_to_audio). tempo: our map,
    for isDefaultBPM. Not covered: misalignedTimeSignature (TempoMap cannot write one), badEndEvent (we write no end
    event) and the 6-fret and flex-lane rules (we write neither).
    """
    issues: list[GateIssue] = []

    def add(inst, diff, kind, message, time=None, error=True):
        issues.append(GateIssue(inst, diff, kind, message, None if time is None else round(time - pad_seconds, 3),
                                error))

    if not any(p.notes for p in song.parts.values()):
        add(None, None, "noNotes", "the chart has no notes")
    by_inst: dict[str, dict[str, TimedPart]] = {}
    for (inst, diff), p in song.parts.items():
        by_inst.setdefault(inst, {})[diff] = p
    for inst, parts in by_inst.items():
        if "expert" not in parts:
            add(inst, None, "noExpert", "lower difficulties without Expert")
            continue
        ex = parts["expert"].notes
        for diff, p in parts.items():
            if diff != "expert" and p.notes == ex and len(_onset_groups(p)) > 20:
                add(inst, diff, "difficultyNotReduced", "identical to Expert")
    if tempo is not None and len(tempo.tempos) == 1 and tempo.tempos[0].bpm_milli == 120000 \
            and len(tempo.time_signatures) == 1 and tempo.time_signatures[0].numerator == 4:
        add(None, None, "isDefaultBPM", "one 120 BPM marker and one 4/4 signature")
    if not song.sections:
        add(None, None, "noSections", "the chart has no sections")

    for (inst, diff), p in song.parts.items():
        groups = _onset_groups(p)
        if not groups:
            continue
        times = [t for t, _ in groups]
        drums = inst == "drums"
        if times[0] < LEAD_S:
            add(inst, diff, "smallLeadingSilence", f"first note at {times[0]:.3f} s of song.ogg (Encore: 2 s)",
                times[0])
        ends = [n.end for n in p.notes if getattr(n, "end", None) is not None]
        last = max(times + ends)
        if audio_end is not None and last > audio_end:
            add(inst, diff, "noteAfterAudio", f"a note at {last:.3f} s, after song.ogg ends ({audio_end:.3f} s)", last)
        long = len(groups) > 50 and times[-1] - times[0] > 60
        if not p.star_power and not drums and long:
            add(inst, diff, "noStarPower", "no star power")
        for s in p.star_power:
            if not _inside(times, s.start, s.end):
                add(inst, diff, "emptyStarPower", "a star-power phrase with no notes", s.start)
        for s in p.solos:
            if not _inside(times, s.start, s.end):
                add(inst, diff, "emptySoloSection", "a solo with no notes", s.start)
        if drums and not p.activation and p.star_power and long:
            add(inst, diff, "noDrumActivationLanes", "star power but no activation lanes")
        prev = None
        gaps: list[tuple[float, float, float]] = []  # (sustain end, scan-chart gap end, Encore gap end)
        for t, notes in groups:
            if drums:
                hands = {h.pad for h in notes if h.pad}
                kick = any(h.pad == 0 for h in notes)
                if diff != "expert" and any(h.double_kick for h in notes):
                    add(inst, diff, "difficultyForbiddenNote", "a 2x kick below Expert", t)
                if diff == "easy" and len(hands) == 2 and kick:
                    add(inst, diff, "difficultyForbiddenNote", "a kick with two pads on Easy", t)
                if len(hands) >= 3:
                    add(inst, diff, "invalidChord", f"{len(hands)} pads at once", t)
                is_open = False
            else:
                n = notes[0]
                frets = set(n.frets)
                is_open = OPEN in frets
                if (diff == "hard" and {0, 4} <= frets) or (diff == "medium" and (4 in frets or {0, 3} <= frets)) \
                        or (diff == "easy" and frets & {3, 4}):
                    add(inst, diff, "difficultyForbiddenNote", f"frets {sorted(frets)} on {diff}", t)
                if len(frets - {OPEN}) == 5:
                    add(inst, diff, "invalidChord", "a 5-note chord", t)
                gaps = [g for g in gaps if g[2] > t]
                if any(a <= t < b for a, b, _ in gaps):
                    add(inst, diff, "badSustainGap", "a note under 40 ms after a sustain ends", t)
                elif any(a <= t < c for a, _, c in gaps):
                    add(inst, diff, "sustainGap", "a note under 60 ms after a sustain ends (Encore)", t)
                if n.end is not None:
                    ms = (n.end - t) * 1000
                    if ms < SCAN_BABY_SUSTAIN_MS:
                        add(inst, diff, "babySustain", f"a {ms:.0f} ms sustain", t)
                    elif ms < SUSTAIN_MIN_MS - 1e-6:
                        add(inst, diff, "shortSustain", f"a {ms:.0f} ms sustain (Encore: 200 ms)", t)
                    if not is_open:  # scan-chart ignores the gaps of open sustains
                        gaps.append((n.end, n.end + SCAN_SUSTAIN_GAP_MS / 1000, n.end + SUSTAIN_GAP_MS / 1000))
            if prev is not None and 0 < (t - prev[0]) * 1000 <= SCAN_BROKEN_NOTE_MS and is_open == prev[1]:
                add(inst, diff, "brokenNote", f"{(t - prev[0]) * 1000:.1f} ms after the previous note", t)
            prev = (t, is_open)
    return issues


def _drum_key(h: DrumHit) -> tuple:
    """A hit as the .chart writer encodes it: accents and ghosts only on pads, an accent winning over a ghost."""
    return (h.pad, h.cymbal and h.pad in (2, 3, 4), h.double_kick, h.accent and h.pad > 0,
            h.ghost and h.pad > 0 and not h.accent)


def self_check(chart: Chart, song: TimedSong) -> list[GateIssue]:
    """The chart as read back from notes.chart against the chart we built: every track and onset, times within
    1 ms, lanes, HOPO / tap / cymbal states, sustain ends and phrases (scan-chart's self-check, DESIGN 2.13 step 3).
    Issue times are on the chart's timeline."""
    tm = chart.tempo
    issues: list[GateIssue] = []
    written = set()
    for tr in chart.tracks:
        if not tr.notes:
            continue
        inst, diff = PART_INSTRUMENT[tr.instrument], LEVEL_KEY[tr.difficulty]
        written.add((inst, diff))
        p = song.parts.get((inst, diff))

        def add(kind_msg, time=None):
            issues.append(GateIssue(inst, diff, "selfCheck", kind_msg, None if time is None else round(time, 3)))

        if p is None:
            add("the track is missing from the written chart")
            continue
        if tr.is_drums:
            want = sorted((tm.tick_to_sec(h.tick), *_drum_key(h)) for h in tr.notes)
            got = sorted((h.time, h.pad, h.cymbal, h.double_kick, h.accent, h.ghost) for h in p.notes)
            if len(want) != len(got):
                add(f"{len(got)} hits read back, {len(want)} written")
            else:
                bad = [w for w, g in zip(want, got) if abs(w[0] - g[0]) > SELF_CHECK_S or w[1:] != g[1:]]
                if bad:
                    add(f"{len(bad)} hits read back differently", bad[0][0])
        else:
            notes: dict[int, FretNote] = {}
            for n in sorted(tr.notes, key=lambda n: n.tick):
                if n.tick in notes:  # quantize and reduce write one note per tick; merge defensively
                    o = notes[n.tick]
                    n = FretNote(n.tick, tuple(sorted(set(o.frets) | set(n.frets))), max(o.length, n.length),
                                 o.flip or n.flip, o.tap or n.tap)
                notes[n.tick] = n
            states = hopo_states(list(notes.values()), tm.resolution)
            got = sorted(p.notes, key=lambda n: n.time)
            if len(got) != len(notes):
                add(f"{len(got)} onsets read back, {len(notes)} written")
            else:
                kinds: dict[str, list[float]] = {}
                for (k, n), g in zip(sorted(notes.items()), got):
                    t = tm.tick_to_sec(k)
                    end = tm.tick_to_sec(k + n.length) if n.length > 0 else None
                    for kind, bad in (
                            ("time", abs(g.time - t) > SELF_CHECK_S),
                            ("lanes", tuple(sorted(set(n.frets))) != g.frets),
                            ("tap", n.tap != g.tap),
                            ("hopo", not n.tap and states[k] != g.hopo),
                            ("sustain", (end is None) != (g.end is None)
                             or (end is not None and abs(end - g.end) > SELF_CHECK_S))):
                        if bad:
                            kinds.setdefault(kind, []).append(t)
                for kind, ts in kinds.items():
                    add(f"{len(ts)} onsets read back with a different {kind}", ts[0])
        spans = {"star power": ([(p_.tick, p_.tick + p_.length) for p_ in tr.phrases if p_.kind == STAR_POWER],
                                p.star_power),
                 "fills": ([(p_.tick, p_.tick + p_.length) for p_ in tr.phrases if p_.kind == DRUM_ACTIVATION],
                           p.activation),
                 "solos": ([(a, b + 1) for a, b in tr.solos], p.solos)}  # the reader includes the soloend tick
        for what, (ours, read) in spans.items():
            want = sorted((tm.tick_to_sec(a), tm.tick_to_sec(b)) for a, b in ours)
            got = sorted((s.start, s.end) for s in read)
            if len(want) != len(got) or any(abs(w[0] - g[0]) > SELF_CHECK_S or abs(w[1] - g[1]) > SELF_CHECK_S
                                            for w, g in zip(want, got)):
                add(f"{what}: {len(got)} read back, {len(want)} written (or their times differ)")
    for inst, diff in sorted(set(song.parts) - written):
        issues.append(GateIssue(inst, diff, "selfCheck", "a track read back that was not written"))
    want_sections = [(tm.tick_to_sec(t), n) for t, n in sorted(chart.sections)]
    if len(want_sections) != len(song.sections) or any(
            abs(a - b) > SELF_CHECK_S or m != n for (a, m), (b, n) in zip(want_sections, song.sections)):
        issues.append(GateIssue(None, None, "selfCheck", f"sections: {len(song.sections)} read back, "
                                                         f"{len(want_sections)} written (or they differ)"))
    return issues


def _read_ini(path: Path) -> dict[str, str]:
    out, section = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
        elif "=" in line and section == "song":
            k, _, v = line.partition("=")
            out[k.strip().lower()] = v.strip()
    return out


def find_scan_chart() -> tuple[list[str] | None, str]:
    """The command that runs scan-chart (node, then SCAN_CHART or $SONGCHARTER_SCAN_CHART) and its version, or
    (None, why it cannot run)."""
    script = Path(os.environ.get("SONGCHARTER_SCAN_CHART") or SCAN_CHART)
    package = script.parent / "node_modules" / "scan-chart" / "package.json"
    node = shutil.which("node")
    if node is None:
        return None, "node is not on PATH"
    if not script.is_file():
        return None, f"{script} is missing"
    if not package.is_file():
        return None, f"{package.parent} is missing (run `npm ci` in {script.parent})"
    try:
        version = str(json.loads(package.read_text(encoding="utf-8")).get("version", "?"))
    except (OSError, ValueError):
        version = "?"
    return [node, str(script)], version


def run_scan_chart(folder, command: list[str]) -> dict:
    """scan-chart's verdict on a song folder (`scan.cjs <folder> --notes`): playable, folder, metadata and chart
    issues, and every parsed note."""
    r = subprocess.run([*command, str(folder), "--notes"], capture_output=True, text=True, encoding="utf-8",
                       timeout=SCAN_CHART_TIMEOUT_S)
    if r.returncode:
        raise ToolError(f"scan-chart exited with {r.returncode}: {r.stderr.strip()[-300:]}")
    return json.loads(r.stdout)


def scan_chart_issues(data: dict, pad_seconds: float = 0.0) -> list[GateIssue]:
    """scan-chart's findings as gate errors: not playable, every folder issue but SCAN_ALLOWED's, every metadata and
    chart issue (times, read from its descriptions, in input seconds)."""
    issues = []
    if not data.get("playable"):
        issues.append(GateIssue(None, None, "notPlayable", "scan-chart: the folder is not playable"))
    for i in data.get("folderIssues") or []:
        if i.get("folderIssue") not in SCAN_ALLOWED:
            issues.append(GateIssue(None, None, i.get("folderIssue") or "folderIssue",
                                    f"scan-chart: {i.get('description')}"))
    for i in data.get("metadataIssues") or []:
        issues.append(GateIssue(None, None, i.get("metadataIssue") or "metadataIssue",
                                f"scan-chart: {i.get('description')}"))
    for i in data.get("chartIssues") or []:
        description = str(i.get("description", ""))
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)\]", description)
        issues.append(GateIssue(i.get("instrument"), i.get("difficulty"),
                                i.get("noteIssue") or i.get("trackIssue") or i.get("chartIssue") or "chartIssue",
                                f"scan-chart: {description}",
                                None if m is None else round(int(m[1]) * 60 + float(m[2]) - pad_seconds, 3)))
    return issues


_SCAN_FRETS = {"green": 0, "red": 1, "yellow": 2, "blue": 3, "orange": 4, "open": OPEN}
_SCAN_PADS = {"kick": 0, "redDrum": 1, "yellowDrum": 2, "blueDrum": 3, "greenDrum": 4}


def scan_chart_song(data: dict) -> TimedSong:
    """scan-chart's parsed notes (`run_scan_chart`) as the TimedSong `self_check` compares, on the chart's timeline:
    onset times as scan-chart computed them, sustain ends from its own tempo list, a chord's end its longest
    sustain, an unknown note type as lane -1 (so the self-check fails on it)."""
    res = data["resolution"]
    tempos = sorted(data["tempos"], key=lambda t: t["tick"])
    starts = [t["tick"] for t in tempos]

    def sec(tick: int) -> float:
        t = tempos[max(0, bisect.bisect_right(starts, tick) - 1)]
        return (t["msTime"] + (tick - t["tick"]) * 60000 / (t["beatsPerMinute"] * res)) / 1000

    def spans(items) -> list[TimedSpan]:
        return [TimedSpan(s["msTime"] / 1000, (s["msTime"] + s["msLength"]) / 1000) for s in items or []]

    parts = {}
    for tr in data.get("tracks") or []:
        inst, diff = tr["instrument"], tr["difficulty"]
        if inst not in INSTRUMENTS or diff not in DIFFICULTIES:
            continue
        if inst == "drums":
            notes = [TimedHit(n["ms"] / 1000, _SCAN_PADS.get(n["type"], -1), "cymbal" in n["flags"],
                              "doubleKick" in n["flags"], "accent" in n["flags"], "ghost" in n["flags"])
                     for n in tr["notes"]]
        else:
            chords: dict[int, list[dict]] = {}
            for n in tr["notes"]:
                chords.setdefault(n["tick"], []).append(n)
            notes = []
            for tick, group in sorted(chords.items()):
                kept = [n for n in group if n["type"] != "open"] or group  # an open with frets is dropped
                flags, length = set(group[0]["flags"]), max(n["length"] for n in kept)
                frets = tuple(sorted(_SCAN_FRETS.get(n["type"], -1) for n in kept))
                notes.append(TimedNote(group[0]["ms"] / 1000, frets, sec(tick + length) if length > 0 else None,
                                       "hopo" in flags and "tap" not in flags, "tap" in flags))
        if notes:
            parts[(inst, diff)] = TimedPart(inst, diff, notes, spans(tr.get("starPower")), spans(tr.get("solos")),
                                            spans(tr.get("activation")))
    return TimedSong("scan-chart", parts, [(s["msTime"] / 1000, s["name"]) for s in data.get("sections") or []])


def lyrics_read_back(path: Path, chart: Chart) -> list[GateIssue]:
    """notes.chart's lyric events (phrase_start, lyric, phrase_end) read back against the ones written, in order:
    an error when they differ, naming only where (the text is never in a message)."""
    lines = _chart_sections(_decode(Path(path).read_bytes())).get("Events", [])
    read = [(int(m[1]), m[2]) for m in map(L.EVENT.fullmatch, lines) if m]
    want = [(t, " ".join(text.replace('"', "`").split()))
            for t, _, text in sorted(chart.lyrics, key=lambda r: (r[0], r[1]))]
    if read == want:
        return []
    at = next((i for i, (a, b) in enumerate(zip(read, want)) if a != b), min(len(read), len(want)))
    return [GateIssue(None, None, "lyricsReadBack", f"notes.chart holds {len(read)} lyric events, {len(want)} were "
                      f"written; they first differ at event {at}")]


def verify_folder(folder, chart: Chart, pad_seconds: float, audio_seconds: float | None = None, *,
                  scan_chart: bool | None = None, record: dict | None = None) -> list[GateIssue]:
    """The gate on a written song folder (DESIGN.md 2.13 steps 2-4): its files, its song.ini, notes.chart read back
    (`self_check`, `scan_rules`), and scan-chart itself (`scan_chart_issues`, and `self_check` on its parsed notes).
    An issue of ours that scan-chart also reports (same track and kind) is left to scan-chart's report.

    audio_seconds: song.ogg's length (padded). scan_chart: None runs it when `find_scan_chart` finds it and warns
    when it does not; True makes a missing scan-chart an error; False skips it. record: a dict that receives
    record["scan_chart"], what scan-chart found (for report.json)."""
    folder = Path(folder)
    issues: list[GateIssue] = []
    files = sorted(f.name.lower() for f in folder.iterdir() if f.is_file())
    for suffixes, none, many, what in (((".chart", ".mid"), "noChart", "multipleChart", "chart"),
                                       ((".ini",), "noMetadata", "multipleIniFiles", "ini"),
                                       ((".ogg", ".mp3", ".wav", ".opus"), "noAudio", "multipleAudio", "audio")):
        found = [f for f in files if f.endswith(suffixes)]
        if len(found) != 1:
            issues.append(GateIssue(None, None, many if found else none,
                                    f"the folder holds {len(found)} {what} files: {', '.join(found) or 'none'}"))
    ini = _read_ini(folder / "song.ini") if (folder / "song.ini").exists() else {}
    for key in INI_REQUIRED:
        if not ini.get(key):
            issues.append(GateIssue(None, None, "missingValue", f"song.ini has no '{key}'"))
    for inst in chart.instruments():
        key = INI_DIFF_KEY.get(inst)
        if key and not ini.get(key, "").lstrip("-").isdigit():
            issues.append(GateIssue(PART_INSTRUMENT.get(inst), None, "missingValue", f"song.ini has no '{key}'"))
    song = read_chart(folder / "notes.chart")

    def checked(read: TimedSong, prefix: str = "") -> list[GateIssue]:
        return [GateIssue(i.instrument, i.difficulty, i.kind, prefix + i.message,
                          None if i.time is None else round(i.time - pad_seconds, 3), i.error)
                for i in self_check(chart, read)]

    issues += checked(song)
    issues += scan_rules(song, pad_seconds, audio_seconds, chart.tempo)
    if chart.lyrics:
        issues += lyrics_read_back(folder / "notes.chart", chart)
    command, version = (None, "turned off") if scan_chart is False else find_scan_chart()
    if command is None:
        summary: dict[str, Any] = {"ran": False, "reason": version}
        found = [GateIssue(None, None, "scanChartNotRun", f"scan-chart not run ({version}): the gate rests on its "
                           "re-implementation of scan-chart's rules", error=bool(scan_chart))]
    else:
        try:
            data = run_scan_chart(folder, command)
            read = scan_chart_song(data)
        except (RuntimeError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as e:
            summary = {"ran": False, "version": version, "reason": str(e)}
            found = [GateIssue(None, None, "scanChartFailed", f"scan-chart did not finish: {e}")]
        else:
            found = scan_chart_issues(data, pad_seconds)
            shared = {(i.instrument, i.difficulty, i.kind) for i in found}
            issues = [i for i in issues if (i.instrument, i.difficulty, i.kind) not in shared]
            own = checked(read, "scan-chart's notes: ")
            summary = {"ran": True, "version": version, "playable": bool(data.get("playable")),
                       "folder_issues": [i.get("folderIssue") for i in data.get("folderIssues") or []],
                       "metadata_issues": [i.get("metadataIssue") for i in data.get("metadataIssues") or []],
                       "chart_issues": len(data.get("chartIssues") or []), "self_check_errors": len(own),
                       "tempo_markers": data.get("tempoMarkerCount")}
            if chart.lyrics:   # Clone Hero reads them only if scan-chart's parser finds them
                summary["has_lyrics"] = data.get("hasLyrics")
                if "hasLyrics" not in data:   # a scan.cjs older than this check
                    own.append(GateIssue(None, None, "lyricsNotChecked", "scan-chart's script does not report "
                                         "lyrics (tools/scan-chart/scan.cjs is older): not checked", error=False))
                elif not data["hasLyrics"]:
                    own.append(GateIssue(None, None, "noLyrics", "scan-chart finds no lyrics in notes.chart"))
            found += own
    if record is not None:
        record["scan_chart"] = summary
    return found + issues


# ------------------------------------------------------------------------------------------------ the build

def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_jsonable(v) for v in x.tolist()]
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return v if math.isfinite(v) else None
    if isinstance(x, Path):
        return str(x)
    return x


def _issue(i: Issue, inst: str, tempo: TempoMap, pad: float, error: bool | None = None) -> GateIssue:
    t = None if i.tick is None else round(tempo.tick_to_sec(i.tick) - pad, 3)
    return GateIssue(inst, i.difficulty.lower(), i.kind, i.message, t, i.error if error is None else error)


def _in_s(tempo: TempoMap, tick: int, pad: float) -> float:
    return round(tempo.tick_to_sec(tick) - pad, 3)


def track_stats(track: Track, tempo: TempoMap, pad: float) -> dict:
    """Counts for the report: onsets, notes, phrases, and per kind (chords, sustains, HOPOs; kicks, cymbals)."""
    ticks = sorted({n.tick for n in track.notes})
    out: dict[str, Any] = {"onsets": len(ticks), "notes": len(track.notes),
                           "star_power": sum(p.kind == STAR_POWER for p in track.phrases),
                           "fills": sum(p.kind == DRUM_ACTIVATION for p in track.phrases), "solos": len(track.solos)}
    if ticks:
        out["first_note"], out["last_note"] = _in_s(tempo, ticks[0], pad), _in_s(tempo, ticks[-1], pad)
    if track.is_drums:
        out.update(kicks=sum(h.pad == 0 for h in track.notes), double_kicks=sum(h.double_kick for h in track.notes),
                   cymbals=sum(h.cymbal for h in track.notes),
                   toms=sum(h.pad in (2, 3, 4) and not h.cymbal for h in track.notes),
                   accents=sum(h.accent for h in track.notes), ghosts=sum(h.ghost for h in track.notes))
    else:
        states = hopo_states(track.notes, tempo.resolution)
        out.update(chords=sum(len(set(n.frets)) >= 2 for n in track.notes),
                   sustains=sum(n.length > 0 for n in track.notes), opens=sum(OPEN in n.frets for n in track.notes),
                   hopos=sum(states[t] for t in ticks) - sum(n.tap for n in track.notes),
                   taps=sum(n.tap for n in track.notes), flips=sum(n.flip for n in track.notes))
    return out


def _import(part: PartConfig, source: Path | None = None) -> TimedSong:
    """The part's source (or one of its takes), which must hold an Expert part of the instrument it is taken
    from."""
    source = source or part.source
    if not source.exists():
        raise FileNotFoundError(f"part {part.key}: {source} does not exist")
    song = read_song(source, part.time_shift, source=f"{part.key}:{source}")
    if (part.from_instrument, "expert") not in song.parts:
        found = sorted({i for i, _ in song.parts})
        raise InputError(f"part {part.key}: {source} has no Expert {part.from_instrument} "
                         f"(it has {', '.join(found) or 'no parts'})")
    return song


def _import_takes(part: PartConfig, song: TimedSong) -> list[TimedSong]:
    """The part's takes (_import), each a run of its own: two runs with the same Expert notes (one file named two
    ways, a copy, a take run with the source's seed) would always agree, and outvote the others (DESIGN.md 2.7)."""
    takes = [_import(part, t) for t in part.takes]
    key = (part.from_instrument, "expert")
    runs = [(part.source, song)] + list(zip(part.takes, takes))
    for j, (path, run) in enumerate(runs):
        same = next((p for p, r in runs[:j] if r.parts[key].notes == run.parts[key].notes), None)
        if same is not None:
            raise InputError(f"part {part.key}: {same} and {path} have the same Expert notes: takes must be other "
                             "runs (another seed), not the same one again")
    return takes


def _splice_takes(part: PartConfig, song: TimedSong, takes: list[TimedSong], sections: list[tuple[float, str]],
                  offset: float) -> tuple[TimedSong, dict]:
    """The part's source with its Expert spliced from the source and its takes (takes.splice), and the report.
    sections: (input seconds, name). The takes share the source's clock, `offset` seconds late against ours
    (_offset), so the windows are cut at the section starts plus the offset; the report gives them in input
    seconds."""
    key = (part.from_instrument, "expert")
    spliced, windows = splice([song.parts[key]] + [t.parts[key] for t in takes], [(t + offset, n) for t, n in sections])
    names = [str(part.source)] + [str(t) for t in part.takes]
    ours = [0.0] + [round(w.start - offset, 4) for w in windows[1:]]  # the first window starts with the song
    info = {"sources": names, "windows": [{"section": w.name, "start": a, "end": b,
                                           "onsets": list(w.onsets), "scores": list(w.scores), "pick": w.pick}
                                          for w, a, b in zip(windows, ours, ours[1:] + [None])],
            "picked": [sum(w.pick == k for w in windows) for k in range(len(names))],  # windows per source
            "onsets": {"source": len({n.time for n in song.parts[key].notes}),
                       "spliced": len({n.time for n in spliced.notes})}}
    return replace(song, parts={**song.parts, key: spliced}), info


def _offset(part: PartConfig, song: TimedSong, tempo: TempoMap, pad: float) -> tuple[float, dict, list[str]]:
    """The part's offset against our grid (measured on its source's Expert; one for all its levels and its takes,
    which share the source's clock), its report and warnings."""
    times = [n.time for n in song.parts[(part.from_instrument, "expert")].notes]
    n = len(set(times))
    measured, conc = estimate_offset(times, tempo, pad)
    trusted = RULES.applies(measured, conc, n)
    applied = (measured if trusted else 0.0) if part.offset == "auto" else float(part.offset)
    info = {"mode": "auto" if part.offset == "auto" else "fixed", "measured": round(measured, 5),
            "concentration": round(conc, 4), "evidence": round(n * conc ** 2, 1), "trusted": bool(trusted),
            "applied": round(applied, 5)}
    warnings = []
    if part.offset == "auto" and not trusted:
        warnings.append(f"part {part.key}: offset {measured * 1000:+.1f} ms measured but not applied "
                        f"(concentration {conc:.2f}, evidence {n * conc ** 2:.0f})")
    return applied, info, warnings


def part_rules(part: PartConfig, octave: int = 1):
    """The quantizer's rules for a part: its HOPO rule (HOPO_RULES), and on a doubled grid (octave 2) the bass one
    slot level coarser and with no triplet slots (DOUBLED_BASS_SLOTS, DESIGN.md 2.6): the bass engine's onsets spread
    about a 16th either side of the notes at 200 BPM, which the doubled grid's 16ths cannot resolve, and its 8ths that
    far off lie nearer the doubled grid's triplets than its 8ths."""
    rules = HOPO_RULES[part.hopo]
    if octave == 2 and part.instrument == "bass":
        rules = replace(rules, straight=DOUBLED_BASS_SLOTS[0], triplet=DOUBLED_BASS_SLOTS[1])
    return rules


def lyric_rules(octave: int = 1) -> QuantizeRules:
    """The rules the lyrics snap by (lyrics.place): the quantizer's, and on a doubled grid (octave 2) one slot level
    coarser (DOUBLED_LYRIC_SLOTS, DESIGN.md 2.15), the doubled grid's 8ths and their triplets, which are the first
    grid's 16ths and its 16th-note triplets: so the words keep the straight slots the first grid gave them (its
    8th-note triplets are a subset of the triplet slots). On the power-metal stress song the aligner puts 0.29 of the
    words 38-75 ms early, and the doubled grid's 75 ms 16ths snap them to the slot before the human's (M5-04: a median
    67 ms off, against 7 ms on the first grid)."""
    if octave == 2:
        return replace(RULES, straight=DOUBLED_LYRIC_SLOTS[0], triplet=DOUBLED_LYRIC_SLOTS[1])
    return RULES


def _quantize(part: PartConfig, song: TimedSong, tempo: TempoMap, pad: float, offset: float, octave: int = 1
              ) -> dict[str, tuple[Track, QuantizeReport]]:
    """The part's taken difficulties on our grid, every one moved by the part's offset (_offset), with its rules
    (part_rules)."""
    levels = {d: p for (i, d), p in song.parts.items() if i == part.from_instrument}
    rules = part_rules(part, octave)
    take = ["expert"] if part.take_difficulties == "expert" else [d for d in DIFFICULTIES if d in levels]
    out = {}
    for d in take:
        p = levels[d]
        clean = TimedPart(part.instrument, d, list(p.notes))  # the tool's phrases go: ours replace them
        out[d] = quantize_part(clean, tempo, pad, offset, rules, song.beats)
    return out


def _ladder(expert: Track, own: dict[str, Track], tempo: TempoMap, sections: list[int],
            loudness: list[float] | None) -> list[Track]:
    """Expert and its lower levels: the source's own where `own` has them (keyed "hard" ...), each other one reduced
    from the level above. Every lower level carries Expert's phrases and solos, for fit_chart to fit."""
    out, upper = [expert], expert
    for level in LEVELS:
        mine = own.get(LEVEL_KEY[level])
        if mine is not None:
            upper = Track(level, expert.instrument, list(mine.notes), list(expert.phrases), list(expert.solos))
        else:
            upper = reduce_level(upper, level, tempo, expert=expert, sections=sections,
                                 loudness=loudness if expert.is_drums else None)
        out.append(upper)
    return out


def _install(staging: Path, target: Path) -> Path:
    """Move a finished build from its staging folder into `target`, replacing what an earlier build left there
    (check_inputs made sure it holds nothing else to lose; a background no earlier build wrote stays: `_ours`)."""
    target.mkdir(parents=True, exist_ok=True)
    new = {p.name for p in staging.iterdir()}
    ours = _ours(target)   # by the earlier build's report.json, before the new one replaces it
    for p in target.iterdir():
        if p.is_file() and p.name.lower() in ours and p.name not in new:
            p.unlink()  # an earlier build's album.jpg or report.json
    for p in staging.iterdir():
        os.replace(p, target / p.name)
    staging.rmdir()
    return target


def _remove_build(folder: Path) -> None:
    """Delete an earlier build's files from `folder` (`_ours`), and the folder when that empties it."""
    if not folder.is_dir():
        return
    ours = _ours(folder)
    for p in folder.iterdir():
        if p.is_file() and p.name.lower() in ours:
            p.unlink()
    if not any(folder.iterdir()):
        folder.rmdir()


def _grid_record(g: BeatGrid) -> dict:
    ev = g.stats["evidence"]
    return {"bpm_median": round(g.bpm, 4), "click_bpm": g.stats["click"]["bpm"], "mode": g.mode,
            "confident_share": ev["confident_share"], "n_confident": ev["n_confident"], "n_beats": ev["n_beats"],
            **({"half_beat": g.stats["half_beat"]} if "half_beat" in g.stats else {})}


def _octave_pass(cfg: AssembleConfig, first: BeatGrid, onsets: dict[str, list[float]],
                 drum_features: OnsetFeatures | None, second_pass) -> tuple[BeatGrid, int, dict, str, list[str]]:
    """The grid's octave (DESIGN.md 2.3, doubling only): (grid, octave, stats, reason, warnings). grid_octave
    decides on the first grid unless the config forces it; a 2 builds the grid again at twice the first grid's
    click tempo, with the fold range doubled, no first-beat hint and the half-beat phase test
    (`second_pass(bpm, bpm_range)`; beatgrid.half_beat_phase). The doubled grid is kept when its confident share is at least OCTAVE_RULES.evidence_min times the first's (a doubled grid
    has fewer drum hits per beat by nature), or when the config forces 2; otherwise the first stays, with a
    warning."""
    rules = OCTAVE_RULES
    want, stats = grid_octave(onsets, first.beats, drum_features, rules)
    stats["thresholds"]["evidence_min"] = rules.evidence_min
    stats["first"] = _grid_record(first)
    dense = f"{stats['pooled_share']:.0%} of intervals under a 16th"
    forced = cfg.grid_octave != "auto"
    if forced:
        want = cfg.grid_octave
        if want == 2 and 2 * first.bpm > rules.max_bpm:
            raise InputError(f"grid_octave 2: the doubled tempo, {2 * first.bpm:.1f} BPM, passes "
                             f"{rules.max_bpm:.0f} BPM")
    if want == 1:
        return first, 1, stats, ("forced: grid_octave 1" if forced else stats["reason"]), []
    lo, hi = BPM_RANGE
    try:
        second = second_pass(2 * first.stats["click"]["bpm"], (2 * lo, 2 * hi))
    except InputError:
        if forced:
            raise
        second = None
    s1 = first.stats["evidence"]["confident_share"]
    s2 = second.stats["evidence"]["confident_share"] if second is not None else 0.0
    ratio = s2 / s1 if s1 > 0 else (math.inf if s2 > 0 else 0.0)
    stats["second"] = None if second is None else _grid_record(second)
    stats["evidence_ratio"] = round(ratio, 4) if math.isfinite(ratio) else None
    if forced or ratio >= rules.evidence_min:
        why = "forced: grid_octave 2" if forced else (
            f"{stats['reason']}; the doubled grid's confident share {s2:.2f} against {s1:.2f} (ratio {ratio:.2f}, "
            f"at least {rules.evidence_min})")
        warn = [f"tempo doubled to {second.bpm:.1f} BPM: " + (
            "grid_octave 2" if forced else f"the notes are too dense for {first.bpm:.1f} BPM ({dense})")]
        hb = second.stats.get("half_beat") or {}
        if hb.get("unsure"):
            warn.append(f"beat phase unsure: the kick is about as strong between the beats as on them (ratio "
                        f"{hb['ratio']:.2f}): check that the beat lines are on the kick")
        return second, 2, stats, why, warn
    why = (f"{stats['reason']}; but the doubled grid's confident share {s2:.2f} against {s1:.2f} (ratio "
           f"{ratio:.2f}, under {rules.evidence_min}): the first grid stays")
    return first, 1, stats, why, [f"tempo: the notes are dense for {first.bpm:.1f} BPM ({dense}) but the drums give "
                                  f"no evidence at {2 * first.bpm:.1f} BPM: check the tempo"]


def assemble(config: AssembleConfig | dict | str | Path, *, lyrics: L.Timed | None = None,
             art: dict | None = None) -> AssembleResult:
    """Build the song folder a config describes (the module docstring), write report.json into it and return the
    chart, the report and every issue. Errors in the checks or the gate do not raise: the build goes to
    <output>.failed for inspection (`AssembleResult.folder`), <output> keeps what it held, and `AssembleResult.ok`
    is False. Bad inputs and a song.ogg out of sync raise, and leave both folders as they were. `lyrics`: the text
    and its syllables' starts in seconds of the decode, written as [Events] lyrics. `art`: where the album art and
    the background came from (art.Pictures.record), for report.json's `art`."""
    if isinstance(config, (str, Path)):
        config = load_config(config)
    elif isinstance(config, dict):
        config = parse_config(config)
    cfg = config
    check_inputs(cfg)
    songs = {p.key: _import(p) for p in cfg.parts}  # a bad source fails here, before any audio work
    takes = {p.key: _import_takes(p, songs[p.key]) for p in cfg.parts}
    sr = SAMPLE_RATE
    warnings: list[str] = []
    report: dict[str, Any] = {"config": _jsonable({**asdict(cfg), "parts": [asdict(p) for p in cfg.parts]})}

    # 1. audio and stems (a file ffmpeg cannot read is an InputError)
    mix = A.decode(cfg.audio, sr)
    duration = mix.shape[1] / sr
    report["audio"] = {"path": str(cfg.audio), "sample_rate": sr, "samples": int(mix.shape[1]),
                       "duration": round(duration, 4)}
    stems: dict[str, np.ndarray] = {}
    report["stems"] = {}
    for name, path in sorted(cfg.stems.items()):
        y, rate = A.read_wav(path)
        if rate != sr:
            raise InputError(f"stem {name}: {rate} Hz, not {sr} Hz")
        stems[name] = y
        check = stem_alignment(mix, y, sr)
        # absolute, so the report finds the stem from any working directory (the preview reads it)
        report["stems"][name] = {"path": str(Path(path).resolve()), **check}
        if not check["ok"]:
            warnings.append(f"stem {name} may not line up with the audio: {check.get('reason') or check}")
    levels_db = {name: frame_levels(y, sr) for name, y in stems.items()}

    # 2. grid, lead-in, tempo map
    src = cfg.grid_source or ("drums" if "drums" in stems else "mix")
    sec = cfg.grid_secondary if cfg.grid_secondary is not None else (
        next((n for n in STEMS_FOR["guitar"] if n in stems and n != src), None) if src != "mix" else None)
    sec = sec or None
    grid_audio = mix if src == "mix" else stems[src]
    features = onset_features(grid_audio, sr)  # once, for both passes and the backbeat test
    second_stem = (mix if sec == "mix" else stems[sec]) if sec else None
    grid = beat_grid(grid_audio, sr, duration=duration, bpm=cfg.bpm, first_beat=cfg.first_beat, mode=cfg.grid_mode,
                     secondary=second_stem, features=features)
    onsets = {p.key: sorted({n.time for n in songs[p.key].parts[(p.from_instrument, "expert")].notes})
              for p in cfg.parts}
    grid, octave, octave_stats, octave_reason, warn = _octave_pass(
        cfg, grid, onsets, features if src == "drums" else None,
        lambda bpm, bpm_range: beat_grid(grid_audio, sr, duration=duration, bpm=bpm, mode=cfg.grid_mode,
                                         secondary=second_stem, features=features, bpm_range=bpm_range,
                                         half_beat=True, keep_line=True))
    warnings += warn
    lead = plan_lead_in(grid.beats, grid.downbeats, sr, min_lead=cfg.lead_in, duration=duration)
    tm = TempoMap.from_beats(lead.beats, bars=lead.bars, tolerance=cfg.tempo_tolerance)
    pad = lead.pad_seconds
    song_end = (mix.shape[1] + lead.pad_samples) / sr  # song.ogg's length on the map: the decode after the pad
    res = tm.resolution
    err = np.abs(tm.ticks_to_secs(np.arange(len(lead.beats)) * res) - np.asarray(lead.beats))
    share = grid.stats["evidence"]["confident_share"]
    report["grid"] = {"source": src, "secondary_source": sec, "mode": grid.mode,
                      "mode_reason": grid.stats["mode"]["reason"],
                      "bpm_median": round(grid.bpm, 4), "beats": int(len(grid.beats)),
                      "first_beat": round(float(grid.beats[0]), 4), "confident_share": share,
                      "downbeat_phase": grid.stats["downbeats"]["phase"],
                      "downbeat_margin": grid.stats["downbeats"]["margin"],
                      "downbeats_uncertain": grid.stats["downbeats"]["uncertain"],
                      "drift_ms": grid.stats["drift_ms"], "octave": octave, "octave_reason": octave_reason,
                      "octave_stats": octave_stats, "stats": _jsonable(grid.stats)}
    if grid.stats["downbeats"]["uncertain"]:
        warnings.append(f"downbeats uncertain (bar-phase margin {grid.stats['downbeats']['margin']:.3f}): "
                        "check that beat 1 is on the kick")
    if not cfg.grid_mode and grid.stats["start"]["grid"] == "line" and abs(share - FREE_SHARE) < MODE_MARGIN:
        warnings.append(f"grid mode {grid.mode} chosen on a thin margin (confident share {share:.3f} against "
                        f"{FREE_SHARE}); grid_mode overrides it")
    # (times in grid.stats are onset times, about 22 ms after the beats: close enough for a warning)
    for t0, t1, bpm, grid_bpm in grid.stats.get("tempo_check", []):
        warnings.append(f"tempo {bpm:.1f} BPM at {t0:.0f}-{t1:.0f} s is not followed by the grid ({grid_bpm:.1f} "
                        "BPM): pass beat hints or start= beats")
    for t0, t1, n, timed in grid.stats.get("secondary", {}).get("stretches", []):
        if n >= GRID_LINE_BEATS and timed < 0.5:
            warnings.append(f"beats at {t0:.0f}-{t1:.0f} s follow the straight line (no drum or second-stem "
                            "evidence): check sync there")
    bpms = [t.bpm for t in tm.tempos]
    report["lead_in"] = {"pad_samples": lead.pad_samples, "pad_seconds": round(pad, 6),
                         "first_beat_tick": lead.first_beat * res, "lead_beats": lead.first_beat}
    report["tempo_map"] = {"resolution": res, "markers": len(tm.tempos), "time_signatures": len(tm.time_signatures),
                           "bpm_min": min(bpms), "bpm_max": max(bpms), "max_error_ms": round(float(err.max()) * 1000, 3),
                           "beats": len(lead.beats)}

    # sections (before the parts: takes are spliced by section)
    if cfg.sections is None:
        sections, how = [], "none"
    elif cfg.sections.startswith("from:"):
        sections = sections_from_chart(songs[cfg.sections[5:]].sections, tm, pad, end=duration,
                                       min_measures=SECTION_MIN_MEASURES)
        how = cfg.sections
    else:
        sections = sections_from_segments(_read_sections(cfg.sections), tm, pad, min_measures=SECTION_MIN_MEASURES,
                                          split_over=SECTION_SPLIT_OVER, split_into=SECTION_SPLIT_INTO)
        how = f"allin1:{cfg.sections}"
    if not sections:
        warnings.append("no sections (scan-chart's noSections)")
    report["sections"] = {"source": how, "count": len(sections),
                          "list": [(_in_s(tm, t, pad), t, n) for t, n in sections]}

    # 3. parts
    by_inst: dict[str, dict[str, Track]] = {}
    report["parts"] = {}
    for part in cfg.parts:
        song, spliced = songs[part.key], None
        applied, offset, warn = _offset(part, song, tm, pad)
        warnings += warn
        if takes[part.key]:
            song, spliced = _splice_takes(part, song, takes[part.key],
                                          [(tm.tick_to_sec(t) - pad, n) for t, n in sections], applied)
            if not sections:
                warnings.append(f"part {part.key}: takes need sections to splice by; the source alone is used")
        q = _quantize(part, song, tm, pad, applied, octave)
        by_inst[part.instrument] = {d: track for d, (track, _) in q.items()}
        src_counts = {d: len({n.time for n in p.notes}) for (i, d), p in songs[part.key].parts.items()
                      if i == part.from_instrument}
        report["parts"][part.key] = {
            "instrument": part.instrument, "source": str(part.source), "source_instrument": part.from_instrument,
            "time_shift": part.time_shift, "take_difficulties": part.take_difficulties, "hopo": part.hopo,
            "source_onsets": src_counts, "offset": offset,
            "slots": {"straight": part_rules(part, octave).straight, "triplet": part_rules(part, octave).triplet},
            "quantize": {d: _jsonable(asdict(r)) for d, (_, r) in q.items()}}
        if spliced is not None:
            report["parts"][part.key]["takes"] = spliced
        stem = next((s for s in STEMS_FOR[part.instrument] if s in levels_db), None)
        if stem and part.trim_silence:
            by_inst[part.instrument], removed = trim_silent_edges(by_inst[part.instrument], levels_db[stem], tm, pad)
            span = active_span(levels_db[stem])
            report["parts"][part.key]["trimmed"] = {
                "stem": stem, "floor_db": TRIM_DB, "kept": None if span is None else [round(x, 3) for x in span],
                "onsets": removed}
        by_inst[part.instrument], clipped = clip_to_audio(by_inst[part.instrument], tm, song_end)
        report["parts"][part.key]["clipped"] = {"audio_end": round(duration, 4), "margin_s": CLIP_MARGIN_S,
                                                "levels": clipped}

    # 4. phrases, reductions (the sections are built before the parts, for the takes)
    confirm = None
    if cfg.solos == "stems":
        if "vocals" not in levels_db:
            warnings.append("solos 'stems' needs a vocals stem: no solos placed")
        else:
            lead_stem = next((s for s in ("guitar", "other") if s in levels_db), None)
            confirm = stem_confirm(tm, pad, LEVEL_FRAME_S, levels_db["vocals"],
                                   levels_db[lead_stem] if lead_stem else None)
    info = SongInfo(**{k: v for k, v in cfg.metadata.items() if k != "year"},
                    year=str(cfg.metadata.get("year", "")))
    experts = [by_inst[i]["expert"] for i in INSTRUMENTS if i in by_inst]
    chart = Chart(info, tm, sections, experts)
    named = cfg.solos if isinstance(cfg.solos, tuple) else None
    solo_record: dict = {}   # the solo rules used and why each solo is where it is (place_solos), for the report
    sp_record: dict = {}     # each part's star-power count: its rules, span and target (place_star_power)
    chart = place_phrases(chart, solos=named is not None or (cfg.solos != "off" and (cfg.solos == "labels"
                                                                                       or confirm is not None)),
                          confirm_solo=confirm, solo_names=named, solo_record=solo_record, sp_record=sp_record)
    if named:
        have = {n for _, n in sections}
        lead_track = next((t for t in chart.tracks if t.instrument == "Single" and t.difficulty == "Expert"), None)
        starts = sorted(sections)
        for name in named:
            if name not in have:
                warnings.append(f"solos: no section is named {name!r} (sections: {', '.join(sorted(have))})")
                continue
            for i, (a, n) in enumerate(starts):
                b = starts[i + 1][0] if i + 1 < len(starts) else None
                if n == name and lead_track is not None and not any(a <= s < (b if b is not None else s + 1)
                                                                    for s, _ in lead_track.solos):
                    warnings.append(f"solos: section {name!r} got no solo (it needs 16 Expert guitar onsets and 4 "
                                    "measures, and a song has at most 3 solos)")
    placed = {t.instrument: t for t in chart.tracks}
    loud = None
    if "drums" in levels_db and sections:
        loud = section_loudness(levels_db["drums"], LEVEL_FRAME_S, sections, tm, pad, duration)
    report["drum_section_loudness_db"] = loud
    tracks: list[Track] = []
    for part in sorted(cfg.parts, key=lambda p: INSTRUMENTS.index(p.instrument)):
        own = by_inst[part.instrument] if part.take_difficulties == "all" else {}
        tracks += _ladder(placed[CHART_INSTRUMENT[part.instrument]], own, tm, [t for t, _ in sections], loud)
    chart = fit_chart(Chart(info, tm, sections, [t for t in tracks if LEVEL_KEY[t.difficulty] in cfg.levels]))
    if lyrics is not None:   # only the counts go into the report
        rules = lyric_rules(octave)
        phrases, stats = L.place(lyrics.lyrics, lyrics.starts, tm, pad,
                                 end_tick=last_tick_by(tm, song_end - CLIP_MARGIN_S), rules=rules)
        chart.lyrics = L.events(phrases)
        report["lyrics"] = {**stats, "slots": {"straight": rules.straight, "triplet": rules.triplet},
                            "events": len(chart.lyrics), "markup_dropped": lyrics.lyrics.dropped}

    # checks
    issues: list[GateIssue] = []
    for part in cfg.parts:
        trs = [t for t in chart.tracks if t.instrument == CHART_INSTRUMENT[part.instrument]]
        for i in check_reductions(trs, tm):
            source_ladder = part.take_difficulties == "all" and i.kind in _SOURCE_LADDER_KINDS
            issues.append(_issue(i, part.instrument, tm, pad, False if source_ladder else None))
        issues += [_issue(i, part.instrument, tm, pad) for i in check_phrases(trs, tm)]
        stem = next((s for s in STEMS_FOR[part.instrument] if s in levels_db), None)
        if stem:
            ex_ticks = sorted({n.tick for n in trs[0].notes})
            quiet = silent_onsets([tm.tick_to_sec(t) - pad for t in ex_ticks], levels_db[stem], LEVEL_FRAME_S)
            report["parts"][part.key]["silent_onsets"] = {"stem": stem, "count": len(quiet), "times": quiet[:50]}
            if quiet:
                warnings.append(f"part {part.key}: {len(quiet)} Expert onsets where the {stem} stem is silent "
                                f"(first at {quiet[0]:.2f} s)")

    # 5. the folder, built beside the output and moved there only when it passes the gate
    ratings, features = {}, {}
    for t in chart.tracks:
        if t.difficulty == "Expert" and t.notes:
            ratings[t.instrument], features[PART_INSTRUMENT[t.instrument]] = difficulty_rating(t, tm)
    if info.preview_start_ms is None:
        chorus = next((t for t, n in sections if n.lower().startswith("chorus")), None)
        info.preview_start_ms = round(tm.tick_to_sec(chorus) * 1000) if chorus is not None else None
    cfg.output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{cfg.output.name}.", suffix=".partial", dir=cfg.output.parent))
    try:
        pkg = build_song_folder(staging, chart, mix, lead.pad_samples, sr, difficulty=ratings,
                                album_art=cfg.album_art, background=cfg.background,
                                quality=cfg.quality)  # ffmpeg failing: a ToolError
        report["art"] = art_record(cfg, art)
        report["sync"] = {"ok": pkg.sync.ok, "summary": pkg.sync.summary(),
                          "max_abs_lag_samples": pkg.sync.max_abs_lag, "min_correlation": pkg.sync.min_correlation,
                          "length_difference": pkg.sync.length_difference}
        report["ratings"] = {PART_INSTRUMENT[k]: v for k, v in ratings.items()}
        report["rating_features"] = features
        report["preview_start_ms"] = info.preview_start_ms

        # 6. the gate
        record: dict[str, Any] = {}
        issues += verify_folder(staging, chart, pad, song_end, record=record)
        report["tracks"] = {}
        for t in chart.tracks:
            inst = PART_INSTRUMENT[t.instrument]
            stats = track_stats(t, tm, pad)
            ex = report["tracks"].get(inst, {}).get("expert")
            if ex and ex["onsets"]:
                stats["share_of_expert"] = round(stats["onsets"] / ex["onsets"], 3)
            report["tracks"].setdefault(inst, {})[LEVEL_KEY[t.difficulty]] = stats
        report["phrases"] = {PART_INSTRUMENT[t.instrument]: {
            "star_power": [(_in_s(tm, p.tick, pad), _in_s(tm, p.tick + p.length, pad)) for p in t.phrases
                           if p.kind == STAR_POWER],
            "fills": [(_in_s(tm, p.tick, pad), _in_s(tm, p.tick + p.length, pad)) for p in t.phrases
                      if p.kind == DRUM_ACTIVATION],
            "solos": [(_in_s(tm, a, pad), _in_s(tm, b, pad)) for a, b in t.solos],
            "star_power_count": sp_record.get(t.instrument)}
            for t in chart.tracks if t.difficulty == "Expert"}
        if solo_record and "guitar" in report["phrases"]:
            def solo_row(row: dict) -> dict:
                return {**row, "start": _in_s(tm, row["start"], pad), "end": _in_s(tm, row["end"], pad)}
            report["phrases"]["guitar"].update(
                solo_rules={**solo_record["rules"], "capped": solo_record["capped"]},
                solo_details=[solo_row(r) for r in solo_record["solos"]],
                solos_skipped_by_gap=[solo_row(r) for r in solo_record["skipped_by_gap"]],
                solos_trimmed_by_share=[solo_row(r) for r in solo_record["trimmed_by_share"]],
                solos_skipped_by_share=[solo_row(r) for r in solo_record["skipped_by_share"]])
        for t in chart.tracks:  # how many fills end on a crash (a source that labels crashes as hi-hats shows here)
            if t.difficulty == "Expert" and t.is_drums:
                crash = fill_crash_share(t, tm)
                report["phrases"]["drums"]["fill_crash_share"] = None if crash is None else round(crash, 3)
        errors = [i for i in issues if i.error]
        target = cfg.output if not errors else failed_folder(cfg.output)
        report["folder"] = str(target)
        report["gate"] = {"ok": not errors, "errors": len(errors), "warnings": len(issues) - len(errors),
                          "by_kind": _count(issues), "scan_chart": record.get("scan_chart"),
                          "issues": [asdict(i) for i in issues]}
        report["warnings"] = warnings
        (staging / "report.json").write_text(json.dumps(_jsonable(report), indent=1, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
        folder = _install(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if not errors:
        _remove_build(failed_folder(cfg.output))  # an earlier failed build is stale now
    return AssembleResult(folder, chart, report, grid, lead, replace(pkg, folder=folder), issues)


def art_record(cfg: AssembleConfig, art: dict | None) -> dict:
    """report.json's `art`: for the album art and the background, whether it was added and its file in the folder,
    with where it came from (`art`, the pipeline's record; "config" when only the config named the image)."""
    out = {}
    for key, image, name in (("album_art", cfg.album_art, "album"), ("background", cfg.background, "background")):
        given = {k: v for k, v in ((art or {}).get(key) or {}).items() if k not in ("added", "file")}
        if image is None:
            out[key] = {"added": False, "file": None, "from": None, **{k: v for k, v in given.items() if k == "why"}}
        else:
            out[key] = {"added": True, "file": name + image.suffix.lower(), "from": "config", **given}
    return out


def _count(issues: list[GateIssue]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in issues:
        key = f"{'error' if i.error else 'warning'}:{i.kind}"
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))
