# M4-04: the local UI: server, jobs, progress and cancel

**Branch:** `m4-04-ui-server`, from `main` after M4-02 has merged. **Wave 2**, beside M4-03. **Agent:**
`sc-builder`, then `sc-reviewer` and `sc-inspector`.

## Intent

The friend never sees a command line. He drops a song file into a page on his own machine, keeps or changes the
options the command line has, and watches one line per stage with a cancel button. Any CPU fallback is shown as it
happens, not buried in a log.

The page is DESIGN 4.5's design: a standard-library server on 127.0.0.1, a vanilla-JS page with no CDN, and its
guards. The chart runs as a child process, so cancel can stop everything it started: Node, allin1's Python, ffmpeg.

This order ends at "the build finished, and here is its verdict". M4-06 adds the preview, the export and the
diagnostics.

## Scope

Creates:
- `songcharter/proc.py`: start a process tree, kill a process tree;
- `songcharter/ui/__init__.py`, `songcharter/ui/server.py`, `songcharter/ui/jobs.py`;
- `songcharter/ui/static/index.html`, `app.js`, `app.css`;
- `tests/test_proc.py`, `tests/test_ui_server.py`, `tests/test_ui_jobs.py`.

Changes:
- `songcharter/cli.py`: the `ui` command, and `chart --events`;
- `songcharter/pipeline.py`: an `events` callback;
- `songcharter/engines/autochart.py`: a per-take callback;
- `pyproject.toml`: `songcharter.ui` in `packages`, and its static files as package data. No dependency changes, so
  `uv.lock` stays valid; check with `uv lock --check`.

Must not touch:
- `packaging/`, `runtime.py`, `launch.py` (M4-03, same wave);
- `docs/`.

## Spec

### Events from a chart run

- `pipeline.chart(..., events: Callable[[dict], None] | None = None)`. Every event is a dict with `"event"` and the
  fields below, sent in this order:
  - `plan`: `{"stages": [names in order]}`, as soon as the order is known;
  - `stage_start`: `{"stage", "index", "count", "detail"}`;
  - `take`: `{"index", "count", "seed"}`, before each guitar take (below);
  - `fallback`: `{"stage", "from", "to", "reason"}`, the same records M4-02 adds to `pipeline.json`;
  - `warning`: `{"text"}`, every `warn`;
  - `stage_end`: `{"stage", "seconds", "cached", "detail"}`.
- `cli chart --events`: each event goes to stderr as one line, `@@songcharter ` followed by its JSON
  (`ensure_ascii=True`). The human lines stay as they are.
  - After the summary, the CLI sends `result`:
    `{"ok", "exit", "folder", "work", "preview": result.preview or null, "summary": the summary text}`.
  - On an error it sends `error`: `{"kind": "input" | "tool" | "bug" | "interrupted", "message"}`, before exiting
    2, 3 or 130.
- `engines.autochart.generate(..., on_take: Callable[[int, int, int], None] | None = None)` is called with
  `(index, count, seed)` before each take that is not a cache hit. `pipeline` passes it through as the `take` event.
  The count is that call's number of seeds; for the first-take-alone probe the second call continues the numbering.

### `songcharter/proc.py`

- `start(cmd, *, env, cwd, stdout, stderr) -> Tree`.
  - **Windows:** `subprocess.Popen` with `creationflags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`. Then,
    through ctypes:
    - a Job Object (`CreateJobObjectW`), its `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` with
      `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`;
    - `AssignProcessToJobObject(job, process handle)`.
    - Children join the job (nested jobs are allowed on Windows 8 and later). The window between `Popen` and the
      assignment is harmless here: the child is our own Python, which imports for well over 100 ms before it
      starts anything.
  - **POSIX:** `start_new_session=True`.
- `Tree.kill(timeout=5)`.
  - **Windows:** `TerminateJobObject`; as a backstop, `taskkill /T /F /PID <pid>`.
  - **POSIX:** `os.killpg(SIGTERM)`, wait `timeout`, then `SIGKILL`.

  Then `wait()`. Idempotent.
- `Tree.close()` closes the job handle. The server keeps it open for the job's life, so closing the console window
  that runs the server kills the job too.

### The server (`songcharter ui [--port N] [--no-browser] [--home DIR]`)

- **Socket and lifetime:**
  - `http.server.ThreadingHTTPServer`, bound to 127.0.0.1 only;
  - the port is 8765, else the first free of 8766–8784;
  - before binding, `GET http://127.0.0.1:8765/api/hello`: if it answers `{"app": "songcharter"}`, open the
    browser there and exit 0 (one server per user);
  - `webbrowser.open` once the socket listens, unless `--no-browser`;
  - logs go to `<home>\logs\ui-<date>.log` (home = `$SONGCHARTER_HOME`, else `cache.user_cache()`), and to the
    console.
- **Guards** (DESIGN 4.5; every response):
  - The `Host` header must be `127.0.0.1:<port>` or `localhost:<port>`. Otherwise 403.
  - Every non-GET request needs `X-Songcharter: 1` and an `Origin` of `http://127.0.0.1:<port>` or
    `http://localhost:<port>`. Otherwise 403.
  - Headers: `Content-Security-Policy: default-src 'self'; img-src 'self' data:; connect-src 'self'; script-src
    'self'; style-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'`,
    `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and no CORS header ever.
  - Static files come only from the package's `ui/static/`, by exact name.
- **Endpoints** (JSON unless said):
  - `GET /` and the static files.
  - `GET /api/hello` gives `{"app": "songcharter", "version"}`.
  - `GET /api/status` gives `{"doctor": <home>\doctor.json's device, gpu, guitar_device, guitar_reason, notes, ok,
    or a quick device.report(full=False) when absent>, "job": current job summary or null, "defaults": the
    Options defaults, with "threads_default"}`.
  - `POST /api/upload`:
    - the body is the raw file; header `X-Filename` (percent-encoded);
    - the extension must be one of `.mp3 .wav .flac .ogg .opus .m4a .aac .wma .aiff .aif`, otherwise 415;
    - at most 1 GB, otherwise 413;
    - streamed to `<home>\uploads\<16 hex of its SHA-256>\<safe_name(stem)><ext>` (`cache.safe_name`);
    - answers `{"id", "name", "bytes", "tags", "origin"}`: `tags` are the song.ini values `pipeline.read_tags` and
      `pipeline.song_metadata` give for the file, and `origin` says where each came from;
    - uploads older than 7 days are deleted when the server starts.
  - `POST /api/jobs` with `{"upload": id, "options": {"instruments", "levels", "solos", "takes", "device",
    "threads", "preview", "title", "artist", "album", "year", "genre"}}`:
    - 409 while a job runs;
    - 400 with the message of `pipeline.Options(...).check()` (or the CLI's parsing) when an option is bad;
    - otherwise starts the job (below) and answers 202 with `{"job": id}`.
  - `GET /api/jobs/current` gives the job's state: `queued | running | done | failed | cancelled`, plus its events
    so far.
  - `GET /api/jobs/current/events` is `text/event-stream`:
    - replays every event so far, then streams new ones, each as `data: <json>\n\n`;
    - a `: keepalive` comment every 15 s;
    - closes after `result`, `error` or `cancelled`.
  - `POST /api/jobs/current/cancel`:
    - `Tree.kill()`, then state `cancelled`;
    - then deletes `.<name>.*.partial` folders beside the job's output (assemble's staging, `tempfile.mkdtemp(prefix=
      f".{name}.", suffix=".partial")`);
    - the work folder's caches stay: a new run of the same file reuses what finished.
- **A job** (`ui/jobs.py`):
  - **The command:** `[sys.executable, "-m", "songcharter.cli", "chart", <upload>, "--out", <out>, "--events",
    ...options as flags]`.
    - The environment is the server's (the launcher has set it), plus `PYTHONUTF8=1`.
    - `--threads` is `device.default_threads()` when the options leave it empty and `doctor` says the CPU.
  - **Output folder:** `<home>\library\<16 hex>\<safe_name(f"{artist} - {title}")>`. That folder name is the one
    Clone Hero lists. A rebuild of the same file replaces it: `check_output` allows it, since only a build wrote
    there.
  - **Logs:** stderr is read line by line (UTF-8, `errors="replace"`). `@@songcharter ` lines become events; every
    line also goes to `<home>\logs\job-<yyyyMMdd-HHmmss>.log`.
  - **End:** the exit code decides `done` (0 or 1: the gate's verdict is in `result`), `failed` (2, 3) or
    `cancelled`.
  - **One job at a time.** A job stays the current one until the next starts.

### The page (`static/`)

No framework and no build step; `fetch` and `EventSource` only; every request sends `X-Songcharter: 1`.

1. **Header**, always visible. From `/api/status`:
   - "GPU: <name> (<vram GB> GB)", or "CPU mode: <reason>";
   - then "guitar on WebGPU", "guitar on the CPU: <guitar_reason>" or "guitar on CUDA";
   - the doctor's notes under a "Details" toggle.
2. **Drop:**
   - a drop zone and a file button;
   - an upload progress bar (`XMLHttpRequest` upload events);
   - an unsupported type shows the server's 415 message.
3. **Options**, prefilled with the tags and the defaults, matching the CLI one for one:
   - title, artist, album, year, genre;
   - instruments: three checkboxes;
   - difficulties: Expert, or all, or a list;
   - solos: labels, off, or names;
   - guitar takes: default, 1, 3, 4, 5, with the default's rule shown: "4 on a GPU, 1 on the CPU";
   - device: auto, cpu, cuda;
   - preview: on or off.

   Then a "Chart it" button.
4. **Progress:**
   - one row per stage of `plan`, each with a state icon, its detail, and its elapsed time (a ticking clock while it
     runs, the event's `seconds` after);
   - "take k of n" under the guitar row;
   - warnings listed below;
   - every `fallback` event also shows as a banner at the top: "<stage> runs on the CPU: <reason>";
   - a Cancel button (with a confirm), which posts the cancel and shows "cancelled: the finished stages are kept, so
     charting this file again resumes";
   - reloading the page reattaches to the current job through `/api/jobs/current/events`.
5. **Done:**
   - the gate's verdict: "Ready" or "The check failed: see the details";
   - the summary text (`result.summary`) in a `<pre>`;
   - "Chart another song". M4-06 adds the preview and export here.

## Done means

[dev] In the dev container:

1. The full suite passes, with new tests:
   - `test_proc.py`: a Python child that starts a grandchild (`sleep`), killed by `Tree.kill`, leaves neither
     alive (checked by pid).
   - `test_ui_server.py`, against a server on an ephemeral port in a thread:
     - `GET /` with `Host: evil.example` gives 403;
     - `POST /api/upload` without `X-Songcharter` gives 403, and with a foreign `Origin` 403;
     - a `.txt` upload gives 415;
     - two concurrent `POST /api/jobs` give 202 and 409 (with a stand-in job runner);
     - SSE replays events to a late client;
     - responses carry the CSP;
     - a static path with `..` gives 404.
   - `test_ui_jobs.py`: the `@@songcharter` parsing; the events of a stand-in `songcharter chart` script (a small
     Python that prints known lines and exits 1) end as `done` with `ok: false`; cancel during it ends as
     `cancelled` with no `.partial` folder left.
2. `songcharter chart <clip.wav> --out /dev/shm/m4-04/Clip --device cpu --threads 2 --events` prints, in order:
   - `plan`;
   - 8 `stage_start`/`stage_end` pairs;
   - 1 `take`;
   - `result` with `"ok": true`;

   and exits 0. The clip is made by the planning job's generator, `briefs/m4-assets/make_clip.py` in the director's
   scratchpad (the brief gives the full path), until M4-05 commits it.

   Without `--events`, stdout and stderr are unchanged from `main`.
3. Manual, with the server running in the container (`songcharter ui --no-browser --port 8799`):
   - `curl` uploads the clip, starts a job, follows `/api/jobs/current/events` to `result`;
   - a second job, cancelled during `separate`, leaves no `songcharter` child process (`ps`).
4. No chart changes: the clip's `notes.chart` is byte-identical to `main`'s. Once `eval/golden.py` exists, it shows
   no UNEXPECTED change.

[CI-linux] and [CI-windows]: M4-05 runs a guard check (`packaging/ci/ui_guards.py`) against `songcharter ui
--no-browser`: 403, 403, 415, then a cancel that leaves no child, checked with `tasklist` on Windows.

[Windows HW] M4-08: the friend charts a song from the page alone; cancel works mid-guitar on the GPU.

## Depends on

M4-02 (its `pipeline.py` and `cli.py` changes, `device.default_threads`, the fallbacks record).
