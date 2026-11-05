# M5-07: the page's update notice with a Copy button, and the update path tested in CI

**Branch:** `m5-07-updates`, from `main` after wave 4 (wave 5, alone). **Agent:** `sc-builder`, then `sc-reviewer`.
May push its branch to run CI. **Files:** `songcharter/ui/server.py`, `songcharter/ui/static/{index.html, app.js,
app.css}`, a new `songcharter/updates.py`, `songcharter/launch.py` (environment only, if needed),
`packaging/ci/linux.d/75-update.sh` (new), `packaging/ci/linux.d/70-release.sh` only to share a helper, their tests,
`docs/guide/windows-wsl.md` (section 3's update bullet), `docs/DESIGN.md` 4.5, the README. Not `.github/workflows/
ci.yml` unless the tag fetch below cannot be done from the hook (then one line, said in the report). **Time budget:**
1.5 days, CI included.

## Why

The friend updates by pasting the new version's install line (the guide's section 3), but nothing tells him a new
version exists, and the update path has never run anywhere: CI installs one version, and `install.sh` removes the
other `app/*` folders and rebuilds the wheel (PROGRESS `deferred`, the advisor's finding 10). The owner leans to a
notice on the page with a Copy button for the new line rather than a one-click updater (PROGRESS, 2026-11-05;
M5-00 says what the updater would add) [owner].

## What to build

1. **`songcharter/updates.py`:** `check(home, version, url=RELEASES_URL, timeout=5.0) -> dict | None`:
   - reads `<home>/state/update.json` and returns it when it is under a day old (`CHECK_EVERY_S` = 86400) and for
     this version; otherwise fetches `url` (`https://api.github.com/repos/neb882/song-charting/releases?per_page=10`,
     `SONGCHARTER_RELEASES_URL` overriding it for CI), takes the newest non-draft release whose tag is `v<version>`
     with a version that parses as dotted integers (a pre-release counts while songcharter is under 1.0 [owner];
     a tag with a suffix such as `-ci-abc` does not count), and compares it with `version` the same way;
   - when newer: fetches that release's `SHA256SUMS` asset (its `browser_download_url`), reads install.sh's line, and
     builds the guide's line exactly: `curl -fsSLO <download base>/v<new>/install.sh && echo "<sha>  install.sh" |
     sha256sum -c - && bash install.sh`; without a readable SHA256SUMS the result has no line, only the release page's
     URL;
   - writes update.json `{"checked", "version", "latest", "line", "url"}` and returns it; any failure (offline, a
     timeout, a 4xx, JSON that does not parse) returns None and writes a stamp with `"error"` so it is not retried for
     an hour (`RETRY_AFTER_S` = 3600). With `SONGCHARTER_OFFLINE=1` it never fetches. Only `urllib`, no new dependency;
     the request names `songcharter/<version>` as its User-Agent.
2. **The server:** after the first page is served (never on the startup path), a daemon thread runs `check` once per
   server process; `/api/status` gets `update`: `{"version", "line", "url"} | null`. The server's log says what it
   found, one line.
3. **The page:** when `update` is set, a box under the header: "songcharter <new> is out (you have <this>). To update:
   close this window, open Ubuntu from the Start menu, paste this line and press Enter:" then the line in a read-only
   text box with a **Copy** button (`navigator.clipboard.writeText`, which the browser allows on `localhost`; on the
   fallback address it is unavailable, so the button then selects the text and says "select and copy"), and a link to
   the release page. "Later" hides it for this page load. Nothing else on the page changes; charting is never blocked.
4. **CI, the update path** (`packaging/ci/linux.d/75-update.sh`, in 70-release.sh's manner: the same container image,
   the same local server, `friend` as the user):
   - v0.1.0's four files built from the tag (`git fetch --depth=1 origin tag v0.1.0` in the hook, then a detached
     worktree and `packaging/release/build.sh 0.1.0`: the published assets were built the same way from the same
     tree) and the new version's files from HEAD, served at their release paths;
   - install 0.1.0 with its guide line (the licence prompt answered with Enter), chart the CI clip from the command
     line (`songcharter chart`), note the work folder's path;
   - paste the new version's line over it: the install must say "songcharter <new>: in .../app/<new>", `app/0.1.0`
     must be gone, the server's access log must show only install.sh, the tarball and SHA256SUMS fetched for it (no
     Node, uv, Python, torch or model download: the runtime is kept), `songcharter doctor` must report the new
     version with no problem, and a second chart of the clip must reuse the work cache (its stage lines say
     "(cached)" for separate, drums, bass, sections and guitar);
   - the notice: with `SONGCHARTER_RELEASES_URL` pointing at a JSON file the hook writes on the local server (a
     release `v9.9.9` whose assets' URLs point at the server, with a SHA256SUMS there), `songcharter ui` started as
     the guide does and `/api/status` read after the page: `update.version` 9.9.9 and `update.line` exactly the
     expected line; with the JSON listing only `v0.1.0`, `update` null; with the URL unreachable, null and the server
     up. Also `songcharter uninstall` answered No, then the new line again: a reinstall after an update works.
   - The hook's logs go to `$CI_ART/75-update` (no audio).

## Tests

- `updates.check` with a stand-in opener: newer → the line with the right sha and tag; the same or older → None
  with a stamp; a pre-release newer counts; a `-ci-` tag does not; a draft does not; SHA256SUMS missing → url only;
  a stamp under a day old is returned without fetching; an error stamp under an hour old is returned as None
  without fetching; offline never fetches; a timeout → None.
- The server: `/api/status` carries `update` once the thread has run (a stand-in `check`); the startup path makes no
  request.
- The page: the box renders from `update`, Copy writes the line (a stub clipboard), "Later" hides it.
- Each test fails when its code is broken (say which break).

## Evaluation

- No charting path: no golden run.
- [CI] The new hook runs and passes (read its log; confirm it ran).

## Done means

- [dev] The suite; the new tests fail when their code is broken.
- [CI] Green, 75-update.sh included.
- [docs] The guide's section 3: the notice is how he learns of a new version, then the same steps; DESIGN 4.5; the
  README's update paragraph.

## Limits

- No automatic install, no download by the page, no change to `install.sh`. The check is one request a day at most.
- Nothing personal in the request (the User-Agent names the program and its version only).

## Report

`<scratchpad>/briefs/m5-07.report.md`: the commits, each check's last lines, the CI run's URL with the hook's log
excerpt, anything uncertain.
