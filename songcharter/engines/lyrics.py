"""Lyrics timed to the vocal stem: the text a person gives, aligned word by word and syllable by syllable (DESIGN.md
2.15). It aligns text; it never transcribes.

    result = align(text, vocals, "work/lyrics")   # vocals: float32 (2, n) at 44.1 kHz, sample-aligned to the decode
    result.lyrics, result.starts, result.ends     # the parsed text (lyrics.parse) and each syllable's times (s)

  * **Method** (`METHODS`, chosen in DESIGN.md 2.15 by measurement on the six references): CTC forced alignment
    with one of torchaudio's speech-recognition bundles. The stem, summed to mono and resampled to 16 kHz, goes
    through the network in 30 s windows with 2 s of context on each side, every window starting on the 20 ms frame
    grid, so the frames of the whole song line up; torchaudio.functional.forced_align then finds the best path of
    the whole text through them at once. The text is each word's spelling (lyrics.spelling), with the bundle's word
    separator between the words of a line and a wildcard (a "star" class of log-probability 0 in every frame, which
    any stretch of audio can take) before every line and at the end, so music between the lines, a repeat the text
    lacks or an ad-lib costs nothing. A syllable starts at its first character's frame and ends at its last's; one
    with no character the bundle spells is spread evenly between its neighbours.
  * **Weights** at a pinned URL with a pinned SHA-256, in models/lyrics/ (adtof.models_dir()), downloaded on first
    use and checked whenever they are loaded, then loaded with torch.load(weights_only=True). SONGCHARTER_OFFLINE=1
    forbids the download.
  * **Confidence** (info["confidence"]): per word, the mean probability of its characters on the path; the median
    over the song, its 10th percentile, and the share of words under LOW_SCORE (on the six references' stems a word
    under 0.05 is off by more than 250 ms in 0.19 of cases, the others in 0.08). A median under LOW_MEDIAN (0.25) is
    warned about: the stems' song medians were 0.31 to 0.89 (0.874 to 0.983 of their words within 250 ms), the full
    mixes', where the alignment collapsed, 0.09 to 0.18.
  * **Cache.** out/lyrics.json holds the key (the stem's samples, the text's SHA-256, every setting, the weights'
    SHA-256 and the libraries' versions) and the times by syllable index, never the text: a hit is a file with this
    key and as many syllables as the text parses into.
  * **Unavailable** (`Unavailable`, `missing`): torch or torchaudio not installed (`pip install songcharter[lyrics]`,
    which the app includes), a torchaudio without the bundle or forced_align, or the weights that cannot be had. The
    pipeline then charts without lyrics and warns; lyrics never fail a chart.

Nothing here prints, logs or records any word of the text: errors carry their type and counts only.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from .. import __version__
from .. import audio as A
from ..lyrics import Lyrics, parse
from .adtof import _sha256, models_dir

ENGINE = "songcharter.engines.lyrics"
VERSION = "1"            # bump when the times for the same input and settings change
SAMPLE_RATE = A.SAMPLE_RATE
RATE = 16000             # the bundles' sample rate
HOP = 320                # samples per frame: 20 ms
LOW_SCORE = 0.05         # a word whose characters average under this on the path is a weak one
LOW_MEDIAN = 0.25        # a song whose words' median is under this is warned about


@dataclass(frozen=True)
class Method:
    bundle: str          # the torchaudio pipeline
    url: str             # its weights, as the bundle fetches them
    sha256: str
    file: str
    bytes: int
    upper: bool          # its labels spell letters in upper case
    separator: str | None   # its word separator label, if it has one
    licence: str


METHODS = {
    "english": Method("WAV2VEC2_ASR_LARGE_LV60K_960H",
                      "https://download.pytorch.org/torchaudio/models/wav2vec2_fairseq_large_lv60k_asr_ls960.pth",
                      "7a88965716fbd598a595209bf45c1210a18a6935cfb0cf53527fc986c5543ac7",
                      "wav2vec2_fairseq_large_lv60k_asr_ls960.pth", 1262046195, True, "|", "MIT (fairseq)"),
    "english-base": Method("WAV2VEC2_ASR_BASE_960H",
                           "https://download.pytorch.org/torchaudio/models/wav2vec2_fairseq_base_ls960_asr_ls960.pth",
                           "488fd4f16de84438ffc945334278c1b9fb9b7159a806c1080b16111a958c945d",
                           "wav2vec2_fairseq_base_ls960_asr_ls960.pth", 377664473, True, "|", "MIT (fairseq)"),
}   # the base bundle: 378 MB of weights for 0.046 fewer words within 250 ms (DESIGN.md 2.15)
DEFAULT_METHOD = "english"


@dataclass(frozen=True)
class Settings:
    method: str = DEFAULT_METHOD
    stars: str = "line"          # the wildcard before every line ("line") or word ("word"); always at the text's
                                 # start and end and at every section gap
    window_s: float = 30.0
    context_s: float = 2.0
    device: str = "cpu"          # "cpu" or "cuda" (forced_align itself always runs on the CPU)

    def __post_init__(self):
        if self.method not in METHODS:
            raise ValueError(f"method is one of {', '.join(METHODS)}, not {self.method!r}")
        if self.stars not in ("line", "word", "none"):
            raise ValueError(f"stars is line, word or none, not {self.stars!r}")
        if (self.window_s * RATE) % HOP or (self.context_s * RATE) % HOP or self.window_s <= 0 or self.context_s < 0:
            raise ValueError("window_s and context_s must be whole numbers of 20 ms frames, the window above 0")
        if self.device not in ("cpu", "cuda"):
            raise ValueError(f"device is cpu or cuda, not {self.device!r}")


@dataclass(frozen=True)
class Result:
    lyrics: Lyrics               # the parsed text: shown only in the chart
    starts: tuple[float, ...]    # each syllable's start, seconds of the decode
    ends: tuple[float, ...]
    path: Path                   # lyrics.json: numbers only
    cached: bool
    info: dict                   # numbers only


class Unavailable(Exception):
    """The aligner cannot run here; the message says why and what to install, and holds no word of the text."""


# ------------------------------------------------------------------------------------------------ what it needs

def missing() -> str | None:
    """Why the aligner cannot run here (torch or torchaudio not importable), else None."""
    import importlib.util
    for module in ("torch", "torchaudio"):
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            return f"{module} is not installed: pip install songcharter[lyrics]"
    return None


def _torch():
    why = missing()
    if why:
        raise Unavailable(why)
    try:
        import torch
        import torchaudio
        import torchaudio.functional as F
    except Exception as e:  # noqa: BLE001  a broken install: the type says enough
        raise Unavailable(f"torch or torchaudio does not import ({type(e).__name__})") from None
    if not hasattr(F, "forced_align"):
        raise Unavailable(f"torchaudio {torchaudio.__version__} has no forced_align")
    return torch, torchaudio, F


def versions() -> dict[str, str]:
    """The libraries whose versions can move the times."""
    torch, torchaudio, _ = _torch()
    return {"songcharter": __version__, "torch": torch.__version__, "torchaudio": torchaudio.__version__,
            "numpy": np.__version__}


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


def weights_path(method: Method, models: Path | str | None = None,
                 download: Callable[[str, Path], None] | None = None) -> Path:
    """The pinned weights, models/lyrics/<file>, downloaded on first use to a .part file and renamed once its SHA-256
    matches; a file already there is checked too. Unavailable when they cannot be had."""
    path = Path(models or models_dir()) / "lyrics" / method.file
    if not path.is_file():
        if os.environ.get("SONGCHARTER_OFFLINE") == "1":
            raise Unavailable(f"the aligner's weights are not in {path.parent} and SONGCHARTER_OFFLINE=1")
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        try:
            (download or _download)(method.url, part)
        except OSError as e:
            part.unlink(missing_ok=True)
            raise Unavailable(f"the aligner's weights could not be downloaded from {method.url} "
                              f"({type(e).__name__}: {e})") from None
        got = _sha256(part)
        if got != method.sha256:
            part.unlink()
            raise Unavailable(f"the aligner's weights from {method.url} have SHA-256 {got}, not the pinned "
                              f"{method.sha256}")
        os.replace(part, path)
        return path
    got = _sha256(path)
    if got != method.sha256:
        raise Unavailable(f"{path} has SHA-256 {got}, not the pinned {method.sha256}; delete it and run again")
    return path


def load_model(method: Method, device: str):
    """The bundle and its network with the pinned weights, on `device`. Not kept: its memory (1.2 GB for the large
    bundles) goes back once the alignment is done, before the guitar stage needs the GPU."""
    torch, torchaudio, _ = _torch()
    path = weights_path(method)
    bundle = getattr(torchaudio.pipelines, method.bundle, None)
    if bundle is None:
        raise Unavailable(f"torchaudio {torchaudio.__version__} has no {method.bundle} bundle")
    kwargs = {"dl_kwargs": {"model_dir": str(path.parent), "file_name": path.name, "progress": False,
                            "weights_only": True}}
    model = bundle.get_model(**kwargs)
    return bundle, model.to(device).eval()


# ------------------------------------------------------------------------------------------------ the alignment

def mono16k(vocals: np.ndarray, torch, F) -> np.ndarray:
    """The stem summed to mono and resampled to 16 kHz (float32)."""
    x = torch.from_numpy(np.ascontiguousarray(np.asarray(vocals, dtype=np.float32).mean(axis=0)))
    return F.resample(x, SAMPLE_RATE, RATE).numpy()


def emissions(model, audio: np.ndarray, settings: Settings, torch) -> np.ndarray:
    """Log-probabilities (frames, classes) over the whole song: windows of window_s with context_s of audio on each
    side, each window's frame k placed on the song's own 20 ms grid."""
    window, context = round(settings.window_s * RATE), round(settings.context_s * RATE)
    keep, ctx = window // HOP, context // HOP
    n = len(audio)
    frames = max((n - 400) // HOP + 1, 1)   # the first convolution's 400-sample receptive field
    pad = np.concatenate([np.zeros(context, np.float32), audio.astype(np.float32),
                          np.zeros(context + window, np.float32)])
    out = None
    with torch.inference_mode():
        for i in range(math.ceil(n / window)):
            if i * keep >= frames:
                break
            x = torch.from_numpy(pad[i * window:i * window + window + 2 * context].copy())[None]
            e = torch.log_softmax(model(x.to(next(model.parameters()).device))[0][0].float(), dim=-1).cpu().numpy()
            if out is None:
                out = np.empty((frames, e.shape[1]), np.float32)
            a = i * keep
            seg = e[ctx:ctx + keep][:frames - a]
            out[a:a + len(seg)] = seg
            if a + len(seg) < min(a + keep, frames):   # the last window ran short of frames: repeat its last one
                out[a + len(seg):min(a + keep, frames)] = seg[-1]
    return out


def targets(lyrics: Lyrics, labels: tuple[str, ...], method: Method, stars: str) -> tuple[list[int], list[int]]:
    """The label sequence of the whole text and, per label, the syllable it spells (-1 for a separator or a star).
    The star is the class after the bundle's own labels: before every line (`stars` "line") or word ("word"), and
    whatever `stars` says at the text's start, at every section gap (a blank line or a heading: music the text does
    not sing) and at its end."""
    index = {c: i for i, c in enumerate(labels)}
    star = len(labels)
    seq, owner = [], []
    prev_word, prev_line, separate = None, None, False
    for i, s in enumerate(lyrics.syllables):
        if s.word != prev_word:   # a new word: a star before a line (or every word), else the separator
            if stars == "word" or (stars == "line" and s.line != prev_line) or s.gap:
                if not seq or seq[-1] != star:
                    seq.append(star)
                    owner.append(-1)
                separate = False
            else:
                separate = method.separator is not None and bool(seq) and seq[-1] != star
            prev_word, prev_line = s.word, s.line
        chars = [index[c] for c in (s.spelling.upper() if method.upper else s.spelling) if c in index]
        if chars and separate:
            seq.append(index[method.separator])
            owner.append(-1)
            separate = False
        seq += chars
        owner += [i] * len(chars)
    if seq[-1:] != [star]:
        seq.append(star)
        owner.append(-1)
    return seq, owner


def _spread(starts: list, ends: list) -> tuple[list[float], list[float]]:
    """Syllables with no time (no character the bundle spells) spread evenly between their neighbours."""
    s, e = list(starts), list(ends)
    n, i = len(s), 0
    while i < n:
        if s[i] is None:
            j = i
            while j < n and s[j] is None:
                j += 1
            a = e[i - 1] if i > 0 else (s[j] if j < n else 0.0)
            b = s[j] if j < n else a
            for k in range(i, j):
                s[k] = a + (b - a) * (k - i) / (j - i)
                e[k] = a + (b - a) * (k - i + 1) / (j - i)
            i = j
        i += 1
    return [float(x) for x in s], [float(x) for x in e]


def cache_key(vocals: np.ndarray, text: str, settings: Settings, libs: dict[str, str]) -> str:
    """A hash of the stem's samples, the text's SHA-256, every setting, the weights' SHA-256 and the versions."""
    h = hashlib.sha256()
    method = METHODS[settings.method]
    h.update(repr((ENGINE, VERSION, vocals.shape, SAMPLE_RATE, hashlib.sha256(text.encode("utf-8")).hexdigest(),
                   sorted(asdict(settings).items()), method.sha256, sorted(libs.items()))).encode())
    h.update(np.ascontiguousarray(vocals, dtype="<f4").tobytes())
    return h.hexdigest()[:24]


def _done(path: Path, key: str, n: int) -> dict | None:
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    times = info.get("times") or {}
    if (info.get("key") != key or len(times.get("starts") or []) != n or len(times.get("ends") or []) != n
            or not all(isinstance(x, (int, float)) for x in times["starts"] + times["ends"])):
        return None
    return info


def path_times(em: np.ndarray, seq: list[int], owner: list[int], n: int, blank: int, torch, F
               ) -> tuple[list, list, list[list[float]]]:
    """Each syllable's first and last frame times on the best path of `seq` through the log-probabilities `em`
    (frames, classes), None where it spells nothing, and its characters' probabilities on the path."""
    starts: list = [None] * n
    ends: list = [None] * n
    char_scores: list[list[float]] = [[] for _ in range(n)]
    repeats = sum(1 for a, b in zip(seq, seq[1:]) if a == b)
    if len(seq) + repeats > em.shape[0]:
        raise ValueError(f"the lyrics need {len(seq) + repeats} frames and the audio has {em.shape[0]}")
    if not any(o >= 0 for o in owner):
        return starts, ends, char_scores
    ali, scores = F.forced_align(torch.from_numpy(np.ascontiguousarray(em, dtype=np.float32))[None],
                                 torch.tensor([seq], dtype=torch.int32), blank=blank)
    spans = F.merge_tokens(ali[0], scores[0].exp(), blank=blank)
    if len(spans) != len(seq):
        raise RuntimeError(f"forced_align gave {len(spans)} spans for {len(seq)} labels")
    for span, o in zip(spans, owner):
        if o < 0:
            continue
        if starts[o] is None:
            starts[o] = span.start * HOP / RATE
        ends[o] = span.end * HOP / RATE
        char_scores[o].append(float(span.score))
    return starts, ends, char_scores


class Torchaudio:
    """The aligner itself (the module docstring): the bundle's network on the stem, then the forced alignment."""

    def versions(self) -> dict[str, str]:
        return versions()

    def run(self, lyrics: Lyrics, vocals: np.ndarray, settings: Settings) -> tuple[list, list, list, dict]:
        """(starts, ends, characters' probabilities) per syllable, None where it spells nothing, and the counts and
        timings."""
        torch, _, F = _torch()
        method = METHODS[settings.method]
        t0 = time.perf_counter()
        bundle, model = load_model(method, settings.device)
        audio = mono16k(vocals, torch, F)
        t1 = time.perf_counter()
        em = emissions(model, audio, settings, torch)
        del model
        if settings.device == "cuda":
            torch.cuda.empty_cache()
        labels = tuple(bundle.get_labels())
        if em.shape[1] != len(labels):
            raise RuntimeError(f"the network gives {em.shape[1]} classes for {len(labels)} labels")
        em = np.concatenate([em, np.zeros((em.shape[0], 1), np.float32)], axis=1)   # the star: log-probability 0
        t2 = time.perf_counter()
        seq, owner = targets(lyrics, labels, method, settings.stars)
        starts, ends, char_scores = path_times(em, seq, owner, len(lyrics.syllables), labels.index("-"), torch, F)
        return starts, ends, char_scores, {
            "device": settings.device, "frames": int(em.shape[0]), "labels": len(seq),
            "timings_s": {"load": round(t1 - t0, 2), "emissions": round(t2 - t1, 2),
                          "align": round(time.perf_counter() - t2, 2)}}


def align(text: str, vocals: np.ndarray, out: Path | str, settings: Settings = Settings(), *,
          aligner=None) -> Result:
    """Time every syllable of `text` against the vocal stem (the module docstring); out/lyrics.json is the cache.
    Unavailable when the aligner cannot run here; a ValueError for a stem that is not (2, n) or a text with no word.
    `aligner`: what runs the network and the alignment (Torchaudio(); tests stand in for it)."""
    aligner = aligner or Torchaudio()
    vocals = np.asarray(vocals)
    if vocals.ndim != 2 or vocals.shape[0] != 2 or vocals.shape[1] == 0:
        raise ValueError(f"the vocal stem must be a stereo (2, n) array, not shape {vocals.shape}")
    lyrics = parse(text)
    n = len(lyrics.syllables)
    if n == 0:
        raise ValueError("the lyrics hold no word")
    libs = aligner.versions()
    key = cache_key(vocals, text, settings, libs)
    path = Path(out) / "lyrics.json"
    done = _done(path, key, n)
    if done is not None:
        return Result(lyrics, tuple(done["times"]["starts"]), tuple(done["times"]["ends"]), path, True, done)
    starts, ends, char_scores, run = aligner.run(lyrics, vocals, settings)
    spelled = sum(1 for x in starts if x is not None)
    starts, ends = _spread(starts, ends)
    method = METHODS[settings.method]
    info = {"engine": ENGINE, "version": VERSION, "key": key, "settings": asdict(settings), "versions": libs,
            "method": {"name": settings.method, "bundle": method.bundle, "weights_sha256": method.sha256},
            "input": {"sample_rate": SAMPLE_RATE, "samples": int(vocals.shape[1]),
                      "seconds": round(vocals.shape[1] / SAMPLE_RATE, 3)},
            "counts": {"syllables": n, "words": lyrics.words, "lines": lyrics.lines,
                       "sections": sum(1 for x in lyrics.syllables if x.gap), "spelled_syllables": spelled,
                       "unspelled_words": _unspelled_words(lyrics), "markup_dropped": lyrics.dropped,
                       "frames": run.get("frames"), "labels": run.get("labels")},
            "confidence": confidence(lyrics, char_scores), "device": run.get("device", settings.device),
            "timings_s": run.get("timings_s"),
            "times": {"starts": [round(x, 4) for x in starts], "ends": [round(x, 4) for x in ends]}}
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(info, indent=1), encoding="utf-8")
    os.replace(part, path)
    return Result(lyrics, tuple(info["times"]["starts"]), tuple(info["times"]["ends"]), path, False, info)


def _unspelled_words(lyrics: Lyrics) -> int:
    return sum(1 for s in lyrics.word_spellings() if not s)


def confidence(lyrics: Lyrics, char_scores: list[list[float]]) -> dict:
    """Per word the mean probability of its characters on the path; the median over the song, its 10th
    percentile, the share of words under LOW_SCORE, and whether the median is under LOW_MEDIAN (numbers only)."""
    words: dict[int, list[float]] = {}
    for s, sc in zip(lyrics.syllables, char_scores):
        words.setdefault(s.word, []).extend(sc)
    scores = np.array([np.mean(v) for v in words.values() if v])
    if not len(scores):
        return {"words_scored": 0, "median": None, "p10": None, "low_share": None, "low": True}
    median = float(np.median(scores))
    return {"words_scored": int(len(scores)), "median": round(median, 3),
            "p10": round(float(np.percentile(scores, 10)), 3),
            "low_share": round(float(np.mean(scores < LOW_SCORE)), 3), "low": median < LOW_MEDIAN}
