"""`songcharter listen <song folder>`: a chart you can hear (M6-09, DESIGN.md 2.17).

Watching a chart scroll by, or Clone Hero's bot that hits every note, cannot show a wrong, late, missing or extra
note; hearing the chart over the song can. This renders one part and level of a built song folder (notes.chart or
notes.mid, song.ini, song.ogg) as sound, over the song or alone, into a stereo file:

  * **5-fret parts** (guitar, bass): each note a tone at its lane's pitch, green lowest to orange highest, on
    stacked thirds (C5 E5 G5 B5 D6, a major ninth chord: steps of 3 and 4 semitones, any chord of them pleasant, and
    no lane an octave of another, so no chord fuses into one note and no lane's harmonic is another lane), and an
    open note lower still (G4); the bass an octave below (C4 to D5, open G3). A chord is its pitches together, each
    1/sqrt(n) as loud. A strum is a plucked tone: an attack of 1 ms with bright harmonics, decaying over about half
    a second. A HOPO or a tap is shorter and softer: a 6 ms rise, half the level, almost no harmonics, gone in about
    a quarter of a second. A sustain adds the note's pitch held at a lower level (HOLD) to its end, released over
    40 ms. The lanes are panned a little, green left to orange right, as on the highway.
  * **Drums** (pads as the highway shows them, red to green left to right): the kick a low thump (a sine falling from
    about 150 to 52 Hz, with a soft click for small speakers), the snare a noise burst (1.5-9 kHz) over a 185 Hz body,
    the toms short pitched tones falling a little (yellow 294 Hz, blue 220 Hz, green 165 Hz), the cymbals high noise:
    the hi-hat (yellow) short, the ride (blue) longer with a ping, the crash (green) long. An accent is louder, a ghost
    note softer, an Expert+ kick a kick.
  * **The mix:** the song at SONG_DB (-12 dB) under the tones, or the tones alone (`tones_only`). The tones are at the
    chart's own times, as importers.read_song reads them with the folder's song.ini (its tempo map, the chart's offset
    and song.ini's delay): song seconds, so the chart's 0 is song.ogg's 0 and the lead-in pad is in both. A note's
    tone starts on the sample nearest its time, at 44.1 kHz. The render is song.ogg's length (the chart's end and 2 s
    without one, for tones alone); a note after its end is left out and counted. Fixed levels keep the sum under
    CEILING (-1 dBFS, room for the encoder's overshoot); when a hot song and a dense chord pass it anyway, the whole
    render is turned down once to fit, never limited note by note.
  * **Deterministic:** the noises come from fixed seeds, every note of a kind is the same sound, and the OGG is
    written with ffmpeg's bitexact flags (without them its Ogg stream serial is random), so the same folder gives the
    same bytes.
  * **Out:** OGG Vorbis (quality 5), or 16-bit WAV for a path ending .wav, written through a temporary file beside it
    and never inside the song folder (Clone Hero reads the audio files there by name: no extra file may risk it).

`cached` is the page's (ui/server.py): one render per part and level in a folder of the job's, named by a hash of
the song folder's files and VERSION, so a new chart of the same song renders again.

Exit status of the command: 0 written; 2 a bad input (no such folder, part or level, no song.ogg, an output inside
the song folder or with another extension) or ffmpeg failing; 3 a bug.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import audio as A
from .errors import InputError, ToolError
from .timed import DIFFICULTIES, INSTRUMENTS, OPEN, TimedHit, TimedPart

SR = A.SAMPLE_RATE
VERSION = 1                     # in the page's cache key: a change to the sounds makes the page render again
SONG_DB = -12.0                 # the song under the tones
CEILING = 10 ** (-1 / 20)       # the render's peak at most (-1 dBFS)
SEED = 20261107                 # the noises' seed
QUALITY = 5                     # libvorbis VBR quality (about 160 kbps stereo)
OUTPUTS = (".ogg", ".wav")


def _hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12)


# 5-fret lanes: green, red, yellow, blue, orange (stacked thirds, a major ninth chord), and the open note below them
GUITAR_MIDI = (72, 76, 79, 83, 86)          # C5 E5 G5 B5 D6
OPEN_MIDI = 67                              # G4
BASS_SHIFT = -12                            # the bass an octave down
FRET_PAN = (-0.4, -0.2, 0.0, 0.2, 0.4)      # green left to orange right; the open note in the middle


@dataclass(frozen=True)
class Voice:
    """How a 5-fret tone sounds: the fundamental's level at the attack, the rise to it (a raised cosine), the
    decay's time constant, the tone's length (faded over its last FADE) and its harmonics as (multiple, amplitude
    against the fundamental, decay against the fundamental's)."""
    level: float
    rise: float
    tau: float
    length: float
    harmonics: tuple[tuple[int, float, float], ...]


STRUM = Voice(0.22, 0.001, 0.16, 0.6, ((1, 1.0, 1.0), (2, 0.5, 0.45), (3, 0.25, 0.3), (4, 0.12, 0.22)))
HOPO = Voice(0.11, 0.006, 0.07, 0.35, ((1, 1.0, 1.0), (2, 0.2, 0.5)))   # a HOPO or a tap
HOLD = 0.07          # a sustain's held level (its fundamental), under both voices' attack
RELEASE = 0.04       # a sustain's release after its end
FADE = 0.02          # a tone's fade at the end of its length

# drum pads: 0 kick, 1 red (snare), 2 yellow, 3 blue, 4 green (toms, or cymbals with the cymbal flag)
DRUM_PAN = {0: 0.0, 1: -0.3, 2: -0.1, 3: 0.1, 4: 0.3}
TOM_HZ = {2: 294.0, 3: 220.0, 4: 165.0}
ACCENT, GHOST = 1.3, 0.45


@dataclass
class Rendered:
    audio: np.ndarray        # (2, samples) float32 at SR
    part: str
    difficulty: str
    notes: int               # notes (or hits) heard
    left_out: int            # notes at or after the end of the render
    seconds: float
    tones_only: bool
    turned_down_db: float    # 0, or how far the whole render was turned down to stay under CEILING


# ------------------------------------------------------------------------------------------------ the sounds

def _ramp(n: int, rise: float) -> np.ndarray:
    """0 to 1 over `rise` seconds (a raised cosine), then 1."""
    t = np.arange(n) / SR
    return 0.5 - 0.5 * np.cos(np.pi * np.minimum(t / rise, 1.0))


def _fade(n: int, seconds: float) -> np.ndarray:
    """1, then down to 0 over the last `seconds` (a raised cosine)."""
    out = np.ones(n)
    k = min(n, int(round(seconds * SR)))
    if k:
        out[n - k:] = 0.5 + 0.5 * np.cos(np.pi * (np.arange(k) + 1) / k)
    return out


def tone(hz: float, voice: Voice, hold: float = 0.0) -> np.ndarray:
    """One pitch of a 5-fret note: the voice's attack and decay; for a sustain (`hold` seconds), its fundamental held
    at HOLD to the end and released over RELEASE."""
    natural = int(round(voice.length * SR))
    n = max(natural, int(round((hold + RELEASE) * SR)) if hold > 0 else 0)
    t = np.arange(n) / SR
    y = np.zeros(n)
    tn = t[:natural]
    for k, amp, m in voice.harmonics:
        y[:natural] += amp * np.exp(-tn / (voice.tau * m)) * np.sin(2 * np.pi * k * hz * tn)
    y[:natural] *= voice.level * _fade(natural, FADE)
    if hold > 0:
        gate = np.zeros(n)
        end = min(n, int(round(hold * SR)))
        gate[:end] = 1.0
        r = int(round(RELEASE * SR))
        gate[end:end + r] = 0.5 + 0.5 * np.cos(np.pi * (np.arange(min(r, n - end)) + 1) / r)
        y += HOLD * (1 - np.exp(-t / voice.tau)) * gate * np.sin(2 * np.pi * hz * t)
    return y * _ramp(n, voice.rise)


def _noise(n: int, low: float, high: float, key: int) -> np.ndarray:
    """Deterministic noise with unit RMS, shaped to the band low-high Hz (4th-order slopes, in the spectrum)."""
    rng = np.random.default_rng([SEED, key])
    spectrum = np.fft.rfft(rng.standard_normal(n))
    f = np.maximum(np.fft.rfftfreq(n, 1 / SR), 1.0)
    spectrum *= 1 / np.sqrt(1 + (low / f) ** 8) / np.sqrt(1 + (f / high) ** 8)
    y = np.fft.irfft(spectrum, n)
    y /= max(float(np.sqrt(np.mean(y ** 2))), 1e-12)
    y = 2.5 * np.tanh(y / 2.5)              # its rare peaks rounded off: a burst's level without its spikes
    return y / max(float(np.sqrt(np.mean(y ** 2))), 1e-12)


def _sweep(n: int, hz: np.ndarray) -> np.ndarray:
    """A sine whose frequency follows `hz` (one value a sample), from phase 0."""
    return np.sin(2 * np.pi * np.concatenate([[0.0], np.cumsum(hz[:-1])]) / SR)


def drum_sounds() -> dict[str, np.ndarray]:
    """Each drum sound once (mono, float64): kick, snare, tom2-tom4 (yellow, blue, green), hihat, ride, crash."""
    def shape(seconds: float, rise: float = 0.001):
        n = int(round(seconds * SR))
        return n, np.arange(n) / SR, _ramp(n, rise) * _fade(n, FADE)

    out = {}
    n, t, env = shape(0.35)
    body = _sweep(n, 52 + 100 * np.exp(-t / 0.035)) * np.exp(-t / 0.12)
    click = _noise(n, 200, 3000, 1) * np.exp(-t / 0.004)
    out["kick"] = 0.42 * (body + 0.25 * click) * env
    n, t, env = shape(0.3)
    out["snare"] = 0.22 * (0.5 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05)
                           + 0.6 * _noise(n, 1500, 9000, 2) * np.exp(-t / 0.07)) * env
    for pad, hz in TOM_HZ.items():
        n, t, env = shape(0.45)
        bend = hz * (1 + 0.12 * np.exp(-t / 0.05))
        out[f"tom{pad}"] = 0.25 * (_sweep(n, bend) * np.exp(-t / 0.14)
                                   + 0.3 * _sweep(n, 2 * bend) * np.exp(-t / 0.05)) * env
    n, t, env = shape(0.15)
    out["hihat"] = 0.06 * _noise(n, 7000, 16000, 3) * np.exp(-t / 0.03) * env
    n, t, env = shape(0.8)
    out["ride"] = (0.035 * _noise(n, 5000, 14000, 4) * np.exp(-t / 0.2)
                   + 0.04 * np.sin(2 * np.pi * 2400 * t) * np.exp(-t / 0.25)) * env
    n, t, env = shape(1.5, rise=0.002)
    out["crash"] = 0.05 * _noise(n, 3000, 15000, 5) * np.exp(-t / 0.45) * env
    return out


def drum_sound_name(hit: TimedHit) -> str:
    if hit.pad == 0:
        return "kick"
    if hit.pad == 1:
        return "snare"
    if hit.cymbal:
        return {2: "hihat", 3: "ride", 4: "crash"}[hit.pad]
    return f"tom{hit.pad}"


def _gains(pan: float) -> tuple[float, float]:
    """Constant-power pan, -1 left to 1 right."""
    a = (pan + 1) * np.pi / 4
    return float(np.cos(a)), float(np.sin(a))


def _add(buf: np.ndarray, start: int, sound: np.ndarray, gain: float, pan: float) -> None:
    """Mix `sound` into `buf` (2, n) from sample `start`, cut at both ends."""
    n = buf.shape[1]
    a, b = max(start, 0), min(start + len(sound), n)
    if a >= b:
        return
    piece = sound[a - start:b - start] * gain
    left, right = _gains(pan)
    buf[0, a:b] += piece * left
    buf[1, a:b] += piece * right


def fret_pitches(part: str) -> tuple[tuple[float, ...], float]:
    """The five lanes' pitches and the open note's, in Hz, for guitar or bass."""
    shift = BASS_SHIFT if part == "bass" else 0
    return tuple(_hz(m + shift) for m in GUITAR_MIDI), _hz(OPEN_MIDI + shift)


def tones(part: TimedPart, samples: int) -> tuple[np.ndarray, int]:
    """The part's notes as sound, (2, samples) float64, and how many were heard (before the end)."""
    buf = np.zeros((2, samples))
    heard = 0
    if part.instrument == "drums":
        sounds = drum_sounds()
        for hit in part.notes:
            start = int(round(hit.time * SR))
            if start >= samples:
                continue
            gain = ACCENT if hit.accent else GHOST if hit.ghost else 1.0
            _add(buf, start, sounds[drum_sound_name(hit)], gain, DRUM_PAN.get(hit.pad, 0.0))
            heard += 1
        return buf, heard
    lanes, open_hz = fret_pitches(part.instrument)
    plain: dict[tuple[float, Voice], np.ndarray] = {}   # a tone without a sustain, made once
    for note in part.notes:
        start = int(round(note.time * SR))
        if start >= samples:
            continue
        voice = HOPO if (note.hopo or note.tap) else STRUM
        hold = max(0.0, note.end - note.time) if note.end is not None else 0.0
        gain = 1 / np.sqrt(len(note.frets))
        for fret in note.frets:
            hz, pan = (open_hz, 0.0) if fret == OPEN else (lanes[fret], FRET_PAN[fret])
            if hold > 0:
                sound = tone(hz, voice, hold)
            else:
                sound = plain.get((hz, voice))
                if sound is None:
                    sound = plain[(hz, voice)] = tone(hz, voice)
            _add(buf, start, sound, gain, pan)
        heard += 1
    return buf, heard


# ------------------------------------------------------------------------------------------------ a song folder

def _read(folder: Path):
    from .importers import read_song
    try:
        return read_song(folder)
    except FileNotFoundError:
        raise InputError(f"no notes.chart or notes.mid in {folder}") from None
    except (InputError, OSError) as e:
        raise InputError(f"cannot read the chart in {folder}: {e}") from None


def _level(difficulty: str) -> str:
    return difficulty.capitalize()


def available(folder: Path | str) -> dict[str, list[str]]:
    """The parts with notes in the folder's chart and the levels each has: {"guitar": ["expert", ...], ...}, in
    INSTRUMENTS and DIFFICULTIES order. InputError when there is no chart to read."""
    song = _read(Path(folder))
    out = {}
    for inst in INSTRUMENTS:
        levels = [d for d in DIFFICULTIES if (p := song.parts.get((inst, d))) is not None and p.notes]
        if levels:
            out[inst] = levels
    return out


def render(folder: Path | str, part: str = "guitar", difficulty: str = "expert", tones_only: bool = False,
           song_db: float = SONG_DB) -> Rendered:
    """One part and level of a built song folder as sound (the module docstring)."""
    folder = Path(folder)
    if part not in INSTRUMENTS:
        raise InputError(f"the part is one of {', '.join(INSTRUMENTS)}, not {part!r}")
    if difficulty not in DIFFICULTIES:
        raise InputError(f"the level is one of {', '.join(DIFFICULTIES)}, not {difficulty!r}")
    if not folder.is_dir():
        raise InputError(f"{folder} is not a song folder")
    song = _read(folder)
    p = song.parts.get((part, difficulty))
    if p is None or not p.notes:
        has = [f"{i} on {_level(d)}" for (i, d), q in sorted(song.parts.items(),
               key=lambda kv: (INSTRUMENTS.index(kv[0][0]), DIFFICULTIES.index(kv[0][1]))) if q.notes]
        raise InputError(f"the chart in {folder} has no {part} on {_level(difficulty)}"
                         + (f" (it has {', '.join(has)})" if has else " (it has no notes)"))
    ogg = folder / "song.ogg"
    music = None
    if ogg.is_file():
        music = A.decode(ogg, SR, 2).astype(np.float64)
        samples = music.shape[1]
    elif tones_only:
        last = max((n.end if getattr(n, "end", None) is not None else n.time) for n in p.notes)
        samples = int(round((last + 2.0) * SR))
    else:
        raise InputError(f"no song.ogg in {folder} (--tones-only renders the notes alone)")
    mix, heard = tones(p, samples)
    if not tones_only:
        mix += music * 10 ** (song_db / 20)
    peak = float(np.abs(mix).max()) if mix.size else 0.0
    down = 0.0
    if peak > CEILING:
        mix *= CEILING / peak
        down = 20 * np.log10(peak / CEILING)
    return Rendered(mix.astype(np.float32), part, difficulty, heard, len(p.notes) - heard, samples / SR,
                    tones_only, float(down))


def _write_wav(audio: np.ndarray, path: Path) -> None:
    pcm = np.round(np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(audio.shape[0])
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(np.ascontiguousarray(pcm.T).tobytes())


def _write_ogg(audio: np.ndarray, path: Path) -> None:
    cmd = [A.ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "f32le", "-ar", str(SR),
           "-ac", str(audio.shape[0]), "-i", "pipe:0", "-c:a", "libvorbis", "-q:a", str(QUALITY),
           "-fflags", "+bitexact", "-flags", "+bitexact", "-f", "ogg", str(path)]
    data = np.ascontiguousarray(np.clip(audio, -1, 1).T.astype("<f4")).tobytes()
    try:
        subprocess.run(cmd, input=data, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise ToolError(f"ffmpeg could not write {path}: {A.ffmpeg_error(e)}") from e


def write(audio: np.ndarray, path: Path | str) -> Path:
    """The render as OGG Vorbis, or 16-bit WAV for a path ending .wav, through a temporary file beside it."""
    path = Path(path)
    if path.suffix.lower() not in OUTPUTS:
        raise InputError(f"the output {path} must end .ogg or .wav")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.part")
    try:
        (_write_wav if path.suffix.lower() == ".wav" else _write_ogg)(audio, tmp)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


def inside(path: Path, folder: Path) -> bool:
    """Whether `path` is the song folder or anything under it (links resolved)."""
    try:
        path.resolve().relative_to(folder.resolve())
    except ValueError:
        return False
    return True


def output_path(folder: Path, out: Path | None, part: str, difficulty: str) -> Path:
    """Where the command writes: --out, or <folder name>-<part>-<level>.ogg in the current folder (or in --out when
    that is a folder); never inside the song folder."""
    name = f"{folder.resolve().name}-{part}-{difficulty}.ogg"
    out = None if out is None else out.expanduser()
    path = (Path.cwd() / name if out is None else (out / name if out.is_dir() else out)).absolute()
    if inside(path, folder):
        raise InputError(f"{path} is inside the song folder: Clone Hero reads the audio files there, so write it "
                         "somewhere else (--out FILE)")
    if path.suffix.lower() not in OUTPUTS:
        raise InputError(f"the output {path} must end .ogg or .wav")
    return path


def cache_key(folder: Path, part: str, difficulty: str) -> str:
    """16 hex of a hash of VERSION, the part, the level and the folder's chart, song.ini and song.ogg."""
    h = hashlib.sha256(f"songcharter-listen {VERSION} {part} {difficulty}\n".encode())
    for name in ("notes.chart", "notes.mid", "song.ini", "song.ogg"):
        f = folder / name
        if f.is_file():
            h.update(f"{name} {f.stat().st_size}\n".encode())
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
    return h.hexdigest()[:16]


def cached(folder: Path | str, cache: Path | str, part: str, difficulty: str) -> tuple[Path, bool]:
    """The page's render of one part and level (over the song), in `cache` as <part>-<level>-<key>.ogg: the one
    there for this chart, else a new one (older renders of that part and level go). Answers (its path, whether it
    was there)."""
    folder, cache = Path(folder), Path(cache)
    if part not in INSTRUMENTS or difficulty not in DIFFICULTIES:
        raise InputError(f"no such part and level: {part!r} {difficulty!r}")
    path = cache / f"{part}-{difficulty}-{cache_key(folder, part, difficulty)}.ogg"
    if path.is_file():
        return path, True
    rendered = render(folder, part, difficulty)
    cache.mkdir(parents=True, exist_ok=True)
    write(rendered.audio, path)
    for old in cache.glob(f"{part}-{difficulty}-*.ogg"):
        if old != path:
            old.unlink(missing_ok=True)
    return path, False


def _mmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def summary(r: Rendered) -> str:
    what = "the notes alone" if r.tones_only else f"over the song at {SONG_DB:g} dB"
    unit = "hits" if r.part == "drums" else "notes"
    line = f"listen: {r.part} on {_level(r.difficulty)}, {r.notes} {unit} {what}, {_mmss(r.seconds)}"
    if r.left_out:
        line += f"; {r.left_out} {unit} at or after the end of song.ogg left out"
    if r.turned_down_db:
        line += f"; turned down {r.turned_down_db:.1f} dB so nothing clips"
    return line
