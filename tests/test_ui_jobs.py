"""The UI's job (songcharter.ui.jobs): the page's options checked and turned into `songcharter chart`'s command line,
the `@@songcharter` lines of the child's stderr read as events, the end states, and cancel. The child is a stand-in
program (STANDIN) that writes what `chart --events` writes; the real command line's events are tested in
test_pipeline.py."""
import json
import os
import sys
import time
from pathlib import Path

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


@pytest.mark.parametrize("raw, message", [
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
    assert snap["upload"] == {"id": UPLOAD["id"], "name": UPLOAD["name"]}
    # a second job may start now; it has a log of its own even within the same second
    second = jobs.start(upload(tmp_path), {})
    assert wait_state(second) == "done" and second.log != job.log and jobs.current is second


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
