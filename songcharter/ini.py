"""song.ini: the metadata Clone Hero shows in its song list.

Only keys that describe the song are written. Keys that change gameplay without changing the chart
(delay, hopo_frequency, sustain_cutoff_threshold, ...) are left out on purpose: the chart itself
says everything. song_length is left out too; Clone Hero measures it from the audio.
"""
from __future__ import annotations

from .chart import Chart

# song.ini difficulty key for each chart instrument
_DIFF_KEYS = {
    "Single": ["diff_guitar"],
    "DoubleGuitar": ["diff_guitar_coop"],
    "DoubleBass": ["diff_bass"],
    "DoubleRhythm": ["diff_rhythm"],
    "Drums": ["diff_drums"],
    "Keyboard": ["diff_keys"],
}


def _value(s) -> str:
    return " ".join(str(s).split())


def write_ini(chart: Chart, difficulty: dict[str, int] | None = None, pro_drums: bool | None = None) -> str:
    """difficulty: instrument -> 0..6 rating. pro_drums: defaults to True when any cymbal is charted."""
    info = chart.info
    rows: list[tuple[str, str]] = [("name", info.name), ("artist", info.artist)]
    for key, val in (("album", info.album), ("genre", info.genre), ("year", info.year), ("charter", info.charter)):
        if val:
            rows.append((key, val))
    if info.album_track is not None:
        rows.append(("album_track", str(info.album_track)))
    difficulty = difficulty or {}
    instruments = chart.instruments()
    for inst in instruments:
        for key in _DIFF_KEYS[inst]:
            rows.append((key, str(int(difficulty.get(inst, 3)))))
    if "Drums" in instruments:
        if pro_drums is None:
            pro_drums = any(getattr(n, "cymbal", False) for t in chart.tracks if t.is_drums for n in t.notes)
        rows.append(("diff_drums_real", str(int(difficulty.get("Drums", 3))) if pro_drums else "-1"))
        rows.append(("pro_drums", "True" if pro_drums else "False"))
    if info.preview_start_ms is not None:
        rows.append(("preview_start_time", str(int(info.preview_start_ms))))
    if info.loading_phrase:
        rows.append(("loading_phrase", info.loading_phrase))
    return "[song]\r\n" + "".join(f"{k} = {_value(v)}\r\n" for k, v in rows)
