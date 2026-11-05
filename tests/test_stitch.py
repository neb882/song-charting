"""Stitching a take the engine cut short (songcharter.engines.stitch): a base chart and piece charts made here with
chart.py's writer on known tempo maps, read back with importers.read_song."""
import pytest

from songcharter.chart import STAR_POWER, Chart, FretNote, Phrase, SongInfo, Track, write_chart
from songcharter.engines import stitch as ST
from songcharter.importers import read_chart
from songcharter.tempo import Tempo, TempoMap

BASE_TM = TempoMap(192, [Tempo(0, 120000), Tempo(9600, 100000)], anchors=False)   # 120 BPM, 100 BPM from 25 s
PIECE_TM = TempoMap(480, [Tempo(0, 150000)])    # the piece's own map: 150 BPM, 1200 ticks a second
B, START = 12.0, 4.0                            # the piece keeps from B; its audio starts at B - 8 s


def base_tick(t: float) -> int:
    return round(BASE_TM.sec_to_tick(t))


def piece_tick(t: float) -> int:
    """A note at decode time t in the piece's chart: its audio starts at START."""
    return round((t - START) * 1200)


def write(path, tm, notes, phrases=(), solos=()):
    track = Track("Expert", "Single", list(notes), list(phrases), list(solos))
    chart = Chart(SongInfo("A Song", "A Band", charter="Autochart"), tm, [(0, "Intro"), (3840, "Verse")], [track])
    path.write_text(write_chart(chart), encoding="utf-8", newline="")
    return path


def base_chart(tmp_path, notes_out=None):
    """A note every 0.25 s from 1 s to 25 s, lanes cycling G R Y B; at 11 s a 2-s sustain over B; a flip on the
    note at 2 s; star power and a solo before B and across it. `notes_out` (a list) gets its notes."""
    notes = []
    for k in range(97):
        t = 1 + 0.25 * k
        if 11.0 < t < 13.0:
            continue
        notes.append(FretNote(base_tick(t), ((0, 1, 2, 3)[k % 4],), base_tick(13.0) - base_tick(11.0) if t == 11 else 0,
                              flip=t == 2.0))
    notes.append(FretNote(base_tick(12.0), (4,)))   # a note exactly at B: the piece's is kept instead
    notes.sort(key=lambda n: n.tick)
    if notes_out is not None:
        notes_out.extend(notes)
    return write(tmp_path / "base.chart", BASE_TM, notes,
                 [Phrase(base_tick(2.0), base_tick(4.0) - base_tick(2.0)),
                  Phrase(base_tick(10.0), base_tick(14.0) - base_tick(10.0))],
                 [(base_tick(5.0), base_tick(6.0)), (base_tick(10.0), base_tick(15.0))])


def piece_chart(tmp_path, name="piece.chart"):
    """Notes from 5 s (in the 8-s context) to 30 s on the piece's own map: open notes every 0.5 s, then at 20 s
    two single notes 0.15 s apart (strum on its map, natural HOPO on the base's), at 21 s a forced HOPO 0.2 s
    after the last (natural strum on both maps), at 22 s a tap, at 23 s a 1-s sustain; and its own star power and
    solo, which are dropped."""
    notes = [FretNote(piece_tick(5.0 + 0.5 * k), (7,)) for k in range(30)]   # 5.0 .. 19.5 s
    notes += [FretNote(piece_tick(20.0), (1,)), FretNote(piece_tick(20.15), (2,)),
              FretNote(piece_tick(20.8), (0,)), FretNote(piece_tick(21.0), (3,), flip=True),
              FretNote(piece_tick(22.0), (2,), tap=True), FretNote(piece_tick(23.0), (0, 1), piece_tick(24.0) - piece_tick(23.0)),
              FretNote(piece_tick(30.0), (4,))]
    return write(tmp_path / name, PIECE_TM, notes, [Phrase(piece_tick(13.0), 1200)],
                 [(piece_tick(14.0), piece_tick(16.0))])


def notes_of(text, tmp_path):
    path = tmp_path / "stitched.chart"
    path.write_text(text, encoding="utf-8", newline="")
    return read_chart(path).parts[("guitar", "expert")]


def test_notes_before_b_come_from_the_base_and_after_it_from_the_piece(tmp_path):
    base, piece = base_chart(tmp_path), piece_chart(tmp_path)
    chart = ST.stitch_files(base, [(piece, START, B)])
    text = write_chart(chart)
    assert chart.tempo.sync_track_lines() == BASE_TM.sync_track_lines()   # the base's map, as written
    assert chart.sections == [(0, "Intro"), (3840, "Verse")]
    track = chart.track("Expert", "Single")
    base_notes = read_chart(base).parts[("guitar", "expert")].notes
    stitched = notes_of(text, tmp_path).notes
    before = [n for n in stitched if n.time < B]
    assert [(n.time, n.frets) for n in before] == [(n.time, n.frets) for n in base_notes if n.time < B]
    after = [n for n in stitched if n.time >= B]
    want = [12.0 + 0.5 * k for k in range(15)]     # the piece's open notes from B on (none of the base's)
    assert [round(n.time, 6) for n in after[:15]] == want and all(n.frets == (7,) for n in after[:15])
    # a piece note exactly at B is kept once (the base's own note there is dropped)
    assert [n for n in track.notes if n.tick == base_tick(12.0)] == [FretNote(base_tick(12.0), (7,))]
    # ticks on the base's map, rounded: 20.15 s is tick 7737.6 at 120 BPM (piece tick 19380 at 150 BPM)
    assert next(n for n in track.notes if n.frets == (2,) and n.tick > base_tick(20)).tick == 7738
    # the 100-BPM part of the base's map: 30 s is tick 9600 + 5 s at 320 ticks a second
    assert track.notes[-1] == FretNote(9600 + 1600, (4,))
    # a base sustain crossing B ends GAP (60 ms) before it
    sus = next(n for n in track.notes if n.tick == base_tick(11.0))
    assert sus.length == base_tick(B - ST.GAP) - base_tick(11.0) == 361
    # a sustain of the piece converted the same way
    assert next(n for n in track.notes if n.frets == (0, 1)).length == base_tick(24.0) - base_tick(23.0)
    assert ST.last_note_s(chart) == pytest.approx(30.0)


def test_the_pieces_hopo_intent_and_taps_are_kept_on_the_base_map(tmp_path):
    """The piece's states as read on its own map (strum, forced HOPO, tap) are the stitched chart's on the base's:
    a flip where the natural state on the base's map differs, none where it agrees."""
    base, piece = base_chart(tmp_path), piece_chart(tmp_path)
    chart = ST.stitch_files(base, [(piece, START, B)])
    track = chart.track("Expert", "Single")
    own = {round(n.time + START, 2): n for n in read_chart(piece).parts[("guitar", "expert")].notes}
    stitched = {round(n.time, 2): n for n in notes_of(write_chart(chart), tmp_path).notes}
    for t in (20.0, 20.15, 20.8, 21.0, 22.0, 23.0):
        assert (stitched[t].hopo, stitched[t].tap) == (own[t].hopo, own[t].tap), t
    assert (own[20.15].hopo, own[21.0].hopo, own[22.0].tap) == (False, True, True)
    flips = {round(BASE_TM.tick_to_sec(n.tick), 2): n.flip for n in track.notes if n.tick >= base_tick(20.0)}
    # 20.15 s: natural HOPO on the base's map (58 ticks <= 65) but a strum on the piece's (180 > 162): flipped;
    # 21.0 s: forced HOPO on the piece's, a natural strum on the base's (77 ticks): flipped; the tap needs no flip
    assert flips == {20.0: False, 20.15: True, 20.8: False, 21.0: True, 22.0: False, 23.0: False, 30.0: False}
    assert next(n for n in track.notes if n.tick == base_tick(22.0)).tap
    # the base's own flip before B is kept as written
    assert next(n for n in track.notes if n.tick == base_tick(2.0)).flip


def test_the_pieces_phrases_are_dropped_and_the_bases_end_before_b(tmp_path):
    base, piece = base_chart(tmp_path), piece_chart(tmp_path)
    track = ST.stitch_files(base, [(piece, START, B)]).track("Expert", "Single")
    last = base_tick(B) - 1
    assert track.phrases == [Phrase(base_tick(2.0), base_tick(4.0) - base_tick(2.0), STAR_POWER),
                             Phrase(base_tick(10.0), last + 1 - base_tick(10.0), STAR_POWER)]
    assert track.solos == [(base_tick(5.0), base_tick(6.0)), (base_tick(10.0), last)]


def test_two_pieces_and_a_piece_with_nothing_to_keep(tmp_path):
    """Each piece's notes run from its B to the next one's, its sustains ending GAP before the next seam; a piece
    with no note from its B on moves no seam."""
    base, first = base_chart(tmp_path), piece_chart(tmp_path)
    second = write(tmp_path / "second.chart", PIECE_TM, [FretNote(round((t - 14.0) * 1200), (3,)) for t in
                                                         (15.0, 21.5, 22.5, 26.0)])
    empty = write(tmp_path / "empty.chart", PIECE_TM, [FretNote(round(1.0 * 1200), (1,))])   # 17 s, before its B
    chart = ST.stitch_files(base, [(first, START, B), (second, 14.0, 22.0), (empty, 16.0, 25.0)])
    stitched = [(round(BASE_TM.tick_to_sec(n.tick), 2), n.frets, n.length)
                for n in chart.track("Expert", "Single").notes if n.tick >= base_tick(19.5)]
    assert stitched == [(19.5, (7,), 0), (20.0, (1,), 0), (20.15, (2,), 0), (20.8, (0,), 0), (21.0, (3,), 0),
                        (22.5, (3,), 0), (26.0, (3,), 0)]
    # a sustain of the first piece crossing the second's B ends GAP before it
    long = write(tmp_path / "long.chart", PIECE_TM, [FretNote(piece_tick(20.0), (1,), piece_tick(25.0) - piece_tick(20.0))])
    track = ST.stitch_files(base, [(long, START, B), (second, 14.0, 22.0)]).track("Expert", "Single")
    assert next(n for n in track.notes if n.tick == base_tick(20.0)).length == base_tick(22.0 - ST.GAP) - base_tick(20.0)


def test_two_stitches_of_the_same_inputs_are_byte_identical(tmp_path):
    base, piece = base_chart(tmp_path), piece_chart(tmp_path)
    one = write_chart(ST.stitch_files(base, [(piece, START, B)]))
    two = write_chart(ST.stitch_files(base, [(piece, START, B)]))
    assert one == two and one.encode() == two.encode()
    # no piece: the base's notes as written (ticks, lengths, flips) and its phrases
    written = []
    alone = ST.stitch_files(base_chart(tmp_path, written), []).track("Expert", "Single")
    assert alone.notes == written and len(alone.phrases) == 2 and len(alone.solos) == 2
