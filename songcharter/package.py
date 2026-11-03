"""Assemble a Clone Hero song folder (and a zip of it) from a chart and the decoded song."""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import audio as A
from .chart import Chart, write_chart
from .errors import InputError, ToolError
from .ini import write_ini


@dataclass
class PackageResult:
    folder: Path
    sync: A.SyncReport


def safe_folder_name(artist: str, name: str) -> str:
    raw = f"{artist} - {name}"
    bad = '<>:"/\\|?*'
    cleaned = "".join("_" if c in bad or ord(c) < 32 else c for c in raw).strip(" .")
    return cleaned or "song"


def build_song_folder(out_dir, chart: Chart, song_audio: np.ndarray, pad_samples: int,
                      sample_rate: int = A.SAMPLE_RATE, difficulty: dict[str, int] | None = None,
                      album_art: Path | None = None, quality: float = 7.0) -> PackageResult:
    """Write notes.chart, song.ini and song.ogg (the decode with `pad_samples` of silence in front).

    Raises if the encoded song.ogg does not line up with the samples the chart was made against.
    """
    folder = A.ensure_dir(out_dir)
    (folder / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    (folder / "song.ini").write_text(write_ini(chart, difficulty), encoding="utf-8", newline="")
    padded = A.pad_front(song_audio, pad_samples)
    ogg = folder / "song.ogg"
    A.encode_ogg(padded, ogg, sample_rate, quality)
    sync = A.verify_sync(padded, ogg, sample_rate)
    if not sync.ok:
        raise ToolError(f"song.ogg is out of sync with the chart: {sync.summary()}")
    if album_art is not None:
        suffix = Path(album_art).suffix.lower()
        if suffix not in (".png", ".jpg", ".jpeg"):
            raise InputError("album art must be .png or .jpg")
        (folder / f"album{suffix}").write_bytes(Path(album_art).read_bytes())
    return PackageResult(folder, sync)


def zip_folder(folder, zip_path) -> Path:
    """A zip holding the song folder itself, ready to extract into Clone Hero's Songs folder."""
    folder, zip_path = Path(folder), Path(zip_path)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as z:
        for f in sorted(folder.iterdir()):
            if f.is_file():
                z.write(f, f"{folder.name}/{f.name}")
    return zip_path
