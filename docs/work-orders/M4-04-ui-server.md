# M4-04: the local UI in WSL: server, jobs, progress and cancel

**Branch:** `m4-04-ui-server`, from `main` after M4-02 and M4-05a have merged. **Wave 2**, beside M4-03. **Agent:**
`sc-builder`, then `sc-reviewer` and `sc-inspector`. May push its branch to run CI.

## Intent

The friend never types a command after the install. The shortcut starts `songcharter ui` in WSL, and his Windows
browser opens on the page. He drops a song, keeps or changes the options the command line has, and watches one line
per stage with a cancel button. Every CPU fallback shows as it happens.

DESIGN 4.5's design holds: a standard-library server on loopback, a vanilla-JS page with no CDN, and its guards. The
chart runs as a child process group, so cancel stops everything it started: Node, allin1's Python, ffmpeg.

M4-06 adds what follows the build.

## Scope

Creates:
- `songcharter/proc.py`;
- `songcharter/ui/__init__.py`, `server.py`, `jobs.py`, `static/{index.html,app.js,app.css}`;
- `tests/test_proc.py`, `tests/test_ui_server.py`, `tests/test_ui_jobs.py`;
- `packaging/ci/linux.d/40-ui.sh`.

Changes:
- `cli.py`: `ui`, and `chart --events`;
- `pipeline.py`: an `events` callback;
- `engines/autochart.py`: a per-take callback;
- `pyproject.toml`: `songcharter.ui` and its static files as package data; no dependency change, so `uv lock --check`
  still passes.

Must not touch: `runtime.py`, `launch.py`, `wslsetup.py`, `winshortcut.py`, `packaging/linux/` (M4-03, the same
wave), `docs/`.

## Spec

### Events from a chart run

- `pipeline.chart(..., events=None)` sends dicts with `"event"`:
  - `plan` `{"stages"}`;
  - `stage_start` `{"stage", "index", "count", "detail"}`;
  - `take` `{"index", "count", "seed"}`, before each guitar take that runs;
  - `fallback` `{"stage", "from", "to", "reason"}` (M4-02's records);
  - `warning` `{"text"}`;
  - `stage_end` `{"stage", "seconds", "cached", "detail"}`.
- `engines.autochart.generate(..., on_take=None)` is called with `(index, count, seed)` before each take that is not
  cached. The first-take probe's second call continues the numbering.
- `cli chart --events` writes each event to stderr as `@@songcharter <json>` (`ensure_ascii=True`). Then:
  - after the summary, `result` `{"ok", "exit", "folder", "work", "preview", "summary"}`;
  - before exiting 2, 3 or 130, `error` `{"kind": "input"|"tool"|"bug"|"interrupted", "message"}`.

  Without `--events`, the output is unchanged.

### `songcharter/proc.py` (POSIX)

- `start(cmd, env, cwd, stdout, stderr) -> Tree` starts the command with `start_new_session=True`.
- `Tree.kill(timeout=5)`: `os.killpg(SIGTERM)`, then `SIGKILL` after `timeout`, then `wait()`. Idempotent.
- The process group holds the chart and everything it starts: autochart's `node` and its engine process, allin1's
  runner, ffmpeg.
- (Windows Job Objects belong to the native route: M4-99.)

### The server: `songcharter ui [--port N] [--no-browser] [--from-shortcut]`

#### Startup

1. **Already running?** `GET http://127.0.0.1:<port>/api/hello` for ports 8765–8784. If one answers `{"app":
   "songcharter"}`, open the browser there (below) and exit 0.
2. **Bind** a `ThreadingHTTPServer` to 127.0.0.1 on the first free port from 8765. Each start makes an instance
   token, `secrets.token_hex(8)`, which `/api/hello` returns.
3. **The Windows self-check** (WSL with interop): `wsl.windows_curl("http://localhost:<port>/api/hello")` must return
   this instance's token.
   - That proves Windows' localhost reaches this server: localhost forwarding is on by default, for "ports bound to
     wildcard or localhost" [doc: wsl-config.md].
   - If the answer is another program's (the port is taken on Windows), try the next port.
   - If nothing on 8765–8784 passes, **fall back**:
     - also bind WSL's own address (the first address of `hostname -I`) on the same port;
     - add it to the allowed hosts and origins;
     - log "Windows' localhost does not reach WSL here (localhostForwarding off, or the port is taken); using
       http://<ip>:<port>/".
     - That address is on WSL's host-only NAT network, so it is no wider than localhost [inference].
4. **Open the browser**, unless `--no-browser`:
   - in WSL, `wsl.open_url(url)`, that is `explorer.exe <url>`;
   - elsewhere, `webbrowser.open`;
   - print the URL in every case.
5. **Log** to `$SONGCHARTER_HOME/logs/ui-<date>.log` and to the console window.
6. **Shut down:**
   - on SIGHUP or SIGTERM (the friend closes the window), the server kills a running job's tree and exits;
   - a page the friend closes does not stop the server.

#### Guards (DESIGN 4.5)

- The `Host` header must be one of the allowed hosts (`127.0.0.1:<port>`, `localhost:<port>`, and the fallback
  address when used). Otherwise 403.
- Every non-GET request needs `X-Songcharter: 1` and an `Origin` from the same list. Otherwise 403.
- Every response carries `Content-Security-Policy: default-src 'self'; img-src 'self' data:; connect-src 'self';
  script-src 'self'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. Never a CORS header.
- Static files only from the package's `ui/static/`, by exact name.

#### Endpoints

- `GET /`, the static files, and `GET /api/hello` (`{"app", "version", "token"}`).
- `GET /api/status`: the doctor summary (`$SONGCHARTER_HOME/doctor.json`, or a quick `device.report(full=False)`):
  device, gpu, guitar device and reason, notes, ok. Plus the current job, and the defaults with `threads_default`.
- `POST /api/upload`:
  - the body is the raw file; header `X-Filename` (percent-encoded);
  - the extension must be one of `.mp3 .wav .flac .ogg .opus .m4a .aac .wma .aiff .aif`, otherwise 415;
  - at most 1 GB, otherwise 413;
  - streamed to `$SONGCHARTER_HOME/uploads/<16 hex of its SHA-256>/<cache.safe_name(stem)><ext>`;
  - answers `{"id", "name", "bytes", "tags", "origin"}` (`pipeline.read_tags` and `song_metadata`);
  - uploads older than 7 days go when the server starts.
- `POST /api/jobs` `{"upload", "options"}`:
  - 409 while a job runs;
  - 400 with `Options.check()`'s message;
  - otherwise 202 `{"job"}`.
- `GET /api/jobs/current` gives the state (`running | done | failed | cancelled`) and the events.
- `GET /api/jobs/current/events` is SSE: it replays every event, then streams new ones, with a keepalive every 15 s.
  It closes after `result`, `error` or `cancelled`.
- `POST /api/jobs/current/cancel`:
  - `Tree.kill()`, then state `cancelled`;
  - then deletes `.<name>.*.partial` folders beside the output (assemble's staging);
  - the work folder's caches stay.

#### A job (`ui/jobs.py`)

- **The command:** `[sys.executable, "-m", "songcharter.cli", "chart", <upload>, "--out", <out>, "--events", ...]`,
  with the server's environment (the launcher's) and `PYTHONUTF8=1`.
  - `--threads` is `device.default_threads()` when the options leave it empty and the device is the CPU.
- **The output folder:** `$SONGCHARTER_HOME/library/<16 hex>/<cache.safe_name(f"{artist} - {title}")>`. The name is
  safe for Windows, because M4-06 copies it to `/mnt/c`.
- **Reading the child:** stderr line by line (UTF-8, `errors="replace"`). `@@songcharter` lines become events. Every
  line goes to `logs/job-<yyyyMMdd-HHmmss>.log`.
- **The end state:** exit 0 or 1 gives `done` (the verdict is in `result`); 2 or 3 gives `failed`; a kill gives
  `cancelled`.

### The page

No framework and no build step. Every request sends `X-Songcharter: 1`.

1. **Header:**
   - "GPU: <name> (<GB> GB)", or "CPU mode: <reason>";
   - then "guitar on the GPU", or "guitar on the CPU: <reason>";
   - the doctor's notes under "Details".
2. **Drop:** a drop zone and a file button; upload progress; the 415 message.
3. **Options**, prefilled from the tags and defaults, one for one with the CLI:
   - title, artist, album, year, genre;
   - instruments;
   - difficulties;
   - solos;
   - guitar takes ("default: 4 on a GPU, 1 on the CPU");
   - device;
   - preview.

   Then a "Chart it" button.
4. **Progress:**
   - one row per stage, with a state icon, its detail, and a ticking elapsed time;
   - "take k of n" under the guitar row;
   - the warnings;
   - every `fallback` event as a banner: "<stage> runs on the CPU: <reason>";
   - Cancel, with a confirm;
   - a reload reattaches to the current job through SSE.
5. **Done:** "Ready" or "The check failed", the summary in a `<pre>`, and "Chart another song".

## Done means

[dev] In the dev container:

1. The suite passes, with new tests:
   - **`test_proc.py`:** a child that starts a grandchild (`sleep 60`) leaves neither alive after `Tree.kill`
     (checked by pid).
   - **`test_ui_server.py`,** on an ephemeral port:
     - `Host: evil.example` gives 403;
     - a POST without the header gives 403, and with `Origin: http://evil.example` 403;
     - a `.txt` upload gives 415;
     - two job starts give 202 and 409 (stand-in runner);
     - SSE replays events to a late client;
     - the CSP is on every response;
     - `..` in a static path gives 404;
     - the self-check, with a stand-in `windows_curl` that answers another token, moves to the next port; when
       every port fails, the fallback address is allowed as a host.
   - **`test_ui_jobs.py`:** `@@songcharter` parsing; a stand-in chart that exits 1 ends as `done` with `ok: false`;
     cancel ends as `cancelled` with no `.partial` folder left.
2. `songcharter chart <clip> --out /dev/shm/m4-04/Clip --device cpu --threads 2 --events` prints:
   - `plan`;
   - 8 start/end pairs;
   - 1 `take`;
   - `result` with `"ok": true`.

   It exits 0. Without `--events`, the output is byte-identical to `main`'s. The clip comes from
   `packaging/ci/make_clip.py` (M4-05a).
3. Manual: `songcharter ui --no-browser --port 8799` in the container:
   - `curl` uploads the clip and follows the job to `result`;
   - a second job cancelled during `guitar` leaves no `node` or `songcharter.cli` process (`ps -eo pid,args`).
4. The golden charts show no UNEXPECTED change.

[CI] Hook `40-ui.sh` (`ubuntu-latest`): the new tests, plus a guards run against `songcharter ui --no-browser`:
- `Host` 403;
- `Origin` 403;
- `.txt` 415;
- a job started on the clip.

The real cancel at the first `take` is M4-05's, once the install exists.

[Hardware] M4-08:
- the shortcut opens the page in the Windows browser;
- the self-check passes on both PCs (or the fallback address works);
- cancel works during the guitar stage on CUDA.

## Depends on

- M4-02: `wsl.py` (`windows_curl`, `open_url`), `device`, the fallbacks;
- M4-05a: the hooks and the clip.
