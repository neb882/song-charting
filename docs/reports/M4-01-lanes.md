# M4-01 (lanes and locks): builder's report

Branch `m4-01-lanes` from `main` 56b5591, worktree
`/tmp/claude-0/-home-user/5307d417-c453-5e74-8f13-b43b2df06ab1/scratchpad/wt/m4-01`, final commit **2579784**. Not
pushed (the coordinator said not to; and M4-05a's workflow is not on this branch, so a push would run nothing).

**Verdict:** built, with the coordinator's torchaudio decision (option B, plus the probe guard) applied. Done-means
1–6 pass. [CI] has not run. The cu126 pairing (torch 2.14.1+cu126 with torchaudio 2.11.1+cpu) is **untested**; a
CPU proxy of it passes (section 3).

## 1. Commits

| commit | what |
|---|---|
| d7f14b2 | `pyproject.toml`: `packaging>=24` in `dev`; new extras `ffmpeg`, `app`, `cpu`, `cu126`, `cu132` (cu132 with `nvidia-curand==10.4.4.72; sys_platform == 'linux'`, cited as [here, 5070 spike]); `[tool.uv]` (`required-version = "==0.13.5"`, conflicts, Linux x86_64 only); torch sourced per lane from three explicit PyTorch indexes. `uv.lock`, 114 packages. |
| d2f7d3f | `packaging/allin1/pyproject.toml` and `uv.lock`, as the order specified. |
| 8e9d6a7 | `packaging/check_wheels.py`, `tests/test_check_wheels.py`. |
| dcd820b | `packaging/ci/linux.d/10-lanes.sh`. |
| 9cabeff | allin1: torchaudio by lane. cpu and cu126 take `2.11.1+cpu` from the cpu index; cu132 takes `2.11.1+cu132` from its own. The reason is in a comment beside the sources: allin1 only imports torchaudio; PyPI's 2.11.1 is a CUDA 13 build; cu126's index has no 2.11.1. torchaudio moves from `dependencies` into the three lane extras, because uv refuses an extra-scoped source for a package the extra does not list. Lock: 105 packages (two torchaudio builds). |
| 327c92d | check_wheels: the named exception `CROSS_INDEX = {"cu126": {"torchaudio": "cpu"}}`. The cpu lane's torchaudio comes from its own index, so it needs none. Details below. |
| 2579784 | 10-lanes: the guard. allin1's cpu lane is synced into `$CI_TMP` and `tests/test_engines_sections.py -k probe` runs with `$CI_PY` (default `python3`) and `SONGCHARTER_ALLIN1_PYTHON` set to it; a skipped probe test fails the hook too. |

**How the exception works:**
- The compile's input is now a generated pyproject.toml of the pins.
- Only the lane's named exception gets a source there, on its own index marked `explicit = true`. So no other
  package can come from that index.
- Every other package still resolves from PyPI and the lane's own index.
- torchaudio is now compared in full, like torch (`FULL_VERSION`), since its local part names the build.
- The ok line marks the exception.

**Beyond the letter of the order:**
- allin1's `required-version`.
- The `FULL_VERSION` tightening.

No file of M4-02's or M4-05a's was touched, nor `songcharter/`, other tests, `docs/` or `README.md`.

## 2. Done means (the final commit unless noted)

uv 0.13.5 is the planner's binary, put first on PATH. The container's own uv is 0.11.32; the tests pass with both. The
dev container's `UV_NATIVE_TLS` deprecation warning is filtered from the outputs.

**1. uv and the locks: pass** (run by the hook): `uv 0.13.5`; `uv lock --check` → `Resolved 114 packages`; with
`--project packaging/allin1` → `Resolved 105 packages`; both exit 0.

**2. check_wheels: pass** (exit 0):
```
ok . cpu: 61 packages, torch 2.15.0+cpu
ok . cu126: 80 packages, torch 2.14.1+cu126
ok . cu132: 81 packages, torch 2.15.0+cu132, nvidia-curand 10.4.4.72
ok packaging/allin1 cpu: 63 packages, torch 2.15.0+cpu, torchaudio 2.11.1+cpu, sdist antlr4-python3-runtime 4.9.3 built (antlr4_python3_runtime-4.9.3-py3-none-any.whl)
ok packaging/allin1 cu126: 82 packages, torch 2.14.1+cu126, torchaudio 2.11.1+cpu (from the cpu index), sdist antlr4-python3-runtime 4.9.3 built (...)
ok packaging/allin1 cu132: 82 packages, torch 2.15.0+cu132, torchaudio 2.11.1+cu132, sdist antlr4-python3-runtime 4.9.3 built (...)
```
- **Real negatives:**
  - `CROSS_INDEX` emptied: allin1 cu126 fails ("there is no version of torchaudio==2.11.1+cpu"), exit 1.
  - `PURE_SDISTS` emptied (earlier): allin1 cpu fails on antlr.
- **Tests:** `tests/test_check_wheels.py` has 24 tests, run through the real uv offline. The cases the order and the
  coordinator asked for:
  - a fixture export with a second sdist-only package fails (`test_a_second_sdist_only_package_fails_the_check`);
  - cu126's torchaudio from the other index passes (`test_cu126s_torchaudio_from_the_cpu_index_passes`);
  - any other package from that index fails (`test_any_other_package_from_another_index_fails`);
  - the exception on another lane fails (`test_the_exception_holds_only_on_its_lane`).
  - In the tests, a flat local index stands for the other index. `--no-index` cannot be used, since it also turns
    off explicit indexes; an empty local default index stands in for PyPI instead.
- **Breaking the code:** 20 breaks, one at a time, and each failed at least one test ("missed: 0"). The 6 new ones:
  - the exception ignored;
  - the exception applied on every lane;
  - its index not explicit;
  - torchaudio not compared in full;
  - full versions compared by public version;
  - the exception not shown in the ok line.

**3. Sync and the suite: pass.** `UV_PROJECT_ENVIRONMENT=/dev/shm/m4-01/env uv sync --frozen --extra cpu --extra app
--extra dev` → `Installed 67 packages` (exit 0). The suite, as CLAUDE.md runs it, with that Python:
- main 56b5591: `509 passed, 3 skipped`;
- dcd820b: `529 passed, 3 skipped`;
- 2579784: `533 passed, 3 skipped in 542.36s` (509 + the 24 new tests; `scratchpad/m4-01-scripts/logs/suite3.txt`).
- The skips are the same three each time: the configured-allin1 probe, and `test_package`'s two (no `node_modules`
  in a fresh checkout).

**4. allin1's environment and the real probe: pass** (it failed at d2f7d3f).
`UV_PROJECT_ENVIRONMENT=/dev/shm/m4-01/allin1 uv sync --frozen --project packaging/allin1 --extra cpu` installs
63 packages, including `torch==2.15.0+cpu` and `torchaudio==2.11.1+cpu`. Then
`SONGCHARTER_ALLIN1_PYTHON=/dev/shm/m4-01/allin1/bin/python <env>/bin/python -m pytest -q tests/test_engines_sections.py
-k probe` → `5 passed, 24 deselected`.

**5. Dry runs: pass**, all six syncs exit 0:
```
app-cpu: Would install 62 packages
allin1-cpu: Would download 7 packages, Would install 63 packages
app-cu126: Would download 20 packages, Would install 81 packages
allin1-cu126: Would download 27 packages, Would install 82 packages
app-cu132: Would download 21 packages, Would install 82 packages
allin1-cu132: Would download 27 packages, Would install 82 packages
```
("Would download" counts only what is not in the local cache.)

Download sizes from the locks: the best cp313 manylinux_2_39 wheel per marker-filtered pin, with the sizes of torch
and torchaudio, which the lock omits, read by HEAD (`scratchpad/m4-01-scripts/sizes.py`):

| lane | app | allin1 | both, each package once | expected |
|---|---|---|---|---|
| cpu | 0.47 GB (61 packages) | 0.38 GB (63) | 0.47 GB (68) | about 0.45 |
| cu126 | 3.90 GB (80) | 3.82 GB (82) | 3.91 GB (87) | about 3.9 |
| cu132 | 3.30 GB (81) | 3.16 GB (82) | 3.31 GB (88) | about 3.2 (curand adds 0.06) |

**6. pip in a fresh venv: pass** (on d7f14b2; root `pyproject.toml` has changed since only in a comment).
- `pip install -e ".[dev,separate,drums,bass,sections,preview]"` installed; `pip check` was clean; everything
  imported.
- torch went in first from the cpu index, as M4-05a's CI does.
- `pip install --dry-run -e ".[app,cpu]"` works.

**The hook (2579784), locally, as CI runs it:** exit 0 in 39 s. It printed the six ok lines and the six dry-run
lines above, then:
```
allin1-cpu: Installed 63 packages in 217ms
.....                                                                    [100%]
5 passed, 24 deselected in 19.60s
```

**The guard catches the old failure.** In a scratch checkout of 2579784, with `packaging/allin1` put back to
d2f7d3f (PyPI's torchaudio):
- **The whole hook exits 1**, at the wheels check. With torchaudio compared in full:
  ```
  FAIL packaging/allin1 cpu: ... torchaudio: 2.11.1 in the lock, 2.11.1+cpu in the compile
  FAIL packaging/allin1 cu126: ... torchaudio: 2.11.1 in the lock, 2.11.1+cpu in the compile
  FAIL packaging/allin1 cu132: ... torchaudio: 2.11.1 in the lock, 2.11.1+cu132 in the compile
  ```
- **The guard on its own exits 1** (the same lines, run alone):
  ```
  ImportError: no All-In-One package imports here (allin1_infer: OSError: Could not load this library: .../torchaudio/lib/_torchaudio.so; ...)
  1 failed, 4 passed, 24 deselected
  ```

**[CI]: not run.** M4-05a's `ci.yml` and `run-hooks.sh` are not on this branch. The hook needs uv 0.13.5 on PATH,
Python 3.13, `$CI_PY` with songcharter and pytest, and the network; it adds about 0.4 GB of download and about 20 s.

## 3. The cu126 pairing: untested

- **Not run:** torch 2.14.1+cu126 with torchaudio 2.11.1+cpu.
  - Its environment is a 3.8 GB download, about 5–6 GB unpacked [inference]. That is over the 2 GB budget on /.
  - In `/dev/shm` it would have taken most of the 4–6 GB of RAM available while M4-02's and M4-05a's suites and a
    golden run were going, with no swap.
- **A proxy that passes** [here]: torch **2.14.1+cpu**, torchaudio 2.11.1+cpu and the rest of allin1's cpu lane in a
  scratch environment.
  - `import torch, torchaudio, allin1_infer` gives `2.14.1+cpu 2.11.1+cpu`.
  - The probe tests: `5 passed, 24 deselected`.
  - This covers the ABI question: torchaudio's three libraries link only `libtorch.so`, `libc10.so` and
    `libtorch_cpu.so`, which a cu126 build of 2.14.1 has too.
  - It does not cover loading beside the CUDA 12 runtime. M4-08, or any machine with room, should run the probe once
    in a cu126 allin1 environment.

## 4. For the director at the merge

- **Docs:** per the plan, this order edited no docs. To fold in:
  - PROGRESS: M4-01 built; torchaudio by lane (option B); the lock counts 114 and 105; the sizes above; the cu126
    pairing untested (proxy passed).
  - DESIGN, wherever the lanes are described.
  - CLAUDE.md's commands, if the uv route should sit beside pip.
- **M4-03:** the install's `uv sync --frozen ... --extra app --extra <lane>` and allin1's sync plan cleanly. allin1
  without a lane extra now has no torchaudio (no install does that).

## 5. Disk and cleanup

- **On /:**
  - The first round's 1.6 GB in the shared `/root/.cache/uv` was removed (back to 3,400 MB).
  - Every later uv run used a private cache on `/dev/shm`.
  - The wheels check's metadata and its antlr build use the shared cache (a few MB).
- **On /dev/shm:** everything removed (`/dev/shm/m4-01`: the environments, the private cache, the scratch checkouts, the proxy environment; my `pt_m4_01*` folders). The suite logs and the final hook's outputs are in `scratchpad/m4-01-scripts/logs/`.
- **Kept on purpose:**
  - the worktree;
  - `scratchpad/m4-01-scripts/`: `mutate.py`, `sizes.py` and `logs/`;
  - `scratchpad/briefs/m4-01.torchaudio-option-a.diff`, now obsolete.

## 6. Review round: F1 fixed (commit c0a145c), F2 left alone

**F1:** the check certified the indexes, not the lock.
- **The fix:** once the compile matches, `lock_wheel_problems()` reads `uv.lock` itself. Each kept pin but the
  allowed sdists must have a recorded wheel whose tags are in `LOCK_TAGS`: CPython 3.13 (cp313, abi3 or none),
  Linux x86_64, manylinux no newer than glibc 2.35 (`LOCK_GLIBC`, Ubuntu 22.04's).
- **A pin that fails it:** one missing from the lock, an sdist-only entry, or wheels that do not fit.
- **Both real locks pass**, with the same six ok lines.
- **Tests:** the fixture's lock now records every fixture file. New tests:
  - `test_a_pin_the_lock_has_only_as_an_sdist_fails_though_an_index_has_a_wheel`: the review's fixture. The lock
    holds only `xpkg-1.0.tar.gz`, and the lane's index holds a cp313 manylinux_2_17 wheel.
  - a pin missing from the lock;
  - a locked wheel that needs glibc 2.39;
  - 12 cases of which wheel tags fit.
- **Breaking the code:** 25 breaks, one at a time, and each failed at least one test ("missed: 0"). The 5 new ones:
  - the lock not checked;
  - the glibc bound at 2.39;
  - a free-threaded ABI allowed;
  - an sdist-only entry passing;
  - a missing entry passing.
- 39 tests pass with uv 0.13.5 and 0.11.32.
- **Suite (c0a145c):** `548 passed, 3 skipped in 522.34s (0:08:42)` (509 + the 39 tests of test_check_wheels.py; logs/suite4.txt).

**F2** (deferred by the coordinator): with no lane extra, `uv sync` installs PyPI's CUDA torch. No change.
