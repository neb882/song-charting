# M4-01: the lanes and the locks

**Branch:** `m4-01-lanes`, from `main`. **Wave 1**, beside M4-02. **Agent:** `sc-builder`, then `sc-reviewer` and
`sc-inspector`.

## Intent

The Windows install is one `uv sync --frozen` against a committed lock, in one of three torch lanes (DESIGN 4.3):
`cu132`, `cu126` and `cpu`. allin1 runs in a Python of its own (engines/sections.py), so it gets a locked project of
its own, on the same lanes. A check proves, on Linux, that every package each lane needs on Windows has a wheel for
CPython 3.13 win_amd64, or is one of the named pure-Python sdists, so nothing needs a compiler on the friend's PC.

## Scope

Creates or changes:
- `pyproject.toml`: new extras and `[tool.uv]` tables (below). Existing extras keep their meaning, so
  `pip install -e ".[dev,separate,drums,bass,sections,preview]"` still works.
- `uv.lock` (new).
- `packaging/allin1/pyproject.toml`, `packaging/allin1/uv.lock` (new).
- `packaging/check_wheels.py` (new), with `tests/test_check_wheels.py` for its marker filter.

Must not touch:
- any module under `songcharter/` or `tests/` other than the new test;
- `docs/` and `README.md` (the director folds the doc changes in).

## Spec

### The root project (`pyproject.toml`)

- Keep `requires-python = ">=3.11,<3.14"` and every existing extra.
- Add `packaging>=24` to the `dev` extra (for `check_wheels.py`).
- Add these extras:
  ```toml
  ffmpeg = ["imageio-ffmpeg>=0.6"]                 # ffmpeg for Windows installs (audio.ffmpeg_exe's last resort)
  app = ["songcharter[separate,drums,bass,sections,preview,ffmpeg]"]   # everything `songcharter chart` and the UI use
  cpu = ["torch==2.15.0"]
  cu126 = ["torch==2.14.1"]
  cu132 = ["torch==2.15.0"]
  ```
- `[tool.uv]`:
  ```toml
  required-version = "==0.13.5"
  conflicts = [[{ extra = "cpu" }, { extra = "cu126" }, { extra = "cu132" }]]
  environments = ["sys_platform == 'win32'", "sys_platform == 'linux' and platform_machine == 'x86_64'"]
  required-environments = ["sys_platform == 'win32' and platform_machine == 'AMD64'",
                           "sys_platform == 'linux' and platform_machine == 'x86_64'"]
  ```
- `[tool.uv.sources]`: `torch = [{ index = "pytorch-cpu", extra = "cpu" }, { index = "pytorch-cu126", extra =
  "cu126" }, { index = "pytorch-cu132", extra = "cu132" }]`.
- Three `[[tool.uv.index]]` tables, each with `explicit = true`, named `pytorch-cpu`, `pytorch-cu126` and
  `pytorch-cu132`, with the URLs `https://download.pytorch.org/whl/<lane>`.
- Then run `uv lock` (uv 0.13.5) and commit `uv.lock`.
- Why these versions:
  - DESIGN 4.3's table, checked on 2026-11-03: the newest win_amd64 cp313 torch per index is 2.15.0 on cpu and
    cu132, and 2.14.1 on cu126.
  - uv 0.13.5 was released on 2026-10-22. The installer ships the same version (M4-07), and CI installs it (M4-05).

### allin1's project (`packaging/allin1/pyproject.toml`)

- A virtual project: `[tool.uv] package = false`, so it installs only its dependencies.
- `name = "songcharter-allin1"`, `version = "0.1.0"`, `requires-python = "==3.13.*"`.
- `dependencies = ["all-in-one-infer==3.1.0", "torchaudio==2.11.1"]`.
  - torchaudio is needed because all-in-one-infer 3.1.0 imports it at the top level (`allin1_infer/stems.py`)
    without declaring it (DESIGN 4.3).
  - 2.11.1 because it is the PyPI build that needs only `torch>=2.11`, so it sits beside the lane's own torch: on
    Linux, torch 2.15.0+cpu with it passed the real runner's probe and a fold-0 run [here, planning job].
- The same `cpu`, `cu126` and `cu132` extras, `conflicts`, `environments`, `required-environments`, `sources` and
  indexes as the root. Same torch pins, so both environments link the same torch files from uv's cache.
- `[tool.uv] required-version = "==0.13.5"`; run `uv lock` in that folder and commit its `uv.lock`.
- **Fallback, only if M4-05 shows torchaudio 2.11.1 failing on Windows:**
  - pin `torch==2.11.0` in all three extras of this project;
  - pin `torchaudio==2.11.0` per extra, from the lane's index (cpu, cu126; and cu130 in place of cu132, since the
    cu132 index has no torchaudio);
  - relock.

  Not now.

### `packaging/check_wheels.py`

```
usage: python packaging/check_wheels.py [--project DIR ...] [--lanes cpu,cu126,cu132]
```

- For each project (default: `.` and `packaging/allin1`) and each lane:
  1. `uv export --frozen --project DIR --extra <lane> [--extra app, root only] --no-hashes --no-emit-project
     --format requirements-txt`.
  2. Keep the requirements whose marker is true for Windows. Evaluate with `packaging.markers` against
     `{"sys_platform": "win32", "platform_machine": "AMD64", "platform_system": "Windows", "os_name": "nt",
     "python_version": "3.13", "python_full_version": "3.13.17", "implementation_name": "cpython",
     "platform_python_implementation": "CPython"}`. Drop the marker text.
  3. `uv pip compile <that file> --python-platform x86_64-pc-windows-msvc --python-version 3.13 --index-strategy
     unsafe-best-match --extra-index-url https://download.pytorch.org/whl/<lane>`, into a temporary file, with
     `--only-binary <name>` for every package in the file except the allowed pure-Python sdists below. Not
     `--only-binary :all:`.
- **Allowed sdists:** `PURE_SDISTS = {"antlr4-python3-runtime": "4.9.3"}`.
  - all-in-one-infer requires hydra-core 1.3.8, which pins `antlr4-python3-runtime==4.9.*`, and 4.9.3 is on PyPI
    as an sdist only.
  - It is pure Python (its `setup.py` has no `ext_modules`), and `uv build --wheel` turns it into
    `antlr4_python3_runtime-4.9.3-py3-none-any.whl` with no compiler [here, planning job]. So uv builds it on the
    friend's PC at the bootstrap with setuptools alone.
  - The check proves it: for each allowed sdist, download it from PyPI, check it against the lock's SHA-256, build
    it with `uv build --wheel`, and assert the wheel's tag is `py3-none-any`.
  - Any other sdist is a failure.
- **Pass:** the compile succeeds, and it pins the same package names as the export, with the same public versions
  (`packaging.version.Version(v).public`). torch must match in full, local version included.
  - With the extra index, the compile may take `torchaudio 2.11.1+cpu` (or `+cu132`) where the lock has PyPI's
    `2.11.1` [here]: both install the same release.
  - Expected counts on 2026-11-03: 62 Windows packages per lane for the root, 64 for allin1's project [here].
- Print one line per project and lane: `ok <project> <lane>: <n> packages, torch <version>`, or `FAIL ...` with uv's
  last lines.
- Exit 0 when all pass, 1 otherwise.
- Why filter the markers yourself: uv's `windows` target did not match real Windows' `platform_machine == 'AMD64'`
  markers when tried, and resolved nothing [here, planning job].

### Linux development

Unchanged: the pip command in CLAUDE.md keeps working. For uv users, `uv sync --extra cpu --extra app --extra dev`
gives the same environment. The director adds that line to CLAUDE.md and README at the merge.

## Done means

All of these run in the dev container [dev] (and again in M4-05's Linux job [CI-linux]):

1. `uv --version` prints `uv 0.13.5`, then `uv lock --check` exits 0, and so does `uv lock --check --project
   packaging/allin1`.
2. `python packaging/check_wheels.py` exits 0 and prints six `ok` lines.
   - Expected torch versions per lane: `2.15.0+cpu`, `2.14.1+cu126`, `2.15.0+cu132`, in both projects.
   - Plus one line saying `antlr4-python3-runtime 4.9.3` built as `py3-none-any`.
   - A test with a stand-in export that holds a second sdist-only package (a fixture file, no network) fails.
3. `UV_PROJECT_ENVIRONMENT=/dev/shm/m4-01/env uv sync --frozen --extra cpu --extra app --extra dev` then, with that
   env's Python, the full suite as CLAUDE.md runs it:
   `SONGCHARTER_SCAN_CHART=$PWD/tools/scan-chart/scan.cjs python -m pytest -q -p no:cacheprovider --basetemp=/dev/shm/pt`
   passes with the same counts as `main`, apart from the new test.
4. `UV_PROJECT_ENVIRONMENT=/dev/shm/m4-01/allin1 uv sync --frozen --project packaging/allin1 --extra cpu`, then
   `SONGCHARTER_ALLIN1_PYTHON=/dev/shm/m4-01/allin1/bin/python python -m pytest -q -p no:cacheprovider
   tests/test_engines_sections.py -k probe` (in the env of step 3) passes its real-probe test, which skips without
   that variable.
5. For each lane, `uv sync --frozen --dry-run --extra <lane> --extra app` exits 0.
6. `pip install -e ".[dev,separate,drums,bass,sections,preview]"` in a fresh venv still succeeds (the pip route is
   unchanged).
7. Report: both `uv.lock` sizes and package counts, the six `ok` lines, and the suite's counts.

[CI-windows] M4-05 runs step 5 on `windows-latest` too, and the real `uv sync` of the cpu lane.

## Depends on

Nothing.
