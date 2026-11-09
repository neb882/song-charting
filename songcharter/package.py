"""Assemble a Clone Hero song folder (and a zip of it) from a chart and the decoded song."""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import audio as A
from .chart import Chart, write_chart
from .errors import InputError, ToolError
from .ini import write_ini


SPLIT_PARTS = ("guitar", "bass", "drums")   # the parts whose stem gets a file of its own (<part>.ogg) when split
CONFIDENT = 0.9   # a split file's window that correlates this well with its own samples must lag under a sample


@dataclass
class PackageResult:
    folder: Path
    sync: A.SyncReport                   # the folder's audio summed (song.ogg alone, or the split files) vs the mix
    files: tuple[str, ...] = ("song.ogg",)          # the audio files written, song.ogg first
    tracks: dict = field(default_factory=dict)      # per split file: its worst lag in confident windows, length


def safe_folder_name(artist: str, name: str) -> str:
    raw = f"{artist} - {name}"
    bad = '<>:"/\\|?*'
    cleaned = "".join("_" if c in bad or ord(c) < 32 else c for c in raw).strip(" .")
    return cleaned or "song"


def build_song_folder(out_dir, chart: Chart, song_audio: np.ndarray, pad_samples: int,
                      sample_rate: int = A.SAMPLE_RATE, difficulty: dict[str, int] | None = None,
                      album_art: Path | None = None, quality: float = 7.0,
                      background: Path | None = None, split: dict[str, np.ndarray] | None = None
                      ) -> PackageResult:
    """Write notes.chart, song.ini and song.ogg (the decode with `pad_samples` of silence in front), and copy
    `album_art` and `background` in as album<ext> and background<ext> when given.

    split: Clone Hero's multitrack audio (DESIGN.md 2.13): {part: its stem} for parts of SPLIT_PARTS, each stem on the
    decode's timeline (its length), written as <part>.ogg, and song.ogg is then the decode less those stems (the
    separation's residual, the vocals, piano and the rest stay in it). Each file has the same pad, length, rate and
    encoder settings, so played together they sum to the one-file song.ogg within the encoder's noise, and Clone
    Hero mutes a part's own file on a missed note.

    Raises if the audio does not line up with the samples the chart was made against: the files summed against the
    padded decode (`sync`, the same rule as one song.ogg's), and each split file against its own samples (a window
    that correlates CONFIDENT or better lagging a sample or more).
    """
    folder = A.ensure_dir(out_dir)
    (folder / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    (folder / "song.ini").write_text(write_ini(chart, difficulty), encoding="utf-8", newline="")
    split = {k: split[k] for k in SPLIT_PARTS if k in (split or {})}
    rest = song_audio
    for name, stem in split.items():
        if stem.shape != song_audio.shape:
            raise ToolError(f"the {name} stem has shape {stem.shape}, not the song's {song_audio.shape}")
        rest = rest - stem
    padded = A.pad_front(song_audio, pad_samples)
    sources = {"song.ogg": rest, **{f"{k}.ogg": v for k, v in split.items()}}
    total, tracks = None, {}
    for name, samples in sources.items():
        own = A.pad_front(samples, pad_samples)
        A.encode_ogg(own, folder / name, sample_rate, quality)
        if not split:
            break
        decoded = A.decode(folder / name, sample_rate, own.shape[0])   # summed as it is read: one decode at a time
        if total is None:
            total = decoded.copy()
        else:
            if decoded.shape[1] > total.shape[1]:
                total = np.pad(total, ((0, 0), (0, decoded.shape[1] - total.shape[1])))
            total[:, :decoded.shape[1]] += decoded
        if name != "song.ogg":
            sure = [o for o in A.measure_offset(own, decoded, sample_rate) if o[2] >= CONFIDENT]
            worst = max((abs(o[1]) for o in sure), default=None)
            tracks[name] = {"max_abs_lag_samples": worst, "windows": len(sure),
                            "length_difference": int(decoded.shape[1] - own.shape[1])}
            if worst is not None and worst >= 1.0:
                raise ToolError(f"{name} is out of sync with the chart: {worst:.2f} samples off")
        del decoded, own
    if split:
        sync = A.SyncReport(A.measure_offset(padded, total, sample_rate), total.shape[1] - padded.shape[1])
        what = "the song's audio files together are"
    else:
        sync = A.verify_sync(padded, folder / "song.ogg", sample_rate)
        what = "song.ogg is"
    if not sync.ok:
        raise ToolError(f"{what} out of sync with the chart: {sync.summary()}")
    for image, name in ((album_art, "album"), (background, "background")):
        if image is not None:
            suffix = Path(image).suffix.lower()
            if suffix not in (".png", ".jpg", ".jpeg"):
                raise InputError(f"{name} must be .png or .jpg")
            (folder / f"{name}{suffix}").write_bytes(Path(image).read_bytes())
    return PackageResult(folder, sync, tuple(sources), tracks)


def zip_folder(folder, zip_path) -> Path:
    """A zip holding the song folder itself, ready to extract into Clone Hero's Songs folder."""
    folder, zip_path = Path(folder), Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
        for f in sorted(folder.iterdir()):
            if f.is_file():
                z.write(f, f"{folder.name}/{f.name}")
    return zip_path
