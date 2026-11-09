"""eval/spike/thin_spike.sh (M6's spike on the engine thinning fast runs) and eval/gpu.sh thin-spike, on eval/tools or
the installed app (--app). The real driver, ac_headless.cjs, copied as the install copies it and patched as the spike
patches it, runs a made-up engine (a few lines of Node that answer the job as the real engine does), under a made-up
home: no model, no audio, no GPU. The zip must hold charts and summaries only, with no path, user name or audio."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from songcharter import runtime as R
from test_eval_takes import cli_app, wav

ROOT = Path(__file__).resolve().parent.parent
GPU = ROOT / "eval" / "gpu.sh"
SPIKE = ROOT / "eval" / "spike" / "thin_spike.sh"
DRIVER = ROOT / "eval" / "tools" / "autochart" / "ac_headless.cjs"
NODE = shutil.which("node")
USER = "madeupuser"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None or NODE is None or sys.platform == "win32",
                                reason="the spike needs bash and Node")

# answers the job ac_headless.cjs writes as the real engine does (result.json, the chart and its report), and records
# the settings the job carries; FAKE_DEVICE is the transcriber's device it reports, FAKE_CHART_HEAD a first chart line
ENGINE = r"""
const fs = require("fs"), path = require("path");
const job = JSON.parse(fs.readFileSync(process.argv[process.argv.indexOf("--job") + 1], "utf8"));
const r = job.generation.resolved, out = job.outputDir, device = process.env.FAKE_DEVICE || job.transcriberDevice;
fs.appendFileSync(process.env.FAKE_ENGINE_LOG, JSON.stringify({seed: r.seed, temperature: r.temperature,
  knobs: r.knobs, knobsActive: r.knobsActive, device: job.transcriberDevice,
  ffmpeg: process.env.AUTOCHART_FFMPEG_PATH || null}) + "\n");
fs.mkdirSync(path.join(out, "chart"), {recursive: true});
const chart = path.join(out, "chart", "notes.chart");
fs.writeFileSync(chart, (process.env.FAKE_CHART_HEAD || "") +
  `[Song]\n{\n  Name = "${job.title}"\n  Resolution = 192\n}\n[SyncTrack]\n{\n  0 = B 120000\n}\n` +
  `[ExpertSingle]\n{\n  0 = N 0 0\n  192 = N ${r.seed % 5} 0\n}\n`);
fs.writeFileSync(path.join(out, "chart", "full_song_report.json"), JSON.stringify({note_line_count: 2,
  token_stats: {n_tokens: 9, n_beats: 4, generation_seconds: 0.1}, timing: {tempoBpm: 120, audioDuration: 2}}));
fs.writeFileSync(path.join(out, "result.json"), JSON.stringify({status: "completed", chartPath: chart,
  provenance: {runtime: {devices: {transcriber: device}, cachedStages: []}}}));
console.log(JSON.stringify({type: "stage", stage: "transcription", status: "completed", device}));
"""
KNOBS = ["speed", "chords", "hopos", "taps", "movement"]


def spike_install(root: Path) -> Path:
    """An autochart install as the app's setup makes it (runtime.DRIVER_FILES copied from eval/tools/autochart), with
    the made-up engine in place of the real one and no models."""
    for d in ("src/engine/bin", "models/fretformer-v2", "node_modules/onnxruntime-node"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for name in R.DRIVER_FILES:
        shutil.copyfile(DRIVER.parent / name, root / name)
    manifest = {"engineVersion": "made-up", "generators": [{"id": "autochart.fretformer.v2-onnx", "label": "Made Up",
                "models": {"onnxFolder": "fretformer-v2"}, "capabilities": {"descriptorKnobs": KNOBS}}]}
    (root / "src" / "engine" / "manifest.json").write_text(json.dumps(manifest))
    (root / "src" / "engine" / "bin" / "autochart-engine.cjs").write_text(ENGINE)
    (root / "models" / "fretformer-v2" / "manifest.json").write_text("{}")
    return root


def stub(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return path


def fake_ffmpeg(path: Path, log: Path) -> Path:
    """ffmpeg as the driver runs it for song.ogg: an Ogg header into its last argument."""
    return stub(path, f"echo \"$*\" >> '{log}'\nfor a; do last=$a; done\nprintf 'OggS made up' > \"$last\"\n")


def engine_log(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def members(zpath: Path) -> dict[str, str]:
    with zipfile.ZipFile(zpath) as z:
        return {n: z.read(n).decode() for n in z.namelist()}


@pytest.fixture
def spike(tmp_path):
    """thin_spike.sh run directly (eval/tools' way): a made-up home holding the song, the install and OUT."""
    home = tmp_path / "home"
    inst = spike_install(home / "ac")
    song = home / "Music" / "made up song.wav"
    wav(song, 1)
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_CPU", "AC_DEVICE", "FFMPEG", "PYTHONPATH")}
    env.update(HOME=str(home), USER=USER, SONGCHARTER_AUTOCHART=str(inst), EVAL_PY=sys.executable,
               SPIKE_OUT=str(home / "out"), FAKE_ENGINE_LOG=str(tmp_path / "engine.jsonl"), ARMS="base:T=0.95",
               SEEDS="7", AUTOCHART_FFMPEG_PATH=str(fake_ffmpeg(tmp_path / "bin" / "ffmpeg", tmp_path / "ff.txt")))

    def run(*audio, **more):
        return subprocess.run(["bash", str(SPIKE), *map(str, audio or [song])], env={**env, **more},
                              capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    run.home, run.inst, run.song, run.out, run.tmp = home, inst, song, home / "out", tmp_path
    return run


# --------------------------------------------------------------------------------------- gpu.sh thin-spike --app

def app_spike(tmp_path: Path, lane="cu132"):
    """`eval/gpu.sh thin-spike --app` on a made-up PC (test_eval_takes.cli_app): the app's autochart is the spike's
    install, somewhere runtime.json names (not the default runtime/autochart), its Node a wrapper of the real one that
    logs each call, its ffmpeg the stand-in; the song in ~/Music."""
    env, home, data = cli_app(tmp_path, lane=lane)
    app = home / ".local" / "share" / "songcharter"
    inst = spike_install(tmp_path / "h" / "elsewhere" / "autochart")
    d = inst / "node_modules" / "onnxruntime-node" / "bin"
    d.mkdir(parents=True)
    (d / "libonnxruntime_providers_cuda.so").write_bytes(b"made up")
    node = stub(app / "runtime" / "node" / "bin" / "node",
                f"echo \"$*\" >> '{tmp_path / 'node.txt'}'\nexec '{NODE}' \"$@\"\n")
    ffmpeg = fake_ffmpeg(app / "runtime" / "ffmpeg", tmp_path / "ff.txt")
    record = json.loads((app / "runtime" / "runtime.json").read_text())
    record.update(autochart=str(inst), node=str(node), ffmpeg=str(ffmpeg))
    (app / "runtime" / "runtime.json").write_text(json.dumps(record))
    song = home / "Music" / "made up song.wav"
    wav(song, 1)
    env = {k: v for k, v in env.items() if k not in ("ARMS", "SEEDS", "AC_DEVICE", "FFMPEG", "SONGCHARTER_AUTOCHART")}
    env.update(USER=USER, ARMS="base:T=0.95 dense5:speed=5", SEEDS="7", FAKE_ENGINE_LOG=str(tmp_path / "engine.jsonl"))
    return env, home, data, inst, song


def gpu(args, env):
    return subprocess.run(["bash", str(GPU), *map(str, args)], env=env, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=300)


def finished(data: Path, timeout=120) -> str:
    """gpu_run.log once the detached run has ended."""
    log, end = data / "runs" / "gpu_run.log", time.time() + timeout
    while time.time() < end:
        text = log.read_text() if log.exists() else ""
        if "thin spike finished" in text and not (data / "runs" / "gpu_run.pid").exists():
            return text
        time.sleep(0.2)
    raise AssertionError(f"the thin spike did not finish in {timeout} s: {log.read_text() if log.exists() else ''}")


def test_app_spike_runs_the_apps_autochart_node_and_ffmpeg_and_zips_no_path(tmp_path):
    env, home, data, inst, song = app_spike(tmp_path)
    ref = data / "refs" / "aaa" / "input.wav"   # a built reference's input: its takes go under its id
    p = gpu(["thin-spike", "--app", ref, song], env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "check: ok" in p.stdout and "started (pid" in p.stdout and str(home) not in p.stdout + p.stderr
    log = finished(data)
    assert "thin spike started (2 files, the installed app)" in log and "thin spike finished (exit 0)" in log, log
    # the app's Node ran the patched driver, which ran the app's autochart with the app's ffmpeg
    assert any("ac_knobs.cjs --audio" in c for c in (tmp_path / "node.txt").read_text().splitlines())
    jobs = engine_log(tmp_path / "engine.jsonl")
    assert [(j["knobs"]["speed"], j["knobsActive"], j["temperature"]) for j in jobs] == [(None, False, 0.95),
                                                                                        (5, True, 0.95)] * 2
    assert all(j["device"] == "cuda" and j["ffmpeg"] == str(home / ".local/share/songcharter/runtime/ffmpeg")
               for j in jobs)
    out = data / "runs" / "thin_spike"
    raw = (out / "song" / "base" / "seed_7" / "autochart_run" / "summary.json").read_text()
    assert str(home) in raw   # the driver's summary holds the song's, the work folder's and ffmpeg's paths
    got = members(out / "thin_spike_results.zip")
    assert sorted(got) == sorted(f"{label}/{arm}/seed_7/{f}" for label in ("aaa", "song") for arm in ("base", "dense5")
                                 for f in ("notes.chart", "autochart_run/summary.json"))
    for name, text in got.items():   # a summary keeps no path at all; nothing holds the home folder or user name
        assert "/" not in text or name.endswith("notes.chart"), name
        assert str(home) not in text and USER not in text, name
    s = json.loads(got["song/dense5/seed_7/autochart_run/summary.json"])
    assert s["knobs"] == {"speed": 5, "chords": None, "hopos": None, "taps": None, "movement": None}
    assert s["knobsActive"] is True and s["temperature"] == 0.95 and s["runs"][0]["devices"] == {"transcriber": "cuda"}
    assert s["inputSha256"] == hashlib.sha256(song.read_bytes()).hexdigest() and not {"input", "ffmpeg"} & set(s)
    assert "jobDir" not in s["runs"][0] and "check_no_audio: ok" in (out / "thin_spike.log").read_text()
    assert not list(out.glob("*/*/seed_*/song.ogg"))
    assert (inst / "ac_headless.cjs").read_bytes() == DRIVER.read_bytes()   # the install's own driver is untouched
    assert str(home) not in (out / "thin_spike.log").read_text()


@pytest.mark.parametrize("change, code, why", [
    ({"lane": "cu126"}, 1, "problem: the app is on the cu126 lane"),
    ({"no_app": True}, 2, "no installed songcharter at ~/none"),
])
def test_app_spike_refuses_before_anything_detaches(tmp_path, change, code, why):
    env, home, data, _, song = app_spike(tmp_path, lane=change.get("lane", "cu132"))
    if change.get("no_app"):
        env["SONGCHARTER_HOME"] = str(home / "none")
    p = gpu(["thin-spike", "--app", song], env)
    assert p.returncode == code and why in p.stdout, p.stdout + p.stderr
    assert not (data / "runs").exists() and str(home) not in p.stdout + p.stderr


def test_the_spike_without_app_runs_eval_tools_autochart_as_before(tmp_path):
    """_thin, the detached half, without --app: SONGCHARTER_AUTOCHART (eval/tools'), PATH's Node, EVAL_PY."""
    home, data = tmp_path / "home", tmp_path / "data"
    inst = spike_install(tmp_path / "ac")
    song = home / "song.wav"
    wav(song, 3)
    (data / "runs").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if k not in ("ALLOW_CPU", "AC_DEVICE", "SONGCHARTER_APP", "FFMPEG")}
    env.update(HOME=str(home), USER=USER, EVAL_DATA=str(data), SONGCHARTER_AUTOCHART=str(inst), EVAL_PY=sys.executable,
               ARMS="base:T=0.95", SEEDS="7", FAKE_ENGINE_LOG=str(tmp_path / "engine.jsonl"),
               AUTOCHART_FFMPEG_PATH=str(fake_ffmpeg(tmp_path / "ffmpeg", tmp_path / "ff.txt")))
    p = gpu(["_thin", song], env)
    assert p.returncode == 0 and "thin spike finished (exit 0)" in p.stdout, p.stdout + p.stderr
    assert sorted(members(data / "runs" / "thin_spike" / "thin_spike_results.zip")) == [
        "song/base/seed_7/autochart_run/summary.json", "song/base/seed_7/notes.chart"]


# --------------------------------------------------------------------------------------- thin_spike.sh

@pytest.mark.parametrize("edit, found", [
    (lambda s: s.replace("knobsActive: false", "knobsActive: true"), 0),     # a target gone
    (lambda s: s + "// knobsActive: false\n", 2),                             # a target twice
    (lambda s: s.replace("const HERE = __dirname;", "const HERE = __dirname ;"), 0),
])
def test_the_patch_applies_each_target_exactly_once_or_stops(spike, edit, found):
    driver = spike.inst / "ac_headless.cjs"
    driver.write_text(edit(driver.read_text()))
    p = spike()
    assert p.returncode == 2 and f"patch target found {found} times, not once" in p.stderr, p.stdout + p.stderr
    assert not (spike.out / "song").exists() and not (spike.tmp / "engine.jsonl").exists()


def test_the_install_driver_patches_and_records_the_knobs(spike):
    p = spike(ARMS="dense6:speed=6,chords=2 hot:T=1.05")
    assert p.returncode == 0, p.stdout + p.stderr
    assert [(j["knobs"], j["knobsActive"], j["temperature"]) for j in engine_log(spike.tmp / "engine.jsonl")] == [
        ({**dict.fromkeys(KNOBS), "speed": 6, "chords": 2}, True, 0.95), (dict.fromkeys(KNOBS), False, 1.05)]
    s = json.loads((spike.out / "song" / "dense6" / "seed_7" / "autochart_run" / "summary.json").read_text())
    assert s["knobs"]["speed"] == 6 and s["knobsActive"] is True
    assert (spike.inst / "ac_headless.cjs").read_bytes() == DRIVER.read_bytes()
    p = spike()   # another run in the same OUT: its zip holds its own takes, not the ones before
    assert p.returncode == 0 and sorted(members(spike.out / "thin_spike_results.zip")) == [
        "song/base/seed_7/autochart_run/summary.json", "song/base/seed_7/notes.chart"]


@pytest.mark.parametrize("head, kind", [
    ("// {home}/Music\n", "path"),
    ("// made by {user}\n", "user name"),
    ("// /mnt/c/Users/x/Music\n", "path"),
    ("RIFF made up\n", "check_no_audio: FAIL"),
])
def test_the_guard_stops_a_zip_with_a_path_a_user_name_or_audio(spike, head, kind):
    spike(SEEDS="8")   # a zip from before: a stopped run leaves none
    assert (spike.out / "thin_spike_results.zip").exists()
    p = spike(FAKE_CHART_HEAD=head.format(home=spike.home, user=USER.upper()))
    assert p.returncode == 1 and kind in p.stdout, p.stdout + p.stderr
    if kind != "check_no_audio: FAIL":
        assert "song/base/seed_7/notes.chart: " + kind in p.stdout and "the guard stopped it" in p.stdout
    assert not list(spike.out.glob("thin_spike_results.zip*"))
    assert str(spike.home) not in p.stdout + p.stderr + (spike.out / "thin_spike.log").read_text()


@pytest.mark.parametrize("allow", [False, True])
def test_a_take_on_the_cpu_stops_the_spike_unless_allowed(spike, allow):
    p = spike(SEEDS="7 8", FAKE_DEVICE="cpu", **({"ALLOW_CPU": "1"} if allow else {}))
    if allow:
        assert p.returncode == 0 and (spike.out / "thin_spike_results.zip").exists(), p.stdout + p.stderr
    else:
        assert p.returncode == 1 and "the transcriber did not run on cuda; stopping" in p.stdout
        assert len(engine_log(spike.tmp / "engine.jsonl")) == 1 and not (spike.out / "thin_spike_results.zip").exists()


def test_a_take_is_kept_only_for_the_same_input(spike):
    assert spike().returncode == 0
    p = spike()
    assert p.returncode == 0 and "song base seed 7: kept" in p.stdout
    assert len(engine_log(spike.tmp / "engine.jsonl")) == 1
    other = spike.home / "Music" / "another.wav"
    wav(other, 2)
    p = spike(other)   # the same label (song), another input: made again, not kept
    assert p.returncode == 0 and "a take of another input; made again" in p.stdout, p.stdout
    s = json.loads(members(spike.out / "thin_spike_results.zip")["song/base/seed_7/autochart_run/summary.json"])
    assert s["inputSha256"] == hashlib.sha256(other.read_bytes()).hexdigest()
    p = spike(other, spike.song, SEEDS="7,9")   # labels in order: song, song_2; commas in SEEDS
    assert p.returncode == 0, p.stdout + p.stderr
    assert sorted(n for n in members(spike.out / "thin_spike_results.zip") if n.endswith(".chart")) == [
        f"{label}/base/seed_{s}/notes.chart" for label in ("song", "song_2") for s in (7, 9)]
