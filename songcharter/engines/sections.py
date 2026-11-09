"""Song sections as allin1 segments: All-In-One run as a separate program, or a fallback on librosa (DESIGN.md 2.5).

    result = find_sections(mix, stems, "work/sections")   # mix, stems: float32 (channels, n) at 44.1 kHz
    result.path       # work/sections/segments.json: {"segments": [[start, end, label], ...]}, what assemble's
                      # "sections" reads (songcharter.sections.read_allin1); work/sections/engine.json says how

Segment times are seconds of the input audio (the decode the stems were separated from). Labels are allin1's set
(start, end, intro, outro, break, bridge, inst, solo, verse, chorus); "start" and "end" mark the silence before and
after the music. songcharter.sections snaps them to measures, merges, splits and names them.

  * **allin1** (All-In-One, trained on the Harmonix Set). Our stems are folded to its four (bass, drums, vocals,
    and "other": every other stem summed, so htdemucs_6s's guitar + piano + other), made into the mono int16 arrays
    allin1 reads from the WAVs Demucs writes for it (each rescaled when it peaks over full scale), and sent on stdin
    to allin1_runner.py in the Python that has all-in-one-infer or allin1 (`Settings.python`, else
    $SONGCHARTER_ALLIN1_PYTHON, else this Python when it has one of them): no second separation, no stem files.
    The runner starts under that Python's own import rules, user site and PYTHONPATH included, as a plain
    `python -c "import allin1_infer"` would (RUNNER_BOOT), so a `pip install --user` counts.
    `model="auto"` is fold 0 on every device (AUTO_MODEL): the 8-fold ensemble measured no better (DESIGN.md 2.5),
    and the grid's rules that read allin1's beats and downbeats were measured on fold 0 (M6-10). The checkpoints
    come from the Hugging Face hub at a pinned revision, downloaded on first use; each is checked against its
    SHA-256 before the runner loads it (they are pickles: the check is what makes loading them safe).
  * **CUDA.** The probe runs a CUDA kernel rather than trusting `torch.cuda.is_available()`, which is also true on a
    GPU the torch build has no kernels for; `device="auto"` takes CUDA only when the kernel ran. A CUDA run that
    fails is run again on the CPU, with the same model, in a fresh process (the runner itself never moves to the
    CPU), so the CPU run's memory check applies (Memory): any failure, a kill included, when the device was
    "auto"; only CUDA running out of memory when it was "cuda", where any other failure raises. engine.json
    records the fallback ("CUDA ran out of memory (...); analysed on the CPU", "the CUDA run failed (...); ...").
  * **Memory** (M8-05, DESIGN.md 2.5). allin1's own peak on the CPU grows by about 1 GiB a minute of audio, and the
    process tree with it (M8-03 part A's lines, CHILD_MIB and PARENT_MIB). Given a SongArrays with a loader (the
    pipeline's), the mix and stems are let go while the runner runs, once its input bytes and the key are made, and
    read again only when they are needed (the librosa fallback, or the caller after). Before a run on the CPU the
    predicted tree, with MARGIN_MIB, is compared with this machine's MemTotal (fixed per PC, never MemAvailable;
    swap is not counted: allin1 deep in swap was never measured and could run for hours, worse than the librosa fallback): when it does not fit, allin1 is left out at once (memory_skip), instead of being killed minutes
    later; a runner ended by SIGKILL is named as most likely stopped for memory (stopped_line). On CUDA nothing is
    checked before the run, whatever the song's length (allin1's host memory there was measured once, not as a
    line). A CUDA run that runs out of memory, fails or is killed is run again on the CPU (CUDA above), and that
    run is checked like any other: a song past the line goes to the librosa fallback with memory_skip's words.
    doctor's figure (device.findings, longest_s) is the CPU's.
  * **librosa** (numpy, scipy and librosa only), for when allin1 is not available. Laplacian structural
    segmentation (McFee and Ellis 2014, as in librosa's gallery) on beat-synchronous CQT and MFCC; the cluster
    count is the one whose segments, after those under 16 beats merge, come closest to one per
    `seconds_per_segment` (25) of music. Names come from the stems: no vocals at the start is the intro and at
    the end the outro; elsewhere no vocals is a solo when the guitar (else "other") stem is clearly louder than
    usual, a break when the song is quiet, else an instrumental; of the clusters with vocals, the loudest one that
    repeats is the chorus, a cluster heard once between two choruses the bridge, the rest verses. Without stems:
    intro, outro, the most repeated cluster as the chorus, verses. The naming rules are untested guesses.
  * **Choice.** `backend="auto"` takes allin1 when its Python is set, its probe passes and the run succeeds, else
    the fallback; engine.json records the backend and why. `backend="allin1"` raises instead of falling back, and
    so does "auto" when allin1 failed and librosa is not installed (an errors.ToolError naming both).
  * **Cache.** engine.json holds a key of the samples the backend read and every setting that changes the result
    (the allin1 package and version, the model and its weights' hashes, the device; the librosa version and the
    fallback's parameters and constants). A call whose key matches the folder's engine.json returns the files
    already there; for allin1 the probe still runs first (a few seconds), since its answer is part of the key.
    The hit's engine.json is rewritten with this call's "why" and "settings", so it says why this call chose
    the backend; the rest describes the run that made the files (its timings under "seconds"/"run").

The fallback needs librosa (`pip install songcharter[sections]`). allin1 needs a Python with all-in-one-infer and
torchaudio (`pip install all-in-one-infer torchaudio`: wheels, nothing to compile; all-in-one-infer 3.1.0 imports
torchaudio but declares it only in its `natten` extra), either this one or one of its own.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

import numpy as np

from .. import audio as A
from ..errors import InputError, ToolError
from ..sections import Segment, read_allin1

SAMPLE_RATE = A.SAMPLE_RATE
ENGINE_VERSION = 1          # part of the key: bump it when a change here changes the segments
ENV_PYTHON = "SONGCHARTER_ALLIN1_PYTHON"
ALLIN1_MODULES = ("allin1_infer", "allin1")   # all-in-one-infer, else the original allin1 (allin1_runner.PACKAGES)
RUNNER = Path(__file__).with_name("allin1_runner.py")
# `python -c RUNNER_BOOT <runner> <args>`: the runner as __main__, with the allin1 Python's user site and PYTHONPATH
# (what allin1_python's find_spec sees here) but not the current folder, nor the runner's own (run_path on a file
# leaves sys.path alone). `-I` would drop the user site and PYTHONPATH too; `-P` needs Python 3.11.
RUNNER_BOOT = ("import sys; getattr(sys.flags, 'safe_path', False) or sys.path.pop(0); import runpy; "
               "sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')")
SEGMENTS, ENGINE = "segments.json", "engine.json"

ALLIN1_REPO = "taejunkim/allinone"                            # tagged MIT on the hub
ALLIN1_REVISION = "379e5fd010b3fdd0ee8381ff8cbcfa51d70b5c19"
ALLIN1_FOLDS = {  # model name -> (file, SHA-256): the Harmonix folds allin1's loaders name
    "harmonix-fold0": ("harmonix-fold0-0vra4ys2.pth",
                       "0db596dfb0995f41d62f6267d76a9d54c046f1649bd35e1dbeca0c5f9a7b8acd"),
    "harmonix-fold1": ("harmonix-fold1-3ozjhtsj.pth",
                       "607b4864eaabccd4f6951410d5ea6676666ad1cfa6ce2e18bc99f3824b77c3b7"),
    "harmonix-fold2": ("harmonix-fold2-gmgo0nsy.pth",
                       "67c28ec7ca612d365e5fcb152f6530eb53e34c4303940afb30fd17a295c958a4"),
    "harmonix-fold3": ("harmonix-fold3-i92b7m8p.pth",
                       "446d05672b2669cdb7d9b8bbbc228a4f3592484335a7995cca89a744e3950ddc"),
    "harmonix-fold4": ("harmonix-fold4-1bql5qo0.pth",
                       "96327222ab9b33c005388b788ba602f529aa03cc4dde1c859c011f1004490493"),
    "harmonix-fold5": ("harmonix-fold5-x4z5zeef.pth",
                       "c87f162a1090290bcbb863688746784919cf912c56744fb3d81a1a7dba3b114e"),
    "harmonix-fold6": ("harmonix-fold6-x7t226rq.pth",
                       "13e7e639bf30fcd3fa049ad863088773a4e57b06d7c68581385b3ef625c60688"),
    "harmonix-fold7": ("harmonix-fold7-qwwskhg6.pth",
                       "b888b7fba95efa3d5a37ca013fe7efe2741621ea9ca335e6b2723e4fd0fade57"),
}
ALLIN1_MODELS = {**{name: [name] for name in ALLIN1_FOLDS}, "harmonix-all": list(ALLIN1_FOLDS)}
# model "auto" on every device. Not the ensemble on CUDA: it measured no gain (ensemble - fold 0: -0.004 at +-3 s,
# DESIGN.md 2.5), and since M6 allin1's beats and downbeats set the grid (the bar phase, the doubled grid's start,
# the halving test), measured on fold 0 only, where the ensemble's beats can sit at another octave (M6-10)
AUTO_MODEL = "harmonix-fold0"
ALLIN1_STEMS = ("bass", "drums", "other", "vocals")   # allin1's four; every other stem folds into "other"
PROBE_TIMEOUT_S = 300

# memory (M8-03 part A, 24 kept songs on the CPU; MiB, d the song's seconds): allin1's own peak (A-a, residuals -233
# / +202), the pipeline's process while it runs (A-b), and what the parent lets go when its arrays are released (the
# mix and six stems, 142 MiB a minute, and the int16 payload, 20: A-b); the tree is the sum, 853.5 + 20.4 d, or
# 853.5 + 17.7 d with the arrays let go. The margin is the child line's largest residual and a reserve of 1 GiB (A-d)
CHILD_MIB = (354.5, 17.443)
PARENT_MIB = (499.0, 2.96)
FREED_MIB_PER_S = 162 / 60
MARGIN_MIB = 202 + 1024
MEMINFO = Path("/proc/meminfo")
# what the page's banner says when the sections fall back (Allin1Error.plain; the result's info["plain"])
FAILED_PLAIN = "allin1 failed (the diagnostics zip has the details)"
TIMEOUT_PLAIN = "allin1 did not finish in time"
NOT_INSTALLED_PLAIN = "allin1 is not installed"
LEFT_OUT_PLAIN = "allin1 is left out on this PC to save memory"   # doctor's and the install's memory rule
KILLED = -9                 # subprocess's returncode for a child ended by SIGKILL (on Linux, the kernel's OOM killer)
# the runner's error line when CUDA ran out of memory: torch.OutOfMemoryError (torch.cuda.OutOfMemoryError in an
# older torch)
OUT_OF_MEMORY = re.compile(r"\bOutOfMemoryError: (.*)")

# the fallback
FEATURE_RATE = 22050        # librosa's default rate; the mix is halved to it
HOP = 512                   # feature frames of 23 ms
MIN_SEGMENT_BEATS = 16      # 4 bars of 4/4
CLUSTERS = range(2, 13)     # cluster counts tried
KMEANS_RUNS = 10            # seeded k-means restarts, the lowest distortion kept
SILENCE_DB = -40.0          # music starts and ends where the mix is within this of its loudest frame
VOCALS_DB = -20.0           # a block has vocals when the vocal stem is within this of the mix (bleed: -28 dB and below)
VOCAL_SHARE = 0.25          # a segment has vocals when this share of its blocks do
SOLO_DB = 2.0               # a solo's guitar is this much louder against the mix than the song's median segment
QUIET_DB = -6.0             # a break is this much quieter than the song's median segment
BLOCK_S = 0.5               # stem-level blocks


def _fallback_constants() -> tuple:
    """The fallback's constants as they are now: part of its key, so a changed one is a new key."""
    return (FEATURE_RATE, HOP, MIN_SEGMENT_BEATS, tuple(CLUSTERS), KMEANS_RUNS, SILENCE_DB, VOCALS_DB, VOCAL_SHARE,
            SOLO_DB, QUIET_DB, BLOCK_S)


class Allin1Error(ToolError):
    """allin1 is not available here, or its run failed (a RuntimeError, as errors.ToolError is). `plain`: what the
    page's banner says of it (no path, command or exception text: those stay in the message), else FAILED_PLAIN."""

    def __init__(self, message: str, plain: str | None = None):
        super().__init__(message)
        self.plain = plain


class _RunFailed(Allin1Error):
    """The runner exited with an error; `line` is the error's own line from its traceback."""

    def __init__(self, message: str, line: str, plain: str | None = None):
        super().__init__(message, plain)
        self.line = line


@dataclass(frozen=True)
class Settings:
    backend: str = "auto"              # "auto" (allin1 if it works, else librosa), "allin1" or "librosa"
    model: str = "auto"                # allin1: "auto" (AUTO_MODEL, fold 0, on every device), or a name in
                                       # ALLIN1_MODELS ("harmonix-fold0", ..., "harmonix-all")
    device: str = "auto"               # allin1: "auto" (CUDA if the allin1 Python has it), "cpu" or "cuda"
    python: str | None = None          # the Python with allin1 (default $SONGCHARTER_ALLIN1_PYTHON)
    threads: int | None = None         # allin1's torch threads (default: all cores but one)
    timeout_s: float = 3600.0          # allin1's run
    seconds_per_segment: float = 25.0  # librosa: the target segment length (DESIGN.md 2.5's k = duration / 25 s)


@dataclass(frozen=True)
class SectionsResult:
    path: Path        # segments.json (allin1 format)
    info: dict        # engine.json
    cached: bool

    @property
    def backend(self) -> str:
        return self.info["backend"]

    @property
    def segments(self) -> list[Segment]:
        return read_allin1(self.path)


class SongArrays:
    """The mix and stems find_sections reads, held so that allin1's run can let them go (module docstring, Memory).
    `load` reads them again, the same arrays (the pipeline's: decode.wav and the stem WAVs, float32 as written);
    without it they are kept."""

    def __init__(self, mix: np.ndarray, stems: Mapping[str, np.ndarray],
                 load: Callable[[], tuple[np.ndarray, Mapping[str, np.ndarray]]] | None = None):
        self.samples, self.names = int(mix.shape[1]), tuple(sorted(stems))
        self._held: tuple | None = (mix, dict(stems))
        self._load = load

    @property
    def can_release(self) -> bool:
        return self._load is not None

    @property
    def released(self) -> bool:
        return self._held is None

    def arrays(self) -> tuple[np.ndarray, Mapping[str, np.ndarray]]:
        """The mix and stems: those held, or (after release) read again and held again."""
        if self._held is None:
            mix, stems = self._load()
            self._held = (mix, dict(stems))
        return self._held

    def release(self) -> bool:
        """Let the arrays go when `load` can read them again; whether this holder now holds none."""
        if self._load is not None:
            self._held = None
        return self._held is None

    def take(self) -> tuple[np.ndarray, Mapping[str, np.ndarray]]:
        """The arrays (read again if they were let go), which this holder then lets go: the caller holds them."""
        arrays = self.arrays()
        self._held = None
        return arrays


def _mmss(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def child_mib(seconds: float) -> float:
    """allin1's own peak on the CPU for a song of `seconds` (M8-03 A-a's line)."""
    return CHILD_MIB[0] + CHILD_MIB[1] * seconds


def tree_mib(seconds: float, freed: bool) -> float:
    """The process tree's peak while allin1 runs on the CPU (child and parent), `freed`: with the arrays let go."""
    return child_mib(seconds) + PARENT_MIB[0] + (PARENT_MIB[1] - FREED_MIB_PER_S * freed) * seconds


def capacity_mib(path: Path | None = None) -> float | None:
    """This machine's memory, MemTotal (in WSL: .wslconfig's memory), in MiB; None where /proc/meminfo does not say.
    Never MemAvailable, which changes from run to run; nor SwapTotal: allin1 deep in swap was never measured and could run for hours, worse than the librosa fallback."""
    try:
        text = (path or MEMINFO).read_text(encoding="ascii", errors="replace")
    except OSError:
        return None
    kb = {}
    for line in text.splitlines():
        m = re.match(r"(MemTotal):\s+(\d+)\s*kB", line)
        if m:
            kb[m.group(1)] = int(m.group(2))
    return kb["MemTotal"] / 1024 if "MemTotal" in kb else None


def longest_s(capacity: float, freed: bool = True) -> float:
    """The longest song whose tree, with MARGIN_MIB, fits `capacity` MiB (memory_skip's limit)."""
    base, per_s = tree_mib(0.0, freed), tree_mib(1.0, freed) - tree_mib(0.0, freed)
    return max(0.0, (capacity - MARGIN_MIB - base) / per_s)


def memory_skip(seconds: float, freed: bool, capacity: float | None) -> str | None:
    """Why allin1 is left out on the CPU for a song of `seconds` on a machine of `capacity` MiB, else None."""
    if capacity is None or tree_mib(seconds, freed) + MARGIN_MIB <= capacity:
        return None
    return (f"allin1 was left out for memory (a song of {_mmss(seconds)} needs about {child_mib(seconds) / 1024:.1f} "
            f"GiB for it on the CPU, {(tree_mib(seconds, freed) + MARGIN_MIB) / 1024:.1f} GiB with the rest of the "
            f"chart and a margin; this PC has {capacity / 1024:.1f} GiB of memory)")


def no_python_plain() -> str:
    """The banner's words for no allin1 Python: left out for memory where the install leaves it out (WSL with under
    device.ALLIN1_MEMORY of MemTotal), else not installed."""
    from .. import device, wsl   # here: device imports this module
    total = capacity_mib()
    if wsl.is_wsl() and total is not None and total * 2 ** 20 < device.ALLIN1_MEMORY:
        return LEFT_OUT_PLAIN
    return NOT_INSTALLED_PLAIN


def stopped_line(seconds: float) -> str:
    """What a runner ended by SIGKILL is reported as."""
    return (f"allin1 was stopped, most likely for memory (a song of {_mmss(seconds)} needs about "
            f"{child_mib(seconds) / 1024:.1f} GiB for it on the CPU)")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def checkpoint_paths(model: str, download: Callable[..., str] | None = None) -> list[Path]:
    """The model's checkpoints at the pinned revision (downloaded on first use), in fold order, each checked
    against its SHA-256."""
    if model not in ALLIN1_MODELS:
        raise ValueError(f"unknown allin1 model {model!r} (known: {', '.join(ALLIN1_MODELS)})")
    if download is None:
        from huggingface_hub import hf_hub_download as download
    out = []
    for fold in ALLIN1_MODELS[model]:
        file, sha = ALLIN1_FOLDS[fold]
        path = Path(download(ALLIN1_REPO, file, revision=ALLIN1_REVISION))
        got = _sha256(path)
        if got != sha:
            raise RuntimeError(f"allin1 {file} has SHA-256 {got}, not the pinned {sha}; delete it and run again")
        out.append(path)
    return out


def cache_key(arrays: Mapping[str, np.ndarray], params: Mapping) -> str:
    """A hash of the named arrays (their samples, shapes and types) and the parameters."""
    h = hashlib.sha256()
    h.update(repr(sorted((str(k), repr(v)) for k, v in params.items())).encode())
    for name in sorted(arrays):
        a = np.ascontiguousarray(arrays[name])
        h.update(repr((name, a.shape, a.dtype.str)).encode())
        h.update(a.tobytes())
    return h.hexdigest()[:24]


def fold_stems(stems: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """allin1's four stems from ours: bass, drums and vocals as they are, "other" the sum of the rest."""
    missing = [s for s in ("bass", "drums", "vocals") if s not in stems]
    rest = sorted(s for s in stems if s not in ("bass", "drums", "vocals"))
    if missing or not rest:
        raise Allin1Error(f"allin1 needs bass, drums, vocals and at least one other stem, not {sorted(stems)}")
    other = np.sum([np.asarray(stems[s], dtype=np.float32) for s in rest], axis=0, dtype=np.float32)
    return {"bass": stems["bass"], "drums": stems["drums"], "other": other, "vocals": stems["vocals"]}


def allin1_stem(y: np.ndarray) -> np.ndarray:
    """A stem as allin1 reads it from a WAV Demucs wrote for it: rescaled when it peaks over full scale (Demucs's
    default "rescale" clip mode), quantized to 16 bits per channel (x 32768, rounded, clamped), then mixed to mono
    the way madmom does for integer audio (the mean, truncated back to int16)."""
    y = np.asarray(y, dtype=np.float32)
    y = y / max(1.01 * float(np.max(np.abs(y))) if y.size else 0.0, 1.0)
    q = np.clip(np.round(np.clip(y, -1, 1) * 32768.0), -32768, 32767).astype(np.int16)
    return q.mean(axis=0).astype(np.int16)


def allin1_input(stems: Mapping[str, np.ndarray]) -> np.ndarray:
    """What the runner reads on stdin: allin1's four stems (fold_stems), each as allin1_stem, shape (4, n)."""
    four = fold_stems(stems)
    return np.stack([allin1_stem(four[name]) for name in ALLIN1_STEMS])


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _cached(out: Path, key: str, live: dict) -> SectionsResult | None:
    """The result already in `out` for this key, else None. A hit's engine.json takes this call's `live` fields
    (why, settings) and is written back, so the file and the result say why this call chose the backend."""
    try:
        info = json.loads((out / ENGINE).read_text(encoding="utf-8"))
        if info.get("key") != key:
            return None
        read_allin1(out / SEGMENTS)
    except (OSError, ValueError):
        return None
    seconds = info.get("seconds") or {}
    info = {**info, **live, "cached": True, "seconds": {"total": 0.0, "run": seconds.get("run", seconds)}}
    _write_json(out / ENGINE, info)
    return SectionsResult(out / SEGMENTS, info, True)


def _save(out: Path, segments: dict, info: dict) -> SectionsResult:
    out.mkdir(parents=True, exist_ok=True)
    (out / ENGINE).unlink(missing_ok=True)  # engine.json is written last: without it the folder is no hit
    _write_json(out / SEGMENTS, segments)
    _write_json(out / ENGINE, info)
    return SectionsResult(out / SEGMENTS, info, False)


def _tail(proc: subprocess.CompletedProcess, lines: int = 8) -> str:
    text = proc.stderr or proc.stdout or ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    return "\n".join(text.strip().splitlines()[-lines:])


def _error_line(proc: subprocess.CompletedProcess) -> str:
    """The exception's line of a traceback ("RuntimeError: CUDA error: ..."), else the last line, at most 200
    characters: a CUDA error's message goes on with lines of advice after it."""
    lines = _tail(proc, 40).splitlines()
    named = [line for line in lines if re.match(r"[A-Za-z_][\w.]*(Error|Exception): ", line)]
    return (named or lines or [""])[-1].strip()[:200]


def runner_command(python: str, *args: str) -> list[str]:
    """The command that runs allin1_runner.py with `args` in `python` (RUNNER_BOOT)."""
    return [python, "-c", RUNNER_BOOT, str(RUNNER), *args]


def allin1_python(settings: Settings) -> str | None:
    """The Python to run allin1 in: the setting, $SONGCHARTER_ALLIN1_PYTHON, or this one when it has allin1."""
    if settings.python or os.environ.get(ENV_PYTHON):
        return settings.python or os.environ[ENV_PYTHON]
    if any(importlib.util.find_spec(m) is not None for m in ALLIN1_MODULES):
        return sys.executable
    return None


def probe(python: str, run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict:
    """What the allin1 Python has: package, version, torch, cuda (a kernel ran), cuda_error, attention.
    Allin1Error when it cannot run it."""
    with tempfile.TemporaryDirectory(prefix="allin1-probe-") as tmp:
        out = Path(tmp) / "probe.json"
        try:
            proc = run(runner_command(python, "probe", str(out)), capture_output=True, text=True,
                       timeout=PROBE_TIMEOUT_S, cwd=tmp)
        except (OSError, subprocess.SubprocessError) as e:
            raise Allin1Error(f"allin1's Python {python} did not run ({type(e).__name__}: {e})") from e
        if proc.returncode != 0 or not out.is_file():
            raise Allin1Error(f"allin1's Python {python} failed its probe (exit {proc.returncode}):\n{_tail(proc)}")
        return json.loads(out.read_text(encoding="utf-8"))


def _check(mix: np.ndarray, stems: Mapping[str, np.ndarray] | None, sample_rate: int, settings: Settings,
           beats: np.ndarray | None) -> None:
    if sample_rate != SAMPLE_RATE:
        raise ValueError(f"find_sections needs {SAMPLE_RATE} Hz audio, not {sample_rate} Hz")
    if mix.ndim != 2 or mix.shape[1] == 0:
        raise ValueError(f"the mix must be a (channels, samples) array, not shape {mix.shape}")
    for name, y in (stems or {}).items():
        if y.ndim != 2 or y.shape[1] != mix.shape[1]:
            raise ValueError(f"stem {name} has shape {y.shape}; stems must be (channels, {mix.shape[1]}) like the mix")
    if settings.backend not in ("auto", "allin1", "librosa"):
        raise ValueError(f"backend is auto, allin1 or librosa, not {settings.backend!r}")
    if settings.model != "auto" and settings.model not in ALLIN1_MODELS:
        raise ValueError(f"unknown allin1 model {settings.model!r} (known: auto, {', '.join(ALLIN1_MODELS)})")
    if settings.device not in ("auto", "cpu", "cuda"):
        raise ValueError(f"device is auto, cpu or cuda, not {settings.device!r}")
    if not settings.seconds_per_segment > 0:
        raise ValueError("seconds_per_segment must be positive")
    if beats is not None:  # times outside the audio are fine (trimmed); a NaN is the caller's bug
        b = np.asarray(beats, dtype=np.float64)
        if b.ndim != 1 or not np.all(np.isfinite(b)):
            raise ValueError(f"beats must be a 1-D array of finite times in seconds, not shape {b.shape} with "
                             f"{int(np.sum(~np.isfinite(b)))} non-finite")


def find_sections(mix: np.ndarray, stems: Mapping[str, np.ndarray] | None, out: Path | str,
                  settings: Settings = Settings(), *, sample_rate: int = SAMPLE_RATE, beats: np.ndarray | None = None,
                  run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                  download: Callable[..., str] | None = None) -> SectionsResult:
    """Segments of the song in out/segments.json and how they were made in out/engine.json (module docstring).

    mix:   the decoded song, float32 (channels, n) at 44.1 kHz; stems: name -> array of the same shape (or None).
           Or `mix` a SongArrays holding both (stems None), which allin1's run lets go (module docstring, Memory).
    beats: beat times in seconds for the fallback's beat-synchronous features (default: librosa's tracker); those
           before 0 s (a tempo map's lead-in) or after the end are left out.
    run, download: stand-ins for subprocess.run and huggingface_hub's hf_hub_download (tests).
    """
    if isinstance(mix, SongArrays):
        if stems is not None:
            raise ValueError("stems come from the SongArrays: pass stems=None")
        song = mix
        _check(*song.arrays(), sample_rate, settings, beats)
    else:
        _check(mix, stems, sample_rate, settings, beats)
        song = SongArrays(mix, stems or {})
    del mix, stems   # the song's arrays are held by `song` alone, so allin1's run can let them go
    out = Path(out)
    why = []
    if settings.backend in ("auto", "allin1"):
        try:
            return _allin1(song, out, settings, run, download)
        except Allin1Error as e:
            if settings.backend == "allin1":
                raise
            try:  # the fallback's own import, here so that its absence also names why allin1 failed
                import librosa  # noqa: F401
            except ImportError:
                raise ToolError(f"allin1 failed ({e}) and the librosa fallback is not installed: pip install "
                                "songcharter[sections]") from e
            why.append(str(e))
            plain = e.plain or FAILED_PLAIN
    elif settings.backend == "librosa":
        why.append("backend librosa asked for")
    result = _librosa(*song.arrays(), out, settings, beats, why)
    want = plain if settings.backend != "librosa" else None   # the page's words, beside `why`'s details
    if result.info.get("plain") != want:   # this call's, also on a hit made by another call
        result.info.pop("plain", None)
        if want is not None:
            result.info["plain"] = want
        if (out / ENGINE).is_file():
            _write_json(out / ENGINE, result.info)
    return result


# ------------------------------------------------------------------------------------------------------------ allin1

def _allin1(song: SongArrays, out: Path, s: Settings, run, download) -> SectionsResult:
    python = allin1_python(s)
    if python is None:
        raise Allin1Error(f"no allin1 Python: set {ENV_PYTHON} to a Python with all-in-one-infer (or allin1)",
                          no_python_plain())
    data = allin1_input(song.arrays()[1]).astype("<i2")
    shape, data = data.shape, data.tobytes()   # what the runner reads on stdin
    payload = np.frombuffer(data, dtype="<i2").reshape(shape)   # the same samples for the key, without a copy
    found = probe(python, run)
    cuda_error = f" ({found['cuda_error']})" if found.get("cuda_error") else ""
    if s.device == "cuda" and not found.get("cuda"):
        raise Allin1Error(f"device cuda asked for, but allin1's Python {python} has no working CUDA{cuda_error}")
    device = s.device if s.device != "auto" else ("cuda" if found.get("cuda") else "cpu")
    why, fallback = f"backend {s.backend}: allin1's Python {python} passed its probe", None
    if s.device == "auto" and cuda_error:
        fallback = f"CUDA does not run here{cuda_error}; analysed on the CPU"
        why += f"; {fallback}"
    try:
        return _allin1_job(song, payload, data, out, s, python, found, device, why, fallback, run, download)
    except _RunFailed as e:
        oom = OUT_OF_MEMORY.search(e.line)
        if device == "cpu" or (s.device != "auto" and not oom):  # asked for cuda: no second try, but out of memory
            raise
        failed = f"CUDA ran out of memory ({oom.group(1)[:120]})" if oom else f"the CUDA run failed ({e.line})"
        fallback = f"{failed}; analysed on the CPU"   # a fresh process, which _allin1_job checks for memory first
        try:
            return _allin1_job(song, payload, data, out, s, python, found, "cpu", f"{why}; {fallback}", fallback,
                               run, download)
        except Allin1Error as again:
            raise Allin1Error(f"{failed}, and then on the CPU: {again}", again.plain) from again


def _allin1_job(song: SongArrays, payload: np.ndarray, data: bytes, out: Path, s: Settings, python: str, found: dict,
                device: str, why: str, fallback: str | None, run, download) -> SectionsResult:
    """One allin1 run on `device` (or the cached result of one); _RunFailed when the runner exits with an error,
    Allin1Error when the song does not fit this machine's memory on the CPU (memory_skip)."""
    model = s.model if s.model != "auto" else AUTO_MODEL
    weights = {ALLIN1_FOLDS[f][0]: ALLIN1_FOLDS[f][1] for f in ALLIN1_MODELS[model]}
    key = cache_key({"stems": payload}, {"backend": "allin1", "engine": ENGINE_VERSION, "package": found.get("package"),
                           "version": found.get("version"), "model": model, "weights": weights, "device": device,
                           "rate": SAMPLE_RATE})
    live = {"why": why, "settings": {**asdict(s), "python": python}}
    hit = _cached(out, key, live)
    if hit is not None:
        return hit
    seconds = song.samples / SAMPLE_RATE
    # on CUDA nothing is checked (module docstring, Memory): a CUDA run that fails comes back here on the CPU
    skip = memory_skip(seconds, song.can_release, capacity_mib()) if device == "cpu" else None
    if skip:
        raise Allin1Error(skip, skip)
    try:
        checkpoints = checkpoint_paths(model, download)
    except (ImportError, OSError, RuntimeError, ValueError) as e:  # no hub client, no download, not the pinned file
        raise Allin1Error(f"allin1 weights for {model}: {type(e).__name__}: {e}") from e
    threads = s.threads or max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()  # reported only
    with tempfile.TemporaryDirectory(prefix="allin1-") as tmp:
        work = Path(tmp)
        job = {"samples": int(payload.shape[1]), "stems": list(ALLIN1_STEMS), "device": device, "threads": threads,
               "checkpoints": [str(p) for p in checkpoints], "seed": 0, "out": str(work / "result.json")}
        _write_json(work / "job.json", job)
        song.release()   # while the child runs, only `data` stays here of the song (module docstring, Memory)
        try:
            proc = run(runner_command(python, "run", str(work / "job.json")), capture_output=True,
                       input=data, timeout=s.timeout_s, cwd=tmp)
        except (OSError, subprocess.SubprocessError) as e:
            raise Allin1Error(f"allin1 did not finish ({type(e).__name__}: {e})",
                              TIMEOUT_PLAIN if isinstance(e, subprocess.TimeoutExpired) else None) from e
        if proc.returncode == KILLED:
            raise _RunFailed(stopped_line(seconds), stopped_line(seconds), stopped_line(seconds))
        if proc.returncode != 0 or not (work / "result.json").is_file():
            raise _RunFailed(f"allin1 failed (exit {proc.returncode}):\n{_tail(proc)}", _error_line(proc))
        res = json.loads((work / "result.json").read_text(encoding="utf-8"))
    seconds = round(time.perf_counter() - t0, 2)
    segments = {"segments": res["segments"], "bpm": res.get("bpm"), "beats": res.get("beats"),
                "downbeats": res.get("downbeats")}
    info = {"engine": "sections", "engine_version": ENGINE_VERSION, "key": key, "backend": "allin1", **live,
            "cached": False,
            "input": {"duration_s": round(song.samples / SAMPLE_RATE, 3), "stems": list(song.names),
                      "other": [n for n in song.names if n not in ("bass", "drums", "vocals")]},
            "allin1": {**found, "model": model, "device": res.get("device", device),
                       "fallback": fallback, "threads": res.get("threads"),
                       "repo": ALLIN1_REPO, "revision": ALLIN1_REVISION, "weights": weights,
                       "attention": res.get("attention", found.get("attention")),
                       "peak_rss_mb": res.get("peak_rss_mb")},   # the runner's own peak (allin1_runner.peak_rss_mb)
            "seconds": {"total": seconds,  # the runner's own total as "runner"
                        **{("runner" if k == "total" else k): v for k, v in (res.get("seconds") or {}).items()}},
            "segments": len(res["segments"])}
    return _save(out, segments, info)


# ----------------------------------------------------------------------------------------------------------- librosa

def _mono(y: np.ndarray) -> np.ndarray:
    return np.asarray(y, dtype=np.float64).mean(axis=0)


def _block_power(y: np.ndarray, block: int) -> np.ndarray:
    """Mean power of a (channels, n) array in blocks of `block` samples (the last one partial)."""
    x = _mono(y) ** 2
    n = int(np.ceil(len(x) / block))
    x = np.pad(x, (0, n * block - len(x)))
    return x.reshape(n, block).mean(axis=1)


def _db(p) -> np.ndarray:
    return 10 * np.log10(np.maximum(p, 1e-12))


def _kmeans(x: np.ndarray, k: int) -> np.ndarray:
    """Seeded k-means++ (scipy), the lowest-distortion of KMEANS_RUNS restarts, as cluster labels."""
    import warnings
    from scipy.cluster.vq import kmeans2
    best, labels = np.inf, None
    for seed in range(KMEANS_RUNS):
        with warnings.catch_warnings():  # an empty cluster: this restart scores worse, another wins
            warnings.simplefilter("ignore")
            try:
                centroids, lab = kmeans2(x, k, minit="++", rng=np.random.default_rng(seed))
            except TypeError:  # scipy before 1.15 names it seed
                centroids, lab = kmeans2(x, k, minit="++", seed=np.random.default_rng(seed))
        d = float(np.sum((x - centroids[lab]) ** 2))
        if d < best - 1e-12:
            best, labels = d, lab
    return labels


def _runs(labels: np.ndarray, min_len: int) -> list[list[int]]:
    """[start column, cluster] of each run of one label, runs shorter than min_len merged into the one before
    (the first into the one after), the shortest first; neighbours left with one cluster are joined."""
    runs = [[0, int(labels[0])]] + [[i, int(labels[i])] for i in range(1, len(labels)) if labels[i] != labels[i - 1]]
    while len(runs) > 1:
        lengths = [b[0] - a[0] for a, b in zip(runs, runs[1:])] + [len(labels) - runs[-1][0]]
        n, i = min((n, i) for i, n in enumerate(lengths))
        if n >= min_len:
            break
        if i == 0:
            runs[1][0] = 0
        del runs[i]
        joined = [runs[0]]
        for r in runs[1:]:
            if r[1] != joined[-1][1]:
                joined.append(r)
        runs = joined
    return runs


def laplacian_segments(y: np.ndarray, beat_frames: np.ndarray, target: int) -> tuple[list[list[int]], np.ndarray, dict]:
    """Runs [start column, cluster] of the Laplacian segmentation of mono `y` (FEATURE_RATE) on the beat frames,
    the columns' start frames, and what was chosen."""
    import librosa
    import scipy.linalg
    import scipy.ndimage
    import scipy.sparse.csgraph
    C = librosa.amplitude_to_db(np.abs(librosa.cqt(y=y, sr=FEATURE_RATE, hop_length=HOP, bins_per_octave=36,
                                                   n_bins=252)), ref=np.max)
    mfcc = librosa.feature.mfcc(y=y, sr=FEATURE_RATE, hop_length=HOP, n_mfcc=20)
    bounds = librosa.util.fix_frames(beat_frames, x_min=0, x_max=C.shape[1])
    c_sync = librosa.util.sync(C, bounds, aggregate=np.median, pad=False)
    m_sync = librosa.util.sync(mfcc, bounds, pad=False)
    rec = librosa.segment.recurrence_matrix(c_sync, width=3, mode="affinity", sym=True)
    rec = librosa.segment.timelag_filter(scipy.ndimage.median_filter)(rec, size=(1, 7))
    path_distance = np.sum(np.diff(m_sync, axis=1) ** 2, axis=0)
    path_sim = np.exp(-path_distance / max(float(np.median(path_distance)), 1e-12))
    r_path = np.diag(path_sim, k=1) + np.diag(path_sim, k=-1)
    deg_path, deg_rec = r_path.sum(axis=1), rec.sum(axis=1)
    mu = deg_path.dot(deg_path + deg_rec) / np.sum((deg_path + deg_rec) ** 2)
    lap = scipy.sparse.csgraph.laplacian(mu * rec + (1 - mu) * r_path, normed=True)
    _, evecs = scipy.linalg.eigh(lap)
    evecs = scipy.ndimage.median_filter(evecs, size=(9, 1))
    cnorm = np.cumsum(evecs ** 2, axis=1) ** 0.5
    tried = {}
    for k in CLUSTERS:
        if k >= c_sync.shape[1]:
            break
        x = evecs[:, :k] / np.maximum(cnorm[:, k - 1:k], 1e-12)
        tried[k] = _runs(_kmeans(x, k), MIN_SEGMENT_BEATS)
    if not tried:
        return [[0, 0]], bounds[:-1], {"clusters": 1, "tried": {}}
    k = min(tried, key=lambda k: (abs(len(tried[k]) - target), k))
    return tried[k], bounds[:-1], {"clusters": k, "tried": {str(k): len(r) for k, r in tried.items()}}


def name_segments(feats: list[dict], have_vocals: bool) -> list[str]:
    """allin1 labels for the segments from their stem levels (module docstring). feats: per segment "cluster",
    "loud_db" (mix level), "vocals" (share of blocks with vocals) and "guitar_db" (guitar against the mix)."""
    n = len(feats)
    labels = [""] * n
    loud_mid = float(np.median([f["loud_db"] for f in feats]))
    guitars = [f["guitar_db"] for f in feats if f["guitar_db"] is not None]
    guitar_mid = float(np.median(guitars)) if guitars else None
    sung = [not have_vocals or f["vocals"] >= VOCAL_SHARE for f in feats]
    for i, f in enumerate(feats):
        if sung[i]:
            continue
        if i == 0:
            labels[i] = "intro"
        elif i == n - 1:
            labels[i] = "outro"
        elif guitar_mid is not None and f["guitar_db"] - guitar_mid >= SOLO_DB:
            labels[i] = "solo"
        elif f["loud_db"] - loud_mid <= QUIET_DB:
            labels[i] = "break"
        else:
            labels[i] = "inst"
    if not have_vocals:  # no vocal stem: the ends are the intro and the outro
        labels[0] = "intro"
        if n > 1:
            labels[-1] = "outro"
    vocal = [i for i in range(n) if not labels[i]]
    counts: dict[int, list[int]] = {}
    for i in vocal:
        counts.setdefault(feats[i]["cluster"], []).append(i)
    repeated = [c for c, idx in counts.items() if len(idx) > 1]
    loudness = {c: float(np.mean([feats[i]["loud_db"] for i in idx])) for c, idx in counts.items()}
    if repeated:
        if have_vocals:   # the loudest cluster that repeats
            chorus = max(repeated, key=lambda c: (loudness[c], len(counts[c]), -c))
        else:             # the most repeated, the louder on a tie
            chorus = max(repeated, key=lambda c: (len(counts[c]), loudness[c], -c))
    else:
        chorus = None
    choruses = counts.get(chorus, []) if chorus is not None else []
    for i in vocal:
        labels[i] = "chorus" if i in choruses else "verse"
    if len(choruses) >= 2:  # a cluster heard once between two choruses: the bridge (the longest such one)
        once = [i for i in vocal if len(counts[feats[i]["cluster"]]) == 1 and choruses[0] < i < choruses[-1]]
        if once:
            labels[max(once, key=lambda i: (feats[i]["end"] - feats[i]["start"], -i))] = "bridge"
    return labels


def _librosa(mix, stems, out: Path, s: Settings, beats, why: list[str]) -> SectionsResult:
    import librosa
    import scipy
    from scipy.signal import resample_poly
    guitar_stem = "guitar" if "guitar" in stems else ("other" if "other" in stems else None)
    arrays = {"mix": mix, **{k: stems[k] for k in ("vocals", guitar_stem) if k is not None and k in stems}}
    duration = mix.shape[1] / SAMPLE_RATE
    if beats is not None:  # only the beats inside the audio: a tempo map's lead-in is before 0 s
        beats = np.asarray(beats, dtype=np.float64)
        beats = beats[(beats >= 0) & (beats <= duration)]
        arrays["beats"] = beats.astype(np.float32)
    params = {"backend": "librosa", "engine": ENGINE_VERSION, "librosa": librosa.__version__,
              "seconds_per_segment": s.seconds_per_segment, "rate": SAMPLE_RATE, "guitar": guitar_stem,
              "constants": _fallback_constants()}
    key = cache_key(arrays, params)
    live = {"why": "; ".join(why), "settings": asdict(s)}
    hit = _cached(out, key, live)
    if hit is not None:
        return hit
    t0 = time.perf_counter()  # reported only
    y = resample_poly(_mono(mix), 1, SAMPLE_RATE // FEATURE_RATE).astype(np.float32)
    # the music: from the first to the last frame within SILENCE_DB of the loudest
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
    loud = np.flatnonzero(_db(rms ** 2) >= _db(float(np.max(rms)) ** 2) + SILENCE_DB)
    if not len(loud):
        raise InputError("the mix is silent")
    first = float(librosa.frames_to_time(loud[0], sr=FEATURE_RATE, hop_length=HOP))
    last = min(duration, float(librosa.frames_to_time(loud[-1] + 1, sr=FEATURE_RATE, hop_length=HOP)))
    if beats is None:
        _, frames = librosa.beat.beat_track(y=y, sr=FEATURE_RATE, hop_length=HOP, trim=False)
        beat_source = "librosa"
    else:
        frames = librosa.time_to_frames(beats, sr=FEATURE_RATE, hop_length=HOP)
        beat_source = "given"
    frames = np.unique(np.asarray(frames, dtype=int))
    if len(frames) < 2 * MIN_SEGMENT_BEATS:  # no usable beats: half-second columns instead
        frames = np.arange(0, len(rms), max(1, int(round(0.5 * FEATURE_RATE / HOP))))
        beat_source = "none (0.5 s columns)"
    target = max(1, round((last - first) / s.seconds_per_segment))
    runs, starts, chosen = laplacian_segments(y, frames, target)
    times = librosa.frames_to_time(starts, sr=FEATURE_RATE, hop_length=HOP)
    inside = [(float(times[c]), cl) for c, cl in runs if first < times[c] < last]
    before = [cl for c, cl in runs if times[c] <= first]  # the run playing when the music starts
    bounds = [first] + [t for t, _ in inside] + [last]
    clusters = before[-1:] + [cl for _, cl in inside]
    # levels per segment, in BLOCK_S blocks of the 44.1 kHz arrays
    block = int(BLOCK_S * SAMPLE_RATE)
    p_mix = _block_power(mix, block)
    p_voc = _block_power(stems["vocals"], block) if "vocals" in stems else None
    p_gtr = _block_power(stems[guitar_stem], block) if guitar_stem else None
    feats = []
    for (a, b), cl in zip(zip(bounds, bounds[1:]), clusters):
        i, j = int(a / BLOCK_S), max(int(a / BLOCK_S) + 1, int(np.ceil(b / BLOCK_S)))
        f = {"start": round(a, 3), "end": round(b, 3), "cluster": int(cl),
             "loud_db": round(float(_db(np.mean(p_mix[i:j]))), 2), "vocals": None, "guitar_db": None}
        if p_voc is not None:
            f["vocals"] = round(float(np.mean(_db(p_voc[i:j]) - _db(p_mix[i:j]) >= VOCALS_DB)), 3)
        if p_gtr is not None:
            f["guitar_db"] = round(float(_db(np.mean(p_gtr[i:j])) - _db(np.mean(p_mix[i:j]))), 2)
        feats.append(f)
    labels = name_segments(feats, p_voc is not None)
    for f, lab in zip(feats, labels):
        f["label"] = lab
    segs = ([[0.0, round(first, 3), "start"]] if first > 0 else [])
    segs += [[f["start"], f["end"], f["label"]] for f in feats]
    segs += ([[round(last, 3), round(duration, 3), "end"]] if last < duration else [])
    info = {"engine": "sections", "engine_version": ENGINE_VERSION, "key": key, "backend": "librosa", **live,
            "cached": False,
            "input": {"duration_s": round(duration, 3), "stems": sorted(stems), "guitar": guitar_stem},
            "librosa": {"version": librosa.__version__, "numpy": np.__version__, "scipy": scipy.__version__,
                        "beats": beat_source, "beat_count": int(len(frames)), "target_segments": target,
                        "music": [round(first, 3), round(last, 3)], **chosen, "segments": feats},
            "seconds": {"total": round(time.perf_counter() - t0, 2)}, "segments": len(segs)}
    return _save(out, {"segments": segs}, info)
