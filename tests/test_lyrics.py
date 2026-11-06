"""Lyrics (songcharter.lyrics, songcharter.engines.lyrics and the pipeline's lyrics stage), with made-up words only
and audio generated here: the text model and what Clone Hero shows, the events in [Events], the phrases split at
lines and long rests, the grid, the cache, the fallback when the aligner is missing or fails, and that no word goes
anywhere but notes.chart. No model runs and none is downloaded: a stand-in aligner times the syllables from the
generated vocal stem; the forced alignment itself runs on made-up emissions when torchaudio is installed."""
import json
import re
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from songcharter import lyrics as L
from songcharter.assemble import find_scan_chart, lyric_rules, verify_folder
from songcharter.chart import Chart, SongInfo, write_chart
from songcharter.cli import main, read_lyrics
from songcharter.engines import lyrics as E
from songcharter.errors import InputError
from songcharter.importers import _chart_sections, _decode
from songcharter.pipeline import Options, chart
from songcharter.quantize import RULES
from songcharter.tempo import Tempo, TempoMap

sys.path.insert(0, str(Path(__file__).parent))
from test_pipeline import SR, standins, write_song  # noqa: E402

TEXT = ("zorp blen-dak quiv\n"
        "fim, wob's 12 — 東京\n"
        "\n"
        "[Glorp]\n"
        "dree café-nu \"vex\" ta#ko\n"
        "... smee_lo plin-\n")
WORDS = ("zorp", "blen", "quiv", "dree", "smee", "plin", "Glorp", "tako", "wob's", "caf\u00e9")  # TEXT's, distinct
VOCAL_SPANS = ((16.5, 32.5), (48.5, 62.0))   # where test_pipeline's generated song has its vocal tone


def expected_lines(text: str) -> list[str]:
    """What Clone Hero should show for each line of `text`, worked out on its own from the rules: whitespace and `_`
    split words, `"` shows as `'`, the markup symbols are left out, so are hyphens at a word's ends and doubled
    ones; a heading or blank line shows nothing."""
    out = []
    for line in text.splitlines():
        if not line.strip() or re.fullmatch(r"\s*\[[^\[\]]*\]\s*", line):
            continue
        tokens = []
        for tok in line.replace("_", " ").split():
            tok = "".join(c for c in tok.replace('"', "'") if c not in "+=#^*%$/§<>")
            tok = re.sub("-+", "-", tok.strip("-"))
            if tok:
                tokens.append(tok)
        if any(any(c.isalnum() for c in t) for t in tokens):
            out.append(" ".join(tokens))
    return out


def tm120(resolution: int = 192) -> TempoMap:
    return TempoMap(resolution, [Tempo(0, 120000)])


def even_starts(lyrics: L.Lyrics, first: float = 3.0, step: float = 0.5) -> list[float]:
    return [first + step * i for i in range(len(lyrics.syllables))]


def written_events(phrases, tm: TempoMap, sections=()) -> list[str]:
    """[Events] of a chart holding the phrases, as written and read back from the text."""
    text = write_chart(Chart(SongInfo("t", "a"), tm, list(sections), [], L.events(phrases)))
    return _chart_sections(_decode(text.encode("utf-8")))["Events"]


# ------------------------------------------------------------------------------------------------ the text

def test_lines_gaps_words_and_syllables():
    x = L.parse(TEXT)
    assert x.lines == 4 and x.words == 14
    assert [s.text for s in x.syllables][:4] == ["zorp", "blen", "dak", "quiv"]
    assert [s.last for s in x.syllables][:4] == [True, False, True, True]   # blen-dak: two syllables, one word
    assert [L.event_text(s) for s in x.syllables][1:3] == ["blen=", "dak"]   # '=' shows the hyphen and joins
    gaps = [i for i, s in enumerate(x.syllables) if s.gap]
    assert [x.syllables[i].text for i in gaps] == ["zorp", "dree"]           # the text's start, the blank + heading
    assert "Glorp" not in " ".join(s.text for s in x.syllables)              # a [heading] is not sung


def test_markup_and_punctuation():
    x = L.parse(TEXT)
    shown = [s.text for s in x.syllables]
    assert "fim," in shown and "wob's" in shown and "'vex'" in shown         # " shows as '
    assert "12 —" in shown                                              # a dash rides with the word before
    assert "ta" not in shown and "tako" in shown                             # '#' left out
    assert "... smee" in shown and "lo" in shown and "plin" in shown         # '_' splits, edge hyphen left out
    assert x.dropped == 2 + 1 + 1                                            # two quotes, '#', plin's hyphen
    assert not any(s.text.endswith(("-", "=")) for s in x.syllables)


def test_every_markup_symbol_is_left_out_of_the_display():
    """Each symbol Clone Hero acts on, in made-up words, against the display written out by hand."""
    text = 'zo+rp bl=en d#ak qu^iv f*im w%ob dr$ee ca/fe sm\u00a7ee <pl>in ta_ko "vex" -gl-'
    x = L.parse(text)
    assert [s.text for s in x.syllables] == ["zorp", "blen", "dak", "quiv", "fim", "wob", "dree", "cafe", "smee",
                                             "plin", "ta", "ko", "'vex'", "gl"]
    assert x.dropped == 11 + 2 + 2          # + = # ^ * % $ / \u00a7 < >, the two quotes changed, gl's two hyphens
    phrases, _ = L.place(x, even_starts(x), tm120())
    assert L.shown_lines(L.read_events(written_events(phrases, tm120()))) == [
        "zorp blen dak quiv fim wob dree cafe smee plin ta ko 'vex' gl"]


def test_spelling_for_the_aligner():
    assert L.spelling("Café") == "cafe" and L.spelling("wob’s") == "wob's"
    assert L.spelling("12") == "twelve" and L.spelling("1999") == "onethousandninehundredninetynine"
    assert L.spelling("zib&zab") == "zibandzab" and L.spelling("東京") == ""
    x = L.parse(TEXT)
    assert x.word_spellings()[5] == "twelve" and x.word_spellings()[6] == ""   # 東京: a word the aligner can't spell


def test_no_text_left_out_or_duplicated(tmp_path):
    """Every line shows exactly as typed (the markup rules apart), once, in order, read back from notes.chart."""
    texts = [TEXT, "zorp\n", "a-b-c d--e -f g- - h\n\nh","x_y  z\r\nq — r\rs", "[Hed]\n\n\nmeep morp\n[Two]\nlast"]
    for text in texts:
        x = L.parse(text)
        assert not any(s.text.endswith(("-", "=")) for s in x.syllables)   # the game would join the next one
        phrases, stats = L.place(x, even_starts(x), tm120())
        assert stats["rest_splits"] == 0
        events = written_events(phrases, tm120())
        assert L.shown_lines(L.read_events(events)) == expected_lines(text), text
        shown = " ".join(L.shown_lines(L.read_events(events)))
        assert sorted(shown.split()) == sorted(" ".join(expected_lines(text)).split())


def test_a_text_with_no_word():
    assert L.parse("\n  \n[Hed]\n... —\n").syllables == ()
    with pytest.raises(InputError, match="no word"):
        Options(lyrics="\n[Hed]\n").check()
    with pytest.raises(InputError, match="lyrics is a text"):
        Options(lyrics=["zorp"]).check()
    Options(lyrics="zorp").check()


# ------------------------------------------------------------------------------------------------ the chart

def test_event_format():
    x = L.parse("zorp blen-dak\nquiv fim")
    tm = tm120()
    phrases, _ = L.place(x, [3.0, 3.5, 3.75, 6.0, 6.5], tm)
    lines = written_events(phrases, tm, sections=[(0, "Intro"), (phrases[1].start, "Verse")])
    lyric = [l for l in lines if "lyric" in l or "phrase" in l]
    kinds = [re.fullmatch(r'\d+ = E "(phrase_start|phrase_end|lyric) ?.*"', l)[1] for l in lyric]
    assert kinds == ["phrase_start", "lyric", "lyric", "lyric", "phrase_end",
                     "phrase_start", "lyric", "lyric", "phrase_end"]
    assert lyric[1:4] == [f'{phrases[0].syllables[0][0]} = E "lyric zorp"',
                          f'{phrases[0].syllables[1][0]} = E "lyric blen="',
                          f'{phrases[0].syllables[2][0]} = E "lyric dak"']
    ticks = [int(l.split(" = ")[0]) for l in lines]
    assert ticks == sorted(ticks)
    # a section on a phrase's tick comes first; a phrase_end on the next phrase's start tick comes before it
    at = [l for l in lines if l.startswith(f"{phrases[1].start} ")]
    assert at[0].endswith('"section Verse"')
    for p in phrases:
        ts = [t for t, _ in p.syllables]
        assert p.start <= ts[0] and ts == sorted(set(ts)) and ts[-1] < p.end
    assert phrases[0].end <= phrases[1].syllables[0][0] and phrases[1].start >= phrases[0].end


def test_events_on_one_tick_keep_their_order():
    rows = L.events([L.Phrase(0, 96, ((0, "zorp"), (48, "blen"))), L.Phrase(96, 192, ((96, "dak"),))])
    lines = written_events([L.Phrase(0, 96, ((0, "zorp"), (48, "blen"))), L.Phrase(96, 192, ((96, "dak"),))], tm120())
    assert lines == ['0 = E "phrase_start"', '0 = E "lyric zorp"', '48 = E "lyric blen"', '96 = E "phrase_end"',
                     '96 = E "phrase_start"', '96 = E "lyric dak"', '192 = E "phrase_end"']
    assert len(rows) == 7


def test_sections_alone_are_written_as_before():
    """With no lyrics, [Events] is exactly the sorted section lines it always was."""
    sections = [(768, "Verse 1"), (0, "Intro"), (768, "A"), (1536, 'Say "hi"')]
    text = write_chart(Chart(SongInfo("t", "a"), tm120(), sections, []))
    events = _chart_sections(_decode(text.encode()))["Events"]
    assert events == [f'{t} = {s}' for t, s in sorted((t, f'E "section {n.replace(chr(34), "`")}"')
                                                        for t, n in sections)]


def test_phrases_split_at_lines_and_long_rests():
    x = L.parse("zorp blen quiv\nfim")
    tm = tm120()
    gap = L.REST_SPLIT_S
    split, stats = L.place(x, [3.0, 3.5, 3.5 + gap + 0.05, 3.5 + gap + 1.0], tm)
    assert [len(p.syllables) for p in split] == [2, 1, 1] and stats["rest_splits"] == 1
    whole, stats = L.place(x, [3.0, 3.5, 3.5 + gap - 0.05, 3.5 + gap + 1.0], tm)
    assert [len(p.syllables) for p in whole] == [3, 1] and stats["rest_splits"] == 0
    # the reference charts' medians: phrase_start about 0.15 s ahead, phrase_end about 0.7 s after the last start
    p = whole[0]
    assert abs(tm.tick_to_sec(p.syllables[0][0]) - tm.tick_to_sec(p.start) - L.PHRASE_LEAD_S) < 0.07
    assert p.end <= whole[1].syllables[0][0]


def test_syllables_are_quantized_onto_the_grid():
    x = L.parse("zorp blen dak quiv fim wob")
    tm = tm120(192)
    starts = [3.0 + 0.125 * k + 0.006 for k in range(6)]   # 16ths at 120 BPM, 6 ms late
    phrases, stats = L.place(x, starts, tm)
    ticks = [t for t, _ in phrases[0].syllables]
    assert all(t % 48 == 0 for t in ticks) and ticks == [round((s - 0.006) * 384) for s in starts]
    assert stats["snap_ms"]["max"] < 7
    same, stats = L.place(L.parse("zorp blen"), [3.0, 3.0], tm)    # two on one slot: the second moves on
    assert [t for t, _ in same[0].syllables] == [1152, 1200] and stats["moved_to_next_slot"] == 1
    lead, _ = L.place(x, [3.0 + 0.5 * k for k in range(6)], tm, 1.0)  # the decode's seconds sit after the pad
    assert lead[0].syllables[0][0] == 4.0 * 384


def test_on_a_doubled_grid_a_word_snaps_one_slot_level_coarser():
    """assemble.lyric_rules: on a doubled grid (octave 2) the 8ths and their triplets, so at 200 BPM a word 50 ms
    before a beat goes on the beat, where the grid's 16ths put it a 1/16 (75 ms) early; on a first grid (octave 1)
    the quantizer's own rules, as before, whatever the tempo."""
    x = L.parse("zorp blen quiv fim")
    tm = TempoMap(192, [Tempo(0, 200000)])      # 0.3 s beats, 75 ms 16ths
    beats = (8, 12, 16, 20)
    starts = [0.3 * b - 0.050 for b in beats]
    doubled = lyric_rules(2)
    assert (doubled.straight, doubled.triplet) == (2, 3) and replace(doubled, straight=4) == RULES
    on, stats = L.place(x, starts, tm, rules=doubled)
    assert [t for t, _ in on[0].syllables] == [192 * b for b in beats]
    assert stats["snap_ms"]["max"] == pytest.approx(50, abs=1) and stats["moved_to_next_slot"] == 0
    assert lyric_rules(1) == RULES
    early, _ = L.place(x, starts, tm, rules=lyric_rules(1))
    assert [t for t, _ in early[0].syllables] == [192 * b - 48 for b in beats]


def test_lyrics_read_back_is_checked(tmp_path):
    from songcharter.assemble import lyrics_read_back
    x = L.parse("zorp blen")
    phrases, _ = L.place(x, [3.0, 3.5], tm120())
    c = Chart(SongInfo("t", "a"), tm120(), [], [], L.events(phrases))
    path = tmp_path / "notes.chart"
    path.write_text(write_chart(c), encoding="utf-8", newline="")
    assert lyrics_read_back(path, c) == []
    path.write_text(write_chart(c).replace('E "lyric blen"', 'E "lyric blem"'), encoding="utf-8", newline="")
    issues = lyrics_read_back(path, c)
    assert [i.kind for i in issues] == ["lyricsReadBack"] and "blen" not in issues[0].message
    assert "differ at event 2" in issues[0].message
    blen = phrases[0].syllables[1][0]
    path.write_text(write_chart(c).replace(f'{blen} = E "lyric blen"', f'{blen + 48} = E "lyric blen"'),
                    encoding="utf-8", newline="")
    issues = lyrics_read_back(path, c)                    # the same text a 1/16 later
    assert [i.kind for i in issues] == ["lyricsReadBack"] and "differ at event 2" in issues[0].message


# ------------------------------------------------------------------------------------------------ the engine

class Aligner:
    """Stands in for the network: the syllables of line k start 0.5 + 3k s after the generated vocal stem first
    gets loud, 0.4 s apart; one the aligner cannot spell gets no time; every character scores 0.6. Counts its
    runs."""

    def __init__(self, score: float = 0.6, version: str = "1"):
        self.runs, self.score, self.version = 0, score, version

    def versions(self):
        return {"songcharter": "test", "stand-in": self.version}

    def run(self, lyrics, vocals, settings):
        self.runs += 1
        level = np.abs(vocals[0])
        first = int(np.flatnonzero(level > 0.01)[0]) / SR
        starts, j = [], 0
        for i, s in enumerate(lyrics.syllables):
            j = 0 if i == 0 or s.line != lyrics.syllables[i - 1].line else j + 1
            starts.append(first + 0.5 + 3 * s.line + 0.4 * j if s.spelling else None)
        ends = [None if t is None else t + 0.2 for t in starts]
        scores = [[self.score] * len(s.spelling) for s in lyrics.syllables]
        return starts, ends, scores, {"device": settings.device, "frames": len(level) // 320, "labels": 0,
                                      "timings_s": {"load": 0.0, "emissions": 0.0, "align": 0.0}}


def vocal_stem(seconds: float = 20.0) -> np.ndarray:
    """A generated stem: a tone from 4 s to 16 s, silence around it."""
    n = int(seconds * SR)
    y = np.zeros(n, np.float32)
    i, j = int(4 * SR), int(16 * SR)
    y[i:j] = 0.1 * np.sin(2 * np.pi * 220 * np.arange(j - i) / SR)
    return np.stack([y, y])


def test_the_cache(tmp_path):
    stem, a = vocal_stem(), Aligner()
    r1 = E.align(TEXT, stem, tmp_path, aligner=a)
    assert not r1.cached and a.runs == 1 and len(r1.starts) == len(r1.lyrics.syllables)
    assert all(4.0 <= t <= 17.0 for t in r1.starts) and list(r1.starts) == sorted(r1.starts)
    r2 = E.align(TEXT, stem, tmp_path, aligner=a)
    assert r2.cached and a.runs == 1 and r2.starts == r1.starts and r2.ends == r1.ends
    # each of the text (one letter, the same syllables), the stem's samples and a setting misses the cache alone
    for other in (dict(text=TEXT.replace("zorp", "zarp")), dict(stem=stem * 0.5),
                  dict(settings=E.Settings(stars="word"))):
        E.align(TEXT, stem, tmp_path, aligner=a)              # the file holds the first call's key again
        before = a.runs
        r = E.align(other.get("text", TEXT), other.get("stem", stem), tmp_path, other.get("settings", E.Settings()),
                    aligner=a)
        assert not r.cached and a.runs == before + 1, other.keys()
    E.align(TEXT, stem, tmp_path, aligner=a)
    newer = Aligner(version="2")                              # a library upgrade: the times are made again
    assert not E.align(TEXT, stem, tmp_path, aligner=newer).cached and newer.runs == 1
    E.align(TEXT, stem, tmp_path, aligner=a)
    before = a.runs
    (tmp_path / "lyrics.json").write_text("{not json", encoding="utf-8")
    assert not E.align(TEXT, stem, tmp_path, aligner=a).cached and a.runs == before + 1
    data = (tmp_path / "lyrics.json").read_bytes()
    assert not any(w.encode() in data for w in WORDS)        # numbers only
    info = json.loads(data)
    assert info["counts"]["words"] == 14 and info["counts"]["unspelled_words"] == 1
    assert info["confidence"]["median"] == 0.6 and info["confidence"]["low"] is False


OTHER_SCRIPT = "\u0437\u043e\u0440\u043f \u0431\u043b\u0435\u043d\n\u03b6\u03bf\u03c1\u03c0 \u03b2\u03bb\u03b5\u03bd"   # made up


def test_a_text_the_aligner_cannot_spell_is_left_out(tmp_path):
    """Made-up words in Cyrillic and Greek letters: no syllable has a letter to time, so none can be spread from
    another; the lyrics are unavailable, saying why, instead of all landing at 0 s. One spelled word is enough."""
    a = Aligner()
    with pytest.raises(E.Unavailable, match="none of the 4 words has a letter the aligner spells"):
        E.align(OTHER_SCRIPT, vocal_stem(), tmp_path, aligner=a)
    assert a.runs == 0 and not (tmp_path / "lyrics.json").exists()

    class Silent(Aligner):   # an aligner that gives no syllable a time
        def run(self, lyrics, vocals, settings):
            starts, ends, scores, info = super().run(lyrics, vocals, settings)
            return [None] * len(starts), [None] * len(ends), scores, info

    with pytest.raises(E.Unavailable, match="none of the 1 words"):
        E.align("zorp", vocal_stem(), tmp_path, aligner=Silent())
    r = E.align(OTHER_SCRIPT + " zorp", vocal_stem(), tmp_path, aligner=a)
    assert r.info["counts"]["spelled_syllables"] == 1 and min(r.starts) > 4.0


def test_unspelled_syllables_are_spread_between_their_neighbours():
    s, e = E._spread([1.0, None, None, 4.0], [1.5, None, None, 4.5])
    assert s == [1.0, 1.5, 2.75, 4.0] and e == [1.5, 2.75, 4.0, 4.5]   # from the end before to the start after
    assert E._spread([None, 2.0], [None, 2.5])[0] == [2.0, 2.0]   # nothing before: it takes the next one's start


def test_targets_spell_the_words_with_stars_and_separators():
    english = ("-", "|", "A", "B", "D", "E", "F", "I", "K", "L", "M", "N", "O", "P", "R", "S", "W", "Z", "'")
    m = E.Method("X", "u", "0", "f", 0, True, "|", "")
    x = L.parse("zorp blen\n東京 fim\nwob's")
    seq, owner = E.targets(x, english, m, "line")
    star, bar = len(english), english.index("|")
    spelled = "".join(english[t] if t not in (star, bar) else ("*" if t == star else "|") for t in seq)
    assert spelled == "*ZORP|BLEN*FIM*WOB'S*"     # the unspelled word gives nothing, and no doubled separator
    assert owner[:5] == [-1, 0, 0, 0, 0] and len(owner) == len(seq)
    seq, _ = E.targets(x, english, m, "none")    # stars at the start and the end only
    assert "".join(english[t] if t != star else "*" for t in seq) == "*ZORP|BLEN|FIM|WOB'S*"
    seq, _ = E.targets(L.parse("zorp blen\n\n[Hed]\nfim\nwob"), english, m, "none")   # and at a section gap
    assert "".join(english[t] if t != star else "*" for t in seq) == "*ZORP|BLEN*FIM|WOB*"
    lower = E.Method("X", "u", "0", "f", 0, False, None, "")
    seq, _ = E.targets(L.parse("zo blen"), tuple("-zoblen"), lower, "word")
    assert seq == [7, 1, 2, 7, 3, 4, 5, 6, 7]   # a star before every word and at the end


def test_the_forced_alignment_on_made_up_emissions():
    """torchaudio's forced_align on emissions where each character peaks on known frames: each syllable starts on
    its first character's frame, and a long silence goes to the star."""
    torch = pytest.importorskip("torch")
    pytest.importorskip("torchaudio")
    import torchaudio.functional as F
    if not hasattr(F, "forced_align"):
        pytest.skip("this torchaudio has no forced_align")
    labels = ("-", "|", "Z", "O", "B", "L")
    m = E.Method("X", "u", "0", "f", 0, True, "|", "")
    x = L.parse("zo bol\nzol")
    seq, owner = E.targets(x, labels, m, "line")
    frames = 400
    em = np.full((frames, len(labels) + 1), -12.0, np.float32)
    em[:, 0] = -0.01                                     # blank everywhere
    em[:, -1] = 0.0                                      # the star, as align() appends it
    peaks = {50: "Z", 52: "O", 60: "|", 70: "B", 72: "O", 74: "L", 300: "Z", 302: "O", 304: "L"}
    for f, c in peaks.items():
        em[f, labels.index(c)] = 0.0
        em[f, 0] = -12.0
        em[f, -1] = -12.0
    em[100:290, :-1] = -12.0                             # music: nothing but the star can take it
    starts, ends, scores = E.path_times(em, seq, owner, len(x.syllables), 0, torch, F)
    assert [round(t / 0.02) for t in starts] == [50, 70, 300]
    assert all(sc and min(sc) > 0.9 for sc in scores)


def never_called(url, dest):
    raise AssertionError("downloaded")


def test_the_windows_stitch_into_one_pass_over_the_song():
    """emissions() on a stand-in network whose frames depend only on their own 400 samples (a strided
    convolution, as the bundles' first layer): the windows with their context, stitched, give exactly one pass over
    the whole song, for a song of several windows that ends partway through one."""
    torch = pytest.importorskip("torch")

    class Net(torch.nn.Module):
        def __init__(self):
            super().__init__()
            torch.manual_seed(0)
            self.conv = torch.nn.Conv1d(1, 5, kernel_size=400, stride=320)

        def forward(self, x):
            return self.conv(x[:, None, :]).transpose(1, 2), None

    net = Net().eval()
    settings = E.Settings(window_s=1.0, context_s=0.2)      # 50-frame windows, 10 frames of context
    rng = np.random.default_rng(1)
    audio = rng.standard_normal(int(3.7 * E.RATE)).astype(np.float32)
    stitched = E.emissions(net, audio, settings, torch)
    with torch.inference_mode():
        whole = torch.log_softmax(net(torch.from_numpy(audio)[None])[0][0], dim=-1).numpy()
    assert stitched.shape == whole.shape == ((len(audio) - 400) // 320 + 1, 5)
    assert np.allclose(stitched, whole, atol=1e-5)


def test_missing_libraries_and_unreachable_weights(tmp_path, monkeypatch):
    import importlib.util
    monkeypatch.delenv("SONGCHARTER_OFFLINE", raising=False)
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, *a: None if name == "torchaudio" else real(name, *a))
    assert E.missing() == "torchaudio is not installed: pip install songcharter[lyrics]"
    with pytest.raises(E.Unavailable, match="torchaudio is not installed"):
        E.align("zorp", vocal_stem(), tmp_path)
    monkeypatch.undo()
    m = E.METHODS["english"]

    def offline(url, dest):
        raise OSError("network unreachable")

    with pytest.raises(E.Unavailable, match="could not be downloaded"):
        E.weights_path(m, tmp_path, download=offline)
    assert not list((tmp_path / "lyrics").iterdir())
    with pytest.raises(E.Unavailable, match="not the pinned"):
        E.weights_path(m, tmp_path, download=lambda url, dest: dest.write_bytes(b"not the weights"))
    assert not list((tmp_path / "lyrics").iterdir())          # the bad .part is gone
    # weights already in place are checked too: the right ones load, others are refused and left for the person
    import hashlib
    small = E.Method("X", "u", hashlib.sha256(b"zorp weights").hexdigest(), "w.pth", 12, True, "|", "")
    got = E.weights_path(small, tmp_path, download=lambda url, dest: dest.write_bytes(b"zorp weights"))
    assert got == tmp_path / "lyrics" / "w.pth" and got.read_bytes() == b"zorp weights"
    assert E.weights_path(small, tmp_path, download=never_called) == got
    got.write_bytes(b"blen weights")
    with pytest.raises(E.Unavailable, match="delete it and run again"):
        E.weights_path(small, tmp_path, download=never_called)
    monkeypatch.setenv("SONGCHARTER_OFFLINE", "1")

    def never(url, dest):
        raise AssertionError("downloaded while offline")

    with pytest.raises(E.Unavailable, match="SONGCHARTER_OFFLINE"):
        E.weights_path(m, tmp_path, download=never)


# ------------------------------------------------------------------------------------------------ the pipeline

def with_lyrics(aligner=None, missing=None, raises=None):
    """test_pipeline's stand-in engines, with a lyrics stage: the real engine (its cache and its records) around
    the stand-in aligner, or missing libraries, or an aligner that raises."""
    base = standins()

    class WithLyrics(base):
        def lyrics_missing(self):
            return missing

        def lyrics(self, vocals, text, out, device):
            self.calls.append(("lyrics", vocals.shape, out, device))
            if raises is not None:
                raise raises
            return E.align(text, vocals, out, E.Settings(device=device), aligner=aligner or Aligner())

    return WithLyrics


def _all_files(*folders):
    for folder in folders:
        for p in Path(folder).rglob("*"):
            if p.is_file():
                yield p


@pytest.fixture(scope="module")
def song(tmp_path_factory):
    root = tmp_path_factory.mktemp("lyrics")
    write_song(root / "song.flac")
    return root


def run(song, tmp_path, monkeypatch, engines, lyrics=TEXT, name="out"):
    monkeypatch.setenv("SONGCHARTER_CACHE", str(tmp_path / "cache"))
    lines = []
    result = chart(song / "song.flac", tmp_path / name, Options(takes=1, lyrics=lyrics, preview=False),
                   engines=engines, log=lines.append, sampler=None)
    report = json.loads((result.work / "pipeline.json").read_text(encoding="utf-8"))
    return result, report, lines


def test_lyrics_go_into_the_chart_and_nowhere_else(song, tmp_path, monkeypatch):
    engines = with_lyrics()()
    result, report, lines = run(song, tmp_path, monkeypatch, engines)
    assert result.ok, [i for i in result.assembled.issues if i.error]
    assert [c[0] for c in engines.calls].count("lyrics") == 1
    assert any(l.startswith("[6/8] lyrics:") for l in lines)    # after the sections, before the guitar
    text = (result.folder / "notes.chart").read_text(encoding="utf-8")
    events = _chart_sections(_decode(text.encode()))["Events"]
    assert L.shown_lines(L.read_events(events)) == expected_lines(TEXT)
    ticks = [t for p in L.read_events(events) for t, _ in p.syllables]
    seconds = [result.assembled.chart.tempo.tick_to_sec(t) - result.assembled.lead.pad_seconds for t in ticks]
    assert all(VOCAL_SPANS[0][0] - 0.1 <= s <= VOCAL_SPANS[1][1] + 0.1 for s in seconds)
    ly = report["lyrics"]
    assert ly["given"] and ly["added"] and ly["words"] == 14 and ly["syllables"] == 16 and ly["lines"] == 4
    assert ly["confidence"]["median"] == 0.6 and ly["chart"]["phrases"] >= 4 and ly["chart"]["events"] > 16
    assert report["options"]["lyrics"] is True and result.lyrics == ly
    gate = result.assembled.report["gate"]
    scan = gate["scan_chart"]
    if find_scan_chart()[0] is not None:
        assert scan["ran"] and scan["playable"] and scan["chart_issues"] == 0
        assert scan["has_lyrics"] is True or ("warning:lyricsNotChecked" in gate["by_kind"]
                                               and scan["has_lyrics"] is None)   # an older scan.cjs
    # the gate catches lyrics lost on the way: read back from notes.chart, and by scan-chart where it reports them
    lost = tmp_path / "lost"
    shutil.copytree(result.folder, lost)
    (lost / "notes.chart").write_text("\r\n".join(l for l in text.splitlines() if "lyric" not in l and "phrase_"
                                                    not in l) + "\r\n", encoding="utf-8", newline="")
    kinds = {i.kind for i in verify_folder(lost, result.assembled.chart, result.assembled.lead.pad_seconds) if i.error}
    assert "lyricsReadBack" in kinds
    if scan.get("has_lyrics") is True:
        assert "noLyrics" in kinds
    # no word anywhere but notes.chart: pipeline.json, report.json, assemble.json, lyrics.json, every work file
    for p in _all_files(result.work, result.folder):
        if p.name == "notes.chart" or p.suffix in (".wav", ".ogg", ".flac", ".png"):   # audio: bytes, not text
            continue
        data = p.read_bytes()
        assert not any(w.encode() in data for w in WORDS), p
    assert not any(w in line for line in lines for w in WORDS)
    # a rerun answers from the lyrics cache
    again, report2, _ = run(song, tmp_path, monkeypatch, engines, name="out2")
    assert report2["lyrics"]["cached"] is True and (again.folder / "notes.chart").read_text(encoding="utf-8") == text


def test_the_events_stream_holds_no_words(song, tmp_path, monkeypatch, capsys):
    """The UI's events (chart(events=), `chart --events`): the lyrics stage's start, end and warnings, never a word,
    whether the lyrics are added or the aligner fails with a word in its message."""
    monkeypatch.setenv("SONGCHARTER_CACHE", str(tmp_path / "cache"))
    for k, engines in enumerate((with_lyrics()(), with_lyrics(raises=RuntimeError("zorp blen could not be aligned"))())):
        seen: list[dict] = []
        result = chart(song / "song.flac", tmp_path / f"ev{k}", Options(takes=1, lyrics=TEXT, preview=False),
                       engines=engines, log=lambda line: None, sampler=None, events=seen.append)
        assert result.ok
        stages = [e for e in seen if e.get("stage") == "lyrics"]
        assert [e["event"] for e in stages] == ["stage_start", "stage_end"]
        assert ("lyrics" in next(e for e in seen if e["event"] == "plan")["stages"])
        if k == 1:
            assert {"event": "warning", "text": "lyrics: not added (the aligner failed: RuntimeError)"} in seen
        raw = json.dumps(seen, ensure_ascii=False)
        assert not any(w in raw for w in WORDS + ("zorp",)), k
    # the command line's stream too
    (tmp_path / "l.txt").write_text(TEXT, encoding="utf-8")
    monkeypatch.setattr("songcharter.pipeline.Engines", with_lyrics())
    code = main(["chart", str(song / "song.flac"), "--out", str(tmp_path / "cli-ev"), "--lyrics", str(tmp_path / "l.txt"),
                 "--no-preview", "--takes", "1", "--events"])
    out = capsys.readouterr()
    assert code == 0 and "@@songcharter " in out.err and '"stage": "lyrics"' in out.err
    assert not any(w in out.err or w in out.out for w in WORDS)


def test_pipeline_json_holds_no_words(song, tmp_path, monkeypatch):
    """pipeline.json, whatever happens: added, missing aligner, unreachable weights, an aligner that fails with a
    word in its message."""
    cases = [with_lyrics()(), with_lyrics(missing="torchaudio is not installed: pip install songcharter[lyrics]")(),
             with_lyrics(raises=E.Unavailable("the aligner's weights could not be downloaded"))(),
             with_lyrics(raises=RuntimeError("zorp blen could not be aligned"))()]
    for k, engines in enumerate(cases):
        result, report, lines = run(song, tmp_path, monkeypatch, engines, name=f"case{k}")
        raw = (result.work / "pipeline.json").read_text(encoding="utf-8")
        assert not any(w in raw for w in WORDS), k
        assert result.ok
        assert not any(w in line for line in lines + result.warnings for w in WORDS), k


def test_a_missing_aligner_never_fails_a_chart(song, tmp_path, monkeypatch, capsys):
    engines = with_lyrics(missing="torchaudio is not installed: pip install songcharter[lyrics]")()
    result, report, lines = run(song, tmp_path, monkeypatch, engines)
    assert result.ok and not any(c[0] == "lyrics" for c in engines.calls)
    assert "lyrics: not added (torchaudio is not installed: pip install songcharter[lyrics])" in result.warnings
    assert report["lyrics"] == {"given": True, "added": False,
                                "why": "torchaudio is not installed: pip install songcharter[lyrics]"}
    assert "lyric" not in (result.folder / "notes.chart").read_text(encoding="utf-8")
    assert not any(l.startswith("[") and " lyrics:" in l for l in lines)   # no lyrics stage
    for k, (raised, why) in enumerate(((E.Unavailable("the weights are out of reach"), "the weights are out of reach"),
                                       (RuntimeError("zorp"), "the aligner failed: RuntimeError"))):
        result, report, _ = run(song, tmp_path, monkeypatch, with_lyrics(raises=raised)(), name=f"raised{k}")
        assert result.ok and report["lyrics"]["added"] is False and report["lyrics"]["why"] == why
        assert f"lyrics: not added ({why})" in result.warnings
        assert "lyric" not in (result.folder / "notes.chart").read_text(encoding="utf-8")
    assert report["lyrics"]["error"] == "RuntimeError" and report["lyrics"]["where"]


def test_lyrics_with_nothing_to_spell_are_left_out_with_why(song, tmp_path, monkeypatch):
    result, report, _ = run(song, tmp_path, monkeypatch, with_lyrics()(), lyrics=OTHER_SCRIPT)
    why = "none of the 4 words has a letter the aligner spells (it aligns the letters a-z, and does not romanize " \
          "other scripts)"
    assert result.ok and report["lyrics"]["added"] is False and report["lyrics"]["why"] == why
    assert f"lyrics: not added ({why})" in result.warnings
    assert "lyric" not in (result.folder / "notes.chart").read_text(encoding="utf-8")


def test_the_confidence_warns_on_the_share_of_weak_words():
    """The warning reads the share of weak words (DESIGN.md 2.15): over UNSURE_SHARE is unsure, at any median.
    One weak word in nine (0.111) is warned about, one in ten (0.100) is not, though their median of 0.06 is far
    under the 0.25 the median rule warned at; a weak word in three is, though the median is 0.9; no scored word is."""
    words = "zorp blen dak quiv fim wob dree smee plin tako"
    weak = [[0.01, 0.02]] + [[0.06]] * 9       # one word averaging 0.015, nine at 0.06
    c = E.confidence(L.parse(words), weak)
    assert (c["words_scored"], c["low_share"], c["median"], c["statistic"]) == (10, 0.1, 0.06, "low_share")
    assert c["threshold"] == E.UNSURE_SHARE and c["low"] is False
    assert c["why"] == "share of weak words (score under 0.05) 0.100, not over 0.108"
    c = E.confidence(L.parse(words.rsplit(" ", 1)[0]), weak[:9])
    assert c["low_share"] == 0.111 and c["low"] is True
    assert c["why"] == "share of weak words (score under 0.05) 0.111, over 0.108"
    c = E.confidence(L.parse("zorp blen-dak quiv"), [[0.01, 0.04], [0.9], [0.95], [0.9]])
    assert c["words_scored"] == 3 and c["median"] == 0.9 and c["low_share"] == 0.333 and c["low"] is True
    c = E.confidence(L.parse("zorp blen"), [[], []])
    assert c == {"words_scored": 0, "median": None, "p10": None, "low_share": None, "statistic": "low_share",
                 "threshold": E.UNSURE_SHARE, "low": True, "why": "no word was scored"}


def test_a_cached_confidence_is_judged_again(tmp_path):
    """A cache hit judges the cached confidence by today's rule: a lyrics.json made when the median rule warned
    (its low True, no why) is not unsure by the share of weak words, and says why."""
    stem = vocal_stem()
    first = E.align(TEXT, stem, tmp_path, aligner=Aligner(score=0.2))
    assert first.info["confidence"]["low"] is False
    path = tmp_path / "lyrics.json"
    info = json.loads(path.read_text(encoding="utf-8"))
    info["confidence"] = {"words_scored": 13, "median": 0.2, "p10": 0.2, "low_share": 0.0, "low": True}
    path.write_text(json.dumps(info), encoding="utf-8")
    again = E.align(TEXT, stem, tmp_path, aligner=Aligner(score=0.2))
    assert again.cached and again.info["confidence"]["low"] is False
    assert again.info["confidence"]["why"] == "share of weak words (score under 0.05) 0.000, not over 0.108"
    # A verdict that already carries a why is judged again too (a later threshold must not leave stale warnings).
    info["confidence"] = {"words_scored": 13, "median": 0.2, "p10": 0.2, "low_share": 0.0, "statistic": "low_share",
                          "threshold": 0.0, "low": True, "why": "share of weak words (score under 0.05) 0.000, over 0.0"}
    path.write_text(json.dumps(info), encoding="utf-8")
    stale = E.align(TEXT, stem, tmp_path, aligner=Aligner(score=0.2))
    assert stale.cached and stale.info["confidence"]["low"] is False
    assert stale.info["confidence"]["why"] == "share of weak words (score under 0.05) 0.000, not over 0.108"
    info["confidence"] = {"words_scored": 13, "median": 0.6, "p10": 0.01, "low_share": 0.154, "low": False}
    path.write_text(json.dumps(info), encoding="utf-8")
    assert E.align(TEXT, stem, tmp_path, aligner=Aligner(score=0.2)).info["confidence"]["low"] is True


def test_an_unsure_alignment_is_warned_about(song, tmp_path, monkeypatch):
    """The pipeline's warning carries confidence's why, and pipeline.json keeps every field of the confidence: every
    word weak (characters at 0.01) is warned about; a median of 0.2 (the median rule warned under 0.25) is not."""
    result, report, _ = run(song, tmp_path, monkeypatch, with_lyrics(aligner=Aligner(score=0.01))())
    conf = report["lyrics"]["confidence"]
    assert result.ok and report["lyrics"]["added"] and conf["low"] is True
    assert conf == {"words_scored": 13, "median": 0.01, "p10": 0.01, "low_share": 1.0, "statistic": "low_share",
                    "threshold": 0.108, "low": True, "why": "share of weak words (score under 0.05) 1.000, over 0.108"}
    assert ("lyrics: the alignment is unsure (share of weak words (score under 0.05) 1.000, over 0.108): check the "
            "lyrics' timing") in result.warnings
    result, report, _ = run(song, tmp_path, monkeypatch, with_lyrics(aligner=Aligner(score=0.2, version="2"))(),
                            name="out2")
    conf = report["lyrics"]["confidence"]
    assert result.ok and not report["lyrics"]["cached"] and conf["median"] == 0.2 and conf["low"] is False
    assert not any("unsure" in w for w in result.warnings)


def test_without_lyrics_nothing_changes(song, tmp_path, monkeypatch):
    engines = with_lyrics()()
    result, report, _ = run(song, tmp_path, monkeypatch, engines, lyrics=None)
    assert result.ok and "lyrics" not in report and report["options"]["lyrics"] is False
    assert not any(c[0] == "lyrics" for c in engines.calls) and result.lyrics is None
    assert "lyric" not in (result.folder / "notes.chart").read_text(encoding="utf-8")
    assert "lyrics" not in result.assembled.report


def test_the_cli_reads_the_lyrics_file(song, tmp_path, monkeypatch, capsys):
    for data in ("café zorp\n".encode("utf-8-sig"), "café zorp\n".encode("cp1252"),
                 "café zorp\n".encode("utf-16")):
        (tmp_path / "l.txt").write_bytes(data)
        assert read_lyrics(tmp_path / "l.txt") == "café zorp\n"
    with pytest.raises(InputError, match="cannot read the lyrics file"):
        read_lyrics(tmp_path / "none.txt")
    (tmp_path / "bad.txt").write_bytes(b"zorp \x81\x8d\x8f blen")   # bytes neither UTF-8 nor cp1252 can be
    with pytest.raises(InputError, match="not UTF-8") as e:
        read_lyrics(tmp_path / "bad.txt")
    assert "zorp" not in str(e.value)
    (tmp_path / "l.txt").write_text("zorp blen\n", encoding="utf-8")
    monkeypatch.setenv("SONGCHARTER_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr("songcharter.pipeline.Engines", with_lyrics())
    code = main(["chart", str(song / "song.flac"), "--out", str(tmp_path / "cli"), "--lyrics", str(tmp_path / "l.txt"),
                 "--no-preview", "--takes", "1"])
    out = capsys.readouterr()
    assert code == 0, out.err[-2000:]
    assert "lyrics: 2 words in 1 phrases" in out.out and "zorp" not in out.out and "zorp" not in out.err
    assert main(["chart", str(song / "song.flac"), "--out", str(tmp_path / "cli2"), "--lyrics",
                 str(tmp_path / "none.txt")]) == 2
    assert "cannot read the lyrics file" in capsys.readouterr().err
