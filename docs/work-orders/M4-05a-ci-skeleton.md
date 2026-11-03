# M4-05a: the CI skeleton

**Branch:** `m4-05a-ci-skeleton`, from `main`. **Wave 1**, beside M4-01 and M4-02. **Agent:** `sc-builder`, then
`sc-reviewer`. **This order pushes** its branch (`git push origin m4-05a-ci-skeleton`); its brief must allow it.
Pushing a workflow file from a session works [here, planning job].

## Intent

Every later order needs somewhere to run its checks the day it lands, not in wave 3. This order makes the workflow
and its hook folders, and nothing else: the suite on Linux, and a Windows job for the few files songcharter writes on
the Windows side (the Start-menu shortcut). Each later order adds hook files, never `ci.yml`.

## Scope

Creates:
- `.github/workflows/ci.yml`;
- `packaging/ci/run-hooks.sh`, `packaging/ci/run-hooks.ps1`;
- `packaging/ci/linux.d/README.txt`, `packaging/ci/windows.d/README.txt`: the hook contract, below;
- `packaging/ci/make_clip.py`: the planning job's generator (in the director's scratchpad,
  `briefs/m4-assets/make_clip.py`; the brief gives the full path), with a module docstring;
- `packaging/ci/check_gate.py`, `packaging/ci/check_no_audio.py`.

Must not touch: `songcharter/`, `tests/`, `pyproject.toml`, `docs/`.

## Spec

### `ci.yml`

- **Triggers:** `push` to `main` and `m4-*`, `pull_request`, `workflow_dispatch`.
- `permissions: contents: read`; `concurrency: ci-${{ github.ref }}` with `cancel-in-progress: true`.
- **Actions:** `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`, `actions/cache@v4`,
  `actions/upload-artifact@v4`.

#### Job `linux` (`ubuntu-latest`, 120 min)

1. Python 3.13 and Node 24.19.0.
2. Install.
   - Until `uv.lock` exists:
     - `pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu`, so pip never pulls the 3 GB
       CUDA build from PyPI;
     - then `pip install -e ".[dev,separate,drums,bass,sections,preview]"`.
   - Once `uv.lock` exists (M4-01): `pip install uv==0.13.5`, then `uv sync --frozen --extra cpu --extra app --extra
     dev`. The step chooses by whether `uv.lock` is there.
3. `(cd tools/scan-chart && npm ci)`. Then the suite as CLAUDE.md runs it, with `--basetemp=$RUNNER_TEMP/pt`:
   0 failures.
4. `bash packaging/ci/run-hooks.sh linux`.
5. Artifacts (`if: always()`): `$RUNNER_TEMP/ci-artifacts/`, after `check_no_audio.py` on it.

#### Job `windows` (`windows-latest`, 30 min, `shell: pwsh`)

1. Python 3.13.
2. `pip install pytest LnkParse3`.
3. `./packaging/ci/run-hooks.ps1 windows`. With no hooks yet, it prints "no Windows hooks" and passes.

### The hooks

- **`run-hooks.sh linux`:**
  - runs each `packaging/ci/linux.d/*.sh` in name order with `bash -euo pipefail`;
  - prints a header per hook and its time;
  - fails on the first non-zero exit.
- **`run-hooks.ps1 windows`:** the same for `packaging/ci/windows.d/*.ps1`.
- **Hooks see these variables:**
  - `CI_PY`: the Python with songcharter installed;
  - `CI_ART`: a folder for artifacts, never audio;
  - `CI_TMP`: scratch;
  - `CI_CLIP`: a 30-s clip that `make_clip.py` made before the hooks.
- **Numbering:**
  - 10 lanes (M4-01), 20 device (M4-02), 30 install (M4-03), 40 UI (M4-04), 50 end to end (M4-05), 60 results
    (M4-06), 70 release (M4-07);
  - Windows hooks reuse the same numbers.

### The helpers

- **`check_gate.py <song folder>`** passes when:
  - `report.json`'s `gate.ok` is true;
  - `gate.scan_chart.ran` is true, `playable` true, and `chart_issues` 0;
  - the folder holds `notes.chart`, `song.ini`, `song.ogg` and `report.json`;
  - guitar, bass and drums each have Expert onsets (the planning run had 23, 120 and 119).

  Otherwise it lists each failure.
- **`check_no_audio.py <folder>`** exits 1 on any audio extension (`.wav .mp3 .ogg .flac .m4a .opus .aac .wma .aif
  .aiff`), or on a file starting with `RIFF`, `OggS`, `ID3`, `fLaC` or an MPEG frame sync.

## Done means

1. [dev]
   - `bash -n packaging/ci/run-hooks.sh` and `python -m py_compile packaging/ci/*.py` both pass;
   - `check_no_audio.py` exits 1 on a folder with an `.ogg` and on a renamed WAV, and 0 on JSON and PNG files;
   - `make_clip.py clip.wav 30` writes a 30.0-s stereo WAV.
2. [CI] After the push, both jobs are green on `m4-05a-ci-skeleton`. Report the run's URL and the job times.
   - Reading the Actions API from a session may be refused by the proxy (planning job: `actions/permissions` was
     refused; listing runs answered). If it is, the owner reads the run, and the report says so.

## Depends on

Nothing.
