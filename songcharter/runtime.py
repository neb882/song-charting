"""The install's second half (M4-03), run by packaging/linux/install.sh in the environment uv made: Node,
scan-chart, autochart's engine with its models (and, on a GPU lane, onnxruntime-node's CUDA provider), the
pipeline's models, then runtime.json and doctor.json.

    python -m songcharter.runtime setup --home H --app A --lane cpu|cu126|cu132 --lane-reason TEXT
    python -m songcharter.runtime check --home H          # verifies what setup made, downloading nothing

  * **The layout.** H ($SONGCHARTER_HOME, ~/.local/share/songcharter) holds runtime/: node/ (Node 24.19.0),
    scan-chart/ (scan.cjs and its node_modules), autochart/ (src/, the engine at its pinned commit; models/; our
    driver ac_headless.cjs and its node_modules), runtime.json, and state/ (downloads in progress, install.done). The
    pipeline's models go to the per-user cache, ~/.cache/songcharter/models (hf/ for the hub's, adtof/), where the
    pipeline looks for them.
  * **Rerunnable.** Each step first checks its result (a version, a stamp, every file's size and SHA-256) and is done
    at once when it is there. Otherwise it makes it again through a `.part` file or folder renamed into place last, so
    a run cut off anywhere leaves nothing half made that counts as made; `fetch` resumes a download.
  * **runtime.json** is written last, atomically, once every step has its result: the launcher (launch.py) reads it,
    so an install that has not finished is never taken for one that has. doctor.json follows, with the launcher's
    environment.
  * **autochart's archive** is GitHub's zip of the pinned commit. Its bytes are not promised stable, so the zip is not
    hashed: every file in it is checked against the app's packaging/autochart/engine-files.sha256 (path, size and
    SHA-256; none missing, none extra). $SONGCHARTER_AUTOCHART_URL names a mirror of the same archive (a machine that
    cannot reach GitHub's archives, such as the dev container); the check makes a mirror unable to change a byte.
  * **The CUDA provider** comes from onnxruntime-node's own installer (NuGet's Microsoft.ML.OnnxRuntime.Gpu.Linux
    1.27.0), which checks nothing, so its two libraries are checked against the planning job's hashes. On the cpu
    lane it is removed; on cu126 it is installed too, though it needs CUDA 13 (cu132) to load, so the switch to cu132
    after a driver update downloads less.
  * **Exit status** of setup: 0 ok; 1 doctor found problems (doctor.json lists them); 2 a step failed (`songcharter:
    <step> failed: <one line>. Run the same command again to continue.`, also written to $SONGCHARTER_FAILURE when
    install.sh sets it); 3 a bug, with its traceback and that line. check: 0, or 2 with each step that failed.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import http.client
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable

from .errors import SongcharterError, ToolError

LANES = ("cpu", "cu126", "cu132")
GPU_LANES = ("cu126", "cu132")
NODE_VERSION = "24.19.0"      # autochart's own pin (its scripts/runtime-artifacts.json), as the SHA-256 and size
NODE_FILE = f"node-v{NODE_VERSION}-linux-x64.tar.gz"
NODE_URL = f"https://nodejs.org/dist/v{NODE_VERSION}/{NODE_FILE}"
NODE_SHA256 = "f625d97cd707df4ff96254916fbc5ff014f09c09effe5a1e0ca8f6d41a8789d4"
NODE_SIZE = 57_409_532
AUTOCHART_COMMIT = "b5a41e8e44db84d4c7288c946cf35aa2264dcbf5"   # packaging/autochart/make_engine_list.py's
AUTOCHART_URL = f"https://github.com/dvar0/autochart/archive/{AUTOCHART_COMMIT}.zip"
ENGINE_LIST = "packaging/autochart/engine-files.sha256"          # in the app folder
DRIVER_FILES = ("ac_headless.cjs", "package.json", "package-lock.json")   # from the app's eval/tools/autochart
SCAN_FILES = ("scan.cjs", "package.json", "package-lock.json")            # from the app's tools/scan-chart
MODELS_COMPONENT = "fretformer-2-onnx"   # in the engine's catalog.json: Fretformer 2, as fetch_models.sh fetches it
MODELS_URL = "https://huggingface.co/Dvaro/autochart-models/resolve/8a88855d745f0b508f68ac606d7cbdac2878c87d"
ORT_BIN = "node_modules/onnxruntime-node/bin/napi-v6/linux/x64"   # in runtime/autochart
ORT_INSTALL = "node_modules/onnxruntime-node/script/install.js"
PROVIDER = {"libonnxruntime_providers_cuda.so":     # SHA-256 and size of the planning job's copy of 1.27.0
                ("0d3171e422fc7b554cb05af69009b519beec03d6084ebe924782307b29338f39", 251_623_184),
            "libonnxruntime_providers_shared.so":
                ("c6a12593396095f5670160e284c35d1700b7708cf3037b7042e2a5200ccae772", None)}
PROVIDER_OTHER = ("libonnxruntime_providers_tensorrt.so",)   # the installer's third file: not used, removed with them
STAMP = ".songcharter-npm"   # in a folder npm ci filled: its lock's SHA-256 and Node's version
NPM_CI = ("ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund")   # no audit or funding request either
PROGRESS_BYTES = 50 * 10 ** 6   # fetch prints a line every 50 MB
TIMEOUT_S = 60.0                # fetch's socket timeout
ATTEMPTS = 4                    # fetch's tries (3 retries), each resuming the last
RETRY_PAUSE_S = 2.0             # the pause before retry n is n times this
MB = 10 ** 6


class StepFailed(ToolError):
    """A step that could not make its result: the message is its one line."""


def _say(text: str) -> None:
    print(text, flush=True)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def file_ok(path: Path, sha: str | None, size: int | None = None) -> bool:
    """Whether `path` is a file of that size and SHA-256 (each None is not checked)."""
    try:
        if not path.is_file() or (size is not None and path.stat().st_size != size):
            return False
    except OSError:
        return False
    return sha is None or file_sha256(path) == sha


def offline() -> bool:
    return os.environ.get("SONGCHARTER_OFFLINE") == "1"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _write_json(path: Path, data: dict) -> None:
    """`path` written atomically: through path.part and os.replace."""
    part = path.with_name(path.name + ".part")
    part.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(part, path)


def _rmtree(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


# ------------------------------------------------------------------------------------------------ fetch

def _total(response, have: int) -> int | None:
    """The whole file's size from a response to a request that starts at `have`."""
    m = re.match(r"bytes \d+-\d+/(\d+)", response.headers.get("Content-Range") or "")
    if m:
        return int(m.group(1))
    length = response.headers.get("Content-Length")
    return have + int(length) if length and length.isdigit() else None


def download_part(url: str, part: Path | str, size: int | None = None, *, name: str | None = None,
                  say: Callable[[str], None] = _say, attempts: int = ATTEMPTS, timeout: float = TIMEOUT_S,
                  pause: Callable[[float], None] = time.sleep) -> Path:
    """`url` into `part`: the downloader every download of songcharter's own goes through (fetch, and the engines'
    weights in engines/adtof.py and engines/lyrics.py). Resumed with a Range request where `part` holds a start (a
    server that ignores Range sends the whole file again), up to `attempts` tries (3 retries by default, each resuming
    the last) with a `timeout`-s socket timeout. Its lines (`name`: the file's, by default `part`'s name without
    .part): `fetch <name>: <N> MB` (or `resuming at`) first, one every 50 MB, and `fetch <name>: done, <N> MB` once it is
    whole, so every download ends with one (ADTOF's and the lyrics aligner's weights too: M5-08). It is whole once it
    holds `size` bytes, or the length the server gives (Content-Length or Content-Range): a body that ends short of
    that is a cut connection and is tried again, never taken for the file; so is one that breaks off mid-chunk
    (http.client's IncompleteRead). Raises StepFailed, at once for a 4xx but 408 and 429, else after the last try. It
    checks no SHA-256 and renames nothing (the caller does both), and a part left by a failure is resumed by the next
    call."""
    part = Path(part)
    name = name or part.name.removesuffix(".part")
    part.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(attempts):
        have = part.stat().st_size if part.is_file() else 0
        if size is not None and have > size:
            part.unlink()
            have = 0
        if size is not None and have == size:
            break
        headers = {"User-Agent": "songcharter-install", **({"Range": f"bytes={have}-"} if have else {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                if have and r.status != 206:   # the server ignored the Range: the whole file again
                    have = 0
                total = _total(r, have)
                if total is None and size is not None:
                    total = size
                of = "?" if total is None else str(total // MB)
                say(f"fetch {name}: resuming at {have // MB} of {of} MB" if have else f"fetch {name}: {of} MB")
                t0, done = time.monotonic(), have
                mark = (have // PROGRESS_BYTES + 1) * PROGRESS_BYTES
                with open(part, "ab" if have else "wb") as f:
                    for block in iter(lambda: r.read(1 << 20), b""):
                        f.write(block)
                        done += len(block)
                        if done >= mark:
                            rate = (done - have) / MB / max(time.monotonic() - t0, 1e-6)
                            say(f"fetch {name}: {done // MB} of {of} MB, {rate:.1f} MB/s")
                            mark = (done // PROGRESS_BYTES + 1) * PROGRESS_BYTES
            if total is None or done >= total:
                break
            error = f"the connection closed at {done} of {total} bytes"
        except urllib.error.HTTPError as e:
            if e.code == 416 and have:   # nothing after `have`: the .part is whole
                break
            if 400 <= e.code < 500 and e.code not in (408, 429):   # no use asking again
                raise StepFailed(f"could not download {url}: HTTP {e.code} {e.reason}") from e
            error = f"HTTP {e.code} {e.reason}"
        except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
            # a timeout, a reset, no network; HTTPException for a chunked response cut mid-chunk (IncompleteRead) and
            # the other ends http.client sees that are not OSErrors
            error = f"{type(e).__name__}: {getattr(e, 'reason', None) or e}"
        if attempt == attempts - 1:
            raise StepFailed(f"could not download {url} ({attempts} tries): {error}")
        say(f"fetch {name}: {error}; trying again")
        pause(RETRY_PAUSE_S * (attempt + 1))
    say(f"fetch {name}: done, {part.stat().st_size // MB} MB")
    return part


def fetch(url: str, dest: Path | str, sha256: str | None, size: int | None = None, *,
          say: Callable[[str], None] = _say, attempts: int = ATTEMPTS, timeout: float = TIMEOUT_S,
          pause: Callable[[float], None] = time.sleep) -> Path:
    """`url` downloaded to `dest` through dest.part (download_part: resumed, retried, its lines and the done line),
    then checked (its size and SHA-256, where given) and renamed into place. A `dest` already there and right is kept,
    with no request. SONGCHARTER_OFFLINE=1 refuses the download. Raises StepFailed."""
    dest = Path(dest)
    if file_ok(dest, sha256, size):
        return dest
    if offline():
        raise StepFailed(f"{dest.name} is not here and SONGCHARTER_OFFLINE=1 forbids downloading it")
    part = download_part(url, dest.with_name(dest.name + ".part"), size, name=dest.name, say=say, attempts=attempts,
                         timeout=timeout, pause=pause)
    got_size = part.stat().st_size
    if size is not None and got_size != size:
        part.unlink()
        raise StepFailed(f"{url} gave {got_size} bytes, not {size}")
    if sha256 is not None:
        got = file_sha256(part)
        if got != sha256:
            part.unlink()
            raise StepFailed(f"{url} has SHA-256 {got}, not the pinned {sha256}")
    os.replace(part, dest)
    return dest


# ------------------------------------------------------------------------------------------------ the engine list

def read_list(path: Path) -> dict[str, tuple[str, int]]:
    """engine-files.sha256: {path: (sha256, size)}, from its `<sha256>  <size>  <path>` lines."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            sha, size, rel = line.split("  ", 2)
            out[rel] = (sha, int(size))
    return out


def check_tree(root: Path, expected: dict[str, tuple[str, int]]) -> list[str]:
    """What differs between the files under `root` and the list: each listed file that is missing, of another size
    or SHA-256, or not a plain file, and each file (or symlink) the list does not hold. [] when they match."""
    found: dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames + [d for d in dirnames if (Path(dirpath) / d).is_symlink()]:
            p = Path(dirpath) / name
            found[p.relative_to(root).as_posix()] = p
    problems = []
    for rel, (sha, size) in expected.items():
        p = found.get(rel)
        if p is None:
            problems.append(f"missing: {rel}")
        elif p.is_symlink():
            problems.append(f"not a plain file: {rel}")
        elif p.stat().st_size != size:
            problems.append(f"changed: {rel} ({p.stat().st_size} bytes, not {size})")
        elif file_sha256(p) != sha:
            problems.append(f"changed: {rel} (another SHA-256)")
    problems += [f"extra: {rel}" for rel in sorted(set(found) - set(expected))]
    return problems


def extract_zip(archive: Path, dest: Path) -> None:
    """A GitHub archive (one top folder) into `dest`, the top folder dropped; a path that would leave `dest` is
    refused."""
    with zipfile.ZipFile(archive) as z:
        tops = {PurePosixPath(i.filename).parts[0] for i in z.infolist() if i.filename.strip("/")}
        if len(tops) != 1:
            raise StepFailed(f"{archive.name} has {len(tops)} top folders, not one")
        for info in z.infolist():
            rel = PurePosixPath(info.filename).parts[1:]
            if not rel:
                continue
            if info.filename.startswith("/") or any(p in ("", ".", "..") or "\\" in p for p in rel):
                raise StepFailed(f"{archive.name} holds an unsafe path: {info.filename!r}")
            target = dest.joinpath(*rel)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


# ------------------------------------------------------------------------------------------------ the steps

@dataclass
class Setup:
    home: Path
    app: Path
    lane: str
    lane_reason: str = ""
    download: bool = True                     # False: `check`, which verifies only
    say: Callable[[str], None] = _say
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run
    done: dict = field(default_factory=dict)  # step name -> when it was done or verified

    @property
    def runtime(self) -> Path:
        return self.home / "runtime"

    @property
    def downloads(self) -> Path:
        return self.runtime / "state" / "downloads"

    @property
    def node(self) -> Path:
        return self.runtime / "node" / "bin" / "node"

    @property
    def autochart(self) -> Path:
        return self.runtime / "autochart"

    def need(self, what: str) -> None:
        """Refuses to make `what` again when only checking, or when offline."""
        if not self.download:
            raise StepFailed(f"{what} is missing or not as pinned")
        if offline():
            raise StepFailed(f"{what} is missing or not as pinned, and SONGCHARTER_OFFLINE=1 forbids downloading it")


def _node_version(s: Setup) -> str | None:
    try:
        proc = s.run([str(s.node), "--version"], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    return (proc.stdout or "").strip() if proc.returncode == 0 else None


def step_node(s: Setup) -> None:
    """Node 24.19.0 in runtime/node, from nodejs.org's tarball (pinned SHA-256 and size)."""
    if _node_version(s) == f"v{NODE_VERSION}":
        return
    s.need(f"Node {NODE_VERSION}")
    tarball = fetch(NODE_URL, s.downloads / NODE_FILE, NODE_SHA256, NODE_SIZE, say=s.say)
    part = s.runtime / "node.part"
    _rmtree(part)
    part.mkdir(parents=True)
    with tarfile.open(tarball) as t:
        t.extractall(part, filter="data")
    inner = part / NODE_FILE.removesuffix(".tar.gz")
    if not inner.is_dir():
        raise StepFailed(f"{NODE_FILE} does not hold {inner.name}/")
    _rmtree(s.runtime / "node")
    os.replace(inner, s.runtime / "node")
    _rmtree(part)
    tarball.unlink()
    got = _node_version(s)
    if got != f"v{NODE_VERSION}":
        raise StepFailed(f"{s.node} --version printed {got!r}, not v{NODE_VERSION}")


def _copy_files(s: Setup, src: Path, dest: Path, names: tuple[str, ...]) -> None:
    """The named files from `src` into `dest`, each copied only when its bytes differ (`check` copies nothing)."""
    for name in names:
        if not (src / name).is_file():
            raise StepFailed(f"the app has no {src / name}")
        if not (dest / name).is_file() or (dest / name).read_bytes() != (src / name).read_bytes():
            if not s.download:
                raise StepFailed(f"{dest / name} is not the app's")
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / name, dest / name)


def _stamp(s: Setup, folder: Path) -> str:
    return f"{file_sha256(folder / 'package-lock.json')} node-v{NODE_VERSION}\n"


def _npm_ci(s: Setup, folder: Path, ready: Path, what: str) -> None:
    """`npm ci --omit=dev --ignore-scripts --no-audit --no-fund` with our Node's npm in `folder`, unless its stamp says
    it was done for this lock and `ready` (a file or folder npm ci makes) is there. npm_config_loglevel=error (M5-08):
    npm's warnings are not shown (its "npm warn deprecated", and npm-packlist's "npm warn gitignore-fallback No
    .npmignore file found", said for each git dependency npm packs: scan-chart's stream-audio-fingerprint and dsp.js),
    its errors are, and its debug log in the cache still has every line."""
    stamp = folder / STAMP
    if stamp.is_file() and stamp.read_text(encoding="utf-8") == _stamp(s, folder) and ready.exists():
        return
    s.need(what)
    stamp.unlink(missing_ok=True)
    npm = s.runtime / "node" / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js"
    # npm's cache (its tarballs, and its debug logs in _logs) in runtime/state, which uninstall removes either way; the
    # default, ~/.npm, it never would (M4-05). Kept after a failure, for the log npm's last line names and for the
    # tarballs a rerun reuses; deleted once npm ci has succeeded.
    cache = s.runtime / "state" / "npm-cache"
    env = {**os.environ, "PATH": f"{s.node.parent}{os.pathsep}{os.environ.get('PATH', '')}",
           "npm_config_update_notifier": "false", "npm_config_cache": str(cache), "npm_config_loglevel": "error"}
    proc = s.run([str(s.node), str(npm), *NPM_CI], cwd=str(folder), env=env)
    if proc.returncode != 0:
        raise StepFailed(f"npm ci in {folder} exited {proc.returncode} (its output above names its log, kept in {cache})")
    _rmtree(cache)
    if not ready.exists():
        raise StepFailed(f"npm ci in {folder} left no {ready.relative_to(folder)}")
    stamp.write_text(_stamp(s, folder), encoding="utf-8")


def step_scan_chart(s: Setup) -> None:
    """scan-chart in runtime/scan-chart: the app's scan.cjs and package files, then npm ci."""
    folder = s.runtime / "scan-chart"
    _copy_files(s, s.app / "tools" / "scan-chart", folder, SCAN_FILES)
    _npm_ci(s, folder, folder / "node_modules" / "scan-chart" / "package.json", "scan-chart's packages")


def step_autochart(s: Setup) -> None:
    """autochart's engine at the pinned commit in runtime/autochart/src (every file checked against the list), our
    driver and its package files, npm ci, and the CUDA provider on a GPU lane (removed on the cpu lane)."""
    listing = read_list(s.app / ENGINE_LIST)
    src = s.autochart / "src"
    problems = check_tree(src, listing) if src.is_dir() else ["no src/"]
    if problems:
        s.need(f"autochart's engine ({problems[0]})")
        archive = fetch(os.environ.get("SONGCHARTER_AUTOCHART_URL") or AUTOCHART_URL,
                        s.downloads / f"autochart-{AUTOCHART_COMMIT}.zip", None, say=s.say)
        part = s.autochart / "src.part"
        _rmtree(part)
        try:
            extract_zip(archive, part)
        except (zipfile.BadZipFile, EOFError) as e:
            archive.unlink()
            raise StepFailed(f"{archive.name} is not a whole zip ({e}): it is downloaded again next time") from e
        archive.unlink()
        problems = check_tree(part, listing)
        if problems:
            raise StepFailed(f"autochart's archive differs from {ENGINE_LIST}: {len(problems)} files, "
                             f"{'; '.join(problems[:3])}")
        _rmtree(src)
        os.replace(part, src)
    _copy_files(s, s.app / "eval" / "tools" / "autochart", s.autochart, DRIVER_FILES)
    _npm_ci(s, s.autochart, s.autochart / "node_modules" / "onnxruntime-node" / "package.json",
            "autochart's packages (onnxruntime-node)")
    step_provider(s)


def provider_ok(s: Setup) -> bool:
    return all(file_ok(s.autochart / ORT_BIN / name, sha, size) for name, (sha, size) in PROVIDER.items())


def step_provider(s: Setup) -> None:
    """onnxruntime-node's CUDA provider: on a GPU lane installed with its own installer and checked; on the cpu lane
    removed."""
    folder = s.autochart / ORT_BIN
    if s.lane not in GPU_LANES:
        if not s.download:   # `check` changes nothing
            return
        for name in (*PROVIDER, *PROVIDER_OTHER):
            if (folder / name).exists():
                (folder / name).unlink()
                s.say(f"removed {name} (the cpu lane has no CUDA provider)")
        return
    if provider_ok(s):
        return
    s.need("onnxruntime-node's CUDA provider")
    env = {**os.environ, "PATH": f"{s.node.parent}{os.pathsep}{os.environ.get('PATH', '')}"}
    proc = s.run([str(s.node), ORT_INSTALL, "--onnxruntime-node-install=cuda12"], cwd=str(s.autochart), env=env)
    if proc.returncode != 0:
        raise StepFailed(f"onnxruntime-node's installer exited {proc.returncode} (its output is above)")
    for name, (sha, size) in PROVIDER.items():
        if not file_ok(folder / name, sha, size):
            got = file_sha256(folder / name) if (folder / name).is_file() else "no file"
            raise StepFailed(f"the CUDA provider's {name} from NuGet is {got}, not the pinned {sha}")


def model_files(s: Setup) -> list[dict]:
    """The Fretformer 2 component's files in the engine's catalog.json: {"path", "size", "sha256", "source"}."""
    catalog = json.loads((s.autochart / "src" / "engine" / "catalog.json").read_text(encoding="utf-8"))
    comps = catalog["components"]
    comps = comps if isinstance(comps, list) else list(comps.values())
    for comp in comps:
        if comp.get("id") == MODELS_COMPONENT:
            return comp["files"]
    raise StepFailed(f"autochart's catalog.json has no {MODELS_COMPONENT}")


def step_models(s: Setup) -> None:
    """autochart's models in runtime/autochart/models, each file by its size and SHA-256 from the catalog: the remote
    ones from the hub at the pinned revision, the bundled licences copied from the engine (as fetch_models.sh)."""
    for f in model_files(s):
        dest = s.autochart / "models" / f["path"]
        if file_ok(dest, f["sha256"], f["size"]):
            continue
        if f["source"] == "bundled-license":
            src = s.autochart / "src" / "engine" / f["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            if not file_ok(dest, f["sha256"], f["size"]):
                raise StepFailed(f"the bundled {f['path']} is not as the catalog pins it")
            continue
        s.need(f"autochart's model {f['path']}")
        fetch(f"{MODELS_URL}/{f['path']}", dest, f["sha256"], f["size"], say=s.say)


def hf_home() -> Path:
    from .cache import user_cache
    return user_cache() / "models" / "hf"


SEPARATION, SECTIONS = "htdemucs_6s", "harmonix-all"   # the pipeline's models the install fetches from the hub
# allin1's 8 folds are 11.2 MB (DESIGN.md 4.2): fold 0, which model "auto" runs on every device since M6-10, and
# 9.8 MB that only a model asked for reads. Kept: about 0.1 % of a GPU lane's downloads, and the installed app
# reads the hub offline (launch.environment), so a model asked for (harmonix-all, say) is there only if fetched now


@contextlib.contextmanager
def hub_quiet():
    """The hub's logger ("huggingface_hub") at ERROR while the install's downloads run (M5-08). Its warnings are not
    shown: the hub's server sends one in an X-HF-Warning header, "You are sending unauthenticated requests to the HF
    Hub. Please set a HF_TOKEN ...", which huggingface_hub (utils/_http.py, _warn_on_warning_headers) logs as a
    warning, and a dropped connection's "Trying to resume download" before it tries again. Its errors are shown, and
    every failure still raises, so it still ends as StepFailed. Never a token or a login."""
    logger = logging.getLogger("huggingface_hub")
    level = logger.level
    logger.setLevel(max(level, logging.ERROR))
    try:
        yield
    finally:
        logger.setLevel(level)


def hub_labels() -> dict[tuple[str, str], str]:
    """(repository, file) -> the name a person reads in the hub downloads' lines: "htdemucs_6s, file 2 of 2",
    "allin1 fold 3 of 8"."""
    from . import separate
    from .engines import sections
    spec = separate.MODELS[SEPARATION]
    out = {(spec.repo, f): f"{SEPARATION}, file {i} of {len(spec.files)}" for i, f in enumerate(spec.files, 1)}
    folds = sections.ALLIN1_MODELS[SECTIONS]
    out.update({(sections.ALLIN1_REPO, sections.ALLIN1_FOLDS[fold][0]): f"allin1 fold {i} of {len(folds)}"
                for i, fold in enumerate(folds, 1)})
    return out


def said_downloads(get: Callable[..., str], labels: dict[tuple[str, str], str],
                   say: Callable[[str], None] = _say) -> Callable[..., str]:
    """`get` (hf_hub_download with the cache's settings) with our own lines in place of the hub's bars (which
    HF_HUB_DISABLE_PROGRESS_BARS turns off): for each file it downloads, `fetch <label>: <N> MB` first, when the hub
    gives its size, and `fetch <label>: done, <N> MB` once it is there. A file already in the cache says nothing. The
    size comes from the hub's dry run (`dry_run=True`: a metadata request, none for a file the cache has at the pinned
    commit); its errors are the download's own."""
    def download(repo_id: str, filename: str, **kw) -> str:
        label = labels.get((repo_id, filename), filename)
        info = get(repo_id, filename, dry_run=True, **kw)
        if not info.will_download:
            return get(repo_id, filename, **kw)
        if info.file_size is not None:
            say(f"fetch {label}: {info.file_size // MB} MB")
        path = get(repo_id, filename, **kw)
        say(f"fetch {label}: done, {Path(path).stat().st_size // MB} MB")
        return path
    return download


def step_pipeline_models(s: Setup) -> None:
    """The pipeline's models, through its own pinned, hash-checked loaders, into the per-user cache: the separation's
    (htdemucs_6s), allin1's Harmonix folds and ADTOF's weights. The hub's with our lines (said_downloads), no bars
    and no warnings (hub_quiet); ADTOF's through download_part, whose lines it has."""
    os.environ["HF_HOME"] = str(hf_home())   # before the hub's client is imported: it reads them then
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"   # bars as wide as the terminal (M4-08): said_downloads' lines
    local = not s.download or offline()
    from huggingface_hub import hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError

    from . import separate
    from .engines import adtof, sections
    get = said_downloads(functools.partial(hf_hub_download, cache_dir=str(hf_home() / "hub"), local_files_only=local),
                         hub_labels(), s.say)

    def no_download(url: str, dest: Path) -> None:
        raise StepFailed(f"the ADTOF weights are missing ({url} not downloaded: only checking)")

    try:
        with hub_quiet():
            separate.model_paths(SEPARATION, get)
            sections.checkpoint_paths(SECTIONS, get)
        adtof.weights_path(download=no_download if local else None)
    except (OSError, ValueError, RuntimeError, EntryNotFoundError) as e:   # the hub's: mostly OSErrors
        raise StepFailed(f"{type(e).__name__}: {str(e).strip().splitlines()[0] if str(e).strip() else ''}") from e


STEPS: list[tuple[str, Callable[[Setup], None]]] = [
    ("node", step_node), ("scan-chart", step_scan_chart), ("autochart", step_autochart),
    ("autochart's models", step_models), ("the pipeline's models", step_pipeline_models)]


# ------------------------------------------------------------------------------------------------ runtime.json

def runtime_file(home: Path) -> Path:
    return Path(home) / "runtime" / "runtime.json"


def runtime_record(s: Setup) -> dict:
    """runtime.json's content once every step is done."""
    import imageio_ffmpeg

    from . import __version__
    allin1 = s.runtime / "allin1" / "bin" / "python"
    return {"version": 1, "songcharter": __version__, "app": str(s.app), "home": str(s.home), "lane": s.lane,
            "lane_reason": s.lane_reason, "python": sys.executable,
            "allin1_python": str(allin1) if allin1.exists() else None, "node": str(s.node),
            "scan_chart": str(s.runtime / "scan-chart" / "scan.cjs"), "autochart": str(s.autochart),
            "ffmpeg": imageio_ffmpeg.get_ffmpeg_exe(), "hf_home": str(hf_home()), "models_complete": True,
            "steps": dict(s.done)}


def set_allin1(home: Path, keep: bool) -> bool:
    """runtime.json's allin1_python set to allin1's Python (`keep`, when it is there) or null, for the memory rule
    (wslsetup); whether that changed it. No runtime.json: nothing to change."""
    path = runtime_file(home)
    if not path.is_file():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    python = Path(home) / "runtime" / "allin1" / "bin" / "python"
    want = str(python) if keep and python.exists() else None
    if data.get("allin1_python") == want:
        return False
    data["allin1_python"] = want
    _write_json(path, data)
    return True


def doctor(home: Path, say: Callable[[str], None] = _say) -> int:
    """device.report(full=True) with the launcher's environment, into H/doctor.json; 0 when ok, 1 with problems."""
    from . import device, launch
    runtime = json.loads(runtime_file(home).read_text(encoding="utf-8"))
    os.environ.update(launch.environment(runtime))
    report = device.report(full=True)
    _write_json(Path(home) / "doctor.json", report)
    n = len(report["problems"])
    say("doctor: OK" if report["ok"] else f"doctor: {n} problem{'s' * (n != 1)} (in {Path(home) / 'doctor.json'})")
    return 0 if report["ok"] else 1


def setup(s: Setup, steps: list[tuple[str, Callable[[Setup], None]]] | None = None) -> int:
    """Every step, then runtime.json (last), then doctor. Raises StepFailed (with .step set) for a step that fails."""
    if s.lane not in LANES:
        raise StepFailed(f"no torch lane is chosen ({s.lane!r}): it is one of {', '.join(LANES)}")
    for name, fn in steps if steps is not None else STEPS:
        s.say(f"-- {name}")
        try:
            fn(s)
        except (SongcharterError, OSError) as e:
            e.step = name
            raise
        s.done[name] = _now()
    s.runtime.mkdir(parents=True, exist_ok=True)
    _write_json(runtime_file(s.home), runtime_record(s))
    return doctor(s.home, s.say)


def check(home: Path, say: Callable[[str], None] = _say,
          steps: list[tuple[str, Callable[[Setup], None]]] | None = None) -> int:
    """Every step's result verified, nothing downloaded: 0 when all hold, 2 otherwise (each failure said)."""
    path = runtime_file(home)
    if not path.is_file():
        say(f"songcharter: check failed: {path} is missing: run the install line again")
        return 2
    r = json.loads(path.read_text(encoding="utf-8"))
    s = Setup(Path(home), Path(r["app"]), r["lane"], r.get("lane_reason") or "", download=False, say=say)
    failed = 0
    for name, fn in steps if steps is not None else STEPS:
        try:
            fn(s)
            say(f"{name}: ok")
        except (SongcharterError, OSError) as e:
            failed += 1
            say(f"{name}: FAILED: {e}")
    say("check: OK" if not failed else f"check: {failed} step{'s' * (failed != 1)} failed: run the install line again")
    return 0 if not failed else 2


def say_failed(line: str) -> None:
    """The one failure line, last on stderr; also into $SONGCHARTER_FAILURE when install.sh set it, which is how it
    knows the line was said (install.sh's `helper`: any other end of a helper gets its own line)."""
    print(line, file=sys.stderr, flush=True)
    if os.environ.get("SONGCHARTER_FAILURE"):
        try:
            Path(os.environ["SONGCHARTER_FAILURE"]).write_text(line + "\n", encoding="utf-8")
        except OSError:
            pass


def _one_line(e: BaseException) -> str:
    lines = [x.strip() for x in str(e).splitlines() if x.strip()]
    return lines[0] if lines else type(e).__name__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m songcharter.runtime",
                                     description="The install's second half (install.sh runs it).")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("setup", help="Node, scan-chart, autochart and its models, the pipeline's models, runtime.json")
    p.add_argument("--home", type=Path, required=True)
    p.add_argument("--app", type=Path, required=True)
    p.add_argument("--lane", required=True)
    p.add_argument("--lane-reason", default="")
    c = sub.add_parser("check", help="verify what setup made, downloading nothing")
    c.add_argument("--home", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "check":
        return check(args.home.expanduser().absolute())
    s = Setup(args.home.expanduser().absolute(), args.app.expanduser().absolute(), args.lane, args.lane_reason)
    try:
        return setup(s)
    except (SongcharterError, OSError) as e:
        say_failed(f"songcharter: {getattr(e, 'step', 'setup')} failed: {_one_line(e)}. Run the same command again "
                   "to continue.")
        return 2
    except KeyboardInterrupt:
        say_failed("songcharter: setup failed: interrupted. Run the same command again to continue.")
        return 2
    except Exception:  # noqa: BLE001  a bug: its traceback, then the line install.sh ends with
        traceback.print_exc()
        say_failed("songcharter: setup failed: an internal error (a bug: please report it with the traceback above). "
                   "Run the same command again to continue.")
        return 3


if __name__ == "__main__":
    sys.exit(main())
