"""Lead guitar from dvar0/autochart's engine, run as a separate program (DESIGN.md 2.7, route B1).

autochart's engine (`engine/bin/autochart-engine.cjs`, AGPL) runs htdemucs_6s, its fine-tuned Beat This and
Fretformer 2 under onnxruntime-node. Our own job driver (`eval/tools/autochart/ac_headless.cjs`, written from reading
the app's code) writes the job the app would write and assembles the song folder; this module runs that driver once
per take, behind a process boundary, so no AGPL code is imported.

  * **Takes.** One run per seed (the engine's default seed first), Expert only: the build reduces the other levels
    and splices the takes (takes.py). All takes share one work folder, where the engine caches its separation and
    beat map per audio file, so every take after the first pays only for the transcription.
  * **Input.** The gapless decode written as WAV, not the user's MP3, so the takes' times are seconds of our decode.
  * **Cache.** A take is reused when its folder holds notes.chart, the driver's summary.json of a completed run and
    our take.json, written after the run, with the same key: the input (SHA-256), the seed, the sampling settings
    and the install (`install_key`: engine/manifest.json's engineVersion, and a SHA-256 over the engine's manifest
    and catalog, which pins every model file's SHA-256, the models' manifest, onnxruntime-node's package.json and
    the driver). So an updated engine, model set or driver runs every take again, and a take without take.json (an
    older songcharter's) is run again too. A take whose transcriber did not run on the requested device is not
    reused either.
  * **Devices.** "cpu", "cuda" or "webgpu" (the engine's own names). With "cuda" the engine itself would move the
    transcriber to WebGPU whenever a WebGPU adapter answers its probe, even a software one that runs on the CPU (seen
    in WSL: 1031 s for a take that took 319 s on CUDA), so the transcriber is pinned to the requested device with the
    engine's AUTOCHART_ONNX_TRANSCRIBER_DEVICE (unless it is set already). The engine still falls back to the CPU by
    itself when a provider fails to load; the devices it used are in each take's summary.
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
from ..errors import ToolError

DEFAULT_SEED = 20260609          # the engine's own default seed
TEMPERATURE, TOP_P = 0.95, 0.98   # the app's "Standard" preset (the driver's defaults)
REPO_INSTALL = Path(__file__).resolve().parents[2] / "eval" / "tools" / "autochart"
TAKE = "take.json"               # in each take's folder: the key it was made with, written once the run succeeded


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


def install_key(install: Install) -> dict:
    """What a take depends on in the install: engine/manifest.json's engineVersion (a date-based name that may stay
    the same across commits) and a SHA-256 over the files that define the engine, the models and the job: the
    engine's manifest and catalog (the catalog pins every model file's SHA-256, which fetch_models.sh checks), the
    models' manifest, onnxruntime-node's package.json and our driver. A missing file counts as absent."""
    engine, root = install.app_root / "engine", install.driver.parent
    files = {"engine/manifest.json": engine / "manifest.json", "engine/catalog.json": engine / "catalog.json",
             "models/fretformer-v2/manifest.json": install.models / "fretformer-v2" / "manifest.json",
             "onnxruntime-node/package.json": root / "node_modules" / "onnxruntime-node" / "package.json",
             "driver": install.driver}
    h = hashlib.sha256()
    for name, path in files.items():
        data = path.read_bytes() if path.is_file() else None
        h.update(f"{name}:{-1 if data is None else len(data)}:".encode())
        h.update(data or b"")
    try:
        version = json.loads(files["engine/manifest.json"].read_text(encoding="utf-8")).get("engineVersion")
    except (OSError, ValueError, AttributeError):
        version = None
    return {"engineVersion": version, "install": h.hexdigest()}


def take_key(input_sha: str, seed: int, install: dict) -> dict:
    """A take's key (take.json): the input, the seed, the sampling settings and the install (install_key)."""
    return {"inputSha256": input_sha, "seed": seed, "difficulties": ["expert"], "temperature": TEMPERATURE,
            "topP": TOP_P, **install}


def _summary(folder: Path, key: dict) -> dict | None:
    """The driver's summary of a completed run in `folder` for the key's input, seed and settings, else None."""
    chart, summary = folder / "notes.chart", folder / "autochart_run" / "summary.json"
    if not (chart.is_file() and summary.is_file()):
        return None
    try:
        s = json.loads(summary.read_text(encoding="utf-8"))
    except ValueError:
        return None
    runs = s.get("runs") or []
    ok = (s.get("inputSha256") == key["inputSha256"] and s.get("seed") == key["seed"]
          and s.get("difficulties") == key["difficulties"] and s.get("temperature") == key["temperature"]
          and s.get("topP") == key["topP"] and runs and all(r.get("status") == "completed" for r in runs))
    return s if ok else None


def _done(folder: Path, key: dict, device: str | None = None) -> dict | None:
    """The summary of a finished take in `folder` made with this key (its take.json) and, if given, with its
    transcriber on `device`, else None."""
    try:
        made = json.loads((folder / TAKE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    s = _summary(folder, key) if made == key else None
    return s if s is not None and _on_device(s, device) else None


def generate(install: Install, audio: Path | str, out: Path | str, seeds: Sequence[int] = (DEFAULT_SEED,), *,
             device: str = "cpu", work: Path | str | None = None, timeout_s: float = 3600, ffmpeg: str | None = None,
             title: str | None = None, artist: str | None = None,
             run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> list[Take]:
    """One Expert take per seed of `audio` (a WAV of the gapless decode), in out/seed_<seed>/ (a song folder:
    notes.chart, song.ini, song.ogg, autochart_run/, take.json). Takes already there with the same key (input,
    seed, sampling settings, install) are reused. A failed run raises errors.ToolError (a RuntimeError) with the
    driver's last lines."""
    audio, out = Path(audio).resolve(), Path(out).resolve()
    if not audio.is_file():
        raise FileNotFoundError(f"autochart input {audio} does not exist")
    if len(set(seeds)) != len(seeds) or not seeds:
        raise ValueError(f"seeds must be distinct and at least one, not {list(seeds)}")
    if device not in ("cpu", "cuda", "webgpu"):
        raise ValueError(f"device is cpu, cuda or webgpu, not {device!r}")
    work = Path(work).resolve() if work else out / "work"
    input_sha, installed = sha256(audio), install_key(install)
    takes = []
    for seed in seeds:
        folder, key = out / f"seed_{seed}", take_key(input_sha, seed, installed)
        summary = _done(folder, key, device)
        if summary is not None:
            takes.append(Take(seed, folder / "notes.chart", summary, True, 0.0))
            continue
        folder.mkdir(parents=True, exist_ok=True)
        (folder / TAKE).unlink(missing_ok=True)  # a run cut off from here on leaves no hit
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
        try:
            proc = run([install.node, str(install.driver), "--audio", str(audio), "--out", str(folder), "--work",
                        str(work)], env=env, cwd=str(install.driver.parent), capture_output=True, text=True,
                       timeout=timeout_s + 600)
        except subprocess.TimeoutExpired as e:
            raise ToolError(f"autochart seed {seed} did not finish within {e.timeout:.0f} s") from e
        seconds = round(time.perf_counter() - t0, 1)
        summary = _summary(folder, key)
        if proc.returncode != 0 or summary is None:
            tail = "\n".join((proc.stderr or "").strip().splitlines()[-8:])
            raise ToolError(f"autochart seed {seed} failed (exit {proc.returncode}):\n{tail}")
        (folder / TAKE).write_text(json.dumps(key, indent=1), encoding="utf-8")
        takes.append(Take(seed, folder / "notes.chart", summary, False, seconds))
    return takes
