"""Tests of the CI tools in packaging/ci: the two hook runners and the helpers. They live here, not in tests/, because
they test CI itself; both CI jobs run them before the suite (`python -m pytest packaging/ci/test_ci.py`), the Windows
job with Windows' own pwsh.

Each test runs the scripts beside this file as programs, in throwaway folders: the bash runner's tests skip on Windows,
and the pwsh runner's tests skip where no pwsh is found ($PWSH, or pwsh on PATH). Only synthetic bytes are used: a
silent WAV from the `wave` module and audio headers written by hand.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import wave
import zipfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PWSH = os.environ.get("PWSH") or shutil.which("pwsh")
BASH = None if sys.platform == "win32" else shutil.which("bash")
need_bash = pytest.mark.skipif(BASH is None, reason="the bash runner's tests run on Linux")
need_pwsh = pytest.mark.skipif(PWSH is None, reason="no pwsh ($PWSH, or pwsh on PATH)")


def run(args, **kw) -> tuple[int, str]:
    p = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120, **kw)
    return p.returncode, p.stdout + p.stderr


# ------------------------------------------------------------------------------------------------ the hook runners

def repo(tmp_path: Path, platform: str, entries: dict[str, str | None] | None) -> Path:
    """A repository with packaging/ci/<runner>, and <platform>.d holding README.txt and `entries` (name: a file's
    text, or None for a folder). entries None: no hook folder at all. Returns the runner's path."""
    ci = tmp_path / "repo" / "packaging" / "ci"
    ci.mkdir(parents=True)
    script = ci / ("run-hooks.sh" if platform == "linux" else "run-hooks.ps1")
    shutil.copy(HERE / script.name, script)
    if entries is not None:
        hooks = ci / f"{platform}.d"
        hooks.mkdir()
        (hooks / "README.txt").write_text("the contract\n", encoding="utf-8")
        for name, text in entries.items():
            if text is None:
                (hooks / name).mkdir()
            else:
                (hooks / name).write_text(text, encoding="utf-8")
    return script


def ci_env(tmp_path: Path) -> dict[str, str]:
    clip = tmp_path / "clip.wav"     # given and present, so the bash runner does not make one (no numpy needed)
    clip.write_bytes(b"")
    return {**os.environ, "CI_PY": sys.executable, "CI_TMP": str(tmp_path / "ci-tmp"),
            "CI_ART": str(tmp_path / "ci-art"), "CI_CLIP": str(clip)}


def run_sh(tmp_path, entries):   # stdin holds a line, which no hook may read
    return run([BASH, repo(tmp_path, "linux", entries), "linux"], env=ci_env(tmp_path), input="FROM-STDIN\n")


def run_ps(tmp_path, entries):
    return run([PWSH, "-NoProfile", "-NonInteractive", "-File", repo(tmp_path, "windows", entries), "windows"],
               env=ci_env(tmp_path), input="FROM-STDIN\n")


@need_bash
def test_sh_a_folder_with_only_its_readme_passes(tmp_path):
    code, out = run_sh(tmp_path, {})
    assert code == 0 and "no Linux hooks" in out, out


@need_bash
def test_sh_a_missing_hook_folder_fails(tmp_path):
    code, out = run_sh(tmp_path, None)
    assert code == 2 and "no hook folder" in out, out


@need_bash
@pytest.mark.parametrize("stray", ["30-install.bash", "50-e2e", "10-x.ps1", "sub", ".hidden.sh", "notes.md"])
def test_sh_anything_but_hooks_and_the_readme_fails_before_any_hook_runs(tmp_path, stray):
    code, out = run_sh(tmp_path, {"10-ok.sh": "echo HOOK-RAN", stray: None if stray == "sub" else "echo x"})
    assert code == 2 and f"not a hook: linux.d/{stray}" in out and "HOOK-RAN" not in out, out


@need_bash
def test_sh_hooks_run_in_bytewise_order_and_the_first_failure_stops_the_run(tmp_path):
    code, out = run_sh(tmp_path, {"9-b.sh": "echo HOOK-B; exit 7", "10-a.sh": "echo HOOK-A", "B.sh": "echo HOOK-C"})
    assert code == 7 and out.index("HOOK-A") < out.index("HOOK-B") and "HOOK-C" not in out, out
    assert "linux.d/9-b.sh FAILED (exit 7)" in out


@need_bash
@pytest.mark.parametrize("body", ["false; echo AFTER", 'echo "$NOT_SET_ANYWHERE"; echo AFTER',
                                  "false | true; echo AFTER", "read -r line; echo AFTER $line"])
def test_sh_a_hook_runs_with_errexit_nounset_pipefail_and_no_stdin(tmp_path, body):
    code, out = run_sh(tmp_path, {"10-strict.sh": body})
    assert code != 0 and "AFTER" not in out, out


@need_pwsh
def test_ps_a_folder_with_only_its_readme_passes(tmp_path):
    code, out = run_ps(tmp_path, {})
    assert code == 0 and "no Windows hooks" in out, out


@need_pwsh
def test_ps_a_missing_hook_folder_fails(tmp_path):
    code, out = run_ps(tmp_path, None)
    assert code == 2 and "no hook folder" in out, out


@need_pwsh
@pytest.mark.parametrize("stray", ["30-shortcut.psm1", "50-e2e", "10-x.sh", "sub", ".hidden.ps1", "x.ps1xml"])
def test_ps_anything_but_hooks_and_the_readme_fails_before_any_hook_runs(tmp_path, stray):
    code, out = run_ps(tmp_path, {"10-ok.ps1": "'HOOK-RAN'", stray: None if stray == "sub" else "'x'"})
    assert code == 2 and f"not a hook: windows.d/{stray}" in out and "HOOK-RAN" not in out, out


@need_pwsh
def test_ps_hooks_run_in_ordinal_order_and_the_first_failure_stops_the_run(tmp_path):
    code, out = run_ps(tmp_path, {"9-b.ps1": "'HOOK-B'; exit 7", "10-a.ps1": "'HOOK-A'", "B.ps1": "'HOOK-C'"})
    assert code == 7 and out.index("HOOK-A") < out.index("HOOK-B") and "HOOK-C" not in out, out
    assert "windows.d/9-b.ps1 FAILED (exit 7)" in out


NATIVE_FAILS = "& $env:CI_PY -c 'import sys; sys.exit(3)'"
NATIVE_PASSES = "& $env:CI_PY -c 'pass'"


@need_pwsh
@pytest.mark.parametrize("body", ["Write-Error 'boom'", NATIVE_FAILS, "$x = $notSetAnywhere", "throw 'thrown'",
                                  "[int]::Parse('x')", "Get-Item -LiteralPath ./no/such/file"])
def test_ps_a_hook_stops_at_an_error_a_failing_native_command_or_an_unset_variable(tmp_path, body):
    code, out = run_ps(tmp_path, {"10-strict.ps1": f"{body}\n'AFTER'\n"})
    assert code != 0 and "AFTER" not in out, out


@need_pwsh
def test_ps_a_tolerated_native_failure_passes_once_reset(tmp_path):
    body = ("$PSNativeCommandUseErrorActionPreference = $false\n" + NATIVE_FAILS +
            "\nif ($LASTEXITCODE -ne 3) { throw 'no exit 3' }\n$global:LASTEXITCODE = 0\n'TOLERATED'\n")
    code, out = run_ps(tmp_path, {"10-tolerant.ps1": body})
    assert code == 0 and "TOLERATED" in out, out


@need_pwsh
def test_ps_warnings_reach_the_log_as_text_not_clixml(tmp_path):
    """F4: a child pwsh started with -EncodedCommand writes its streams as CLIXML on a piped stderr, unless it has
    -OutputFormat Text. Here stdout and stderr are pipes, as in CI."""
    code, out = run_ps(tmp_path, {"10-warn.ps1": "Write-Warning 'careful now'\n'done'\n"})
    assert code == 0 and "WARNING: careful now" in out and "CLIXML" not in out, out


@need_pwsh
def test_ps_a_sub_script_that_fails_last_fails_the_hook(tmp_path):
    """F5, the runner's part: a hook fails when its last $LASTEXITCODE is not 0, as after `& other.ps1` exiting 1."""
    sub = tmp_path / "sub.ps1"
    sub.write_text("exit 1\n", encoding="utf-8")
    code, out = run_ps(tmp_path, {"10-sub.ps1": f"& '{sub}'\n"})
    assert code == 1 and "10-sub.ps1 FAILED (exit 1)" in out, out


@need_pwsh
@pytest.mark.parametrize("call", ["& '{sub}'\nif ($LASTEXITCODE) {{ exit $LASTEXITCODE }}",
                                  "& (Get-Process -Id $PID).Path -NoProfile -File '{sub}'",
                                  "$p = Start-Process -FilePath (Get-Process -Id $PID).Path -ArgumentList "
                                  "'-NoProfile', '-File', '\"{sub}\"' -Wait -PassThru -NoNewWindow\n"
                                  "if ($p.ExitCode) {{ exit $p.ExitCode }}"])
def test_ps_the_readme_s_ways_to_check_a_sub_script_catch_its_failure(tmp_path, call):
    """F5: a sub-script's `exit 1` is lost when a native command succeeds after it, unless the hook checks it as
    windows.d/README.txt says. Each way it gives must fail the hook here."""
    sub = tmp_path / "sub.ps1"
    sub.write_text("exit 1\n", encoding="utf-8")
    code, out = run_ps(tmp_path, {"10-sub.ps1": call.format(sub=sub) + "\n" + NATIVE_PASSES + "\n'AFTER'\n"})
    assert code == 1 and "AFTER" not in out, out


def test_the_windows_readme_says_what_a_hook_must_check_itself():
    """F5: the two failures the runner cannot see are written down for the hooks' authors."""
    text = (HERE / "windows.d" / "README.txt").read_text(encoding="utf-8")
    for needle in ("& other.ps1", "if ($LASTEXITCODE) { exit $LASTEXITCODE }", "pwsh -NoProfile -File other.ps1",
                   "Start-Process -Wait -PassThru", ".ExitCode"):
        assert needle in text, needle


# ------------------------------------------------------------------------------------------------ check_no_audio.py

def wav_bytes() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00" * 4 * 4410)
    return buf.getvalue()


HEADERS = {   # renamed audio of each kind: the first bytes only, which is all the check reads
    "wav": wav_bytes(), "aiff": b"FORM\x00\x00\x10\x00AIFFCOMM" + bytes(64), "aifc": b"FORM\x00\x00\x10\x00AIFCFVER",
    "m4a": b"\x00\x00\x00\x20ftypM4A \x00\x00\x02\x00" + bytes(64), "webm": b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81",
    "ogg": b"OggS\x00\x02" + bytes(64), "flac": b"fLaC\x00\x00\x00\x22", "id3": b"ID3\x04\x00\x00",
    "mp3": b"\xff\xfb\x90\xc4" + bytes(64)}
PNG = b"\x89PNG\r\n\x1a\n" + bytes(64)


def check_no_audio(*paths):
    return run([sys.executable, HERE / "check_no_audio.py", *paths])


def zip_of(files: dict[str, bytes], method=zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", method) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def tar_of(files: dict[str, bytes], mode="w") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode=mode) as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_a_folder_of_json_png_and_text_passes(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "report.json").write_text(json.dumps({"gate": {"ok": True}}), encoding="utf-8")
    (tmp_path / "sub" / "overview.png").write_bytes(PNG)
    (tmp_path / "log.txt").write_text("a log, UTF-8: Jörg\n", encoding="utf-8")
    (tmp_path / "empty").write_bytes(b"")
    code, out = check_no_audio(tmp_path)
    assert code == 0 and "4 files" in out, out


@pytest.mark.parametrize("name", ["song.ogg", "SONG.WAV", "a/b/deep.flac", "x.opus"])
def test_an_audio_extension_fails(tmp_path, name):
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_bytes(b"not even audio")
    code, out = check_no_audio(tmp_path)
    assert code == 1 and "an audio extension" in out, out


@pytest.mark.parametrize("kind", sorted(HEADERS))
def test_renamed_audio_fails_by_its_first_bytes(tmp_path, kind):
    (tmp_path / "report.json").write_bytes(HEADERS[kind])
    code, out = check_no_audio(tmp_path)
    assert code == 1 and "report.json: starts with" in out, out


ARCHIVES = {   # name: (bytes, the member the check must name)
    "bundle.zip": (zip_of({"Clip/report.json": b"{}", "Clip/song.wav": b"x"}), "bundle.zip!Clip/song.wav"),
    "stored.zip": (zip_of({"a.png": PNG, "notes.txt": HEADERS["wav"]}, zipfile.ZIP_STORED), "stored.zip!notes.txt"),
    "dist.tar": (tar_of({"sc-0.1/x.json": HEADERS["m4a"]}), "dist.tar!sc-0.1/x.json"),
    "dist.tar.gz": (tar_of({"sc-0.1/a.json": b"{}", "sc-0.1/clip.bin": HEADERS["wav"]}, "w:gz"),
                    "dist.tar.gz!sc-0.1/clip.bin"),
    "dist.tar.xz": (tar_of({"sc-0.1/t.ogg": b"x"}, "w:xz"), "dist.tar.xz!sc-0.1/t.ogg"),
    "dist.tar.bz2": (tar_of({"sc-0.1/t": HEADERS["flac"]}, "w:bz2"), "dist.tar.bz2!sc-0.1/t"),
    "renamed.dat": (zip_of({"take.mp3": b"x"}), "renamed.dat!take.mp3"),
    "clip.wav.gz": (gzip.compress(HEADERS["wav"], mtime=0), "clip.wav.gz!clip.wav"),
    "blob.gz": (gzip.compress(HEADERS["webm"], mtime=0), "blob.gz!blob"),
    "nested.zip": (zip_of({"inner.tar.gz": tar_of({"d/deep.zip": zip_of({"x.json": HEADERS["aiff"]})}, "w:gz")}),
                   "nested.zip!inner.tar.gz!d/deep.zip!x.json"),
}


@pytest.mark.parametrize("given", ["folder", "file"])
@pytest.mark.parametrize("name", sorted(ARCHIVES))
def test_audio_inside_an_archive_fails_given_its_folder_or_the_archive(tmp_path, name, given):
    data, member = ARCHIVES[name]
    (tmp_path / name).write_bytes(data)
    code, out = check_no_audio(tmp_path if given == "folder" else tmp_path / name)
    assert code == 1 and member in out, out


@pytest.mark.parametrize("given", ["folder", "file"])
def test_clean_archives_pass(tmp_path, given):
    files = {"Clip/report.json": b"{}", "Clip/overview.png": PNG, "Clip/notes.chart": b"[Song]\n"}
    (tmp_path / "d.zip").write_bytes(zip_of({**files, "inner.tar.gz": tar_of(files, "w:gz")}))
    (tmp_path / "r.tar.xz").write_bytes(tar_of(files, "w:xz"))
    code, out = check_no_audio(*([tmp_path] if given == "folder" else [tmp_path / "d.zip", tmp_path / "r.tar.xz"]))
    assert code == 0 and "2 files and 10 archive members" in out, out


def test_an_archive_nested_too_deep_or_unreadable_fails(tmp_path):
    data = zip_of({"x.json": b"{}"})
    for level in range(5):
        data = zip_of({f"level{level}.zip": data})
    (tmp_path / "deep.zip").write_bytes(data)
    (tmp_path / "broken.zip").write_bytes(b"PK\x03\x04" + b"not a zip" * 20)
    code, out = check_no_audio(tmp_path)
    assert code == 1 and "nested deeper than 4 levels" in out and "broken.zip: a zip archive that cannot be read" in out


def test_a_path_that_does_not_exist_is_bad_input(tmp_path):
    code, out = check_no_audio(tmp_path / "nowhere")
    assert code == 2 and "no such file or folder" in out, out


# ------------------------------------------------------------------------------------------------ check_gate.py

def song_folder(path: Path, ok=True) -> Path:
    path.mkdir(parents=True)
    for name in ("notes.chart", "song.ini", "song.ogg"):
        (path / name).write_bytes(b"")
    report = {"gate": {"ok": ok, "errors": 0 if ok else 1, "scan_chart": {"ran": True, "version": "8.0.1",
                                                                          "playable": True, "chart_issues": 0},
                       "issues": [] if ok else [{"kind": "syncLag", "message": "40 ms late", "error": True}]},
              "tracks": {"guitar": {"expert": {"onsets": 23}}, "bass": {"expert": {"onsets": 120}},
                         "drums": {"expert": {"onsets": 119}}}}
    (path / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return path


def check_gate(folder):
    return run([sys.executable, HERE / "check_gate.py", folder])


def test_a_folder_that_passed_its_gate_passes(tmp_path):
    code, out = check_gate(song_folder(tmp_path / "Clip"))
    assert code == 0 and "Expert onsets guitar 23, bass 120, drums 119" in out, out


def test_a_failed_rebuild_beside_an_earlier_good_build_fails(tmp_path):
    """F3: the gate failed the latest build, so it went to Clip.failed, and Clip still holds the earlier, passing
    build."""
    song_folder(tmp_path / "Clip")
    song_folder(tmp_path / "Clip.failed", ok=False)
    code, out = check_gate(tmp_path / "Clip")
    assert code == 1 and "Clip.failed: the gate failed it" in out and "syncLag: 40 ms late" in out, out


def test_a_build_that_only_went_to_failed_fails_and_says_why(tmp_path):
    song_folder(tmp_path / "Clip.failed", ok=False)
    code, out = check_gate(tmp_path / "Clip")
    assert code == 1 and "syncLag: 40 ms late" in out, out


def test_no_folder_at_all_fails(tmp_path):
    code, out = check_gate(tmp_path / "Clip")
    assert code == 1 and "no song folder" in out, out


# ------------------------------------------------------------------------------------------------ make_clip.py

def test_make_clip_writes_a_30_s_stereo_wav(tmp_path):
    pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    code, out = run([sys.executable, HERE / "make_clip.py", tmp_path / "clip.wav", "30"])
    info = sf.info(str(tmp_path / "clip.wav"))
    assert code == 0 and (info.channels, info.samplerate, info.frames) == (2, 44100, 30 * 44100), out
