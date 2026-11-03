"""Lyrics (songcharter.lyrics, songcharter.engines.lyrics and the pipeline's lyrics stage), with made-up words only
and audio generated here: the text model and what Clone Hero shows, the events in [Events], the phrases split at
lines and long rests, the grid, the cache, the fallback when the aligner is missing or fails, and that no word goes
anywhere but notes.chart. No model runs and none is downloaded: a stand-in aligner times the syllables from the
generated vocal stem; the forced alignment itself runs on made-up emissions when torchaudio is installed."""
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

from songcharter import lyrics as L
from songcharter.assemble import find_scan_chart, verify_folder
from songcharter.chart import Chart, SongInfo, write_chart
from songcharter.cli import main, read_lyrics
from songcharter.engines import lyrics as E
from songcharter.errors import InputError
from songcharter.importers import _chart_sections, _decode
from songcharter.pipeline import Options, chart
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


# ------------------------------------------------------------------------------------------------ the engine

class Aligner:
    """Stands in for the network: the syllables of line k start 0.5 + 3k s after the generated vocal stem first
    gets loud, 0.4 s apart; one the aligner cannot spell gets no time; every character scores 0.6. Counts its
    runs."""

    def __init__(self):
        self.runs = 0

    def versions(self):
        return {"songcharter": "test", "stand-in": "1"}

    def run(self, lyrics, vocals, settings):
        self.runs += 1
        level = np.abs(vocals[0])
        first = int(np.flatnonzero(level > 0.01)[0]) / SR
        starts, j = [], 0
        for i, s in enumerate(lyrics.syllables):
            j = 0 if i == 0 or s.line != lyrics.syllables[i - 1].line else j + 1
            starts.append(first + 0.5 + 3 * s.line + 0.4 * j if s.spelling else None)
        ends = [None if t is None else t + 0.2 for t in starts]
        scores = [[0.6] * len(s.spelling) for s in lyrics.syllables]
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
    before = a.runs
    (tmp_path / "lyrics.json").write_text("{not json", encoding="utf-8")
    assert not E.align(TEXT, stem, tmp_path, aligner=a).cached and a.runs == before + 1
    data = (tmp_path / "lyrics.json").read_bytes()
    assert not any(w.encode() in data for w in WORDS)        # numbers only
    info = json.loads(data)
    assert info["counts"]["words"] == 14 and info["counts"]["unspelled_words"] == 1
    assert info["confidence"]["median"] == 0.6 and info["confidence"]["low"] is False


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
    seq, _ = E.targets(x, english, m, "none")
    assert "".join(english[t] for t in seq) == "ZORP|BLEN|FIM|WOB'S"
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
