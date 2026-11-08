"""How long a chart usually takes (M7-10, DESIGN.md 4.5): the progress screen's "Usually about N to M minutes".

    seconds = duration(path)                                       # the song's length from ffmpeg's header, or None
    est = for_job(seconds, options, auto_device, guitar_device)    # {"low_min", "high_min", ...}, or None
    low_s, high_s = chart_seconds(seconds, takes=4, device="cuda")

**The model** (`chart_seconds`): every stage but the guitar costs a fixed part and a rate per second of the song
(`OTHER`, `PREVIEW`, `LYRICS`); the guitar costs, once a chart, its first take's own separation and timing (a rate
per second, `GUITAR_ONCE`), then for each take a transcription that grows with the square of the song's length
(`GUITAR_TAKE`'s k times d squared, d the length in seconds). The transcriber writes its notes one at a time, each
costing more the more it has written, so a song twice as long costs about four times as much a take: the test song
(6:52) against Creep (4:00), at about the same notes a second, took 2.8x the time a take for 1.7x the length [here,
the takes experiment]. Each rate has a low and a high value, from the measured runs below, and the range is where the
ordinary songs fell. **A dense song** (many notes a second) can take longer than the high end, as the guitar's time
grows with the notes it writes. The caches are not counted: a song charted before goes faster.

**The evidence** (k as above; "ordinary": inside the range):
  * **The GPU** (the owner's RTX 5070; the friend's RTX 4070 is not measured):
      - the guitar, 4 takes: the takes experiment's seven songs (docs/reports/takes-experiment.md, 170-886 s) and the
        owner's job logs of four songs (150 s for a 3:07 song, 254 s for 3:41, 2173 s for 9:05, 3383 s for 7:19): k
        0.00067-0.0018 on the eight ordinary ones; 0.0026-0.0043 on Kimochi Warui, Lucretia and the owner's 7:19
        song, all three dense. 1 take: 5 of the 7 songs in the range, the same two dense ones above it. The first
        take's own separation and timing: 13-72 s (0.07-0.17 s a second), the first take's time less a later one's.
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
  * **The preview**: 11 s for the test song on the 5070's PC, 12 s for a 4-minute song here.
Against whole charts: the test song with 1 take on the 5070 took 5.05 min (the range: 4.1-9.8), on this CPU 12.7 min
(11.5-20.7, no preview then); Take Me Out with 1 take on this CPU 6.8 min (6.0-9.9).

`duration` reads the length ffmpeg's header gives (the container's, or one estimated from the bit rate), without a
decode: a few hundredths of a second. None when ffmpeg cannot say.
"""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from typing import Any

DEVICES = ("cpu", "cuda")
CUDA_TAKES = 4   # pipeline.CUDA_TAKES (not imported: pipeline loads numpy)

# (fixed s, rate s a second of the song), each as (low, high), by device
OTHER = {"cpu": ((10.0, 10.0), (0.81, 1.13)), "cuda": ((20.0, 20.0), (0.15, 0.40))}   # all but guitar and lyrics
PREVIEW = ((5.0, 5.0), (0.02, 0.05))
LYRICS = {"cpu": ((10.0, 10.0), (0.45, 0.60)), "cuda": ((10.0, 10.0), (0.10, 0.30))}
# the guitar's device: once a chart, rate * d (the first take's own separation and timing); each take, k * d**2
GUITAR_ONCE = {"cpu": (0.35, 0.50), "cuda": (0.08, 0.17)}
GUITAR_TAKE = {"cpu": (0.0012, 0.0033), "cuda": (0.0007, 0.0018)}

DURATION = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
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
                  preview: bool = True) -> tuple[float, float]:
    """The low and the high estimate of a chart's time in seconds, for a song of `seconds` with `takes` guitar takes
    (0: no guitar), the stages on `device` ("cpu" or "cuda") and the guitar on `guitar` (default: `device`), with or
    without lyrics and the preview (the module docstring)."""
    guitar = device if guitar is None else guitar
    if device not in DEVICES or guitar not in DEVICES:
        raise ValueError(f"the devices are among {DEVICES}, not {device!r} and {guitar!r}")
    d = float(seconds)
    if not d > 0 or takes < 0:
        raise ValueError(f"a song of {seconds!r} s with {takes!r} takes")
    parts = [OTHER[device]] + ([PREVIEW] if preview else []) + ([LYRICS[device]] if lyrics else [])
    out = []
    for i in (0, 1):   # low, high
        total = sum(fixed[i] + rate[i] * d for fixed, rate in parts)
        if takes:
            total += GUITAR_ONCE[guitar][i] * d + takes * GUITAR_TAKE[guitar][i] * d * d
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


def for_job(seconds: Any, options: Any, auto_device: str | None, guitar_device: str | None = None) -> dict | None:
    """The estimate for a job (`options`: jobs.ChartOptions), or None when the song's length (a finite number of
    seconds) or the device is not known: {"seconds", "takes", "device", "low_s", "high_s", "low_min", "high_min"}, `device` the guitar's. The
    stages' device is the options' (the doctor summary's for "auto": `auto_device`); the guitar's takes are the
    options', else, as pipeline.guitar_takes, 4 on CUDA and 1 on the CPU. On CUDA, a guitar the doctor summary found
    on the CPU (`guitar_device`: autochart's CUDA provider did not load) runs there, and by default one take only,
    as the pipeline decides once its first take shows it."""
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
        takes = CUDA_TAKES if guitar == "cuda" else 1
    low_s, high_s = chart_seconds(seconds, takes, device, guitar, lyrics=options.lyrics is not None,
                                  preview=bool(options.preview))
    low_min, high_min = round_minutes(low_s, high_s)
    return {"seconds": float(seconds), "takes": takes, "device": guitar, "low_s": round(low_s, 1),
            "high_s": round(high_s, 1), "low_min": low_min, "high_min": high_min}
