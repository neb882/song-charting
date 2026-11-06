# M5-07: the page's update notice with a Copy button, and the update path tested in CI (builder's report)

Branch `m5-07-updates`, worktree `<wt>/m5-07`, from main at 8ba3cbd (origin/main merged in at 3ca19e1).

## Commits

- 8eca74c updates.py: the update check (M5-07), once a day at most, with the guide's line for a newer release
- 2cf22b7 The page's update notice: the check after the first page, /api/status's update, the box with Copy and Later
- 78ee376 CI: 75-update.sh, v0.1.0 from its tag, then the new line over it, and the notice against a releases JSON
- 27138f2 Docs: the update notice in the guide's section 3, DESIGN 4.5 and the README
- a7ec93a Merge origin/main into m5-07-updates (M5-10's work order, PROGRESS)
- 07ec2a5 75-update.sh: the update's one download line is the app's tarball, from the server; any other fails

## What changed

### `songcharter/updates.py` (new)
`check(home, version, url=None, timeout=5.0, *, opener=None, now=None, say=None) -> dict | None`:
- reads `<home>/state/update.json`; one for this `version` under a day old (`CHECK_EVERY_S` 86400) answers without a
  request; an error stamp under an hour old (`RETRY_AFTER_S` 3600) gives None without a request; a stamp from the
  future, for another version, or not one this module could have written (a line that is not exactly
  `install_line`'s, a non-https url, a version that does not parse, a `checked` that is not a number) is ignored;
- `SONGCHARTER_OFFLINE=1`: no request (a fresh stamp still answers; nothing is written);
- else fetches `url` (None: `$SONGCHARTER_RELEASES_URL`, else `RELEASES_URL` =
  `https://api.github.com/repos/neb882/song-charting/releases?per_page=10`), http(s) only, at most 1 MB, with
  User-Agent `songcharter/<version>` and Accept `application/vnd.github+json`, nothing else;
- the newest release that counts: not a draft, tag `v` + dotted integers (a pre-release counts; `-ci-abc`, `rc1`,
  no `v`, `V`, a trailing dot do not), the highest version wherever it is listed; versions compare as integer tuples
  with trailing zeros dropped (0.2 = 0.2.0, 0.10 > 0.9); a `version` that does not parse is never older;
- newer: fetches that release's SHA256SUMS asset (`browser_download_url`, http(s), at most 64 KB), takes the
  `<64 hex>  install.sh` line, and builds the guide's line exactly (`install_line`):
  `curl -fsSLO https://github.com/neb882/song-charting/releases/download/v<new>/install.sh && echo "<sha>  install.sh" | sha256sum -c - && bash install.sh`.
  Only the version (digits and dots) and the sha (64 hex) come from the network, so the pasted line is always this
  one. Without a readable SHA256SUMS: `line` null, `url` only (the release's `html_url` when it is https, else the
  tag's page);
- writes `{"checked", "version", "latest", "line", "url"}` (atomically) and returns it when newer, else None; any
  failure (URLError, timeouts, HTTP errors, a body that is not a JSON list, too long, not UTF-8) writes
  `{"checked", "version", "error"}` and returns None;
- `say` gets one line saying what it found.

Decision (small, flagged): the order's signature has `url=RELEASES_URL`; I made it `url=None` meaning
"$SONGCHARTER_RELEASES_URL, else RELEASES_URL", so an explicit argument still wins over the environment. The download
base of the line is the constant `https://github.com/neb882/song-charting/releases/download` (the guide's), not
derived from the API's asset URLs: a URL from JSON never reaches the line the friend pastes into a shell.

### `songcharter/ui/server.py`
- `App(..., updates=None)`: a callable taking the log's `say`; `_main` passes `updates.check(root, __version__, say=...)`.
  The tests' Apps pass none (no check).
- `page_served()`: called after index.html is sent (`/` or `/index.html`); the first call starts a daemon thread
  `songcharter-updates` once per process. Nothing on the startup path (bind, the self-check, find_running, the doctor
  thread) asks for it.
- `/api/status` gets `update`: `{"version", "line", "url"}` or null.
- The check's one line goes to the log file (`console=False`), not the console window.

### The page (`index.html`, `app.js`, `app.css`)
- `<section id="update" hidden>` first in `<main>` (under the header): "songcharter <new> is out (you have <this>).
  To update: close this window, open Ubuntu from the Start menu, paste this line and press Enter:", the line in a
  read-only text input, **Copy**, the release page's link (https only), **Later**. Without a line: "Its release page
  has the line to paste in Ubuntu, and the steps:" and the link only.
- "you have <this>" comes from `/api/hello`'s version, asked once, only when there is an update to show.
- Copy: `navigator.clipboard.writeText` (button "Copied" and a hint); with no clipboard (the fallback address is
  not a secure context) or a refused write, it focuses and selects the line, the button says "Select and copy" and
  the hint says to press Ctrl+C.
- Later: hidden for this page load (a later status refresh does not bring it back).
- The server's check starts with the page, so the first `/api/status` usually comes before its answer: the page asks
  `/api/status` again at 2, 6 and 15 s while it has no update (and stops once it has one or Later was pressed). The
  same refresh as "Chart another song" (`refreshStatus`), which now also passes `update` on.

### CI: `packaging/ci/linux.d/75-update.sh` (new)
(see its header) v0.1.0's files rebuilt from the tag in a detached worktree with the tag's own build.sh; HEAD's as
`<HEAD's __version__>-ci-<sha>`; a local `http.server` at the release paths; ubuntu:26.04 with the WSL image's tools
and `friend`, `--network host`, `--init`. Checks, in order: the notice's `install_line` for the new version equals
GUIDE.md's line; each line's one change is github.com to the server; 0.1.0 installed with its line (Enter); the clip
charted (work folder noted); the new line over it: `install.sh: OK`, `songcharter <new>: in $HOME/.local/share/
songcharter/app/<new>`, app/ holds <new> alone, runtime.json's app, `uv 0.13.5: already here`, no download line
(runtime.py's `fetch`, uv's `Download(ing|ed)`, install.sh's `downloading`, uv's `Installed Python`), and the access
log since the mark only install.sh, the tarball (each once) and SHA256SUMS; `songcharter doctor` exits 0 with
`songcharter <HEAD's __version__>, Python 3` and `doctor: OK`, and the install's Python imports
`songcharter.updates`; a second chart into the same work folder with separate, drums, bass, sections and guitar
`(cached)`, and check_gate.py on it; the page four times (v9.9.9 out: update exactly the expected JSON, the JSON and
SHA256SUMS asked once each; again with v0.1.0 only: the kept answer still 9.9.9, no request; the stamp deleted:
null; unreachable: null, an error stamp, /api/hello answering), each with `/api/status` null before the page and
no check line in the log until the page; uninstall (Enter = No), the new line again, no download, `doctor --quick`.
Also reported (never failed on): whether the rebuilt v0.1.0 SHA256SUMS is the published one.

### Docs
- `docs/guide/windows-wsl.md` section 3: the update bullet now says the page's box is how a new version shows up,
  then the same steps.
- `docs/DESIGN.md` 4.5: a bullet on the notice and the CI hook.
- `README.md` (Using it): an Updates bullet.

## Decision on the version (flagged for the orchestrator)

HEAD's `__version__` is 0.1.0 (the bump to 0.2.0 is the release's). doctor reports `__version__`, so "doctor must
report the new version" cannot tell 0.1.0 from HEAD until the bump. The hook builds HEAD as
`<__version__>-ci-<sha>` (as 50-e2e and 70-release do), checks doctor's version line equals HEAD's `__version__`
(0.1.0 today, 0.2.0 after the bump, with no edit to the hook), and proves the new code is installed by runtime.json's
`app` (app/<new>) and by importing `songcharter.updates`, which 0.1.0 does not have.

## Checks

- **Targeted tests (dev, before the worktree's own venv existed, with the old checkout's Python and the worktree's
  code on sys.path):** `python -m pytest -q tests/test_ui_server.py tests/test_updates.py` -> `70 passed in 21.07s`.
  New: `tests/test_updates.py` (12 tests), and 4 in `tests/test_ui_server.py` (the check once after the first page and
  `/api/status`'s update, on a daemon thread `songcharter-updates`; a failing or empty check; `songcharter ui`'s
  startup path asking nothing (S.main in a subprocess with urlopen recording every request but its own port's); the
  page in node with a stand-in DOM and clipboard).
- **The full suite (dev):** queued as `tools/heavy.sh uv run python -m pytest -q -p no:cacheprovider
  --basetemp=/dev/shm/pt-m5-07 -rs` (`<scratchpad>/m5-07/suite.sh`, output `<scratchpad>/m5-07/suite.log`) behind
  the heavy lock, which golden runs held from 23:25 (base-main) and 00:17 (stress-base-main). Still queued when this report was written (00:40): the
  stress golden run was on its first of three songs. When it runs, its last lines and `suite exit N` land in
  `<scratchpad>/m5-07/suite.log`. CI's run 2 below ran the same full suite on the same head (07ec2a5), green.
- **CI run 1, https://github.com/neb882/song-charting/actions/runs/42131709120 (a7ec93a): failure**, in 75-update.sh
  only, at the no-download check: install.sh's `downloading <server>/v<new>/songcharter-<new>.tar.gz` line is the
  update's one expected download (e2e.sh's reinstall uses `--from`, so its log has none). Everything before it had
  passed (the suite, the other seven hooks, and in 75-update: the v0.1.0 rebuild, 0.1.0's install, its chart, and the
  update itself, which ended "songcharter 0.1.0-ci-a7ec93a is installed"). Fixed in 07ec2a5: that exact line is
  allowed (and required); any other `downloading` line still fails, tested on four made-up logs.
- **CI run 2, https://github.com/neb882/song-charting/actions/runs/42134163994 (head 07ec2a5): success.** Suite
  `997 passed, 4 skipped in 476.46s`; CI tools `86 passed`; `all 8 Linux hooks passed: 10-lanes.sh 15s 20-device.sh
  6s 30-install.sh 160s 40-ui.sh 27s 50-e2e.sh 481s 60-results.sh 83s 70-release.sh 88s 75-update.sh 181s`; Windows
  `all 1 Windows hooks passed`. 75-update.sh's log, excerpted:
  ```
  75-update: v0.1.0 is f8ac008b521756f6cb41a7036989063b69123005
  75-update: the files rebuilt from v0.1.0 are the published release's (the same SHA256SUMS)
  75-update: the notice's line for 0.1.0-ci-07ec2a5 is GUIDE.md's
  -- v0.1.0, with its guide's line: ok in 52 s
  stages: decode 0.6 s, separate 18.1 s, drums 1.1 s, bass 11.6 s, sections 10.5 s, guitar 25.5 s, assemble 1.5 s, preview 2.4 s; total 71.5 s
  -- the clip, charted by 0.1.0: ok in 74 s
  nothing downloaded but the app (install.sh's line: downloading http://127.0.0.1:44141/neb882/song-charting/releases/download/v0.1.0-ci-07ec2a5/songcharter-0.1.0-ci-07ec2a5.tar.gz)
  -- the new version's line, pasted over 0.1.0: ok in 7 s
  75-update: the update fetched install.sh and the tarball, once each, and nothing else from the server
  songcharter 0.1.0, Python 3.13.17 (/home/friend/.local/share/songcharter/runtime/env/bin/python), Linux-...
  doctor: OK
  the new code: /home/friend/.local/share/songcharter/runtime/env/lib/python3.13/site-packages/songcharter/updates.py
  [2/8] separate: 6 stems on cpu (cached), 0.0 s
  [3/8] drums: 119 Expert onsets (cached), 0.2 s
  [4/8] bass: 120 Expert onsets (cached), 0.0 s
  [5/8] sections: allin1 harmonix-fold0 on cpu, 3 segments (cached), 2.9 s
  [6/8] guitar: 1 take, 23 Expert onsets in the first (cached), 0.0 s
  check_gate: ok, /home/friend/Songs/Clip after the update: gate ok, scan-chart 8.0.1 playable with 0 chart issues; Expert onsets guitar 23, bass 120, drums 119
  update check: songcharter 9.9.9 is out (this is 0.1.0): https://github.com/neb882/song-charting/releases/tag/v9.9.9
  update: {'version': '9.9.9', 'line': 'curl -fsSLO https://github.com/neb882/song-charting/releases/download/v9.9.9/install.sh && echo "64b15b4e...7be033  install.sh" | sha256sum -c - && bash install.sh', 'url': 'https://github.com/neb882/song-charting/releases/tag/v9.9.9'}
  update check, 0 min ago: songcharter 9.9.9 is out (this is 0.1.0): ...      (v0.1.0 listed only: the kept answer, no request)
  update check: songcharter 0.1.0 is the newest (the newest release is 0.1.0)   -> update: None
  update check failed: http://127.0.0.1:54941/releases.json: URLError: <urlopen error [Errno 111] Connection refused>; ...  -> update: None
  -- songcharter uninstall (No), then the new line again: ok in 9 s
  75-update: ok (0.1.0, then 0.1.0-ci-07ec2a5 over it, and the notice)
  ==== hook linux.d/75-update.sh ok in 181 s
  ```
  A finding of its own: the v0.1.0 files rebuilt in CI from the tag have the published release's SHA256SUMS byte
  for byte (install.sh b55fe04e..., the tarball 070c9a87...), so the update path starts from the friend's exact
  0.1.0. The hook only reports this; it never fails on it.
- **No golden run:** the order touches no charting path (the server, the page, a new module the chart never imports,
  a CI hook, docs).

## Mutations (each break of the new code fails a test)

Run with `<scratchpad>/m5-07/mutate.py` (each mutation applied alone, the named tests run, the file restored):
28 breaks, each caught (`CAUGHT` = the named tests failed):
- updates.py: the same version counted as newer; pre-releases skipped; a suffixed tag counted (`match` for
  `fullmatch`); drafts counted; the line's two spaces made one; any SHA256SUMS line taken; no day stamp; no hour wait
  after a failure; no offline rule; timeouts and URLErrors not caught; no User-Agent; the first listed release taken
  instead of the highest; a tampered stamp's line shown; file:// allowed; $SONGCHARTER_RELEASES_URL ignored.
- server.py: the check started on the startup path; on any static file; on every page; synchronously in the
  handler (missed at first: the response is sent before the check, so a client cannot tell; the test now records the
  opener's thread, which must be the daemon `songcharter-updates`, and catches it); no `update` in the status; a
  bug in the check escaping; the check's line not given to the log.
- app.js: Copy writing something else; no select on the fallback; Later ignored by later renders; no asks again
  after the start; asking forever after the update arrived; a non-https link shown.

## Not done, or uncertain

- **The version string (above):** until the release bumps `__version__`, doctor's "the new version" line cannot
  tell old from new; the hook proves the new code another way. When the release order bumps it to 0.2.0, the hook
  needs no edit (it reads `__version__` from HEAD).
- **`songcharter/ui/__init__.py`'s docstring** lists what the UI keeps in $SONGCHARTER_HOME; `state/update.json` is
  not in that list, as the file is not in this order's list. updates.py's and server.py's docstrings say where it is.
- **`packaging/ci/linux.d/README.txt`'s names table** (10 ... 70) has no row for 75; that file is not this order's
  either (the hooks' README says an order adds its own hooks and nothing else in packaging/ci/).
- **`check`'s signature:** `url=None` (env, else RELEASES_URL) instead of the order's `url=RELEASES_URL` (above).
- **The page asks `/api/status` again at 2, 6 and 15 s** after the start while it has no update, since the check
  begins only once the page is served; a check slower than 15 s (two requests of 5 s each at most, plus DNS) shows
  its notice at the next status refresh ("Chart another song") or the next page load (the answer is kept a day).
- **40-ui.sh and 70-release.sh** each fetch the page once (`curl "$base/"`, `curl "$address"`), so each server now
  makes one real request to GitHub's API in CI: the check finds v0.1.0, not newer than 0.1.0, and logs it. A rate
  limit there would only log a failure; neither hook looks at it. (50-e2e's ui_guards.py asks only the API.)
- **The real releases API was not called by any test:** the JSON shape the check reads (tag_name, draft, prerelease,
  html_url, assets[].name and browser_download_url) was read once from the live API by hand (`gh api`) while
  writing it.

## Scan

`git diff origin/main...HEAD` and `git log origin/main..HEAD`: no assistant-model names (the trailers aside), no
paths but the container's made-up `/home/friend`, no emails, no audio (the clip's in-container paths only), no lyrics.

## Review (sc-reviewer, 2026-11-06)

# M5-07 review (sc-reviewer, 2026-11-06, head 07ec2a5): no major code defect; five findings

(Saved by the orchestrator from the reviewer's reply; its repro scripts probe1.py, probe2.py and mut/run.py are in
the scratchpad and import from a copy of the branch at /dev/shm/review_m507, now deleted.)

- **F1 (test that cannot fail; the orchestrator routes it as a test gap).** updates.py:57 `SUM_LINE`: the
  `[0-9a-f]{64}` class is the only thing keeping SHA256SUMS text out of the pasted line; loosening it to `(\S{64})`
  leaves all 15 tests green, and a hostile SHA256SUMS then puts a shell command substitution into the line the
  friend pastes. The stamp re-check would reject it the next day, but the first answer goes to the page. The test's
  "not a SHA-256" case only uses a short `0123`: it needs a 64-character entry that is not hex, with shell
  metacharacters, expecting line None.
- **F2 (test gaps).** updates.py:157, the SHA256SUMS size cap (MAX_SUMS replaced by 1 GB passes); updates.py:96, `0 <=
  age` dropped for error stamps (a future error stamp, WSL2 clock skew, blocks the check until the clock catches up;
  only a future success stamp is tested); updates.py:153, `_page` accepting a non-https html_url (app.js hides it).
- **F3 (minor defect).** updates.py:56 `VERSION = r"\d+..."`: `\d` matches Unicode digits, so `v٩.٩` counts as newer
  and the pasted URL is non-ASCII; a tag of `v` and 5000 nines makes int() raise ValueError outside check's try (no
  stamp, the API asked on every start). Fix: [0-9] or re.ASCII, a length bound, ValueError as Failed.
- **F4 (minor).** updates.py:149 and :189 accept any https:// release-page URL; app.js checks only the scheme. Fix:
  build it as RELEASE_PAGE.format(version=latest) and ignore html_url.
- **F5 (CI hygiene).** 40-ui.sh and 70-release.sh now make one real GitHub API request each (the page is served
  once). Set SONGCHARTER_RELEASES_URL to a closed local port in both hooks (not SONGCHARTER_OFFLINE, which would
  block 70-release's install downloads).
- The builder's two decisions: both agreed. Its "not done" items (README.txt row for 75, ui/__init__ docstring):
  fine to fold into the release.
- Checked and fine: network text reaches the page only via textContent and input.value; User-Agent, timeouts, the
  releases size cap, OFFLINE, the atomic stamp, foreign stamps ignored; the thread starts once after index.html and
  never blocks; Copy's fallback and Later; 75-update.sh's checks can fail (its 010 case can't tell "0.1.0 is newest"
  from a crash after its one request; the 999 and unreachable cases cover the crash path).

## Review fixes

f2141ce and 15a3d26 (the fixer's session ended in a container restart before it wrote this section; the orchestrator read the diff): VERSION takes ASCII digits, at most 10 parts of 9 digits; a parse error in check is a failure with its stamp; the release page is always RELEASE_PAGE (html_url ignored, the stamp's url checked against it); tests for a 64-character non-hex SHA256SUMS entry with shell metacharacters, an oversized SHA256SUMS, a future error stamp; 40-ui.sh and 70-release.sh point SONGCHARTER_RELEASES_URL at a closed local port; the hooks' README row for 75 and the UI home list. CI run 42139014269 on 15a3d26: success.
