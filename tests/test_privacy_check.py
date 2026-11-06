"""eval/privacy_check.py: the stress set's private names found in files, and never printed (made-up list)."""
import json

from eval import privacy_check as P

LOCAL = [
    {"id": "zorp", "md5": "0123456789abcdef0123456789abcdef", "title": "Glimmer Hollow", "artist": "The Quindles",
     "charter": "fenwick", "alts": [{"md5": "fedcba9876543210fedcba9876543210", "charter": "Moss Tarrow"}]},
    {"id": "blen", "md5": "aaaabbbbccccddddeeeeffff00001111", "title": "Blen", "artist": "Harmonyx",
     "charter": "Harmonyx"},
]


def _run(tmp_path, capsys, text):
    lst = tmp_path / "local.json"
    lst.write_text(json.dumps(LOCAL))
    f = tmp_path / "doc.md"
    f.write_text(text)
    code = P.main(["--local", str(lst), str(f)])
    return code, capsys.readouterr().out


def test_md5s_and_their_prefixes_are_found(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(P, "public_values", lambda repo: set())
    code, out = _run(tmp_path, capsys, "ok line\nlabel 0123 and FEDCBA98 here\nhash 0123456789abcdef0123456789abcdef\n")
    assert code == 1
    assert "doc.md:2: zorp: primary md5 (4 hex)" in out and "doc.md:2: zorp: alt md5 (8 hex)" in out
    assert "doc.md:3: zorp: primary md5 (32 hex)" in out
    assert "0123" not in out.replace("(4 hex)", "") and "fedcba" not in out.lower()   # never the value


def test_a_prefix_inside_a_longer_hex_run_or_too_short_is_not_one(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(P, "public_values", lambda repo: set())
    code, out = _run(tmp_path, capsys, "commit 90123ab and 012 and x0123456789abcdef0123456789abcdef0\n")
    assert code == 0 and "0 found" in out


def test_names_as_whole_words_any_case_and_never_printed(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(P, "public_values", lambda repo: set())
    code, out = _run(tmp_path, capsys, "we played glimmer hollow by THE QUINDLES\ncharted by Moss Tarrow\nfenwicks\n")
    assert code == 1
    assert "doc.md:1: zorp: primary title" in out and "doc.md:1: zorp: primary artist" in out
    assert "doc.md:2: zorp: alt charter" in out and "doc.md:3" not in out          # whole words only
    assert "glimmer" not in out.lower() and "quindles" not in out.lower() and "tarrow" not in out.lower()


def test_ids_and_public_values_are_skipped(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(P, "public_values", lambda repo: {"harmonyx"})
    code, out = _run(tmp_path, capsys, "the song blen, charted by Harmonyx\n")
    assert code == 0 and "0 found" in out


def test_a_missing_list_is_exit_2(tmp_path, capsys):
    assert P.main(["--local", str(tmp_path / "none.json"), str(tmp_path)]) == 2
    assert "cannot read the owner's list" in capsys.readouterr().err
