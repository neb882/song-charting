"""M8-14: the seed as configuration (pipeline.Options.seed, `songcharter chart --seed N`, pipeline.take_seeds) and
the recorded configuration in report.json's `pipeline` (pipeline.folder_record: the seed, each take's seed, the
engines' identities). The pipeline runs on test_pipeline's synthetic song with its stand-in engines (no model runs
here), the guitar's notes made to depend on the seed."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

import songcharter.pipeline as P
from songcharter.cli import main
from songcharter.engines import autochart as AC
from songcharter.engines.autochart import DEFAULT_SEED
from songcharter.errors import InputError

sys.path.insert(0, str(Path(__file__).parent))
from test_pipeline import FretNote, Track, _write, guitar_times, standins, tick, write_song  # noqa: E402

# what the real engines' infos hold (their engine.json, take.json and separate.SeparationInfo), made up but shaped
INFOS = {
    "separate": {"model": "htdemucs_6s", "revision": "3c5ee475be622df764938de97e4281a7b07ffa58", "seed": 42,
                 "device": "cpu", "cached": True, "key": "0123456789abcdef01234567", "shifts": 1, "overlap": 0.25},
    "drums": {"engine": "adtof", "version": "adtof-1", "key": "k" * 24,
              "weights": {"url": "https://example.invalid/w.pth",
                          "sha256": "1bc986e596ec47ba0b44916f87cd4a39f0b2bec23596df3fb5d0e87749217320"}},
    "bass": {"engine": "songcharter.engines.bass", "version": "1", "versions": {"librosa": "0.0.1", "numpy": "0.0.2"}},
    "sections": {"engine_version": 1, "backend": "allin1",
                 "allin1": {"package": "allin1", "version": "0.0.3", "model": "harmonix-fold0",
                            "weights": {"fold0.pth": "a" * 64}, "python": "/made/up/venv/bin/python"},
                 "settings": {"python": "/made/up/venv/bin/python"}},
    "guitar": {"devices": {"transcriber": "cpu"},
               "install": {"engineVersion": "made-up-engine-1", "install": "c" * 64}},
}


def seeded():
    """The stand-in engines, with a guitar whose notes depend on its seed (each seed but autochart's default drops
    another note) and engine infos shaped as the real ones'."""
    base = standins()

    class Seeded(base):
        def separate(self, mix, cache_dir, device):
            stems, folder, info = super().separate(mix, cache_dir, device)
            return stems, folder, {**INFOS["separate"], **info}

        def drums(self, mix, drums, out, device):
            r = super().drums(mix, drums, out, device)
            return P.Run(r.path, r.cached, {**INFOS["drums"], **r.info})

        def bass(self, mix, bass, out):
            r = super().bass(mix, bass, out)
            return P.Run(r.path, r.cached, {**INFOS["bass"], **r.info})

        def sections(self, song, out, device, threads):
            r = super().sections(song, out, device, threads)
            return P.Run(r.path, r.cached, {**r.info, **INFOS["sections"]})

        def guitar(self, audio, out, seeds, device, title, artist, scratch=None, on_take=None):
            self.calls.append(("guitar", audio, out, tuple(seeds), device, title, artist, scratch))
            runs = []
            for k, seed in enumerate(seeds, 1):
                path = out / f"seed_{seed}" / "notes.chart"
                cached = path.is_file()
                if not cached:
                    if on_take is not None:
                        on_take(k, len(seeds), seed)
                    drop = None if seed == DEFAULT_SEED else 10 + seed % 50
                    notes = [FretNote(tick(t), (lane,)) for j, (t, lane) in enumerate(guitar_times()) if j != drop]
                    _write(path, Track("Expert", "Single", notes))
                runs.append(P.Run(path, cached, {**INFOS["guitar"]}))
            return runs

    Seeded.calls = []
    return Seeded


@pytest.fixture(scope="module")
def song(tmp_path_factory):
    """The song, and a chart of it with every option at its default (seed 0) in a cache of this module's."""
    root = tmp_path_factory.mktemp("seed")
    write_song(root / "song.flac")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SONGCHARTER_CACHE", str(root / "cache"))
        engines = seeded()()
        first = P.chart(root / "song.flac", root / "out" / "v1" / "Click Song", P.Options(), engines=engines,
                        log=lambda line: None, sampler=None)
        yield root, first, engines, mp


def chart_again(song, name, options):
    root, _, _, mp = song
    engines = seeded()()
    events = []
    result = P.chart(root / "song.flac", root / "out" / name / "Click Song", options, engines=engines,
                     log=lambda line: None, sampler=None, events=events.append)
    return result, engines, events


def report(result) -> dict:
    return json.loads((result.folder / "report.json").read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_seeds_of_each_take():
    """take_seeds: seed 0 gives every earlier version's seeds (break: the default moved); another seed moves each
    take's seed on by it, the first and every other (Quick's 1 take; Best's 4); the seeds of one chart are always
    distinct; Options.check takes a whole number from 0 to MAX_SEED only (breaks: a bool, a float or a negative let
    through)."""
    assert P.take_seeds(1) == P.take_seeds(1, 0) == (20260609,) and DEFAULT_SEED == 20260609
    assert P.take_seeds(4) == P.take_seeds(4, 0) == (20260609, 101, 202, 303)
    assert P.take_seeds(1, 1) == (20260610,) and P.take_seeds(1, 2) == (20260611,)
    assert P.take_seeds(4, 1) == (20260610, 102, 203, 304)
    assert P.take_seeds(4, 7) == (20260616, 108, 209, 310)
    for seed in (0, 1, 50, 100, 101, 5000, P.MAX_SEED):
        for n in (1, 3, 4, 9):
            seeds = P.take_seeds(n, seed)
            assert len(set(seeds)) == n and seeds[0] == DEFAULT_SEED + seed, (n, seed)
    assert set(P.take_seeds(4, 1)).isdisjoint(P.take_seeds(4, 0))   # every take another way
    P.Options(seed=0).check()
    P.Options(seed=P.MAX_SEED).check()
    assert P.Options().seed == 0
    for bad in (-1, P.MAX_SEED + 1, True, 1.0, "1", None):
        with pytest.raises(InputError, match=r"^seed is a whole number from 0 to 999999, not "):
            P.Options(seed=bad).check()


def test_the_take_cache_is_keyed_on_the_seed():
    """A take's cache key (autochart's take.json) and its folder hold its seed, so another seed never reuses a take
    (checked, not changed: the engines are not this order's)."""
    install = {"engineVersion": "x", "install": "y"}
    assert AC.take_key("s", 1, install)["seed"] == 1
    assert AC.take_key("s", 1, install) != AC.take_key("s", 2, install)
    assert AC.take_key("s", 1, install) == AC.take_key("s", 1, dict(install))


def test_another_seed_charts_the_guitar_again_and_reuses_the_rest(song):
    """Seed 2: the guitar's one take runs with its seed moved on, bass, drums, sections and the separation come from
    the cache, and the chart differs; report.json and pipeline.json record the seed and each take's seed (breaks:
    the seed not reaching take_seeds; the record missing it)."""
    root, first, _, _ = song
    result, engines, events = chart_again(song, "seed2", P.Options(seed=2))
    assert [c[3] for c in engines.calls if c[0] == "guitar"] == [(DEFAULT_SEED + 2,)]
    assert [e["seed"] for e in events if e["event"] == "take"] == [DEFAULT_SEED + 2]
    cached = {s.name: s.cached for s in result.stages}
    assert cached["separate"] and cached["drums"] and cached["bass"] and cached["sections"] and not cached["guitar"]
    assert sha(result.folder / "notes.chart") != sha(first.folder / "notes.chart")
    rec = report(result)["pipeline"]
    assert rec["seed"] == 2 and rec["takes"]["seeds"] == [DEFAULT_SEED + 2] and rec["takes"]["asked"] is None
    assert report(first)["pipeline"]["seed"] == 0 and report(first)["pipeline"]["takes"]["seeds"] == [DEFAULT_SEED]
    work = json.loads((result.work / "pipeline.json").read_text(encoding="utf-8"))
    assert work["options"]["seed"] == 2 and work["takes"]["seeds"] == [DEFAULT_SEED + 2]


def test_best_moves_each_of_its_four_seeds(song):
    """Best (4 takes) with seed 1: each of the four seeds moved on by one (break: only the first moved)."""
    result, engines, _ = chart_again(song, "best1", P.Options(takes=4, seed=1))
    assert [c[3] for c in engines.calls if c[0] == "guitar"] == [(DEFAULT_SEED + 1,), (102,), (203,), (304,)]
    rec = report(result)["pipeline"]
    assert rec["seed"] == 1 and rec["takes"]["seeds"] == [DEFAULT_SEED + 1, 102, 203, 304]
    assert rec["takes"]["asked"] == 4 and rec["takes"]["made"] == 4


def test_the_default_seed_gives_the_same_chart_and_report(song):
    """Seed 0 charted again: the guitar called with autochart's default seed alone, every stage from the cache, and a
    byte-identical notes.chart and report.json (the report holds no time of its own: M8-14's question; breaks: the
    default seed moved; a clock or a random value in the report)."""
    root, first, _, _ = song
    result, engines, _ = chart_again(song, "v1", P.Options(seed=0))
    assert result.folder == first.folder
    assert [c[3] for c in engines.calls if c[0] == "guitar"] == [(DEFAULT_SEED,)]
    assert all(s.cached for s in result.stages if s.name not in ("assemble", "preview"))
    assert sha(result.folder / "notes.chart") == sha(first.folder / "notes.chart")
    first_report = (first.folder / "report.json").read_bytes()
    assert (result.folder / "report.json").read_bytes() == first_report


def test_the_report_records_the_engines_identities_and_no_path(song):
    """report.json's `pipeline.engines`: each engine's identity as its cache keys it, as version strings and short
    hashes (the separation's model, revision and seed; ADTOF's version and weights; the bass rules' version and
    libraries; allin1's version, model and weights; autochart's engine and install), never a path or a URL (breaks:
    a stage's identity not recorded; a long hash or a path kept)."""
    _, first, _, _ = song
    engines = report(first)["pipeline"]["engines"]
    assert engines == {
        "separation": {"model": "htdemucs_6s", "revision": "3c5ee475be62", "seed": 42},
        "drums": {"engine": "adtof-1", "weights": "1bc986e596ec"},
        "bass": {"engine": "1", "libraries": P.short_hash({"librosa": "0.0.1", "numpy": "0.0.2"})},
        "sections": {"backend": "allin1", "engine": 1, "allin1": "0.0.3", "model": "harmonix-fold0",
                     "weights": P.short_hash({"fold0.pth": "a" * 64})},
        "guitar": {"engine": "made-up-engine-1", "install": "c" * 12}}
    text = json.dumps(report(first)["pipeline"])
    assert "/" not in text and "\\" not in text and "example.invalid" not in text
    assert all(len(v) <= P.SHORT for e in engines.values() for k, v in e.items()
               if k in ("revision", "weights", "libraries", "install"))


def test_engine_identities_of_partial_infos():
    """An engine's info without the keys (an older engine.json, a stand-in) gives None for them, never an error; the
    librosa sections give their version; an unknown stage is a bug (ValueError)."""
    assert P.engine_identities("separate", {}) == {"model": None, "revision": None, "seed": None}
    assert P.engine_identities("drums", {"weights": None}) == {"engine": None, "weights": None}
    assert P.engine_identities("guitar", {"install": None}) == {"engine": None, "install": None}
    assert P.engine_identities("sections", {"backend": "librosa", "engine_version": 1,
                                            "librosa": {"version": "0.0.4", "segments": [1, 2]}}) == {
        "backend": "librosa", "engine": 1, "librosa": "0.0.4"}
    assert P.engine_identities("bass", None) == {"engine": None, "libraries": None}
    with pytest.raises(ValueError):
        P.engine_identities("lyrics", {})
    assert P.short_hash(None) is None and P.short_hash("ab" * 20) == "ab" * 6
    assert P.short_hash({"b": 1, "a": 2}) == P.short_hash({"a": 2, "b": 1})   # by content, not by order


def test_the_guitar_runs_carry_their_take_key(tmp_path, monkeypatch):
    """Engines.guitar puts each take's key (take.json: engineVersion and the install's hash) into its run's info, for
    report.json's `engines`; a take without take.json gives None (break: the key not read)."""
    out = tmp_path / "guitar"
    for seed in (5, 6):
        (out / f"seed_{seed}").mkdir(parents=True)
        (out / f"seed_{seed}" / "notes.chart").write_text("[Song]\n{\n}\n", encoding="utf-8")
    (out / "seed_5" / AC.TAKE).write_text(json.dumps({"seed": 5, "engineVersion": "e1", "install": "f" * 64,
                                                      "inputSha256": "0" * 64}), encoding="utf-8")
    monkeypatch.setattr(AC, "find_install", lambda: None)
    monkeypatch.setattr(AC, "generate", lambda install, audio, o, seeds, **kw: [
        AC.Take(s, o / f"seed_{s}" / "notes.chart", {"runs": [{"devices": {"transcriber": "cpu"}}]}, True, 0.0)
        for s in seeds])
    runs = P.Engines().guitar(tmp_path / "a.wav", out, [5, 6], "cpu", "T", "A")
    assert runs[0].info["install"] == {"engineVersion": "e1", "install": "f" * 64}
    assert runs[1].info["install"] is None


def test_the_cli_takes_a_seed(monkeypatch, capsys):
    """--seed N reaches pipeline.Options (0 without it); a seed out of range is refused with exit 2 and the check's
    words (break: --seed not passed on)."""
    seen = []

    def chart(song, out, options, events=None):
        seen.append(options.seed)
        options.check()
        raise KeyboardInterrupt

    monkeypatch.setattr(P, "chart", chart)
    assert main(["chart", "song.mp3", "--out", "o", "--seed", "3"]) == 130
    assert main(["chart", "song.mp3", "--out", "o"]) == 130
    assert main(["chart", "song.mp3", "--out", "o", "--seed", "-1"]) == 2
    assert seen == [3, 0, -1]
    assert "seed is a whole number from 0 to 999999, not -1" in capsys.readouterr().err
