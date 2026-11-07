"""A chart you can hear (songcharter.listen, `songcharter listen`) on made-up charts and audio: each note's tone starts
at its chart time (through the chart's tempo map and song.ini's delay, at 44.1 kHz), lanes are their pitches, a
chord holds its pitches, a sustain lasts to its end, HOPOs and taps differ from strums, the drum pads differ, the
song plays 12 dB down or not at all, nothing clips, the same folder gives the same bytes, the page's cache, and the
command's exit codes."""
import wave
from pathlib import Path

import numpy as np
import pytest

from songcharter import audio as A
from songcharter import cli
from songcharter import listen as L
from songcharter.chart import Chart, DrumHit, FretNote, SongInfo, Track, write_chart
from songcharter.errors import InputError
from songcharter.tempo import Tempo, TempoMap, TimeSignature

SR = 44100
RES = 192
# the lanes' pitches, written out here (not read from listen.py): green C5, red E5, yellow G5, blue B5, orange D6
GUITAR_HZ = (523.25, 659.26, 783.99, 987.77, 1174.66)
OPEN_HZ = 392.00   # G4


def tick(seconds):
    """At 120 BPM (the songs below, before any tempo change): a beat is 0.5 s, RES ticks."""
    return int(round(seconds * 2 * RES))


def folder(path: Path, guitar=(), bass=(), drums=(), hard=(), tempos=None, seconds=8.0, song=None, ini=""):
    """A made-up song folder: notes.chart (Expert guitar, bass and drums, Hard guitar), song.ini and song.ogg
    (`song`: a stereo array; default a quiet 220 Hz sine; False: no song.ogg)."""
    path.mkdir(parents=True, exist_ok=True)
    tm = TempoMap(RES, tempos or [Tempo(0, 120000)], [TimeSignature(0, 4)])
    tracks = [Track("Expert", inst, list(notes)) for inst, notes in
              (("Single", guitar), ("DoubleBass", bass), ("Drums", drums)) if notes]
    tracks += [Track("Hard", "Single", list(hard))] if hard else []
    chart = Chart(SongInfo("Made-Up Song", "Made-Up Band", charter="songcharter"), tm, [(0, "intro")], tracks)
    (path / "notes.chart").write_text(write_chart(chart), encoding="utf-8", newline="")
    (path / "song.ini").write_text(f"[song]\nname = Made-Up Song\ncharter = songcharter\n{ini}", encoding="utf-8")
    if song is not False:
        if song is None:
            t = np.arange(int(seconds * SR)) / SR
            y = 0.1 * np.sin(2 * np.pi * 220 * t)
            song = np.stack([y, y]).astype(np.float32)
        A.encode_ogg(song, path / "song.ogg")
    return path


def wav(rendered_or_path):
    """A WAV's samples (2, n) as float, and its sample rate."""
    with wave.open(str(rendered_or_path), "rb") as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
    assert ch == 2 and width == 2
    return data.reshape(-1, 2).T.astype(np.float64) / 32767, sr


def tones(path, tmp_path, part="guitar", difficulty="expert", name="t.wav"):
    """The part's tones alone, written as a WAV and read back: (mono samples, sample rate)."""
    r = L.render(path, part, difficulty, tones_only=True)
    out = L.write(r.audio, tmp_path / name)
    y, sr = wav(out)
    return y.sum(axis=0), sr


def onset(y, near, sr=SR, before=0.05):
    """The first sample that sounds from `before` seconds ahead of `near`, in seconds."""
    i = int((near - before) * sr)
    assert not np.any(y[i - 10:i]), "a sound before the window"
    return (i + int(np.argmax(np.abs(y[i:]) > 0))) / sr


def peak_hz(y, start, seconds=0.25, sr=SR):
    """The strongest frequency in a window (Hann, zero-padded to 1 Hz bins)."""
    seg = y[int(start * sr):int((start + seconds) * sr)]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), sr))
    return float(np.argmax(spec))


def level_at(y, hz, start, seconds=0.05, sr=SR):
    """The amplitude of the `hz` component in a window (a DFT bin on a Hann window)."""
    seg = y[int(start * sr):int((start + seconds) * sr)]
    t = np.arange(len(seg)) / sr
    w = np.hanning(len(seg))
    return float(2 * abs(np.sum(seg * w * np.exp(-2j * np.pi * hz * t))) / np.sum(w))


def rms(y):
    return float(np.sqrt(np.mean(y ** 2))) if len(y) else 0.0


def test_a_tone_starts_at_its_chart_time_through_the_tempo_map_and_the_delay(tmp_path):
    # 120 BPM, then 90 BPM from beat 4: a note on beat 6 is at 2 + 2 x 2/3 s
    tempos = [Tempo(0, 120000), Tempo(4 * RES, 90000)]
    notes = [FretNote(RES, (0,)), FretNote(3 * RES + 37, (2,)), FretNote(6 * RES, (4,)), FretNote(9 * RES, (1,))]
    want = [0.5, 1.5 + 37 / RES * 0.5, 2 + 2 * 2 / 3, 2 + 5 * 2 / 3]
    song = folder(tmp_path / "s", guitar=notes, tempos=tempos)
    y, sr = tones(song, tmp_path)
    assert sr == SR
    for t in want:
        assert 0 <= onset(y, t) - t <= 0.002, t
    # song.ini's delay moves the notes later, as Clone Hero plays them
    late = folder(tmp_path / "late", guitar=notes, tempos=tempos, ini="delay = 250\n")
    y, _ = tones(late, tmp_path, name="late.wav")
    for t in want:
        assert 0 <= onset(y, t + 0.25) - (t + 0.25) <= 0.002, t
    # the drums too
    drums = folder(tmp_path / "d", drums=[DrumHit(RES, 0), DrumHit(6 * RES, 1)], tempos=tempos)
    y, _ = tones(drums, tmp_path, "drums", name="d.wav")
    for t in (0.5, 2 + 2 * 2 / 3):
        assert 0 <= onset(y, t) - t <= 0.002, t


def test_the_render_is_song_oggs_length_and_a_note_after_it_is_left_out(tmp_path):
    song = folder(tmp_path / "s", guitar=[FretNote(tick(1.0), (0,)), FretNote(tick(9.0), (1,))], seconds=5.0)
    n = A.decode(song / "song.ogg").shape[1]
    for only in (False, True):
        r = L.render(song, tones_only=only)
        assert r.audio.shape == (2, n) and r.audio.dtype == np.float32
        assert (r.notes, r.left_out) == (1, 1)
    assert "1 notes at or after the end of song.ogg left out" in L.summary(r)
    # without song.ogg, the notes alone run to the last note and 2 s more
    bare = folder(tmp_path / "bare", guitar=[FretNote(tick(1.0), (0,), tick(1.0))], song=False)
    r = L.render(bare, tones_only=True)
    assert r.audio.shape[1] == round(4.0 * SR)
    with pytest.raises(InputError, match="no song.ogg"):
        L.render(bare)


def test_lanes_are_their_pitches_and_the_bass_an_octave_down(tmp_path):
    lanes = [(0,), (1,), (2,), (3,), (4,), (7,)]
    notes = [FretNote(tick(1.0 + i), f) for i, f in enumerate(lanes)]
    song = folder(tmp_path / "s", guitar=notes, bass=notes)
    want = list(GUITAR_HZ) + [OPEN_HZ]
    for part, scale in (("guitar", 1.0), ("bass", 0.5)):
        y, _ = tones(song, tmp_path, part, name=f"{part}.wav")
        got = [peak_hz(y, 1.0 + i) for i in range(len(lanes))]
        assert got == pytest.approx([hz * scale for hz in want], abs=2), part


def test_lanes_are_panned_green_left_to_orange_right(tmp_path):
    song = folder(tmp_path / "s", guitar=[FretNote(tick(1.0 + i), (f,)) for i, f in enumerate(range(5))])
    y, _ = wav(L.write(L.render(song, tones_only=True).audio, tmp_path / "t.wav"))
    balance = [rms(y[1, int((1 + i) * SR):int((1.3 + i) * SR)]) / rms(y[0, int((1 + i) * SR):int((1.3 + i) * SR)])
               for i in range(5)]
    assert balance == sorted(balance) and balance[0] < 0.7 and balance[2] == pytest.approx(1, abs=0.01)
    assert balance[4] > 1.4


def test_a_chord_holds_its_pitches_together(tmp_path):
    song = folder(tmp_path / "s", guitar=[FretNote(tick(1.0), (0, 2, 4)), FretNote(tick(3.0), (0,))])
    y, _ = tones(song, tmp_path)
    got = {hz: level_at(y, hz, 1.005, 0.1) for hz in GUITAR_HZ}
    there = [got[GUITAR_HZ[i]] for i in (0, 2, 4)]
    assert max(there) < 1.5 * min(there)                      # the three as loud as each other
    assert max(got[GUITAR_HZ[1]], got[GUITAR_HZ[3]]) < 0.05 * min(there)   # and nothing else
    # each pitch of a 3-note chord 1/sqrt(3) as loud as a note alone
    alone = level_at(y, GUITAR_HZ[0], 3.005, 0.1)
    assert got[GUITAR_HZ[0]] / alone == pytest.approx(1 / np.sqrt(3), rel=0.1)


def test_a_sustain_holds_its_tone_quieter_to_its_end(tmp_path):
    hz = GUITAR_HZ[2]
    song = folder(tmp_path / "s", guitar=[FretNote(tick(1.0), (2,), tick(2.0)), FretNote(tick(5.0), (2,))])
    y, _ = tones(song, tmp_path)
    attack = level_at(y, hz, 1.0, 0.02)
    held = [level_at(y, hz, 1.0 + s) for s in (0.8, 1.4, 1.93)]   # the last window ends 20 ms before its end
    assert all(0.15 * attack < h < 0.6 * attack for h in held)     # held, quieter than the attack
    assert held[0] == pytest.approx(held[2], rel=0.1)              # steady
    assert rms(y[int(3.06 * SR):int(3.5 * SR)]) == 0               # released 40 ms after its end
    # the same note without a sustain has died away by then
    assert level_at(y, hz, 5.0 + 0.8) < 0.02 * attack


def test_hopos_and_taps_are_shorter_and_softer_than_strums(tmp_path):
    hz = GUITAR_HZ[1]
    # far apart, so each is naturally a strum: the flip makes one a HOPO, the tap flag a tap
    notes = [FretNote(tick(1.0), (1,)), FretNote(tick(2.0), (1,), flip=True), FretNote(tick(3.0), (1,), tap=True),
             FretNote(tick(4.0), (2,)), FretNote(tick(4.125), (1,))]   # a natural HOPO: an 8th after another fret
    song = folder(tmp_path / "s", guitar=notes)
    y, _ = tones(song, tmp_path)

    def shape(t):
        seg = np.abs(y[int(t * SR):int((t + 0.6) * SR)])
        top = seg.max()
        rise = np.argmax(seg > 0.5 * top) / SR
        last = len(seg) - np.argmax(seg[::-1] > 0.05 * top)
        return top, rise, last / SR

    strum, hopo, tap = shape(1.0), shape(2.0), shape(3.0)
    assert hopo[0] < 0.6 * strum[0]                  # softer
    assert strum[1] < 0.0015 < 0.003 < hopo[1]       # a slower attack
    assert hopo[2] < 0.6 * strum[2]                  # shorter
    assert tap == pytest.approx(hopo, rel=0.05)      # a tap as a HOPO
    natural = level_at(y, hz, 4.125, 0.02)
    assert natural == pytest.approx(level_at(y, hz, 2.0, 0.02), rel=0.1)
    assert natural < 0.6 * level_at(y, hz, 1.0, 0.02)


def test_the_drum_pads_sound_different(tmp_path):
    pads = [DrumHit(tick(1.0), 0), DrumHit(tick(3.0), 1), DrumHit(tick(5.0), 2), DrumHit(tick(7.0), 3),
            DrumHit(tick(9.0), 4), DrumHit(tick(11.0), 2, cymbal=True), DrumHit(tick(13.0), 3, cymbal=True),
            DrumHit(tick(15.0), 4, cymbal=True), DrumHit(tick(17.0), 1, accent=True),
            DrumHit(tick(19.0), 1, ghost=True)]
    song = folder(tmp_path / "s", drums=pads, seconds=21.0)
    y, _ = tones(song, tmp_path, "drums")

    def window(i, seconds=1.9):
        return y[int((1 + 2 * i) * SR):int((1 + 2 * i + seconds) * SR)]

    def centroid(seg):   # of the power
        power = np.abs(np.fft.rfft(seg)) ** 2
        f = np.fft.rfftfreq(len(seg), 1 / SR)
        return float(np.sum(f * power) / np.sum(power))

    def length(seg):
        env = np.abs(seg)
        return (len(env) - np.argmax(env[::-1] > 0.05 * env.max())) / SR

    kick, snare, hi_tom, mid_tom, low_tom, hihat, ride, crash, accent, ghost = (window(i) for i in range(10))
    assert centroid(kick) < 200
    assert [peak_hz(y, 1 + 2 * i, 0.2) for i in (2, 3, 4)] == pytest.approx([294, 220, 165], rel=0.08)
    assert 1500 < centroid(snare) < 7000
    assert all(centroid(c) > 5000 for c in (hihat, ride, crash))
    assert length(hihat) < 0.2 < length(ride) < length(crash)
    assert np.abs(accent).max() > 1.2 * np.abs(snare).max() > 1.2 ** 2 * np.abs(ghost).max()
    # a double kick (Expert+) is a kick
    dk = folder(tmp_path / "dk", drums=[DrumHit(tick(1.0), 0, double_kick=True)], seconds=3.0)
    y2, _ = tones(dk, tmp_path, "drums", name="dk.wav")
    assert np.allclose(y2[SR:2 * SR], y[SR:2 * SR], atol=1e-4)


def test_the_song_plays_12_db_down_under_the_tones_or_not_at_all(tmp_path):
    t = np.arange(int(4 * SR)) / SR
    y = 0.4 * np.sin(2 * np.pi * 3000 * t)
    song = folder(tmp_path / "s", guitar=[FretNote(tick(1.0), (0,))], song=np.stack([y, -y]).astype(np.float32))
    music = A.decode(song / "song.ogg")
    mix = L.render(song)
    alone = L.render(song, tones_only=True)
    assert mix.turned_down_db == 0 and alone.turned_down_db == 0
    under = mix.audio.astype(np.float64) - alone.audio
    assert np.allclose(under, music * 10 ** (-12 / 20), atol=1e-6)
    quiet = slice(int(2.5 * SR), int(3.5 * SR))           # after the note
    assert not np.any(alone.audio[:, quiet])
    assert rms(mix.audio[0, quiet]) == pytest.approx(0.4 / np.sqrt(2) * 10 ** (-12 / 20), rel=0.02)


def test_nothing_clips(tmp_path):
    loud = np.sign(np.sin(2 * np.pi * 100 * np.arange(int(4 * SR)) / SR)).astype(np.float32)   # a square at 0 dBFS
    chords = [FretNote(tick(0.5 + 0.0625 * i), (0, 1, 2, 4), tick(0.5) * (i % 2)) for i in range(40)]
    # a busy beat: the kick on every beat, the snare accented on 2 and 4, 16th hi-hats, a crash on every downbeat
    hits = [DrumHit(tick(0.5 + 0.125 * i), 2, cymbal=True) for i in range(24)]
    hits += [DrumHit(tick(0.5 + 0.5 * b), 0) for b in range(6)]
    hits += [DrumHit(tick(1.0 + b), 1, accent=True) for b in range(3)]
    hits += [DrumHit(tick(0.5 + 2 * m), 4, cymbal=True) for m in range(2)]
    song = folder(tmp_path / "s", guitar=chords, drums=hits, song=np.stack([loud, loud]))
    half = folder(tmp_path / "half", drums=hits, song=np.stack([loud, loud]) / 2)
    # the levels leave room for a song at 0 dBFS (a square: at its peak all the time) under 16th-note chords, and
    # for one at -6 dBFS under a busy beat
    for where, part in ((song, "guitar"), (half, "drums")):
        r = L.render(where, part)
        assert np.abs(r.audio).max() <= L.CEILING and r.turned_down_db == 0, part
        assert "clips" not in L.summary(r)
    # past them (the song at full level here), the whole render is turned down to the ceiling, once
    r = L.render(song, song_db=0.0)
    assert np.abs(r.audio).max() == pytest.approx(L.CEILING, abs=1e-6) and r.turned_down_db > 0
    assert "so nothing clips" in L.summary(r)
    alone, music = L.render(song, tones_only=True).audio, A.decode(song / "song.ogg")
    assert np.allclose(r.audio, (alone + music) * 10 ** (-r.turned_down_db / 20), atol=1e-5)   # no note limited


def test_the_same_folder_renders_the_same_bytes(tmp_path):
    notes = [FretNote(tick(0.5 + 0.25 * i), ((0,), (1, 3), (7,))[i % 3], tick(0.2) * (i % 2)) for i in range(12)]
    hits = [DrumHit(tick(0.5 + 0.25 * i), i % 5, cymbal=i % 5 > 1 and i % 2 == 0) for i in range(12)]
    song = folder(tmp_path / "s", guitar=notes, drums=hits, seconds=5.0)
    for part in ("guitar", "drums"):
        for ext in (".ogg", ".wav"):
            a = L.write(L.render(song, part).audio, tmp_path / f"a{ext}").read_bytes()
            b = L.write(L.render(song, part).audio, tmp_path / f"b{ext}").read_bytes()
            assert a == b, (part, ext)
    assert (tmp_path / "a.ogg").read_bytes()[:4] == b"OggS" and A.decode(tmp_path / "a.ogg").shape[1] > 4 * SR
    assert not list(tmp_path.glob(".*.part"))


def test_what_the_chart_offers_and_the_refusals(tmp_path):
    song = folder(tmp_path / "s", guitar=[FretNote(0, (0,))], drums=[DrumHit(0, 0)], hard=[FretNote(0, (1,))])
    assert L.available(song) == {"guitar": ["expert", "hard"], "drums": ["expert"]}
    with pytest.raises(InputError, match=r"no bass on Expert \(it has guitar on Expert, guitar on Hard, drums on"):
        L.render(song, "bass")
    with pytest.raises(InputError, match="no drums on Medium"):
        L.render(song, "drums", "medium")
    with pytest.raises(InputError, match="the part is one of"):
        L.render(song, "keys")
    with pytest.raises(InputError, match="the level is one of"):
        L.render(song, "guitar", "expert+")
    with pytest.raises(InputError, match="not a song folder"):
        L.render(tmp_path / "nothing")
    (tmp_path / "empty").mkdir()
    with pytest.raises(InputError, match="no notes.chart or notes.mid"):
        L.available(tmp_path / "empty")
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "notes.chart").write_text("[Song]\n{\n}\n", encoding="utf-8")
    with pytest.raises(InputError, match="cannot read the chart"):
        L.available(tmp_path / "broken")
    with pytest.raises(InputError, match="must end .ogg or .wav"):
        L.write(np.zeros((2, 10), np.float32), tmp_path / "x.mp3")


def test_the_pages_cache_renders_once_per_chart(tmp_path, monkeypatch):
    song = folder(tmp_path / "s", guitar=[FretNote(tick(1.0), (0,))], drums=[DrumHit(tick(1.0), 0)], seconds=3.0)
    cache = tmp_path / "work" / "listen"
    calls = []
    render = L.render
    monkeypatch.setattr(L, "render", lambda *a, **k: calls.append(a[1:]) or render(*a, **k))
    first, was = L.cached(song, cache, "guitar", "expert")
    assert not was and first.parent == cache and first.name.startswith("guitar-expert-")
    again, was = L.cached(song, cache, "guitar", "expert")
    assert was and again == first and calls == [("guitar", "expert")]
    drums, was = L.cached(song, cache, "drums", "expert")
    assert not was and drums != first
    # a new chart of the same song (the same work folder): rendered again, and the older render goes
    folder(tmp_path / "s", guitar=[FretNote(tick(1.5), (1,))], drums=[DrumHit(tick(1.0), 0)], seconds=3.0)
    new, was = L.cached(song, cache, "guitar", "expert")
    assert not was and new != first and not first.exists() and drums.exists()
    assert sorted(p.name for p in cache.iterdir()) == sorted([new.name, drums.name])
    with pytest.raises(InputError):
        L.cached(song, cache, "../guitar", "expert")
    assert len(calls) == 3


def test_songcharter_listen(tmp_path, monkeypatch, capsys):
    song = folder(tmp_path / "Made-Up Band - Song", guitar=[FretNote(tick(1.0), (0,))], drums=[DrumHit(0, 0)],
                  seconds=3.0)
    before = sorted(p.name for p in song.iterdir())
    here = tmp_path / "here"
    here.mkdir()
    monkeypatch.chdir(here)
    assert cli.main(["listen", str(song)]) == 0
    out = capsys.readouterr().out
    made = here / "Made-Up Band - Song-guitar-expert.ogg"
    assert made.is_file() and str(made) in out and "listen: guitar on Expert, 1 notes over the song at -12 dB" in out
    assert cli.main(["listen", str(song), "--part", "drums", "--out", str(here)]) == 0
    assert (here / "Made-Up Band - Song-drums-expert.ogg").is_file()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))   # a quoted ~ (the shell left it): the home folder's
    (tmp_path / "home").mkdir()
    assert cli.main(["listen", str(song), "--part", "drums", "--out", "~"]) == 0
    assert (tmp_path / "home" / "Made-Up Band - Song-drums-expert.ogg").is_file()
    assert cli.main(["listen", str(song), "--tones-only", "--out", str(here / "t.wav")]) == 0
    assert "the notes alone" in capsys.readouterr().out and wav(here / "t.wav")[1] == SR
    for args, why in ((["--part", "bass"], "no bass on Expert"), (["--difficulty", "hard"], "no guitar on Hard"),
                      (["--out", str(song / "x.ogg")], "inside the song folder"),
                      (["--out", str(song)], "inside the song folder"),
                      (["--out", str(here / "x.mp3")], "must end .ogg or .wav")):
        assert cli.main(["listen", str(song), *args]) == 2, args
        assert why in capsys.readouterr().err, args
    assert cli.main(["listen", str(tmp_path / "nothing")]) == 2
    assert "not a song folder" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e:
        cli.main(["listen", str(song), "--part", "keys"])
    assert e.value.code == 2
    assert sorted(p.name for p in song.iterdir()) == before          # nothing was written into the song folder

    def bug(*a, **k):
        raise RuntimeError("made-up bug")
    monkeypatch.setattr(L, "render", bug)
    assert cli.main(["listen", str(song)]) == 3
    assert "made-up bug" in capsys.readouterr().err
