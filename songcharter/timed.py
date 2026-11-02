"""Notes in seconds, before they are placed on a tempo map.

Every source of notes (an importer reading another tool's chart, a transcription model) produces these, in seconds of
the input audio: the single gapless decode that the whole pipeline measures against. Only the quantizer turns them
into ticks of the song's own TempoMap. Keeping the two apart means no note is ever timed by another tool's tempo map.
"""
from __future__ import annotations

from dataclasses import dataclass, field

INSTRUMENTS = ("guitar", "bass", "drums")
DIFFICULTIES = ("expert", "hard", "medium", "easy")
OPEN = 7  # same value as chart.OPEN


@dataclass(frozen=True)
class TimedNote:
    """One onset of a 5-fret part: a single note or a chord."""
    time: float                    # onset, seconds of input audio
    frets: tuple[int, ...]         # lanes 0-4 (green..orange), or (OPEN,)
    end: float | None = None       # sustain end in seconds; None means no sustain
    hopo: bool | None = None       # how the source plays it (natural rules plus forcing): True = HOPO, False = strum;
                                   # None = unknown, so the natural rules on our grid decide
    tap: bool = False


@dataclass(frozen=True)
class TimedHit:
    """One drum hit on one pad. A two-pad hit is two TimedHits at the same time."""
    time: float
    pad: int                       # 0 kick, 1 red, 2 yellow, 3 blue, 4 green
    cymbal: bool = False           # pads 2-4 only
    double_kick: bool = False      # pad 0 only (Expert+)
    accent: bool = False
    ghost: bool = False


@dataclass(frozen=True)
class TimedSpan:
    start: float
    end: float


@dataclass
class TimedPart:
    instrument: str                # one of INSTRUMENTS
    difficulty: str                # one of DIFFICULTIES
    notes: list                    # TimedNote for guitar/bass, TimedHit for drums; sorted by time
    star_power: list[TimedSpan] = field(default_factory=list)
    solos: list[TimedSpan] = field(default_factory=list)
    activation: list[TimedSpan] = field(default_factory=list)   # drum fills


@dataclass
class TimedSong:
    """What an importer returns: every part it found, the source's sections and its own beat times."""
    source: str                                        # e.g. "autochart:/path/notes.chart"
    parts: dict[tuple[str, str], TimedPart] = field(default_factory=dict)   # key: (instrument, difficulty)
    sections: list[tuple[float, str]] = field(default_factory=list)          # (seconds, name)
    beats: list[float] = field(default_factory=list)   # the source tempo map's beat times, for diagnostics only

    def shifted(self, seconds: float) -> "TimedSong":
        """The same song with every time moved by `seconds` (e.g. +0.0697 for a tool that trimmed the audio)."""
        def mv(x):
            return None if x is None else x + seconds

        def note(n):
            if isinstance(n, TimedHit):
                return TimedHit(n.time + seconds, n.pad, n.cymbal, n.double_kick, n.accent, n.ghost)
            return TimedNote(n.time + seconds, n.frets, mv(n.end), n.hopo, n.tap)

        def spans(s):
            return [TimedSpan(x.start + seconds, x.end + seconds) for x in s]

        parts = {k: TimedPart(p.instrument, p.difficulty, [note(n) for n in p.notes], spans(p.star_power),
                              spans(p.solos), spans(p.activation)) for k, p in self.parts.items()}
        return TimedSong(self.source, parts, [(t + seconds, n) for t, n in self.sections],
                         [b + seconds for b in self.beats])
