"""The autochart engine wrapper (songcharter.engines.autochart) with a stand-in for the driver: the command and its
environment (the CUDA library path for "cuda"), one shared work folder, the take cache and its key (the input, the
seed and the install), failures and the install check. autochart itself never runs."""
import json
import subprocess
import sys

import pytest

from songcharter.engines import autochart as AC
from songcharter.engines.autochart import DEFAULT_SEED, Install, find_install, generate
from songcharter.errors import ToolError

ENGINE_VERSION = "2026.06.16-cross-platform-runtime"


def install(tmp_path):
    root = tmp_path / "ac"
    (root / "src" / "engine" / "bin").mkdir(parents=True)
    (root / "src" / "engine" / "bin" / "autochart-engine.cjs").write_text("//", encoding="utf-8")
    (root / "src" / "engine" / "manifest.json").write_text(json.dumps({"engineVersion": ENGINE_VERSION}),
                                                           encoding="utf-8")
    (root / "src" / "engine" / "catalog.json").write_text('{"components": []}', encoding="utf-8")
    (root / "models" / "fretformer-v2").mkdir(parents=True)
    (root / "models" / "fretformer-v2" / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "node_modules" / "onnxruntime-node").mkdir(parents=True)
    (root / "ac_headless.cjs").write_text("//", encoding="utf-8")
    return root


class FakeDriver:
    """Writes a take the way ac_headless.cjs does, and records every call."""

    def __init__(self, fail_seed=None, transcriber=None):
        self.calls = []
        self.fail_seed = fail_seed
        self.transcriber = transcriber  # the device the engine ends up using, if not the one asked for

    def __call__(self, cmd, env, cwd, capture_output, text, timeout):
        self.calls.append((cmd, env, cwd))
        audio, out = cmd[cmd.index("--audio") + 1], cmd[cmd.index("--out") + 1]
        seed = int(env["AC_SEED"])
        if seed == self.fail_seed:
            return subprocess.CompletedProcess(cmd, 1, "", "[autochart] expert: engine job\nError: model crashed\n")
        from pathlib import Path
        folder = Path(out)
        (folder / "autochart_run").mkdir(parents=True, exist_ok=True)
        (folder / "notes.chart").write_text(f"[Song]\n{{\n}}\n// seed {seed}\n", encoding="utf-8")
        summary = {"inputSha256": AC.sha256(Path(audio)), "seed": seed, "difficulties": ["expert"],
                   "temperature": float(env["AC_TEMPERATURE"]), "topP": float(env["AC_TOP_P"]),
                   "runs": [{"status": "completed",
                             "devices": {"transcriber": self.transcriber or env["AC_DEVICE"]}}]}
        (folder / "autochart_run" / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")


def test_one_take_per_seed_on_a_shared_work_folder(tmp_path):
    inst = find_install(install(tmp_path), node="/usr/bin/node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"RIFF....WAVE")
    drv = FakeDriver()
    takes = generate(inst, audio, tmp_path / "out", (DEFAULT_SEED, 101, 202), device="cuda", ffmpeg="/opt/ffmpeg",
                     title="Song", artist="Band", run=drv)
    assert [t.seed for t in takes] == [DEFAULT_SEED, 101, 202] and not any(t.cached for t in takes)
    assert [t.chart for t in takes] == [tmp_path / "out" / f"seed_{s}" / "notes.chart" for s in (DEFAULT_SEED, 101, 202)]
    works = {c[0][c[0].index("--work") + 1] for c in drv.calls}
    assert works == {str(tmp_path / "out" / "work")}  # the engine's separation and beat map are cached there
    cmd, env, cwd = drv.calls[0]
    assert cmd[:2] == ["/usr/bin/node", str(inst.driver)] and cwd == str(inst.driver.parent)
    assert env["AC_DIFFICULTIES"] == "expert" and env["AC_DEVICE"] == "cuda" and env["AUTOCHART_FFMPEG_PATH"] == "/opt/ffmpeg"
    assert env["AC_APP_ROOT"] == str(inst.app_root) and env["AC_MODELS"] == str(inst.models)
    assert env["AC_TITLE"] == "Song" and env["AC_ARTIST"] == "Band"
    assert env["AUTOCHART_ONNX_TRANSCRIBER_DEVICE"] == "cuda"  # not the engine's WebGPU preference
    assert takes[1].devices == {"transcriber": "cuda"}


def test_a_take_made_on_another_device_is_made_again(tmp_path):
    """The engine falls back by itself (CUDA libraries missing, a WebGPU adapter that runs on the CPU): such a take
    is kept and reported, but the next run on the requested device makes it again."""
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"x")
    drv = FakeDriver(transcriber="webgpu")
    first = generate(inst, audio, tmp_path / "out", (1,), device="cuda", run=drv)
    assert first[0].devices == {"transcriber": "webgpu"} and not first[0].cached
    again = generate(inst, audio, tmp_path / "out", (1,), device="cuda", run=FakeDriver())
    assert not again[0].cached and again[0].devices == {"transcriber": "cuda"}
    assert generate(inst, audio, tmp_path / "out", (1,), device="cuda", run=FakeDriver())[0].cached
    # an override set by the caller wins, and webgpu (or none) is left to the engine
    env_drv = FakeDriver()
    generate(inst, audio, tmp_path / "w", (2,), device="webgpu", run=env_drv)
    assert "AUTOCHART_ONNX_TRANSCRIBER_DEVICE" not in env_drv.calls[0][1] or \
        env_drv.calls[0][1]["AUTOCHART_ONNX_TRANSCRIBER_DEVICE"] == AC.os.environ.get("AUTOCHART_ONNX_TRANSCRIBER_DEVICE")


def test_finished_takes_are_reused_and_a_changed_input_is_not(tmp_path):
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"one")
    drv = FakeDriver()
    generate(inst, audio, tmp_path / "out", (1, 2), run=drv)
    assert len(drv.calls) == 2
    again = generate(inst, audio, tmp_path / "out", (2, 1, 3), run=drv)
    assert [t.cached for t in again] == [True, True, False] and len(drv.calls) == 3 and again[0].seconds == 0.0
    audio.write_bytes(b"two")  # another song (or another decode): every take runs again
    fresh = generate(inst, audio, tmp_path / "out", (1,), run=drv)
    assert not fresh[0].cached and len(drv.calls) == 4
    # a take cut off before its summary was written is not reused
    (tmp_path / "out" / "seed_2" / "autochart_run" / "summary.json").unlink()
    assert AC._done(tmp_path / "out" / "seed_2", AC.take_key(AC.sha256(audio), 2, AC.install_key(inst))) is None


def test_on_take_hears_of_each_take_that_runs_before_it_runs(tmp_path):
    """The UI's "take k of n": (index from 1 among the seeds, their count, the seed), before the driver runs, and
    not for a take the cache answers."""
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"one")
    drv, heard = FakeDriver(), []
    generate(inst, audio, tmp_path / "out", (7,), run=drv)
    generate(inst, audio, tmp_path / "out", (5, 7, 9), run=drv,
             on_take=lambda i, n, seed: heard.append((i, n, seed, len(drv.calls))))
    assert heard == [(1, 3, 5, 1), (3, 3, 9, 2)]   # seed 7 was cached; each heard before its own run
    assert [int(c[1]["AC_SEED"]) for c in drv.calls] == [7, 5, 9]
    generate(inst, audio, tmp_path / "out", (5, 7, 9), run=drv, on_take=lambda *a: pytest.fail(f"cached: {a}"))


def test_a_take_is_keyed_by_the_install_too(tmp_path):
    """A take made by another engine, model set or driver is not reused (a re-run after an update would otherwise
    build from the old engine's notes, or splice takes of two engines), and neither is one without take.json."""
    root = install(tmp_path)
    inst = find_install(root, node="node")
    audio, out = tmp_path / "input.wav", tmp_path / "out"
    audio.write_bytes(b"one")
    drv = FakeDriver()
    generate(inst, audio, out, (1, 2), run=drv)
    made = json.loads((out / "seed_1" / AC.TAKE).read_text(encoding="utf-8"))
    assert made == AC.take_key(AC.sha256(audio), 1, AC.install_key(inst)) and made["engineVersion"] == ENGINE_VERSION
    assert [t.cached for t in generate(inst, audio, out, (1, 2), run=drv)] == [True, True] and len(drv.calls) == 2
    updates = [(root / "src" / "engine" / "manifest.json", json.dumps({"engineVersion": "2027.02.01-new-engine"})),
               (root / "src" / "engine" / "catalog.json", '{"components": [{"id": "fretformer-2-onnx"}]}'),
               (root / "models" / "fretformer-v2" / "manifest.json", '{"revision": "new"}'),
               (root / "node_modules" / "onnxruntime-node" / "package.json", '{"version": "1.99.0"}'),
               (root / "ac_headless.cjs", "// driver B")]
    for path, text in updates:
        path.write_text(text, encoding="utf-8")
        calls = len(drv.calls)
        takes = generate(inst, audio, out, (1, 2, 3), run=drv)  # none mixed in from before the update
        assert [t.cached for t in takes] == [False] * 3 and len(drv.calls) == calls + 3, path
    made = json.loads((out / "seed_3" / AC.TAKE).read_text(encoding="utf-8"))
    assert made["engineVersion"] == "2027.02.01-new-engine"
    (out / "seed_1" / AC.TAKE).unlink()  # a take from before take.json (an older songcharter): run again
    assert [t.cached for t in generate(inst, audio, out, (1, 2), run=drv)] == [False, True]


def test_a_failed_take_raises_with_the_drivers_last_lines(tmp_path):
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"x")
    with pytest.raises(ToolError, match=r"(?s)seed 7 failed \(exit 1\):\n.*model crashed"):
        generate(inst, audio, tmp_path / "out", (6, 7), run=FakeDriver(fail_seed=7))
    assert not (tmp_path / "out" / "seed_7" / AC.TAKE).exists() and (tmp_path / "out" / "seed_6" / AC.TAKE).is_file()

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    with pytest.raises(ToolError, match="seed 8 did not finish within 4200 s"):  # a user-facing error, not a bug
        generate(inst, audio, tmp_path / "out", (8,), timeout_s=3600, run=slow)
    with pytest.raises(ValueError, match="distinct"):
        generate(inst, audio, tmp_path / "out", (6, 6), run=FakeDriver())
    with pytest.raises(ValueError, match="device"):
        generate(inst, audio, tmp_path / "out", (6,), device="tpu", run=FakeDriver())
    with pytest.raises(FileNotFoundError, match="does not exist"):
        generate(inst, tmp_path / "missing.wav", tmp_path / "out", run=FakeDriver())


def test_the_install_check_names_what_is_missing(tmp_path, monkeypatch):
    root = install(tmp_path)
    assert isinstance(find_install(root, node="node"), Install)
    (root / "models" / "fretformer-v2" / "manifest.json").unlink()
    (root / "node_modules" / "onnxruntime-node").rmdir()
    with pytest.raises(FileNotFoundError) as e:
        find_install(root, node="node")
    assert "fetch_models.sh" in str(e.value) and "npm ci" in str(e.value) and "setup.sh" not in str(e.value)
    monkeypatch.setenv("SONGCHARTER_AUTOCHART", str(tmp_path / "nowhere"))
    monkeypatch.setattr(AC.shutil, "which", lambda name: None)
    monkeypatch.delenv("SONGCHARTER_NODE", raising=False)
    with pytest.raises(FileNotFoundError, match="node .install Node.js"):
        find_install()


def fake_nvidia(tmp_path, monkeypatch, wsl: bool = True):
    """A site-packages folder holding the nvidia namespace package's CUDA 13 and cuDNN folders (as the cu132 lane's
    wheels lay them out) first on sys.path, and WSL's driver folder (or none)."""
    site = tmp_path / "site-packages"
    for sub in ("cu13/lib", "cudnn/lib", "cusparselt/lib"):
        (site / "nvidia" / sub).mkdir(parents=True)
    monkeypatch.syspath_prepend(str(site))
    monkeypatch.delitem(sys.modules, "nvidia", raising=False)
    (tmp_path / "wsl-lib").mkdir()
    monkeypatch.setattr(AC, "WSL_LIB", tmp_path / ("wsl-lib" if wsl else "no-wsl-lib"))
    return site / "nvidia"


def test_the_cuda_library_path(tmp_path, monkeypatch):
    """cu13/lib and cudnn/lib of every folder of the nvidia package (ours first, as it is first on sys.path), then
    WSL's driver libraries when that folder exists; no other nvidia folder."""
    nvidia = fake_nvidia(tmp_path, monkeypatch)
    path = AC.cuda_library_path()
    assert path[:2] == [str(nvidia / "cu13" / "lib"), str(nvidia / "cudnn" / "lib")]
    assert path[-1] == str(tmp_path / "wsl-lib") and not any("cusparselt" in p for p in path)
    monkeypatch.setattr(AC, "WSL_LIB", tmp_path / "nowhere")
    assert str(tmp_path / "wsl-lib") not in AC.cuda_library_path()
    monkeypatch.setattr(AC.importlib.util, "find_spec", lambda name: None)  # no nvidia package at all (the cpu lane)
    assert AC.cuda_library_path() == []


def test_the_cuda_take_gets_the_library_path_and_the_cpu_take_does_not(tmp_path, monkeypatch):
    """For "cuda" the driver's LD_LIBRARY_PATH starts with the CUDA 13 folders and keeps what was set; for "cpu" it is
    left as it was. This process's own LD_LIBRARY_PATH never changes, and neither does the take's key."""
    nvidia = fake_nvidia(tmp_path, monkeypatch)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/opt/mine")
    inst = find_install(install(tmp_path), node="node")
    audio = tmp_path / "input.wav"
    audio.write_bytes(b"x")
    drv = FakeDriver()
    generate(inst, audio, tmp_path / "gpu", (1,), device="cuda", run=drv)
    generate(inst, audio, tmp_path / "cpu", (1,), device="cpu", run=drv)
    cuda_env, cpu_env = drv.calls[0][1], drv.calls[1][1]
    folders = AC.cuda_library_path()   # ours, then this Python's own nvidia folders when it has them, then WSL's
    assert folders[:2] == [str(nvidia / "cu13" / "lib"), str(nvidia / "cudnn" / "lib")]
    assert cuda_env["LD_LIBRARY_PATH"].split(":") == folders + ["/opt/mine"] and folders[-1] == str(tmp_path / "wsl-lib")
    assert cpu_env["LD_LIBRARY_PATH"] == "/opt/mine" and AC.os.environ["LD_LIBRARY_PATH"] == "/opt/mine"
    key = AC.take_key(AC.sha256(audio), 1, AC.install_key(inst))
    assert json.loads((tmp_path / "gpu" / "seed_1" / AC.TAKE).read_text(encoding="utf-8")) == key
    monkeypatch.delenv("LD_LIBRARY_PATH")
    generate(inst, audio, tmp_path / "gpu2", (1,), device="cuda", run=drv)
    assert drv.calls[2][1]["LD_LIBRARY_PATH"] == ":".join(folders)
    generate(inst, audio, tmp_path / "cpu2", (1,), device="cpu", run=drv)
    assert "LD_LIBRARY_PATH" not in drv.calls[3][1]


# ------------------------------------------------------------------------------------------------ cut short (M5-02)

SONG_SR, SONG_S = 2000, 100.0     # the generated song: a WAV of SONG_S seconds, a guitar note every 0.25 s


def song_wav(path, seconds=SONG_S):
    """A stereo float32 WAV whose every sample differs (so a piece's samples can be checked against it)."""
    import numpy as np
    import soundfile as sf
    n = int(seconds * SONG_SR)
    y = (np.arange(n, dtype=np.float64) / n).astype(np.float32)
    sf.write(str(path), np.stack([y, -y], axis=1), SONG_SR, subtype="FLOAT")
    return path


def song_notes(seconds=SONG_S):
    return [1.0 + 0.25 * k for k in range(int((seconds - 2.0) / 0.25) + 1)]   # 1.0 .. seconds - 1


class CutDriver:
    """The driver on the generated song: each run charts the song's notes from its audio's start (a piece's audio
    is the decode's tail, so its length gives where it starts) on a map of its own (the whole-song run's 120 BPM, a
    piece's 150 BPM), up to `stops[k]` for the k-th run (absolute seconds; past the list, to the end), reporting the
    budget used up (nTokens 8192, or nBeats 1280 with by="beats") when that is before the song's last note.
    `fail`: the run (from 0) that exits with `code`; `devices`: the transcriber's device for the k-th run (default
    the one asked for). Writes notes.chart, song.ini, song.ogg and autochart_run/ as the driver does; `calls` keeps
    each run's (audio, out, env, whether take.json existed)."""

    def __init__(self, stops=(), by="tokens", fail=None, code=1, seconds=SONG_S, devices=None, stderr=None):
        self.stops, self.by, self.fail, self.code, self.seconds = list(stops), by, fail, code, seconds
        self.devices, self.stderr, self.calls, self.charts = devices or {}, stderr, [], []

    def __call__(self, cmd, env, cwd, capture_output, text, timeout):
        import soundfile as sf
        from pathlib import Path
        from songcharter.chart import Chart, FretNote, SongInfo, Track, write_chart
        from songcharter.tempo import Tempo, TempoMap
        k = len(self.calls)
        audio, folder = Path(cmd[cmd.index("--audio") + 1]), Path(cmd[cmd.index("--out") + 1])
        self.calls.append((audio, folder, env, (folder.parent / AC.TAKE).exists() or (folder / AC.TAKE).exists()))
        if k == self.fail:
            if self.code == "timeout":
                raise subprocess.TimeoutExpired(cmd, timeout)
            return subprocess.CompletedProcess(cmd, self.code, "", self.stderr or
                                               "[autochart] FAILED: expert: engine failed (exit 3) transcription x\n")
        info = sf.info(str(audio))
        start = self.seconds - info.frames / info.samplerate
        stop = self.stops[k] if k < len(self.stops) else None
        notes = [t for t in song_notes(self.seconds) if t >= start - 1e-9 and (stop is None or t <= stop + 1e-9)]
        cut = stop is not None and stop < song_notes(self.seconds)[-1]
        per_s = 960 if k == 0 else 1200   # 120 BPM, or the piece's own 150 BPM, at resolution 480
        tm = TempoMap(480, [Tempo(0, 120000 if k == 0 else 150000)])
        track = Track("Expert", "Single", [FretNote(round((t - start) * per_s), ((0, 1, 2, 3, 4)[i % 5],))
                                           for i, t in enumerate(song_notes(self.seconds)) if t in notes])
        text_ = write_chart(Chart(SongInfo("Song", "Band", charter="Autochart"), tm, [], [track]))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "notes.chart").write_text(text_, encoding="utf-8", newline="")
        self.charts.append(text_)
        (folder / "song.ini").write_text("[song]\nname = Song\n", encoding="utf-8")
        (folder / "song.ogg").write_bytes(b"OggS")
        (folder / "autochart_run").mkdir(exist_ok=True)
        (folder / "autochart_run" / "expert_job.json").write_text("{}", encoding="utf-8")
        tokens = 8192 if cut and self.by == "tokens" else 2000
        beats = 1280 if cut and self.by == "beats" else 200
        summary = {"inputSha256": AC.sha256(audio), "seed": int(env["AC_SEED"]), "difficulties": ["expert"],
                   "temperature": float(env["AC_TEMPERATURE"]), "topP": float(env["AC_TOP_P"]), "maxTokens": 8192,
                   "runs": [{"status": "completed", "nTokens": tokens, "nBeats": beats,
                             "devices": {"transcriber": self.devices.get(k, env["AC_DEVICE"])}}]}
        (folder / "autochart_run" / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")


def stitched_times(chart):
    from songcharter.importers import read_song
    return [round(n.time, 6) for n in read_song(chart).parts[("guitar", "expert")].notes]


def listing(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*"))


@pytest.mark.parametrize("by", ["tokens", "beats"])
def test_a_take_cut_short_is_continued_and_stitched(tmp_path, by):
    """A summary with nTokens 8192 (or nBeats 1280) and a chart ending at 60 % of the song: a second run whose
    --audio is a WAV of the decode from B - 8 s (B = floor(60) - 1), the same samples; the stitched notes.chart (every
    note of the song, the piece's moved onto the base's map), the engine's own output in cut_short/, piece_1/ beside
    it, the stitch record in autochart_run/summary.json, take.json written last; the next generate reuses it."""
    import numpy as np
    import soundfile as sf
    inst = find_install(install(tmp_path), node="node")
    audio = song_wav(tmp_path / "decode.wav")
    drv = CutDriver(stops=[60.0], by=by)
    takes = generate(inst, audio, tmp_path / "out", (7,), run=drv)
    folder = tmp_path / "out" / "seed_7"
    assert len(drv.calls) == 2 and not any(c[3] for c in drv.calls)   # no take.json while either ran
    piece_audio, piece_out, env, _ = drv.calls[1]
    assert piece_audio == folder / "piece_1" / "input.wav" and piece_out == folder / "piece_1"
    assert drv.calls[1][2]["AC_SEED"] == "7" and drv.calls[0][2] == env   # the same seed and settings
    y, sr = sf.read(str(piece_audio), dtype="float32", always_2d=True)
    whole, _ = sf.read(str(audio), dtype="float32", always_2d=True)
    assert sr == SONG_SR and np.array_equal(y, whole[51 * SONG_SR:])   # from B - CONTEXT = 59 - 8 s
    assert stitched_times(folder / "notes.chart") == song_notes()
    assert stitched_times(folder / AC.CUT / "notes.chart") == [t for t in song_notes() if t <= 60.0]
    assert {p.name for p in (folder / AC.CUT).iterdir()} == {"notes.chart", "song.ini", "song.ogg", "autochart_run"}
    assert (folder / AC.CUT / "autochart_run" / "expert_job.json").is_file()
    assert {p.name for p in folder.iterdir()} == {"notes.chart", "autochart_run", AC.TAKE, AC.CUT, "piece_1"}
    assert (folder / "piece_1" / "notes.chart").is_file() and (folder / "piece_1" / "song.ini").is_file()
    summary = json.loads((folder / "autochart_run" / "summary.json").read_text(encoding="utf-8"))
    engine = json.loads((folder / AC.CUT / "autochart_run" / "summary.json").read_text(encoding="utf-8"))
    stitch = summary.pop("stitch")
    assert summary == engine   # the whole-song run's summary, plus the record
    piece = stitch["pieces"][0]
    assert (stitch["cut_short"], stitch["cut_at_s"], stitch["last_note_s"], stitch["ended"], len(stitch["pieces"])) \
        == (by, 60.0, 99.0, "end", 1)
    assert (piece["start_s"], piece["keep_from_s"], piece["last_note_s"], piece["cut_short"]) == (51.0, 59.0, 99.0,
                                                                                                 None)
    assert (piece["nTokens"], piece["nBeats"], piece["devices"]) == (2000, 200, {"transcriber": "cpu"})
    assert isinstance(piece["seconds"], float) and stitch["device"] == "cpu"
    take = takes[0]
    assert (take.cut_short, take.stitch, take.cached, take.devices) == (by, stitch, False, {"transcriber": "cpu"})
    written = {p: p.stat().st_mtime_ns for p in folder.rglob("*") if p.is_file()}
    assert max(written, key=written.get) == folder / AC.TAKE   # take.json last
    again = generate(inst, audio, tmp_path / "out", (7,), run=drv)
    assert len(drv.calls) == 2 and again[0].cached and again[0].cut_short == by and again[0].stitch == stitch


def test_a_piece_cut_short_again_is_continued_and_the_loop_ends(tmp_path, monkeypatch):
    """A piece cut short again is continued from its own last note (two pieces); one that advances the take by
    under 20 s ends the loop and is still stitched; at most MAX_PIECES pieces."""
    inst = find_install(install(tmp_path), node="node")
    audio = song_wav(tmp_path / "decode.wav")
    drv = CutDriver(stops=[40.0, 70.0])
    generate(inst, audio, tmp_path / "two", (7,), run=drv)
    folder = tmp_path / "two" / "seed_7"
    stitch = json.loads((folder / "autochart_run" / "summary.json").read_text(encoding="utf-8"))["stitch"]
    assert [(p["start_s"], p["keep_from_s"], p["last_note_s"], p["cut_short"]) for p in stitch["pieces"]] == \
        [(31.0, 39.0, 70.0, "tokens"), (61.0, 69.0, 99.0, None)]
    assert len(drv.calls) == 3 and stitch["ended"] == "end" and stitched_times(folder / "notes.chart") == song_notes()
    assert drv.calls[2][0] == folder / "piece_2" / "input.wav"
    # the 20-s rule: the piece is cut short again at 55 s, 15 s on: the loop ends there, the piece stitched
    drv = CutDriver(stops=[40.0, 55.0])
    generate(inst, audio, tmp_path / "stall", (7,), run=drv)
    folder = tmp_path / "stall" / "seed_7"
    stitch = json.loads((folder / "autochart_run" / "summary.json").read_text(encoding="utf-8"))["stitch"]
    assert len(drv.calls) == 2 and (stitch["ended"], stitch["last_note_s"]) == ("stalled", 55.0)
    assert stitched_times(folder / "notes.chart") == [t for t in song_notes() if t <= 55.0]
    # MAX_PIECES: every piece cut short again 21 s on
    drv = CutDriver(stops=[10.0 + 21 * k for k in range(AC.MAX_PIECES + 1)], seconds=160.0)
    generate(inst, song_wav(tmp_path / "long.wav", 160.0), tmp_path / "max", (7,), run=drv)
    folder = tmp_path / "max" / "seed_7"
    stitch = json.loads((folder / "autochart_run" / "summary.json").read_text(encoding="utf-8"))["stitch"]
    assert AC.MAX_PIECES == 6 and len(drv.calls) == 1 + AC.MAX_PIECES and len(stitch["pieces"]) == AC.MAX_PIECES
    assert (stitch["ended"], stitch["last_note_s"]) == ("max_pieces", 136.0)
    assert stitched_times(folder / "notes.chart") == [t for t in song_notes(160.0) if t <= 136.0]


def test_a_failed_piece_raises_naming_the_seed_and_leaves_no_take(tmp_path):
    """A piece's non-zero exit is a ToolError naming the seed (its exit code where pipeline.failure reads it) and
    the piece; the finished whole-song run and the piece are kept, but no take.json: the next run is run whole
    again. A piece that does not finish is autochart's timeout."""
    inst = find_install(install(tmp_path), node="node")
    audio = song_wav(tmp_path / "decode.wav")
    out = tmp_path / "out"
    with pytest.raises(ToolError, match=r"(?s)^autochart seed 7 failed \(exit 3\) in piece 1 \(its audio from 0:51\):"
                                        r"\n.*engine failed \(exit 3\)"):
        generate(inst, audio, out, (7,), run=CutDriver(stops=[60.0], fail=1, code=3))
    folder = out / "seed_7"
    assert not (folder / AC.TAKE).exists() and (folder / "notes.chart").is_file() and (folder / "piece_1").is_dir()
    with pytest.raises(ToolError, match=r"^autochart seed 7 did not finish within 4200 s in piece 1 "):
        generate(inst, audio, out, (7,), timeout_s=3600, run=CutDriver(stops=[60.0], fail=1, code="timeout"))
    drv = CutDriver(stops=[60.0])
    generate(inst, audio, out, (7,), run=drv)   # run whole again, and continued
    assert len(drv.calls) == 2 and stitched_times(folder / "notes.chart") == song_notes()
    assert {p.name for p in folder.iterdir()} == {"notes.chart", "autochart_run", AC.TAKE, AC.CUT, "piece_1"}


def test_a_take_run_again_starts_from_the_drivers_files_only(tmp_path):
    """A stitched take run again (its key changed: here the driver was updated) or a continuation cut off after the
    engine's output moved: what the earlier continuation left (cut_short/, piece_<k>/) goes before the run, so the
    new take has only its own pieces."""
    root = install(tmp_path)
    inst = find_install(root, node="node")
    audio = song_wav(tmp_path / "decode.wav")
    out, folder = tmp_path / "out", tmp_path / "out" / "seed_7"
    generate(inst, audio, out, (7,), run=CutDriver(stops=[40.0, 70.0]))
    assert {p.name for p in folder.iterdir()} >= {"piece_1", "piece_2", AC.CUT}
    (root / "ac_headless.cjs").write_text("// driver B", encoding="utf-8")
    inst = find_install(root, node="node")
    drv = CutDriver(stops=[60.0])
    generate(inst, audio, out, (7,), run=drv)
    assert len(drv.calls) == 2 and {p.name for p in folder.iterdir()} == {"notes.chart", "autochart_run", AC.TAKE,
                                                                          AC.CUT, "piece_1"}
    assert stitched_times(folder / AC.CUT / "notes.chart")[-1] == 60.0
    # cut off after the move: the engine's output in cut_short/, no notes.chart, no take.json
    (folder / AC.TAKE).unlink()
    (folder / "notes.chart").unlink()
    drv = CutDriver(stops=[50.0])
    generate(inst, audio, out, (7,), run=drv)
    assert len(drv.calls) == 2 and stitched_times(folder / AC.CUT / "notes.chart")[-1] == 50.0
    assert stitched_times(folder / "notes.chart") == song_notes()


def test_a_take_under_both_caps_is_left_as_the_engine_wrote_it(tmp_path):
    """One run, and the folder exactly as the driver left it (its listing and notes.chart byte for byte) plus
    take.json, as before M5-02."""
    inst = find_install(install(tmp_path), node="node")
    audio = song_wav(tmp_path / "decode.wav")
    drv = CutDriver()
    takes = generate(inst, audio, tmp_path / "out", (7,), run=drv)
    folder = tmp_path / "out" / "seed_7"
    assert len(drv.calls) == 1 and takes[0].cut_short is None and takes[0].stitch is None
    assert listing(folder) == ["autochart_run", "autochart_run/expert_job.json", "autochart_run/summary.json",
                               "notes.chart", "song.ini", "song.ogg", AC.TAKE]
    assert (folder / "notes.chart").read_bytes() == drv.charts[0].encode("utf-8")
    assert "stitch" not in json.loads((folder / "autochart_run" / "summary.json").read_text(encoding="utf-8"))


def test_a_cached_take_cut_short_without_its_stitch_is_run_again_and_continued(tmp_path):
    """A take v0.1 cut short (the driver's files and a take.json of today's key, no stitch record) is a miss: run
    whole again and continued, then a hit. A cut-short take with its stitch record is a hit; so is a take with no
    note at all (T = 0), left as it is with a record of no pieces."""
    inst = find_install(install(tmp_path), node="node")
    audio = song_wav(tmp_path / "decode.wav")
    out, folder = tmp_path / "out", tmp_path / "out" / "seed_7"
    old = CutDriver(stops=[60.0])
    old(["node", "drv", "--audio", str(audio), "--out", str(folder), "--work", str(tmp_path / "w")],
        env={"AC_SEED": "7", "AC_TEMPERATURE": "0.95", "AC_TOP_P": "0.98", "AC_DEVICE": "cpu"}, cwd=".",
        capture_output=True, text=True, timeout=1)
    key = AC.take_key(AC.sha256(audio), 7, AC.install_key(inst))
    (folder / AC.TAKE).write_text(json.dumps(key), encoding="utf-8")   # v0.1's take: a hit before M5-02
    assert AC._summary(folder, key) is not None and AC._done(folder, key) is None
    drv = CutDriver(stops=[60.0])
    takes = generate(inst, audio, out, (7,), run=drv)
    assert len(drv.calls) == 2 and not takes[0].cached and takes[0].stitch["pieces"][0]["keep_from_s"] == 59.0
    assert stitched_times(folder / "notes.chart") == song_notes()
    assert generate(inst, audio, out, (7,), run=drv)[0].cached and len(drv.calls) == 2
    # no note at all, cut short: no piece, the engine's files as they are, a record so it is a hit next time
    drv = CutDriver(stops=[0.5])
    takes = generate(inst, audio, tmp_path / "none", (7,), run=drv)
    folder = tmp_path / "none" / "seed_7"
    assert len(drv.calls) == 1 and takes[0].stitch == {"cut_short": "tokens", "device": "cpu", "cut_at_s": None,
                                                       "pieces": [], "last_note_s": None, "ended": "no notes"}
    assert listing(folder) == ["autochart_run", "autochart_run/expert_job.json", "autochart_run/summary.json",
                               "notes.chart", "song.ini", "song.ogg", AC.TAKE]
    assert (folder / "notes.chart").read_bytes() == drv.charts[0].encode("utf-8")
    again = generate(inst, audio, tmp_path / "none", (7,), run=drv)
    assert len(drv.calls) == 1 and again[0].cached and again[0].cut_short == "tokens"


def test_a_piece_on_another_device_counts_for_the_take(tmp_path):
    """Take.devices answers from the whole-song run, but a piece whose transcriber ran on another device than asked
    makes the take's that device; such a take is not reused on the device asked for."""
    inst = find_install(install(tmp_path), node="node")
    audio = song_wav(tmp_path / "decode.wav")
    takes = generate(inst, audio, tmp_path / "out", (7,), device="cuda", run=CutDriver(stops=[60.0], devices={1: "cpu"}))
    assert takes[0].summary["runs"][0]["devices"] == {"transcriber": "cuda"}
    assert takes[0].devices == {"transcriber": "cpu"}
    drv = CutDriver(stops=[60.0])
    again = generate(inst, audio, tmp_path / "out", (7,), device="cuda", run=drv)
    assert len(drv.calls) == 2 and not again[0].cached and again[0].devices == {"transcriber": "cuda"}
    assert generate(inst, audio, tmp_path / "out", (7,), device="cuda", run=drv)[0].cached


def test_the_budget_comes_from_the_models_manifest(tmp_path):
    """The beat cap and the engine's own token budget are the models' manifest's (its transcriber's modelConfig),
    else 8192 and 1280; the driver's maxTokens counts when lower."""
    root = install(tmp_path)
    inst = find_install(root, node="node")
    assert AC.budget(inst) == (8192, 1280)
    (root / "models" / "fretformer-v2" / "manifest.json").write_text(json.dumps(
        {"stages": {"transcriber": {"modelConfig": {"maxTokens": 4096, "maxBeats": 640}}}}), encoding="utf-8")
    assert AC.budget(inst) == (4096, 640)

    def summary(tokens, beats, limit=8192):
        return {"maxTokens": limit, "runs": [{"nTokens": tokens, "nBeats": beats}]}

    assert AC.cut_short(summary(8192, 100)) == "tokens" and AC.cut_short(summary(8191, 1279)) is None
    assert AC.cut_short(summary(100, 1280)) == "beats" and AC.cut_short(summary(8192, 1280)) == "tokens"
    assert AC.cut_short(summary(4096, 100), (4096, 640)) == "tokens" and AC.cut_short(summary(100, 640), (4096, 640))
    assert AC.cut_short(summary(5000, 100, limit=5000)) == "tokens"
    assert AC.cut_short({"runs": [{}]}) is None and AC.cut_short({}) is None   # a summary without the counts
