#!/usr/bin/env bash
# 60-results.sh (M4-06): what follows the build, on ubuntu-latest, through a real `songcharter ui --no-browser`.
#   1. the tests (tests/test_clonehero.py, test_diagnostics.py, test_ui_server.py: stand-ins, no model);
#   2. the clip uploaded and charted through the API, on the CPU, without the guitar (the runner has no autochart
#      engine): done, ok; its results and preview pictures; the zip exported and downloaded (check_no_audio.py must
#      find its song.ogg); a Songs folder at "$CI_TMP/Jörg's Söngs/Clone Hero/Songs" set through the API, the clip
#      installed (200) with its four files checked, again (409, ours), then replaced (200, the older one in replaced/);
#   3. the server again with the variables the launcher sets for a finished install (launch.environment over a
#      runtime.json with models_complete, as runtime_record writes it: HF_HUB_OFFLINE=1), and the clip charted with
#      lyrics pasted (bass only: the stages before are cached). The aligner's weights are not here, so the chart must
#      try their first-use download (the release gate's major finding: the launcher once forbade it, and this hook
#      took that for the expected result). https_proxy names a port nothing listens on, so the download fails at once
#      and CI never fetches the 1.26 GB: the chart is made without lyrics, with a warning, and the reason must be the
#      failed download, not a refusal. No pasted word in any log, record or bundle (only notes.chart may ever hold
#      one);
#   4. the diagnostics bundle through the API and `songcharter diagnostics --out`: check_no_audio.py passes on each,
#      as the zip and unpacked. The bundles, the results and the logs go to $CI_ART/60-results.
# Run by packaging/ci/run-hooks.sh with bash -euo pipefail; uses CI_PY, CI_TMP, CI_ART and CI_CLIP (M4-05a's contract).
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
art="$CI_ART/60-results"
mkdir -p "$art"

"$CI_PY" -m pytest -q -p no:cacheprovider --basetemp="$CI_TMP/pt-results" tests/test_clonehero.py \
  tests/test_diagnostics.py tests/test_ui_server.py

port=8797
base="http://127.0.0.1:$port"
home="$CI_TMP/results-home"
songs="$CI_TMP/Jörg's Söngs/Clone Hero/Songs"
export SONGCHARTER_CACHE="$CI_TMP/results-cache"
rm -rf "$home" "$SONGCHARTER_CACHE" "$CI_TMP/Jörg's Söngs"
mkdir -p "$home" "$songs"
server=
start() {   # ENV=VALUE...: the server, with these set too, answering /api/hello
  env SONGCHARTER_HOME="$home" "$@" "$CI_PY" -m songcharter.cli ui --no-browser --port "$port" \
    >>"$art/server.txt" 2>&1 &
  server=$!
  for _ in $(seq 600); do
    curl -sf "$base/api/hello" >/dev/null && return 0
    kill -0 "$server" 2>/dev/null || { cat "$art/server.txt"; echo "60-results: the server exited" >&2; exit 1; }
    sleep 0.1
  done
  echo "60-results: the server did not answer in 60 s" >&2
  exit 1
}
stop() {
  [ -n "$server" ] || return 0
  kill -TERM "$server" 2>/dev/null || true
  wait "$server" 2>/dev/null || true
  server=
}
trap 'stop; cp "$home"/logs/*.log "$art/" 2>/dev/null || true' EXIT

# the API, as the page uses it: python - PHASE (chart | lyrics); its answers go to $art
drive() {
  "$CI_PY" - "$1" "$base" "$CI_CLIP" "$songs" "$home" "$art" <<'PY'
import io, json, sys, urllib.error, urllib.parse, urllib.request, zipfile
from pathlib import Path

phase, base, clip, songs, home, art = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4], Path(sys.argv[5]), \
    Path(sys.argv[6])
HEADERS = {"X-Songcharter": "1", "Origin": base}
LYRICS = "zorp blen-dak quiv\nfim wob\n\n[Glorp]\ndree smee plin\n"   # made-up words
WORDS = (b"zorp", b"blen", b"quiv", b"wob", b"Glorp", b"dree", b"smee", b"plin")


def say(text):
    print(f"60-results: {text}", flush=True)


def request(method, path, body=None, headers=None, raw=False):
    data = body if isinstance(body, bytes) or body is None else json.dumps(body).encode()
    h = {**(HEADERS if method != "GET" else {}), **(headers or {})}
    if data is not None and not isinstance(body, bytes):
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            payload, status, got = r.read(), r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        payload, status, got = e.read(), e.code, dict(e.headers)
    return (status, got, payload) if raw else (status, json.loads(payload) if payload else None)


def expect(want, what, got):
    status, answer = got
    if status != want:
        sys.exit(f"60-results: {what}: HTTP {status}, not {want}: {answer}")
    say(f"{what}: {status}")
    return answer


up = expect(200, "the clip uploaded", request("POST", "/api/upload", clip.read_bytes(),
                                              {"X-Filename": urllib.parse.quote(clip.name)}))
options = {"instruments": ["bass", "drums"], "device": "cpu"}
if phase == "lyrics":
    options = {"instruments": ["bass"], "device": "cpu", "lyrics": LYRICS}
expect(202, f"a job on the clip ({phase})", request("POST", "/api/jobs", {"upload": up["id"], "options": options}))
with urllib.request.urlopen(base + "/api/jobs/current/events", timeout=1800) as r:   # it closes at the end
    stream = r.read()
(art / f"{phase}-events.txt").write_bytes(stream)
job = request("GET", "/api/jobs/current")[1]
say(f"job {job['job']}: {job['state']} (exit {job['exit']}), events {[e['event'] for e in job['events']]}")
assert job["state"] == "done", job["events"][-1]
result = next(e for e in job["events"] if e["event"] == "result")
assert result["ok"], result["summary"]
res = expect(200, "the results", request("GET", "/api/jobs/current/results"))
(art / f"{phase}-results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
assert res["installable"] and res["preview"].get("overview"), res
for url in [res["preview"]["overview"], *res["preview"]["pages"]]:
    status, headers, body = request("GET", url, raw=True)
    assert status == 200 and headers["Content-Type"] == "image/png" and body[:4] == b"\x89PNG", url
say(f"the preview: the overview and {len(res['preview']['pages'])} pages; flags {res['preview']['flags']}")
for bad in ("pipeline.json", "..%2Fpipeline.json", "notes.chart"):
    assert request("GET", "/api/jobs/current/preview/" + bad)[0] == 404, bad

if phase == "chart":
    zipped = expect(200, "the zip exported", request("POST", "/api/jobs/current/export/zip"))
    status, headers, body = request("GET", zipped["url"], raw=True)
    assert status == 200 and headers["Content-Disposition"].startswith("attachment;"), headers
    names = sorted(zipfile.ZipFile(io.BytesIO(body)).namelist())
    assert names == sorted(f"{res['name']}/{f}" for f in ("notes.chart", "report.json", "song.ini", "song.ogg")), names
    say(f"the zip downloaded: {names}")
    for bad in ("..%2Fui.json", "x.zip", urllib.parse.quote(res["name"])):
        assert request("GET", "/api/exports/" + bad)[0] == 404, bad
    expect(400, "a Songs folder that does not exist", request("POST", "/api/clonehero", {"folder": songs + "-not"}))
    ch = expect(200, "the Songs folder set", request("POST", "/api/clonehero", {"folder": songs}))
    assert ch["folder"] == songs and ch["source"] == "saved", ch
    done = expect(200, "the clip installed", request("POST", "/api/jobs/current/install", {"replace": False}))
    target = Path(songs) / res["name"]
    assert done["installed"] == str(target), done
    files = sorted(p.name for p in target.iterdir())
    assert files == ["notes.chart", "report.json", "song.ini", "song.ogg"], files
    assert json.loads((target / "report.json").read_text(encoding="utf-8"))["gate"]["ok"] is True
    assert "charter = songcharter" in (target / "song.ini").read_text(encoding="utf-8-sig")
    assert (target / "song.ogg").read_bytes()[:4] == b"OggS" and (target / "notes.chart").stat().st_size > 0
    say(f"installed into {target}: {files}")
    again = expect(409, "installed again", request("POST", "/api/jobs/current/install", {"replace": False}))
    assert again["exists"] and again["ours"], again
    replaced = expect(200, "replaced", request("POST", "/api/jobs/current/install", {"replace": True}))
    assert Path(replaced["replaced"]).parent.parent == home / "replaced", replaced
    assert sorted(p.name for p in Path(replaced["replaced"]).iterdir()) == files
    assert [p.name for p in Path(songs).iterdir()] == [res["name"]]   # no .tmp or .old left
    expect(200, "open the exports folder (no Windows here)", request("POST", "/api/open", {"what": "exports"}))
    expect(400, "open another folder", request("POST", "/api/open", {"what": "/etc"}))
else:
    ly = res["lyrics"]
    tried = "the aligner's weights could not be downloaded from https://download.pytorch.org/"   # the dead proxy's
    assert ly and ly["given"] and not ly["added"] and (ly["why"] or "").startswith(tried), ly
    warned = [e["text"] for e in job["events"] if e["event"] == "warning" and e["text"].startswith("lyrics:")]
    assert warned, job["events"]
    say(f"the lyrics: not added, as the first-use download was tried and the dead proxy refused it ({ly['why']}); "
        f"warned: {warned}")
    assert job["options"]["lyrics"] is True, job["options"]   # whether given: never the text
    seen = [stream, json.dumps(job).encode(), json.dumps(res).encode()]
    for root in (home, Path(result["work"])):
        seen += [p.read_bytes() for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".json", ".log",
                                                                                                    ".txt", ".ini")]
    log = next(p for p in sorted((home / "logs").glob("job-*.log")) if "--lyrics=/dev/fd/" in p.read_text("utf-8"))
    say(f"the job's command line names only the memory file: {log.name}")
    for data in seen:
        assert not any(w in data for w in WORDS), data[:200]
    say(f"no pasted word in {len(seen)} logs, records and answers")
status, headers, body = request("GET", "/api/diagnostics", raw=True)
assert status == 200 and headers["Content-Disposition"].startswith('attachment; filename="songcharter-diagnostics-')
(art / f"{phase}-diagnostics.zip").write_bytes(body)
with zipfile.ZipFile(io.BytesIO(body)) as z:
    names = z.namelist()
    assert any(n.endswith("/pipeline.json") for n in names) and "MANIFEST.txt" in names, names
    for n in names:
        assert not any(w in z.read(n) for w in WORDS), n
say(f"the diagnostics bundle: {len(names)} files")
PY
}

start
drive chart
stop
# the launcher's variables for a finished install, one NAME=VALUE a line (PATH aside: the runtime names no Node here)
mapfile -t installed < <("$CI_PY" - "$home" <<'PY'
import sys
from songcharter import launch
env = launch.environment({"home": sys.argv[1], "models_complete": True}, base={})
print("\n".join(f"{k}={v}" for k, v in sorted(env.items()) if k != "PATH"))
PY
)
echo "60-results: the launcher's variables: ${installed[*]}"
case " ${installed[*]} " in
  *" HF_HUB_OFFLINE=1 "*) ;;
  *) echo "60-results: the launcher's variables for a finished install have no HF_HUB_OFFLINE=1" >&2; exit 1 ;;
esac
dead=http://127.0.0.1:9   # the discard port: nothing listens there
start "${installed[@]}" https_proxy=$dead HTTPS_PROXY=$dead no_proxy= NO_PROXY=
drive lyrics
stop
trap - EXIT
cp "$home"/logs/*.log "$art/" 2>/dev/null || true

SONGCHARTER_HOME="$home" "$CI_PY" -m songcharter.cli diagnostics --out "$CI_TMP/d.zip"
mkdir -p "$CI_TMP/d"
"$CI_PY" -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$CI_TMP/d.zip" "$CI_TMP/d"
for bundle in "$CI_TMP/d.zip" "$CI_TMP/d" "$art/chart-diagnostics.zip" "$art/lyrics-diagnostics.zip"; do
  "$CI_PY" packaging/ci/check_no_audio.py "$bundle"
done
cp "$CI_TMP/d.zip" "$art/cli-diagnostics.zip"
# the checker does see audio: the export holds song.ogg
if "$CI_PY" packaging/ci/check_no_audio.py "$home/exports" >/dev/null; then
  echo "60-results: check_no_audio.py passed the export, which holds song.ogg" >&2
  exit 1
fi
echo "60-results: ok"
