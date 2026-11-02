"""Lead guitar from dvar0/autochart's engine, run as a separate program (DESIGN.md 2.7, route B1).

autochart's engine (`engine/bin/autochart-engine.cjs`, AGPL) runs htdemucs_6s, its fine-tuned Beat This and
Fretformer 2 under onnxruntime-node. Our own job driver (`eval/tools/autochart/ac_headless.cjs`, written from reading
the app's code) writes the job the app would write and assembles the song folder; this module runs that driver once
per take, behind a process boundary, so no AGPL code is imported.

  * **Takes.** One run per seed (the engine's default seed first), Expert only: the build reduces the other levels
    and splices the takes (takes.py). All takes share one work folder, where the engine caches its separation and
    beat map per audio file, so every take after the first pays only for the transcription.
  * **Input.** The gapless decode written as WAV, not the user's MP3, so the takes' times are seconds of our decode.
  * **Cache.** A take whose folder holds notes.chart and a summary.json for the same input (SHA-256), seed, sampling
    settings and engine version is reused.
  * **Devices.** "cpu", "cuda" or "webgpu" (the engine's own names). With "cuda" the engine itself would move the
    transcriber to WebGPU whenever a WebGPU adapter answers its probe, even a software one that runs on the CPU (seen
    in WSL: 1031 s for a take that took 319 s on CUDA), so the transcriber is pinned to the requested device with the
    engine's AUTOCHART_ONNX_TRANSCRIBER_DEVICE (unless it is set already). The engine still falls back to the CPU by
    itself when a provider fails to load; the devices it used are in each take's summary, and a take that did not
    run on the requested device is not reused.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from .. import audio as A

DEFAULT_SEED = 20260609          # the engine's own default seed
TEMPERATURE, TOP_P = 0.95, 0.98   # the app's "Standard" preset (the driver's defaults)
REPO_INSTALL = Path(__file__).resolve().parents[2] / "eval" / "tools" / "autochart"


@dataclass(frozen=True)
class Install:
    node: str            # the node executable
    driver: Path         # ac_headless.cjs
    app_root: Path       # the autochart checkout (engine/ inside it)
    models: Path         # the Fretformer 2 models (fetch_models.sh)


@dataclass(frozen=True)
class Take:
    seed: int
    chart: Path          # notes.chart
    summary: dict        # the driver's autochart_run/summary.json
    cached: bool
    seconds: float       # wall time of this run (0 when cached)

    @property
    def devices(self) -> dict | None:
        runs = self.summary.get("runs") or [{}]
        return runs[0].get("devices")


def find_install(root: Path | str | None = None, node: str | None = None) -> Install:
    """The engine install: `root` (default $SONGCHARTER_AUTOCHART, else eval/tools/autochart after its setup.sh) and
    node ($SONGCHARTER_NODE, else PATH). Raises with what is missing."""
    root = Path(root or os.environ.get("SONGCHARTER_AUTOCHART") or REPO_INSTALL)
    node = node or os.environ.get("SONGCHARTER_NODE") or shutil.which("node")
    inst = Install(node or "", root / "ac_headless.cjs", root / "src", root / "models")
    missing = []
    if not node:
        missing.append("node (install Node.js, or set SONGCHARTER_NODE)")
    if not inst.driver.is_file():
        missing.append(f"the driver {inst.driver}")
    if not (inst.app_root / "engine" / "bin" / "autochart-engine.cjs").is_file():
        missing.append(f"autochart's engine under {inst.app_root} (run setup.sh)")
    if not (inst.models / "fretformer-v2" / "manifest.json").is_file():
        missing.append(f"the Fretformer 2 models under {inst.models} (run fetch_models.sh)")
    if not (root / "node_modules" / "onnxruntime-node").is_dir():
        missing.append(f"onnxruntime-node under {root / 'node_modules'} (run npm ci there)")
    if missing:
        raise FileNotFoundError("autochart engine not ready: " + "; ".join(missing))
    return inst


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def _on_device(summary: dict, device: str | None) -> bool:
    """Whether every run's transcriber used `device` (summaries without devices count as yes)."""
    if device is None:
        return True
    used = [(r.get("devices") or {}).get("transcriber") for r in summary.get("runs") or []]
    return all(u in (None, device) for u in used)


def _done(folder: Path, input_sha: str, seed: int, device: str | None = None) -> dict | None:
    """The summary of a finished take in `folder` for this input and seed (and, if given, made on `device`), else
    None."""
    chart, summary = folder / "notes.chart", folder / "autochart_run" / "summary.json"
    if not (chart.is_file() and summary.is_file()):
        return None
    try:
        s = json.loads(summary.read_text(encoding="utf-8"))
    except ValueError:
        return None
    runs = s.get("runs") or []
    ok = (s.get("inputSha256") == input_sha and s.get("seed") == seed and s.get("difficulties") == ["expert"]
          and s.get("temperature") == TEMPERATURE and s.get("topP") == TOP_P
          and runs and all(r.get("status") == "completed" for r in runs) and _on_device(s, device))
    return s if ok else None


def generate(install: Install, audio: Path | str, out: Path | str, seeds: Sequence[int] = (DEFAULT_SEED,), *,
             device: str = "cpu", work: Path | str | None = None, timeout_s: float = 3600, ffmpeg: str | None = None,
             title: str | None = None, artist: str | None = None,
             run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> list[Take]:
    """One Expert take per seed of `audio` (a WAV of the gapless decode), in out/seed_<seed>/ (a song folder:
    notes.chart, song.ini, song.ogg, autochart_run/). Takes already there for the same input and seed are reused.
    A failed run raises RuntimeError with the driver's last lines."""
    audio, out = Path(audio).resolve(), Path(out).resolve()
    if not audio.is_file():
        raise FileNotFoundError(f"autochart input {audio} does not exist")
    if len(set(seeds)) != len(seeds) or not seeds:
        raise ValueError(f"seeds must be distinct and at least one, not {list(seeds)}")
    if device not in ("cpu", "cuda", "webgpu"):
        raise ValueError(f"device is cpu, cuda or webgpu, not {device!r}")
    work = Path(work).resolve() if work else out / "work"
    input_sha = sha256(audio)
    takes = []
    for seed in seeds:
        folder = out / f"seed_{seed}"
        summary = _done(folder, input_sha, seed, device)
        if summary is not None:
            takes.append(Take(seed, folder / "notes.chart", summary, True, 0.0))
            continue
        folder.mkdir(parents=True, exist_ok=True)
        work.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "AC_SEED": str(seed), "AC_DIFFICULTIES": "expert", "AC_DEVICE": device,
               "AC_TEMPERATURE": str(TEMPERATURE), "AC_TOP_P": str(TOP_P), "AC_TIMEOUT_S": str(int(timeout_s)),
               "AC_APP_ROOT": str(install.app_root), "AC_MODELS": str(install.models),
               "AUTOCHART_FFMPEG_PATH": ffmpeg or A.ffmpeg_exe()}
        if device in ("cpu", "cuda"):
            env.setdefault("AUTOCHART_ONNX_TRANSCRIBER_DEVICE", device)
        if title:
            env["AC_TITLE"] = title
        if artist:
            env["AC_ARTIST"] = artist
        t0 = time.perf_counter()  # reported only
        proc = run([install.node, str(install.driver), "--audio", str(audio), "--out", str(folder), "--work", str(work)],
                   env=env, cwd=str(install.driver.parent), capture_output=True, text=True,
                   timeout=timeout_s + 600)
        seconds = round(time.perf_counter() - t0, 1)
        summary = _done(folder, input_sha, seed)
        if proc.returncode != 0 or summary is None:
            tail = "\n".join((proc.stderr or "").strip().splitlines()[-8:])
            raise RuntimeError(f"autochart seed {seed} failed (exit {proc.returncode}):\n{tail}")
        takes.append(Take(seed, folder / "notes.chart", summary, False, seconds))
    return takes
