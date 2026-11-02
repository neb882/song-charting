"""The allin1 side of the sections engine (engines/sections.py): a script run by the Python that has allin1, never
imported by songcharter, so All-In-One's code and dependencies stay behind a process boundary.

    <allin1 python> -I allin1_runner.py probe <out.json>   # the package, its versions, CUDA, the attention backend
    <allin1 python> -I allin1_runner.py run <job.json>     # segments of the stems on stdin, written to job["out"]

Either package that carries All-In-One's code works: all-in-one-infer (`allin1_infer`: pure-PyTorch neighbourhood
attention and madmom-infer, so nothing to compile) first, then the original allin1 (`allin1`, which needs NATTEN's
<= 0.17 ops and madmom). Both have the same pieces, and only these are used:

  * the spectrogram chain of its `spectrogram` module (frames of 2048 at 100 fps, STFT, 12 bands per octave from
    30 Hz to 17 kHz, log(1 + x)), run on the four stems it is sent;
  * `models.allinone.AllInOne` and `models.ensemble.Ensemble`, built from the checkpoint files the job names. The
    caller has checked them against their pinned SHA-256; they are pickles, and that check is what makes loading
    them safe;
  * `postprocessing`: allin1's own decoding of the network's output into segments, beats and downbeats (what its
    `helpers.run_inference` does after the forward pass).

The stems come on stdin, not as files: bass, drums, other and vocals, each the mono int16 array madmom reads from
a stem WAV that Demucs wrote for allin1 (the caller makes them), little-endian, one after the other. Nothing is
written but the result. `analyze()` is not used: it would separate the song again with its own Demucs and download
unpinned weights. Only the standard library, numpy, torch, omegaconf and the package are imported here, never
songcharter.
"""
from __future__ import annotations

import importlib
import importlib.metadata as md
import json
import os
import sys
import time
from pathlib import Path

PACKAGES = (("allin1_infer", "all-in-one-infer"), ("allin1", "allin1"))  # (module, distribution), in order
PARTS = ("spectrogram", "postprocessing", "models.allinone", "models.ensemble")
STEMS = ("bass", "drums", "other", "vocals")   # the order on stdin, and the order allin1 stacks them


def load_package() -> tuple[str, str]:
    """The first All-In-One package that imports with every part used here: (module, distribution)."""
    errors = []
    for module, dist in PACKAGES:
        try:
            for part in ("",) + PARTS:
                importlib.import_module(module + ("." + part if part else ""))
            return module, dist
        except Exception as e:  # noqa: BLE001 - any import failure means "try the next one"; the caller is told
            errors.append(f"{module}: {type(e).__name__}: {e}")
    raise ImportError("no All-In-One package imports here (" + "; ".join(errors) + ")")


def _version(dist: str) -> str | None:
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return None


def attention(module: str) -> str:
    """The neighbourhood attention the model runs on: "torch" (all-in-one-infer's own), or NATTEN and its version
    (a shim reports itself in its version string)."""
    if module == "allin1_infer":
        backend = getattr(importlib.import_module("allin1_infer.models.dinat"), "NA_BACKEND", "torch")
        if backend == "torch":
            return "torch"
    natten = sys.modules.get("natten")
    return f"natten {getattr(natten, '__version__', '?')}"


def _write(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def probe(out: Path) -> None:
    import torch
    module, dist = load_package()
    _write(out, {"package": dist, "module": module, "version": _version(dist), "torch": torch.__version__,
                 "cuda": bool(torch.cuda.is_available()), "attention": attention(module),
                 "python": sys.version.split()[0], "platform": sys.platform})


def _model(module: str, checkpoints: list[str], device: str):
    import torch
    from omegaconf import OmegaConf
    allinone = importlib.import_module(f"{module}.models.allinone")
    models = []
    for path in checkpoints:
        ckpt = torch.load(path, map_location=device, weights_only=False)  # hash-checked by the caller
        model = allinone.AllInOne(OmegaConf.create(ckpt["config"])).to(device)
        model.load_state_dict(ckpt["state_dict"])
        models.append(model.eval())
    if len(models) == 1:
        return models[0]
    return importlib.import_module(f"{module}.models.ensemble").Ensemble(models).to(device).eval()


def spectrogram(module: str, stems: dict) -> "np.ndarray":
    """allin1's input, (4, frames, bins) float32: its spectrogram chain on each mono int16 stem, as its
    `extract_spectrograms` runs it on stem WAVs (all-in-one-infer's `build_spec_processor`, or the same chain
    built from allin1's own imports)."""
    import numpy as np
    sp = importlib.import_module(f"{module}.spectrogram")
    if hasattr(sp, "build_spec_processor"):
        processor = sp.build_spec_processor()
    else:  # allin1 1.x builds it inside extract_spectrograms, from these names
        processor = sp.SequentialProcessor([
            sp.FramedSignalProcessor(frame_size=2048, fps=int(44100 / 441)), sp.ShortTimeFourierTransformProcessor(),
            sp.FilteredSpectrogramProcessor(num_bands=12, fmin=30, fmax=17000, norm_filters=True),
            sp.LogarithmicSpectrogramProcessor(mul=1, add=1)])
    return np.stack([processor(sp.Signal(stems[name], sample_rate=44100)) for name in STEMS])


def _infer(module: str, checkpoints: list[str], spec, device: str) -> tuple[dict, float, float]:
    import torch
    post = importlib.import_module(f"{module}.postprocessing")
    t0 = time.perf_counter()
    model = _model(module, checkpoints, device)
    t1 = time.perf_counter()
    with torch.no_grad():
        logits = model(torch.from_numpy(spec).unsqueeze(0).to(device))
        metrical = post.postprocess_metrical_structure(logits, model.cfg)
        segments = post.postprocess_functional_structure(logits, model.cfg)
    out = {"segments": [[float(s.start), float(s.end), str(s.label)] for s in segments],
           "bpm": post.estimate_tempo_from_beats(metrical["beats"]),
           "beats": [float(b) for b in metrical["beats"]], "downbeats": [float(b) for b in metrical["downbeats"]]}
    out["bpm"] = None if out["bpm"] is None else float(out["bpm"])
    return out, round(t1 - t0, 2), round(time.perf_counter() - t1, 2)


def read_stems(stream, samples: int) -> dict:
    """The four mono int16 stems from a binary stream."""
    import numpy as np
    data = stream.read()
    if len(data) != 2 * samples * len(STEMS):
        raise ValueError(f"expected {len(STEMS)} stems of {samples} int16 samples on stdin, got {len(data)} bytes")
    a = np.frombuffer(data, dtype="<i2").reshape(len(STEMS), samples).astype(np.int16)
    return dict(zip(STEMS, a))


def run(job_path: Path, stream=None) -> None:
    import torch
    job = json.loads(job_path.read_text(encoding="utf-8"))
    module, dist = load_package()
    if job.get("threads"):
        torch.set_num_threads(int(job["threads"]))
    torch.manual_seed(int(job.get("seed", 0)))
    t0 = time.perf_counter()  # timings are reported only
    spec = spectrogram(module, read_stems(stream or sys.stdin.buffer, int(job["samples"])))
    t_spec = round(time.perf_counter() - t0, 2)
    device, fallback = job["device"], None
    try:
        result, t_load, t_infer = _infer(module, job["checkpoints"], spec, device)
    except torch.cuda.OutOfMemoryError as e:
        if device == "cpu":
            raise
        torch.cuda.empty_cache()
        fallback = f"CUDA ran out of memory ({str(e).splitlines()[0][:120]}); analysed on the CPU"
        device = "cpu"
        result, t_load, t_infer = _infer(module, job["checkpoints"], spec, device)
    _write(Path(job["out"]), {
        **result, "package": dist, "version": _version(dist), "torch": torch.__version__,
        "attention": attention(module), "device": device, "fallback": fallback, "threads": torch.get_num_threads(),
        "frames": int(spec.shape[1]),
        "seconds": {"spectrogram": t_spec, "load": t_load, "inference": t_infer,
                    "total": round(time.perf_counter() - t0, 2)}})


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("probe", "run"):
        print("usage: allin1_runner.py probe <out.json> | run <job.json>", file=sys.stderr)
        return 2
    (probe if argv[0] == "probe" else run)(Path(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
