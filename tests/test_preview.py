"""Chart previews (songcharter.preview) on a small synthetic song: what is flagged (gaps, rings, held sustains, notes
in silence, notes after the audio) and against which stem, where the stems and the song's length come from, measure
lines from the chart's time signatures, what the pictures draw, and the command line."""
import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("librosa")

from songcharter import audio as A  # noqa: E402
from songcharter import preview as P  # noqa: E402
from songcharter.chart import Chart, DrumHit, FretNote, SongInfo, Track, write_chart  # noqa: E402
from songcharter.preview import (_draw_frets, _mmss, flags, load, main, measure_stats, remarks,  # noqa: E402
                                 render_overview, render_pages)
from songcharter.tempo import Tempo, TempoMap, TimeSignature  # noqa: E402
from songcharter.timed import TimedNote, TimedPart  # noqa: E402

RES = 192
BEAT = 0.5          # 120 BPM: a 4/4 measure is 2 s
SR = A.SAMPLE_RATE


def song(folder, signatures=(), hard=False):
    """12 measures of 4/4 at 120 BPM. Guitar: 8th notes in measures 1-3, a chord held from measure 5 to 13.75 s,
    nothing in measures 7-8, one note in measure 10. Drums: quarter notes in measures 1-8. hard: a Hard guitar part
    too (the drums stay Expert only)."""
    folder.mkdir(parents=True, exist_ok=True)
    tm = TempoMap(RES, [Tempo(0, 120000)], list(signatures) or [TimeSignature(0, 4)])
    m = 4 * RES
    guitar = [FretNote(k * m + i * RES // 2, ((0,), (1,), (2,))[i % 3]) for k in (1, 2, 3) for i in range(8)]
    guitar += [FretNote(5 * m, (0, 2), 2 * m - RES // 2), FretNote(10 * m, (1,))]
    drums = [DrumHit(k * m + i * RES, i % 2) for k in range(1, 9) for i in range(4)]
    tracks = [Track("Expert", "Single", guitar), Track("Expert", "Drums", drums)]
    tracks += [Track("Hard", "Single", guitar)] if hard else []
    chart = Chart(SongInfo("t", "a"), tm, [(0, "intro"), (5 * m, "verse")], tracks)
    (folder / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    return folder


def signal(seconds=24.0, sr=SR, bursts=(), tones=()):
    """A stereo stem. bursts: (time, seconds) of decaying noise; tones: (start, end, Hz, amplitude, decay seconds or
    None for a steady tone)."""
    rng = np.random.default_rng(0)
    y = np.zeros(int(seconds * sr), dtype=np.float32)
    for t, length in bursts:
        n = int(length * sr)
        i = int(t * sr)
        burst = rng.standard_normal(n) * np.exp(-np.arange(n) / (800 * sr / SR))
        y[i:i + n] += (0.5 * burst[:len(y) - i]).astype(np.float32)
    for t0, t1, hz, amp, decay in tones:
        i, j = int(t0 * sr), int(t1 * sr)
        k = np.arange(j - i) / sr
        env = np.exp(-k / decay) if decay else 1.0
        y[i:j] += (amp * env * np.sin(2 * np.pi * hz * k)).astype(np.float32)
    return np.stack([y, y])


def on_beats(measures):
    return [(2 * k + b * BEAT, 0.1) for k in measures for b in range(4)]


def stem(loud_measures, seconds=24.0, sr=SR):
    """Noise bursts on every beat of the loud measures, silence elsewhere."""
    return signal(seconds, sr, bursts=on_beats(loud_measures))


def found(pv, difficulty="expert"):
    return [(f.instrument, f.kind, f.start, f.end) for f in flags(pv, difficulty)]


@pytest.fixture
def figures(monkeypatch):
    """Every figure the renders save, as (file name, figure), so a test can look at what was drawn."""
    from matplotlib.figure import Figure
    saved = []
    real = Figure.savefig

    def savefig(self, path, *args, **kwargs):
        real(self, path, *args, **kwargs)
        saved.append((Path(path).name, self))

    monkeypatch.setattr(Figure, "savefig", savefig)
    return saved


# ------------------------------------------------------------------------------------------------ flags

def test_gaps_holds_and_notes_in_silence(tmp_path):
    folder = song(tmp_path)
    # the guitar stem plays in measures 1-8; measure 10's note is in silence
    pv = load(folder, stems={"other": stem(range(1, 9))}, pad=0.0)
    assert list(pv.measures[:4]) == [0.0, 2.0, 4.0, 6.0]
    rows = measure_stats(pv, "guitar")
    assert [r["onsets"] for r in rows[:11]] == [0, 8, 8, 8, 0, 1, 0, 0, 0, 0, 1]
    assert rows[6]["held"] and not rows[7]["held"]  # the chord from measure 5 rings through measure 6
    assert found(pv) == [("guitar", "gap", 8.0, 10.0),          # measure 4: stem plays, nothing charted
                         ("guitar", "gap", 14.0, 18.0),         # measures 7-8, merged; measure 6 is held, not a gap
                         ("guitar", "notes in silence", 20.0, 22.0)]  # no drum stem: drums are not judged
    assert "guitar: gap 0:14.0-0:18.0 (2 measures)" in [str(f) for f in flags(pv)]


def test_the_pad_moves_the_stems_onto_the_song(tmp_path):
    """Stems are in input seconds: a 2-s pad (one measure) moves every loud measure one later, so +pad, 0 and -pad
    all give different flags."""
    pv = load(song(tmp_path), stems={"other": stem(range(1, 9))}, pad=2.0)
    assert found(pv) == [("guitar", "notes in silence", 2.0, 4.0), ("guitar", "gap", 8.0, 10.0),
                         ("guitar", "gap", 14.0, 20.0), ("guitar", "notes in silence", 20.0, 22.0)]
    assert pv.envelopes["guitar"].times[0] == pytest.approx(2.0)


def test_report_json_gives_the_stems_and_the_pad(tmp_path, capsys):
    """By default the stems and pad come from report.json (as assemble writes it); stems given by the caller, in
    input seconds, still take the report's pad."""
    folder = song(tmp_path / "song")
    A.write_wav(stem(range(1, 9)), tmp_path / "other.wav")
    A.write_wav(stem(range(1, 9)), tmp_path / "drums.wav")
    report = {"stems": {"other": {"path": str(tmp_path / "other.wav")}, "drums": {"path": str(tmp_path / "drums.wav")}},
              "lead_in": {"pad_seconds": 2.0}}
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    pv = load(folder)
    assert pv.stems == {"guitar": "other", "drums": "drums"} and pv.missing == {}
    want = found(load(folder, stems={"other": stem(range(1, 9)), "drums": stem(range(1, 9))}, pad=2.0))
    assert found(pv) == want
    assert ("drums", "notes in silence", 2.0, 4.0) in want and ("drums", "gap", 18.0, 20.0) in want
    assert found(load(folder, stems={"other": str(tmp_path / "other.wav")})) == [f for f in want if f[0] == "guitar"]
    assert found(load(folder, stems={"other": stem(range(1, 9))}, pad=0.0))[0] == ("guitar", "gap", 8.0, 10.0)
    assert main([str(folder), "--out", str(tmp_path / "pv"), "--no-pages"]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert [line for line in printed if line.startswith("  ")] == [f"  {f}" for f in flags(pv)]


def test_a_stem_at_another_sample_rate(tmp_path):
    """A 48 kHz WAV is read at its own rate, not stretched 8.8% onto 44.1 kHz."""
    folder = song(tmp_path / "song")
    A.write_wav(stem(range(1, 9), sr=48000), tmp_path / "other48.wav", 48000)
    A.write_wav(stem(range(1, 9)), tmp_path / "other44.wav")
    pv48 = load(folder, stems={"other": tmp_path / "other48.wav"}, pad=0.0)
    pv44 = load(folder, stems={"other": tmp_path / "other44.wav"}, pad=0.0)
    assert pv48.duration == pytest.approx(pv44.duration, abs=0.01)
    assert pv48.envelopes["guitar"].times[-1] == pytest.approx(pv44.envelopes["guitar"].times[-1], abs=0.05)
    assert found(pv48) == found(pv44)


def test_drums_are_judged_against_the_drum_stem(tmp_path):
    """Drums are charted in measures 1-8; their stem is silent in measure 3, where the bass stem plays."""
    folder = song(tmp_path)
    drums = stem([1, 2, 4, 5, 6, 7, 8])
    pv = load(folder, stems={"drums": drums, "bass": stem(range(12))}, pad=0.0)
    assert pv.stems == {"drums": "drums"}  # the chart has no bass part
    assert found(pv) == [("drums", "notes in silence", 6.0, 8.0)]


def test_the_level_leaves_out_the_measure_edges(tmp_path):
    """Measure 10's note is in silence although a burst starts on the next downbeat: the frames that reach across
    the measure line are not the measure's."""
    pv = load(song(tmp_path), stems={"other": signal(bursts=on_beats(range(1, 9)) + [(22.0, 0.1)])}, pad=0.0)
    assert ("guitar", "notes in silence", 20.0, 22.0) in found(pv)


def test_a_gap_needs_a_sustained_level_and_new_attacks(tmp_path, monkeypatch):
    """Guitar: a tone that rings on from the held chord (10-13.75 s) to 16 s, two 5-ms clicks (bleed) in measure 8,
    and a hum from 18.3 s. Only the ring is flagged: the clicks are attacks but too short to be playing, the hum has
    one attack and is not the chord's sound. Drums: a cymbal ringing out after the last hit (17.5 s) is no gap."""
    folder = song(tmp_path)
    guitar = signal(bursts=on_beats(range(1, 4)) + [(16.5, 0.005), (17.3, 0.005)],
                    tones=[(10.0, 16.0, 220.0, 0.2, None), (18.3, 20.0, 110.0, 0.1, None)])
    cymbal = [(17.5, 22.0, hz, 0.15, 1.5) for hz in (3100.0, 4700.0, 6300.0)]
    drums = signal(bursts=on_beats(range(1, 9)), tones=cymbal)
    pv = load(folder, stems={"other": guitar, "drums": drums}, pad=0.0)
    rows = {r["start"]: r for r in measure_stats(pv, "drums")}
    assert rows[18.0]["loud_share"] > 0.5 and rows[18.0]["attacks"] == 0  # loud, but rings out: not a gap
    assert found(pv) == [("guitar", "rings past its sustain", 14.0, 16.0), ("guitar", "notes in silence", 20.0, 22.0)]
    rows = {r["start"]: r for r in measure_stats(pv, "guitar")}
    assert rows[16.0]["peak_db"] > P.GAP_DB and rows[16.0]["loud_share"] < P.GAP_SHARE  # the clicks
    assert rows[16.0]["attacks"] == 2
    assert rows[18.0]["loud_share"] > 0.5 and rows[18.0]["attacks"] == 1 and not rows[18.0]["rings"]  # the hum


def test_hum_switching_on_is_no_attack(tmp_path, monkeypatch):
    """A hum (110 Hz and its harmonics) under the whole guitar stem, cut twice in measure 7: where it stops and comes
    back the onset strength peaks, but the level only reaches the stem's floor, so those are no attacks and nothing
    is flagged. With the floor ignored they would make a gap."""
    folder = song(tmp_path)
    hum = [(t0, t1, hz, 0.03, None) for t0, t1 in ((0.0, 14.5), (14.7, 15.2), (15.4, 24.0))
           for hz in (110.0, 220.0, 330.0, 440.0, 550.0)]
    pv = load(folder, stems={"other": signal(bursts=on_beats(range(1, 4)) + on_beats([5, 10]), tones=hum)}, pad=0.0)
    row = next(r for r in measure_stats(pv, "guitar") if r["start"] == 14.0)
    assert row["loud_share"] > 0.5 and row["attacks"] == 0 and not row["rings"]
    assert found(pv) == []
    monkeypatch.setattr(P, "FLOOR_DB", -1e9)
    assert ("guitar", "gap", 14.0, 16.0) in found(pv)


def test_guitar_is_judged_against_guitar_other_and_piano(tmp_path):
    """A 6-stem set: the charted line is in "other" while the guitar stem is silent. Guitar is judged against the sum
    of guitar, other and piano (htdemucs_ft's "other"); a 4-stem set still uses "other" alone."""
    folder = song(tmp_path)
    silent = np.zeros((2, int(24 * SR)), dtype=np.float32)
    pv = load(folder, stems={"guitar": silent, "other": stem(range(1, 9)), "piano": silent}, pad=0.0)
    assert pv.stems["guitar"] == "guitar+other+piano"
    want = [("guitar", "gap", 8.0, 10.0), ("guitar", "gap", 14.0, 18.0), ("guitar", "notes in silence", 20.0, 22.0)]
    assert [f for f in found(pv) if f[0] == "guitar"] == want  # measure 10 is silent in all three: still flagged
    pv4 = load(folder, stems={"other": stem(range(1, 9))}, pad=0.0)
    assert pv4.stems == {"guitar": "other"} and found(pv4) == want


def test_a_level_the_chart_lacks_is_not_judged(tmp_path, capsys):
    """Guitar has Expert and Hard, drums Expert only: at Hard the drums are not judged (no whole-song "gap"), and
    the text says why."""
    folder = song(tmp_path / "song", hard=True)
    pv = load(folder, stems={"other": stem(range(1, 9)), "drums": stem(range(1, 9))}, pad=0.0)
    assert [f[0] for f in found(pv, "hard")] == ["guitar"] * 3
    assert measure_stats(pv, "drums", "hard") == []
    assert remarks(pv, "hard") == ["drums: no hard part (levels: expert)"]
    assert flags(pv, "medium") == []
    assert remarks(pv, "medium") == ["no instrument has a medium part (levels: expert, hard)"]
    A.write_wav(stem(range(1, 9)), tmp_path / "drums.wav")
    (folder / "report.json").write_text(json.dumps({"stems": {"drums": {"path": str(tmp_path / "drums.wav")}}}))
    assert main([str(folder), "--difficulty", "hard", "--out", str(tmp_path / "pv")]) == 0
    printed = capsys.readouterr().out
    assert "  drums: no hard part (levels: expert)" in printed and "drums: gap" not in printed


def test_the_song_runs_to_the_chart_past_a_short_song_ogg(tmp_path, capsys):
    """A 1-s stub song.ogg (as the eval refs carry) no longer cuts the pictures to 1 s: the song runs to the chart's
    or the stems' end, and the notes after the audio are flagged and named."""
    folder = song(tmp_path / "song")
    A.encode_ogg(np.zeros((2, SR), dtype=np.float32), folder / "song.ogg")
    pv = load(folder, stems={"other": stem(range(1, 9)), "drums": stem(range(1, 9))}, pad=0.0)
    assert pv.audio_end == pytest.approx(1.0, abs=0.01) and pv.duration == pytest.approx(24.0)
    assert len(measure_stats(pv, "guitar")) == 12 and measure_stats(pv, "guitar")[-1]["peak_db"] is not None
    after = [f for f in flags(pv) if f.kind == "notes after audio"]
    assert [(f.instrument, f.start, f.end, f.measures) for f in after] == [
        ("drums", pytest.approx(1.0, abs=0.01), 17.5, 9), ("guitar", pytest.approx(1.0, abs=0.01), 20.0, 10)]
    assert ("guitar", "gap", 14.0, 18.0) in found(pv)
    assert remarks(pv)[0] == "song.ogg is 0:01.0 long (a stub?) but the chart runs to 0:20.0: drawn to 0:24.0"
    assert main([str(folder), "--out", str(tmp_path / "pv")]) == 0
    printed = capsys.readouterr().out
    assert " and 1 pages" in printed and "  guitar: notes after audio 0:01.0-0:20.0 (10 measures)" in printed


def test_stems_report_json_lists_but_cannot_find_are_named(tmp_path, capsys, figures):
    """A folder moved from another machine: report.json's paths are not there. A stem of the same name in the song
    folder is used; one that is nowhere is named, in the text and on the overview; an entry without a path is no
    crash."""
    folder = song(tmp_path / "song")
    A.write_wav(stem(range(1, 9)), folder / "drums.wav")
    report = {"stems": {"other": {"path": "/home/someone/work/ft/other.wav"},
                        "drums": {"path": "C:\\Users\\someone\\work\\ft\\drums.wav"}, "vocals": {}},
              "lead_in": {"pad_seconds": 0.0}}
    (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
    pv = load(folder)
    assert pv.stems == {"drums": "drums"}
    assert pv.missing == {"other": "/home/someone/work/ft/other.wav", "vocals": ""}
    line = "guitar not judged: report.json lists stem other at /home/someone/work/ft/other.wav, not found"
    assert remarks(pv) == [line]
    assert main([str(folder), "--out", str(tmp_path / "pv"), "--no-pages"]) == 0
    assert f"  {line}" in capsys.readouterr().out
    (_, fig), = figures
    guitar = fig.axes[0]
    assert "no stem: not judged" in [t.get_text() for t in guitar.texts]


# ------------------------------------------------------------------------------------------------ measure lines

def test_measure_lines_follow_the_time_signatures(tmp_path):
    folder = song(tmp_path, [TimeSignature(0, 4), TimeSignature(8 * RES, 3)])
    pv = load(folder)
    assert list(pv.measures[:5]) == [0.0, 2.0, 4.0, 5.5, 7.0]
    assert pv.envelopes == {}  # no report.json and no stems: notes only
    pv = load(song(tmp_path / "six8", [TimeSignature(0, 6, 8)]))
    assert list(pv.measures[:4]) == [0.0, 1.5, 3.0, 4.5]
    assert pv.measures[-1] < pv.duration <= pv.measures[-1] + 1.5  # extended to the song's end


def test_measure_lines_come_from_the_file_the_notes_come_from(tmp_path):
    """notes.mid beside notes.chart: the notes are read from notes.mid (as Clone Hero reads them), and so are the
    measure lines (its 1/4 pickup), not from the 3/4 notes.chart."""
    mido = pytest.importorskip("mido")
    folder = song(tmp_path, [TimeSignature(0, 3)])
    mf = mido.MidiFile(type=1, ticks_per_beat=480)
    mf.tracks.append(mido.MidiTrack([mido.MetaMessage("set_tempo", tempo=500000, time=0),
                                     mido.MetaMessage("time_signature", numerator=1, denominator=4, time=0),
                                     mido.MetaMessage("time_signature", numerator=4, denominator=4, time=480)]))
    guitar = [mido.MetaMessage("track_name", name="PART GUITAR", time=0)]
    for k in range(16):
        guitar += [mido.Message("note_on", note=96, velocity=100, time=0 if k == 0 else 420),
                   mido.Message("note_off", note=96, velocity=0, time=60)]
    mf.tracks.append(mido.MidiTrack(guitar))
    mf.save(folder / "notes.mid")
    pv = load(folder)
    assert Path(pv.song.source).name == "notes.mid"
    assert list(pv.measures[:4]) == [0.0, 0.5, 2.5, 4.5]


# ------------------------------------------------------------------------------------------------ pictures

def _heads(figs):
    """Every note head drawn where it can be seen, as its time."""
    from matplotlib.collections import PathCollection
    out = []
    for _, fig in figs:
        for ax in fig.axes:
            lo, hi = ax.get_xlim()
            out += [x for c in ax.collections if isinstance(c, PathCollection) for x, _ in c.get_offsets()
                    if lo <= x <= hi]
    return sorted(out)


def test_pages_show_every_second_once(tmp_path, figures):
    """A page that is not a whole number of strips (5 s in strips of 2) ends on a short strip: every note head is on
    exactly one page, none lost between pages, none drawn twice."""
    pv = load(song(tmp_path))
    pages = render_pages(pv, tmp_path / "pages", page_s=5, strip_s=2)
    assert len(pages) == 5 and pv.duration == 22.0
    want = [n.time for n in pv.song.parts[("guitar", "expert")].notes for _ in n.frets]
    want += [h.time for h in pv.song.parts[("drums", "expert")].notes if h.pad]
    assert _heads(figures) == pytest.approx(sorted(want))
    _, first = figures[0]
    assert len(first.axes) == 3 and first.axes[2].get_xlim() == (4.0, 6.0)  # the short strip keeps the scale


def test_bad_page_lengths_are_refused(tmp_path, capsys):
    pv = load(song(tmp_path / "song"))
    with pytest.raises(ValueError):
        render_pages(pv, tmp_path / "pages", page_s=0)
    for bad in ("0", "-5", "nan", "x"):
        with pytest.raises(SystemExit) as e:
            main([str(tmp_path / "song"), "--page", bad, "--out", str(tmp_path / "pv")])
        assert e.value.code == 2
    with pytest.raises(SystemExit):
        main([str(tmp_path / "nowhere")])
    assert not (tmp_path / "pv").exists() and "--page" in capsys.readouterr().err
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "notes.chart").write_text("not a chart", encoding="utf-8")
    assert main([str(tmp_path / "broken")]) == 2  # a file that cannot be read: one line, no traceback
    assert capsys.readouterr().err == "preview: error: not a .chart: no sections\n"


def test_a_sustain_carries_into_the_next_strip():
    """A chord held from 13.5 to 16 s: the 0-15 s strip draws its heads and its sustain to 15 s, the 15-30 s strip
    the rest of the sustain (no heads, which are off that strip)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    part = TimedPart("guitar", "expert", [TimedNote(13.5, (0, 2), 16.0), TimedNote(14.0, (1,))])
    for (a, b), lines, heads in (((0.0, 15.0), [(13.5, 15.0)] * 2, 3), ((15.0, 30.0), [(15.0, 16.0)] * 2, 0)):
        fig, ax = plt.subplots()
        _draw_frets(ax, part, 0.0, a, b)
        assert [tuple(line.get_xdata()) for line in ax.lines] == lines
        assert len(ax.collections) == heads
        plt.close(fig)


def test_page_titles_clear_the_first_strip(tmp_path, figures):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    pv = load(song(tmp_path))
    render_pages(pv, tmp_path / "p60", page_s=60)
    render_pages(pv, tmp_path / "p90", page_s=90)
    for _, fig in figures:
        canvas = FigureCanvasAgg(fig)  # a closed figure has lost its canvas
        canvas.draw()
        r = canvas.get_renderer()
        assert fig._suptitle.get_window_extent(r).y0 >= fig.axes[0].get_tightbbox(r).y1 - 0.5


def test_what_the_pages_draw(tmp_path, figures):
    """Each fret note lane and each drum pad other than the kick is one head, a kick is a short bar, and each
    instrument with a stem has its onset band in every strip."""
    from matplotlib.collections import PathCollection, PolyCollection
    pv = load(song(tmp_path), stems={"other": stem(range(1, 9)), "drums": stem(range(1, 9))}, pad=0.0)
    pages = render_pages(pv, tmp_path / "pages", page_s=12, strip_s=6)
    assert [p.name for p in pages] == ["page_01.png", "page_02.png"]
    axes = [ax for _, fig in figures for ax in fig.axes]
    assert len(axes) == 4
    kicks = [h for h in pv.song.parts[("drums", "expert")].notes if h.pad == 0]
    bars = [line for ax in axes for line in ax.lines if line.get_linewidth() == 5]
    assert sorted(np.mean(line.get_xdata()) for line in bars) == pytest.approx([h.time for h in kicks])
    heads = sum(len(n.frets) for n in pv.song.parts[("guitar", "expert")].notes) + 16  # and the red pad
    assert sum(isinstance(c, PathCollection) for ax in axes for c in ax.collections) == len(_heads(figures)) == heads
    assert [sum(isinstance(c, PolyCollection) for c in ax.collections) for ax in axes] == [2] * 4
    assert "other stem" in [t.get_text() for t in axes[0].get_yticklabels()]


def test_what_the_overview_draws(tmp_path, figures):
    """Per row: one flag span per flag in its colour; the raw level in grey behind the bars; over them each
    measure's peak (the level the flags judge) as a step, and the two thresholds."""
    import matplotlib.colors as mc
    pv = load(song(tmp_path), stems={"other": stem(range(1, 9)), "drums": stem([1, 2, 4, 5, 6, 7, 8, 9])}, pad=0.0)
    assert render_overview(pv, tmp_path / "overview.png") == flags(pv)
    (_, fig), = figures
    for i, inst in enumerate(("guitar", "drums")):
        ax = fig.axes[i]
        twins = [t for t in fig.axes if t is not ax and np.allclose(t.get_position().bounds, ax.get_position().bounds)]
        back, front = sorted(twins, key=lambda t: t.get_zorder())
        assert back.get_zorder() < ax.get_zorder() < front.get_zorder()
        assert [mc.to_hex(line.get_color()) for line in back.lines] == [P.RAW_COLOR]
        rows = measure_stats(pv, inst)
        step = next(line for line in front.lines if line.get_drawstyle() == "steps-post")
        assert list(step.get_ydata()[:-1]) == pytest.approx([np.clip(r["peak_db"], -45, 3) for r in rows])
        limits = [line for line in front.lines if line is not step]
        assert sorted(line.get_ydata()[0] for line in limits) == [P.SILENT_DB, P.GAP_DB]
        assert all(line.get_linewidth() >= 1.2 for line in limits)
        for kind, color in P.FLAG_COLORS.items():
            spans = [p for p in ax.patches if mc.to_hex(p.get_facecolor()) == color]
            assert len(spans) == sum(f.instrument == inst and f.kind == kind for f in flags(pv)), (inst, kind)
    assert ("drums", "notes in silence", 6.0, 8.0) in found(pv) and ("drums", "gap", 18.0, 20.0) in found(pv)


# ------------------------------------------------------------------------------------------------ command line

@pytest.mark.filterwarnings("ignore:Glyph")
def test_cli_on_a_folder_name_the_console_cannot_show(tmp_path, monkeypatch):
    """stdout in cp1252 (Windows, redirected) and a Japanese folder name: the flags are still printed."""
    folder = song(tmp_path / "気持ち")
    A.write_wav(stem(range(1, 9)), tmp_path / "other.wav")
    (folder / "report.json").write_text(json.dumps({"stems": {"other": {"path": str(tmp_path / "other.wav")}}}))
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", stdout)
    assert main([str(folder), "--no-pages"]) == 0
    stdout.flush()
    printed = stdout.buffer.getvalue().decode("cp1252")
    assert "\\u6c17\\u6301\\u3061" in printed and "  guitar: gap 0:08.0-0:10.0 (1 measures)" in printed


def test_times_read_as_minutes_and_seconds():
    assert _mmss(59.96) == "1:00.0" and _mmss(125.04) == "2:05.0" and _mmss(-1) == "0:00.0"
