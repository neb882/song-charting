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
    `model="auto"` is fold 0 on the CPU and the 8-fold ensemble on CUDA. The checkpoints come from the Hugging Face
    hub at a pinned revision, downloaded on first use; each is checked against its SHA-256 before the runner loads
    it (they are pickles: the check is what makes loading them safe). CUDA out of memory falls back to the CPU, and
    engine.json says so.
  * **librosa** (numpy, scipy and librosa only), for when allin1 is not available. Laplacian structural
    segmentation (McFee and Ellis 2014, as in librosa's gallery) on beat-synchronous CQT and MFCC; the cluster
    count is the one whose segments, after those under 16 beats merge, come closest to one per
    `seconds_per_segment` (25) of music. Names come from the stems: no vocals at the start is the intro and at
    the end the outro; elsewhere no vocals is a solo when the guitar (else "other") stem is clearly louder than
    usual, a break when the song is quiet, else an instrumental; of the clusters with vocals, the loudest one that
    repeats is the chorus, a cluster heard once between two choruses the bridge, the rest verses. Without stems:
    intro, outro, the most repeated cluster as the chorus, verses. The naming rules are untested guesses.
  * **Choice.** `backend="auto"` takes allin1 when its Python is set, its probe passes and the run succeeds, else
    the fallback; engine.json records the backend and why. `backend="allin1"` raises instead of falling back.
  * **Cache.** engine.json holds a key of the samples the backend read and every setting that changes the result
    (the allin1 package and version, the model and its weights' hashes, the device; the librosa version and the
    fallback's parameters and constants). A call whose key matches the folder's engine.json returns the files
    already there; for allin1 the probe still runs first (a few seconds), since its answer is part of the key.

The fallback needs librosa (`pip install songcharter[sections]`). allin1 needs a Python with all-in-one-infer
(`pip install all-in-one-infer`: pure Python, nothing to compile), either this one or one of its own.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

import numpy as np

from .. import audio as A
from ..sections import Segment, read_allin1

SAMPLE_RATE = A.SAMPLE_RATE
ENGINE_VERSION = 1          # part of the key: bump it when a change here changes the segments
ENV_PYTHON = "SONGCHARTER_ALLIN1_PYTHON"
ALLIN1_MODULES = ("allin1_infer", "allin1")   # all-in-one-infer, else the original allin1 (allin1_runner.PACKAGES)
RUNNER = Path(__file__).with_name("allin1_runner.py")
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
ALLIN1_STEMS = ("bass", "drums", "other", "vocals")   # allin1's four; every other stem folds into "other"
PROBE_TIMEOUT_S = 300

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


class Allin1Error(RuntimeError):
    """allin1 is not available here, or its run failed."""


@dataclass(frozen=True)
class Settings:
    backend: str = "auto"              # "auto" (allin1 if it works, else librosa), "allin1" or "librosa"
    model: str = "auto"                # allin1: "auto" (fold 0 on the CPU, the ensemble on CUDA), or a name in
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


def _cached(out: Path, key: str) -> SectionsResult | None:
    """The result already in `out` for this key, else None."""
    try:
        info = json.loads((out / ENGINE).read_text(encoding="utf-8"))
        if info.get("key") != key:
            return None
        read_allin1(out / SEGMENTS)
    except (OSError, ValueError):
        return None
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


def allin1_python(settings: Settings) -> str | None:
    """The Python to run allin1 in: the setting, $SONGCHARTER_ALLIN1_PYTHON, or this one when it has allin1."""
    if settings.python or os.environ.get(ENV_PYTHON):
        return settings.python or os.environ[ENV_PYTHON]
    if any(importlib.util.find_spec(m) is not None for m in ALLIN1_MODULES):
        return sys.executable
    return None


def probe(python: str, run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> dict:
    """What the allin1 Python has: package, version, torch, cuda, attention. Allin1Error when it cannot run it."""
    with tempfile.TemporaryDirectory(prefix="allin1-probe-") as tmp:
        out = Path(tmp) / "probe.json"
        try:
            proc = run([python, "-I", str(RUNNER), "probe", str(out)], capture_output=True, text=True,
                       timeout=PROBE_TIMEOUT_S)
        except (OSError, subprocess.SubprocessError) as e:
            raise Allin1Error(f"allin1's Python {python} did not run ({type(e).__name__}: {e})") from e
        if proc.returncode != 0 or not out.is_file():
            raise Allin1Error(f"allin1's Python {python} failed its probe (exit {proc.returncode}):\n{_tail(proc)}")
        return json.loads(out.read_text(encoding="utf-8"))


def _check(mix: np.ndarray, stems: Mapping[str, np.ndarray] | None, sample_rate: int, settings: Settings) -> None:
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


def find_sections(mix: np.ndarray, stems: Mapping[str, np.ndarray] | None, out: Path | str,
                  settings: Settings = Settings(), *, sample_rate: int = SAMPLE_RATE, beats: np.ndarray | None = None,
                  run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                  download: Callable[..., str] | None = None) -> SectionsResult:
    """Segments of the song in out/segments.json and how they were made in out/engine.json (module docstring).

    mix:   the decoded song, float32 (channels, n) at 44.1 kHz; stems: name -> array of the same shape (or None).
    beats: beat times in seconds for the fallback's beat-synchronous features (default: librosa's tracker).
    run, download: stand-ins for subprocess.run and huggingface_hub's hf_hub_download (tests).
    """
    _check(mix, stems, sample_rate, settings)
    out = Path(out)
    why = []
    if settings.backend in ("auto", "allin1"):
        try:
            return _allin1(mix, stems or {}, out, settings, run, download)
        except Allin1Error as e:
            if settings.backend == "allin1":
                raise
            why.append(str(e))
    elif settings.backend == "librosa":
        why.append("backend librosa asked for")
    return _librosa(mix, stems or {}, out, settings, beats, why)


# ------------------------------------------------------------------------------------------------------------ allin1

def _allin1(mix, stems, out: Path, s: Settings, run, download) -> SectionsResult:
    python = allin1_python(s)
    if python is None:
        raise Allin1Error(f"no allin1 Python: set {ENV_PYTHON} to a Python with all-in-one-infer (or allin1)")
    payload = allin1_input(stems)
    found = probe(python, run)
    device = s.device if s.device != "auto" else ("cuda" if found.get("cuda") else "cpu")
    if device == "cuda" and not found.get("cuda"):
        raise Allin1Error(f"device cuda asked for, but allin1's Python {python} has no CUDA")
    model = s.model if s.model != "auto" else ("harmonix-all" if device == "cuda" else "harmonix-fold0")
    weights = {ALLIN1_FOLDS[f][0]: ALLIN1_FOLDS[f][1] for f in ALLIN1_MODELS[model]}
    key = cache_key({"stems": payload}, {"backend": "allin1", "engine": ENGINE_VERSION, "package": found.get("package"),
                           "version": found.get("version"), "model": model, "weights": weights, "device": device,
                           "rate": SAMPLE_RATE})
    hit = _cached(out, key)
    if hit is not None:
        return hit
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
        try:
            proc = run([python, "-I", str(RUNNER), "run", str(work / "job.json")], capture_output=True,
                       input=payload.astype("<i2").tobytes(), timeout=s.timeout_s)
        except (OSError, subprocess.SubprocessError) as e:
            raise Allin1Error(f"allin1 did not finish ({type(e).__name__}: {e})") from e
        if proc.returncode != 0 or not (work / "result.json").is_file():
            raise Allin1Error(f"allin1 failed (exit {proc.returncode}):\n{_tail(proc)}")
        res = json.loads((work / "result.json").read_text(encoding="utf-8"))
    seconds = round(time.perf_counter() - t0, 2)
    segments = {"segments": res["segments"], "bpm": res.get("bpm"), "beats": res.get("beats"),
                "downbeats": res.get("downbeats")}
    info = {"engine": "sections", "engine_version": ENGINE_VERSION, "key": key, "backend": "allin1",
            "why": f"backend {s.backend}: allin1's Python {python} passed its probe",
            "settings": {**asdict(s), "python": python},
            "input": {"duration_s": round(mix.shape[1] / SAMPLE_RATE, 3), "stems": sorted(stems),
                      "other": sorted(n for n in stems if n not in ("bass", "drums", "vocals"))},
            "allin1": {**found, "model": model, "device": res.get("device", device), "fallback": res.get("fallback"),
                       "threads": res.get("threads"), "repo": ALLIN1_REPO, "revision": ALLIN1_REVISION,
                       "weights": weights, "attention": res.get("attention", found.get("attention"))},
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
    return tried[k], bounds[:-1], {"clusters": k, "tried": {k: len(r) for k, r in tried.items()}}


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
    if beats is not None:
        arrays["beats"] = np.asarray(beats, dtype=np.float32)
    params = {"backend": "librosa", "engine": ENGINE_VERSION, "librosa": librosa.__version__,
              "seconds_per_segment": s.seconds_per_segment, "rate": SAMPLE_RATE, "guitar": guitar_stem,
              "constants": _fallback_constants()}
    key = cache_key(arrays, params)
    hit = _cached(out, key)
    if hit is not None:
        return hit
    t0 = time.perf_counter()  # reported only
    duration = mix.shape[1] / SAMPLE_RATE
    y = resample_poly(_mono(mix), 1, SAMPLE_RATE // FEATURE_RATE).astype(np.float32)
    # the music: from the first to the last frame within SILENCE_DB of the loudest
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
    loud = np.flatnonzero(_db(rms ** 2) >= _db(float(np.max(rms)) ** 2) + SILENCE_DB)
    if not len(loud):
        raise ValueError("the mix is silent")
    first = float(librosa.frames_to_time(loud[0], sr=FEATURE_RATE, hop_length=HOP))
    last = min(duration, float(librosa.frames_to_time(loud[-1] + 1, sr=FEATURE_RATE, hop_length=HOP)))
    if beats is None:
        _, frames = librosa.beat.beat_track(y=y, sr=FEATURE_RATE, hop_length=HOP, trim=False)
        beat_source = "librosa"
    else:
        frames = librosa.time_to_frames(np.asarray(beats, dtype=np.float64), sr=FEATURE_RATE, hop_length=HOP)
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
    info = {"engine": "sections", "engine_version": ENGINE_VERSION, "key": key, "backend": "librosa",
            "why": "; ".join(why), "settings": asdict(s),
            "input": {"duration_s": round(duration, 3), "stems": sorted(stems), "guitar": guitar_stem},
            "librosa": {"version": librosa.__version__, "numpy": np.__version__, "scipy": scipy.__version__,
                        "beats": beat_source, "beat_count": int(len(frames)), "target_segments": target,
                        "music": [round(first, 3), round(last, 3)], **chosen, "segments": feats},
            "seconds": {"total": round(time.perf_counter() - t0, 2)}, "segments": len(segs)}
    return _save(out, {"segments": segs}, info)
