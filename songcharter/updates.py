"""The update check (M5-07): whether a newer songcharter is out, and the line that installs it.

    check(home, version) -> {"checked", "version", "latest", "line", "url"} | None

The page shows a notice when it returns something (ui/server.py runs it once per server process, on a thread, after
the first page is served): "songcharter <latest> is out", the install line with a Copy button, and the release page.
Nothing is ever installed or downloaded by it (the owner's decision over a one-click updater, 2026-11-05: M5-00
section 8; M5-99 says what one would add).

  * **The releases:** GitHub's list of the repository's releases (RELEASES_URL, the ten newest;
    $SONGCHARTER_RELEASES_URL replaces it, for CI's check). A release counts when it is not a draft and its tag is
    v<dotted integers> (v0.2.0; ASCII digits, at most 10 parts of 9 digits): a pre-release counts, since the friend is
    on one [decided, the owner]; a tag with a suffix (v0.2.0-ci-abc, v0.2.0rc1) does not. The newest is the highest
    version of those, compared as integers (0.10 is after 0.9; 0.2 is 0.2.0); it is newer than `version` when it is
    higher (a `version` that is not dotted integers is never older).
  * **The line**, for a newer one: the guide's own (docs/guide/windows-wsl.md, section 3, as packaging/release/
    build.sh fills it in; `install_line`), with install.sh's SHA-256 from that release's SHA256SUMS asset (its
    browser_download_url), on one line:
        curl -fsSLO https://github.com/neb882/song-charting/releases/download/v<latest>/install.sh
        && echo "<sha>  install.sh" | sha256sum -c - && bash install.sh
    Only its version (digits and dots) and the SHA-256 (64 hex) come from the network, so what the friend pastes is
    always this line. Without a readable SHA256SUMS (none, a failed fetch, no install.sh line in it) there is no line
    (null), only the release page (`url`: always the tag's page on GitHub, RELEASE_PAGE, never the API's html_url).
  * **At most one request a day** (CHECK_EVERY_S): <home>/state/update.json keeps the last answer, and one under a day
    old for this `version` answers without a request. Any failure (no network, a timeout, an HTTP error, an answer
    that is not the releases' JSON) returns None and keeps {"checked", "version", "error"}, so the next try comes an
    hour later (RETRY_AFTER_S) at the earliest. SONGCHARTER_OFFLINE=1: no request at all (a stamp under a day old
    still answers).
  * **Nothing personal:** a plain GET with the User-Agent songcharter/<version> (GitHub's API refuses a request with
    none), no token, no cookie; only urllib.

`say`, when given, gets one line saying what the check found (the server's log).
"""
from __future__ import annotations

import http.client
import json
import os
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

REPO = "neb882/song-charting"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=10"
DOWNLOAD_URL = f"https://github.com/{REPO}/releases/download"   # the guide's line's (build.sh's RELEASE_URL less /v<x>)
RELEASE_PAGE = f"https://github.com/{REPO}/releases/tag/v{{version}}"
CHECK_EVERY_S = 86400   # an answer this recent is kept: one request a day at most
RETRY_AFTER_S = 3600    # after a failure, the next try at the earliest
TIMEOUT_S = 5.0         # each request's socket timeout
MAX_RELEASES = 1 << 20  # bytes of the releases' JSON read at most (ten releases are about 50 KB)
MAX_SUMS = 1 << 16      # bytes of a SHA256SUMS read at most (two lines)
STAMP = Path("state") / "update.json"   # under the home
VERSION = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,9}){0,9}")   # ASCII digits, at most 10 parts of 9 digits
SUM_LINE = re.compile(r"([0-9a-f]{64}) [ *]install\.sh")   # sha256sum's line for install.sh


class Failed(Exception):
    """A check that got no answer it can use (the message says why)."""


def parse(version: Any) -> tuple[int, ...] | None:
    """A version of dotted integers as a tuple to compare, its trailing zeros dropped (0.2.0 is 0.2); else None."""
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        return None
    parts = [int(p) for p in version.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def newer(latest: Any, version: Any) -> bool:
    """Whether `latest` is a higher version than `version` (both dotted integers)."""
    a, b = parse(latest), parse(version)
    return a is not None and b is not None and a > b


def install_line(latest: str, sha256: str) -> str:
    """The guide's install line for release v<latest>, with install.sh's SHA-256."""
    return (f"curl -fsSLO {DOWNLOAD_URL}/v{latest}/install.sh && echo \"{sha256}  install.sh\" | sha256sum -c - && "
            "bash install.sh")


def stamp_path(home: Path | str) -> Path:
    return Path(home) / STAMP


def check(home: Path | str, version: str, url: str | None = None, timeout: float = TIMEOUT_S, *,
          opener: Callable[..., Any] | None = None, now: float | None = None,
          say: Callable[[str], None] | None = None) -> dict | None:
    """The update for `version`, {"checked", "version", "latest", "line", "url"}, when a newer release is out, else
    None (the module docstring). `url`: the releases' JSON (None: $SONGCHARTER_RELEASES_URL, else RELEASES_URL);
    `opener`: urllib.request.urlopen's stand-in (tests); `now`: the clock (time.time)."""
    say = say or (lambda line: None)
    now = time.time() if now is None else now
    path = stamp_path(home)
    kept = _read(path, version)
    if kept is not None:
        age = now - kept["checked"]
        if "error" in kept:
            if 0 <= age < RETRY_AFTER_S:
                say(f"update check: not tried again until an hour after it failed, {_ago(age)} ({kept['error']})")
                return None
        elif 0 <= age < CHECK_EVERY_S:
            say(f"update check, {_ago(age)}: {_found(kept)}")
            return kept if newer(kept["latest"], version) else None
    if os.environ.get("SONGCHARTER_OFFLINE") == "1":
        say("update check: not made (SONGCHARTER_OFFLINE=1)")
        return None
    url = url or os.environ.get("SONGCHARTER_RELEASES_URL") or RELEASES_URL
    get = opener or urllib.request.urlopen
    try:
        release = _newest(_fetch(get, url, version, timeout, MAX_RELEASES, "application/vnd.github+json"))
    except (Failed, ValueError, TypeError) as e:   # a parse error too: a failure, with its stamp, never a raise
        e = e if isinstance(e, Failed) else Failed(f"the releases' answer: {type(e).__name__}: {e}")
        _write(path, {"checked": now, "version": version, "error": str(e)})
        say(f"update check failed: {e}; the next try is an hour away at the earliest")
        return None
    latest = release["tag_name"][1:] if release else None
    result = {"checked": now, "version": version, "latest": latest, "line": None, "url": None}
    if release and newer(latest, version):
        result["url"] = RELEASE_PAGE.format(version=latest)   # never the API's html_url: only the version is theirs
        result["line"] = _line(get, release, latest, version, timeout)
    _write(path, result)
    say(f"update check: {_found(result)}")
    return result if result["url"] else None


# ------------------------------------------------------------------------------------------------ the requests

def _fetch(get: Callable[..., Any], url: str, version: str, timeout: float, limit: int, accept: str) -> bytes:
    """GET `url` (http or https only), at most `limit` bytes; Failed with why."""
    if urlsplit(url).scheme not in ("http", "https"):
        raise Failed(f"{url} is not an http or https URL")
    request = urllib.request.Request(url, headers={"User-Agent": f"songcharter/{version}", "Accept": accept})
    try:
        with get(request, timeout=timeout) as r:
            data = r.read(limit + 1)
    except (OSError, http.client.HTTPException, ValueError) as e:   # URLError, HTTPError and timeouts are OSErrors
        raise Failed(f"{url}: {type(e).__name__}: {e}") from None
    if len(data) > limit:
        raise Failed(f"{url} sent more than {limit} bytes")
    return data


def _newest(data: bytes) -> dict | None:
    """The newest release that counts (the module docstring) in the releases' JSON, or None; Failed when it is not a
    list of releases."""
    try:
        releases = json.loads(data.decode("utf-8"))
    except ValueError as e:
        raise Failed(f"the releases' answer is not JSON ({e})") from None
    if not isinstance(releases, list):
        raise Failed(f"the releases' answer is a JSON {type(releases).__name__}, not a list")
    best, best_key = None, None
    for r in releases:
        if not isinstance(r, dict) or r.get("draft") not in (None, False):
            continue
        tag = r.get("tag_name")
        key = parse(tag[1:]) if isinstance(tag, str) and tag.startswith("v") else None
        if key is not None and (best_key is None or key > best_key):
            best, best_key = r, key
    return best


def _line(get: Callable[..., Any], release: dict, latest: str, version: str, timeout: float) -> str | None:
    """The install line from the release's SHA256SUMS asset, or None when it cannot be read."""
    assets = release.get("assets")
    sums = next((a for a in assets if isinstance(a, dict) and a.get("name") == "SHA256SUMS"), None) \
        if isinstance(assets, list) else None
    link = sums.get("browser_download_url") if sums else None
    if not isinstance(link, str):
        return None
    try:
        text = _fetch(get, link, version, timeout, MAX_SUMS, "*/*").decode("utf-8")
    except (Failed, ValueError):
        return None
    sha = next((m.group(1) for m in map(SUM_LINE.fullmatch, text.splitlines()) if m), None)
    return install_line(latest, sha) if sha else None


# ------------------------------------------------------------------------------------------------ the stamp

def _read(path: Path, version: str) -> dict | None:
    """update.json when it is one this module wrote for `version`: an error stamp, or an answer whose line is the one
    install_line makes (so the page never shows another); else None."""
    try:
        r = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(r, dict) or r.get("version") != version:
        return None
    checked = r.get("checked")
    if isinstance(checked, bool) or not isinstance(checked, (int, float)):
        return None
    if "error" in r:
        return {"checked": checked, "version": version, "error": r["error"]} if isinstance(r["error"], str) else None
    latest, line, url = r.get("latest"), r.get("line"), r.get("url")
    answer = {"checked": checked, "version": version, "latest": latest, "line": line, "url": url}
    if latest is not None and parse(latest) is None:
        return None
    if not newer(latest, version):
        return answer if line is None and url is None else None
    if url != RELEASE_PAGE.format(version=latest):
        return None
    if line is not None:
        m = re.fullmatch(r'.*echo "([0-9a-f]{64})  install\.sh".*', line) if isinstance(line, str) else None
        if not m or line != install_line(latest, m.group(1)):
            return None
    return answer


def _write(path: Path, value: dict) -> None:
    """update.json, whole or not at all; a home that cannot be written only means the next start asks again."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        part.write_text(json.dumps(value, indent=1) + "\n", encoding="utf-8")
        os.replace(part, path)
    except OSError:
        pass


def _found(r: dict) -> str:
    if r["url"]:
        how = "" if r["line"] else " (its SHA256SUMS could not be read: the notice links the release page only)"
        return f"songcharter {r['latest']} is out (this is {r['version']}){how}: {r['url']}"
    if r["latest"]:
        return f"songcharter {r['version']} is the newest (the newest release is {r['latest']})"
    return f"no release of songcharter found (this is {r['version']})"


def _ago(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes} min ago" if minutes < 120 else f"{minutes // 60} h ago"
