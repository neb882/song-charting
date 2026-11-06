#!/usr/bin/env bash
# 40-ui.sh (M4-04): the local UI on ubuntu-latest.
#   1. the UI's tests (tests/test_proc.py, test_ui_server.py, test_ui_jobs.py: stand-in charts, no model);
#   2. the guards against a real `songcharter ui --no-browser` on port 8799, with curl: a foreign Host gives 403, a POST
#      with a foreign Origin 403, a .txt upload 415; then the clip is uploaded and a job started on it (202), and
#      followed over SSE to its end (this job has no autochart engine, so its chart stops at the component check with
#      an error, exit 2: the job reads `failed`); cancel answers 409 then, and no `songcharter.cli chart` is left;
#   3. SIGTERM stops the server within 5 s.
# The real cancel at the first `take` is M4-05's, once the install exists.
# Run by packaging/ci/run-hooks.sh with bash -euo pipefail; uses CI_PY, CI_TMP, CI_ART and CI_CLIP (M4-05a's contract).
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

"$CI_PY" -m pytest -q -p no:cacheprovider --basetemp="$CI_TMP/pt-ui" tests/test_proc.py tests/test_ui_server.py \
  tests/test_ui_jobs.py

port=8799
base="http://127.0.0.1:$port"
home="$CI_TMP/ui-home"
rm -rf "$home"
mkdir -p "$home" "$CI_ART"
log="$CI_ART/40-ui-server.txt"
# the update check the page starts goes to a closed local port: CI asks no real API (M5-07; 75-update.sh tests it)
SONGCHARTER_HOME="$home" SONGCHARTER_CACHE="$CI_TMP/ui-cache" SONGCHARTER_RELEASES_URL=http://127.0.0.1:9/releases.json \
  "$CI_PY" -m songcharter.cli ui --no-browser \
  --port "$port" >"$log" 2>&1 &
server=$!
stop() {   # SIGTERM, then the server must be gone within 5 s
  kill -TERM "$server" 2>/dev/null || return 0
  for _ in $(seq 50); do
    kill -0 "$server" 2>/dev/null || { wait "$server" || true; return 0; }
    sleep 0.1
  done
  echo "40-ui: the server did not stop within 5 s of SIGTERM" >&2
  kill -KILL "$server" 2>/dev/null || true
  return 1
}
trap 'stop || true; cp "$home"/logs/*.log "$CI_ART/" 2>/dev/null || true' EXIT
for _ in $(seq 600); do
  curl -sf "$base/api/hello" >/dev/null && break
  kill -0 "$server" 2>/dev/null || { cat "$log"; echo "40-ui: the server exited" >&2; exit 1; }
  sleep 0.1
done
curl -sf "$base/api/hello"; echo

expect() {   # CODE WHAT CURL-ARGS...: curl's status must be CODE
  local want=$1 what=$2 got
  shift 2
  got=$(curl -s -o "$CI_TMP/ui-body" -w '%{http_code}' "$@")
  if [ "$got" != "$want" ]; then
    echo "40-ui: $what: HTTP $got, not $want: $(cat "$CI_TMP/ui-body")" >&2
    exit 1
  fi
  echo "40-ui: $what: $got"
}
ours=(-H "X-Songcharter: 1" -H "Origin: $base")
expect 403 "Host evil.example" -H "Host: evil.example" "$base/api/hello"
expect 403 "a POST without X-Songcharter" -X POST -H "Origin: $base" -H "X-Filename: clip.wav" \
  --data-binary @"$CI_CLIP" "$base/api/upload"
expect 403 "Origin evil.example" -X POST -H "X-Songcharter: 1" -H "Origin: http://evil.example" \
  -H "X-Filename: clip.wav" --data-binary @"$CI_CLIP" "$base/api/upload"
printf 'not a song\n' >"$CI_TMP/notes.txt"
expect 415 "a .txt upload" -X POST "${ours[@]}" -H "X-Filename: notes.txt" --data-binary @"$CI_TMP/notes.txt" \
  "$base/api/upload"
grep -q "Content-Security-Policy: default-src 'self'" <(curl -s -D - -o /dev/null "$base/") ||
  { echo "40-ui: no CSP on the page" >&2; exit 1; }

expect 200 "the clip uploaded" -X POST "${ours[@]}" -H "X-Filename: clip%20%C3%A9.wav" --data-binary @"$CI_CLIP" \
  "$base/api/upload"
id=$("$CI_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$CI_TMP/ui-body")
expect 202 "a job started on the clip" -X POST "${ours[@]}" -H "Content-Type: application/json" \
  --data "{\"upload\": \"$id\", \"options\": {}}" "$base/api/jobs"
timeout 600 curl -sN "$base/api/jobs/current/events" >"$CI_ART/40-ui-events.txt"   # it closes at the end
for _ in $(seq 100); do   # the stream closes once the job has ended; this only makes sure
  curl -s "$base/api/jobs/current" >"$CI_ART/40-ui-job.json"
  grep -q '"state": "running"' "$CI_ART/40-ui-job.json" || break
  sleep 0.1
done
"$CI_PY" - "$CI_ART/40-ui-job.json" <<'PY'
import json, sys
job = json.load(open(sys.argv[1], encoding="utf-8"))
kinds = [e["event"] for e in job["events"]]
last = job["events"][-1]
print(f"40-ui: job {job['job']}: {job['state']} (exit {job['exit']}), events {kinds}")
print(f"40-ui: its end: {json.dumps(last)[:400]}")
assert job["state"] in ("done", "failed") and last["event"] in ("result", "error"), job["state"]
assert job["exit"] in (0, 1, 2), job["exit"]
PY
expect 409 "cancel with no job running" -X POST "${ours[@]}" "$base/api/jobs/current/cancel"
if pgrep -af "songcharter.cli chart"; then
  echo "40-ui: a chart process is left" >&2
  exit 1
fi
trap - EXIT
stop
cp "$home"/logs/*.log "$CI_ART/" 2>/dev/null || true
grep -q "SIGTERM: stopping" "$log" || { cat "$log"; echo "40-ui: no clean stop in the log" >&2; exit 1; }
echo "40-ui: ok"
