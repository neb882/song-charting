"""Audio in and out, on one timeline.

Everything is measured against a single gapless decode of the user's file. An MP3 starts with
encoder priming (this tool's first song carries 1105 samples, 25 ms); a decoder that ignores the
LAME header plays the song that much late. So the tool:

  1. decodes the input once with ffmpeg, which honours the header (the time reference),
  2. runs every analysis on that decode,
  3. encodes the song files Clone Hero plays (song.ogg, and guitar.ogg, bass.ogg and drums.ogg from
     the stems when the audio is split: package.py) from the same samples, with the lead-in silence in
     front,
  4. decodes those files back and measures their offset against the reference, window by window.
     The package is only accepted when the offset is under a sample.

Every file written is byte-identical for the same samples (and the same ffmpeg and libsndfile): the
Ogg files with ffmpeg's bitexact flags, which fix the stream serial (random otherwise) and leave the
encoder's version out of the header; the FLAC stems (`write_flac`) carry nothing but the samples and
libFLAC's own vendor string.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .errors import InputError, ToolError

SAMPLE_RATE = 44100
# the audio files Clone Hero (and scan-chart, its hasAudioName) reads in a song folder: these names with one of
# these extensions; preview and crowd are not the song's music (scan-chart leaves them out of its audio too)
SONG_AUDIO_NAMES = ("song", "guitar", "bass", "rhythm", "keys", "vocals", "vocals_1", "vocals_2", "drums", "drums_1",
                    "drums_2", "drums_3", "drums_4", "crowd", "preview")
SONG_AUDIO_EXTENSIONS = (".ogg", ".mp3", ".wav", ".opus")
NOT_MUSIC = ("preview", "crowd")
BITEXACT = ("-fflags", "+bitexact", "-flags:a", "+bitexact")   # a fixed Ogg serial, no version in the header


def ffmpeg_exe() -> str:
    """ffmpeg from $FFMPEG, then PATH, then the imageio-ffmpeg wheel (bundled on Windows installs)."""
    exe = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise ToolError("ffmpeg not found: install it or `pip install imageio-ffmpeg`") from e


def ffmpeg_error(e: subprocess.CalledProcessError) -> str:
    """The last line ffmpeg printed before it failed."""
    text = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else str(e.stderr or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else f"exit status {e.returncode}"


def decode(path, sample_rate: int = SAMPLE_RATE, channels: int = 2) -> np.ndarray:
    """Gapless float32 decode of the first audio stream, shape (channels, samples). A file ffmpeg cannot read is an
    InputError."""
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(path), "-map", "0:a:0",
           "-ac", str(channels), "-ar", str(sample_rate), "-f", "f32le", "-c:a", "pcm_f32le", "pipe:1"]
    try:
        raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    except subprocess.CalledProcessError as e:
        raise InputError(f"ffmpeg could not read {path}: {ffmpeg_error(e)}") from e
    y = np.frombuffer(raw, dtype="<f4")
    if y.size == 0:
        raise InputError(f"no audio decoded from {path}")
    return y.reshape(-1, channels).T.copy()


def pad_front(audio: np.ndarray, samples: int) -> np.ndarray:
    return np.concatenate([np.zeros((audio.shape[0], samples), dtype=audio.dtype), audio], axis=1)


def encode_ogg(audio: np.ndarray, path, sample_rate: int = SAMPLE_RATE, quality: float = 7.0) -> None:
    """Ogg Vorbis (libvorbis, VBR quality 0-10; 7 is about 224 kbps stereo), byte-identical for the same samples
    (BITEXACT). ffmpeg failing is a ToolError."""
    ch = audio.shape[0]
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "f32le", "-ar", str(sample_rate),
           "-ac", str(ch), "-i", "pipe:0", "-c:a", "libvorbis", "-q:a", str(quality), *BITEXACT, "-f", "ogg",
           str(path)]
    data = np.ascontiguousarray(np.clip(audio, -1, 1).T.astype("<f4")).tobytes()
    try:
        subprocess.run(cmd, input=data, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise ToolError(f"ffmpeg could not write {path}: {ffmpeg_error(e)}") from e


@dataclass
class SyncReport:
    offsets: list[tuple[float, float, float]]  # (window centre s, lag in samples (+ = file late), correlation)
    length_difference: int                    # decoded samples minus reference samples

    @property
    def max_abs_lag(self) -> float:
        return max(abs(o[1]) for o in self.offsets) if self.offsets else float("inf")

    @property
    def min_correlation(self) -> float:
        return min(o[2] for o in self.offsets) if self.offsets else 0.0

    @property
    def ok(self) -> bool:
        return bool(self.offsets) and self.max_abs_lag < 1.0 and self.min_correlation > 0.9

    def summary(self) -> str:
        return (f"sync {'OK' if self.ok else 'FAILED'}: worst offset {self.max_abs_lag:.2f} samples over "
                f"{len(self.offsets)} windows, lowest correlation {self.min_correlation:.3f}, "
                f"length difference {self.length_difference} samples")


def measure_offset(reference: np.ndarray, test: np.ndarray, sample_rate: int = SAMPLE_RATE, windows: int = 9,
                   window_s: float = 1.0, max_lag_s: float = 0.1) -> list[tuple[float, float, float]]:
    """Lag of `test` against `reference` (mono mixes) in loud windows across the file.

    Cross-correlation by FFT, with a parabolic fit around the peak for a sub-sample lag. The method
    follows the real-take alignment in neb882/source-VOIP-converter6 (reference.js), much simplified.
    """
    r = reference.mean(axis=0) if reference.ndim == 2 else reference
    t = test.mean(axis=0) if test.ndim == 2 else test
    n = min(len(r), len(t))
    w, L = int(window_s * sample_rate), int(max_lag_s * sample_rate)
    if n < w + 2 * L:
        return []
    # candidate windows: the loudest of evenly spaced slots (silence correlates with nothing)
    slots = np.linspace(L, n - w - L, num=windows * 3).astype(int)
    energy = np.array([np.mean(r[s:s + w] ** 2) for s in slots])
    picks = sorted(slots[np.argsort(energy)[::-1][:windows]])
    out = []
    for s in picks:
        a = r[s:s + w].astype(np.float64)
        b = t[s - L:s + w + L].astype(np.float64)
        if np.mean(a ** 2) < 1e-10:
            continue
        nfft = 1 << int(np.ceil(np.log2(len(a) + len(b))))
        c = np.fft.irfft(np.fft.rfft(b, nfft) * np.conj(np.fft.rfft(a, nfft)), nfft)[:2 * L + 1]
        k = int(np.argmax(c))
        frac = 0.0
        if 0 < k < len(c) - 1:
            y0, y1, y2 = c[k - 1], c[k], c[k + 1]
            den = y0 - 2 * y1 + y2
            frac = 0.5 * (y0 - y2) / den if den else 0.0
        lag = k + frac - L
        seg = b[k:k + w]
        corr = float(np.dot(a, seg) / (np.linalg.norm(a) * np.linalg.norm(seg) + 1e-12))
        out.append(((s + w / 2) / sample_rate, float(lag), corr))
    return out


def verify_sync(reference: np.ndarray, path, sample_rate: int = SAMPLE_RATE) -> SyncReport:
    """Decode `path` back and compare it with the samples it was encoded from."""
    test = decode(path, sample_rate, reference.shape[0])
    return SyncReport(measure_offset(reference, test, sample_rate), test.shape[1] - reference.shape[1])


def song_audio_files(folder) -> list[Path]:
    """The song's music in a Clone Hero song folder: the files with a name Clone Hero reads as audio
    (SONG_AUDIO_NAMES and SONG_AUDIO_EXTENSIONS, as scan-chart matches them: lower case), but preview and crowd,
    sorted by name. song.ogg alone for a one-file folder; song.ogg, guitar.ogg, bass.ogg and drums.ogg for one whose
    audio is split."""
    folder = Path(folder)
    try:
        files = sorted(p for p in folder.iterdir() if p.is_file())
    except OSError:
        return []
    return [p for p in files if p.suffix in SONG_AUDIO_EXTENSIONS and p.stem in SONG_AUDIO_NAMES
            and p.stem not in NOT_MUSIC]


def decode_song_audio(folder, sample_rate: int = SAMPLE_RATE, channels: int = 2) -> np.ndarray | None:
    """The folder's music as Clone Hero plays it when no note is missed: its audio files (`song_audio_files`)
    decoded and summed, as long as the longest; None when it has none."""
    total = None
    for path in song_audio_files(folder):
        y = decode(path, sample_rate, channels)
        if total is None:
            total = y
        else:
            if y.shape[1] > total.shape[1]:
                total, y = y, total
            total[:, :y.shape[1]] += y
    return total


def write_flac(audio: np.ndarray, path, sample_rate: int = SAMPLE_RATE) -> int:
    """24-bit FLAC of `audio` (channels, samples), clipped to full scale, byte-identical for the same samples: made in
    memory, then written as one file, so a full disk is an OSError (ENOSPC) here and not libsndfile's error. Returns
    the bytes written."""
    import io
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, np.clip(audio, -1.0, 1.0).T, sample_rate, format="FLAC", subtype="PCM_24")
    data = buf.getvalue()
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def write_wav(audio: np.ndarray, path, sample_rate: int = SAMPLE_RATE) -> None:
    import soundfile as sf
    sf.write(str(path), audio.T, sample_rate, subtype="FLOAT")


def read_wav(path) -> tuple[np.ndarray, int]:
    import soundfile as sf
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return y.T.copy(), sr


def ensure_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
