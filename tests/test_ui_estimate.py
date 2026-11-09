"""The progress screen's time estimate (songcharter.ui.estimate, M7-10): its arithmetic, its rounding, the device and
the takes it assumes for a job, the song's length from ffmpeg's header, and its rates against the measured runs they
come from (the module docstring): the ordinary songs inside the range, the dense ones above it."""
import math
import subprocess
import time

import numpy as np
import pytest

from songcharter import audio as A
from songcharter.ui import estimate as E
from songcharter.ui import jobs as J


def test_the_arithmetic_on_a_four_minute_song():
    """240 s, 4 takes on the GPU, with the preview: every part's low and high values summed, by hand; the GPU's high
    rates the 5070's times 1.35 (the friend's 4070, M7-10's review), each take's own start 0 to 10 s."""
    low = (20 + 0.15 * 240) + (5 + 0.01 * 240) + 0.07 * 240 + 4 * (0 + 0.0007 * 240 ** 2)
    high = (20 + 0.40 * 1.35 * 240) + (5 + 0.05 * 240) + 0.19 * 1.35 * 240 + 4 * (10 + 0.0018 * 1.35 * 240 ** 2)
    assert E.chart_seconds(240, 4, "cuda") == pytest.approx((low, high))
    assert (round(low, 2), round(high, 2)) == (241.48, 828.03)   # (246.28, 821.55) before the v0.4.0 gate
    assert E.round_minutes(low, high) == (4, 14)   # the page's "4 to 14 minutes"
    assert E.round_minutes(*E.chart_seconds(240, 1, "cuda")) == (2, 7)


def test_the_gpus_high_rates_are_the_5070s_with_the_4070s_margin():
    assert E.FRIEND_GPU == 1.35 and E.TAKE_FIXED == (0.0, 10.0)
    assert E.GUITAR_TAKE["cuda"] == pytest.approx((0.0007, 0.0018 * 1.35))
    assert E.GUITAR_ONCE["cuda"] == pytest.approx((0.07, 0.19 * 1.35))
    assert E.OTHER["cuda"] == ((20.0, 20.0), pytest.approx((0.15, 0.40 * 1.35)))
    assert E.GUITAR_TAKE["cpu"] == (0.0012, 0.0033) and E.OTHER["cpu"] == ((10.0, 10.0), (0.81, 1.13))


def test_each_part_counts_once_and_where_it_runs():
    d = 300.0
    base = E.chart_seconds(d, 0, "cpu", preview=False)
    assert base == pytest.approx((10 + 0.81 * d, 10 + 1.13 * d))   # no guitar: the other stages alone
    preview = E.chart_seconds(d, 0, "cpu")
    assert [b - a for a, b in zip(base, preview)] == pytest.approx([5 + 0.01 * d, 5 + 0.05 * d])
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
    # "auto" on a GPU: 1 take there too, the owner's decision of 2026-11-09 (break: the default back to 4)
    est = E.for_job(d, options(), "cuda", "cuda")
    assert {k: est[k] for k in ("seconds", "takes", "device")} == {"seconds": d, "takes": 1, "device": "cuda"}
    assert (est["low_s"], est["high_s"]) == tuple(round(x, 1) for x in E.chart_seconds(d, 1, "cuda"))
    assert (est["low_min"], est["high_min"]) == E.round_minutes(*E.chart_seconds(d, 1, "cuda")) == (2, 7)
    best = E.for_job(d, options(takes=E.BEST_TAKES), "cuda", "cuda")   # "Best chart"
    assert (best["takes"], best["low_min"], best["high_min"]) == (4, 4, 14)
    assert est == E.for_job(d, options(), "cuda", None)   # a guitar not checked counts as on the GPU
    # the doctor found the guitar on the CPU: one take there, the other stages on the GPU
    est = E.for_job(d, options(), "cuda", "cpu")
    assert (est["takes"], est["device"]) == (1, "cpu")
    assert est["low_s"] == round(E.chart_seconds(d, 1, "cuda", "cpu")[0], 1)
    assert E.for_job(d, options(), "cpu", "cpu")["takes"] == 1
    assert E.for_job(d, options(takes=3), "cpu", "cpu")["takes"] == 3   # asked for, on any device
    assert E.for_job(d, options(device="cpu"), "cuda", "cuda")["device"] == "cpu"   # the options' device first
    assert E.for_job(d, options(device="cuda"), "cpu", "cpu")["takes"] == 1   # CUDA asked for, the guitar on the CPU
    assert E.for_job(d, options(device="cuda"), None, None)["takes"] == 1
    est = E.for_job(d, options(instruments=["drums", "bass"]), "cuda", "cuda")
    assert est["takes"] == 0 and est["low_s"] == round(E.chart_seconds(d, 0, "cuda")[0], 1)
    est = E.for_job(d, options(preview=False, lyrics="a line\n"), "cpu", "cpu")
    assert est["high_s"] == round(E.chart_seconds(d, 1, "cpu", lyrics=True, preview=False)[1], 1)
    assert est["audio"] == "split" and E.for_job(d, options(one_audio=True), "cpu", "cpu")["audio"] == "one"


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


@pytest.mark.parametrize("ext", ["mp3", "wav", "flac", "m4a"])
def test_a_tag_that_holds_a_duration_is_not_the_songs_length(tmp_path, ext):
    """The v0.4.0 gate's review: ffmpeg prints the input's tags before the container's own Duration line, and a
    downloaded song's tag (a description, a comment) can hold "Duration: 1:00:00": a 2.5-s song is still 2.5 s, not
    an hour (the page said "about 620 to 2150 minutes")."""
    t = np.arange(int(2.5 * A.SAMPLE_RATE)) / A.SAMPLE_RATE
    y = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    A.write_wav(np.stack([y, y]), tmp_path / "s.wav")
    song = tmp_path / f"tagged.{ext}"
    subprocess.run([A.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i",
                    str(tmp_path / "s.wav"), "-metadata", "comment=Duration: 01:00:00.00", str(song)], check=True)
    said = subprocess.run([A.ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", str(song)], capture_output=True)
    assert "Duration: 01:00:00.00" in said.stderr.decode("utf-8", "replace")   # the tag is there to be misread
    assert E.duration(song) == pytest.approx(2.5, abs=0.1)


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
    # ffmpeg's own layout (n9.0.2): the tags first, then the container's line; a tag's text is never the length,
    # whether in its value, a value's later line, or its key (an ID3 TXXX frame's description is the key)
    ("Input #0, mp3, from 'song.mp3':\n  Metadata:\n    comment         : Duration: 01:00:00.00\n"
     "    encoder         : Lavf63.1.102\n  Duration: 00:00:12.50, start: 0.025057, bitrate: 64 kb/s\n"
     "  Stream #0:0: Audio: mp3 (mp3float), 44100 Hz, mono, fltp, 64 kb/s, start 0.025057", 12.5),
    ("Input #0, mp3, from 'song.mp3':\n  Metadata:\n    comment         : a first line\n"
     "                    : Duration: 01:00:00.00, start: 0.0, bitrate: 1 kb/s\n"
     "  Duration: 00:03:05.00, start: 0.025057, bitrate: 192 kb/s", 185.0),
    ("Input #0, mp3, from 'song.mp3':\n  Metadata:\n    Duration: 01:00:00.00: x\n"
     "  Duration: 00:03:05.00, start: 0.025057, bitrate: 192 kb/s", 185.0),
    ("Input #0, mp3, from 'song.mp3':\n  Metadata:\n    comment         : Duration: 01:00:00.00\n"
     "  Duration: N/A, bitrate: N/A", None),
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


# the first take's own separation and timing on the 5070: its time less the mean of the three later takes (the
# takes experiment's table), on the five ordinary songs; and the preview, on the 5070's PC and on this CPU
ONCE = {"dd": 74 - (33 + 34 + 29) / 3, "tmo": 96 - (76 + 69 + 63) / 3, "atst": 59 - (42 + 49 + 47) / 3,
        "creep": 66 - (35 + 37 + 47) / 3, "test": 264 - (224 + 164 + 187) / 3}
PREVIEW_S = {"test": 11.0, 240.0: 12.0}


def test_the_first_takes_own_part_and_the_preview_fall_inside_their_ranges(the_5070):
    """Each part's range is where its measured runs fell (the module docstring; the v0.4.0 gate's review: Drunk
    Drivers' 0.19 s a second and All the Small Things' 0.07 were outside 0.08-0.17, the test song's 11-s preview
    under its 13-s low end)."""
    for song, seconds in ONCE.items():
        low, high = (rate * LENGTH[song] for rate in E.GUITAR_ONCE["cuda"])
        assert low <= seconds <= high, (song, round(seconds, 1), round(low, 1), round(high, 1))
    for song, seconds in PREVIEW_S.items():
        d = LENGTH.get(song, song)
        low, high = (fixed + rate * d for fixed, rate in zip(*E.PREVIEW))
        assert low <= seconds <= high, (song, seconds, round(low, 1), round(high, 1))


# the build (assemble and its checks) on this CPU, every level (the golden runs' builds; s, the song's length):
# split audio, the default since M8-12, at v0.5.0's candidate; one song.ogg, at the golden set's kept builds before
# M8-12 [here, each run's pipeline.json stage times]; and M8-12's creep, Expert only: 35.1 s split, 17.1 s one file
BUILD_SPLIT = {"atst": 25.76, "creep": 33.06, "dd": 33.79, "kw": 38.9, "luc": 32.8, "tmo": 34.36, "test": 59.8}
BUILD_ONE = {"atst": 10.5, "creep": 15.51, "dd": 13.3, "kw": 18.72, "luc": 14.86, "tmo": 16.14, "test": 29.63}


def test_the_builds_fall_inside_their_range_split_or_one_file():
    """The v0.5.0 review's docs-assemble-estimate-split: the build's rates are split builds' since M8-12 made the split
    audio the default (it about doubled the build), and one-file builds' for "One audio file"; each measured build
    falls inside its range (break: the split builds against the one-file rates: creep's 35.1 s over 24.2 s)."""
    def inside(rates, d, seconds):
        low, high = (fixed + rate * d for fixed, rate in zip(*rates))
        return low <= seconds <= high
    for song, seconds in BUILD_SPLIT.items():
        assert inside(E.ASSEMBLE, LENGTH[song], seconds), (song, seconds)
    for song, seconds in BUILD_ONE.items():
        assert inside(E.ASSEMBLE_ONE, LENGTH[song], seconds), (song, seconds)
    assert inside(E.ASSEMBLE, 240.0, 35.1) and inside(E.ASSEMBLE_ONE, 240.0, 17.1)   # M8-12's creep
    assert inside(E.ASSEMBLE_ONE, LENGTH["test"], 16.0) and inside(E.ASSEMBLE_ONE, LENGTH["test"], 17.2)   # the 5070
    assert inside(E.STEMS, 240.0, 4.3)   # M8-12's creep: "Save the stems"


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


# ------------------------------------------------------------------------------------------------ the time left (M8-04)

PLAN = {"event": "plan", "stages": ["decode", "separate", "drums", "bass", "sections", "guitar", "assemble", "preview"]}


def takes_at(times, start=1000.0, count=None, first=1):
    """The take events of takes timed `times` (s), from `start`: each event as the take starts (pipeline.run_take)."""
    count = count or len(times) + first - 1
    out, at = [], start
    for i, t in enumerate(times):
        out.append({"event": "take", "index": first + i, "count": count, "seed": 101 * (first + i), "at": at})
        at += t
    return out


def test_the_time_left_from_the_test_songs_first_take():
    """The test song's 4 takes on the 5070 (264, 224, 164 and 187 s: the takes experiment's table). At take 2's start
    (its event's `at` less take 1's: 264 s), by hand: the first take's own part at its high rate is 0.19 * 1.35 =
    0.2565 s a second, 105.78 s on 412.4 s, so a take left costs 264 - 105.78 = 158.22 s at the low end and 264 s at
    the high end (nothing off: the events do not say whether take 1's part was cached, M8-04's review F3); the split
    build 0.5 + 0.05 * 412.4 = 21.12 to 5 + 0.16 * 412.4 = 70.98 s, the preview 5 + 0.01 * 412.4 = 9.12 to 5 + 0.05 *
    412.4 = 25.62 s; with 3 takes left, 3 * 158.22 + 30.24 = 504.9 to 3 * 264 + 96.6 = 888.6 s, about 8 to 15
    minutes, from take 2's `at`. They took 224 + 164 + 187 s and the build and preview 16 + 11 s: 602 s, inside, and
    so is about 618 s with a split build, about twice the one-file build's 16 s (M8-12) [est.]. With one song.ogg,
    the build at 0.5 + 0.025 * 412.4 = 10.81 to 5 + 0.08 * 412.4 = 37.99 s; with the stems saved, 4.62 to 18.5 s
    more."""
    est = {"seconds": 412.4, "takes": 4, "device": "cuda"}
    events = [PLAN] + takes_at([264, 224, 164, 187])
    assert E.remaining(est, events[:2]) is None   # one take started: nothing timed yet
    left = E.remaining(est, events[:3])
    assert left == {"from": 1264.0, "low_s": 504.9, "high_s": 888.6, "low_min": 8, "high_min": 15, "takes_left": 3,
                    "first_s": 264.0, "take_s": [158.2, 264.0]}
    assert left["low_s"] <= 224 + 164 + 187 + 16 + 11 <= left["high_s"]
    assert left["low_s"] <= 224 + 164 + 187 + 2 * 16 + 11 <= left["high_s"]
    assert E.remaining({**est, "audio": "split"}, events) == E.remaining(est, events) == left   # once, at take 2
    no_preview = {**PLAN, "stages": PLAN["stages"][:-1]}
    assert E.remaining(est, [no_preview] + events[1:3])["low_s"] == pytest.approx(3 * 158.22 + 21.12, abs=0.1)
    one = E.remaining({**est, "audio": "one"}, events[:3])
    assert (one["low_s"], one["high_s"]) == pytest.approx((3 * 158.22 + 10.81 + 9.12, 3 * 264 + 37.99 + 25.62),
                                                          abs=0.1)
    stems = {**PLAN, "stages": [*PLAN["stages"][:-1], "stems", "preview"]}   # the plan with "Save the stems"
    with_stems = E.remaining(est, [stems] + events[1:3])
    assert (with_stems["low_s"], with_stems["high_s"]) == pytest.approx((504.9 + 4.62, 888.6 + 18.5), abs=0.1)


def test_the_time_left_from_the_905_songs_first_take():
    """The owner's 9:05 song (545 s): its 4 takes took 2173 s on the 5070, its single takes not kept, so they are split
    here with the five ordinary songs' mean first-take part, 0.13 s a second (70.85 s): later takes 525.54 s each, the
    first 596.39 s. By hand at take 2's start: its own part at the high rate 0.2565 * 545 = 139.79 s, so a take left
    596.39 - 139.79 = 456.60 s at the low end and 596.39 s at the high end; the split build 27.75 to 92.20 s, the
    preview 10.45 to 32.25 s; with 3 left, 1408.0 to 1913.6 s: 23 to 35 minutes (32 up to the next 5). The three
    later takes (1576.6 s) and a build fall inside."""
    once = 0.13 * 545
    later = (2173 - once) / 4
    first = later + once
    est = {"seconds": 545.0, "takes": 4, "device": "cuda"}
    left = E.remaining(est, [PLAN] + takes_at([first, later, later, later], start=0.0))
    assert left == {"from": round(first, 4), "low_s": 1408.0, "high_s": 1913.6, "low_min": 23, "high_min": 35,
                    "takes_left": 3, "first_s": 596.4, "take_s": [456.6, 596.4]}
    assert left["low_s"] <= 3 * later + 27.75 + 10.45 and 3 * later + 92.2 + 32.25 <= left["high_s"]


def test_the_time_left_when_take_1_found_its_separation_cached():
    """M8-04's review, F3: a song charted again after a cancel runs take 1 with autochart's separation and timing
    from its cache, as fast as a later take, and the events do not say so; the high end then takes nothing off. The
    9:05 song with take 1 at a later take's 525.54 s: 3 * (525.54 - 139.79) + 38.2 = 1195.4 to 3 * 525.54 + 124.45 =
    1701.1 s, against 1576.6 s of takes and a build and preview of about 60 s (about 1636 s); taking the part off the
    high end too gave 1542.9 with the one-file build's rates, below it. The test song with take 1 at 210.4 s:
    3 * (210.4 - 105.78) + 30.24 = 344.1 to 3 * 210.4 + 96.6 = 727.8 s, against the 602 s left."""
    later = (2173 - 0.13 * 545) / 4
    nine = E.remaining({"seconds": 545.0, "takes": 4, "device": "cuda"},
                       [PLAN] + takes_at([later, later, later, later], start=0.0))
    assert (nine["low_s"], nine["high_s"], nine["take_s"]) == (1195.4, 1701.1, [385.7, 525.5])
    assert nine["low_s"] <= 3 * later + 60 <= nine["high_s"]
    test = E.remaining({"seconds": 412.4, "takes": 4, "device": "cuda"}, [PLAN] + takes_at([210.4, 224, 164, 187]))
    assert (test["low_s"], test["high_s"]) == (344.1, 727.8) and test["low_s"] <= 602 <= test["high_s"]


def test_the_time_left_after_the_guitar_and_when_it_cannot_say():
    """A 1-take chart has only the guitar's stage_end: then the stages after it alone (the test song: 30.2 to 96.6 s,
    about 1 to 2 minutes). A first take the cache answered (take 2's event first) is a later take, with nothing taken
    off. None without an estimate or a guitar, and once a take was run again on the CPU after its GPU run failed."""
    est = {"seconds": 412.4, "takes": 1, "device": "cpu"}
    events = [PLAN] + takes_at([500]) + [{"event": "stage_end", "stage": "guitar", "seconds": 500.0, "cached": False,
                                          "at": 1500.0}]
    assert E.remaining(est, events[:2]) is None
    after = {"from": 1500.0, "low_s": 30.2, "high_s": 96.6, "low_min": 1, "high_min": 2, "takes_left": 0,
             "first_s": None, "take_s": None}
    assert E.remaining(est, events) == after
    # a 4-take chart too: once the guitar ends, the stages after it alone, not take 2's count (M8-04's review, F1)
    four = [PLAN] + takes_at([264, 224, 164, 187], start=500.0) + [
        {"event": "stage_end", "stage": "guitar", "seconds": 839.0, "cached": False, "at": 1339.0}]
    assert E.remaining({"seconds": 412.4, "takes": 4, "device": "cuda"}, four) == {**after, "from": 1339.0}
    gpu = {"seconds": 412.4, "takes": 4, "device": "cuda"}
    cached = E.remaining(gpu, [PLAN] + takes_at([200, 190], first=2, count=4))   # take 1 from the cache
    assert cached["take_s"] == [200.0, 200.0] and cached["takes_left"] == 2
    assert cached["low_s"] == pytest.approx(400 + 30.24, abs=0.1) and cached["high_s"] == pytest.approx(496.6, abs=0.1)
    retried = [PLAN] + takes_at([264]) + [{"event": "take", "index": 1, "count": 4, "seed": 101, "device": "cpu",
                                           "at": 1100.0}, {"event": "take", "index": 2, "count": 4, "at": 1500.0}]
    assert E.remaining(gpu, retried) is None
    for bad in (None, {}, {**gpu, "takes": 0}, {**gpu, "seconds": None}, {**gpu, "seconds": float("inf")},
                {**gpu, "device": "tpu"}):
        assert E.remaining(bad, [PLAN] + takes_at([264, 224])) is None, bad
    assert E.remaining(gpu, None) is None
    assert E.remaining(gpu, [PLAN, {"event": "take", "index": 1, "count": 4, "at": 1000.0},
                             {"event": "take", "index": 2, "count": 4}]) is None   # no clock
