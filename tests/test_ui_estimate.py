"""The progress screen's time estimate (songcharter.ui.estimate, M7-10): its arithmetic, its rounding, the device and
the takes it assumes for a job, the song's length from ffmpeg's header, and its rates against the measured runs they
come from (the module docstring): the ordinary songs inside the range, the dense ones above it."""
import math
import time

import numpy as np
import pytest

from songcharter import audio as A
from songcharter.ui import estimate as E
from songcharter.ui import jobs as J


def test_the_arithmetic_on_a_four_minute_song():
    """240 s, 4 takes on the GPU, with the preview: every part's low and high values summed, by hand; the GPU's high
    rates the 5070's times 1.35 (the friend's 4070, M7-10's review), each take's own start 0 to 10 s."""
    low = (20 + 0.15 * 240) + (5 + 0.02 * 240) + 0.08 * 240 + 4 * (0 + 0.0007 * 240 ** 2)
    high = (20 + 0.40 * 1.35 * 240) + (5 + 0.05 * 240) + 0.17 * 1.35 * 240 + 4 * (10 + 0.0018 * 1.35 * 240 ** 2)
    assert E.chart_seconds(240, 4, "cuda") == pytest.approx((low, high))
    assert (round(low, 2), round(high, 2)) == (246.28, 821.55)
    assert E.round_minutes(low, high) == (4, 14)   # the page's "4 to 14 minutes"
    assert E.round_minutes(*E.chart_seconds(240, 1, "cuda")) == (2, 7)


def test_the_gpus_high_rates_are_the_5070s_with_the_4070s_margin():
    assert E.FRIEND_GPU == 1.35 and E.TAKE_FIXED == (0.0, 10.0)
    assert E.GUITAR_TAKE["cuda"] == pytest.approx((0.0007, 0.0018 * 1.35))
    assert E.GUITAR_ONCE["cuda"] == pytest.approx((0.08, 0.17 * 1.35))
    assert E.OTHER["cuda"] == ((20.0, 20.0), pytest.approx((0.15, 0.40 * 1.35)))
    assert E.GUITAR_TAKE["cpu"] == (0.0012, 0.0033) and E.OTHER["cpu"] == ((10.0, 10.0), (0.81, 1.13))


def test_each_part_counts_once_and_where_it_runs():
    d = 300.0
    base = E.chart_seconds(d, 0, "cpu", preview=False)
    assert base == pytest.approx((10 + 0.81 * d, 10 + 1.13 * d))   # no guitar: the other stages alone
    preview = E.chart_seconds(d, 0, "cpu")
    assert [b - a for a, b in zip(base, preview)] == pytest.approx([5 + 0.02 * d, 5 + 0.05 * d])
    lyrics = E.chart_seconds(d, 0, "cpu", lyrics=True, preview=False)
    assert [b - a for a, b in zip(base, lyrics)] == pytest.approx([10 + 0.45 * d, 10 + 0.60 * d])
    one = E.chart_seconds(d, 1, "cpu", preview=False)
    three = E.chart_seconds(d, 3, "cpu", preview=False)
    assert [b - a for a, b in zip(base, one)] == pytest.approx([0.35 * d + 0.0012 * d * d,
                                                                0.50 * d + 10 + 0.0033 * d * d])
    # each take after the first adds its start and a transcription, not the first take's own separation
    assert [b - a for a, b in zip(one, three)] == pytest.approx([2 * 0.0012 * d * d, 2 * (10 + 0.0033 * d * d)])
    # the stages on the GPU, the guitar on the CPU: each part at its own device's rates
    mixed = E.chart_seconds(d, 1, "cuda", "cpu", preview=False)
    gpu = E.chart_seconds(d, 0, "cuda", preview=False)
    assert [m - g for g, m in zip(gpu, mixed)] == pytest.approx([b - a for a, b in zip(base, one)])
    # a song twice as long: the takes' transcriptions four times as long (their starts the same)
    takes = lambda s: [b - a for a, b in zip(E.chart_seconds(s, 0, "cuda"), E.chart_seconds(s, 4, "cuda"))]
    once = [r * d for r in E.GUITAR_ONCE["cuda"]]
    starts = [4 * f for f in E.TAKE_FIXED]
    assert [t2 - 2 * o - f for t2, o, f in zip(takes(2 * d), once, starts)] == pytest.approx(
        [4 * (t - o - f) for t, o, f in zip(takes(d), once, starts)])


@pytest.mark.parametrize("bad", [dict(seconds=0, takes=1, device="cpu"), dict(seconds=-1, takes=1, device="cpu"),
                                 dict(seconds=60, takes=-1, device="cpu"), dict(seconds=60, takes=1, device="mps"),
                                 dict(seconds=60, takes=1, device="cpu", guitar="tpu")])
def test_nonsense_is_refused(bad):
    with pytest.raises(ValueError):
        E.chart_seconds(**bad)


@pytest.mark.parametrize("low_s, high_s, minutes", [
    (246.28, 588.52, (4, 10)),     # down and up to whole minutes
    (240.0, 600.0, (4, 10)),       # exact minutes stay
    (10.0, 20.0, (1, 2)),          # at least a minute, and a range
    (61.0, 62.0, (1, 2)),
    (1000.0, 1790.0, (16, 30)),
    (1000.0, 1801.0, (16, 35)),    # from 30 minutes on, to 5
    (1900.0, 2500.0, (30, 45)),
    (3000.0, 3000.0, (50, 50 + 1)),
])
def test_the_minutes_never_narrow_the_range(low_s, high_s, minutes):
    low, high = E.round_minutes(low_s, high_s)
    assert (low, high) == minutes
    assert low * 60 <= max(low_s, 60) and high * 60 >= high_s and high > low


def options(**kw):
    return J.parse_options(kw)


def test_a_jobs_device_and_takes():
    d = 241.0
    est = E.for_job(d, options(), "cuda", "cuda")   # "auto" on a GPU: 4 takes there
    assert {k: est[k] for k in ("seconds", "takes", "device")} == {"seconds": d, "takes": 4, "device": "cuda"}
    assert (est["low_s"], est["high_s"]) == tuple(round(x, 1) for x in E.chart_seconds(d, 4, "cuda"))
    assert (est["low_min"], est["high_min"]) == E.round_minutes(*E.chart_seconds(d, 4, "cuda"))
    assert est == E.for_job(d, options(), "cuda", None)   # a guitar not checked counts as on the GPU
    # the doctor found the guitar on the CPU: one take there, the other stages on the GPU
    est = E.for_job(d, options(), "cuda", "cpu")
    assert (est["takes"], est["device"]) == (1, "cpu")
    assert est["low_s"] == round(E.chart_seconds(d, 1, "cuda", "cpu")[0], 1)
    assert E.for_job(d, options(), "cpu", "cpu")["takes"] == 1
    assert E.for_job(d, options(takes=3), "cpu", "cpu")["takes"] == 3   # asked for, on any device
    assert E.for_job(d, options(device="cpu"), "cuda", "cuda")["device"] == "cpu"   # the options' device first
    assert E.for_job(d, options(device="cuda"), "cpu", "cpu")["takes"] == 1   # CUDA asked for, the guitar on the CPU
    assert E.for_job(d, options(device="cuda"), None, None)["takes"] == 4
    est = E.for_job(d, options(instruments=["drums", "bass"]), "cuda", "cuda")
    assert est["takes"] == 0 and est["low_s"] == round(E.chart_seconds(d, 0, "cuda")[0], 1)
    est = E.for_job(d, options(preview=False, lyrics="a line\n"), "cpu", "cpu")
    assert est["high_s"] == round(E.chart_seconds(d, 1, "cpu", lyrics=True, preview=False)[1], 1)


@pytest.mark.parametrize("seconds, auto", [(None, "cuda"), (0, "cuda"), (-3.0, "cuda"), (True, "cuda"),
                                           ("241", "cuda"), (float("nan"), "cuda"), (float("inf"), "cuda"),
                                           (241.0, None)])
def test_no_estimate_without_a_length_or_a_device(seconds, auto):
    assert E.for_job(seconds, options(), auto, "cuda") is None


def test_the_length_from_ffmpegs_header(tmp_path):
    t = np.arange(int(2.5 * A.SAMPLE_RATE)) / A.SAMPLE_RATE
    y = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    A.write_wav(np.stack([y, y]), tmp_path / "s.wav")
    assert E.duration(tmp_path / "s.wav") == pytest.approx(2.5, abs=0.02)
    (tmp_path / "x.mp3").write_bytes(b"not audio at all")
    assert E.duration(tmp_path / "x.mp3") is None
    assert E.duration(tmp_path / "missing.wav") is None
    assert E.duration(tmp_path / "s.wav", ffmpeg=str(tmp_path / "no-ffmpeg")) is None   # no ffmpeg: no estimate


def test_an_ffmpeg_that_hangs_gives_no_length_within_the_timeout(tmp_path, monkeypatch):
    """M7-10's review (F2): an ffmpeg that never answers would hold the upload, and "Chart it", for good: the probe
    gives up after PROBE_TIMEOUT_S and the song has no estimate."""
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\nexec sleep 100\n", encoding="utf-8")
    fake.chmod(0o755)
    assert 5 <= E.PROBE_TIMEOUT_S <= 60   # long enough for a slow disk, short enough to wait for
    monkeypatch.setattr(E, "PROBE_TIMEOUT_S", 0.5)
    began = time.monotonic()
    assert E.duration(tmp_path / "song.mp3", ffmpeg=str(fake)) is None
    assert time.monotonic() - began < 5


@pytest.mark.parametrize("said, seconds", [
    ("Input #0, mp3, from 'x.mp3':\n  Duration: 01:02:03.45, start: 0.025057, bitrate: 320 kb/s", 3723.45),
    ("  Duration: 00:04:01.00, bitrate: 1411 kb/s\nAt least one output file must be specified", 241.0),
    ("  Duration: 00:00:00.00, bitrate: N/A", None),
    ("  Duration: N/A, bitrate: N/A", None),
    ("nothing about a length", None),
])
def test_the_header_line_is_read_whatever_comes_around_it(tmp_path, said, seconds):
    """ffmpeg's answer as a stand-in ffmpeg prints it (on stderr, exit 1: no output named)."""
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\ncat >&2 <<'EOF'\n" + said + "\nEOF\nexit 1\n", encoding="utf-8")
    fake.chmod(0o755)
    got = E.duration(tmp_path / "song.mp3", ffmpeg=str(fake))
    assert got == (pytest.approx(seconds) if seconds is not None else None)


# ------------------------------------------------------------------------------------------------ the measured runs

LENGTH = {"atst": 175.2, "creep": 240.0, "dd": 225.0, "kw": 288.2, "luc": 239.9, "tmo": 241.0, "test": 412.4}
# the guitar stage in seconds: 4 and 1 GPU takes (the takes experiment's table, RTX 5070), and the owner's four songs;
# Kimochi Warui's 4 takes are above the 5070's own range and inside the 4070's
GPU4 = {"dd": 170, "tmo": 304, "atst": 197, "creep": 185, "test": 839, 187: 150, 221: 254, 545: 2173}
GPU4_DENSE = {"kw": 886, "luc": 833, 439: 3383}
GPU1 = {"dd": 74, "tmo": 96, "atst": 59, "creep": 66, "test": 264, "kw": 202}
GPU1_DENSE = {"luc": 240}
# 1 CPU take: the golden runs' cold builds (two of each song), autochart's own separation included
CPU1 = [("kw", 393.1), ("dd", 206.1), ("atst", 170.7), ("creep", 221.3), ("test", 528.6), ("kw", 365.1),
        ("dd", 174.8), ("tmo", 218.6), ("atst", 151.1), ("creep", 176.0), ("test", 432.0)]
CPU1_ABOVE = [("tmo", 327.5), ("luc", 452.7), ("luc", 385.4)]


def guitar(song, takes, device):
    d = LENGTH.get(song, song)
    without, with_ = E.chart_seconds(d, 0, device), E.chart_seconds(d, takes, device)
    return with_[0] - without[0], with_[1] - without[1]


@pytest.fixture
def the_5070(monkeypatch):
    """The GPU's high rates as the 5070 measured them, without the 4070's margin."""
    m = E.FRIEND_GPU
    monkeypatch.setitem(E.GUITAR_TAKE, "cuda", (E.GUITAR_TAKE["cuda"][0], E.GUITAR_TAKE["cuda"][1] / m))
    monkeypatch.setitem(E.GUITAR_ONCE, "cuda", (E.GUITAR_ONCE["cuda"][0], E.GUITAR_ONCE["cuda"][1] / m))
    monkeypatch.setitem(E.OTHER, "cuda", (E.OTHER["cuda"][0], (E.OTHER["cuda"][1][0], E.OTHER["cuda"][1][1] / m)))


@pytest.mark.parametrize("measured, takes, device, inside, rates", [
    (GPU4, 4, "cuda", True, "5070"), (GPU4_DENSE, 4, "cuda", False, "5070"),
    (GPU1, 1, "cuda", True, "5070"), (GPU1_DENSE, 1, "cuda", False, "5070"),
    ({**GPU4, "kw": 886}, 4, "cuda", True, "4070"), ({"luc": 833, 439: 3383}, 4, "cuda", False, "4070"),
    (GPU1, 1, "cuda", True, "4070"), (GPU1_DENSE, 1, "cuda", False, "4070"),
    (dict(enumerate(CPU1)), 1, "cpu", True, "cpu"), (dict(enumerate(CPU1_ABOVE)), 1, "cpu", False, "cpu")])
def test_the_ordinary_songs_fall_inside_the_range_and_the_dense_ones_above(request, measured, takes, device, inside,
                                                                           rates):
    if rates == "5070":
        request.getfixturevalue("the_5070")
    for key, seconds in measured.items():
        song = key
        if isinstance(seconds, tuple):
            song, seconds = seconds
        low, high = guitar(song, takes, device)
        assert (low <= seconds <= high) if inside else seconds > high, (song, seconds, round(low), round(high))


@pytest.mark.parametrize("minutes, song, takes, device, preview", [
    (5.05, "test", 1, "cuda", True),    # M4-08 A6, through the real install on the 5070
    (12.7, "test", 1, "cpu", False),    # M3 on this CPU, before the preview
    (6.8, "tmo", 1, "cpu", False),
])
def test_whole_charts_fall_inside_the_range(minutes, song, takes, device, preview):
    low, high = E.chart_seconds(LENGTH[song], takes, device, preview=preview)
    assert low <= minutes * 60 <= high
    lo_min, hi_min = E.round_minutes(low, high)
    assert lo_min <= minutes <= hi_min and math.isfinite(hi_min)


def test_the_page_and_the_pipeline_agree_on_the_default_takes():
    from songcharter import pipeline
    assert E.CUDA_TAKES == pipeline.CUDA_TAKES
    assert pipeline.guitar_takes(None, "cuda")[0] == E.for_job(60.0, options(), "cuda", "cuda")["takes"]
    assert pipeline.guitar_takes(None, "cpu")[0] == E.for_job(60.0, options(), "cpu", "cpu")["takes"]
