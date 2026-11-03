"""Checks that every torch lane of the locked projects installs from wheels alone on the friend's Linux (WSL2).

usage: python packaging/check_wheels.py [--project DIR ...] [--lanes cpu,cu126,cu132]

Run it with uv 0.13.5 (the projects' required version) as `uv run --no-project --with packaging python
packaging/check_wheels.py`. For each project (default `.` and `packaging/allin1`) and lane:

1. `uv export --frozen` gives the lock's pins for that lane, with `app` where the project has that extra;
2. the pins whose marker holds on CPython 3.13, Linux x86_64 are kept (`packaging.markers`);
3. `uv pip compile` resolves them again for x86_64-manylinux_2_39 (glibc 2.39, CI's Ubuntu 24.04; the friend's
   Ubuntu 26.04 has 2.43, so what passes here installs there), from PyPI and the lane's PyTorch index, with
   `--only-binary` for every package but the allowed pure-Python sdists (PURE_SDISTS). The one exception to that
   index rule is named in CROSS_INDEX: that package alone may come from another lane's PyTorch index.

A pair passes when the compile gives the same names at the same public versions (torch and torchaudio in full: their
local part, `+cu132`, names the build); when the lock itself records, for each pin but the allowed sdists, a wheel
that installs on CPython 3.13, Linux x86_64 with glibc 2.35 (Ubuntu 22.04's, the oldest the install meets), since
`uv sync --frozen` installs the lock's files, not the compile's; and when every allowed sdist among its pins downloads
from the lock's URL with the lock's hash and builds (`uv build --wheel`) to a py3-none-any wheel. Prints one
`ok <project> <lane>: <n> packages, torch <v>` line per pair, with the lane's other pins (and the index of a
cross-index one) and the sdists built; exit 0, or 1 with the failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (".", "packaging/allin1")
LANES = ("cpu", "cu126", "cu132")
PYTORCH = "https://download.pytorch.org/whl/{lane}"
PLATFORM = "x86_64-manylinux_2_39"
PYTHON = "3.13"
BUILD_PYTHON = PYTHON   # the Python the allowed sdists are built with (uv finds or fetches a 3.13)
# the sdists allowed in a lane, at these versions only: each must build to py3-none-any with no compiler.
# antlr4-python3-runtime: hydra-core 1.3.8 (all-in-one-infer needs it) pins ==4.9.*, and 4.9.3 is an sdist only.
PURE_SDISTS = {"antlr4-python3-runtime": "4.9.3"}
# the one exception to the index rule (PyPI and the lane's own PyTorch index): lane -> {package: the lane whose index
# it comes from}. allin1's torchaudio on cu126 comes from the cpu index, which also serves the cpu lane as its own:
# PyPI's 2.11.1 is a CUDA 13 build and cu126's index has no 2.11.1 (packaging/allin1/pyproject.toml).
CROSS_INDEX = {"cu126": {"torchaudio": "cpu"}}
# the packages compared with their local part, which names the build (`+cpu`, `+cu132`)
FULL_VERSION = ("torch", "torchaudio")
# the tags a wheel recorded in the lock may carry: CPython 3.13 (its own ABI, abi3 or none), Linux x86_64 with
# manylinux no newer than glibc 2.35, Ubuntu 22.04's, the oldest Ubuntu the install meets (CI also runs it there)
LOCK_GLIBC = (2, 35)
_LOCK_PLATFORMS = [f"manylinux_{LOCK_GLIBC[0]}_{minor}_x86_64" for minor in range(LOCK_GLIBC[1], 4, -1)] + [
    "manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"]
LOCK_TAGS = frozenset([*cpython_tags((3, 13), abis=["cp313"], platforms=_LOCK_PLATFORMS),
                       *compatible_tags((3, 13), "cp313", _LOCK_PLATFORMS)])
# where the pins are evaluated: CPython 3.13 on Linux x86_64. python_full_version is 3.13.0, as for `uv pip compile
# --python-version 3.13`, so the two steps agree.
MARKER_ENV = {
    "implementation_name": "cpython", "implementation_version": "3.13.0", "os_name": "posix",
    "platform_machine": "x86_64", "platform_python_implementation": "CPython", "platform_release": "",
    "platform_system": "Linux", "platform_version": "", "python_full_version": "3.13.0", "python_version": "3.13",
    "sys_platform": "linux", "extra": "",
}


class CheckError(Exception):
    """One project and lane failed; the message says why."""


def find_uv() -> str:
    """uv: the one running this script under `uv run` ($UV), else the one on PATH."""
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise SystemExit("check_wheels: uv not found (run it with `uv run`, or put uv 0.13.5 on PATH)")
    return uv


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def tail(proc: subprocess.CompletedProcess, lines: int = 15) -> str:
    text = (proc.stderr or proc.stdout or "").strip().splitlines()
    return "\n".join("    " + line for line in text[-lines:])


def extras(project: Path) -> dict[str, list[str]]:
    data = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))
    return data.get("project", {}).get("optional-dependencies", {})


def export_command(uv: str, project: Path, lane: str) -> list[str]:
    app = ["--extra", "app"] if "app" in extras(project) else []
    return [uv, "export", "--frozen", "--project", str(project), "--extra", lane, *app, "--no-hashes",
            "--no-emit-project", "--format", "requirements-txt"]


def pins(export: str) -> dict[str, str]:
    """The `name==version` pins of a requirements export whose markers hold on CPython 3.13, Linux x86_64."""
    out = {}
    for line in export.splitlines():
        if not line.strip() or line.startswith(("#", " ", "\t")):
            continue  # blank, a comment, or a `# via` annotation
        try:
            req = Requirement(line)
        except InvalidRequirement as e:
            raise CheckError(f"not a requirement: {line}") from e
        if req.marker is not None and not req.marker.evaluate(MARKER_ENV):
            continue
        specs = list(req.specifier)
        if req.url or len(specs) != 1 or specs[0].operator != "==":
            raise CheckError(f"not a pinned registry package: {line}")
        name = canonicalize_name(req.name)
        if name in out and out[name] != specs[0].version:
            raise CheckError(f"two pins of {name} on Linux, CPython 3.13: {out[name]} and {specs[0].version}")
        out[name] = specs[0].version
    return out


def pytorch_index(lane: str) -> dict:
    """The `[[tool.uv.index]]` fields of a lane's PyTorch index, for a cross-index exception's source."""
    return {"url": PYTORCH.format(lane=lane)}


def compile_input(pinned: dict[str, str], lane: str, folder: Path) -> Path:
    """The compile's input, a pyproject.toml whose dependencies are the pins. Each of the lane's cross-index
    exceptions among them (CROSS_INDEX) gets a source on that index, marked explicit, so no other package can come
    from it."""
    cross = {name: other for name, other in CROSS_INDEX.get(lane, {}).items() if name in pinned}
    lines = ["[project]", 'name = "check-wheels-pins"', 'version = "0"', "dependencies = ["]
    lines += [f"    {json.dumps(f'{name}=={version}')}," for name, version in sorted(pinned.items())]
    lines.append("]")
    if cross:
        lines += ["", "[tool.uv.sources]"]
        lines += [f'{name} = {{ index = "cross-{other}" }}' for name, other in sorted(cross.items())]
        for other in sorted(set(cross.values())):
            table = {"name": f"cross-{other}", **pytorch_index(other), "explicit": True}
            lines += ["", "[[tool.uv.index]]", *(f"{k} = {json.dumps(v)}" for k, v in table.items())]
    path = folder / "pyproject.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def compile_command(uv: str, pinned: dict[str, str], requirements: Path, lane: str,
                    index: list[str] | None = None) -> list[str]:
    """`uv pip compile` of the pins for the friend's platform, wheels only but for the allowed sdists. index: where
    to look (default PyPI plus the lane's PyTorch index)."""
    index = index if index is not None else ["--extra-index-url", PYTORCH.format(lane=lane)]
    binary = [arg for name in sorted(pinned) if PURE_SDISTS.get(name) != pinned[name]
              for arg in ("--only-binary", name)]
    return [uv, "pip", "compile", str(requirements), "--python-platform", PLATFORM, "--python-version", PYTHON,
            "--index-strategy", "unsafe-best-match", *index, *binary, "--no-header", "--no-annotate"]


def compare(want: dict[str, str], got: dict[str, str]) -> list[str]:
    """The differences between the lock's pins and the compile's: names, public versions, and FULL_VERSION's
    packages in full."""
    problems = []
    for name in sorted(set(want) | set(got)):
        if name not in got:
            problems.append(f"{name} {want[name]}: in the lock, not in the compile")
        elif name not in want:
            problems.append(f"{name} {got[name]}: in the compile, not in the lock")
        else:
            a, b = Version(want[name]), Version(got[name])
            if (a != b) if name in FULL_VERSION else (Version(a.public) != Version(b.public)):
                problems.append(f"{name}: {want[name]} in the lock, {got[name]} in the compile")
    return problems


def wheel_fits(filename: str) -> bool:
    """Whether a wheel installs on CPython 3.13, Linux x86_64, glibc 2.35 (LOCK_TAGS)."""
    return any(tag in LOCK_TAGS for tag in parse_wheel_filename(filename)[3])


def lock_wheel_problems(project: Path, pinned: dict[str, str]) -> list[str]:
    """The pins, the allowed sdists aside, for which the lock itself records no wheel that fits (wheel_fits): what
    `uv sync --frozen` would have to build or could not install, whatever an index offers at that version."""
    lock = tomllib.loads((project / "uv.lock").read_text(encoding="utf-8"))
    entries: dict[tuple, list[dict]] = {}
    for package in lock.get("package", []):
        entries.setdefault((canonicalize_name(package["name"]), Version(package["version"])), []).append(package)
    problems = []
    for name, version in sorted(pinned.items()):
        if PURE_SDISTS.get(name) == version:
            continue
        found = entries.get((name, Version(version)))
        if not found:
            problems.append(f"{name} {version}: not in {project / 'uv.lock'}")
        for package in found or []:
            files = [urllib.parse.unquote((w.get("url") or w.get("path") or w.get("filename", "")).rsplit("/", 1)[-1])
                     for w in package.get("wheels", [])]
            if not any(wheel_fits(f) for f in files if f.endswith(".whl")):
                what = f"{len(files)} wheels, none for it" if files else "an sdist only"
                problems.append(f"{name} {version}: the lock records no wheel for CPython 3.13, Linux x86_64, glibc "
                                f"{LOCK_GLIBC[0]}.{LOCK_GLIBC[1]} ({what})")
    return problems


def locked_sdist(project: Path, name: str, version: str) -> dict:
    """The lock's `sdist = {url, hash, ...}` entry for a package."""
    lock = tomllib.loads((project / "uv.lock").read_text(encoding="utf-8"))
    for package in lock.get("package", []):
        if canonicalize_name(package["name"]) == name and Version(package["version"]) == Version(version):
            if "sdist" in package and "url" in package["sdist"]:
                return package["sdist"]
    raise CheckError(f"{name} {version}: no sdist in {project / 'uv.lock'}")


def build_sdist(uv: str, entry: dict, name: str, version: str, work: Path) -> str:
    """Download an allowed sdist from the lock's URL (entry: its `sdist` table), check it against the lock's hash,
    build it with `uv build --wheel`, and check the wheel is py3-none-any. Returns the wheel's file name."""
    algorithm, _, digest = entry.get("hash", "").partition(":")
    if algorithm != "sha256" or not digest:
        raise CheckError(f"{name} {version}: the lock gives no sha256 for its sdist")
    try:
        with urllib.request.urlopen(entry["url"], timeout=120) as response:
            data = response.read()
    except OSError as e:
        raise CheckError(f"{name} {version}: its sdist did not download from {entry['url']} ({e})") from e
    if hashlib.sha256(data).hexdigest() != digest:
        raise CheckError(f"{name} {version}: the sdist at {entry['url']} does not match the lock's hash")
    folder = Path(tempfile.mkdtemp(prefix=f"sdist-{name}-", dir=work))
    out = folder / "dist"
    out.mkdir(parents=True)
    archive = folder / entry["url"].rsplit("/", 1)[-1]
    archive.write_bytes(data)
    proc = run([uv, "build", "--wheel", str(archive), "--out-dir", str(out), "--python", BUILD_PYTHON],
               cwd=folder)
    wheels = sorted(p.name for p in out.glob("*.whl"))
    if proc.returncode != 0 or len(wheels) != 1:
        raise CheckError(f"{name} {version}: its sdist did not build one wheel (exit {proc.returncode})\n"
                         + tail(proc))
    tags = {str(tag) for tag in parse_wheel_filename(wheels[0])[3]}
    if tags != {"py3-none-any"}:
        raise CheckError(f"{name} {version}: its sdist built {wheels[0]}, not a py3-none-any wheel")
    return wheels[0]


def check(uv: str, project: Path, lane: str, work: Path, label: str, export: str | None = None,
          index: list[str] | None = None, built: dict | None = None) -> str:
    """One project and lane: the `ok` line, or CheckError. export: the requirements export (default `uv export`);
    index: as compile_command's; built: the sdists already built (by the lock's URL and hash), shared across
    calls."""
    built = {} if built is None else built
    if export is None:
        proc = run(export_command(uv, project, lane))
        if proc.returncode != 0:
            raise CheckError(f"uv export failed (exit {proc.returncode})\n{tail(proc)}")
        export = proc.stdout
    want = pins(export)
    folder = Path(tempfile.mkdtemp(prefix=f"{lane}-", dir=work))
    proc = run(compile_command(uv, want, compile_input(want, lane, folder), lane, index), cwd=folder)
    if proc.returncode != 0:
        raise CheckError(f"no wheels-only resolution (exit {proc.returncode})\n{tail(proc)}")
    got = pins(proc.stdout)
    problems = compare(want, got)
    if problems:
        raise CheckError("the compile differs from the lock:\n" + "\n".join("    " + p for p in problems))
    problems = lock_wheel_problems(project, want)
    if problems:
        raise CheckError("the lock's own files do not install from wheels:\n" + "\n".join("    " + p for p in problems))
    sdists = []
    for name in sorted(n for n in want if PURE_SDISTS.get(n) == want[n]):
        entry = locked_sdist(project, name, want[name])
        key = (entry["url"], entry.get("hash"))
        if key not in built:
            built[key] = build_sdist(uv, entry, name, want[name], work)
        sdists.append(f"sdist {name} {want[name]} built ({built[key]})")
    lane_pins = [canonicalize_name(Requirement(r).name) for r in extras(project).get(lane, [])]
    shown = ["torch"] + [n for n in lane_pins if n != "torch" and n in got]
    cross = CROSS_INDEX.get(lane, {})
    listed = ", ".join(f"{n} {got.get(n, 'none')}" + (f" (from the {cross[n]} index)" if n in cross else "")
                       for n in shown)
    return ", ".join([f"ok {label} {lane}: {len(got)} packages", listed, *sdists])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--project", action="append", metavar="DIR",
                        help="a uv project with a uv.lock (repeatable; default . and packaging/allin1)")
    parser.add_argument("--lanes", default=",".join(LANES), help="comma-separated (default %(default)s)")
    args = parser.parse_args(argv)
    lanes = [lane for lane in args.lanes.split(",") if lane]
    if not lanes or set(lanes) - set(LANES):
        parser.error(f"--lanes: choose from {','.join(LANES)}")
    uv = find_uv()
    # the default projects are this repository's; a DIR given is taken from the current folder
    projects = [(d, Path(d).resolve()) for d in args.project] if args.project else [(d, ROOT / d) for d in PROJECTS]
    failures, built = [], {}
    with tempfile.TemporaryDirectory(prefix="check-wheels-") as tmp:
        for label, project in projects:
            for lane in lanes:
                try:
                    print(check(uv, project, lane, Path(tmp), label, built=built), flush=True)
                except CheckError as e:
                    failures.append(f"FAIL {label} {lane}: {e}")
                    print(failures[-1], flush=True)
    if failures:
        print(f"{len(failures)} of {len(lanes) * len(projects)} failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
