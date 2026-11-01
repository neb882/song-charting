import pytest

from songcharter.chart import (OPEN, STAR_POWER, Chart, DrumHit, FretNote, Phrase, SongInfo, Track,
                               write_chart)
from songcharter.ini import write_ini
from songcharter.tempo import Tempo, TempoMap


def small_chart():
    tm = TempoMap(192, [Tempo(0, 120000)])
    expert = Track("Expert", "Single", [
        FretNote(768, (0,)), FretNote(864, (2,)), FretNote(928, (3,), flip=True),
        FretNote(1152, (0, 2)), FretNote(1344, (1,), length=144), FretNote(1536, (OPEN,)),
        FretNote(1632, (4,), tap=True),
    ], [Phrase(768, 384, STAR_POWER)], [(1536, 1632)])
    drums = Track("Expert", "Drums", [
        DrumHit(768, 0), DrumHit(768, 2, cymbal=True), DrumHit(864, 1, accent=True),
        DrumHit(960, 0, double_kick=True), DrumHit(1056, 4, cymbal=True), DrumHit(1152, 1, ghost=True),
    ])
    info = SongInfo("Test Song", 'An "Artist"', album="Album", genre="Rock", year="2014", charter="songcharter")
    return Chart(info, tm, [(768, "Intro"), (1536, "Verse 1")], [drums, expert])


def test_format_details():
    text = write_chart(small_chart())
    lines = text.split("\r\n")
    assert lines[0] == "[Song]" and lines[1] == "{"
    assert '  Artist = "An `Artist`"' in lines            # no double quotes inside strings
    assert '  Year = ", 2014"' in lines
    assert "  Resolution = 192" in lines and "  Offset = 0" in lines
    assert '  MusicStream = "song.ogg"' in lines
    heads = [l for l in lines if l.startswith("[")]
    assert heads == ["[Song]", "[SyncTrack]", "[Events]", "[ExpertSingle]", "[ExpertDrums]"]
    assert '  768 = E "section Intro"' in lines
    for l in lines:
        if l.startswith("  ") and " = " in l and not l.startswith("  Name"):
            assert "  " not in l.strip()  # single spaces between fields


def test_note_encodings():
    text = write_chart(small_chart())
    for want in ["928 = N 3 0", "928 = N 5 0", "1632 = N 4 0", "1632 = N 6 0", "1536 = N 7 0",
                 "1344 = N 1 144", "768 = S 2 384", "1536 = E solo", "1632 = E soloend",
                 "768 = N 66 0", "864 = N 34 0", "960 = N 32 0", "1056 = N 68 0", "1152 = N 40 0"]:
        assert f"  {want}" in text, want


def test_ticks_sorted_in_every_section():
    text = write_chart(small_chart())
    for block in text.split("[")[2:]:
        ticks = [int(l.split(" = ")[0]) for l in block.split("\r\n") if l.startswith("  ") and l.strip()[0].isdigit()]
        assert ticks == sorted(ticks)


def test_invalid_notes_are_rejected():
    with pytest.raises(ValueError):
        FretNote(0, (OPEN, 1)).lines()
    with pytest.raises(ValueError):
        FretNote(0, (0, 1, 2, 3, 4)).lines()
    with pytest.raises(ValueError):
        DrumHit(0, 1, cymbal=True).lines()


def test_ini():
    ini = write_ini(small_chart(), {"Single": 4, "Drums": 3})
    lines = ini.split("\r\n")
    assert lines[0] == "[song]"
    assert "artist = An \"Artist\"" in lines
    assert "diff_guitar = 4" in lines and "diff_drums = 3" in lines
    assert "diff_drums_real = 3" in lines and "pro_drums = True" in lines
    assert not any(l.startswith(("delay", "song_length", "hopo_frequency")) for l in lines)
