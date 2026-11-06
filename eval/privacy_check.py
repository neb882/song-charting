"""python -I eval/privacy_check.py [--local LIST] [FILE ...]: the stress set's private names in committed files.

The stress set's package md5s, titles, artists and charters live only in the owner's list outside the repository
(`$EVAL_DATA/stress.local.json`, eval/README.md, Stress songs). This checks that none of them is in a tracked file
(default: `git ls-files`), or in the files given (a report before it is committed): an md5 or a prefix of one
(4 or more hex digits, case-insensitive, not inside a longer hex run), or a title, artist or charter as a whole word
(case-insensitive; across a line wrap, with comment markers between its words; with its markup tags and without). A value that is a song's id, that eval/refs.json (the reference set's public metadata) also
holds, or that COINCIDENT lists (by hash), is not private and is skipped. It prints only the file, the line, the song's id and the kind of value, never
the value. Exit 0 when nothing is found, 1 when something is, 2 when the list is missing, unreadable or malformed, or the files
cannot be listed.
Run it before every push to main (docs/PIPELINE.md, the merge).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HEX = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{4,32}(?![0-9a-fA-F])")
MIN_NAME = 3
REPO = Path(__file__).resolve().parent.parent
TAG = re.compile(r"<[^>]*>")
GAP = r"(?:\s|#|//|\*|>|-{2,})+"   # between a name's words: spaces, a line wrap, comment and quote markers


# Names public by coincidence, as SHA-256 of the lower-cased name (so the script spells none): a game developer's
# name that one stress chart's charter field also holds; DESIGN.md names the developer since before the stress set.
COINCIDENT = {"4ba848b4cf6c5e96e1692ca52b1815ab9c4b0378e9b838366fade54a98bdf5dd"}


class Malformed(ValueError):
    pass


def name_pattern(v: str) -> re.Pattern:
    """A name as a whole word (no word character on either side, so "Panic!" works), its words joined by GAP."""
    return re.compile(r"(?<!\w)" + GAP.join(re.escape(w) for w in v.split()) + r"(?!\w)", re.I)


def secrets(local: list, public: set[str]) -> tuple[list[tuple[str, str, str]], list[tuple[re.Pattern, str, str]]]:
    """(md5s, names): each md5 with its song id and kind (primary/alt), each name as a whole-word pattern."""
    md5s, names = [], []
    if not isinstance(local, list):
        raise Malformed("the list is not a list of songs")
    for song in local:
        if not isinstance(song, dict) or not isinstance(song.get("id"), str) or not isinstance(song.get("alts", []), list):
            raise Malformed("a song without an id")
        sid = song["id"]
        for kind, item in [("primary", song)] + [("alt", a) for a in song.get("alts", [])]:
            if not isinstance(item, dict):
                raise Malformed(f"{sid}: an alt that is not an object")
            if item.get("md5"):
                md5s.append((str(item["md5"]).lower(), sid, kind))
            for key in ("title", "artist", "charter"):
                raw = str(item.get(key) or "").strip()
                for v in {raw, " ".join(TAG.sub(" ", raw).split())}:   # with its markup, and without
                    if (len(v) >= MIN_NAME and v.lower() != sid.lower() and v.lower() not in public
                            and hashlib.sha256(v.lower().encode()).hexdigest() not in COINCIDENT):
                        names.append((name_pattern(v), sid, f"{kind} {key}"))
    return md5s, names


def public_values(repo: Path) -> set[str]:
    """Every string value of eval/refs.json (lower-cased): the reference set's metadata is public."""
    out: set[str] = set()
    path = repo / "eval" / "refs.json"
    if not path.is_file():
        return out

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            out.add(x.strip().lower())
    walk(json.loads(path.read_text(encoding="utf-8")))
    return out


def scan(text: str, md5s, names) -> list[tuple[int, str, str]]:
    """(line, id, kind) for each hit, sorted; a name split by a line wrap counts on the line it starts on."""
    hits = set()
    line_of = lambda pos: text.count("\n", 0, pos) + 1   # noqa: E731
    for m in HEX.finditer(text):
        tok = m.group(0).lower()
        for md5, sid, kind in md5s:
            if md5.startswith(tok):
                hits.add((line_of(m.start()), sid, f"{kind} md5 ({len(tok)} hex)"))
    for pat, sid, kind in names:
        for m in pat.finditer(text):
            hits.add((line_of(m.start()), sid, kind))
    return sorted(hits)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--local", help="the owner's list (default $EVAL_DATA/stress.local.json)")
    ap.add_argument("files", nargs="*", help="files to check (default: every tracked file)")
    a = ap.parse_args(argv)
    repo = REPO
    local_path = Path(a.local) if a.local else Path(os.environ.get("EVAL_DATA", repo / "eval" / "data")) / "stress.local.json"
    try:
        local = json.loads(local_path.read_text(encoding="utf-8"))
        md5s, names = secrets(local, public_values(repo))
    except (OSError, ValueError) as e:   # Malformed is a ValueError; its message names no value
        why = str(e) if isinstance(e, Malformed) else type(e).__name__
        print(f"privacy_check: cannot use the owner's list {local_path}: {why}", file=sys.stderr)
        return 2
    if a.files:
        files = [Path(f) for f in a.files]
    else:
        listed = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True)
        if listed.returncode != 0:
            print(f"privacy_check: cannot list the tracked files of {repo} (not a git checkout?)", file=sys.stderr)
            return 2
        files = [repo / f for f in listed.stdout.decode().split("\0") if f]
    found = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line, sid, kind in scan(text, md5s, names):
            found += 1
            print(f"{f}:{line}: {sid}: {kind}")
    print(f"privacy_check: {len(files)} files, {len(md5s)} md5s and {len(names)} names checked, {found} found")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
