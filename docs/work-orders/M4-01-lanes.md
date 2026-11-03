# M4-01: the lanes and the locks (Linux, for WSL2)

**Branch:** `m4-01-lanes`, from `main`. **Wave 1**, beside M4-02 and M4-05a. **Agent:** `sc-builder`, then
`sc-reviewer` and `sc-inspector`. May push its branch to run CI.

## Intent

The friend's install is one `uv sync --frozen` against a committed lock, in one of three torch lanes:
- **cu132:** a driver of 580 or newer;
- **cu126:** an older driver;
- **cpu:** no NVIDIA GPU.

allin1 runs in a Python of its own (engines/sections.py), so it gets a locked project too, on the same lanes. On cu132
the lane must also carry everything autochart's CUDA provider needs (M4-00, finding 4), so the guitar runs on the GPU
with no extra environment.

## Scope

Creates or changes:
- `pyproject.toml`: extras and `[tool.uv]` tables. The existing extras keep their meaning, so CLAUDE.md's pip
  command still works.
- `uv.lock` (new);
- `packaging/allin1/pyproject.toml`, `packaging/allin1/uv.lock` (new);
- `packaging/check_wheels.py` and `tests/test_check_wheels.py` (new);
- `packaging/ci/linux.d/10-lanes.sh` (new; the hook folder comes from M4-05a, same wave: a new file, no overlap).

Must not touch: `songcharter/`, other tests, `docs/`, `README.md`.

## Spec

### The root project

Keep `requires-python = ">=3.11,<3.14"` and every existing extra. Add `packaging>=24` to `dev`, then:

```toml
ffmpeg = ["imageio-ffmpeg>=0.6"]
app = ["songcharter[separate,drums,bass,sections,preview,ffmpeg]"]
cpu = ["torch==2.15.0"]
cu126 = ["torch==2.14.1"]
cu132 = ["torch==2.15.0", "nvidia-curand==10.4.4.72; sys_platform == 'linux'"]
```

- **The curand pin:** `libcurand.so.10` for onnxruntime-node's CUDA provider, which needs CUDA 13. The cu132 torch
  wheel brings every other library it needs (M4-00, finding 4).
- **`[tool.uv]`:**
  - `required-version = "==0.13.5"`;
  - `conflicts = [[{ extra = "cpu" }, { extra = "cu126" }, { extra = "cu132" }]]`;
  - `environments = ["sys_platform == 'linux' and platform_machine == 'x86_64'"]`.
- **`[tool.uv.sources]`:** torch per lane extra, from three `explicit = true` indexes named `pytorch-cpu`,
  `pytorch-cu126` and `pytorch-cu132`, with the URLs `https://download.pytorch.org/whl/<lane>`.
- **`uv lock`** with uv 0.13.5 (released 2026-10-22; the installer pins the same version).
- **Versions** (2026-11-03): the newest Linux cp313 torch on each index is 2.15.0 for cpu and cu132, and 2.14.1 for
  cu126.
- The native-Windows environment (win32) was dropped with the route. M4-99 brings it back with a native release.

### allin1's project (`packaging/allin1/pyproject.toml`)

- A virtual project: `[tool.uv] package = false`, `name = "songcharter-allin1"`, `version = "0.1.0"`,
  `requires-python = "==3.13.*"`.
- `dependencies = ["all-in-one-infer==3.1.0", "torchaudio==2.11.1"]`. torchaudio 2.11.1 needs only `torch>=2.11`, so
  it sits beside the lane's torch 2.15. On Linux, that pairing passed the real runner's probe and a fold-0 run [here,
  planning job].
- The same three extras (cu132 without curand: allin1 needs none), conflicts, environments, sources and indexes. The
  same torch pins, so both environments hardlink the same torch files from uv's cache.
- `uv lock` there. It resolved 105 packages in the planning job.

### `packaging/check_wheels.py`

```
usage: python packaging/check_wheels.py [--project DIR ...] [--lanes cpu,cu126,cu132]
```

For each project (default `.` and `packaging/allin1`) and lane:
1. Export: `uv export --frozen --project DIR --extra <lane> [--extra app] --no-hashes --no-emit-project`.
2. Keep the lines whose marker is true for `{"sys_platform": "linux", "platform_machine": "x86_64",
   "python_version": "3.13", ...}`, evaluated with `packaging.markers`.
3. `uv pip compile` that file with `--python-platform x86_64-manylinux_2_39 --python-version 3.13
   --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/<lane>`, and `--only-binary
   <name>` for every package except the allowed pure-Python sdists. glibc 2.39 is CI's Ubuntu 24.04; the friend's
   Ubuntu 26.04 has 2.43, so a wheel that passes here installs there.

**Allowed sdists:** `PURE_SDISTS = {"antlr4-python3-runtime": "4.9.3"}`.
- hydra-core 1.3.8, which all-in-one-infer needs, pins `==4.9.*`, and 4.9.3 is an sdist only.
- It has no `ext_modules`, and `uv build --wheel` gives `py3-none-any` with no compiler [here].
- The check downloads it, compares it with the lock's hash, builds it, and asserts the tag.

**Pass:** the same names with the same public versions (`Version(v).public`; torch in full, local part included).

**Output:** one `ok <project> <lane>: <n> packages, torch <v>` line per project and lane. Exit 0, or 1 with the
failures.

### Hook `packaging/ci/linux.d/10-lanes.sh`

- `uv lock --check` for both projects;
- `uv run --no-project --with packaging python packaging/check_wheels.py`;
- for each lane, `uv sync --frozen --dry-run --extra <lane> --extra app`;
- `uv sync --frozen --dry-run --project packaging/allin1 --extra <lane>`.

## Done means

[dev] In the dev container:

1. `uv --version` is `uv 0.13.5`. `uv lock --check` exits 0, and so does `uv lock --check --project
   packaging/allin1`.
2. `uv run --no-project --with packaging python packaging/check_wheels.py` exits 0 with six `ok` lines:
   - torch `2.15.0+cpu`, `2.14.1+cu126` and `2.15.0+cu132`;
   - the cu132 root line lists `nvidia-curand 10.4.4.72`;
   - the antlr sdist is built.
   - Its test fails a fixture export that holds a second sdist-only package.
3. `UV_PROJECT_ENVIRONMENT=/dev/shm/m4-01/env uv sync --frozen --extra cpu --extra app --extra dev`, then the
   suite with that environment's Python, as CLAUDE.md runs it: the same counts as `main`, plus the new test.
4. `UV_PROJECT_ENVIRONMENT=/dev/shm/m4-01/allin1 uv sync --frozen --project packaging/allin1 --extra cpu`. Then, from
   step 3's environment, `SONGCHARTER_ALLIN1_PYTHON=/dev/shm/m4-01/allin1/bin/python python -m pytest -q
   tests/test_engines_sections.py -k probe` passes its real-probe test.
5. Each lane's `uv sync --frozen --dry-run` exits 0. Report the download size per lane from the lock: expected about
   0.45, 3.9 and 3.2 GB [here, planning job].
6. Every dependency still installs in a fresh venv: `pip install -e ".[dev,separate,drums,bass,sections,preview]"`.

[CI] The `10-lanes` hook passes on `ubuntu-latest` (M4-05a's workflow).

## Depends on

Nothing. M4-05a's hook folder lands in the same wave.
