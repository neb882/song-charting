"""The UI's job (songcharter.ui.jobs): the page's options checked and turned into `songcharter chart`'s command line,
the `@@songcharter` lines of the child's stderr read as events, the end states, and cancel. The child is a stand-in
program (STANDIN) that writes what `chart --events` writes; the real command line's events are tested in
test_pipeline.py."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from songcharter import device, proc
from songcharter.errors import InputError
from songcharter.ui import jobs as J

STANDIN = r'''
import json, os, subprocess, sys, time
mode, out = sys.argv[1], sys.argv[2]

def ev(**e):
    sys.stderr.write("@@songcharter " + json.dumps(e, ensure_ascii=True) + "\n")
    sys.stderr.flush()

print("song folder: on stdout", flush=True)
ev(event="plan", stages=["decode", "guitar", "assemble"])
ev(event="stage_start", stage="decode", index=1, count=3, detail="song.wav")
sys.stderr.write("[1/3] decode: song.wav\n@@songcharter {not json\n")
sys.stderr.buffer.write("caf\xe9 \u266b\n".encode("utf-8") + b"\xff broken utf-8\n")
sys.stderr.flush()
ev(event="stage_end", stage="decode", seconds=0.1, cached=False, detail="1.00 s of audio")
if mode == "gate_failed":
    ev(event="result", ok=False, exit=1, folder=out + ".failed", work="/w", preview=None, summary="gate: FAILED")
    sys.exit(1)
if mode == "ok":
    ev(event="result", ok=True, exit=0, folder=out, work="/w", preview="/w/preview", summary="gate: OK")
    sys.exit(0)
if mode == "linger":   # the result out, then a second of exiting (the interpreter's shutdown, say)
    ev(event="result", ok=True, exit=0, folder=out, work="/w", preview="/w/preview", summary="gate: OK")
    time.sleep(1.0)
    sys.exit(0)
if mode == "bad_input":
    sys.stderr.write("songcharter: error: no instruments to chart\n")
    ev(event="error", kind="input", message="no instruments to chart")
    sys.exit(2)
if mode == "crash":   # exit 3 with no error event: the job writes its own
    sys.stderr.write("Traceback (most recent call last):\nKeyError: 'a bug'\n")
    sys.exit(3)
if mode == "silent":   # exit 0 with no result: not a verdict
    sys.exit(0)
if mode == "result_then_dies":   # the result out (the build in place), then a crash on the way out
    ev(event="result", ok=True, exit=0, folder=out, work="/w", preview=None, summary="gate: OK")
    os._exit(3)
if mode == "killed":   # the kernel's OOM killer, say: SIGKILL from elsewhere
    os.kill(os.getpid(), 9)
# "hang": assemble's staging beside the output, a grandchild (autochart's node, say), then a take that never ends
staging = os.path.join(os.path.dirname(out), "." + os.path.basename(out) + ".x1y2.partial")
os.makedirs(os.path.join(staging, "sub"))
open(os.path.join(staging, "sub", "notes.chart"), "w").close()
grandchild = subprocess.Popen(["sleep", "60"])
ev(event="stage_start", stage="guitar", index=2, count=3, detail="autochart, 1 take")
ev(event="take", index=1, count=1, seed=20260609, pids=[os.getpid(), grandchild.pid])
time.sleep(60)
'''

UPLOAD = {"id": "0123456789abcdef", "name": "Jörg's Song.flac",
          "metadata": {"name": "Ünïcode: Title?", "artist": "Ann/Bo"}}


@pytest.fixture
def standin(tmp_path):
    script = tmp_path / "standin.py"
    script.write_text(STANDIN, encoding="utf-8")

    def make(mode: str):
        def command(song, out, options, threads):
            return [sys.executable, str(script), mode, str(out)]
        return command
    return make


def upload(tmp_path) -> dict:
    song = tmp_path / "uploads" / UPLOAD["id"] / "Jorg's Song.flac"
    song.parent.mkdir(parents=True, exist_ok=True)
    song.write_bytes(b"not really audio")
    return {**UPLOAD, "path": str(song)}


def wait_state(job, timeout=20.0):
    deadline = time.monotonic() + timeout
    while job.state == "running" and time.monotonic() < deadline:
        time.sleep(0.02)
    if job.reader is not None:
        job.reader.join(timeout)
    return job.state


def wait_event(job, kind, timeout=20.0):
    seen = 0
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        new, ended = job.wait_events(seen, 0.2)
        for e in new:
            if e["event"] == kind:
                return e
        seen += len(new)
        if ended:
            break
    raise AssertionError(f"no {kind} event in {[e['event'] for e in job.events]}")


# ------------------------------------------------------------------------------------------------ the lines

def test_parse_line():
    assert J.parse_line('@@songcharter {"event": "take", "index": 1, "count": 4, "seed": 101}') == {
        "event": "take", "index": 1, "count": 4, "seed": 101}
    for line in ("[1/8] decode: song.flac", '@@songcharter {"event": 1}', "@@songcharter [1, 2]",
                 "@@songcharter {not json", '  @@songcharter {"event": "plan"}', '@@songcharter{"event": "plan"}',
                 '@@songcharte {"event": "plan"}', '@@songchartex {"event": "plan"}', '{"event": "plan"}', ""):
        assert J.parse_line(line) is None, line


# ------------------------------------------------------------------------------------------------ the options

def test_the_options_become_the_command_line(tmp_path, monkeypatch):
    opts = J.parse_options({"title": "  -Title  with  spaces ", "artist": "", "album": None, "year": "1999",
                            "genre": "Rock", "instruments": ["Guitar", "drums"], "levels": ["hard", "expert"],
                            "solos": ["Solo 1", " Solo  2 "], "takes": 3, "device": "cpu", "preview": False})
    assert opts.metadata == {"title": "-Title with spaces", "year": "1999", "genre": "Rock"}
    assert opts.instruments == ("guitar", "drums") and opts.levels == ("hard", "expert")
    assert opts.solos == ("Solo 1", "Solo 2") and opts.takes == 3 and not opts.preview
    out = tmp_path / "library" / "x" / "Ann_Bo - T"
    cmd = J.chart_command(Path("/s/song.flac"), out, opts, 7)
    assert cmd[:5] == [sys.executable, "-m", "songcharter.cli", "chart", "/s/song.flac"]
    # every value as --flag=VALUE: a title that starts with "-" stays a title
    assert cmd[5:] == [f"--out={out}", "--events", "--instruments=guitar,drums", "--levels=expert,hard",
                       "--solos=Solo 1,Solo 2", "--device=cpu", "--takes=3", "--threads=7", "--no-preview",
                       "--title=-Title with spaces", "--year=1999", "--genre=Rock"]
    import songcharter.pipeline as P
    from songcharter.cli import main
    seen = {}

    def chart(song, o, options, events=None):
        seen.update(options=options, events=events)
        raise KeyboardInterrupt

    monkeypatch.setattr(P, "chart", chart)
    assert main(cmd[3:]) == 130   # the command line takes exactly those arguments
    o = seen["options"]
    assert (o.instruments, o.levels, o.solos, o.takes, o.device, o.threads, o.preview) == (
        ("guitar", "drums"), ("expert", "hard"), ("Solo 1", "Solo 2"), 3, "cpu", 7, False)
    assert o.metadata == {"name": "-Title with spaces", "year": "1999", "genre": "Rock"} and seen["events"]

    defaults = J.parse_options({})
    assert J.chart_command(Path("/s.mp3"), out, defaults, None)[5:] == [
        f"--out={out}", "--events", "--instruments=guitar,bass,drums", "--levels=expert", "--solos=labels",
        "--device=auto"]
    assert J.parse_options(None) == defaults and J.parse_options({"solos": "OFF", "takes": None}).solos == "off"


def test_the_stems_and_one_audio_options_become_their_flags(tmp_path, monkeypatch):
    """M8-12: `stems` and `one_audio`, off by default, become --stems and --one-audio, reach pipeline.Options, and
    the job's records show them (break: a flag left off the command, or not read by the command line)."""
    opts = J.parse_options({"stems": True, "one_audio": True})
    assert opts.stems and opts.one_audio and opts.as_dict()["stems"] is True and opts.as_dict()["one_audio"] is True
    out = tmp_path / "Ann - T"
    cmd = J.chart_command(Path("/s.mp3"), out, opts, None)
    assert cmd[-2:] == ["--stems", "--one-audio"]
    off = J.parse_options({})
    assert not off.stems and not off.one_audio and "--stems" not in J.chart_command(Path("/s.mp3"), out, off, None)
    assert "--one-audio" not in J.chart_command(Path("/s.mp3"), out, off, None)
    import songcharter.pipeline as P
    from songcharter.cli import main
    seen = {}

    def chart(song, o, options, events=None):
        seen.update(options=options)
        raise KeyboardInterrupt

    monkeypatch.setattr(P, "chart", chart)
    assert main(cmd[3:]) == 130
    assert seen["options"].stems is True and seen["options"].one_audio is True
    assert main(J.chart_command(Path("/s.mp3"), out, off, None)[3:]) == 130
    assert seen["options"].stems is False and seen["options"].one_audio is False
    # a cancelled chart's stems staging goes with assemble's (partial_folders), for a name a glob would misread too
    # (break: glob.escape left off the stems' name: M8-12's review)
    live = tmp_path / "Ann - T [Live]"
    for name in (".Ann - T.x1.partial", ".Ann - T (stems).x2.partial", ".Other.x3.partial",
                 ".Ann - T [Live].x4.partial", ".Ann - T [Live] (stems).x5.partial", ".Ann - T L (stems).x6.partial"):
        (tmp_path / name).mkdir()
    assert [p.name for p in J.partial_folders(out)] == [".Ann - T (stems).x2.partial", ".Ann - T.x1.partial"]
    assert [p.name for p in J.partial_folders(live)] == [".Ann - T [Live] (stems).x5.partial",
                                                        ".Ann - T [Live].x4.partial"]


@pytest.mark.parametrize("raw, message", [
    ({"stems": "yes"}, "stems is true or false"),
    ({"one_audio": 1}, "one_audio is true or false"),
    ({"instruments": ["guitar", "piano"]}, "instruments are guitar, bass, drums"),
    ({"instruments": []}, "no instruments"),
    ({"instruments": "guitar"}, "instruments is a list"),
    ({"levels": ["hard"]}, "expert among them"),
    ({"takes": 2}, "takes is 1, or 3 or more"),
    ({"takes": "4"}, "takes is 1, or 3 or more"),
    ({"takes": 3, "instruments": ["bass"]}, "takes are guitar takes"),
    ({"device": "gpu"}, "device is auto, cpu or cuda"),
    ({"threads": 0}, "threads must be"),
    ({"preview": "yes"}, "preview is true or false"),
    ({"solos": "loud"}, "solos is"),
    ({"solos": ["Solo, 1"]}, "cannot hold a comma"),
    ({"solos": "stems", "instruments": ["drums"]}, "solos are guitar solos"),
    ({"title": 3}, "title is text"),
    ({"album_art": 3}, "album_art is an uploaded image"),
    ({"background": ["x.png"]}, "background is an uploaded image"),
    ({"background": "  "}, "background is an image file's path or None"),
    ({"tempo": "auto"}, "unknown option(s): tempo"),
    ([], "options is an object"),
])
def test_bad_options_are_refused_with_the_checks_message(raw, message):
    with pytest.raises(InputError, match=None) as e:
        J.parse_options(raw)
    assert message in str(e.value), str(e.value)


def test_the_pictures_become_their_flags(tmp_path, monkeypatch):
    """The images' paths (the server's, for the page's upload ids) become --album-art and --background, as values
    (one that starts with "-" stays a value), and reach pipeline.Options; the job's records say only whether each
    was given."""
    art, bg = tmp_path / "up" / "-cover.png", tmp_path / "up" / "bg one.jpg"
    opts = J.parse_options({"album_art": str(art), "background": str(bg)})
    assert (opts.album_art, opts.background) == (str(art), str(bg))
    assert opts.as_dict()["album_art"] is True and opts.as_dict()["background"] is True
    assert str(art) not in json.dumps(opts.as_dict())
    out = tmp_path / "library" / "x" / "A - T"
    cmd = J.chart_command(Path("/s/song.flac"), out, opts, None)
    assert cmd[-2:] == [f"--album-art={art}", f"--background={bg}"]
    import songcharter.pipeline as P
    from songcharter.cli import main
    seen = {}

    def chart(song, o, options, events=None):
        seen.update(options=options)
        raise KeyboardInterrupt

    monkeypatch.setattr(P, "chart", chart)
    assert main(cmd[3:]) == 130
    assert (seen["options"].album_art, seen["options"].background) == (art, bg)
    none = J.parse_options({"album_art": None})
    assert none.album_art is None and none.as_dict()["album_art"] is False
    assert not any(a.startswith(("--album-art", "--background")) for a in J.chart_command(Path("/s"), out, none, None))


def test_threads_default_on_the_cpu_only():
    opts = J.parse_options
    n = device.default_threads()
    assert J.threads_for(opts({"device": "cpu"}), None) == n
    assert J.threads_for(opts({}), "cpu") == n
    assert J.threads_for(opts({}), "cuda") is None and J.threads_for(opts({}), None) is None
    assert J.threads_for(opts({"device": "cuda"}), "cpu") is None
    assert J.threads_for(opts({"threads": 3}), "cpu") == 3


def test_the_output_folder_is_safe_for_windows(tmp_path):
    up = {**UPLOAD, "path": "/u/x.flac"}
    assert J.output_folder(tmp_path, up, J.parse_options({})) == (
        tmp_path / "library" / UPLOAD["id"] / "Ann_Bo - Unicode_ Title_")
    given = J.parse_options({"artist": "Ånn Øx", "title": "Xylö"})
    assert J.output_folder(tmp_path, up, given).name == "Ann Ox - Xylo"
    bare = {"id": UPLOAD["id"], "path": "/u/CON.flac", "metadata": {}}
    assert J.output_folder(tmp_path, bare, J.parse_options({})).name == "Unknown - CON"


def test_the_library_folder_is_cut_at_a_word_within_80(tmp_path):
    """The name the friend sees in Clone Hero's Songs folder: up to LIBRARY_NAME_MAX (80) units, not the work
    folder's 40, cut at a word; installed, its deepest Windows path (clonehero.py's .tmp copy) stays under 259."""
    artist, title = "The Made-Up Orchestra of Somewhere", "A Rather Long Song Title That Goes On and On Forever"
    up = {"id": UPLOAD["id"], "path": "/u/x.flac", "metadata": {"name": title, "artist": artist}}
    name = J.output_folder(tmp_path, up, J.parse_options({})).name
    full = f"{artist} - {title}"
    assert len(full) > J.LIBRARY_NAME_MAX == 80
    # 78 units: the cut at 80 fell inside "On"
    assert name == "The Made-Up Orchestra of Somewhere - A Rather Long Song Title That Goes On and"
    assert len(name) <= 80 and full[len(name)] == " "   # ends at a word: the next character is a space
    given = J.parse_options({"artist": "Given Band", "title": "x" * 90})
    assert J.output_folder(tmp_path, up, given).name == "Given Band - " + "x" * 67   # one long word: cut hard
    deepest = ("C:\\Users\\" + "u" * 20 + "\\Documents\\Clone Hero\\Songs\\." + "n" * J.LIBRARY_NAME_MAX
               + ".songcharter-01234567.tmp\\background.jpg")
    assert len(deepest) == 178 < 259


# ------------------------------------------------------------------------------------------------ a job

def test_a_chart_whose_gate_fails_is_done_with_ok_false(tmp_path, standin):
    jobs = J.Jobs(tmp_path, command=standin("gate_failed"))
    job = jobs.start(upload(tmp_path), {})
    assert wait_state(job) == "done" and job.returncode == 1
    kinds = [e["event"] for e in job.events]
    assert kinds == ["plan", "stage_start", "stage_end", "result"] and job.events[-1]["ok"] is False
    assert all(isinstance(e["at"], float) for e in job.events)
    assert job.out == tmp_path / "library" / UPLOAD["id"] / "Ann_Bo - Unicode_ Title_"
    # every line of the child, stdout's included, in the job's log; the events too; bad UTF-8 replaced
    assert job.log.parent == tmp_path / "logs" and job.log.name == f"job-{job.id}.log"
    log = job.log.read_text(encoding="utf-8")
    for line in ("song folder: on stdout", "[1/3] decode: song.wav", "@@songcharter {not json", "café ♫",
                 "\ufffd broken utf-8", '@@songcharter {"event": "result", "ok": false'):
        assert line in log, line
    snap = job.snapshot()
    assert snap["state"] == "done" and snap["exit"] == 1 and len(snap["events"]) == 4
    assert snap["upload"] == {"id": UPLOAD["id"], "name": UPLOAD["name"]} and snap["estimate"] is None
    # a second job may start now; it has a log of its own even within the same second
    second = jobs.start(upload(tmp_path), {})
    assert wait_state(second) == "done" and second.log != job.log and jobs.current is second


def test_the_estimate_given_at_the_start_is_in_the_snapshot(tmp_path, standin):
    """The server's estimate (estimate.for_job) goes into the job as given, a copy, and its snapshot carries it for
    the progress screen (M7-10)."""
    est = {"seconds": 241.0, "takes": 4, "device": "cuda", "low_s": 246.3, "high_s": 588.5, "low_min": 4,
           "high_min": 10}
    given = dict(est)
    job = J.Jobs(tmp_path, command=standin("ok")).start(upload(tmp_path), {}, auto_device="cuda", estimate=given)
    given["low_min"] = 99
    assert wait_state(job) == "done"
    assert job.snapshot()["estimate"] == est and job.snapshot(events=False)["estimate"] == est
    assert json.loads(json.dumps(job.snapshot()))["estimate"] == est


@pytest.mark.parametrize("mode, kind, head, tail", [
    ("bad_input", "input", "no instruments to chart", ""),
    ("crash", "bug", "the chart exited 3:\n", "\ncafé ♫\n\ufffd broken utf-8\nTraceback (most recent call last):\n"
                                              "KeyError: 'a bug'"),   # the log's last lines, the event lines left out
    ("silent", "bug", "the chart exited 0:\n", "\n[1/3] decode: song.wav\n@@songcharter {not json\ncafé ♫\n"
                                               "\ufffd broken utf-8"),
    ("killed", "tool", "the chart was stopped by SIGKILL (by the system: out of memory, perhaps):\n", "broken utf-8"),
])
def test_a_chart_that_fails_ends_with_an_error(tmp_path, standin, mode, kind, head, tail):
    jobs = J.Jobs(tmp_path, command=standin(mode))
    job = jobs.start(upload(tmp_path), {})
    assert wait_state(job) == "failed"
    last = job.events[-1]
    assert last["event"] == "error" and last["kind"] == kind, last
    assert last["message"].startswith(head) and last["message"].endswith(tail), last["message"]
    assert sum(e["event"] in J.CLOSING for e in job.events) == 1


def test_a_new_job_waits_for_one_whose_result_is_out(tmp_path, standin):
    """The page offers the next song once the result is in; the chart's process may take a moment more to exit.
    A start then waits for it instead of answering 409."""
    jobs = J.Jobs(tmp_path, command=standin("linger"))
    first = jobs.start(upload(tmp_path), {})
    wait_event(first, "result")
    assert first.state == "running"   # still exiting
    t0 = time.monotonic()
    second = jobs.start(upload(tmp_path), {})
    assert first.state == "done" and 0.3 < time.monotonic() - t0 < 5 and jobs.current is second
    assert wait_state(second) == "done"


def test_a_cancel_after_the_result_keeps_the_chart_done(tmp_path, standin):
    """The second after the result, while the chart's process is still exiting: a cancel then (a click, or the
    server stopping) cuts the exit short but leaves the outcome: done, no `cancelled`, one closing event."""
    jobs = J.Jobs(tmp_path, command=standin("linger"))
    job = jobs.start(upload(tmp_path), {})
    wait_event(job, "result")
    assert job.state == "running"
    assert jobs.cancel() is job
    assert job.state == "done" and job.returncode == -15
    assert [e["event"] for e in job.events][-1] == "result" and sum(e["event"] in J.CLOSING for e in job.events) == 1
    new, ended = job.wait_events(len(job.events), 0.1)
    assert new == [] and ended
    # a chart whose process fails after its result is done too: the result comes once the build is in place
    jobs = J.Jobs(tmp_path, command=standin("result_then_dies"))
    job = jobs.start(upload(tmp_path), {})
    assert wait_state(job) == "done" and job.returncode == 3 and job.events[-1]["event"] == "result"


def test_one_job_at_a_time(tmp_path, standin):
    jobs = J.Jobs(tmp_path, command=standin("hang"))
    job = jobs.start(upload(tmp_path), {})
    try:
        with pytest.raises(J.JobRunning):
            jobs.start(upload(tmp_path), {})
        with pytest.raises(InputError, match="takes is 1, or 3 or more"):   # bad options: refused before the 409
            J.Jobs(tmp_path, command=standin("hang")).start(upload(tmp_path), {"takes": 2})
    finally:
        jobs.cancel()
    assert job.state == "cancelled"
    with pytest.raises(J.NotRunning):
        jobs.cancel()


def test_cancel_kills_the_tree_and_deletes_the_staging(tmp_path, standin):
    jobs = J.Jobs(tmp_path, command=standin("hang"))
    job = jobs.start(upload(tmp_path), {})
    take = wait_event(job, "take")
    pids = take["pids"]
    staging = job.out.parent / f".{job.out.name}.x1y2.partial"
    assert staging.is_dir() and all(proc.alive(p) for p in pids)
    keep = job.out.parent / "kept.txt"   # anything else beside the output stays
    keep.write_text("x")
    t0 = time.monotonic()
    assert jobs.cancel() is job
    assert time.monotonic() - t0 < 4
    assert job.state == "cancelled" and job.returncode == -15
    assert not any(proc.alive(p) for p in pids)            # the chart and its grandchild, by pid
    assert not proc.group_alive(job.tree.pgid)
    assert not staging.exists() and J.partial_folders(job.out) == [] and keep.is_file()
    assert [e["event"] for e in job.events][-2:] == ["take", "cancelled"]
    new, ended = job.wait_events(len(job.events), 0.1)
    assert new == [] and ended
    # a song whose name holds [ or ] (a glob's character class): its staging goes too
    job4 = jobs.start(upload(tmp_path), {"title": "Song [Live] *?"})
    wait_event(job4, "take")
    staging4 = job4.out.parent / f".{job4.out.name}.x1y2.partial"
    assert job4.out.name == "Ann_Bo - Song [Live] __" and staging4.is_dir()
    assert jobs.cancel().state == "cancelled" and not staging4.exists()
    # two cancels at once (a click, and the server stopping): one kill, one "cancelled", the other NotRunning
    import threading
    job3 = jobs.start(upload(tmp_path), {})
    wait_event(job3, "take")
    answers = []

    def cancel():
        try:
            answers.append(jobs.cancel().state)
        except J.NotRunning:
            answers.append("not running")

    both = [threading.Thread(target=cancel) for _ in range(2)]
    for t in both:
        t.start()
    for t in both:
        t.join(20)
    assert sorted(answers) == ["cancelled", "not running"]
    assert [e["event"] for e in job3.events].count("cancelled") == 1
    # a stopped server stops its job the same way
    jobs2 = J.Jobs(tmp_path, command=standin("hang"))
    job2 = jobs2.start(upload(tmp_path), {})
    pids2 = wait_event(job2, "take")["pids"]
    jobs2.shutdown()
    assert job2.state == "cancelled" and not any(proc.alive(p) for p in pids2)
    jobs2.shutdown()   # nothing running: nothing to do


def test_a_log_that_cannot_be_written_still_ends_the_job(tmp_path, standin, monkeypatch):
    """A full disk, say: the lines are read on (so the child never blocks on a full pipe) and the job still ends."""
    jobs = J.Jobs(tmp_path, command=standin("ok"))
    real = open

    class Full:
        def write(self, text):
            raise OSError(28, "No space left on device")

        def flush(self):
            pass

        def close(self):
            pass

    def full_open(path, mode="r", *a, **k):
        return Full() if str(path).endswith(".log") and mode == "a" else real(path, mode, *a, **k)

    monkeypatch.setattr("builtins.open", full_open)
    job = jobs.start(upload(tmp_path), {})
    assert wait_state(job) == "done" and job.events[-1]["event"] == "result"


@pytest.mark.parametrize("name", ["Band - Song", "Band - Song [Live]", "[2011 Remaster] x", "a]b[c"])
def test_partial_folders_finds_assembles_staging_whatever_the_name(tmp_path, name):
    import tempfile
    out = tmp_path / name
    staging = Path(tempfile.mkdtemp(prefix=f".{out.name}.", suffix=".partial", dir=tmp_path))   # as assemble names it
    (tmp_path / f".{name}x.y.partial").mkdir()        # another song's
    (tmp_path / f".{name}.y.partial.zip").touch()     # not a staging folder
    assert J.partial_folders(out) == [staging]


def test_the_child_gets_the_environment_and_pythonutf8(tmp_path):
    script = tmp_path / "env.py"
    script.write_text("import json, os, sys\nsys.stderr.write('@@songcharter ' + json.dumps({'event': 'result', "
                      "'ok': True, 'env': {k: os.environ.get(k) for k in ('PYTHONUTF8', 'SONGCHARTER_X')}}) + '\\n')\n")
    jobs = J.Jobs(tmp_path, command=lambda *a: [sys.executable, str(script)], env={**os.environ, "SONGCHARTER_X": "1"})
    job = jobs.start(upload(tmp_path), {})
    assert wait_state(job) == "done" and job.events[-1]["env"] == {"PYTHONUTF8": "1", "SONGCHARTER_X": "1"}
    with open(job.log, encoding="utf-8") as f:
        assert f.readline().startswith(f"songcharter ui job {job.id}: {sys.executable} ")
    assert json.loads(json.dumps(job.snapshot()))["options"]["instruments"] == ["guitar", "bass", "drums"]


def test_the_snapshot_carries_the_time_left_once_the_first_take_is_timed(tmp_path, monkeypatch):
    """M8-04: the snapshot's `remaining` is estimate.remaining of the job's estimate and its events, each stamped with
    `at` as it is read (the take events carry no seconds of their own); None before take 2, and when a bug in it is
    caught (the snapshot still answers)."""
    from songcharter.ui import estimate as E
    est = {"seconds": 412.4, "takes": 4, "device": "cuda", "low_s": 400.0, "high_s": 1400.0, "low_min": 6,
           "high_min": 24}
    job = J.Job("j", dict(UPLOAD), J.ChartOptions(), ["x"], tmp_path / "out", tmp_path / "log", estimate=est)
    job.add({"event": "plan", "stages": ["decode", "guitar", "assemble", "preview"]})
    job.add({"event": "take", "index": 1, "count": 4, "seed": 101})
    assert job.snapshot()["remaining"] is None and job.snapshot(events=False)["remaining"] is None
    job.add({"event": "take", "index": 2, "count": 4, "seed": 202})
    snap = job.snapshot()
    assert all("at" in e for e in snap["events"])
    assert snap["remaining"] == E.remaining(est, snap["events"]) and snap["remaining"]["takes_left"] == 3
    assert snap["remaining"]["from"] == snap["events"][2]["at"]

    def broken(*args):
        raise ZeroDivisionError("a bug in the time left")
    monkeypatch.setattr(E, "remaining", broken)
    assert job.snapshot()["remaining"] is None and job.snapshot()["state"] == "running"


# ------------------------------------------------------------------------------------------------ the queue (M8-10)

# a queued song's chart: its mode is the song's title option ("ok", "check", "dies", "hang"); every run appends
# "start <time>" and "end <time>" to the record file, so two runs at once would overlap
QUEUED = r'''
import json, os, sys, time
out, record = sys.argv[1], sys.argv[2]
mode = next((a[len("--title="):] for a in sys.argv if a.startswith("--title=")), "ok")

def ev(**e):
    sys.stderr.write("@@songcharter " + json.dumps(e) + "\n")
    sys.stderr.flush()

def mark(what):
    with open(record, "a") as f:
        f.write(f"{what} {time.time():.6f} {mode}\n")

mark("start")
ev(event="plan", stages=["decode", "guitar"])
time.sleep(0.3)
if mode == "hang":
    ev(event="take", index=1, count=1, seed=1, pids=[os.getpid()])
    time.sleep(60)
if mode == "linger":   # the result out, then a few seconds of exiting
    mark("end")
    ev(event="result", ok=True, exit=0, folder=out, work="/w", preview=None, summary="gate")
    time.sleep(3)
    sys.exit(0)
if mode == "killed":   # the kernel's out-of-memory killer, say
    mark("end")
    os.kill(os.getpid(), 9)
if mode == "silent":   # exit 3 with no error event
    mark("end")
    sys.exit(3)
if mode == "dies":
    mark("end")
    ev(event="error", kind="tool", message="out of memory, say\nthe rest of it")
    sys.exit(2)
mark("end")
ev(event="result", ok=mode != "check", exit=0 if mode != "check" else 1, folder=out + (".failed" if mode == "check"
   else ""), work="/w", preview=None, summary="gate")
sys.exit(0 if mode != "check" else 1)
'''


@pytest.fixture
def queued(tmp_path):
    """A Queue over Jobs that run QUEUED, its songs' uploads made up; `add(mode)` adds one with that mode."""
    script = tmp_path / "queued.py"
    script.write_text(QUEUED, encoding="utf-8")
    record = tmp_path / "record.txt"
    home = tmp_path / "home"
    lines, disk = [], {"low": None}

    def command(song, out, options, threads):
        return [sys.executable, str(script), str(out), str(record), f"--title={options.metadata.get('title', 'ok')}"]

    def prepare(entry):
        if entry["upload"]["id"] == "gone000000000000":
            raise InputError("Gone.mp3 is not there any more: drop it again")
        return {**upload(tmp_path), "id": entry["upload"]["id"]}, J.parse_options(entry["options"]), "cpu"

    def make():
        jobs = J.Jobs(home, command=command, log=lines.append)
        return J.Queue(jobs, home, prepare=prepare, disk_low=lambda: disk["low"], log=lines.append)

    ctx = SimpleNamespace(home=home, record=record, lines=lines, disk=disk, make=make, queue=make())

    def add(mode, est=None, lyrics=None, uid=None):
        up = {"id": uid or f"{len(ctx.queue.entries):016x}", "name": f"{mode}.mp3", "seconds": 60}
        return ctx.queue.add(up, {"title": mode}, est, lyrics=lyrics)

    ctx.add = add
    yield ctx
    ctx.queue.shutdown()


def settled(queue, timeout=30.0):
    """Wait until nothing charts and nothing that may start waits."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = queue.snapshot()
        states = [e["state"] for e in snap["entries"]]
        if "charting" not in states and ("waiting" not in states or snap["paused"]):
            return snap
        time.sleep(0.05)
    raise AssertionError(f"the queue did not settle: {queue.snapshot()}")


def runs(record: Path) -> list[tuple[float, float, str]]:
    starts, out = {}, []
    for line in record.read_text().splitlines():
        what, at, mode = line.split()
        if what == "start":
            starts.setdefault(mode, []).append(float(at))
        else:
            out.append((starts[mode].pop(0), float(at), mode))
    return sorted(out)


def test_two_charts_never_run_at_once_and_each_starts_when_the_last_ends(queued):
    """M8-10: songs added while one charts wait, and the server starts each in turn when the last ends (no page
    asks); a stand-in child records its start and end: the runs never overlap, in the order added."""
    entry, job = queued.add("ok")
    assert job is not None and entry["state"] == "charting" and entry["job"] == job.id
    for mode in ("ok", "check", "ok"):
        entry, job = queued.add(mode)
        assert job is None
    snap = settled(queued.queue)
    assert [e["state"] for e in snap["entries"]] == ["ready", "ready", "check_failed", "ready"]
    assert len({e["job"] for e in snap["entries"]}) == 4
    spans = runs(queued.record)
    assert [m for _, _, m in spans] == ["ok", "ok", "check", "ok"]
    for (_, end, _), (start, _, _) in zip(spans, spans[1:]):
        assert end <= start, spans   # the next starts after the last has ended
    assert snap["entries"][2]["chart"] == "Ann_Bo - check"   # the folder's name, without .failed
    assert snap["left"] is None and snap["paused"] is None and snap["run"] == 1


def test_two_songs_in_a_row_that_do_not_finish_pause_the_queue(queued):
    """A failed check is a finished chart; two songs in a row that do not finish (exit 2, or one that cannot start)
    pause the queue with the rest waiting; Carry on goes on."""
    queued.add("hang")
    for mode in ("dies", "check", "dies"):
        queued.add(mode)
    queued.add("ok", uid="gone000000000000")   # cannot start: its file is gone
    queued.add("ok")
    queued.add("dies")
    assert queued.queue.snapshot()["entries"][0]["state"] == "charting"
    queued.queue.jobs.cancel()
    snap = settled(queued.queue)
    assert [e["state"] for e in snap["entries"]] == ["cancelled", "not_finished", "check_failed", "not_finished",
                                                     "not_finished", "waiting", "waiting"]
    assert snap["paused"] == "failures" and snap["entries"][1]["error"] == "out of memory, say"
    assert snap["entries"][4]["error"] == "Gone.mp3 is not there any more: drop it again"
    queued.queue.carry_on()
    snap = settled(queued.queue)
    assert [e["state"] for e in snap["entries"][5:]] == ["ready", "not_finished"]
    assert snap["paused"] is None   # nothing waits: nothing to pause


def test_pause_after_this_song_remove_and_the_disk(queued):
    """Pause after this song: the charting one finishes and none starts; Remove takes a waiting song out (not the
    charting one); the disk under MIN_FREE before a song pauses with why; Carry on goes on."""
    first, _ = queued.add("hang")
    second, _ = queued.add("ok")
    third, _ = queued.add("ok")
    queued.queue.pause()
    with pytest.raises(J.NotInQueue):
        queued.queue.remove(first["id"])
    with pytest.raises(J.NotInQueue):
        queued.queue.remove("nope")
    queued.queue.remove(third["id"])
    queued.queue.jobs.cancel()
    snap = settled(queued.queue)
    assert [e["state"] for e in snap["entries"]] == ["cancelled", "waiting"] and snap["paused"] == "you"
    queued.disk["low"] = "C: is nearly full"
    queued.queue.carry_on()
    snap = settled(queued.queue)
    assert snap["paused"] == "disk" and snap["why"] == "C: is nearly full" and snap["entries"][1]["state"] == "waiting"
    queued.disk["low"] = None
    queued.queue.carry_on()
    assert [e["state"] for e in settled(queued.queue)["entries"]] == ["cancelled", "ready"]
    with pytest.raises(J.NotInQueue):
        queued.queue.pause()   # none waits


def test_a_waiting_song_keeps_its_stems_and_audio_options(queued):
    """M8-12: the options are per song: queue.json keeps `stems` and `one_audio` for a waiting song, and its job
    gets them as flags when it starts (break: the queue dropping an option it keeps for no other song)."""
    queued.add("hang")
    up = {"id": "00000000000000aa", "name": "ok.mp3", "seconds": 60}
    entry, job = queued.queue.add(up, {"title": "ok", "stems": True, "one_audio": True}, None)
    assert job is None
    kept = json.loads(J.queue_path(queued.home).read_text(encoding="utf-8"))
    saved = next(e for e in kept["entries"] if e["id"] == entry["id"])
    assert saved["options"]["stems"] is True and saved["options"]["one_audio"] is True
    opts = J.parse_options(saved["options"])   # what `prepare` gives the job when the song starts
    cmd = J.chart_command(Path("/s.mp3"), Path("/o"), opts, None)
    assert opts.stems and opts.one_audio and "--stems" in cmd and "--one-audio" in cmd


def test_lyrics_only_for_a_song_that_starts_at_once_and_the_lists_limit(queued, monkeypatch):
    queued.add("hang", lyrics="zorp quiv")   # starts at once: its lyrics go to the chart as before
    with pytest.raises(InputError, match="Lyrics only for a song that starts at once"):
        queued.add("ok", lyrics="zorp quiv")
    monkeypatch.setattr(J, "QUEUE_MAX", 2)
    queued.add("ok")
    queued.add("ok")
    with pytest.raises(J.QueueFull):
        queued.add("ok")
    assert len(queued.queue.entries) == 3
    assert "zorp" not in J.queue_path(queued.home).read_text(encoding="utf-8")


def test_a_restart_keeps_the_list_paused_until_carry_on(queued):
    """queue.json survives the server: the song that was charting goes back to waiting at the top, and the queue is
    paused ("3 songs were waiting") until Carry on; a finished song is kept by its job id (results, Look) after the
    restart too; Clear the list empties it."""
    done, _ = queued.add("ok")
    settled(queued.queue)
    queued.add("hang")
    queued.add("ok")
    queued.add("check")
    deadline = time.monotonic() + 20
    while not any(e["event"] == "take" for e in queued.queue.jobs.current.events):
        assert time.monotonic() < deadline
        time.sleep(0.02)
    queued.queue.shutdown()   # the window closes: the tree killed, the song back to waiting
    data = json.loads(J.queue_path(queued.home).read_text(encoding="utf-8"))
    assert [e["state"] for e in data["entries"]] == ["ready", "waiting", "waiting", "waiting"]
    queued.queue = queued.make()
    snap = queued.queue.snapshot()
    assert snap["paused"] == "restart" and snap["restarted"] == 3
    assert [e["state"] for e in snap["entries"]] == ["ready", "waiting", "waiting", "waiting"]
    job_id = snap["entries"][0]["job"]
    kept = queued.queue.job(job_id)
    assert kept.result()["ok"] is True and kept.snapshot()["events"][0]["event"] == "result"
    assert queued.queue.job("20000101-000000") is None
    time.sleep(0.5)
    assert queued.queue.jobs.current is None   # nothing starts by itself
    queued.queue.entries[1]["options"] = {"title": "ok"}   # the hang, charted this time
    queued.queue.carry_on()
    snap = settled(queued.queue)
    assert [e["state"] for e in snap["entries"]] == ["ready", "ready", "ready", "check_failed"]
    queued.queue.clear()
    assert queued.queue.snapshot()["entries"] == [] and J.queued_uploads(queued.home) == set()


def test_a_broken_queue_json_starts_an_empty_list(queued):
    path = J.queue_path(queued.home)
    path.parent.mkdir(parents=True, exist_ok=True)
    for text in ("{not json", "[]", json.dumps({"entries": [{"id": 1}, "x"]})):
        path.write_text(text, encoding="utf-8")
        q = queued.make()
        assert q.entries == [] and q.paused is None


def test_a_crash_leaves_the_charting_song_waiting(queued):
    """A server killed outright (no shutdown) leaves "charting" in queue.json: read back, the song waits at the top,
    and the queue is paused."""
    path = J.queue_path(queued.home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"run": 4, "entries": [
        {"id": "e1", "run": 4, "state": "charting", "job": "20000101-000000", "upload": {"id": "a" * 16},
         "options": {}}, {"id": "e2", "run": 4, "state": "waiting", "upload": {"id": "b" * 16}, "options": {}}]}))
    q = queued.make()
    assert [(e["state"], e.get("job")) for e in q.entries] == [("waiting", None), ("waiting", None)]
    assert q.paused == "restart" and q.restarted == 2 and q.run == 4


def test_the_whole_queues_time_left(queued):
    """The waiting songs' ranges summed, with the charting song's range less the time it has run (at least 0);
    None with a song that has no estimate."""
    est = {"seconds": 60, "takes": 1, "device": "cpu", "low_s": 100.0, "high_s": 300.0, "low_min": 2, "high_min": 5}
    queued.add("hang", est)
    queued.add("ok", est)
    queued.add("ok", {**est, "low_s": 50.0, "high_s": 60.0})
    time.sleep(3)
    left = queued.queue.snapshot()["left"]
    ran = time.time() - queued.queue.jobs.current.started
    assert left["songs"] == 3 and abs(left["high_s"] - (360 + 300 - ran)) <= 1 and abs(left["low_s"] - (250 - ran)) <= 1
    queued.add("ok")
    assert queued.queue.snapshot()["left"] is None


def test_the_queues_uploads_are_kept_past_the_weeks_pruning(tmp_path):
    from songcharter.ui import server as S
    home = tmp_path
    for name in ("a" * 16, "b" * 16, "c" * 16, "d" * 16):
        (home / "uploads" / name).mkdir(parents=True)
        (home / "uploads" / name / "x").touch()
        os.utime(home / "uploads" / name / "x", (1, 1))
        os.utime(home / "uploads" / name, (1, 1))
    J.queue_path(home).parent.mkdir(parents=True)
    J.queue_path(home).write_text(json.dumps({"entries": [
        {"id": "e1", "run": 1, "state": "waiting", "upload": {"id": "a" * 16}, "options": {"album_art": "b" * 16}},
        {"id": "e2", "run": 1, "state": "ready", "upload": {"id": "c" * 16}, "options": {}},
        {"id": "e3", "run": 1, "state": "charting", "upload": {"id": "e" * 16}, "options": {}}]}), encoding="utf-8")
    assert J.queued_uploads(home) == {"a" * 16, "b" * 16, "e" * 16}   # a crash's charting song: restarted first
    assert sorted(S.prune_uploads(home, keep=J.queued_uploads(home))) == ["c" * 16, "d" * 16]


# ------------------------------------------------------------------------------------------------ M8-10's review

def test_a_cancel_naming_a_song_that_has_ended_never_reaches_the_next(queued):
    """S-S1: A ends and the queue starts B; a Cancel the page sent for A (its dialog open across A's end) answers
    NotRunning and leaves B charting; one naming B cancels it."""
    a, _ = queued.add("ok")
    b, _ = queued.add("hang")
    deadline = time.monotonic() + 20
    while queued.queue.snapshot()["entries"][1]["state"] != "charting":
        assert time.monotonic() < deadline
        time.sleep(0.05)
    first = queued.queue.snapshot()["entries"][0]["job"]
    with pytest.raises(J.NotRunning):
        queued.queue.jobs.cancel(first)
    snap = queued.queue.snapshot()
    assert [e["state"] for e in snap["entries"]] == ["ready", "charting"]
    assert queued.queue.jobs.cancel(snap["entries"][1]["job"]).state == "cancelled"


def test_a_song_whose_result_was_out_when_the_window_closed_is_not_charted_twice(queued):
    """S-S3: the window closes while a chart's process is exiting, its result out: the song is recorded as charted
    (ready), not put back to waiting to be charted again after the restart."""
    queued.add("linger")
    deadline = time.monotonic() + 20
    while not any(e["event"] == "result" for e in queued.queue.jobs.current.events):
        assert time.monotonic() < deadline
        time.sleep(0.02)
    queued.queue.shutdown()
    data = json.loads(J.queue_path(queued.home).read_text(encoding="utf-8"))
    assert [e["state"] for e in data["entries"]] == ["ready"]
    assert queued.make().paused is None


def test_a_killed_or_silent_song_says_why_in_plain_words(queued):
    """P-F4: the list's reason for a song the system killed, or one that exited with no error, is plain words, not
    "the chart exited 3:"; the Done screen keeps the whole message."""
    queued.add("killed")
    queued.add("silent")
    snap = settled(queued.queue)
    assert [e["error"] for e in snap["entries"]] == [J.PLAIN_MEMORY, J.PLAIN_SILENT]
    assert queued.queue.job(snap["entries"][0]["job"]).snapshot()["events"][0]["message"].startswith(
        "the chart was stopped by SIGKILL")


def test_a_restart_says_a_songs_pasted_lyrics_were_not_kept(queued):
    """S-S2: a song that started at once with lyrics and went back to waiting when the window closed keeps a flag
    that it had some (never the text), and the list says they were lost."""
    queued.add("hang", lyrics="zorp quiv")
    deadline = time.monotonic() + 20
    while not any(e["event"] == "take" for e in queued.queue.jobs.current.events):
        assert time.monotonic() < deadline
        time.sleep(0.02)
    queued.queue.shutdown()
    text = J.queue_path(queued.home).read_text(encoding="utf-8")
    assert "zorp" not in text and json.loads(text)["entries"][0]["lyrics"] is True
    snap = queued.make().snapshot()
    assert snap["entries"][0]["state"] == "waiting" and snap["entries"][0]["lyrics_lost"] is True


def test_the_full_lists_words(queued, monkeypatch):
    monkeypatch.setattr(J, "QUEUE_MAX", 1)
    queued.add("hang")
    queued.add("ok")
    with pytest.raises(J.QueueFull, match="^1 song is waiting already: add more once some are charted$"):
        queued.add("ok")


# ------------------------------------------------------------------------------------------------ the v0.5.0 review

def take_started(queue, timeout=20.0):
    deadline = time.monotonic() + timeout
    while not any(e["event"] == "take" for e in queue.jobs.current.events):
        assert time.monotonic() < deadline
        time.sleep(0.02)


def test_a_song_already_waiting_or_charting_is_refused_and_a_finished_one_may_be_charted_again(queued):
    """install-01: the same upload added again while it charts, while it waits, or while it waits after a restart (the
    window closed mid-chart, its song back at the top of the list, paused) is refused in plain words, and nothing is
    added; once it has finished it may be charted again, as before (break: no check in Queue.add: the song is charted
    twice, into the same library folder)."""
    up = {"id": "00000000000000aa", "name": "hang.mp3", "seconds": 60}
    other = {"id": "00000000000000bb", "name": "ok.mp3", "seconds": 60}
    assert queued.queue.add(up, {"title": "hang"})[1] is not None
    with pytest.raises(InputError, match=r"^This song is already in the list: it is charting now\.$"):
        queued.queue.add(up, {"title": "ok"})
    queued.queue.add(other, {"title": "ok"})
    with pytest.raises(InputError, match=r"^This song is already in the list: it is charted in its turn\.$"):
        queued.queue.add(other, {"title": "ok"})
    assert [e["state"] for e in queued.queue.entries] == ["charting", "waiting"]
    take_started(queued.queue)
    queued.queue.shutdown()   # the window closes mid-chart
    queued.queue = queued.make()   # started again: the song waits at the top, the list paused
    assert queued.queue.snapshot()["paused"] == "restart"
    with pytest.raises(InputError, match=r"^This song is already in the list: press Carry on to chart it\.$"):
        queued.queue.add(up, {"title": "ok"})
    assert len(queued.queue.entries) == 2
    queued.queue.entries[0]["options"] = {"title": "ok"}   # charted this time
    queued.queue.carry_on()
    assert [e["state"] for e in settled(queued.queue)["entries"]] == ["ready", "ready"]
    entry, job = queued.queue.add(up, {"title": "ok"})   # finished: it may be charted again
    assert job is not None and entry["state"] == "charting"
    assert [e["state"] for e in settled(queued.queue)["entries"]] == ["ready", "ready", "ready"]


def test_a_new_evening_and_a_cancel_reset_the_failures_and_the_list_keeps_the_last_finished(queued, monkeypatch):
    """tests-4: a song added to an idle list starts a new evening, whose failures count from 0 (break: Queue.add not
    resetting them: the next evening pauses after its first failure); a cancel ends a run of failures too (break: the
    cancelled branch not resetting them: dies, a cancel, dies pauses); the list keeps the last KEEP_FINISHED finished
    songs (break: _trim emptied: queue.json grows for ever), and a trimmed song's job id still finds its chart
    (correct-1: Queue.dropped_chart)."""
    queued.add("dies")
    assert settled(queued.queue)["entries"][0]["state"] == "not_finished" and queued.queue.failures == 1
    queued.add("dies")   # a new evening: its first failure, not its second
    queued.add("ok")
    snap = settled(queued.queue)
    assert [(e["run"], e["state"]) for e in snap["entries"]] == [(1, "not_finished"), (2, "not_finished"),
                                                                 (2, "ready")]
    assert snap["paused"] is None
    queued.add("dies")
    queued.add("hang")
    queued.add("dies")
    queued.add("ok")
    deadline = time.monotonic() + 20
    while queued.queue.snapshot()["entries"][4]["state"] != "charting":
        assert time.monotonic() < deadline
        time.sleep(0.02)
    take_started(queued.queue)
    queued.queue.jobs.cancel()   # dies, cancelled, dies: not two in a row
    snap = settled(queued.queue)
    assert [e["state"] for e in snap["entries"][3:]] == ["not_finished", "cancelled", "not_finished", "ready"]
    assert snap["paused"] is None
    monkeypatch.setattr(J, "KEEP_FINISHED", 3)
    first = next(e for e in queued.queue.entries if e["id"] == snap["entries"][2]["id"])   # ready: it made a chart
    queued.add("ok")   # 7 finished: the 4 oldest go
    snap = settled(queued.queue)
    assert len(snap["entries"]) == 4 and first["id"] not in {e["id"] for e in snap["entries"]}
    kept = json.loads(J.queue_path(queued.home).read_text(encoding="utf-8"))["entries"]
    assert [e["id"] for e in kept] == [e["id"] for e in snap["entries"]]
    assert queued.queue.job(first["job"]) is None
    assert queued.queue.dropped_chart(first["job"]) == J.chart_id(Path(first["closing"]["folder"]))


def test_stop_orphan_stops_only_the_chart_its_file_names(tmp_path):
    """A second advisor's finding 7, the pid file's own rules: a process group whose leader is the process chart.pid
    names (the same start time) is stopped, its members too; a pid whose start time differs (used again since: here
    another process in a session of its own) is never touched; a damaged or missing file stops nothing; the file goes
    either way (break: the start time not compared: the other process is stopped)."""
    if not Path("/proc/self/stat").exists():
        pytest.skip("needs /proc (Linux)")
    leader = subprocess.Popen(["sh", "-c", "sleep 60 & sleep 60"], start_new_session=True)
    other = subprocess.Popen(["sleep", "60"], start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while J.proc_start(leader.pid) is None:
            assert time.monotonic() < deadline
            time.sleep(0.02)
        path = J.pid_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"pid": other.pid, "start": "1", "job": "x"}), encoding="utf-8")
        assert J.stop_orphan(tmp_path, timeout=1) is None and not path.exists()   # another process: untouched
        assert other.poll() is None and proc.alive(other.pid)
        for text in ("{not json", "[]", json.dumps({"pid": True, "start": "1"}), json.dumps({"pid": 1, "start": "1"})):
            path.write_text(text, encoding="utf-8")
            assert J.stop_orphan(tmp_path) is None and not path.exists(), text
        assert J.stop_orphan(tmp_path) is None   # no file
        # its server alive (this process, with its start time): not an orphan, and its file kept (the v0.5.0
        # re-review's R1; break: the server not checked, so a live songcharter's chart is stopped)
        alive = {"pid": leader.pid, "start": J.proc_start(leader.pid), "job": "20000101-000000",
                 "server": os.getpid(), "server_start": J.proc_start(os.getpid())}
        path.write_text(json.dumps(alive), encoding="utf-8")
        assert J.stop_orphan(tmp_path, timeout=1) is None and path.exists() and proc.group_alive(leader.pid)
        said = []
        path.write_text(json.dumps({**alive, "server_start": "1"}), encoding="utf-8")   # its server gone
        assert J.stop_orphan(tmp_path, said.append, timeout=2) == leader.pid
        leader.wait(5)
        assert not proc.group_alive(leader.pid) and not path.exists()
        assert said and "job 20000101-000000" in said[0]
    finally:
        for p in (leader, other):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait(5)


def test_a_jobs_pid_file_lives_while_its_chart_runs(queued):
    """chart.pid names the running chart (its pid and start time) from its start to its end, cancelled or not."""
    queued.add("hang")
    take_started(queued.queue)
    job = queued.queue.jobs.current
    record = json.loads(J.pid_path(queued.home).read_text(encoding="utf-8"))
    assert record == {"pid": job.tree.pid, "start": J.proc_start(job.tree.pid), "job": job.id, "server": os.getpid(),
                      "server_start": J.proc_start(os.getpid())}
    queued.queue.jobs.cancel()
    assert not J.pid_path(queued.home).exists()
    queued.add("ok")
    settled(queued.queue)
    deadline = time.monotonic() + 10
    while J.pid_path(queued.home).exists():   # the reader thread removes it as the chart exits
        assert time.monotonic() < deadline
        time.sleep(0.02)
