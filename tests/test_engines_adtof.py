"""The ADTOF drums engine (songcharter.engines.adtof) and its lane mapping (songcharter.engines.drumlanes): features,
the network's layout and blocked convolutions, the pinned weights, peak picking, the fusion and lane rules, 2x kicks,
and the engine folder with its cache. An untrained network and chosen activations stand in for the real weights,
which are never downloaded here."""
import hashlib
import json

import numpy as np
import pytest

from songcharter.engines import drumlanes as L
from songcharter.engines.drumlanes import Settings
from songcharter.importers import read_song

torch = pytest.importorskip("torch")

from songcharter.engines import adtof as AD  # noqa: E402

SR = AD.SAMPLE_RATE


def test_features_are_centred_frames_on_semitone_bands():
    fb = AD.filterbank()
    assert fb.shape == (84, AD.N_FFT // 2) and np.allclose(fb.sum(axis=1), 1.0)
    hz = AD.band_hz()
    assert np.all(np.diff(hz) > 0) and hz[0] < 50 and hz[-1] > 15000
    x = np.zeros(SR, np.float32)
    x[50 * AD.HOP] = 1.0  # a click at 0.5 s
    f = AD.features(x)
    assert f.shape == (1 + SR // AD.HOP, 84) and f.dtype == np.float32
    assert int(np.argmax(f.sum(axis=1))) == 50
    t = np.arange(SR) / SR
    tone = AD.features((0.5 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32))
    assert abs(hz[int(np.argmax(tone[50]))] - 1000) < 60
    with pytest.raises(ValueError, match="mono"):
        AD.features(np.zeros((2, 100), np.float32))


def test_the_network_matches_the_converted_layout_and_runs_in_blocks(tmp_path, monkeypatch):
    torch.manual_seed(0)
    net = AD.frame_rnn().eval()
    keys = list(net.state_dict())
    assert keys[0] == "cnn_blocks.0.0.weight" and "cnn_blocks.1.5.running_var" in keys
    assert "gru_layers.2.weight_hh_l0_reverse" in keys and keys[-1] == "output_layer.bias"
    path = tmp_path / "w.pth"  # the converted file holds float64 tensors under "model_weights"
    torch.save({"model_weights": {k: v.double() for k, v in net.state_dict().items()}, "model_info": {}}, path)
    loaded = AD.load_model(path)
    feat = np.random.default_rng(0).random((300, 84)).astype(np.float32)
    whole = AD.activations(loaded, feat)
    with torch.no_grad():
        direct = net(torch.from_numpy(feat)[None])[0].numpy()
    assert whole.shape == (300, 5) and np.all((whole >= 0) & (whole <= 1))
    assert np.abs(whole - direct).max() < 1e-5
    monkeypatch.setattr(AD, "CNN_BLOCK", 64)  # blocks of 64 frames with 4 frames of context: the same activations
    assert np.abs(AD.activations(loaded, feat) - whole).max() < 1e-5


def test_pinned_weights_are_hash_checked_and_downloaded_once(tmp_path, monkeypatch):
    good = b"weights" * 100
    monkeypatch.setattr(AD, "WEIGHTS", AD.Weights("https://example.invalid/w.pth", hashlib.sha256(good).hexdigest(),
                                                  "w.pth"))
    monkeypatch.delenv("SONGCHARTER_OFFLINE", raising=False)
    asked = []

    def download(url, dest):
        asked.append(url)
        dest.write_bytes(good)

    path = AD.weights_path(tmp_path, download)
    assert path == tmp_path / "adtof" / "w.pth" and path.read_bytes() == good
    assert AD.weights_path(tmp_path, download) == path and asked == ["https://example.invalid/w.pth"]  # reused
    path.write_bytes(b"evil")
    with pytest.raises(RuntimeError, match="delete it"):
        AD.weights_path(tmp_path, download)
    path.unlink()
    with pytest.raises(RuntimeError, match="not the pinned"):
        AD.weights_path(tmp_path, lambda url, dest: dest.write_bytes(b"truncated"))
    assert list((tmp_path / "adtof").iterdir()) == []  # no .part left, nothing renamed
    monkeypatch.setenv("SONGCHARTER_OFFLINE", "1")
    with pytest.raises(FileNotFoundError, match="OFFLINE"):
        AD.weights_path(tmp_path, download)
    assert len(asked) == 1
    monkeypatch.setenv("SONGCHARTER_MODELS", str(tmp_path / "m"))
    assert AD.models_dir() == tmp_path / "m"


def test_peaks_follow_madmoms_note_peak_picking():
    a = np.zeros(400, np.float32)
    a[100], a[102] = 0.9, 0.6       # two peaks two frames apart: the stronger stays
    a[200] = 0.15                   # under the threshold
    a[300:340] = 0.8                # a plateau is no peak after its first frames (the moving average catches up)
    p = AD.peaks(a, 0.22)
    assert 100 in p and 102 not in p and 200 not in p
    assert all(300 <= x < 302 for x in p if x >= 300)
    assert AD.peaks(np.zeros(50, np.float32), 0.2).size == 0


def found(**classes):
    """drumlanes input from {class: [(frame, activation), ...]}."""
    out = {}
    for lab in L.LABELS:
        rows = classes.get(lab, [])
        out[lab] = (np.array([f for f, _ in rows], dtype=np.int64), np.array([s for _, s in rows], dtype=np.float64))
    return out


def pads(hit):
    return [(p, c) for p, c, _ in hit.pads]


NO_GATE = Settings(hat_gate_db=None, beat_s=0.5)


def test_peaks_merge_into_hits_within_30_ms():
    hits = L.merge(found(BD=[(10, 0.9), (50, 0.5)], HH=[(12, 0.4), (53, 0.7)], SD=[(52, 0.3), (52, 0.6)]), 100, 0.030)
    assert [f for f, _ in hits] == [10, 50, 53]  # 12 joins 10; 53 is 30 ms after 50, a hit of its own
    assert hits[0][1] == {"BD": 0.9, "HH": 0.4} and hits[1][1] == {"BD": 0.5, "SD": 0.6}


def test_lane_rules():
    stem = np.zeros(10 * SR, np.float32)
    f = found(BD=[(100, 0.9)],
              HH=[(100, 0.5), (200, 0.9), (400, 0.5)],
              CY=[(100, 0.6), (200, 0.4), (300, 0.9), (325, 0.8), (350, 0.8), (375, 0.8), (400, 0.8), (800, 0.9)],
              SD=[(400, 0.9)], TT=[(400, 0.9), (800, 0.8)])
    hits, counts = L.lanes(f, 100, NO_GATE, 0.5, stem, SR)
    by = {round(h.time * 100): h for h in hits}
    assert pads(by[100]) == [(0, False), (4, True)]  # CY stronger than HH: the cymbal only, alone: a crash
    assert pads(by[200]) == [(2, True)]              # HH stronger: the hi-hat
    assert pads(by[300]) == [(3, True)]              # at least 4 CY hits within +-2 beats (1 s): a ride
    # snare, ride, tom and hat on one hit: the hat loses to the ride, then two hands: the ride and the snare
    assert pads(by[400]) == [(1, False), (3, True)]
    assert pads(by[800]) == [(4, True)]              # an isolated crash on green; its green tom loses the pad
    assert counts["hh_cy_both"] == 3 and counts["hands_dropped"] == 1 and counts["same_pad_dropped"] == 1
    assert counts["ride"] == 5 and counts["cymbals"] == 8 and counts["toms"] == 2


def test_toms_cluster_by_pitch():
    t = np.arange(int(0.08 * SR)) / SR
    stem = np.zeros(8 * SR, np.float32)
    frames = [100, 200, 300, 400, 500, 600]
    for f, hz in zip(frames, (90, 140, 220, 90, 140, 225)):
        a = f * AD.HOP
        stem[a:a + len(t)] = np.sin(2 * np.pi * hz * t)
    hits, _ = L.lanes(found(TT=[(f, 0.9) for f in frames]), 100, NO_GATE, 0.5, stem, SR)
    assert [h.pads[0][0] for h in hits] == [4, 3, 2, 4, 3, 2]  # low green, middle blue, high yellow, all toms
    assert not any(h.pads[0][1] for h in hits)
    assert L.tom_lanes(np.array([100.0, 104.0])) == ["Gtom", "Gtom"]  # one cluster


def test_the_hat_gate_asks_the_drum_stem_for_evidence():
    hz = AD.band_hz()
    mix = np.full((600, 84), 0.5, np.float32)
    stem = mix.copy()
    stem[300:, :] = 0.0                    # the stem falls silent at 3 s: a drumless stretch
    stem[100:106, hz >= 2000] = 0.001      # a hit whose highs the stem lacks (the separation dropped the hat)
    wide = Settings(beat_s=0.5)            # the default: the stem within 40 dB of the mix over +-0.5 s, every band
    level = L.stem_level_db(stem, mix, hz, wide, 100)
    assert abs(level[50]) < 0.1 and level[101] > -1 and np.isneginf(level[400])
    narrow = Settings(beat_s=0.5, hat_gate_db=30.0, hat_gate_hz=2000.0, hat_gate_window=(-0.01, 0.03))
    tight = L.stem_level_db(stem, mix, hz, narrow, 100)
    assert tight[101] < -30 and abs(tight[50]) < 0.1  # read at the hit itself, in the highs
    f = found(HH=[(50, 0.9), (101, 0.9), (400, 0.9)], CY=[(410, 0.9)], BD=[(400, 0.9)])
    quiet = np.zeros(6 * SR, np.float32)
    hits, counts = L.lanes(f, 100, wide, 0.5, quiet, SR, level)
    assert [(round(h.time * 100), pads(h)) for h in hits] == [(50, [(2, True)]), (101, [(2, True)]),
                                                              (400, [(0, False)])]
    assert counts["hat_gate_removed"] == {"HH": 1, "CY": 1}  # the stem's own kick stays
    _, strict = L.lanes(f, 100, narrow, 0.5, quiet, SR, tight)
    assert strict["hat_gate_removed"] == {"HH": 2, "CY": 1}
    with pytest.raises(ValueError, match="stem_level_db"):
        L.lanes(f, 100, wide, 0.5, quiet, SR)


def test_2x_kicks_only_where_kicks_run_faster_than_6_a_second():
    roll = 2.0 + np.arange(16) / 8.0       # 8 kicks a second for 2 s
    burst = np.array([6.0, 6.1, 6.2])      # a quick burst among slow kicks
    slow = np.arange(4.5, 9.0, 0.5)
    times = np.sort(np.concatenate([roll, burst, slow[~np.isin(slow, burst)]]))
    d = L.double_kicks(times, 6.0)
    assert not d[~np.isin(times, roll)].any()
    assert list(d[np.isin(times, roll)]) == [False, True] * 8  # every other one: single-pedal kicks 1/4 s apart
    fast = 1.0 + np.arange(8) / 20.0       # 20 a second: single-pedal kicks every 4th, 0.2 s apart
    assert list(L.double_kicks(fast, 6.0)) == [False, True, True, True, False, True, True, True]
    rows = [(int(round(t * 100)), 0.9) for t in roll]
    hits, counts = L.lanes(found(BD=rows), 100, NO_GATE, 0.5, np.zeros(5 * SR, np.float32), SR)
    assert counts["double_kicks"] == 8 and sum(h.pads[0][2] for h in hits) == 8
    _, none = L.lanes(found(BD=rows), 100, Settings(hat_gate_db=None, beat_s=0.5, double_kick_rate=None), 0.5,
                      np.zeros(5 * SR, np.float32), SR)
    assert none["double_kicks"] == 0


def test_beat_period_of_a_click_track():
    x = np.zeros(20 * SR, np.float32)
    for k in range(40):
        a = int(k * 0.5 * SR)
        x[a:a + 200] = np.hanning(200)
    assert L.beat_period(np.stack([x, x])) == pytest.approx(0.5, rel=0.01)


def test_settings_are_checked():
    for bad in (dict(thresholds=(0.2,) * 4), dict(from_mix=("XX",)), dict(merge_s=0.5), dict(hat_gate_db=0),
                dict(hat_gate_window=(0.1, 0.5)), dict(hat_gate_hz=-1.0), dict(beat_s=3.0), dict(double_kick_rate=-1)):
        with pytest.raises(ValueError):
            Settings(**bad).check()


class Stand:
    """Chosen activations in place of the network's: kick and snare on the stem, hi-hats on the mix."""

    def __init__(self, mix_feat, n):
        self.mix_key = mix_feat.tobytes()
        self.calls = 0
        self.mix, self.stem = np.zeros((n, 5), np.float32), np.zeros((n, 5), np.float32)
        for f in range(50, n - 20, 50):
            self.stem[f, 0 if f % 100 == 0 else 1] = 0.9
            self.mix[f, 3] = 0.8
            self.mix[f + 25, 3] = 0.8
            self.mix[f, 0] = 0.9            # the mix's own kicks are never read

    def __call__(self, model, feat, device="cpu"):
        self.calls += 1
        return self.mix if feat.tobytes() == self.mix_key else self.stem


def song(seconds=6.0):
    rng = np.random.default_rng(1)
    n = int(seconds * SR)
    mix = (0.1 * rng.standard_normal((2, n))).astype(np.float32)
    drums = (0.5 * mix + 0.02 * rng.standard_normal((2, n))).astype(np.float32)
    return mix, drums


def test_the_engine_writes_a_folder_the_importer_reads_and_caches_it(tmp_path, monkeypatch):
    mix, drums = song()
    torch.manual_seed(0)
    net = AD.frame_rnn()
    stand = Stand(AD.features(mix.mean(axis=0)), 1 + mix.shape[1] // AD.HOP)
    monkeypatch.setattr(AD, "activations", stand)
    st = Settings(hat_gate_db=None, beat_s=0.5)
    r = AD.generate(mix, drums, tmp_path / "out", st, model=net)
    assert not r.cached and stand.calls == 2
    assert sorted(p.name for p in r.folder.iterdir()) == ["activations.npz", "engine.json", "notes.chart", "song.ini"]
    ini = (r.folder / "song.ini").read_text(encoding="utf-8")
    assert "pro_drums = True" in ini
    chart = r.chart.read_text(encoding="utf-8")
    assert "Resolution = 480" in chart and "B 120000" in chart and "[ExpertDrums]" in chart
    assert "[HardDrums]" not in chart
    s = read_song(r.folder)
    assert list(s.parts) == [("drums", "expert")]
    hits = s.parts[("drums", "expert")].notes
    kicks = [h.time for h in hits if h.pad == 0]
    hats = [h.time for h in hits if h.pad == 2]
    assert kicks == pytest.approx([f / 100 for f in range(100, 551, 100)], abs=0.0011)
    assert len(hats) == 2 * len(range(50, 551, 50)) and all(h.cymbal for h in hits if h.pad == 2)
    info = json.loads((r.folder / "engine.json").read_text(encoding="utf-8"))
    assert info["key"] == r.info["key"] and info["counts"]["peaks"]["HH"] == len(hats)
    assert info["settings"]["hat_gate_db"] is None and info["beat_from"] == "settings"
    assert info["chart"] == {"resolution": 480, "bpm": 120.0, "difficulties": ["expert"]}

    again = AD.generate(mix, drums, tmp_path / "out", st, model=net)
    assert again.cached and stand.calls == 2 and again.info == info
    other = AD.generate(mix, drums, tmp_path / "out", Settings(hat_gate_db=None, beat_s=0.5, merge_s=0.0), model=net)
    assert not other.cached and other.info["activations_cached"] and stand.calls == 2  # lanes only
    fresh = AD.generate(mix, drums, tmp_path / "fresh", st, model=net)
    assert fresh.chart.read_bytes() == r.chart.read_bytes()  # deterministic
    assert AD.cache_key(mix[:, :-1], drums[:, :-1], "w", st) != AD.cache_key(mix, drums, "w", st)
    with pytest.raises(ValueError, match="same shape"):
        AD.generate(mix, drums[:, :-1], tmp_path / "bad", st, model=net)


def test_the_engine_drops_the_mix_hats_where_the_stem_is_silent(tmp_path, monkeypatch):
    mix, drums = song()
    drums[:, int(3.1 * SR):] = 0.0  # the drums stop at 3.1 s; the mix's "hats" go on
    stand = Stand(AD.features(mix.mean(axis=0)), 1 + mix.shape[1] // AD.HOP)
    monkeypatch.setattr(AD, "activations", stand)
    torch.manual_seed(0)
    r = AD.generate(mix, drums, tmp_path / "out", Settings(beat_s=0.5), model=AD.frame_rnn())
    hats = [h.time for h in read_song(r.folder).parts[("drums", "expert")].notes if h.pad == 2]
    # a hat stays while the stem plays within half a second of it
    assert hats and max(hats) < 3.6 and r.info["counts"]["hat_gate_removed"]["HH"] == len(range(375, 576, 25))
