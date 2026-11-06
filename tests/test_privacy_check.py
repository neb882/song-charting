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
    r = capsys.readouterr()
    return code, r.out + "\nSTDERR:" + r.err


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
    assert "cannot use the owner's list" in capsys.readouterr().err


def test_a_name_split_by_a_line_wrap_or_markup_is_found(tmp_path, capsys, monkeypatch):
    """Docs wrap at 120 columns, so a title can start on one line and end on the next (comment markers between); a
    name that holds markup or punctuation at its ends is still found, and so is the name inside the markup."""
    monkeypatch.setattr(P, "LOCAL_EXTRA", [{"id": "dak", "md5": "", "title": "Panic!", "artist": "Wob",
                                            "charter": "<b>Fim Quorrel</b>"},
                                           {"id": "qux", "md5": "", "title": "[Zim]"}], raising=False)
    local = LOCAL + P.LOCAL_EXTRA
    lst = tmp_path / "local.json"
    lst.write_text(json.dumps(local))
    f = tmp_path / "doc.md"
    f.write_text("we played Glimmer\n  Hollow twice\n# a comment: The\n# Quindles\nshout panic! now\ncharted by Fim Quorrel\nby [zim]\n")
    monkeypatch.setattr(P, "public_values", lambda repo: set())
    assert P.main(["--local", str(lst), str(f)]) == 1
    out = capsys.readouterr().out
    assert "doc.md:1: zorp: primary title" in out and "doc.md:3: zorp: primary artist" in out
    assert "doc.md:5: dak: primary title" in out and "doc.md:6: dak: primary charter" in out
    assert "doc.md:7: qux: primary title" in out             # a name that starts with a non-word character
    assert "doc.md:1: zorp: primary charter" not in out        # "fenwick" is nowhere


def test_every_name_of_three_letters_or_more_counts_and_nothing_reaches_stderr(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(P, "public_values", lambda repo: set())
    code, out = _run(tmp_path, capsys, "by fenwick, hash FEDCBA9876543210\n")   # out holds stderr too
    assert code == 1 and "zorp: primary charter" in out and "zorp: alt md5 (16 hex)" in out
    assert "fenwick" not in out and "fedcba" not in out.lower()


def test_a_public_value_skips_only_itself(tmp_path, capsys, monkeypatch):
    """Only a value equal to one of eval/refs.json's is public, never one that a public value merely contains."""
    monkeypatch.setattr(P, "public_values", lambda repo: {"the quindles live", "harmonyx"})
    code, out = _run(tmp_path, capsys, "The Quindles\n")
    assert code == 1 and "zorp: primary artist" in out


def test_the_default_is_every_tracked_file(tmp_path, capsys, monkeypatch):
    """With no files given, the check reads `git ls-files` of the repository (here a made-up one)."""
    import subprocess
    repo = tmp_path / "repo"
    (repo / "eval").mkdir(parents=True)
    (repo / "notes.md").write_text("Glimmer Hollow\n")
    (repo / "untracked.md").write_text("The Quindles\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "notes.md"], check=True)
    lst = tmp_path / "local.json"
    lst.write_text(json.dumps(LOCAL))
    monkeypatch.setattr(P, "REPO", repo)
    assert P.main(["--local", str(lst)]) == 1
    out = capsys.readouterr().out
    assert "notes.md:1: zorp: primary title" in out and "untracked" not in out and "1 files" in out


def test_a_malformed_list_or_no_git_is_exit_2(tmp_path, capsys, monkeypatch):
    lst = tmp_path / "local.json"
    for bad in ({"id": "zorp"}, [{"md5": "0123"}], [1]):
        lst.write_text(json.dumps(bad))
        assert P.main(["--local", str(lst), str(lst)]) == 2
    lst.write_text(json.dumps(LOCAL))
    monkeypatch.setattr(P, "REPO", tmp_path)                 # not a git checkout
    assert P.main(["--local", str(lst)]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_a_coincident_public_name_is_skipped_by_its_hash(tmp_path, capsys, monkeypatch):
    import hashlib
    monkeypatch.setattr(P, "public_values", lambda repo: set())
    monkeypatch.setattr(P, "COINCIDENT", {hashlib.sha256(b"moss tarrow").hexdigest()})
    code, out = _run(tmp_path, capsys, "charted by Moss Tarrow\n")
    assert code == 0 and "0 found" in out
