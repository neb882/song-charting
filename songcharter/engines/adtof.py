"""Drums from ADTOF's Frame_RNN (Zehren et al. 2023), run as our own PyTorch module (DESIGN.md 2.9, Goal 2).

    result = generate(mix, drums, "work/drums")   # mix and drum stem: float32 (2, n) at 44.1 kHz, sample-aligned
    song = importers.read_song(result.folder)      # its Expert drums, in seconds of the decode (time_offset 0)

  * **Licence.** This module is a separate component, treated as CC BY-NC-SA 4.0 (DESIGN.md 4.2, 9 Q15). Its
    network, input features and peak picking come from the research port written from reading xavriley/
    ADTOF-pytorch, an unlicensed port of ADTOF, whose whole repository is BY-NC-SA; the weights are BY-NC-SA by
    inheritance. Nothing of either repository is vendored, and the weights are downloaded on first use. The fusion
    and the lane mapping (drumlanes.py) are our own and not part of this component.
  * **Model.** Frame_RNN: two convolution blocks and three bidirectional GRUs on a log-filtered spectrogram (84
    semitone bands, 100 frames a second), giving per-frame activations for kick (BD), snare (SD), toms (TT),
    hi-hat (HH) and cymbals (CY). Peaks are picked per class with a variant of madmom's NotePeakPickingProcessor
    at ADTOF's settings (peaks() says how it differs). The convolutions run in blocks of frames (exact: they see 4
    frames either side), so a long song needs little memory.
  * **Weights.** The converted 3.6 MB state dict at a pinned commit of xavriley/ADTOF-pytorch, checked against its
    SHA-256 whether downloaded or already in the models folder, and loaded with torch.load(weights_only=True).
  * **Signals.** The model runs on the drum stem and on the mix; drumlanes.py takes kick, snare and toms from the
    stem and hi-hat and cymbals from the mix, and maps the hits to pro-drum lanes.
  * **Output.** out/notes.chart (Expert drums only, on a constant 120 BPM map at resolution 480, so 1 tick is
    1.04 ms and the quantizer sees the hits' own times), out/song.ini (pro_drums = True) and out/engine.json (the
    settings, versions, counts and timings). out/activations.npz keeps the model's activations.
  * **Cache.** A folder whose engine.json holds the same key (the samples, the weights, every setting and the beat
    period used) is reused as it is. The beat period is in the key because, unless settings.beat_s gives it, it is
    beatgrid's tempo estimate, which lives outside this engine and its version; so a run estimates it before
    looking (a few seconds a song). The activations are reused for the same samples and weights when only lane
    settings change.

Needs torch (`pip install songcharter[drums]`, or [separate], which brings it too); importing this module does not.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .. import audio as A
from ..chart import Chart, SongInfo, Track, write_chart
from ..ini import write_ini
from ..tempo import Tempo, TempoMap
from . import drumlanes as L

ENGINE_VERSION = "adtof-1"   # bump when the output for the same input and settings changes
SAMPLE_RATE = A.SAMPLE_RATE
FPS = 100                    # activation frames per second
HOP = SAMPLE_RATE // FPS     # 441 samples
N_FFT = 2048
LABELS = L.LABELS            # BD, SD, TT, HH, CY: the model's outputs, in order
CNN_BLOCK = 4096             # frames per convolution block
CNN_HALO = 4                 # frames of context each side: four 3x3 convolutions
# ADTOF's settings for madmom's NotePeakPickingProcessor (seconds): moving average, moving maximum, combine
PEAK_PRE_AVG, PEAK_POST_AVG, PEAK_PRE_MAX, PEAK_POST_MAX, PEAK_COMBINE = 0.1, 0.01, 0.02, 0.01, 0.02
CHART_RESOLUTION, CHART_BPM_MILLI = 480, 120000   # 960 ticks a second


@dataclass(frozen=True)
class Weights:
    url: str             # at a pinned commit
    sha256: str
    file: str


WEIGHTS = Weights("https://raw.githubusercontent.com/xavriley/ADTOF-pytorch/85c192e78f716ea0b111cc8a5ee4a8f6a3a4f8a9/"
                  "src/adtof_pytorch/data/adtof_frame_rnn_pytorch_weights.pth",
                  "1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320",
                  "adtof_frame_rnn_pytorch_weights.pth")  # 3,617,805 bytes


@dataclass(frozen=True)
class Result:
    folder: Path
    chart: Path          # notes.chart
    info: dict           # engine.json
    cached: bool


# ------------------------------------------------------------------------------------------------ weights

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def models_dir() -> Path:
    """Where downloaded weights live: $SONGCHARTER_MODELS, else %LOCALAPPDATA%\\songcharter\\models on Windows, else
    $XDG_CACHE_HOME (or ~/.cache)/songcharter/models."""
    if os.environ.get("SONGCHARTER_MODELS"):
        return Path(os.environ["SONGCHARTER_MODELS"])
    if sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "songcharter" / "models"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "songcharter" / "models"


def _download(url: str, dest: Path, attempts: int = 3) -> None:
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
                for block in iter(lambda: r.read(1 << 20), b""):
                    f.write(block)
            return
        except OSError:
            if i == attempts - 1:
                raise


def weights_path(models: Path | str | None = None, download: Callable[[str, Path], None] | None = None) -> Path:
    """The pinned weights file, models/adtof/<file> (models: models_dir() by default), downloaded on first use to a
    .part file and renamed once its SHA-256 matches. A file already there is checked too. SONGCHARTER_OFFLINE=1
    forbids the download."""
    path = Path(models or models_dir()) / "adtof" / WEIGHTS.file
    if not path.is_file():
        if os.environ.get("SONGCHARTER_OFFLINE") == "1":
            raise FileNotFoundError(f"the ADTOF weights are not in {path.parent} and SONGCHARTER_OFFLINE=1")
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        (download or _download)(WEIGHTS.url, part)
        got = _sha256(part)
        if got != WEIGHTS.sha256:
            part.unlink()
            raise RuntimeError(f"the ADTOF weights from {WEIGHTS.url} have SHA-256 {got}, not the pinned "
                               f"{WEIGHTS.sha256}")
        os.replace(part, path)
        return path
    got = _sha256(path)
    if got != WEIGHTS.sha256:
        raise RuntimeError(f"{path} has SHA-256 {got}, not the pinned {WEIGHTS.sha256}; delete it and run again")
    return path


# ------------------------------------------------------------------------------------------------ features

def filterbank() -> np.ndarray:
    """Triangular filters on semitones from 20 Hz to 20 kHz over the STFT bins, each normalised to sum 1:
    shape (84, N_FFT // 2). Semitones that fall on the same bin are one filter."""
    freqs, f = [], 20.0
    while f <= 20000 * (1 + 1e-12):
        freqs.append(f)
        f *= 2 ** (1 / 12)
    fft = np.fft.fftfreq(N_FFT, 1 / SAMPLE_RATE)[:N_FFT // 2]
    bins: list[int] = []
    for x in freqs:
        b = int(np.argmin(np.abs(fft - x)))
        if not bins or b > bins[-1]:
            bins.append(b)
    fb = np.zeros((len(bins) - 2, len(fft)), np.float32)
    for i in range(len(bins) - 2):
        lo, mid, hi = bins[i], bins[i + 1], bins[i + 2]
        if hi - lo < 2:
            fb[i, lo] = 1
            continue
        for k in range(lo, mid):
            fb[i, k] = (k - lo) / (mid - lo)
        fb[i, mid] = 1
        for k in range(mid + 1, hi):
            fb[i, k] = (hi - k) / (hi - mid)
    s = fb.sum(1, keepdims=True)
    s[s == 0] = 1
    return fb / s


def band_hz() -> np.ndarray:
    """Each filter's centre frequency (Hz)."""
    fb = filterbank()
    fft = np.fft.fftfreq(N_FFT, 1 / SAMPLE_RATE)[:N_FFT // 2]
    return fft[np.argmax(fb, axis=1)]


def features(x: np.ndarray, block_frames: int = 4096) -> np.ndarray:
    """The model's input for mono float32 audio at 44.1 kHz: log10(1 + filterbank @ |STFT|), shape (frames, 84).

    The STFT is librosa's with center=True and zero padding: 2048-point frames under a symmetric Hann window
    (np.hanning), hop 441, so frame i is centred at i / 100 s and there are 1 + n // 441 frames.
    """
    x = np.asarray(x, dtype=np.float32)
    if x.ndim != 1:
        raise ValueError(f"features need mono audio, not shape {x.shape}")
    n_frames = 1 + len(x) // HOP
    pad = np.zeros(len(x) + N_FFT, dtype=np.float32)
    pad[N_FFT // 2:N_FFT // 2 + len(x)] = x
    frames = np.lib.stride_tricks.sliding_window_view(pad, N_FFT)[::HOP][:n_frames]
    window = np.hanning(N_FFT).astype(np.float32)
    fb = filterbank()
    out = np.empty((n_frames, fb.shape[0]), dtype=np.float32)
    for s in range(0, n_frames, block_frames):
        e = min(n_frames, s + block_frames)
        mag = np.abs(np.fft.rfft(frames[s:e] * window, axis=1))[:, :N_FFT // 2]
        out[s:e] = np.log10(1 + mag @ fb.T)
    return out


# ------------------------------------------------------------------------------------------------ model

def _modules():
    import torch
    from torch import nn

    class Pool(nn.Module):
        """Max pool of 3 over frequency with Keras's "same" padding (zeros, as the port pads)."""

        def forward(self, x):
            f = x.shape[-1]
            pad = max(0, ((f + 2) // 3 - 1) * 3 + 3 - f)
            x = nn.functional.pad(x, (pad // 2, pad - pad // 2, 0, 0))
            return nn.functional.max_pool2d(x, (1, 3), (1, 3))

    class FrameRNN(nn.Module):
        """ADTOF's Frame_RNN; parameter names follow the converted state dict."""

        def __init__(self):
            super().__init__()

            def block(i, o):
                return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(o, eps=1e-3),
                                     nn.Conv2d(o, o, 3, padding=1), nn.ReLU(), nn.BatchNorm2d(o, eps=1e-3), Pool(),
                                     nn.Dropout2d(0.3))

            self.cnn_blocks = nn.ModuleList([block(1, 32), block(32, 64)])
            self.gru_layers = nn.ModuleList([nn.GRU(640, 60, batch_first=True, bidirectional=True),
                                             nn.GRU(120, 60, batch_first=True, bidirectional=True),
                                             nn.GRU(120, 60, batch_first=True, bidirectional=True)])
            self.output_layer = nn.Linear(120, len(LABELS))

        def cnn(self, x):
            """(batch, frames, 84) -> (batch, frames, 640)."""
            x = x[:, None]
            for b in self.cnn_blocks:
                x = b(x)
            n, c, t, f = x.shape
            return x.permute(0, 2, 3, 1).reshape(n, t, f * c)

        def rnn(self, x):
            """(batch, frames, 640) -> activations (batch, frames, 5) in [0, 1]."""
            for g in self.gru_layers:
                x, _ = g(x)
            return torch.sigmoid(self.output_layer(x))

        def forward(self, x):
            return self.rnn(self.cnn(x))

    return FrameRNN


def frame_rnn():
    """An untrained FrameRNN (tests; load_model gives the trained one)."""
    return _modules()()


def load_model(path: Path | str | None = None, models: Path | str | None = None, device: str = "cpu"):
    """The FrameRNN with the pinned weights (path: a checked weights file; default weights_path(models)), in eval
    mode on `device`."""
    import torch
    path = Path(path) if path is not None else weights_path(models)
    net = frame_rnn()
    state = torch.load(path, map_location="cpu", weights_only=True)
    net.load_state_dict(state["model_weights"], strict=True)
    return net.eval().to(device)


def activations(model, feat: np.ndarray, device: str = "cpu") -> np.ndarray:
    """Per-frame activations, shape (frames, 5) float32, of features(x)."""
    import torch
    n = len(feat)
    with torch.no_grad():
        f = torch.from_numpy(np.ascontiguousarray(feat, dtype=np.float32))[None].to(device)
        parts = []
        for s in range(0, n, CNN_BLOCK):
            a, e = max(0, s - CNN_HALO), min(n, s + CNN_BLOCK + CNN_HALO)
            parts.append(model.cnn(f[:, a:e])[:, s - a:s - a + min(CNN_BLOCK, n - s)])
        out = model.rnn(torch.cat(parts, dim=1))[0]
    return out.cpu().numpy().astype(np.float32)


# ------------------------------------------------------------------------------------------------ peaks

def peaks(act: np.ndarray, threshold: float, fps: int = FPS) -> np.ndarray:
    """Peak frames of one class's activations: the activation minus its moving average (0.1 s before, 0.01 s after)
    must reach `threshold` and be the maximum of its window (0.02 s before, 0.01 s after); peaks within 0.02 s of
    each other keep the strongest (the first of equals).

    A variant of madmom's NotePeakPickingProcessor at ADTOF's settings. Its threshold test is madmom's, so ADTOF's
    thresholds select the same frames; it differs in two ways. It takes the maximum of the activation minus its
    average, where madmom takes that of the raw activation, and a chain of peaks keeps its strongest, where madmom
    keeps the first within 0.02 s. So on the reference songs about 5.6 % of peaks come one frame (10 ms) earlier
    than madmom's, with no measurable change in score."""
    a = np.asarray(act, dtype=np.float32)
    la, ra = int(round(PEAK_PRE_AVG * fps)), int(round(PEAK_POST_AVG * fps))
    k = np.ones(la + ra + 1, np.float32) / (la + ra + 1)
    p = np.maximum(0, a - np.convolve(np.pad(a, (la, ra), mode="edge"), k, "valid"))
    lm, rm = int(round(PEAK_PRE_MAX * fps)), int(round(PEAK_POST_MAX * fps))
    wmax = np.lib.stride_tricks.sliding_window_view(np.pad(p, (lm, rm), mode="edge"), lm + rm + 1).max(axis=1)
    idx = np.flatnonzero((p >= wmax) & (p >= threshold))
    if len(idx) == 0:
        return idx
    combine = max(1, int(round(PEAK_COMBINE * fps)))
    kept, group = [], [idx[0]]
    for i in idx[1:]:
        if i - group[-1] <= combine:
            group.append(i)
        else:
            kept.append(max(group, key=lambda j: p[j]))
            group = [i]
    kept.append(max(group, key=lambda j: p[j]))
    return np.array(kept, dtype=np.int64)


# ------------------------------------------------------------------------------------------------ the engine

def _samples_hash(*arrays: np.ndarray):
    h = hashlib.sha256()
    for a in arrays:
        a = np.ascontiguousarray(a, dtype="<f4")
        h.update(repr(a.shape).encode())
        h.update(a.tobytes())
    return h


def cache_key(mix: np.ndarray, drums: np.ndarray, weights: str, settings: L.Settings, beat_s: float) -> str:
    """A hash of the samples, the weights, every setting and the beat period used for ride or crash (settings.beat_s,
    or beatgrid's estimate, which a beatgrid change can move without a new ENGINE_VERSION)."""
    h = _samples_hash(mix, drums)
    h.update(repr((ENGINE_VERSION, weights, sorted(asdict(settings).items()), float(beat_s), SAMPLE_RATE)).encode())
    return h.hexdigest()[:24]


def activations_key(mix: np.ndarray, drums: np.ndarray, weights: str) -> str:
    h = _samples_hash(mix, drums)
    h.update(repr((ENGINE_VERSION, weights, FPS, N_FFT, SAMPLE_RATE)).encode())
    return h.hexdigest()[:24]


def _state_sha(model) -> str:
    """For a model passed in (tests): a hash of its parameters."""
    h = hashlib.sha256()
    for k, v in sorted(model.state_dict().items()):
        h.update(k.encode())
        h.update(np.ascontiguousarray(v.detach().cpu().numpy()).tobytes())
    return "state:" + h.hexdigest()[:24]


def _cached(folder: Path, key: str) -> dict | None:
    """engine.json of a finished run in `folder` with this key, else None."""
    meta = folder / "engine.json"
    if not (meta.is_file() and (folder / "notes.chart").is_file() and (folder / "song.ini").is_file()):
        return None
    try:
        info = json.loads(meta.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return info if info.get("key") == key else None


def chart_of(hits: list, info: SongInfo | None = None) -> Chart:
    """The Expert drums chart of drumlanes hits on the engine's constant tempo map."""
    tm = TempoMap(CHART_RESOLUTION, [Tempo(0, CHART_BPM_MILLI)])
    per_second = CHART_RESOLUTION * CHART_BPM_MILLI / 60000
    notes = L.drum_hits(hits, lambda t: int(round(t * per_second)))
    info = info or SongInfo("ADTOF drums", "songcharter", charter="songcharter adtof engine")
    return Chart(info, tm, [], [Track("Expert", "Drums", notes)])


def generate(mix: np.ndarray, drums: np.ndarray, out: Path | str, settings: L.Settings = L.Settings(), *,
             model: Any = None, models: Path | str | None = None, device: str = "cpu") -> Result:
    """Expert drums of the song in `out` (notes.chart, song.ini, engine.json, activations.npz).

    mix, drums: the decode and its drum stem, float32 (2, n) at 44.1 kHz (sample-aligned, as separate.py gives).
    model: None for the pinned weights (from `models`, downloaded on first use), or a FrameRNN object (tests).
    A folder already holding this key's output is returned as it is (cached). The key holds the beat period, so
    with settings.beat_s None the mix's tempo is estimated first, a cached run included.
    """
    if mix.ndim != 2 or mix.shape[0] != 2 or drums.shape != mix.shape:
        raise ValueError(f"generate needs a stereo (2, n) mix and a drum stem of the same shape, not {mix.shape} "
                         f"and {drums.shape}")
    settings.check()
    out = Path(out)
    t0 = time.perf_counter()  # wall times are reported only; nothing depends on them
    weights = WEIGHTS.sha256 if model is None else _state_sha(model)
    beat_s, beat_from = settings.beat_s, "settings"
    if beat_s is None:
        beat_s, beat_from = L.beat_period(mix), "mix"
    beat_seconds = round(time.perf_counter() - t0, 2)
    key = cache_key(mix, drums, weights, settings, beat_s)
    info = _cached(out, key)
    if info is not None:
        return Result(out, out / "notes.chart", info, True)
    out.mkdir(parents=True, exist_ok=True)
    (out / "engine.json").unlink(missing_ok=True)  # a run cut off below must not pass for another key's output
    import torch
    seconds: dict[str, float] = {"beat": beat_seconds}
    m_mono, s_mono = mix.mean(axis=0), drums.mean(axis=0)
    t = time.perf_counter()
    feat = {"mix": features(m_mono), "stem": features(s_mono)}
    seconds["features"] = round(time.perf_counter() - t, 2)

    akey = activations_key(mix, drums, weights)
    act_file = out / "activations.npz"
    act = None
    if act_file.is_file():
        with np.load(act_file) as z:
            if str(z["key"]) == akey:
                act = {"mix": z["mix"], "stem": z["stem"]}
    cached_act = act is not None
    if act is None:
        net = load_model(models=models, device=device) if model is None else model.eval().to(device)
        t = time.perf_counter()
        act = {k: activations(net, feat[k], device) for k in ("mix", "stem")}
        seconds["model"] = round(time.perf_counter() - t, 2)
        tmp = out / "activations.part.npz"
        np.savez_compressed(tmp, key=np.array(akey), mix=act["mix"], stem=act["stem"])
        os.replace(tmp, act_file)

    t = time.perf_counter()
    found = {}
    for i, lab in enumerate(LABELS):
        a = act["mix" if lab in settings.from_mix else "stem"][:, i]
        f = peaks(a, settings.thresholds[i])
        found[lab] = (f, a[f].astype(np.float64))
    level = None if settings.hat_gate_db is None else L.stem_level_db(feat["stem"], feat["mix"], band_hz(), settings,
                                                                       FPS)
    hits, counts = L.lanes(found, FPS, settings, beat_s, s_mono, SAMPLE_RATE, level)
    chart = chart_of(hits)
    seconds["lanes"] = round(time.perf_counter() - t, 2)
    seconds["total"] = round(time.perf_counter() - t0, 2)

    (out / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    (out / "song.ini").write_text(write_ini(chart, pro_drums=True), encoding="utf-8", newline="")
    info = {"engine": "adtof", "version": ENGINE_VERSION, "key": key, "activations_key": akey,
            "activations_cached": cached_act, "settings": asdict(settings),
            "weights": {"url": WEIGHTS.url, "sha256": weights} if model is None else {"sha256": weights},
            "input": {"samples": int(mix.shape[1]), "seconds": round(mix.shape[1] / SAMPLE_RATE, 3)},
            "beat_s": round(float(beat_s), 6), "beat_from": beat_from, "counts": counts,
            "notes": len(chart.tracks[0].notes), "device": device, "seconds": seconds,
            "versions": {"python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__},
            "chart": {"resolution": CHART_RESOLUTION, "bpm": CHART_BPM_MILLI / 1000, "difficulties": ["expert"]}}
    (out / "engine.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return Result(out, out / "notes.chart", info, False)
