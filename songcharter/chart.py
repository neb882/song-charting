"""The chart model and the .chart writer.

The writer emits the text format exactly as Moonscraper Chart Editor writes it, since that is what
Clone Hero, YARG, Moonscraper and scan-chart all read:

  * sections in the order [Song], [SyncTrack], [Events], then the instrument tracks,
  * two-space indent, `KEY = VALUE` with exactly one space each side of `=`, single spaces between fields,
  * every section sorted by tick, a length on every `N` and `S` line, quoted global events.

Lyrics and vocals are not part of this model: the tool charts instruments only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .tempo import TempoMap

# 5-fret lanes
GREEN, RED, YELLOW, BLUE, ORANGE = 0, 1, 2, 3, 4
OPEN = 7
_FLIP, _TAP = 5, 6  # modifiers: flip natural HOPO/strum, tap

# drum pads (4-lane / pro)
KICK, SNARE, HIHAT_TOM_Y, RIDE_TOM_B, CRASH_TOM_G = 0, 1, 2, 3, 4  # aliases for readability
_DOUBLE_KICK = 32

# phrases
STAR_POWER = 2
DRUM_ACTIVATION = 64
ROLL = 65
DOUBLE_ROLL = 66

DIFFICULTIES = ("Expert", "Hard", "Medium", "Easy")
INSTRUMENTS = ("Single", "DoubleGuitar", "DoubleBass", "DoubleRhythm", "Drums", "Keyboard")


@dataclass(frozen=True)
class FretNote:
    """A 5-fret note or chord. frets: lanes 0-4, or (OPEN,) for an open note."""
    tick: int
    frets: tuple[int, ...]
    length: int = 0
    flip: bool = False  # flip the natural HOPO/strum state
    tap: bool = False

    def lines(self) -> list[tuple[int, str]]:
        if not self.frets:
            raise ValueError(f"empty note at tick {self.tick}")
        frets = sorted(set(self.frets))
        if OPEN in frets and len(frets) > 1:
            raise ValueError(f"open note combined with frets at tick {self.tick}")
        if any(f not in (0, 1, 2, 3, 4, OPEN) for f in frets):
            raise ValueError(f"bad fret in {frets} at tick {self.tick}")
        if len(frets) > 4:
            raise ValueError(f"5-note chord at tick {self.tick} (invalid in Clone Hero)")
        out = [(self.tick, f"N {f} {self.length}") for f in frets]
        if self.flip:
            out.append((self.tick, f"N {_FLIP} 0"))
        if self.tap:
            out.append((self.tick, f"N {_TAP} 0"))
        return out


@dataclass(frozen=True)
class DrumHit:
    """One pad hit. pad: 0 kick, 1 red, 2 yellow, 3 blue, 4 green (4-lane)."""
    tick: int
    pad: int
    cymbal: bool = False       # yellow, blue, green only (pro drums)
    double_kick: bool = False  # Expert+ kick (pad 0 only)
    accent: bool = False
    ghost: bool = False

    def lines(self) -> list[tuple[int, str]]:
        if self.pad not in (0, 1, 2, 3, 4):
            raise ValueError(f"bad drum pad {self.pad} at tick {self.tick}")
        if self.cymbal and self.pad not in (2, 3, 4):
            raise ValueError(f"only yellow, blue and green can be cymbals (tick {self.tick})")
        if self.double_kick:
            if self.pad != 0:
                raise ValueError("double kick must be on the kick")
            return [(self.tick, f"N {_DOUBLE_KICK} 0")]
        out = [(self.tick, f"N {self.pad} 0")]
        if self.cymbal:
            out.append((self.tick, f"N {64 + self.pad} 0"))
        if self.pad and self.accent:
            out.append((self.tick, f"N {33 + self.pad} 0"))
        elif self.pad and self.ghost:
            out.append((self.tick, f"N {39 + self.pad} 0"))
        return out


@dataclass(frozen=True)
class Phrase:
    tick: int
    length: int
    kind: int = STAR_POWER


@dataclass
class Track:
    difficulty: str  # Expert, Hard, Medium, Easy
    instrument: str  # Single, DoubleBass, DoubleRhythm, Drums, ...
    notes: list = field(default_factory=list)          # FretNote or DrumHit
    phrases: list[Phrase] = field(default_factory=list)
    solos: list[tuple[int, int]] = field(default_factory=list)  # (start tick, end tick), end inclusive

    def __post_init__(self) -> None:
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"unknown difficulty {self.difficulty}")
        if self.instrument not in INSTRUMENTS:
            raise ValueError(f"unknown instrument {self.instrument}")

    @property
    def name(self) -> str:
        return f"{self.difficulty}{self.instrument}"

    @property
    def is_drums(self) -> bool:
        return self.instrument == "Drums"

    def lines(self) -> list[tuple[int, str]]:
        rows: list[tuple[int, int, str]] = []
        for n in self.notes:
            if self.is_drums != isinstance(n, DrumHit):
                raise ValueError(f"{type(n).__name__} in track {self.name}")
            rows.extend((t, 0, s) for t, s in n.lines())
        rows.extend((p.tick, 1, f"S {p.kind} {p.length}") for p in self.phrases)
        for a, b in self.solos:
            rows.append((a, 2, "E solo"))
            rows.append((b, 3, "E soloend"))
        # sort by tick; within a tick: notes (by code), phrases, solo markers
        rows = sorted(set(rows), key=lambda r: (r[0], r[1], _code(r[2])))
        return [(t, s) for t, _, s in rows]


def _code(text: str) -> int:
    parts = text.split()
    return int(parts[1]) if parts[0] in ("N", "S") else 0


@dataclass
class SongInfo:
    name: str
    artist: str
    album: str = ""
    genre: str = ""
    year: str = ""
    charter: str = ""
    album_track: int | None = None
    preview_start_ms: int | None = None
    loading_phrase: str = ""
    music_stream: str = "song.ogg"


@dataclass
class Chart:
    info: SongInfo
    tempo: TempoMap
    sections: list[tuple[int, str]] = field(default_factory=list)  # (tick, name), practice sections
    tracks: list[Track] = field(default_factory=list)

    @property
    def resolution(self) -> int:
        return self.tempo.resolution

    def track(self, difficulty: str, instrument: str) -> Track | None:
        return next((t for t in self.tracks if t.difficulty == difficulty and t.instrument == instrument), None)

    def instruments(self) -> list[str]:
        return sorted({t.instrument for t in self.tracks if t.notes})

    def last_tick(self) -> int:
        ends = [0]
        for t in self.tracks:
            for n in t.notes:
                ends.append(n.tick + getattr(n, "length", 0))
        return max(ends)


def _text(s: str) -> str:
    """A value safe inside a quoted .chart string: no double quotes (Moonscraper uses backticks), no newlines."""
    return " ".join(str(s).replace('"', "`").split())


def write_chart(chart: Chart) -> str:
    info = chart.info
    song = [
        f'Name = "{_text(info.name)}"',
        f'Artist = "{_text(info.artist)}"',
        f'Charter = "{_text(info.charter)}"',
        f'Album = "{_text(info.album)}"',
    ]
    if info.year:
        song.append(f'Year = ", {_text(info.year)}"')
    song += [
        "Offset = 0",
        f"Resolution = {chart.resolution}",
        "Player2 = bass",
        "Difficulty = 0",
        "PreviewStart = 0",
        "PreviewEnd = 0",
        f'Genre = "{_text(info.genre)}"',
        'MediaType = "cd"',
        f'MusicStream = "{_text(info.music_stream)}"',
    ]
    out = ["[Song]", "{"] + [f"  {s}" for s in song] + ["}"]
    out += ["[SyncTrack]", "{"] + [f"  {t} = {s}" for t, s in chart.tempo.sync_track_lines()] + ["}"]
    events = sorted((t, f'E "section {_text(name)}"') for t, name in chart.sections)
    out += ["[Events]", "{"] + [f"  {t} = {s}" for t, s in events] + ["}"]
    order = {(d, i): (INSTRUMENTS.index(i), DIFFICULTIES.index(d)) for d in DIFFICULTIES for i in INSTRUMENTS}
    names = set()
    for tr in sorted(chart.tracks, key=lambda t: order[(t.difficulty, t.instrument)]):
        if tr.name in names:
            raise ValueError(f"track {tr.name} appears twice")
        names.add(tr.name)
        if not tr.notes:
            continue
        out += [f"[{tr.name}]", "{"] + [f"  {t} = {s}" for t, s in tr.lines()] + ["}"]
    return "\r\n".join(out) + "\r\n"
