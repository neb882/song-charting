"""Stem separation: one Demucs pass on the decoded song, shared by every stage (DESIGN.md 2.2).

    stems, info = separate(mix)                 # mix: float32 (2, n) at 44.1 kHz from audio.decode
    stems["drums"], stems["bass"], stems["guitar"], stems["vocals"], ...   # float32 (2, n), sample-aligned to mix

  * **Model.** htdemucs_6s by default (drums, bass, other, vocals, guitar, piano); htdemucs_ft for the M2 stem
    comparison. The weights come from the Hugging Face hub at a pinned revision, and every file's SHA-256 is checked
    before it is loaded; they are downloaded on first use, never bundled. They are treated as non-commercial
    (DESIGN.md 4.2).
  * **On the array, never the file.** Separating an MP3 directly made the 6s stems 1105 samples (the encoder delay)
    late; the decoded array has the delay removed, so the stems line up with it.
  * **Deterministic.** Demucs's random time shift draws from Python's `random`; it and torch are seeded right before
    the call, so two runs on one device give the same stems.
  * **Device.** CUDA when a CUDA kernel runs here (`cuda_works`), else the CPU: torch.cuda.is_available() alone is
    also true on a GPU the torch build has no kernels for. CUDA running out of memory falls back to the CPU too, and
    `info` says why the CPU was used (the UI tells the user).
  * **Cache.** Stems are cached as float32 WAV (the decoded mix peaks above 1.0, which an integer format would clip),
    keyed by the samples and every setting that changes the result, the device among them (CUDA's stems differ from
    the CPU's in their last bits). A cached run returns the same arrays. info.json is written last and is the hit,
    but only when every stem it lists is there and reads and it says they were made on the device asked for: a
    folder half deleted (or half written) is separated again, never an error. A hit says this call's fallback, not
    the one of the run that made it.
      - **The keys since v0.5.0.** The CPU's key is the key every earlier version gave on either device, so stems
        already cached on the CPU still answer. Stems made on CUDA get a key of their own: CUDA stems cached by an
        earlier version sit under the CPU's key, answer no CUDA request (each such song is separated once more on
        CUDA, under the new key) and no CPU request either (their info.json says cuda: separated again on the CPU,
        in place).
      - CUDA running out of memory gives CPU stems, under the CPU's key (a CPU stem folder there already answers
        it), and a later CUDA request separates on CUDA again rather than taking them.

Needs torch and demucs >= 4.1 (`pip install songcharter[separate]`); importing this module does not.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from . import audio as A
from .errors import ToolError

SAMPLE_RATE = A.SAMPLE_RATE
DEFAULT_MODEL = "htdemucs_6s"


@dataclass(frozen=True)
class ModelFiles:
    repo: str                    # Hugging Face repository
    revision: str                # the commit the hashes belong to
    bag: str                     # the bag definition (yaml)
    files: dict[str, str]        # file name -> SHA-256, the bag's yaml included


MODELS = {
    "htdemucs_6s": ModelFiles("adefossez/HTDemucs-6s", "3c5ee475be622df764938de97e4281a7b07ffa58", "htdemucs_6s.yaml",
                              {"htdemucs_6s.yaml": "207405151270af8fd81c2373c25d27950916682ac91dca7884a11ce13dad6f58",
                               "5c90dfd2.safetensors":
                                   "d2a1745f0744721f6b8ca5bf469b67c651ea5ed1b52998cab033b2158609d411"}),
    "htdemucs_ft": ModelFiles("adefossez/HTDemucs-ft", "d74ac89c3a1e874fc78f152555cf4d8533f06cd4", "htdemucs_ft.yaml",
                              {"htdemucs_ft.yaml": "69470b8c1bbd674437b51bc9fb491327a10ab0396b702c93389b9cf750016346",
                               "f7e0c4bc.safetensors":
                                   "2c85ab3c62dd6edd8e0b965e38b16fd1cdde357cc25de6b6bc9ce7c83f60925f",
                               "d12395a8.safetensors":
                                   "5b01a97567ae9a3178a6236fb520251045c03eb8834bc8c24a4eec11d6c8fb56",
                               "92cfc3b6.safetensors":
                                   "a241863551f30d01c42bd7b97da40839922ead3acb0f1fcab25682f55b4eeb59",
                               "04573f0d.safetensors":
                                   "68854b0d7c2b3274723b5761f6fd9f5aec5f1bcd3f0de7c1669546fdb7871b7c"}),
}


@dataclass(frozen=True)
class SeparationInfo:
    model: str
    revision: str | None         # None for a model object passed in (tests)
    device: str                  # the device the stems came from
    fallback: str | None         # why the CPU was used instead of CUDA, or None
    seconds: float               # wall time of the separation (0 for a cache hit)
    cached: bool
    key: str                     # the cache key
    seed: int
    shifts: int
    overlap: float


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def model_paths(name: str, download: Callable[..., str] | None = None) -> dict[str, Path]:
    """The model's files at its pinned revision (downloaded on first use), each checked against its SHA-256."""
    if name not in MODELS:
        raise ValueError(f"unknown separation model {name!r} (known: {', '.join(MODELS)})")
    spec = MODELS[name]
    if download is None:
        from huggingface_hub import hf_hub_download as download
    out = {}
    for file, sha in spec.files.items():
        path = Path(download(spec.repo, file, revision=spec.revision))
        got = _sha256(path)
        if got != sha:
            raise ToolError(f"{name}: {file} has SHA-256 {got}, not the pinned {sha}; delete it and run again")
        out[file] = path
    return out


def load_model(name: str = DEFAULT_MODEL, download: Callable[..., str] | None = None):
    """A Demucs bag of models from its pinned, hash-checked files."""
    import yaml
    from demucs.apply import BagOfModels
    from demucs.hf import load_safetensors_model
    paths = model_paths(name, download)
    bag = yaml.safe_load(paths[MODELS[name].bag].read_text(encoding="utf-8"))
    models = [load_safetensors_model(paths[f"{sig}.safetensors"]) for sig in bag["models"]]
    model = BagOfModels(models, bag.get("weights"), bag.get("segment"))
    model.eval()
    return model


def cache_key(mix: np.ndarray, model: str, revision: str | None, seed: int, shifts: int, overlap: float,
              device: str = "cpu") -> str:
    """A hash of the samples and every setting that changes the stems, the device among them ("cpu" or "cuda"). The
    CPU's key is exactly the device-less key of the versions before v0.5.0 (the module docstring, Cache)."""
    h = hashlib.sha256()
    a = np.ascontiguousarray(mix, dtype="<f4")
    settings = (a.shape, model, revision, seed, shifts, overlap, SAMPLE_RATE)
    h.update(repr(settings if device == "cpu" else (*settings, device)).encode())
    h.update(a.tobytes())
    return h.hexdigest()[:24]


def _cached(cache_dir: Path | str | None, key: str, mix: np.ndarray, device: str,
            fallback: str | None) -> tuple[dict[str, np.ndarray], SeparationInfo] | None:
    """The stems in cache_dir/<key>/ and their info with this call's `fallback`, else None: a hit only when every
    stem info.json lists is there and reads, as long as the mix, and info.json says they were made on `device` (CUDA
    stems of an earlier version sit under the CPU's key)."""
    folder = Path(cache_dir) / key if cache_dir is not None else None
    if folder is None or not (folder / "info.json").exists():
        return None
    try:  # a folder half deleted is a miss
        meta = json.loads((folder / "info.json").read_text(encoding="utf-8"))
        if meta["info"]["device"] != device:
            return None
        stems = {s: A.read_wav(folder / f"{s}.wav")[0] for s in meta["stems"]}
    except (OSError, RuntimeError, ValueError, KeyError, TypeError):  # soundfile's errors are RuntimeErrors
        return None
    if not stems or any(y.shape != mix.shape for y in stems.values()):
        return None
    return stems, SeparationInfo(**{**meta["info"], "seconds": 0.0, "cached": True, "fallback": fallback})


def cuda_works() -> tuple[bool, str | None]:
    """Whether a CUDA kernel runs here, and the error's first line when torch has CUDA but the kernel failed (as on a
    GPU this torch build has no kernels for: "no kernel image is available"). The sections runner probes the same
    way in allin1's Python."""
    import torch
    if not torch.cuda.is_available():
        return False, None
    try:
        torch.ones(1, device="cuda").add_(1).item()
        return True, None
    except Exception as e:  # noqa: BLE001  any failure means "not on this GPU"; the caller says why
        return False, f"{type(e).__name__}: {(str(e).strip().splitlines() or [''])[0][:200]}"


def _run(model, mix: np.ndarray, device: str, seed: int, shifts: int, overlap: float, progress: bool) -> dict:
    import torch
    from demucs.apply import apply_model
    wav = torch.from_numpy(np.ascontiguousarray(mix, dtype=np.float32))
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8   # demucs.api's normalization
    random.seed(seed)                          # the random time shift (demucs apply.py) draws from `random`
    torch.manual_seed(seed)
    with torch.no_grad():
        out = apply_model(model, ((wav - mean) / std)[None], shifts=shifts, split=True, overlap=overlap,
                          device=device, progress=progress)[0]
    out = out * std + mean
    return {name: out[i].cpu().numpy().astype(np.float32) for i, name in enumerate(model.sources)}


def separate(mix: np.ndarray, sample_rate: int = SAMPLE_RATE, *, model: Any = DEFAULT_MODEL, device: str = "auto",
             seed: int = 0, shifts: int = 1, overlap: float = 0.25, cache_dir: Path | str | None = None,
             progress: bool = False) -> tuple[dict[str, np.ndarray], SeparationInfo]:
    """Stems of the decoded mix (float32, (2, n) at 44.1 kHz), each as long as the mix, and how they were made.

    model:  a name in MODELS (loaded from its pinned files) or a Demucs model object (tests).
    device: "auto" (CUDA if a kernel runs: cuda_works), "cuda" or "cpu". CUDA out of memory retries on the CPU.
    cache_dir: if given, stems are read from and written to cache_dir/<key>/ (float32 WAV, then info.json), the key
           the device's (cache_key; info.key: the folder the stems are in).
    """
    if sample_rate != SAMPLE_RATE:
        raise ValueError(f"separate needs {SAMPLE_RATE} Hz audio, not {sample_rate} Hz")
    if mix.ndim != 2 or mix.shape[0] != 2:
        raise ValueError(f"separate needs a stereo (2, n) array, not shape {mix.shape}")
    name = model if isinstance(model, str) else type(model).__name__
    revision = MODELS[model].revision if isinstance(model, str) and model in MODELS else None
    if isinstance(model, str) and model not in MODELS:
        raise ValueError(f"unknown separation model {model!r} (known: {', '.join(MODELS)})")
    fallback = None
    if device == "auto":   # resolved before the cache: the key is the device's
        works, why = cuda_works()
        device = "cuda" if works else "cpu"
        if why:
            fallback = f"CUDA does not run here ({why}); separated on the CPU"
    key = cache_key(mix, name, revision, seed, shifts, overlap, device)
    hit = _cached(cache_dir, key, mix, device, fallback)
    if hit is not None:
        return hit

    import torch
    net = load_model(model) if isinstance(model, str) else model
    t0 = time.perf_counter()  # wall time is reported only; nothing depends on it
    try:
        stems = _run(net, mix, device, seed, shifts, overlap, progress)
    except torch.cuda.OutOfMemoryError as e:
        if device == "cpu":
            raise
        torch.cuda.empty_cache()
        fallback = f"CUDA ran out of memory ({str(e).splitlines()[0][:120]}); separated on the CPU"
        device, key = "cpu", cache_key(mix, name, revision, seed, shifts, overlap, "cpu")   # CPU stems: its key
        hit = _cached(cache_dir, key, mix, device, fallback)
        if hit is not None:
            return hit
        stems = _run(net, mix, device, seed, shifts, overlap, progress)
    for s, y in stems.items():
        if y.shape != mix.shape:
            raise RuntimeError(f"stem {s} has shape {y.shape}, not the mix's {mix.shape}")
    info = SeparationInfo(name, revision, device, fallback, round(time.perf_counter() - t0, 2), False, key, seed,
                          shifts, overlap)
    folder = Path(cache_dir) / key if cache_dir is not None else None
    if folder is not None:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "info.json").unlink(missing_ok=True)  # written last: a folder without it is never a hit
        for s, y in stems.items():
            A.write_wav(y, folder / f"{s}.wav")
        (folder / "info.json").write_text(json.dumps({"stems": list(stems), "info": asdict(info)}, indent=1),
                                          encoding="utf-8")
    return stems, info
