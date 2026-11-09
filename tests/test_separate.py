"""Stem separation (songcharter.separate) with Demucs's tiny untrained unit-test model: shapes, seeding, the cache,
the CPU fallback and the pinned-file check. The real weights are never downloaded here."""
import hashlib
import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("demucs")

import songcharter.separate as S  # noqa: E402
from songcharter.separate import MODELS, ModelFiles, model_paths, separate  # noqa: E402


@pytest.fixture(scope="module")
def tiny():
    from demucs.pretrained import get_model
    return get_model("demucs_unittest").eval()


def mix(seconds=3.0, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * S.SAMPLE_RATE)
    t = np.arange(n) / S.SAMPLE_RATE
    y = 0.3 * np.sin(2 * np.pi * 220 * t) + 0.05 * rng.standard_normal(n)
    return np.stack([y, 0.8 * y]).astype(np.float32)


def test_stems_line_up_with_the_mix(tiny):
    m = mix()
    stems, info = separate(m, model=tiny, device="cpu")
    assert list(stems) == list(tiny.sources)
    for y in stems.values():
        assert y.shape == m.shape and y.dtype == np.float32 and np.isfinite(y).all()
    assert info.device == "cpu" and info.fallback is None and not info.cached and info.revision is None


def test_the_same_seed_gives_the_same_stems(tiny):
    m = mix()
    a, _ = separate(m, model=tiny, device="cpu", seed=3)
    b, _ = separate(m, model=tiny, device="cpu", seed=3)
    assert all(np.array_equal(a[s], b[s]) for s in a)
    c, _ = separate(m, model=tiny, device="cpu", seed=4)  # another random time shift
    assert any(not np.array_equal(a[s], c[s]) for s in a)


def test_the_cache_returns_the_same_stems_without_separating(tiny, tmp_path, monkeypatch):
    m = mix()
    a, info = separate(m, model=tiny, device="cpu", cache_dir=tmp_path)
    assert (tmp_path / info.key / "info.json").exists()
    monkeypatch.setattr(S, "_run", lambda *a, **k: pytest.fail("separated again"))
    b, again = separate(m, model=tiny, device="cpu", cache_dir=tmp_path)
    assert again.cached and again.seconds == 0.0 and again.key == info.key
    assert all(np.array_equal(a[s], b[s]) for s in a)
    # another seed, or other samples, is another key
    assert S.cache_key(m, "x", None, 1, 1, 0.25) != S.cache_key(m, "x", None, 0, 1, 0.25)
    assert S.cache_key(m[:, :-1], "x", None, 0, 1, 0.25) != S.cache_key(m, "x", None, 0, 1, 0.25)
    # a folder without info.json (an interrupted write) is not a hit
    (tmp_path / info.key / "info.json").unlink()
    monkeypatch.setattr(S, "_run", lambda model, mix, *a, **k: {s: mix.copy() for s in model.sources})
    _, fresh = separate(m, model=tiny, device="cpu", cache_dir=tmp_path)
    assert not fresh.cached


def test_stems_written_again_never_write_through_a_hard_link(tiny, tmp_path):
    """The v0.5.0 re-review's R2: eval/golden.py hard-links another cache's stems into a build's cache folder. When
    that folder is separated again in place (its info.json says another device), each WAV is a new file: the linked
    source keeps its bytes (break: write_wav over the link truncates and rewrites the source's own file)."""
    m = mix()
    stems, made = separate(m, model=tiny, device="cpu", cache_dir=tmp_path / "a")
    source, linked = tmp_path / "source" / made.key, tmp_path / "b" / made.key
    source.mkdir(parents=True)
    linked.mkdir(parents=True)
    for s in stems:   # "another device's" stems in the source, linked into the build's cache folder
        S.A.write_wav(-stems[s], source / f"{s}.wav")
        (linked / f"{s}.wav").hardlink_to(source / f"{s}.wav")
    meta = json.loads((tmp_path / "a" / made.key / "info.json").read_text(encoding="utf-8"))
    (source / "info.json").write_text(json.dumps({**meta, "info": {**meta["info"], "device": "cuda"}}))
    (linked / "info.json").write_text((source / "info.json").read_text())
    before = {s: (source / f"{s}.wav").read_bytes() for s in stems}
    again, info = separate(m, model=tiny, device="cpu", cache_dir=tmp_path / "b")
    assert not info.cached and all(np.array_equal(again[s], stems[s]) for s in stems)
    assert {s: (source / f"{s}.wav").read_bytes() for s in stems} == before
    assert not any((linked / f"{s}.wav").samefile(source / f"{s}.wav") for s in stems)


def test_a_cache_folder_missing_a_stem_is_separated_again(tiny, tmp_path):
    """info.json beside stems that are gone or do not read (a folder deleted in name order up to a file in use, a
    file cut short) is a miss, separated and written again, not an error."""
    m = mix()
    a, info = separate(m, model=tiny, device="cpu", cache_dir=tmp_path)
    folder = tmp_path / info.key
    for broken in ("missing", "cut short"):
        stem = folder / f"{list(a)[0]}.wav"
        if broken == "missing":
            stem.unlink()
        else:
            stem.write_bytes(stem.read_bytes()[:30])
        b, again = separate(m, model=tiny, device="cpu", cache_dir=tmp_path)
        assert not again.cached and all(np.array_equal(a[s], b[s]) for s in a), broken
        assert stem.is_file() and separate(m, model=tiny, device="cpu", cache_dir=tmp_path)[1].cached, broken


def test_cuda_out_of_memory_falls_back_to_the_cpu(tiny, monkeypatch):
    real = S._run
    calls = []

    def run(model, m, device, *rest):
        calls.append(device)
        if device == "cuda":
            raise torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB")
        return real(model, m, device, *rest)

    monkeypatch.setattr(S, "_run", run)
    stems, info = separate(mix(), model=tiny, device="cuda")
    assert calls == ["cuda", "cpu"] and info.device == "cpu"
    assert info.fallback.startswith("CUDA ran out of memory") and "separated on the CPU" in info.fallback
    assert list(stems) == list(tiny.sources)


def test_the_device_is_in_the_key_and_the_cpus_key_is_as_before(tiny, tmp_path, monkeypatch):
    """A second advisor's finding 8 (v0.5.0): stems made on the CPU answered a later CUDA request, so after one CPU
    fallback the song's GPU charts used CPU stems. The device is in the key now. The CPU's key is exactly the
    device-less key of earlier versions (pinned: v0.4.0's code gives 4d21...), so the CPU stems already cached still
    answer. A folder under the CPU's key whose info.json says cuda (an earlier version's CUDA stems) answers no
    request. CUDA out of memory puts its CPU stems under the CPU's key, or takes them from there, and a hit says
    this call's fallback, not the run's."""
    fixed = np.arange(8, dtype=np.float32).reshape(2, 4) / 8
    assert S.cache_key(fixed, "htdemucs_6s", "rev", 0, 1, 0.25) == "4d21dc63c65a94267d50b396"   # v0.4.0's
    assert S.cache_key(fixed, "htdemucs_6s", "rev", 0, 1, 0.25, "cpu") == "4d21dc63c65a94267d50b396"
    assert S.cache_key(fixed, "htdemucs_6s", "rev", 0, 1, 0.25, "cuda") != "4d21dc63c65a94267d50b396"
    real, calls = S._run, []

    def run(model, m, device, *rest):   # no GPU here: "CUDA" stems are the CPU's negated, to tell them apart
        calls.append(device)
        stems = real(model, m, "cpu", *rest)
        return {s: -y for s, y in stems.items()} if device == "cuda" else stems

    monkeypatch.setattr(S, "_run", run)
    m = mix()
    cpu, made = separate(m, model=tiny, device="cpu", cache_dir=tmp_path)
    gpu, info = separate(m, model=tiny, device="cuda", cache_dir=tmp_path)   # not the CPU's stems
    assert calls == ["cpu", "cuda"] and not info.cached and info.device == "cuda" and info.key != made.key
    assert all(np.array_equal(gpu[s], -cpu[s]) for s in cpu) and (tmp_path / info.key / "info.json").is_file()
    again_gpu, hit = separate(m, model=tiny, device="cuda", cache_dir=tmp_path)
    assert hit.cached and hit.key == info.key and all(np.array_equal(again_gpu[s], gpu[s]) for s in gpu)
    again_cpu, hit = separate(m, model=tiny, device="cpu", cache_dir=tmp_path)
    assert hit.cached and hit.key == made.key and all(np.array_equal(again_cpu[s], cpu[s]) for s in cpu)
    assert calls == ["cpu", "cuda"]
    # an earlier version's CUDA stems under the CPU's key: a CPU request separates again, in place
    path = tmp_path / made.key / "info.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**meta, "info": {**meta["info"], "device": "cuda"}}), encoding="utf-8")
    _, fresh = separate(m, model=tiny, device="cpu", cache_dir=tmp_path)
    assert calls == ["cpu", "cuda", "cpu"] and not fresh.cached and fresh.key == made.key
    assert json.loads(path.read_text(encoding="utf-8"))["info"]["device"] == "cpu"

    def oom(model, m, device, *rest):
        calls.append(device)
        if device == "cuda":
            raise torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 2.00 GiB")
        return real(model, m, device, *rest)

    monkeypatch.setattr(S, "_run", oom)
    calls.clear()
    song = mix(seed=1)   # out of memory on CUDA: the CPU's stems, under the CPU's key
    _, moved = separate(song, model=tiny, device="cuda", cache_dir=tmp_path)
    cpu_key = S.cache_key(song, type(tiny).__name__, None, 0, 1, 0.25)
    assert calls == ["cuda", "cpu"] and moved.device == "cpu" and moved.key == cpu_key and not moved.cached
    assert moved.fallback.startswith("CUDA ran out of memory")
    _, again = separate(song, model=tiny, device="cuda", cache_dir=tmp_path)   # CUDA tried again; the CPU's cached
    assert calls == ["cuda", "cpu", "cuda"] and again.cached and again.key == cpu_key
    assert again.fallback == moved.fallback
    _, asked = separate(song, model=tiny, device="cpu", cache_dir=tmp_path)   # a CPU-asked hit names no fallback
    assert asked.cached and asked.key == cpu_key and asked.fallback is None and calls == ["cuda", "cpu", "cuda"]


def test_auto_separates_on_the_cpu_when_cuda_does_not_run(tiny, monkeypatch):
    """torch.cuda.is_available() is also true on a GPU the torch build has no kernels for: "auto" probes with a
    kernel (cuda_works), takes the CPU when it fails, and says why."""
    real = torch.ones

    def ones(*a, device=None, **k):
        if str(device).startswith("cuda"):
            raise RuntimeError("CUDA error: no kernel image is available for execution on the device")
        return real(*a, **k) if device is None else real(*a, device=device, **k)

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch, "ones", ones)
    assert S.cuda_works() == (False, "RuntimeError: CUDA error: no kernel image is available for execution on the "
                                     "device")
    stems, info = separate(mix(), model=tiny, device="auto")
    assert info.device == "cpu" and list(stems) == list(tiny.sources)
    assert info.fallback == ("CUDA does not run here (RuntimeError: CUDA error: no kernel image is available for "
                             "execution on the device); separated on the CPU")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)  # no CUDA at all: the CPU, nothing to report
    assert S.cuda_works() == (False, None) and separate(mix(), model=tiny, device="auto")[1].fallback is None


def test_pinned_files_are_hash_checked(tmp_path, monkeypatch):
    good = tmp_path / "model.yaml"
    good.write_text("models: ['abc']\n", encoding="utf-8")
    sha = hashlib.sha256(good.read_bytes()).hexdigest()
    monkeypatch.setitem(MODELS, "fake", ModelFiles("someone/Fake", "0" * 40, "model.yaml", {"model.yaml": sha}))
    asked = []

    def download(repo, file, revision):
        asked.append((repo, file, revision))
        return str(good)

    assert model_paths("fake", download) == {"model.yaml": good}
    assert asked == [("someone/Fake", "model.yaml", "0" * 40)]  # always the pinned revision
    good.write_text("models: ['evil']\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="not the pinned"):
        model_paths("fake", download)


def test_bad_inputs():
    m = mix(1.0)
    with pytest.raises(ValueError, match="44100 Hz"):
        separate(m, 48000)
    with pytest.raises(ValueError, match="stereo"):
        separate(m[0])
    with pytest.raises(ValueError, match="unknown separation model"):
        separate(m, model="spleeter")
    assert {"htdemucs_6s", "htdemucs_ft"} <= set(MODELS)
