"""A guitar take the engine cut short, stitched from its whole-song run and the pieces that continued it (DESIGN.md
2.7, M5-02). Pure functions: engines/autochart.py runs the engine and decides where each piece starts; this module
only joins charts.

  * **The base** is the whole-song run's chart. Its [SyncTrack] covers the whole audio (the engine's timing stage
    ran on the whole song; only the decode stopped), so it is the stitched take's tempo map, and its [Song] and
    section names stay too. Its Expert notes before the first piece's `keep_from_s` (B) are kept exactly as the
    engine wrote them (ticks, lengths, flips, taps), read raw as the importer reads a .chart; a sustain crossing B
    ends GAP before B.
  * **A piece** is one more engine run on the decode from `start_s` (B minus the context) to the end. Its notes are
    read with importers.read_song (seconds of the piece's audio, the HOPO and tap state Clone Hero gives each), moved
    by `start_s` onto the decode and kept from its B (a note at B is the piece's, never the base's too) up to the
    next piece's B, where its sustains end GAP before as the base's do. A piece with no note to keep moves no seam:
    what came before it keeps its notes.
  * **Ticks:** a kept note's onset and sustain end go through the base's TempoMap (`sec_to_tick`, rounded to the
    nearest tick). The piece's own map differs (its engine timed its own audio), so its HOPO intent is kept by a
    flip wherever the natural state on the base's map differs (as quantize._frets writes them); taps are kept. A
    note that would land on or before the previous note's tick is dropped.
  * **Phrases:** the pieces' star power, solos and fills are dropped (assemble drops every source's phrases anyway);
    the base's that start before B stay, ending before B.

The same inputs give a byte-identical chart.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..chart import OPEN, STAR_POWER, Chart, FretNote, Phrase, SongInfo, Track
from ..importers import _E, _FRETS, _RE_META, _chart_sections, _decode, _parse_chart, read_song
from ..quantize import HOPO_THRESHOLD, _natural
from ..tempo import Tempo, TempoMap, TimeSignature
from ..timed import TimedNote

GAP = 0.060     # s: a sustain crossing a seam ends this long before it
SAME = 1e-6     # s: times this close count as the same (a note at B is the piece's)


@dataclass(frozen=True)
class Piece:
    start_s: float                 # where the piece's audio starts in the decode
    keep_from_s: float             # B: from here on the piece's notes replace what came before
    notes: Sequence[TimedNote]     # its Expert guitar notes, in seconds of its own audio


def read_piece(chart: Path | str, start_s: float, keep_from_s: float) -> Piece:
    """A piece's song folder chart (its notes.chart), read with read_song."""
    part = read_song(chart).parts.get(("guitar", "expert"))
    return Piece(start_s, keep_from_s, tuple(part.notes) if part else ())


def tempo_map(raw) -> TempoMap:
    """A raw chart's (importers._parse_chart's) tempo map, written back without anchors as the engine writes it."""
    tempos = [Tempo(tick, round(bpm * 1000)) for tick, bpm in raw.tempos]
    signatures = [TimeSignature(t, n, d) for t, n, d in raw.signatures] or [TimeSignature(0, 4)]
    if signatures[0].tick != 0:
        signatures.insert(0, TimeSignature(0, 4))
    return TempoMap(raw.resolution, tempos, signatures, anchors=False)


def _song_info(text: str) -> SongInfo:
    meta = dict(m.groups() for m in map(_RE_META.fullmatch, _chart_sections(text).get("Song", [])) if m)
    return SongInfo(meta.get("Name", ""), meta.get("Artist", ""), album=meta.get("Album", ""),
                    genre=meta.get("Genre", ""), charter=meta.get("Charter", ""),
                    music_stream=meta.get("MusicStream") or "song.ogg")


def _raw_notes(track) -> list[FretNote]:
    """A raw Expert guitar track's notes as the engine wrote them: one per tick, its frets, the longest length of
    them, its flip (N 5) and tap (N 6); an open charted with frets is dropped from the chord (as read_song)."""
    by_tick: dict[int, list] = {}
    for e in track.events:
        by_tick.setdefault(e.tick, []).append(e)
    out = []
    for tick in sorted(by_tick):
        evs = by_tick[tick]
        frets = [e for e in evs if e.type in _FRETS]
        if not frets:
            continue
        lanes = sorted({_FRETS[e.type] for e in frets})
        if len(lanes) > 1 and OPEN in lanes:
            lanes.remove(OPEN)
        kinds = {e.type for e in evs}
        out.append(FretNote(tick, tuple(lanes), max(e.length for e in frets), _E.FORCE_UNNATURAL in kinds,
                            _E.FORCE_TAP in kinds))
    return out


def _clip(tm: TempoMap, tick: int, length: int, seam: float) -> int:
    """A sustain's length, ending GAP before `seam` when it runs past it."""
    if length and tm.tick_to_sec(tick + length) > seam:
        return max(0, round(tm.sec_to_tick(seam - GAP)) - tick)
    return length


def stitch(base_text: str, pieces: Sequence[Piece]) -> Chart:
    """The stitched take: the base chart's (its text) notes before the first piece's B, then each piece's notes from
    its B to the next one's, on the base's tempo map (the module docstring)."""
    raw = _parse_chart(base_text)
    if raw.offset:
        raise ValueError(f"the base chart has an offset ({raw.offset} s): the engine writes none")
    tm = tempo_map(raw)
    track = next((t for t in raw.tracks if (t.instrument, t.difficulty) == ("guitar", "expert")), None)
    base = _raw_notes(track) if track else []
    kept = []   # the pieces that move a seam: (piece, its notes on the decode from its B)
    for p in pieces:
        own = [n for n in p.notes if n.time + p.start_s >= p.keep_from_s - SAME]
        if own:
            kept.append((p, own))
    seams = [p.keep_from_s for p, _ in kept] + [math.inf]

    first = seams[0]
    notes = [FretNote(n.tick, n.frets, _clip(tm, n.tick, n.length, first), n.flip, n.tap)
             for n in base if tm.tick_to_sec(n.tick) < first - SAME]
    threshold = math.floor(HOPO_THRESHOLD * tm.resolution)
    for (p, own), seam in zip(kept, seams[1:]):
        for n in own:
            at = n.time + p.start_s
            if at >= seam - SAME:
                break
            tick = round(tm.sec_to_tick(at))
            prev = notes[-1] if notes else None
            if prev is not None and tick <= prev.tick:
                continue
            length = 0
            if n.end is not None:
                length = _clip(tm, tick, max(0, round(tm.sec_to_tick(n.end + p.start_s)) - tick), seam)
            natural = _natural(prev and tuple(sorted(set(prev.frets))), tick - prev.tick if prev else 0, n.frets,
                               threshold)
            flip = not n.tap and n.hopo is not None and n.hopo != natural
            notes.append(FretNote(tick, n.frets, length, flip, n.tap))

    phrases, solos = [], []
    if track is not None:
        cut = math.ceil(tm.sec_to_tick(first - SAME)) - 1 if first != math.inf else None   # the last tick before B
        for e in track.star_power:
            if cut is None or e.tick <= cut:
                phrases.append(Phrase(e.tick, e.length if cut is None else min(e.length, cut + 1 - e.tick),
                                      STAR_POWER))
        for e in track.solos:   # its length holds the soloend tick: one past the end
            if cut is None or e.tick <= cut:
                end = e.tick + e.length - 1
                solos.append((e.tick, end if cut is None else min(end, cut)))
    out = Track("Expert", "Single", notes, phrases, solos)
    return Chart(_song_info(base_text), tm, sorted(raw.sections), [out])


def stitch_files(base: Path | str, pieces: Sequence[tuple[Path | str, float, float]]) -> Chart:
    """The stitched take from the base's notes.chart and each piece's (chart, start_s, keep_from_s); chart.py's
    write_chart writes it."""
    return stitch(_decode(Path(base).read_bytes()), [read_piece(c, s, k) for c, s, k in pieces])


def last_note_s(chart: Chart) -> float | None:
    """The time of the last Expert guitar onset of a chart (on its own map), None without one."""
    track = chart.track("Expert", "Single")
    return chart.tempo.tick_to_sec(max(n.tick for n in track.notes)) if track and track.notes else None
