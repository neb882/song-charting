"""Importers: small synthetic .chart and .mid files read back as TimedSong, with Clone Hero's rules as scan-chart
implements them (HOPO thresholds and forcing, sustain cut-off, cymbals and tom markers, phrase overlaps)."""
import pytest

from songcharter.chart import Chart, DrumHit, FretNote, Phrase, SongInfo, Track, write_chart
from songcharter.importers import ChartModifiers, read_chart, read_ini_modifiers, read_mid, read_song
from songcharter.tempo import Tempo, TempoMap
from songcharter.timed import OPEN

mido = pytest.importorskip("mido")


# ------------------------------------------------------------------------------------------------ helpers

def write_chart_file(path, tracks, res=192, sync=("0 = TS 4", "0 = B 120000"), events=(), song=()):
    """A .chart in Moonscraper's layout. tracks: {"ExpertSingle": ["0 = N 0 0", ...]}."""
    blocks = [("Song", [f"Resolution = {res}", *song]), ("SyncTrack", list(sync)), ("Events", list(events))]
    blocks += list(tracks.items())
    lines = []
    for name, rows in blocks:
        lines += [f"[{name}]", "{"] + [f"  {r}" for r in rows] + ["}"]
    path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return path


def note(tick, pitch, length, velocity=100, channel=0):
    return [(tick, mido.Message("note_on", note=pitch, velocity=velocity, channel=channel)),
            (tick + length, mido.Message("note_off", note=pitch, velocity=0, channel=channel))]


ALL = 0x7E  # stands in for 0xFF (every difficulty), which mido will not write; write_mid_file puts 0xFF back


def sysex(tick, difficulty, kind, on):
    """Phase Shift SysEx switch: kind 1 = open, 4 = tap; difficulty 0-3 (easy..expert) or ALL."""
    return [(tick, mido.Message("sysex", data=[0x50, 0x53, 0, 0, difficulty, kind, 1 if on else 0]))]


def text(tick, s):
    return [(tick, mido.MetaMessage("text", text=s))]


def write_mid_file(path, tracks, tpb=480, tempo=500000):
    """Format-1 MIDI: a tempo track, then one named track per entry of {name: [(abs tick, message), ...]}."""
    mf = mido.MidiFile(type=1, ticks_per_beat=tpb)
    mf.tracks.append(mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=tempo, time=0)]))
    for name, events in tracks.items():
        tr = mido.MidiTrack([mido.MetaMessage("track_name", name=name, time=0)])
        last = 0
        # note offs before note ons on the same tick, as editors write them
        for tick, msg in sorted(events, key=lambda e: (e[0], e[1].type != "note_off")):
            tr.append(msg.copy(time=tick - last))
            last = tick
        mf.tracks.append(tr)
    mf.save(path)
    path.write_bytes(path.read_bytes().replace(b"PS\x00\x00\x7e", b"PS\x00\x00\xff"))
    return path


def onsets(part):
    return [(n.time, n.frets, n.hopo, n.tap) for n in part.notes]


# ------------------------------------------------------------------------------------------------ .chart

def test_chart_times_offset_sections_and_beats(tmp_path):
    f = write_chart_file(tmp_path / "notes.chart", {"ExpertSingle": ["384 = N 0 0", "960 = N 1 0"]},
                         sync=("0 = TS 4", "0 = B 120000", "768 = A 2000000", "768 = B 60000"),
                         events=('0 = E "section Intro"', '768 = E "[prc_chorus]"', '800 = E "lyric la"'),
                         song=("Offset = 0.5",))
    s = read_chart(f, time_offset=0.25)
    part = s.parts[("guitar", "expert")]
    # 384 ticks at 120 BPM = 1 s; 960 = 2 s + 192 ticks at 60 BPM; then the chart's Offset and the caller's offset
    assert [n.time for n in part.notes] == pytest.approx([1.75, 3.75])
    assert s.sections == [(pytest.approx(0.75), "Intro"), (pytest.approx(2.75), "chorus")]
    assert s.beats == pytest.approx([0.75, 1.25, 1.75, 2.25, 2.75, 3.75])
    assert s.source == str(f)
    assert list(s.parts) == [("guitar", "expert")]


def test_chart_natural_hopos_forcing_and_taps(tmp_path):
    rows = ["0 = N 0 0",                    # first note: strum
            "65 = N 1 0",                   # 65 ticks, new fret: HOPO (threshold floor(65/192 x 192) = 65)
            "131 = N 2 0",                  # 66 ticks: strum
            "160 = N 2 0",                  # same fret again: strum
            "200 = N 0 0", "200 = N 1 0",   # chord: strum
            "240 = N 1 0",                  # a note of the previous chord: HOPO in .chart
            "300 = N 3 0", "300 = N 5 0",   # natural HOPO, flipped: strum
            "500 = N 4 0", "500 = N 5 0",   # natural strum, flipped: HOPO
            "520 = N 3 0", "520 = N 6 0",   # tap over a natural HOPO
            "800 = N 2 0", "800 = N 6 0"]   # tap over a strum
    part = read_chart(write_chart_file(tmp_path / "notes.chart", {"ExpertSingle": rows})).parts[("guitar", "expert")]
    assert [n.hopo for n in part.notes] == [False, True, False, False, False, True, False, True, True, False]
    assert [n.tap for n in part.notes] == [False] * 8 + [True, True]
    assert part.notes[4].frets == (0, 1)


def test_chart_hopo_threshold_scales_with_resolution(tmp_path):
    f = write_chart_file(tmp_path / "notes.chart", {"ExpertSingle": ["0 = N 0 0", "162 = N 1 0", "325 = N 2 0"]},
                         res=480)  # floor(65/192 x 480) = 162
    assert [n.hopo for n in read_chart(f).parts[("guitar", "expert")].notes] == [False, True, False]
    mods = ChartModifiers(hopo_frequency=200)
    assert [n.hopo for n in read_chart(f, modifiers=mods).parts[("guitar", "expert")].notes] == [False, True, True]


def test_chart_sustains_opens_star_power_and_solos(tmp_path):
    rows = ["768 = N 7 0", "768 = S 2 384",
            "960 = N 0 10", "960 = E solo",          # .chart keeps even a 10-tick sustain
            "1152 = N 1 0", "1152 = N 2 96", "1152 = E soloend",
            "1344 = N 7 0", "1344 = N 0 0"]          # an open with a fret: the open is dropped
    part = read_chart(write_chart_file(tmp_path / "notes.chart", {"ExpertDoubleBass": rows})).parts[("bass", "expert")]
    sec = 1 / 384  # seconds per tick at 120 BPM, resolution 192
    assert [(n.frets, n.end) for n in part.notes] == [
        ((OPEN,), None), ((0,), pytest.approx(970 * sec)), ((1, 2), pytest.approx(1248 * sec)), ((0,), None)]
    assert [(p.start, p.end) for p in part.star_power] == [(pytest.approx(768 * sec), pytest.approx(1152 * sec))]
    # the soloend tick is inside the solo
    assert [(p.start, p.end) for p in part.solos] == [(pytest.approx(960 * sec), pytest.approx(1153 * sec))]


def test_chart_overlapping_sustains_and_phrases(tmp_path):
    rows = ["0 = N 0 400", "0 = S 2 768", "192 = N 0 0", "384 = S 2 100",
            "1536 = N 1 0", "1536 = S 2 96", "1536 = S 2 192"]
    part = read_chart(write_chart_file(tmp_path / "notes.chart", {"ExpertSingle": rows})).parts[("guitar", "expert")]
    sec = 1 / 384
    # the sustain stops at the next green, which carries the rest of it
    assert [n.end for n in part.notes] == [pytest.approx(192 * sec), pytest.approx(400 * sec), None]
    assert [(p.start / sec, p.end / sec) for p in part.star_power] == [
        pytest.approx((0, 384)), pytest.approx((384, 768)), pytest.approx((1536, 1728))]


def test_chart_chord_snap(tmp_path):
    f = write_chart_file(tmp_path / "notes.chart", {"ExpertSingle": ["0 = N 0 0", "5 = N 1 0", "96 = N 2 0"]})
    assert len(read_chart(f).parts[("guitar", "expert")].notes) == 3
    snapped = read_chart(f, modifiers=ChartModifiers(chord_snap_threshold=10)).parts[("guitar", "expert")]
    assert [(n.time, n.frets) for n in snapped.notes] == [(0.0, (0, 1)), (pytest.approx(0.25), (2,))]


def test_chart_pro_drums(tmp_path):
    rows = ["768 = N 0 0", "768 = N 2 0", "768 = N 66 0",                 # kick, yellow cymbal
            "768 = S 2 96",
            "864 = N 1 0", "864 = N 34 0",                                # red accent
            "960 = N 32 0",                                               # 2x kick
            "1056 = N 4 0", "1056 = N 68 0", "1056 = N 37 0",             # green cymbal, accent
            "1152 = N 1 0", "1152 = N 40 0",                              # red ghost
            "1248 = N 3 0",                                               # blue tom
            "1344 = N 3 0", "1344 = N 67 0", "1344 = N 42 0",             # blue cymbal, ghost
            "1536 = S 64 192", "1600 = N 1 0",                            # a fill
            "3072 = S 64 192", "3100 = N 0 0"]                            # after [coda]: a big rock ending
    s = read_chart(write_chart_file(tmp_path / "notes.chart", {"ExpertDrums": rows}, events=('3000 = E "coda"',)))
    part = s.parts[("drums", "expert")]
    sec = 1 / 384
    hits = [(round(h.time / sec), h.pad, h.cymbal, h.double_kick, h.accent, h.ghost) for h in part.notes]
    assert hits == [(768, 0, False, False, False, False), (768, 2, True, False, False, False),
                    (864, 1, False, False, True, False), (960, 0, False, True, False, False),
                    (1056, 4, True, False, True, False), (1152, 1, False, False, False, True),
                    (1248, 3, False, False, False, False), (1344, 3, True, False, False, True),
                    (1600, 1, False, False, False, False), (3100, 0, False, False, False, False)]
    assert [(round(a.start / sec), round(a.end / sec)) for a in part.activation] == [(1536, 1728)]
    assert len(part.star_power) == 1


def test_chart_four_and_five_lane_drums(tmp_path):
    four = write_chart_file(tmp_path / "four.chart", {"ExpertDrums": ["0 = N 2 0", "192 = N 4 0"]})
    assert not any(h.cymbal for h in read_chart(four).parts[("drums", "expert")].notes)  # no markers: no cymbals
    five = write_chart_file(tmp_path / "five.chart", {"ExpertDrums": ["0 = N 2 0", "192 = N 4 0", "384 = N 5 0",
                                                                     "576 = N 4 0", "576 = N 5 0"]})
    hits = [(h.pad, h.cymbal) for h in read_chart(five).parts[("drums", "expert")].notes]
    # 5-lane: yellow and orange are cymbals (orange on green); green is a tom, on blue when orange shares its tick
    assert hits == [(2, True), (4, True), (4, False), (3, False), (4, True)]


def test_round_trip_through_the_chart_writer(tmp_path):
    tm = TempoMap(192, [Tempo(0, 120000), Tempo(768, 90000)])
    guitar = Track("Expert", "Single", [
        FretNote(768, (0,)), FretNote(832, (2,)), FretNote(896, (3,), flip=True), FretNote(1152, (0, 2), length=192),
        FretNote(1536, (OPEN,)), FretNote(1600, (4,), tap=True)], [Phrase(768, 384)], [(1536, 1600)])
    drums = Track("Expert", "Drums", [DrumHit(768, 0), DrumHit(768, 2, cymbal=True), DrumHit(864, 1, accent=True),
                                      DrumHit(960, 0, double_kick=True), DrumHit(1056, 3, ghost=True)])
    chart = Chart(SongInfo("T", "A"), tm, [(768, "Verse")], [guitar, drums])
    f = tmp_path / "notes.chart"
    f.write_text(write_chart(chart), encoding="utf-8")
    s = read_chart(f)
    g = s.parts[("guitar", "expert")]
    assert [n.time for n in g.notes] == pytest.approx([tm.tick_to_sec(n.tick) for n in guitar.notes])
    assert [n.frets for n in g.notes] == [(0,), (2,), (3,), (0, 2), (OPEN,), (4,)]
    # 64-tick fret changes are natural HOPOs, so the flipped one strums; the tap is a HOPO underneath
    assert [n.hopo for n in g.notes] == [False, True, False, False, False, True]
    assert [n.tap for n in g.notes] == [False] * 5 + [True]
    assert g.notes[3].end == pytest.approx(tm.tick_to_sec(1344))
    assert [(p.start, p.end) for p in g.solos] == [
        (pytest.approx(tm.tick_to_sec(1536)), pytest.approx(tm.tick_to_sec(1601)))]  # the soloend tick is inside
    d = s.parts[("drums", "expert")]
    assert [(h.pad, h.cymbal, h.double_kick, h.accent, h.ghost) for h in d.notes] == [
        (0, False, False, False, False), (2, True, False, False, False), (1, False, False, True, False),
        (0, False, True, False, False), (3, False, False, False, True)]
    assert s.sections == [(pytest.approx(tm.tick_to_sec(768)), "Verse")]


def test_bad_chart_is_rejected(tmp_path):
    f = tmp_path / "notes.chart"
    f.write_text("[Song]\r\n{\r\n  Name = \"x\"\r\n}\r\n")
    with pytest.raises(ValueError):
        read_chart(f)


# ------------------------------------------------------------------------------------------------ .mid

def guitar_mid(tmp_path, name="notes.mid"):
    ev = text(0, "[ENHANCED_OPENS]")
    ev += note(0, 96, 120)                          # G; 120 ticks <= floor(480/3) + 1 = 161: no sustain
    ev += note(120, 97, 162)                        # R, 120 ticks later: natural HOPO; 162 ticks: a sustain
    ev += note(480, 98, 60)                         # Y, 360 ticks: strum
    ev += note(960, 99, 60) + note(960, 101, 40)    # B, forced HOPO
    ev += note(1080, 100, 60) + note(1080, 102, 1)  # O, natural HOPO forced to strum
    ev += note(1440, 96, 60) + note(1440, 104, 60)  # tap (note 104)
    ev += note(1920, 97, 60) + sysex(1920, 3, 4, True) + sysex(1921, 3, 4, False)   # tap (SysEx, Expert)
    ev += note(2400, 96, 400) + sysex(2400, ALL, 1, True) + sysex(2401, ALL, 1, False)  # open (SysEx)
    ev += note(2880, 95, 100)                       # open (ENHANCED_OPENS)
    ev += note(3360, 96, 60) + note(3360, 97, 60)   # chord G+R
    ev += note(3480, 97, 60)                        # R from that chord: never a natural HOPO in .mid
    ev += note(0, 116, 960) + note(1920, 103, 960)  # star power, one solo
    ev += note(0, 84, 100)                          # Hard G
    events = text(0, "[section Intro]") + text(1920, "[prc_verse_1]") + text(2000, "[lighting (verse)]")
    return write_mid_file(tmp_path / name, {"PART GUITAR": ev, "EVENTS": events})


def test_mid_guitar(tmp_path):
    s = read_mid(guitar_mid(tmp_path), time_offset=0.0697)
    sec = 1 / 960  # seconds per tick at 120 BPM, 480 ticks per beat
    e = s.parts[("guitar", "expert")]
    assert [(round((n.time - 0.0697) / sec), n.frets, n.hopo, n.tap) for n in e.notes] == [
        (0, (0,), False, False), (120, (1,), True, False), (480, (2,), False, False), (960, (3,), True, False),
        (1080, (4,), False, False), (1440, (0,), False, True), (1920, (1,), False, True),
        (2400, (OPEN,), False, False), (2880, (OPEN,), False, False), (3360, (0, 1), False, False),
        (3480, (1,), False, False)]
    ends = [None if n.end is None else round((n.end - 0.0697) / sec) for n in e.notes]
    assert ends == [None, 282, None, None, None, None, None, 2800, None, None, None]
    assert [(round((p.start - 0.0697) / sec), round((p.end - 0.0697) / sec)) for p in e.star_power] == [(0, 960)]
    assert [(round((p.start - 0.0697) / sec), round((p.end - 0.0697) / sec)) for p in e.solos] == [(1920, 2880)]
    h = s.parts[("guitar", "hard")]
    assert onsets(h) == [(pytest.approx(0.0697), (0,), False, False)]
    assert len(h.star_power) == 1 and len(h.solos) == 1  # instrument-wide phrases reach every charted difficulty
    assert set(s.parts) == {("guitar", "expert"), ("guitar", "hard")}
    assert s.sections == [(pytest.approx(0.0697), "Intro"), (pytest.approx(0.0697 + 2.0), "verse_1")]


def test_mid_drums(tmp_path):
    ev = text(0, "[ENABLE_CHART_DYNAMICS]")
    ev += note(0, 96, 1) + note(0, 98, 1)           # kick, yellow: a cymbal
    ev += note(480, 98, 1) + note(480, 110, 1)      # yellow under a tom marker: tom
    ev += note(960, 99, 1) + note(960, 100, 1) + note(960, 112, 480)  # blue cymbal, green tom
    ev += note(1440, 100, 1)                        # the marker's end tick is outside it: cymbal
    ev += note(1920, 95, 1)                         # 2x kick
    ev += note(2400, 97, 1, velocity=127) + note(2880, 97, 1, velocity=1) + note(3360, 97, 1)  # accent, ghost, plain
    ev += [x for p in range(120, 125) for x in note(3840, p, 480)] + note(3900, 97, 1)  # a fill (120-124)
    ev += note(0, 116, 480)
    ev += note(0, 84, 1) + note(0, 86, 1)           # Hard kick + yellow
    s = read_mid(write_mid_file(tmp_path / "notes.mid", {"PART DRUMS": ev}))
    sec = 1 / 960
    d = s.parts[("drums", "expert")]
    assert [(round(h.time / sec), h.pad, h.cymbal, h.double_kick, h.accent, h.ghost) for h in d.notes] == [
        (0, 0, False, False, False, False), (0, 2, True, False, False, False), (480, 2, False, False, False, False),
        (960, 3, True, False, False, False), (960, 4, False, False, False, False), (1440, 4, True, False, False, False),
        (1920, 0, False, True, False, False), (2400, 1, False, False, True, False),
        (2880, 1, False, False, False, True),
        (3360, 1, False, False, False, False), (3900, 1, False, False, False, False)]
    assert [(round(a.start / sec), round(a.end / sec)) for a in d.activation] == [(3840, 4320)]
    assert [(h.pad, h.cymbal) for h in s.parts[("drums", "hard")].notes] == [(0, False), (2, True)]


def test_mid_four_lane_drums_need_pro_drums_for_cymbals(tmp_path):
    folder = tmp_path / "song"
    folder.mkdir()
    write_mid_file(folder / "notes.mid", {"PART DRUMS": note(0, 98, 1) + note(480, 100, 1)})
    assert not any(h.cymbal for h in read_mid(folder / "notes.mid").parts[("drums", "expert")].notes)
    (folder / "song.ini").write_text("[song]\r\nname = x\r\npro_drums = True\r\n")
    assert all(h.cymbal for h in read_song(folder).parts[("drums", "expert")].notes)


def test_mid_bass_and_legacy_star_power(tmp_path):
    ev = note(0, 96, 1) + note(960, 97, 1) + note(0, 103, 480) + note(960, 103, 480)
    s = read_mid(write_mid_file(tmp_path / "notes.mid", {"PART BASS": ev, "PART VOCALS": note(0, 60, 100)}))
    part = s.parts[("bass", "expert")]
    # no note-116 phrase and more than one note-103 phrase: a GH1/GH2 chart, where 103 is star power
    assert len(part.star_power) == 2 and not part.solos
    assert list(s.parts) == [("bass", "expert")]
    kept = read_mid(tmp_path / "notes.mid", modifiers=ChartModifiers(multiplier_note=116)).parts[("bass", "expert")]
    assert not kept.star_power and len(kept.solos) == 2


def test_mid_running_status_and_velocity_zero_note_off(tmp_path):
    def chunk(kind, body):
        return kind + len(body).to_bytes(4, "big") + body
    name = b"PART GUITAR"
    tempo = bytes([0x00, 0xFF, 0x51, 0x03, 0x07, 0xA1, 0x20, 0x00, 0xFF, 0x2F, 0x00])          # 500000 us/beat
    guitar = (bytes([0x00, 0xFF, 0x03, len(name)]) + name
              + bytes([0x00, 0x90, 96, 100, 0x83, 0x60, 96, 0,     # note on, then (running status) velocity 0 = off
                       0x00, 97, 100, 0x83, 0x60, 97, 0, 0x00, 0xFF, 0x2F, 0x00]))
    data = chunk(b"MThd", (1).to_bytes(2, "big") + (2).to_bytes(2, "big") + (480).to_bytes(2, "big"))
    f = tmp_path / "notes.mid"
    f.write_bytes(data + chunk(b"MTrk", tempo) + chunk(b"MTrk", guitar))
    part = read_mid(f).parts[("guitar", "expert")]
    assert [(n.time, n.frets, n.end, n.hopo) for n in part.notes] == [
        (0.0, (0,), pytest.approx(0.5), False), (pytest.approx(0.5), (1,), pytest.approx(1.0), False)]


def test_mid_format_zero_is_rejected(tmp_path):
    mf = mido.MidiFile(type=0, ticks_per_beat=480)
    mf.tracks.append(mido.MidiTrack())
    mf.save(tmp_path / "notes.mid")
    with pytest.raises(ValueError):
        read_mid(tmp_path / "notes.mid")


# ------------------------------------------------------------------------------------------------ folders and song.ini

def test_read_song_picks_the_chart_and_applies_song_ini(tmp_path):
    folder = tmp_path / "song"
    folder.mkdir()
    write_chart_file(folder / "notes.chart", {"ExpertSingle": ["0 = N 0 0", "100 = N 1 0"]}, song=("Offset = 1",))
    guitar_mid(folder)
    (folder / "song.ini").write_text("[Song]\r\nname = x\r\ndelay = 250\r\nhopo_frequency = 100\r\n")
    s = read_song(folder)  # notes.mid wins over notes.chart, as in scan-chart
    assert s.source == str(folder / "notes.mid")
    assert s.parts[("guitar", "expert")].notes[0].time == pytest.approx(0.25)
    c = read_song(folder / "notes.chart", time_offset=0.5, source="tool:x")
    assert s is not c and c.source == "tool:x"
    # the ini's delay replaces the chart's Offset; its hopo_frequency makes the 100-tick change a HOPO
    assert onsets(c.parts[("guitar", "expert")]) == [(pytest.approx(0.75), (0,), False, False),
                                                     (pytest.approx(0.75 + 100 / 384), (1,), True, False)]
    with pytest.raises(FileNotFoundError):
        read_song(tmp_path)


def test_read_ini_modifiers(tmp_path):
    f = tmp_path / "song.ini"
    f.write_text("; comment\r\n[other]\r\npro_drums = True\r\n[SONG]\r\nhopofreq = 170\r\neighthnote_hopo = 1\r\n"
                 "sustain_cutoff_threshold = -1\r\nchord_snap_threshold = 12\r\nstar_power_note = 103\r\n"
                 "five_lane_drums = true\r\ndelay = -120\r\n")
    assert read_ini_modifiers(f) == ChartModifiers(hopo_frequency=170, eighthnote_hopo=True,
                                                   sustain_cutoff_threshold=-1, chord_snap_threshold=12,
                                                   multiplier_note=103, pro_drums=False, five_lane_drums=True,
                                                   delay_ms=-120)
