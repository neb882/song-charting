"""Importers: another tool's .chart or .mid, read as a TimedSong in seconds of the input audio.

A chart is read the way Clone Hero plays it. Every rule follows scan-chart (the parser behind Chorus Encore, Clone
Hero's song site; tools/scan-chart/node_modules/scan-chart/src/chart), so each note gets the time, lanes and HOPO,
tap and cymbal state the game gives it:

  * time: tick to ms with scan-chart's float arithmetic, then seconds, plus the chart's own offset (.chart `Offset`,
    or song.ini `delay` when that is non-zero; both delay the notes) and the caller's `time_offset`.
  * HOPO: natural when the note is a single fret, differs from the previous note and starts at most the threshold
    after it (floor(65/192 x resolution) ticks in .chart, floor(1 + resolution/3) in .mid). In .mid a note that was
    part of the previous chord is never natural. Forcing comes on top: `N 5` flips the natural state in .chart, the
    forced-HOPO and forced-strum notes set it in .mid. Taps: `N 6`, .mid note 104 or the Phase Shift SysEx.
  * sustains: in .mid a sustain of floor(resolution/3) + 1 ticks or less is no sustain; .chart keeps every length.
    A sustain that runs into the next note on its lane stops there, and that note carries what was left of it.
  * drums: pro (with cymbals) when song.ini sets pro_drums or when any drum track has a cymbal or tom marker.
    In .mid yellow, blue and green are cymbals unless a tom marker (110-112) covers them; in .chart they are toms
    unless a cymbal marker (66-68) shares their tick. 5-lane drums map as scan-chart maps them.
  * star power and solos: a phrase that overlaps the next one ends where it starts. A .chart solo includes the note
    on its `soloend` tick.

What the TimedSong contract leaves open, decided here:
  * TimedNote.hopo is never None. For a tap it is the state the note would have without its tap.
    TimedNote.hopo_forced is True where forcing made that state differ from the natural one on the source's map.
  * A chord's `end` is its longest sustain. An open note charted on the same tick as frets is dropped from the chord.
  * A TimedSpan is half-open: a note at t is inside it when start <= t < end.
  * activation holds drum fills only (`S 64`, .mid note 120, in a drum track before any [coda] event); big rock
    endings are left out.
  * beats: one every `resolution` ticks (the beat the BPM counts) from tick 0 to the chart's last event.
  * measures: the measure lines of the time signatures (.chart `TS n [d]`, the denominator 2^d, /4 without it; .mid
    track 0's time-signature events; 4/4 before the first), a measure being resolution x 4 x n / denominator ticks.
    Each time signature opens a new measure on its own tick, as Moonscraper and TempoMap.measure_starts place them.
    They run to the last beat and one line past it, so the last two lines are a whole measure of the last meter.

Not read: disco flips, flams, rolls and trills, lyrics and vocals, and instruments other than guitar, bass and drums.
"""
from __future__ import annotations

import bisect
import math
import re
import struct
from dataclasses import dataclass, field
from enum import IntEnum
from fractions import Fraction
from pathlib import Path

from .errors import InputError
from .timed import DIFFICULTIES, INSTRUMENTS, OPEN, TimedHit, TimedNote, TimedPart, TimedSong, TimedSpan


@dataclass(frozen=True)
class ChartModifiers:
    """The song.ini settings that change how Clone Hero reads a chart (scan-chart's IniChartModifiers)."""
    hopo_frequency: float = 0             # natural HOPO threshold in ticks; 0 = the format's default
    eighthnote_hopo: bool = False         # threshold floor(1 + resolution/2): an 8th note
    sustain_cutoff_threshold: float = -1  # sustains this many ticks long or shorter are cut; -1 = the format's default
    chord_snap_threshold: float = 0       # a note this many ticks or fewer after a chord joins it; 0 = off
    multiplier_note: float = 0            # 103: .mid guitar/bass star power is on note 103 (GH1/GH2 charts)
    pro_drums: bool = False
    five_lane_drums: bool = False
    delay_ms: float = 0                   # song.ini delay: later notes; when non-zero it replaces the .chart Offset


class _E(IntEnum):
    """Raw track event types, numbered as scan-chart's eventTypes: .mid events on one tick are ordered by them."""
    STAR_POWER = 0
    SOLO = 1
    REJECTED_STAR_POWER = 2
    SOLO_START = 3
    SOLO_END = 4
    OPEN = 5
    GREEN = 6
    RED = 7
    YELLOW = 8
    BLUE = 9
    ORANGE = 10
    KICK = 17
    KICK_2X = 18
    RED_DRUM = 19
    YELLOW_DRUM = 20
    BLUE_DRUM = 21
    GREEN_DRUM = 22        # 4-lane green, 5-lane orange
    FIVE_GREEN_DRUM = 23   # 5-lane green
    FLEX_SINGLE = 24
    FLEX_DOUBLE = 25
    FREESTYLE = 26         # drum fill, or a big rock ending after [coda]
    FORCE_OPEN = 27
    FORCE_TAP = 28
    FORCE_STRUM = 29
    FORCE_HOPO = 30
    FORCE_UNNATURAL = 31
    FLAM = 32
    YELLOW_TOM = 33
    BLUE_TOM = 34
    GREEN_TOM = 35
    YELLOW_CYMBAL = 36
    BLUE_CYMBAL = 37
    GREEN_CYMBAL = 38
    RED_GHOST = 39
    YELLOW_GHOST = 40
    BLUE_GHOST = 41
    GREEN_GHOST = 42
    FIVE_GREEN_GHOST = 43
    KICK_GHOST = 44
    RED_ACCENT = 45
    YELLOW_ACCENT = 46
    BLUE_ACCENT = 47
    GREEN_ACCENT = 48
    FIVE_GREEN_ACCENT = 49
    KICK_ACCENT = 50
    DYNAMICS = 54          # .mid [ENABLE_CHART_DYNAMICS]


_FRETS = {_E.OPEN: OPEN, _E.GREEN: 0, _E.RED: 1, _E.YELLOW: 2, _E.BLUE: 3, _E.ORANGE: 4}  # event -> lane
_KICKS = (_E.KICK, _E.KICK_2X)
_HANDS = {_E.RED_DRUM: 1, _E.YELLOW_DRUM: 2, _E.BLUE_DRUM: 3, _E.GREEN_DRUM: 4, _E.FIVE_GREEN_DRUM: 4}  # -> pad
_MARKERS = {_E.YELLOW_TOM, _E.BLUE_TOM, _E.GREEN_TOM, _E.YELLOW_CYMBAL, _E.BLUE_CYMBAL, _E.GREEN_CYMBAL}
_ACCENT_GHOST = {  # drum note -> (its accent modifier, its ghost modifier)
    _E.KICK: (_E.KICK_ACCENT, _E.KICK_GHOST), _E.KICK_2X: (_E.KICK_ACCENT, _E.KICK_GHOST),
    _E.RED_DRUM: (_E.RED_ACCENT, _E.RED_GHOST), _E.YELLOW_DRUM: (_E.YELLOW_ACCENT, _E.YELLOW_GHOST),
    _E.BLUE_DRUM: (_E.BLUE_ACCENT, _E.BLUE_GHOST), _E.GREEN_DRUM: (_E.GREEN_ACCENT, _E.GREEN_GHOST),
    _E.FIVE_GREEN_DRUM: (_E.FIVE_GREEN_ACCENT, _E.FIVE_GREEN_GHOST),
}

# scan-chart's noteFlags bits (their values decide which duplicate note survives)
_STRUM, _HOPO, _TAP, _DOUBLE_KICK, _TOM, _CYMBAL, _GHOST, _ACCENT = 1, 2, 4, 8, 16, 32, 512, 1024
_FOUR_LANE, _PRO, _FIVE_LANE = 0, 1, 2  # drum types


# ------------------------------------------------------------------------------------------------ public API

def read_chart(path, time_offset: float = 0.0, *, modifiers: ChartModifiers | None = None,
               source: str | None = None) -> TimedSong:
    """A .chart file. modifiers: song.ini settings (none by default; `read_song` reads them from the folder)."""
    mods = modifiers or ChartModifiers()
    raw = _parse_chart(_decode(Path(path).read_bytes()))
    return _build(raw, "chart", mods, time_offset, source or str(path))


def read_mid(path, time_offset: float = 0.0, *, modifiers: ChartModifiers | None = None,
             source: str | None = None) -> TimedSong:
    """A Clone Hero / Rock Band .mid file (tempo map in track 0; PART GUITAR, PART BASS, PART DRUMS, EVENTS)."""
    mods = modifiers or ChartModifiers()
    raw = _parse_mid(Path(path).read_bytes(), mods)
    return _build(raw, "mid", mods, time_offset, source or str(path))


def read_song(path, time_offset: float = 0.0, *, source: str | None = None) -> TimedSong:
    """A song folder or one chart file in it, read with the folder's song.ini settings.

    In a folder the chart is chosen as scan-chart chooses it: notes.mid, then notes.chart, then any other .mid or
    .chart. The ini is song.ini, or else the folder's last other .ini.
    """
    p = Path(path)
    folder = p if p.is_dir() else p.parent
    chart = _find_chart(p) if p.is_dir() else p
    inis = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() == ".ini")
    ini = next((f for f in inis if f.name == "song.ini"), inis[-1] if inis else None)
    mods = read_ini_modifiers(ini) if ini else ChartModifiers()
    read = read_mid if chart.suffix.lower() == ".mid" else read_chart
    return read(chart, time_offset, modifiers=mods, source=source)


def read_ini_modifiers(path) -> ChartModifiers:
    """The chart-reading settings of a song.ini (values as scan-chart parses them; -1 means unset)."""
    song: dict[str, str] = {}
    section = None
    for line in _decode(Path(path).read_bytes()).splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("["):
            m = re.fullmatch(r"\[(.+)\]", line)
            section = m[1].strip().lower() if m else section
        elif "=" in line and section == "song":
            key, _, value = line.partition("=")
            song[key.strip().lower()] = value.strip()

    def number(key, legacy=None, default=0.0):
        for k in (key, legacy):
            m = re.match(r"\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?", song.get(k, "")) if k else None
            if m and float(m[0]) != -1:  # parseFloat, with -1 meaning unset
                return float(m[0])
        return default

    def flag(key):
        return song.get(key, "").lower() in ("true", "1")

    return ChartModifiers(
        hopo_frequency=number("hopo_frequency", "hopofreq"),
        eighthnote_hopo=flag("eighthnote_hopo"),
        sustain_cutoff_threshold=number("sustain_cutoff_threshold", default=-1),
        chord_snap_threshold=number("chord_snap_threshold"),
        multiplier_note=number("multiplier_note", "star_power_note"),
        pro_drums=flag("pro_drums"),
        five_lane_drums=flag("five_lane_drums"),
        delay_ms=number("delay"),
    )


def _find_chart(folder: Path) -> Path:
    files = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in (".chart", ".mid"))
    if not files:
        raise FileNotFoundError(f"no .chart or .mid in {folder}")
    # scan-chart: the notes.* name first, then .mid before .chart
    return min(files, key=lambda f: (f.name not in ("notes.chart", "notes.mid"), f.suffix.lower() != ".mid"))


def _decode(data: bytes) -> str:
    """Text as scan-chart decodes it: UTF-16 with a byte-order mark, else UTF-8 (a UTF-8 BOM is dropped)."""
    if data[:2] == b"\xff\xfe":
        return data[2:].decode("utf-16-le", errors="replace")
    if data[:2] == b"\xfe\xff":
        return data[2:].decode("utf-16-be", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


# ------------------------------------------------------------------------------------------------ raw chart data

@dataclass(slots=True)
class _Ev:
    """One raw track event: a note, a modifier or a phrase, with its length in ticks."""
    tick: int
    length: int
    type: int
    velocity: int = 127
    channel: int = 0


@dataclass
class _RawTrack:
    instrument: str
    difficulty: str
    events: list[_Ev] = field(default_factory=list)      # notes and modifiers
    star_power: list[_Ev] = field(default_factory=list)
    solos: list[_Ev] = field(default_factory=list)       # length includes a .chart soloend tick
    fills: list[_Ev] = field(default_factory=list)       # drum activation lanes (big rock endings removed)


@dataclass
class _Raw:
    """A chart before any rule is applied (scan-chart's RawChartData)."""
    resolution: int
    offset: float                     # seconds the notes are delayed against the audio
    tempos: list[tuple[int, float]]   # (tick, BPM), the first at tick 0
    sections: list[tuple[int, str]]
    tracks: list[_RawTrack]
    signatures: list[tuple[int, int, int]] = field(default_factory=list)  # (tick, numerator, denominator)


def _sort_track(t: _RawTrack, events: list[_Ev], first_coda: int | None) -> _RawTrack:
    for e in events:
        if e.type == _E.STAR_POWER:
            t.star_power.append(e)
        elif e.type == _E.SOLO:
            t.solos.append(e)
        elif e.type == _E.FREESTYLE:
            if first_coda is None or e.tick < first_coda:
                t.fills.append(e)
        elif e.type not in (_E.REJECTED_STAR_POWER, _E.FLEX_SINGLE, _E.FLEX_DOUBLE):
            t.events.append(e)
    return t


def _tempo_list(tempos: list[tuple[int, float]]) -> list[tuple[int, float]]:
    if any(bpm <= 0 for _, bpm in tempos):
        raise InputError("tempo marker of zero BPM")
    if not tempos or tempos[0][0] != 0:
        tempos.insert(0, (0, 120.0))  # the default tempo before the first marker
    return sorted(tempos, key=lambda t: t[0])


# ------------------------------------------------------------------------------------------------ .chart

_CHART_TRACKS = {f"{d.capitalize()}{name}": (inst, d)
                 for name, inst in (("Single", "guitar"), ("DoubleBass", "bass"), ("Drums", "drums"))
                 for d in DIFFICULTIES}
_CHART_FRET = {"0": _E.GREEN, "1": _E.RED, "2": _E.YELLOW, "3": _E.BLUE, "4": _E.ORANGE,
               "5": _E.FORCE_UNNATURAL, "6": _E.FORCE_TAP, "7": _E.OPEN}
_CHART_DRUM = {"0": _E.KICK, "1": _E.RED_DRUM, "2": _E.YELLOW_DRUM, "3": _E.BLUE_DRUM, "4": _E.GREEN_DRUM,
               "5": _E.FIVE_GREEN_DRUM, "32": _E.KICK_2X,
               "34": _E.RED_ACCENT, "35": _E.YELLOW_ACCENT, "36": _E.BLUE_ACCENT, "37": _E.GREEN_ACCENT,
               "38": _E.FIVE_GREEN_ACCENT,
               "40": _E.RED_GHOST, "41": _E.YELLOW_GHOST, "42": _E.BLUE_GHOST, "43": _E.GREEN_GHOST,
               "44": _E.FIVE_GREEN_GHOST,
               "66": _E.YELLOW_CYMBAL, "67": _E.BLUE_CYMBAL, "68": _E.GREEN_CYMBAL}
_CHART_PHRASE = {"2": _E.STAR_POWER, "64": _E.FREESTYLE, "65": _E.FLEX_SINGLE, "66": _E.FLEX_DOUBLE}
_CHART_SOLO = {"solo": _E.SOLO_START, "soloend": _E.SOLO_END}

# scan-chart's line patterns, matched against whole trimmed lines
_RE_META = re.compile(r'(.+?) = "?(.*?)"?')
_RE_TEMPO = re.compile(r"(\d+) = B (\d+)", re.ASCII)
_RE_TS = re.compile(r"(\d+) = TS (\d+)(?: (\d+))?", re.ASCII)
_RE_SECTION = re.compile(r'(\d+) = E "\[?(?:section|prc)[ _](.*?)\]?"', re.ASCII)
_RE_CODA = re.compile(r'(\d+) = E "\s*\[?coda\]?\s*"', re.ASCII)
_RE_EVENT = re.compile(r"(\d+) = ([A-Z]+) ([\w\s\[\]]+?)( \d+)?", re.ASCII)


def _chart_sections(text: str) -> dict[str, list[str]]:
    """The [Name] { ... } blocks as trimmed, non-empty lines, found as scan-chart finds them: on each line, only the
    text before an `=` or `{` can open or close a block."""
    out: dict[str, list[str]] = {}
    name, start, pos = None, 0, 0
    for line in text.split("\n"):
        i = 0
        while i < len(line):
            c = line[i]
            if c == "=":
                break
            if c == "{":
                start = pos + i + 1
                break
            if c == "}":
                if name is None:
                    raise InputError("not a .chart: a block ends before any [section] name")
                out[name] = [s.strip() for s in text[start:pos + i].split("\n") if s.strip()]
            elif c == "[":
                j = line.find("]", i + 1)
                if j < 0:
                    raise InputError("not a .chart: unterminated [section] name")
                name, start, i = line[i + 1:j], pos + i + 1, j
            i += 1
        pos += len(line) + 1
    return out


def _number(s: str | None) -> float:
    try:
        return float(s) if s else 0.0
    except ValueError:
        return 0.0


def _parse_chart(text: str) -> _Raw:
    sections = _chart_sections(text)
    if not sections:
        raise InputError("not a .chart: no sections")
    meta = dict(m.groups() for m in map(_RE_META.fullmatch, sections.get("Song", [])) if m)
    res = _number(meta.get("Resolution"))
    if not res:
        raise InputError("not a .chart: no Resolution")
    res = int(res) if res.is_integer() else res
    sync = sections.get("SyncTrack", [])
    tempos = _tempo_list([(int(m[1]), int(m[2]) / 1000) for m in map(_RE_TEMPO.fullmatch, sync) if m])
    signatures = [(int(m[1]), int(m[2]), 2 ** int(m[3]) if m[3] else 4)
                  for m in map(_RE_TS.fullmatch, sync) if m and (not m[3] or int(m[3]) <= _MAX_DEN_LOG2)]
    events = sections.get("Events", [])
    names = [(int(m[1]), m[2]) for m in map(_RE_SECTION.fullmatch, events) if m]
    codas = [int(m[1]) for m in map(_RE_CODA.fullmatch, events) if m]
    first_coda = codas[0] if codas else None
    tracks = []
    for name, lines in sections.items():
        if name not in _CHART_TRACKS:
            continue
        inst, diff = _CHART_TRACKS[name]
        notes = _CHART_DRUM if inst == "drums" else _CHART_FRET
        evs = []
        for m in map(_RE_EVENT.fullmatch, lines):
            if not m:
                continue
            code, value = m[2], m[3]
            typ = (notes.get(value) if code == "N" else _CHART_PHRASE.get(value) if code == "S"
                   else _CHART_SOLO.get(value) if code == "E" else None)
            if typ is not None:
                evs.append(_Ev(int(m[1]), int(m[4]) if m[4] else 0, typ))
        evs.sort(key=lambda e: e.tick)
        tracks.append(_sort_track(_RawTrack(inst, diff), _merge_solos(evs), first_coda))
    return _Raw(res, _number(meta.get("Offset")), tempos, names, tracks, signatures)


def _merge_solos(evs: list[_Ev]) -> list[_Ev]:
    """`E solo` ... `E soloend` pairs become one solo event, one tick longer so the soloend tick is inside."""
    starts = []
    for e in evs:
        if e.type == _E.SOLO_START:
            starts.append(e)
        elif e.type == _E.SOLO_END and starts:
            s = starts.pop()
            s.type, s.length = _E.SOLO, e.tick - s.tick + 1
    return [e for e in evs if e.type not in (_E.SOLO_START, _E.SOLO_END)]


# ------------------------------------------------------------------------------------------------ .mid

_MID_TRACKS = (("PART GUITAR", "guitar"), ("T1 GEMS", "guitar"), ("PART BASS", "bass"), ("PART DRUMS", "drums"))
_MID_NAMES = {name for name, _ in _MID_TRACKS} | {"EVENTS"}
_FRET_BASE = {"easy": 59, "medium": 71, "hard": 83, "expert": 95}   # 5-fret: base + 0 open, 1-5 G..O, 6 HOPO, 7 strum
_DRUM_BASE = {"easy": 60, "medium": 72, "hard": 84, "expert": 96}   # drums: base - 1 2x kick, 0 kick, 1-5 pads
_FRET_OFFSET = {1: _E.GREEN, 2: _E.RED, 3: _E.YELLOW, 4: _E.BLUE, 5: _E.ORANGE, 6: _E.FORCE_HOPO, 7: _E.FORCE_STRUM}
_DRUM_OFFSET = {-1: _E.KICK_2X, 0: _E.KICK, 1: _E.RED_DRUM, 2: _E.YELLOW_DRUM, 3: _E.BLUE_DRUM, 4: _E.GREEN_DRUM,
                5: _E.FIVE_GREEN_DRUM}
_MID_ALL = {103: _E.SOLO, 104: _E.FORCE_TAP, 109: _E.FLAM, 110: _E.YELLOW_TOM, 111: _E.BLUE_TOM, 112: _E.GREEN_TOM,
            116: _E.STAR_POWER, 120: _E.FREESTYLE, 126: _E.FLEX_SINGLE, 127: _E.FLEX_DOUBLE}  # every difficulty
_SYSEX_DIFF = {0: "easy", 1: "medium", 2: "hard", 3: "expert", 0xFF: "all"}
_RE_MID_SECTION = re.compile(r"\[?(?:section|prc)[ _]([^\]]*)\]?")


def _text(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1")


def _read_smf(data: bytes) -> tuple[int, list[list[tuple]]]:
    """A Standard MIDI File as (ticks per beat, tracks). Each track is a list of (absolute tick, kind, *values) for
    the events an importer needs: tempo, name, text, on, off (channel, note, velocity) and sysex. As in scan-chart's
    MIDI library, a note on with velocity 0 is a note off and running status carries across meta and SysEx events."""
    if len(data) < 14 or data[:4] != b"MThd":
        raise InputError("not a MIDI file")
    fmt, count, division = struct.unpack(">HHH", data[8:14])
    if fmt != 1:
        raise InputError(f"MIDI format {fmt}: charts are format 1")
    if division & 0x8000:
        raise InputError("MIDI time in SMPTE frames is not supported")
    pos = 8 + int.from_bytes(data[4:8], "big")
    tracks = []
    while pos + 8 <= len(data) and len(tracks) < count:
        size = int.from_bytes(data[pos + 4:pos + 8], "big")
        if data[pos:pos + 4] == b"MTrk":
            tracks.append(_read_track(data[pos + 8:pos + 8 + size]))
        pos += 8 + size
    if not tracks:
        raise InputError("MIDI file without tracks")
    return division, tracks


def _read_track(b: bytes) -> list[tuple]:
    out: list[tuple] = []
    pos, tick, status = 0, 0, None

    def varint():
        nonlocal pos
        v = 0
        while True:
            c = b[pos]
            pos += 1
            v = (v << 7) | (c & 0x7F)
            if not c & 0x80:
                return v

    try:
        while pos < len(b):
            tick += varint()
            st = b[pos]
            pos += 1
            if st == 0xFF:
                kind = b[pos]
                pos += 1
                n = varint()
                payload, pos = b[pos:pos + n], pos + n
                if kind == 0x51 and n == 3:
                    out.append((tick, "tempo", int.from_bytes(payload, "big")))
                elif kind == 0x58 and n >= 2:
                    out.append((tick, "ts", payload[0], payload[1]))  # numerator, log2 of the denominator
                elif kind in (0x01, 0x03):
                    out.append((tick, "text" if kind == 0x01 else "name", _text(payload)))
            elif st in (0xF0, 0xF7):
                n = varint()
                out.append((tick, "sysex", b[pos:pos + n]))
                pos += n
            elif st > 0xF0:
                raise InputError(f"bad MIDI status byte {st:#x}")
            else:
                if st < 0x80:  # running status: this byte is the first data byte
                    if status is None:
                        raise InputError("MIDI running status before any status byte")
                    p1, st = st, status
                else:
                    status, p1 = st, b[pos]
                    pos += 1
                kind = st >> 4
                if kind in (0x8, 0x9):
                    vel = b[pos]
                    pos += 1
                    out.append((tick, "on" if kind == 0x9 and vel else "off", st & 0x0F, p1, vel))
                elif kind in (0xA, 0xB, 0xE):
                    pos += 1
    except IndexError:
        pass  # a track cut short ends at its last whole event
    return out


@dataclass(slots=True)
class _End:
    """One end of a .mid event (a note on or off, a SysEx switch), before starts and ends are paired."""
    tick: int
    type: int
    velocity: int
    channel: int
    start: bool


def _parse_mid(data: bytes, mods: ChartModifiers) -> _Raw:
    resolution, tracks = _read_smf(data)
    tempos, signatures = [], []
    for tick, kind, *v in tracks[0]:
        if kind == "tempo":
            if not v[0]:
                raise InputError("MIDI tempo of zero microseconds per beat")
            tempos.append((tick, 60000000 / v[0]))
        elif kind == "ts" and v[1] <= _MAX_DEN_LOG2:
            signatures.append((tick, v[0], 2 ** v[1]))
    named: dict[str, list[tuple]] = {}
    for track in tracks:
        name = None
        for tick, kind, *v in track:  # the name must come before the track's first event after tick 0
            if tick:
                break
            if kind == "name" and v[0] in _MID_NAMES:
                name = v[0]
        if name is not None and name not in named:
            named[name] = track
    texts = [(tick, v[0]) for tick, kind, *v in named.get("EVENTS", []) if kind == "text"]
    sections = [(tick, m[1]) for tick, text in texts if (m := _RE_MID_SECTION.fullmatch(text))]
    first_coda = next((tick for tick, text in texts if text.strip() in ("coda", "[coda]")), None)
    raw_tracks = []
    done = set()
    for name, inst in _MID_TRACKS:
        if name not in named or inst in done:
            continue
        done.add(inst)
        drums = inst == "drums"
        per_diff = _mid_split_modifiers(_mid_pair(_mid_ends(named[name], drums)), drums)
        if not drums:
            _legacy_star_power(per_diff, mods)
        for diff in DIFFICULTIES:
            t = _sort_track(_RawTrack(inst, diff), per_diff[diff], first_coda)
            if t.events:
                raw_tracks.append(t)
    return _Raw(resolution, 0.0, _tempo_list(tempos), sections, raw_tracks, signatures)


def _mid_ends(track: list[tuple], drums: bool) -> dict[str, list[_End]]:
    """Every note on/off and SysEx switch the chart spec defines, by difficulty ("all": instrument-wide)."""
    ends: dict[str, list[_End]] = {d: [] for d in ("all",) + DIFFICULTIES}
    enhanced_opens = False  # [ENHANCED_OPENS]: the note below green is an open note, from that event on
    for tick, kind, *v in track:
        if kind == "sysex":
            d = v[0]
            if len(d) > 6 and d[:4] == b"PS\x00\x00" and d[5] in (1, 4) and d[4] in _SYSEX_DIFF:
                typ = _E.FORCE_OPEN if d[5] == 1 else _E.FORCE_TAP
                ends[_SYSEX_DIFF[d[4]]].append(_End(tick, typ, 127, 1, d[6] == 1))
        elif kind in ("on", "off"):
            channel, note, velocity = v
            diff = ("easy" if note <= 66 else "medium" if note <= 78 else "hard" if note <= 90
                    else "expert" if note <= 102 else "all")
            if diff == "all":
                typ = _MID_ALL.get(note)
            elif drums:
                typ = _DRUM_OFFSET.get(note - _DRUM_BASE[diff])
            else:
                off = note - _FRET_BASE[diff]
                typ = (_E.OPEN if enhanced_opens else None) if off == 0 else _FRET_OFFSET.get(off)
            if typ is not None:
                ends[diff].append(_End(tick, typ, velocity, channel, kind == "on"))
        elif kind == "text":
            if v[0] in ("ENHANCED_OPENS", "[ENHANCED_OPENS]"):
                enhanced_opens = True
            elif v[0] in ("ENABLE_CHART_DYNAMICS", "[ENABLE_CHART_DYNAMICS]"):
                ends["all"] += [_End(tick, _E.DYNAMICS, 127, 1, True), _End(tick, _E.DYNAMICS, 127, 1, False)]
    return ends


def _mid_pair(ends: dict[str, list[_End]]) -> dict[str, list[_Ev]]:
    """Instrument-wide ends copied into each charted difficulty, then each end paired with the latest open start of
    its type on its channel. Starts that never end are dropped."""
    out = {}
    for diff in DIFFICULTIES:
        own = ends[diff]
        stream = own + [_End(e.tick, e.type, e.velocity, e.channel, e.start) for e in ends["all"]] if own else []
        stream.sort(key=lambda e: (e.tick, -e.type))  # stable, as scan-chart's orderBy
        events, open_ = [], {}
        for e in stream:
            starts = open_.setdefault(e.type, [])
            if e.start:
                ev = _Ev(e.tick, -1, e.type, e.velocity, e.channel)
                starts.append(ev)
                events.append(ev)
            else:
                for i in range(len(starts) - 1, -1, -1):
                    if starts[i].channel == e.channel:
                        ev = starts.pop(i)
                        ev.length = e.tick - ev.tick
                        break
        out[diff] = [e for e in events if e.length != -1]
    return out


def _mid_split_modifiers(events: dict[str, list[_Ev]], drums: bool) -> dict[str, list[_Ev]]:
    """.mid modifiers held over notes (HOPO, strum, tap, open; tom markers, flams) become one zero-length modifier
    on each note tick they cover (their end tick excluded), as .chart stores them. Chart dynamics turn drum
    velocities 1 and 127 into ghosts and accents."""
    held = ({_E.FLAM, _E.YELLOW_TOM, _E.BLUE_TOM, _E.GREEN_TOM} if drums
            else {_E.FORCE_OPEN, _E.FORCE_TAP, _E.FORCE_STRUM, _E.FORCE_HOPO})
    notes = set(_KICKS) | set(_HANDS) if drums else set(_FRETS)
    dynamics = False  # once seen, on for the rest of the track (scan-chart keeps it across difficulties)
    out = {}
    for diff in DIFFICULTIES:
        has_notes, active, latest, new = False, [], {}, []
        for e in events[diff]:
            if e.type == _E.DYNAMICS:
                dynamics = True
                continue
            # a held modifier covers [tick, tick + length); a zero-length one only its own tick
            active = [m for m in active if m.tick + m.length > e.tick or (m.length == 0 and m.tick >= e.tick)]
            if e.type in held:
                active.append(e)
                continue
            if e.type in notes:
                has_notes = True
                for m in active:
                    if m.type not in latest or latest[m.type].tick < e.tick:
                        latest[m.type] = _Ev(e.tick, 0, m.type, m.velocity, m.channel)
                        new.append(latest[m.type])
                if dynamics and drums and e.velocity in (1, 127):
                    accent, ghost = _ACCENT_GHOST[e.type]
                    new.append(_Ev(e.tick, 0, ghost if e.velocity == 1 else accent, 127, e.channel))
            new.append(e)
        out[diff] = new if has_notes else []
    return out


def _legacy_star_power(events: dict[str, list[_Ev]], mods: ChartModifiers) -> None:
    """GH1/GH2 .mid charts put star power on note 103: used when multiplier_note says so, or when a guitar or bass
    difficulty has no note-116 phrase but more than one note-103 phrase."""
    if mods.multiplier_note == 116:
        return
    for evs in events.values():
        sp = [e for e in evs if e.type == _E.STAR_POWER]
        solos = [e for e in evs if e.type == _E.SOLO]
        if mods.multiplier_note == 103 or (not sp and len(solos) > 1):
            for e in solos:
                e.type = _E.STAR_POWER
            for e in sp:
                e.type = _E.REJECTED_STAR_POWER


# ------------------------------------------------------------------------------------------------ shared rules

_MAX_DEN_LOG2 = 16  # a time signature over more than 2^16 is not a meter: left out


def _measure_ticks(signatures: list[tuple[int, int, int]], res, end) -> list[Fraction]:
    """Measure-line ticks: 4/4 from tick 0 until the first time signature, each signature opening a measure on its
    own tick, up to `end` and one line past it. Lengths stay exact (15/16 at an odd resolution is a fraction of a
    tick). A signature with a zero numerator, or a measure under one tick, is left out; the last one on a tick wins."""
    length = {0: Fraction(4) * Fraction(res)}
    for tick, num, den in sorted(signatures, key=lambda s: s[0]):
        m = Fraction(res) * 4 * num / den
        if num > 0 and m >= 1:
            length[tick] = m
    ticks = sorted(t for t in length if t <= end)
    out: list[Fraction] = []
    for t, stop in zip(ticks, ticks[1:] + [None]):
        m, step = Fraction(t), length[t]
        while (m < stop) if stop is not None else (m <= end):
            out.append(m)
            m += step
    out.append(m)  # the line past the end
    return out


class _Clock:
    """Chart ticks to milliseconds with scan-chart's float64 arithmetic, operation for operation."""

    def __init__(self, resolution, tempos: list[tuple[int, float]]):
        self.resolution = resolution
        self.ticks = [t for t, _ in tempos]
        self.bpms = [b for _, b in tempos]
        self.ms_at = [0.0]
        for (t0, b0), (t1, _) in zip(tempos, tempos[1:]):
            self.ms_at.append(self.ms_at[-1] + ((t1 - t0) * 60000) / (b0 * resolution))

    def ms(self, tick: float) -> float:
        i = max(bisect.bisect_right(self.ticks, tick) - 1, 0)
        return self.ms_at[i] + ((tick - self.ticks[i]) * 60000) / (self.bpms[i] * self.resolution)


@dataclass(slots=True)
class _Note:
    tick: int
    length: int
    lane: int    # fret lane 0-4 or OPEN; drum pad 0-4
    flags: int   # scan-chart's noteFlags bits


@dataclass(slots=True)
class _Group:
    """The notes on one tick: a single note, a chord, or a drum hit on several pads."""
    notes: list[_Note]
    hopo: bool = False   # 5-fret: the HOPO state, tap aside
    forced: bool = False  # 5-fret: forcing made that state differ from the natural one


def _by_tick(events: list[_Ev]) -> list[list[_Ev]]:
    groups: dict[int, list[_Ev]] = {}
    for e in events:
        groups.setdefault(e.tick, []).append(e)
    return [groups[t] for t in sorted(groups)]


def _resolve_frets(groups: list[list[_Ev]], mods: ChartModifiers, res, fmt: str) -> list[_Group]:
    threshold = mods.hopo_frequency or math.floor(
        1 + res / 2 if mods.eighthnote_hopo else 1 + res / 3 if fmt == "mid" else 65 / 192 * res)
    out = []
    last_tick, last_kinds = 0, None
    for evs in groups:
        if any(e.type == _E.FORCE_OPEN for e in evs):  # .mid open: the longest note of the chord becomes open
            frets = [e for e in evs if e.type in _FRETS]
            if frets:
                longest = max(frets, key=lambda e: e.length)
                evs = [e for e in evs if e.type not in _FRETS and e.type != _E.FORCE_OPEN] + [longest]
                longest.type = _E.OPEN
        frets = [e for e in evs if e.type in _FRETS]
        if not frets:
            continue
        types = {e.type for e in evs}
        kinds = {e.type for e in frets}
        tick = frets[0].tick
        natural = (last_kinds is not None and tick - last_tick <= threshold and len(kinds) == 1
                   and len(kinds | last_kinds) > 1  # not the same single fret again
                   and not (fmt == "mid" and len(last_kinds) > 1 and kinds <= last_kinds))
        hopo = (True if _E.FORCE_HOPO in types else False if _E.FORCE_STRUM in types
                else natural != (_E.FORCE_UNNATURAL in types))
        flags = _TAP if _E.FORCE_TAP in types else _HOPO if hopo else _STRUM
        out.append(_Group([_Note(e.tick, e.length, _FRETS[e.type], flags) for e in frets], hopo, hopo != natural))
        last_tick, last_kinds = tick, kinds
    return out


def _resolve_drums(groups: list[list[_Ev]], drum_type: int, fmt: str) -> list[_Group]:
    out = []
    for evs in groups:
        kicks = [e for e in evs if e.type in _KICKS]
        hands = [e for e in evs if e.type in _HANDS]
        if not kicks and not hands:
            continue
        marks = {e.type for e in evs if e.type not in _HANDS and e.type not in _KICKS}  # the tick's modifiers
        notes = [_Note(e.tick, e.length, 0, (_DOUBLE_KICK if e.type == _E.KICK_2X else 0) | _dynamics(e.type, marks))
                 for e in kicks]
        types = {e.type for e in hands}
        orange_and_green = _E.GREEN_DRUM in types and _E.FIVE_GREEN_DRUM in types  # 5-lane: green moves to blue
        for e in hands:
            pad = 3 if e.type == _E.FIVE_GREEN_DRUM and orange_and_green else _HANDS[e.type]
            flags = _tom_or_cymbal(e.type, marks, drum_type, fmt) | _dynamics(e.type, marks)
            notes.append(_Note(e.tick, e.length, pad, flags))
        out.append(_Group(notes))
    return out


def _dynamics(typ: int, marks: set) -> int:
    accent, ghost = _ACCENT_GHOST[typ]
    return _ACCENT if accent in marks else _GHOST if ghost in marks else 0


def _tom_or_cymbal(typ: int, marks: set, drum_type: int, fmt: str) -> int:
    if drum_type == _FOUR_LANE:
        return _TOM
    if drum_type == _FIVE_LANE:
        return _CYMBAL if typ in (_E.YELLOW_DRUM, _E.GREEN_DRUM) else _TOM
    if typ in (_E.RED_DRUM, _E.FIVE_GREEN_DRUM):
        return _TOM
    if fmt == "mid":  # cymbals unless a tom marker covers them
        tom = {_E.YELLOW_DRUM: _E.YELLOW_TOM, _E.BLUE_DRUM: _E.BLUE_TOM, _E.GREEN_DRUM: _E.GREEN_TOM}[typ]
        return _TOM if tom in marks else _CYMBAL
    cymbal = {_E.YELLOW_DRUM: _E.YELLOW_CYMBAL, _E.BLUE_DRUM: _E.BLUE_CYMBAL, _E.GREEN_DRUM: _E.GREEN_CYMBAL}[typ]
    return _CYMBAL if cymbal in marks else _TOM


def _snap_chords(groups: list[_Group], threshold: float, drums: bool) -> list[_Group]:
    """song.ini chord_snap_threshold: a group fewer than `threshold` ticks after the last kept one joins it and takes
    its flags (per pad on drums)."""
    if threshold <= 0 or not groups:
        return groups
    out = [groups[0]]
    for g in groups[1:]:
        last = out[-1]
        if g.notes[0].tick - last.notes[0].tick >= threshold:
            out.append(g)
            continue
        for n in g.notes:
            if drums:
                prev = next((m for m in last.notes if m.lane == n.lane), None)
                n.flags = n.flags if prev is None else prev.flags
            else:
                n.flags = last.notes[0].flags
        for n in g.notes:
            n.tick = last.notes[0].tick
            last.notes.append(n)
    return out


def _fix_note_overlaps(groups: list[_Group]) -> None:
    """One note per lane per tick (the longest, then the one with the most flags), and a sustain that runs into the
    next note on its lane ends there, that note carrying the rest."""
    for g in groups:
        g.notes.sort(key=lambda n: (n.lane, -n.length, -n.flags))
        seen: set[int] = set()
        g.notes[:] = [n for n in g.notes if not (n.lane in seen or seen.add(n.lane))]
    prev: dict[int, _Note] = {}
    for g in groups:
        for n in g.notes:
            p = prev.get(n.lane)
            prev[n.lane] = n
            if p is not None and p.tick + p.length > n.tick:
                n.length = max(n.length, p.length - (n.tick - p.tick))
                p.length = n.tick - p.tick


def _fix_span_overlaps(spans: list[_Ev]) -> list[_Ev]:
    """One phrase per tick (the longest); a phrase that runs into the next ends there, the next carrying the rest."""
    out: list[_Ev] = []
    for e in sorted(spans, key=lambda e: (e.tick, -e.length)):
        if not out or out[-1].tick != e.tick:
            out.append(e)
    for p, e in zip(out, out[1:]):
        if p.tick + p.length > e.tick:
            e.length = max(e.length, p.length - (e.tick - p.tick))
            p.length = e.tick - p.tick
    return out


def _build(raw: _Raw, fmt: str, mods: ChartModifiers, time_offset: float, source: str) -> TimedSong:
    res = raw.resolution
    clock = _Clock(res, raw.tempos)
    offset = time_offset + (mods.delay_ms / 1000 if mods.delay_ms else raw.offset)

    def sec(tick: float) -> float:
        return clock.ms(tick) / 1000 + offset

    drum_events = [e for t in raw.tracks if t.instrument == "drums" for e in t.events]
    drum_type = (_PRO if mods.pro_drums else _FIVE_LANE if mods.five_lane_drums
                 else _PRO if any(e.type in _MARKERS for e in drum_events)
                 else _FIVE_LANE if any(e.type == _E.FIVE_GREEN_DRUM for e in drum_events) else _FOUR_LANE)
    cut = (mods.sustain_cutoff_threshold if mods.sustain_cutoff_threshold != -1
           else res // 3 + 1 if fmt == "mid" else 0)
    parts: dict[tuple[str, str], TimedPart] = {}
    last = max([t for t, _ in raw.tempos] + [t for t, _ in raw.sections])
    for t in raw.tracks:
        drums = t.instrument == "drums"
        if cut > 0:
            for e in t.events:
                if e.length <= cut:
                    e.length = 0
        groups = _by_tick(t.events)
        groups = _resolve_drums(groups, drum_type, fmt) if drums else _resolve_frets(groups, mods, res, fmt)
        groups = _snap_chords(groups, mods.chord_snap_threshold, drums)
        _fix_note_overlaps(groups)
        if not groups:
            continue
        if drums:
            notes = sorted((TimedHit(sec(n.tick), n.lane, bool(n.flags & _CYMBAL), bool(n.flags & _DOUBLE_KICK),
                                     bool(n.flags & _ACCENT), bool(n.flags & _GHOST))
                            for g in groups for n in g.notes), key=lambda h: (h.time, h.pad))
        else:
            notes = []
            for g in groups:
                kept = [n for n in g.notes if n.lane != OPEN] or g.notes  # an open with frets is dropped
                tick, length, flags = g.notes[0].tick, max(n.length for n in kept), g.notes[0].flags
                notes.append(TimedNote(sec(tick), tuple(sorted(n.lane for n in kept)),
                                       sec(tick + length) if length > 0 else None,
                                       g.hopo if flags & _TAP else bool(flags & _HOPO), bool(flags & _TAP),
                                       g.forced))
        spans = {"sp": _fix_span_overlaps(t.star_power), "solo": _fix_span_overlaps(t.solos),
                 "fill": sorted(t.fills, key=lambda e: e.tick) if drums else []}  # fills as charted (scan-chart)
        last = max([last] + [n.tick + n.length for g in groups for n in g.notes]
                   + [e.tick + e.length for v in spans.values() for e in v])
        parts[(t.instrument, t.difficulty)] = TimedPart(
            t.instrument, t.difficulty, notes,
            *([TimedSpan(sec(e.tick), sec(e.tick + e.length)) for e in spans[k]] for k in ("sp", "solo", "fill")))
    order = sorted(parts, key=lambda k: (INSTRUMENTS.index(k[0]), DIFFICULTIES.index(k[1])))
    beats = math.ceil(last / res)
    return TimedSong(source, {k: parts[k] for k in order},
                     [(sec(tick), name) for tick, name in sorted(raw.sections, key=lambda s: s[0])],
                     [sec(k * res) for k in range(beats + 1)],
                     [sec(float(m)) for m in _measure_ticks(raw.signatures, res, beats * res)])
