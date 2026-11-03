"""Stem separation (songcharter.separate) with Demucs's tiny untrained unit-test model: shapes, seeding, the cache,
the CPU fallback and the pinned-file check. The real weights are never downloaded here."""
import hashlib

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
