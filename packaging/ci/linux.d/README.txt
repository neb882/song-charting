Linux CI hooks: the `linux` job of .github/workflows/ci.yml (ubuntu-latest, 120 min for the whole job)

Each work order lands its own CI checks here as hook files, the day it lands. Only M4-05a edits ci.yml and the
runners; an order adds or changes its own hooks and nothing else in packaging/ci/.

How they run
- After the suite has passed, `bash packaging/ci/run-hooks.sh linux` runs every *.sh file in this folder in name
  order (bytewise), each as `bash -euo pipefail <hook>`, from the repository's root, with stdin from /dev/null.
- Each hook gets a header and its time in the log. The first hook that exits non-zero fails the job, and the hooks
  after it do not run.
- By hand, from the repository's root: `CI_PY=<a Python with songcharter> bash packaging/ci/run-hooks.sh linux`.

Names: NN-name.sh, NN being the order that adds the hook
  10 lanes (M4-01)          40 UI (M4-04)               70 release (M4-07)
  20 device (M4-02)         50 end to end (M4-05)
  30 install (M4-03)        60 results (M4-06)
Windows hooks (../windows.d) reuse the same numbers.

What a hook sees
  CI_PY    the Python with songcharter installed, with the extras the suite uses (the suite's own Python):
           setup-python's 3.13 with `pip install -e ".[dev,separate,drums,bass,sections,preview]"` and torch from
           PyTorch's cpu index; once uv.lock exists, the project's .venv from
           `uv sync --frozen --extra cpu --extra app --extra dev`.
  CI_ART   a folder for artifacts, uploaded when the job ends, pass or fail (artifact `ci-linux`). Never audio:
           check_no_audio.py runs on it first, and one audio file fails the job and stops the upload.
  CI_TMP   scratch, gone with the runner.
  CI_CLIP  a 30-s synthetic clip (WAV, stereo, 44.1 kHz), written by make_clip.py before the first hook. It is audio:
           never copy it into CI_ART.
  Also: the working folder is the repository's root; node and npm (Node 24.19.0); tools/scan-chart/node_modules
  (npm ci) and SONGCHARTER_SCAN_CHART pointing at tools/scan-chart/scan.cjs; uv 0.13.5 once uv.lock exists; Docker
  (ubuntu-latest has it); the network.

Helpers (packaging/ci/; check_gate.py and check_no_audio.py need only the standard library)
  make_clip.py OUT.wav [SECONDS]    the clip (default 30 s), deterministic
  check_gate.py SONG_FOLDER         a built song folder passed its gate: the four files, gate.ok, scan-chart ran and
                                    found it playable with 0 chart issues, Expert onsets on guitar, bass and drums
  check_no_audio.py FOLDER ...      no audio by extension or by its first bytes; exit 1 lists each file
