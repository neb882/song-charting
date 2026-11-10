"""How long a chart usually takes (M7-10, DESIGN.md 4.5): the progress screen's "Usually about N to M minutes".

    seconds = duration(path)                                       # the song's length from ffmpeg's header, or None
    est = for_job(seconds, options, auto_device, guitar_device)    # {"low_min", "high_min", ...}, or None
    low_s, high_s = chart_seconds(seconds, takes=1, device="cuda")
    left = remaining(est, job_events)   # M8-04: the time left once the first take is timed, or None

**The model** (`chart_seconds`): every stage but the guitar costs a fixed part and a rate per second of the song
(`OTHER`, `PREVIEW`, `LYRICS`); the guitar costs, once a chart, its first take's own separation and timing (a rate
per second, `GUITAR_ONCE`), then for each take a transcription that grows with the square of the song's length
(`GUITAR_TAKE`'s k times d squared, d the length in seconds), after its own start (`TAKE_FIXED`: 0 to 10 s a take,
the high end for short songs). The transcriber writes its notes one at a time, each costing more the more it has
written, so a song twice as long costs about four times as much a take, or more: the test song (6:52) against Creep
(4:00), at about the same notes a second (3.1 against 2.9 from their first takes), took 4.8x the time a later take
(192 s against 40 s, the mean of three), 4.0x the first take (264 s against 66 s) and 4.5x for all four (839 s
against 185 s), for 1.7x the length, whose square is 2.9 [here, the takes experiment's table]. That pair grows faster
than the square, which k's range takes up; the five ordinary songs of the experiment grow about as the square (their
later takes fit d to the 1.9th), and d to the 2.4th with the owner's three ordinary songs, his 9:05 song the steepest
(below). Each rate has a low and a high value, from the measured runs below, and the range is where the ordinary
songs fell; **the GPU's high rates are the 5070's times `FRIEND_GPU` (1.35)** for the friend's 4070, until M4-08 part
B times his PC. **A dense song** (many notes a second) can take longer than the high end, as the guitar's time grows
with the notes it writes, and on the 4070 **a song much longer than 9 minutes** may too: the 9:05 song's 4 takes
(2173 s on the 5070) are 95 % of the guitar's high end at the 5070's own rates and 71 % of the page's; along d to the
2.4th the page's high end holds on the 5070 to 20 minutes, but a 4070 1.35x as slow passes it from about 10 minutes
(1.2x as slow: about 14) [inference, the v0.4.0 gate]. The caches are not counted: a song charted before goes faster.

**The evidence** (k as above; "ordinary": inside the range):
  * **The GPU** (the owner's RTX 5070; the friend's RTX 4070 is not measured):
      - the guitar, 4 takes: the takes experiment's seven songs (docs/reports/takes-experiment.md, 170-886 s) and the
        owner's job logs of four songs (150 s for a 3:07 song, 254 s for 3:41, 2173 s for 9:05, 3383 s for 7:19): k
        0.00067-0.0018 on the eight ordinary ones; 0.0026-0.0043 on Kimochi Warui, Lucretia and the owner's 7:19
        song, all three dense. With the 5070's rates, the eight inside the range and the three above it; with the
        4070's (times 1.35), Kimochi Warui inside too. 1 take: 6 of the 7 songs inside, Lucretia above. The first
        take's own separation and timing, its time less the mean of the later three, on the five ordinary songs:
        13-72 s, 0.07-0.19 s a second (All the Small Things 0.074, Drunk Drivers 0.187; Lucretia's 0.176 inside too,
        Kimochi Warui's negative, its later takes the slower).
      - each take's own start: the 5070's later takes grow as the square of their notes with no fixed part to within
        a few seconds (Drunk Drivers' 611 Expert onsets 29-34 s a take, Take Me Out's 872 63-76 s: 2.2x the time for
        2.0x the notes squared), but no song under 3 minutes was measured, and each take starts a node process and
        loads its models: 0 to 10 s a take [est.], which only a short song notices.
      - the 4070: about 4 % fewer CUDA cores than the 5070 and 25 % less memory bandwidth (504 against 672 GB/s; the
        public specifications), reviewed about 20-25 % slower; the transcriber writes one token at a time, which the
        memory bandwidth bounds, so its GPU stages may take 1.1-1.35x as long [inference, M7-10's review].
      - the rest: the test song with 1 take through the real install (docs/work-orders/M4-08-results.md, A6): decode
        1 s, separation 9, drums 4, bass 18, sections 40, build 16, preview 11; the owner's later runs: separation
        14 s, sections 72 s.
  * **The CPU** (the dev container: 4 shared vCPUs, 2 threads; a desktop's own CPU is likely faster):
      - the guitar, 1 take: the golden runs' cold builds of the seven songs, two of each (151-529 s), autochart's own
        separation included (about 187 s of the test song's first take: 404 s, against 217 s for its second): k
        0.0013-0.0033 on 11 of the 14 builds; Take Me Out's slower build 0.0039, Lucretia's two 0.0049-0.0061 (dense).
      - the rest: the same builds' decode, drums, bass, sections and assemble (0.46-0.68 s a second), and the
        separation, which those builds took from a cache: 169 s for the test song on 2 threads, 143 s on 3.
  * **Lyrics** (only with pasted words): 105-134 s for a 4-minute song on 2 threads of the CPU, and 9 s to load the
    weights (DESIGN.md 2.15); on the GPU unmeasured, taken as a fifth to a half of the CPU's [est.]. The first song
    with lyrics also downloads 1.26 GB, which is not counted.
  * **The preview**: 11 s for the test song on the 5070's PC, 12 s for a 4-minute song here (the range: 9.1-25.6 s
    and 7.4-17 s).
Against whole charts: the test song with 1 take on the 5070 took 5.05 min (the range: 4.0-13.3), on this CPU 12.7
min (11.5-20.9, no preview then); Take Me Out with 1 take on this CPU 6.8 min (6.0-10.1). A 4-minute song: 2 to 7
minutes with the GPU's default of 1 take, 4 to 14 with "Best chart"'s 4, 6 to 11 on the CPU; a 9-minute song 5 to 21,
16 to 60, 16 to 35.

**The time left** (`remaining`, M8-04, the v0.4.0 gate's note: a dense song's guitar can pass the high end, so the
page says how long is left once the guitar's first take is timed). The pipeline's `take` event comes as each take
starts, with no seconds; jobs.py stamps every event with `at`, the server's clock, so a take's time is `at` of the next
take's event less its own (the v0.4.0 advisor's finding 5). From the second take's start: the takes left (this one
and those after it) at that first take's time less its own separation and timing at the low end (`GUITAR_ONCE`'s
high rate times d), and at that first take's time itself at the high end: the events do not say whether autochart's
cache already held take 1's separation and timing (a song charted again after a cancel, as the page's "gone" text
suggests, runs take 1 about as fast as a later take), and taking them off a take that did not run them put the range
too low (M8-04's review, F3: on the 9:05 song 1182-1543 s against about 1636 s left). Nothing is taken off when the
first take that ran was not take 1 (the cache answered take 1, and the beat map with it). Plus the stages after the
guitar the plan has: the build (`ASSEMBLE`, or `ASSEMBLE_ONE` for one song.ogg: the estimate's `audio`), "Save the
stems" (`STEMS`) and the preview (`PREVIEW`). After the guitar's `stage_end` (a 1-take chart has only that) the stages
after it alone. It is worked out once, at that event (`from`), and the page counts it down. **The evidence:** the takes
experiment's later takes against the first on the 5070 (above: the five ordinary songs' first takes 13-72 s longer
than the mean of their later three, inside the rate's range; Kimochi Warui's later takes slower than its first, which
the high end does not cover), so the test song's 4 takes (264, 224, 164 and 187 s) give, at take 2's start, 158-264 s
a take for the three left, 505-889 s with the split build and the preview, against the 602 s they took with a
one-file build (about 618 s with a split one, twice the build [est.]) [here, tests/test_ui_estimate.py]; the owner's
9:05 song's 4 takes (2173 s; its single takes were not kept) split with the mean first-take part (0.13 s a second)
give 1408-1914 s against its 1577 s of later takes and its build. **The build** (assemble and its checks, either
device: the CPU's work, encodes and decodes):
  * **split audio** (the default since M8-12: three more Vorbis encodes, and the four files decoded back for the
    gate's sync check), `ASSEMBLE`: on this CPU, the golden runs at v0.5.0's candidate (every level) 25.8 s for All the
    Small Things (2:55) to 59.8 s for the test song (6:52), 0.135-0.150 s a second over the seven songs, and creep
    (4:00) 35.1 s in M8-12 (Expert only) [here, each run's pipeline.json]: 0.5-5 s and 0.05-0.16 s a second, the low
    end for a desktop CPU up to about 2.7 times as fast (the 5070's PC built the test song's one file in 16 s, this
    CPU in 29.6 s).
  * **one song.ogg** ("One audio file"), `ASSEMBLE_ONE`: 16 s and 17.2 s for the test song (the 5070's PC; the
    release gate's run), 19.3 s for Take Me Out on this CPU, the golden set's kept builds before M8-12 10.5-29.6 s
    (0.060-0.072 s a second), creep 17.1 s in M8-12, about 1 s for CI's 20-s clip: 0.5-5 s and 0.025-0.08 s a second.
  * **"Save the stems"** (`STEMS`): creep's 4.3 s for 188 MB of FLAC in M8-12, on this CPU; 0.5-2 s and 0.01-0.04 s a
    second around it [est.].
The whole chart's `OTHER` already holds the split build: on this CPU the seven songs' decode, drums, bass, sections
and split build came to 0.52-0.57 s a second, inside the 0.46-0.68 above, and the test song's build on the 5070
doubled from 16 s keeps its 1-take chart inside the range (5.3 against 4.0-13.3 minutes) [here]. None when a take
was run again on the CPU after its GPU run failed (the event's `device`): that take's time is no longer the model's.

`duration` reads the length ffmpeg's header gives (the container's, or one estimated from the bit rate), without a
decode: a few hundredths of a second; only the container's own line, never a tag that holds "Duration: ...". None
when ffmpeg cannot say.
"""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from typing import Any

DEVICES = ("cpu", "cuda")
CUDA_TAKES = 1   # pipeline.CUDA_TAKES (not imported: pipeline loads numpy): 1 take by default on every device
BEST_TAKES = 4   # the page's "Best chart" (--takes 4): slower, and only sometimes better (pipeline.guitar_takes)

# The friend's RTX 4070 against the owner's RTX 5070, which the GPU's rates were measured on: the high rates times
# this until M4-08 part B times his PC (the 4070 has about 25 % less memory bandwidth, 504 against 672 GB/s, and the
# transcriber writes one token at a time, which memory bandwidth bounds [inference, M7-10's review])
FRIEND_GPU = 1.35
# (fixed s, rate s a second of the song), each as (low, high), by device
OTHER = {"cpu": ((10.0, 10.0), (0.81, 1.13)),
         "cuda": ((20.0, 20.0), (0.15, 0.40 * FRIEND_GPU))}   # every stage but the guitar and the lyrics
PREVIEW = ((5.0, 5.0), (0.01, 0.05))
LYRICS = {"cpu": ((10.0, 10.0), (0.45, 0.60)), "cuda": ((10.0, 10.0), (0.10, 0.30))}
# the guitar's device: once a chart, rate * d (the first take's own separation and timing); each take, its own start
# (TAKE_FIXED s) and k * d**2
GUITAR_ONCE = {"cpu": (0.35, 0.50), "cuda": (0.07, 0.19 * FRIEND_GPU)}
GUITAR_TAKE = {"cpu": (0.0012, 0.0033), "cuda": (0.0007, 0.0018 * FRIEND_GPU)}
TAKE_FIXED = (0.0, 10.0)
# the build and its checks (assemble), after the guitar: (fixed s, rate s a second), each as (low, high), on either
# device (the time left, `remaining`): Clone Hero's split audio, the default since M8-12 (three more encodes and the
# four files decoded back for the gate), and one song.ogg ("One audio file", `one_audio`); the module docstring
ASSEMBLE = ((0.5, 5.0), (0.05, 0.16))
ASSEMBLE_ONE = ((0.5, 5.0), (0.025, 0.08))
STEMS = ((0.5, 2.0), (0.01, 0.04))   # "Save the stems" (M8-12), after the build when the plan has it [est.]
# "Chart it differently" (M8-14) with the song's work folder still in the cache: the decode checked and the separation,
# drums, bass and sections read from their caches (`cached`) [est.], then the guitar's takes and the build
CACHED = ((5.0, 30.0), (0.01, 0.05))

# the container's own line, which ffmpeg prints indented by two spaces after the input's Metadata block; a tag's line
# (its key, a value's later lines) is indented by four or more, so a tag holding "Duration: 1:00:00" is not read
# (the v0.4.0 gate's review: a downloaded song's description tag can hold one)
DURATION = re.compile(r"^  Duration: *(\d+):(\d{2}):(\d{2}(?:\.\d+)?)", re.M)
PROBE_TIMEOUT_S = 30.0


def duration(path: Path | str, ffmpeg: str | None = None) -> float | None:
    """The song's length in seconds as ffmpeg's header says it (`ffmpeg -i`, no output), or None: no ffmpeg, no
    length in its answer ("N/A"), a length of 0, or an error."""
    try:
        from .. import audio
        exe = ffmpeg or audio.ffmpeg_exe()
        proc = subprocess.run([exe, "-hide_banner", "-nostdin", "-i", str(path)], capture_output=True,
                              timeout=PROBE_TIMEOUT_S, stdin=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001  no ffmpeg, a timeout: no estimate, and nothing else changes
        return None
    m = DURATION.search(proc.stderr.decode("utf-8", "replace"))
    if m is None:
        return None
    seconds = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    return round(seconds, 2) if seconds > 0 else None


def chart_seconds(seconds: float, takes: int, device: str, guitar: str | None = None, *, lyrics: bool = False,
                  preview: bool = True, cached: bool = False) -> tuple[float, float]:
    """The low and the high estimate of a chart's time in seconds, for a song of `seconds` with `takes` guitar takes
    (0: no guitar), the stages on `device` ("cpu" or "cuda") and the guitar on `guitar` (default: `device`), with or
    without lyrics and the preview (the module docstring). `cached`: every stage but the guitar's takes and the build
    comes from the work folder's caches (CACHED and ASSEMBLE instead of OTHER: "Chart it differently", M8-14); the
    guitar's own separation and timing stay counted, as autochart's scratch folder may have gone."""
    guitar = device if guitar is None else guitar
    if device not in DEVICES or guitar not in DEVICES:
        raise ValueError(f"the devices are among {DEVICES}, not {device!r} and {guitar!r}")
    d = float(seconds)
    if not d > 0 or takes < 0:
        raise ValueError(f"a song of {seconds!r} s with {takes!r} takes")
    parts = ([CACHED, ASSEMBLE] if cached else [OTHER[device]]) + ([PREVIEW] if preview else []) + \
        ([LYRICS[device]] if lyrics else [])
    out = []
    for i in (0, 1):   # low, high
        total = sum(fixed[i] + rate[i] * d for fixed, rate in parts)
        if takes:
            total += GUITAR_ONCE[guitar][i] * d + takes * (TAKE_FIXED[i] + GUITAR_TAKE[guitar][i] * d * d)
        out.append(total)
    return out[0], out[1]


def round_minutes(low_s: float, high_s: float) -> tuple[int, int]:
    """The range in whole minutes, never narrower than the seconds': the low end down and the high end up, to 5
    minutes from 30 on; the low end at least 1 minute, the high end above it."""
    low = max(1, math.floor(low_s / 60))
    high = math.ceil(high_s / 60)
    if low >= 30:
        low = low // 5 * 5
    if high >= 30:
        high = -(-high // 5) * 5
    return low, max(high, low + 1)


def for_job(seconds: Any, options: Any, auto_device: str | None, guitar_device: str | None = None, *,
            cached: bool = False) -> dict | None:
    """The estimate for a job (`options`: jobs.ChartOptions), or None when the song's length (a finite number of
    seconds) or the device is not known: {"seconds", "takes", "device", "low_s", "high_s", "low_min", "high_min",
    "audio"}, `device` the guitar's and `audio` the build's ("split", or "one" for one song.ogg: `remaining`'s build
    rate). The stages' device is the options' (the doctor summary's for "auto": `auto_device`); the guitar's takes are
    the options', else, as pipeline.guitar_takes, 1 on every device (CUDA_TAKES; the page's "Best chart" asks for
    BEST_TAKES). On CUDA, a guitar the doctor summary found on the CPU (`guitar_device`: autochart's CUDA provider did
    not load) is timed there. `cached`: the song's other stages come from the cache (chart_seconds)."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 < seconds < math.inf:
        return None
    device = options.device if options.device in DEVICES else auto_device
    if device not in DEVICES:
        return None
    guitar = "cuda" if device == "cuda" and guitar_device != "cpu" else "cpu"
    if "guitar" not in options.instruments:
        takes = 0
    elif options.takes is not None:
        takes = int(options.takes)
    else:
        takes = CUDA_TAKES if guitar == "cuda" else 1   # 1 either way since 2026-11-09
    low_s, high_s = chart_seconds(seconds, takes, device, guitar, lyrics=options.lyrics is not None,
                                  preview=bool(options.preview), cached=cached)
    low_min, high_min = round_minutes(low_s, high_s)
    return {"seconds": float(seconds), "takes": takes, "device": guitar, "low_s": round(low_s, 1),
            "high_s": round(high_s, 1), "low_min": low_min, "high_min": high_min,
            "audio": "one" if getattr(options, "one_audio", False) else "split"}


def remaining(est: Any, events: Any) -> dict | None:
    """The time left (the module docstring) from a job's estimate (`for_job`'s dict) and its events so far (each with
    `at`): {"from", "low_s", "high_s", "low_min", "high_min", "takes_left", "take_s", "first_s"} once the second take
    has started (`first_s` the timed take, `take_s` the range a take left is given) or the guitar has ended
    (`takes_left` 0, both None), counted from `from` (that event's `at`); None before, without a guitar or an
    estimate, or after a take was run again on the CPU."""
    if not isinstance(est, dict) or not est.get("takes") or not isinstance(events, (list, tuple)):
        return None
    d = est.get("seconds")
    guitar = est.get("device")
    if isinstance(d, bool) or not isinstance(d, (int, float)) or not 0 < d < math.inf or guitar not in DEVICES:
        return None
    plan: list = []
    takes: list[dict] = []
    ended = None
    for e in events:
        if not isinstance(e, dict):
            continue
        kind = e.get("event")
        if kind == "plan" and isinstance(e.get("stages"), list):
            plan = e["stages"]
        elif kind == "take":
            if e.get("device") is not None:   # run again on the CPU: its times are not the model's
                return None
            takes.append(e)
        elif kind == "stage_end" and e.get("stage") == "guitar":
            ended = e
    after = plan[plan.index("guitar") + 1:] if "guitar" in plan else ["assemble", "preview"]
    build = ASSEMBLE_ONE if est.get("audio") == "one" else ASSEMBLE   # split by default, as an older estimate's
    parts = [build] * ("assemble" in after) + [STEMS] * ("stems" in after) + [PREVIEW] * ("preview" in after)
    rest = [sum(fixed[i] + rate[i] * d for fixed, rate in parts) for i in (0, 1)]
    if ended is not None:
        start, left, first, each = ended.get("at"), 0, None, None
        low, high = rest
    else:
        if len(takes) < 2:
            return None
        a, b = takes[0], takes[1]
        try:
            first = float(b["at"]) - float(a["at"])
            index, count = int(b["index"]), int(b["count"])
            took_one = int(a["index"]) == 1
        except (KeyError, TypeError, ValueError):
            return None
        if not first >= 0 or index > count:
            return None
        once = GUITAR_ONCE[guitar]
        # the low end takes off take 1's own separation and timing at its high rate; the high end takes off nothing,
        # as the events do not say whether autochart's cache already held them (a chart run again after a cancel)
        each = (max(0.0, first - once[1] * d), first) if took_one else (first, first)
        start, left = b.get("at"), count - index + 1
        low, high = (left * each[i] + rest[i] for i in (0, 1))
    if isinstance(start, bool) or not isinstance(start, (int, float)):
        return None
    low_min, high_min = round_minutes(low, high)
    return {"from": start, "low_s": round(low, 1), "high_s": round(high, 1), "low_min": low_min,
            "high_min": high_min, "takes_left": left, "first_s": None if first is None else round(first, 1),
            "take_s": None if each is None else [round(each[0], 1), round(each[1], 1)]}
