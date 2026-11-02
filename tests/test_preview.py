"""Chart previews (songcharter.preview) on a small synthetic song: what is flagged (gaps, held sustains, notes in
silence), measure lines from the time signatures, and that both pictures are drawn."""
import numpy as np
import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("librosa")

from songcharter import audio as A  # noqa: E402
from songcharter.chart import Chart, DrumHit, FretNote, SongInfo, Track, write_chart  # noqa: E402
from songcharter.preview import _mmss, flags, load, measure_stats, render_overview, render_pages  # noqa: E402
from songcharter.tempo import Tempo, TempoMap, TimeSignature  # noqa: E402

RES = 192
BEAT = 0.5          # 120 BPM: a 4/4 measure is 2 s
SR = A.SAMPLE_RATE


def song(tmp_path, signatures=()):
    """12 measures of 4/4 at 120 BPM. Guitar: 8th notes in measures 1-3, a chord held from measure 5 through measure
    6, nothing in measures 7-8, one note in measure 10. Drums: quarter notes in measures 1-8."""
    tm = TempoMap(RES, [Tempo(0, 120000)], list(signatures) or [TimeSignature(0, 4)])
    m = 4 * RES
    guitar = [FretNote(k * m + i * RES // 2, ((0,), (1,), (2,))[i % 3]) for k in (1, 2, 3) for i in range(8)]
    guitar += [FretNote(5 * m, (0, 2), 2 * m - RES // 2), FretNote(10 * m, (1,))]
    drums = [DrumHit(k * m + i * RES, i % 2) for k in range(1, 9) for i in range(4)]
    chart = Chart(SongInfo("t", "a"), tm, [(0, "intro"), (5 * m, "verse")],
                  [Track("Expert", "Single", guitar), Track("Expert", "Drums", drums)])
    (tmp_path / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    return tmp_path


def stem(loud_measures, seconds=24.0):
    """A stereo stem: noise bursts on every beat of the loud measures, silence elsewhere."""
    rng = np.random.default_rng(0)
    y = np.zeros(int(seconds * SR), dtype=np.float32)
    burst = (rng.standard_normal(int(0.1 * SR)) * np.exp(-np.arange(int(0.1 * SR)) / 800)).astype(np.float32)
    for k in loud_measures:
        for b in range(4):
            i = int((2 * k + b * BEAT) * SR)
            y[i:i + len(burst)] += 0.5 * burst
    return np.stack([y, y])


def test_gaps_holds_and_notes_in_silence(tmp_path):
    folder = song(tmp_path)
    # the guitar stem plays in measures 1-8; measure 10's note is in silence
    pv = load(folder, stems={"other": stem(range(1, 9))}, pad=0.0)
    assert list(pv.measures[:4]) == [0.0, 2.0, 4.0, 6.0]
    rows = measure_stats(pv, "guitar")
    assert [r["onsets"] for r in rows[:11]] == [0, 8, 8, 8, 0, 1, 0, 0, 0, 0, 1]
    assert rows[6]["held"] and not rows[7]["held"]  # the chord from measure 5 rings through measure 6
    found = [(f.instrument, f.kind, f.start, f.end) for f in flags(pv)]
    assert ("guitar", "gap", 8.0, 10.0) in found          # measure 4: stem plays, nothing charted
    assert ("guitar", "gap", 14.0, 18.0) in found         # measures 7-8, merged
    assert not any(f[2] == 12.0 for f in found)           # measure 6 is held, not a gap
    assert ("guitar", "notes in silence", 20.0, 22.0) in found
    assert all(f[0] == "guitar" for f in found)           # no drum stem: drums are not judged
    assert "guitar: gap 0:14.0-0:18.0 (2 measures)" in [str(f) for f in flags(pv)]


def test_measure_lines_follow_the_time_signatures(tmp_path):
    folder = song(tmp_path, [TimeSignature(0, 4), TimeSignature(8 * RES, 3)])
    pv = load(folder)
    assert list(pv.measures[:5]) == [0.0, 2.0, 4.0, 5.5, 7.0]
    assert pv.envelopes == {}  # no report.json and no stems: notes only


def test_both_pictures_are_drawn(tmp_path):
    folder = song(tmp_path)
    pv = load(folder, stems={"other": stem(range(1, 9)), "drums": stem(range(1, 9))}, pad=0.0)
    found = render_overview(pv, tmp_path / "overview.png")
    pages = render_pages(pv, tmp_path / "pages", page_s=12, strip_s=6)
    assert (tmp_path / "overview.png").stat().st_size > 10_000 and found == flags(pv)
    assert [p.name for p in pages] == ["page_01.png", "page_02.png"] and all(p.stat().st_size > 10_000 for p in pages)


def test_times_read_as_minutes_and_seconds():
    assert _mmss(59.96) == "1:00.0" and _mmss(125.04) == "2:05.0" and _mmss(-1) == "0:00.0"
