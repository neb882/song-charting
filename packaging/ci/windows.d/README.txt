Windows CI hooks: the `windows` job of .github/workflows/ci.yml (windows-latest, 30 min for the whole job, pwsh)

For the few files songcharter writes on the Windows side (the Start-menu shortcut, M4-03), checked by Windows itself.
Each work order lands its own hooks here. Only M4-05a edits ci.yml and the runners; an order adds or changes its own
hooks and nothing else in packaging/ci/.

How they run
- `./packaging/ci/run-hooks.ps1 windows` runs every *.ps1 file in this folder in name order (ordinal), each in a
  fresh pwsh from the repository's root.
- A hook runs with $ErrorActionPreference = 'Stop', Set-StrictMode -Version Latest and
  $PSNativeCommandUseErrorActionPreference = $true, PowerShell's `bash -euo pipefail`: an error, or a native command
  that exits non-zero, stops it. To let a native command fail, set $PSNativeCommandUseErrorActionPreference = $false
  around it and read $LASTEXITCODE.
- A hook fails by stopping that way, by `exit N` with N not 0, or by ending with a non-zero $LASTEXITCODE. The first
  hook that fails fails the job, and the hooks after it do not run. Each hook gets a header and its time in the log.
- With no hooks the runner prints "no Windows hooks" and passes.

Names: NN-name.ps1, the same numbers as the Linux hooks (../linux.d/README.txt): 30 is M4-03's shortcut.

What a hook sees
  CI_PY    setup-python's Python 3.13, with pytest and LnkParse3 only. songcharter is not installed here: import it
           from the repository's root, the working folder (`python -c "from songcharter import ..."`,
           `python -m pytest tests/...`), so a hook can use only modules that need no third-party package.
  CI_ART   a folder for artifacts, uploaded when the job ends, pass or fail (artifact `ci-windows`). Never audio:
           check_no_audio.py runs on it first, and one audio file fails the job and stops the upload.
  CI_TMP   scratch, gone with the runner.
  There is no CI_CLIP on Windows: the job installs no numpy or soundfile, so make_clip.py cannot run.
  The runner image turns long paths on and Defender's real-time protection off, so a hook cannot prove either.
