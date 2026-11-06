#!/usr/bin/env bash
# 75-update.sh (M5-07): the update path as the friend takes it, and the page's update notice, in 70-release.sh's
# manner (ubuntu:26.04 with the WSL image's tools, a local server at the release paths, friend as the user).
#   1. v0.1.0's four files built from its tag (`git fetch --depth=1 origin tag v0.1.0`, a detached worktree and its
#      own packaging/release/build.sh 0.1.0: the published assets were built the same way from the same tree), and
#      the new version's from HEAD, as <HEAD's __version__>-ci-<short sha> (70-release's naming): both served at
#      their release paths (/neb882/song-charting/releases/download/v<version>/), each line exactly as its GUIDE.md
#      has it but for https://github.com/ becoming the server, and $SONGCHARTER_RELEASE_URL naming it for the tarball;
#      the notice's line for the new version (updates.install_line) is GUIDE.md's own;
#   2. 0.1.0 installed with its line (Enter at the licence prompt), and CI's clip charted with `songcharter chart`
#      (its work folder noted);
#   3. the new line pasted over it: "songcharter <new>: in .../app/<new>", app/0.1.0 gone, and only install.sh and
#      the tarball fetched from the server for it (SHA256SUMS too may be), each once; nothing else downloaded (no line
#      of runtime.py's fetch, uv's downloads, install.sh's own but the app's tarball, or uv's Python install: the
#      runtime is kept); `songcharter doctor` exits 0 with "doctor: OK" and HEAD's __version__ (the same as 0.1.0's
#      until the release changes it, so the new code is also proven by runtime.json's app and by the install's Python
#      importing songcharter.updates, which 0.1.0 has not); the clip charted again into the same work folder, with
#      separate, drums, bass, sections and guitar "(cached)", and check_gate.py passes on it;
#   4. the notice: `songcharter` (the page, as the guide starts it) with $SONGCHARTER_RELEASES_URL naming a JSON file
#      on the server; /api/status before the page has no update and makes no request, then the page, then (once the
#      check's line is in the log) /api/status again: with a release v9.9.9 whose assets are on the server, with a
#      SHA256SUMS there, update.version 9.9.9 and update.line exactly the expected line, from one request for the
#      JSON and one for the SHA256SUMS; started again with a JSON of v0.1.0 only, the answer kept for a day still
#      says 9.9.9, with no request; the kept answer deleted, update null; with the URL unreachable, null, and the page
#      still answering;
#   5. `songcharter uninstall` answered with Enter (No), then the new line again: the reinstall after an update works,
#      with nothing downloaded but install.sh and the tarball.
# The logs, the server's access log and the JSON files go to $CI_ART/75-update (no audio: the clip, the charts and
# the work folders stay in the container).
# Run by packaging/ci/run-hooks.sh with bash -euo pipefail; uses CI_PY, CI_TMP, CI_ART and CI_CLIP, git, curl and Docker.
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
art="$CI_ART/75-update"
work="$CI_TMP/update"
mkdir -p "$art"
fail() { echo "75-update: $*"; exit 1; }

old=0.1.0
head_version=$(git show HEAD:songcharter/__init__.py | sed -n 's/^__version__ = "\(.*\)"$/\1/p')
[ -n "$head_version" ] || fail "no __version__ in HEAD's songcharter/__init__.py"
new="$head_version-ci-$(git rev-parse --short HEAD)"
base="neb882/song-charting/releases/download"
old_tree="$work/v$old"
name="sc-update-$$"
server=""

cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  if [ -n "$server" ]; then kill "$server" 2>/dev/null || true; fi
  git worktree remove --force "$old_tree" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# --- 1. the two versions' files, served
rm -rf "$work"
mkdir -p "$work"
git worktree prune
git rev-parse -q --verify "refs/tags/v$old^{commit}" >/dev/null || git fetch --depth=1 --no-tags origin tag "v$old"
git worktree add --detach "$old_tree" "v$old" >/dev/null
echo "75-update: v$old is $(git -C "$old_tree" rev-parse HEAD)"
PYTHON="$CI_PY" bash "$old_tree/packaging/release/build.sh" "$old" "$work/dist-$old"
PYTHON="$CI_PY" bash packaging/release/build.sh "$new" "$work/dist-new"
cp "$work/dist-$old/SHA256SUMS" "$art/SHA256SUMS-$old"
# reported, never failed on: whether the rebuild is byte for byte the published release (git archive's gzip may differ
# between git versions; the files are self-consistent either way)
if published=$(curl -fsSL --max-time 30 "https://github.com/$base/v$old/SHA256SUMS" 2>/dev/null) &&
  [ "$published" = "$(cat "$work/dist-$old/SHA256SUMS")" ]; then
  echo "75-update: the files rebuilt from v$old are the published release's (the same SHA256SUMS)"
else
  echo "75-update: the files rebuilt from v$old differ from the published release's, or it could not be read (reported only)"
fi
cp "$work/dist-new/SHA256SUMS" "$art/SHA256SUMS-new"

guide_line() {   # GUIDE.md: its one install line
  local n
  n=$(grep -cE 'curl|wget' "$1" || true)
  [ "$n" -eq 1 ] || fail "$1 has $n lines with curl or wget, not 1"
  grep -E 'curl|wget' "$1"
}
old_line=$(guide_line "$work/dist-$old/GUIDE.md")
new_line=$(guide_line "$work/dist-new/GUIDE.md")
new_sha=$(sha256sum "$work/dist-new/install.sh" | cut -d' ' -f1)
notice_line=$("$CI_PY" -c 'import sys; from songcharter import updates; print(updates.install_line(*sys.argv[1:]))' \
  "$new" "$new_sha")
[ "$notice_line" = "$new_line" ] || fail "the notice's line is not GUIDE.md's:
  notice: $notice_line
  guide:  $new_line"
echo "75-update: the notice's line for $new is GUIDE.md's"

root="$work/server"
for v in "$old" new; do
  version=$([ "$v" = new ] && echo "$new" || echo "$v")
  mkdir -p "$root/$base/v$version"
  cp "$work/dist-$v/install.sh" "$work/dist-$v/songcharter-$version.tar.gz" "$work/dist-$v/SHA256SUMS" \
    "$root/$base/v$version/"
done
port=$("$CI_PY" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
closed=$("$CI_PY" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
server_log="$art/server.log"
"$CI_PY" -u -m http.server --bind 127.0.0.1 --directory "$root" "$port" >"$server_log" 2>&1 &
server=$!
for _ in $(seq 1 100); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$port/$base/v$new/SHA256SUMS" 2>/dev/null; then break; fi
  kill -0 "$server" 2>/dev/null || { cat "$server_log"; fail "the local server did not start"; }
  sleep 0.1
done
url="http://127.0.0.1:$port/"
local_old=${old_line//https:\/\/github.com\//$url}
local_new=${new_line//https:\/\/github.com\//$url}
one_change() {   # GUIDE-LINE LOCAL-LINE: the local line is the guide's with https://github.com/ as the server
  [ "${2/$url/https://github.com/}" = "$1" ] && [ "$2" != "$1" ] ||
    fail "a line's one change is not https://github.com/ to $url: $2"
}
one_change "$old_line" "$local_old"
one_change "$new_line" "$local_new"
echo "75-update: serving $root at $url"

# the notice's releases: v9.9.9 (a pre-release, its assets on the server, its SHA256SUMS the new build's), and v0.1.0
mkdir -p "$root/$base/v9.9.9"
cp "$work/dist-new/SHA256SUMS" "$root/$base/v9.9.9/SHA256SUMS"
"$CI_PY" - "$root" "$url$base" <<'PY'
import json, sys
from pathlib import Path
root, download = Path(sys.argv[1]), sys.argv[2]


def release(version, prerelease):
    return {"tag_name": f"v{version}", "name": f"songcharter {version} (WSL)", "draft": False,
            "prerelease": prerelease, "html_url": f"https://github.com/neb882/song-charting/releases/tag/v{version}",
            "assets": [{"name": n, "browser_download_url": f"{download}/v{version}/{n}"}
                       for n in ("install.sh", "SHA256SUMS")]}


(root / "releases-999.json").write_text(json.dumps([release("9.9.9", True), release("0.1.0", True)], indent=1))
(root / "releases-010.json").write_text(json.dumps([release("0.1.0", True)], indent=1))
PY
cp "$root"/releases-*.json "$art/"
expect_999=$("$CI_PY" -c 'import json, sys; from songcharter import updates
print(json.dumps({"version": "9.9.9", "line": updates.install_line("9.9.9", sys.argv[1]),
                  "url": "https://github.com/neb882/song-charting/releases/tag/v9.9.9"}))' "$new_sha")
echo "75-update: the notice for v9.9.9 should be $expect_999"

docker run -d --init --name "$name" --network host -v "$PWD/packaging/ci:/ci:ro" ubuntu:26.04 sleep infinity >/dev/null
docker exec -e DEBIAN_FRONTEND=noninteractive "$name" bash -euo pipefail -c \
  'apt-get update -qq && apt-get install -y -qq curl ca-certificates git xz-utils >/dev/null && useradd -m friend'
docker exec -i -u friend -e HOME=/home/friend "$name" sh -c 'mkdir -p ~/clips && cat >~/clips/clip.wav' <"$CI_CLIP"

# helpers in friend's scripts
PRELUDE='
home=$HOME/.local/share/songcharter
py=$home/runtime/env/bin/python
die() { echo "75-update: $*"; exit 1; }
run() {   # LOG COMMAND...: its output into LOG; when it fails, the last lines and its exit status
  local log=$1 code=0
  shift
  "$@" >"$log" 2>&1 || code=$?
  if [ $code -ne 0 ]; then tail -n 40 "$log"; die "$* exited $code"; fi
}
line() {   # LOG URL LINE: the guide line LINE, with $SONGCHARTER_RELEASE_URL=URL, answered with Enter
  local log=$1 code=0
  printf "\n" | SONGCHARTER_RELEASE_URL=$2 bash -c "$3" >"$log" 2>&1 || code=$?
  if [ $code -ne 0 ]; then tail -n 40 "$log"; die "the line exited $code"; fi
  tail -n 6 "$log"
  grep -qx "install.sh: OK" "$log" || die "no \"install.sh: OK\" in $log"
}
no_download() {   # LOG: the install downloaded nothing but the app'"'"'s tarball, from the server (e2e.sh'"'"'s
  # no_download, and uv'"'"'s Python install)
  local found=0 app="downloading $NEW_URL/songcharter-$NEW.tar.gz"
  if grep -nE "^fetch " "$1"; then echo "75-update: runtime.py fetched (above)"; found=1; fi
  if grep -nE "Download(ing|ed) " "$1"; then echo "75-update: uv downloaded (above)"; found=1; fi
  if grep -E "^downloading " "$1" | grep -vxF "$app"; then
    echo "75-update: install.sh downloaded more than the app (above)"; found=1
  fi
  grep -qxF "$app" "$1" || { echo "75-update: no \"$app\" line"; found=1; }
  if grep -nE "^Installed Python" "$1"; then echo "75-update: uv installed Python (above)"; found=1; fi
  [ $found -eq 0 ] || exit 1
  echo "nothing downloaded but the app (install.sh'"'"'s line: $app)"
}
installed_new() {   # LOG: the new version is in app/<new>, alone, and its install ended well
  grep -qx "songcharter $NEW: in $home/app/$NEW" "$1" || die "no \"songcharter $NEW: in $home/app/$NEW\" in $1"
  grep -q "^songcharter $NEW is installed (lane cpu" "$1" || die "no \"songcharter $NEW is installed\" in $1"
  [ "$(ls "$home/app")" = "$NEW" ] || { ls -la "$home/app"; die "app/ does not hold $NEW alone"; }
  "$py" -P -c "import json, sys; r = json.load(open(sys.argv[1])); sys.exit(0 if r[\"app\"] == sys.argv[2] else \"runtime.json app: \" + r[\"app\"])" \
    "$home/runtime/runtime.json" "$home/app/$NEW"
}
said() { cat "$home"/logs/ui-*.log 2>/dev/null | grep -c "update check" || true; }
page() {   # TAG RELEASES-URL: `songcharter` (the page) with $SONGCHARTER_RELEASES_URL; /api/status before the page,
  # the page, then /api/status once the check has logged its line; /tmp/status-TAG{-before,}.json; then stopped
  local tag=$1 log=/tmp/page-$1.log before pid address="" n=0
  before=$(said)
  SONGCHARTER_RELEASES_URL=$2 songcharter >"$log" 2>&1 &
  pid=$!
  for _ in $(seq 1 600); do
    address=$(sed -n "s|^songcharter is at \(http://[^ ]*\) .*|\1|p" "$log" | head -n 1)
    [ -z "$address" ] || break
    kill -0 "$pid" 2>/dev/null || { cat "$log"; die "songcharter ended"; }
    sleep 0.1
  done
  [ -n "$address" ] || { cat "$log"; die "songcharter gave no address"; }
  curl -fsS "${address}api/status" -o "/tmp/status-$tag-before.json"
  sleep 1
  [ "$(said)" -eq "$before" ] || die "the update check ran before the page was served"
  curl -fsS "$address" | grep -q "<title>songcharter</title>"
  for _ in $(seq 1 300); do
    n=$(said)
    [ "$n" -le "$before" ] || break
    sleep 0.1
  done
  [ "$n" -gt "$before" ] || die "no update check line in the log within 30 s of the page"
  cat "$home"/logs/ui-*.log | grep "update check" | tail -n 1
  curl -fsS "${address}api/status" -o "/tmp/status-$tag.json"
  curl -fsS -o /dev/null "${address}api/hello" || die "the page stopped answering"
  kill -TERM "$pid"
  wait "$pid"
}
update_is() {   # TAG JSON: /api/status had no update before the page, and this one after it
  "$py" -P - "/tmp/status-$1-before.json" "/tmp/status-$1.json" "$2" <<'"'"'PY'"'"'
import json, sys
before, after = (json.load(open(p, encoding="utf-8"))["update"] for p in sys.argv[1:3])
want = json.loads(sys.argv[3])
if before is not None:
    sys.exit(f"75-update: /api/status had an update before the page: {before!r}")
if after != want:
    sys.exit(f"75-update: /api/status update is {after!r}, not {want!r}")
print(f"update: {after!r}")
PY
}
'

friend() {   # NAME SCRIPT: SCRIPT as friend, in a login shell (a new Ubuntu window's PATH), timed
  local start=$SECONDS
  echo "-- $1"
  docker exec -u friend -e HOME=/home/friend -w /home/friend -e OLD="$old" -e NEW="$new" -e HEAD_VERSION="$head_version" \
    -e OLD_LINE="$local_old" -e NEW_LINE="$local_new" -e OLD_URL="$url$base/v$old" -e NEW_URL="$url$base/v$new" \
    -e SERVER="$url" -e CLOSED="http://127.0.0.1:$closed/releases.json" -e EXPECT_999="$expect_999" "$name" \
    bash -lc "set -euo pipefail
$PRELUDE
$2"
  echo "-- $1: ok in $((SECONDS - start)) s"
}
keep() {   # FILE...: copied from the container into $art
  for f in "$@"; do docker cp "$name:$f" "$art/" >/dev/null 2>&1 || true; done
}
mark() { wc -l <"$server_log"; }
since() { tail -n "+$(($1 + 1))" "$server_log"; }   # MARK: the access log's lines after it
asked() {   # MARK PATH: how many times PATH was served since MARK
  since "$1" | grep -cF "\"GET /$2 HTTP/1." || true
}
only() {   # MARK PATH...: since MARK, the server answered 200 for these paths and nothing else
  local line ok p
  while IFS= read -r line; do
    ok=0
    for p in "${@:2}"; do
      case $line in *"\"GET /$p HTTP/1."[01]"\" 200 "*) ok=1 ;; esac
    done
    [ $ok -eq 1 ] || fail "the server was asked for something else: $line"
  done < <(since "$1")
}

# --- 2. 0.1.0, as the friend has it
friend "v$old, with its guide's line" '
line /tmp/install-old.log "$OLD_URL" "$OLD_LINE"
grep -q "^songcharter $OLD is installed (lane cpu" /tmp/install-old.log || die "0.1.0 is not installed"'
keep /tmp/install-old.log
friend "the clip, charted by $old" '
mkdir -p ~/Songs
run /tmp/chart-old.log songcharter chart ~/clips/clip.wav --out ~/Songs/Clip
tail -n 3 /tmp/chart-old.log
sed -n "s/^work folder: \(.*\) (.*$/\1/p" /tmp/chart-old.log | head -n 1 >/tmp/work-old.txt
[ -d "$(cat /tmp/work-old.txt)" ] || die "no work folder in /tmp/chart-old.log"
echo "work folder: $(cat /tmp/work-old.txt)"'
keep /tmp/chart-old.log

# --- 3. the new line over it
before=$(mark)
friend "the new version's line, pasted over $old" '
line /tmp/update.log "$NEW_URL" "$NEW_LINE"
installed_new /tmp/update.log
grep -qx "uv 0.13.5: already here" /tmp/update.log || die "uv was not kept"
[ ! -e "$home/app/$OLD" ] || die "app/$OLD is still there"
no_download /tmp/update.log'
keep /tmp/update.log
only "$before" "$base/v$new/install.sh" "$base/v$new/songcharter-$new.tar.gz" "$base/v$new/SHA256SUMS"
[ "$(asked "$before" "$base/v$new/install.sh")" -eq 1 ] && [ "$(asked "$before" "$base/v$new/songcharter-$new.tar.gz")" -eq 1 ] ||
  fail "the update did not fetch install.sh and the tarball once each"
echo "75-update: the update fetched install.sh and the tarball, once each, and nothing else from the server"

friend "songcharter doctor, after the update" '
run /tmp/doctor.log songcharter doctor
cat /tmp/doctor.log
grep -q "^songcharter $HEAD_VERSION, Python 3" /tmp/doctor.log || die "doctor does not report $HEAD_VERSION"
grep -qx "doctor: OK" /tmp/doctor.log || die "doctor found a problem"
"$py" -P -c "import songcharter.updates as u; print(\"the new code:\", u.__file__)"'
keep /tmp/doctor.log

friend "the clip again, by the new version: the work cache reused" '
run /tmp/chart-new.log songcharter chart ~/clips/clip.wav --out ~/Songs/"Clip after the update"
grep -E "^\[[0-9]+/[0-9]+\] " /tmp/chart-new.log
work=$(sed -n "s/^work folder: \(.*\) (.*$/\1/p" /tmp/chart-new.log | head -n 1)
[ "$work" = "$(cat /tmp/work-old.txt)" ] || die "the work folder is $work, not $(cat /tmp/work-old.txt)"
for stage in separate drums bass sections guitar; do
  grep -qE "^\[[0-9]+/[0-9]+\] $stage: .* \(cached\), [0-9.]+ s$" /tmp/chart-new.log || die "$stage was not cached"
done
"$py" /ci/check_gate.py ~/Songs/"Clip after the update"'
keep /tmp/chart-new.log

# --- 4. the notice
before=$(mark)
friend "the page, with a release v9.9.9 out" '
page 999 "${SERVER}releases-999.json"
update_is 999 "$EXPECT_999"'
only "$before" releases-999.json "$base/v9.9.9/SHA256SUMS"
[ "$(asked "$before" releases-999.json)" -eq 1 ] && [ "$(asked "$before" "$base/v9.9.9/SHA256SUMS")" -eq 1 ] ||
  fail "the check did not ask for the JSON and the SHA256SUMS once each"
before=$(mark)
friend "the page again, with only v$old listed: the answer kept for a day" '
page kept "${SERVER}releases-010.json"
update_is kept "$EXPECT_999"
grep -q "\"latest\": \"9.9.9\"" "$home/state/update.json"'
[ -z "$(since "$before")" ] || fail "the check asked the server again within a day: $(since "$before")"
before=$(mark)
friend "the page, with only v$old listed (the kept answer deleted)" '
rm "$home/state/update.json"
page 010 "${SERVER}releases-010.json"
update_is 010 null'
only "$before" releases-010.json
friend "the page, with the releases unreachable" '
rm "$home/state/update.json"
page unreachable "$CLOSED"
update_is unreachable null
"$py" -P -c "import json, sys; r = json.load(open(sys.argv[1])); print(\"stamp:\", r); sys.exit(0 if \"error\" in r else 1)" \
  "$home/state/update.json"'
keep /home/friend/.local/share/songcharter/logs /home/friend/.local/share/songcharter/state/update.json \
  /tmp/page-999.log /tmp/page-kept.log /tmp/page-010.log /tmp/page-unreachable.log
for tag in 999 kept 010 unreachable; do keep "/tmp/status-$tag.json"; done

# --- 5. uninstall (No), then the new line again
before=$(mark)
friend "songcharter uninstall (No), then the new line again" '
printf "\n" | songcharter uninstall >/tmp/uninstall.log 2>&1 || { cat /tmp/uninstall.log; die "uninstall failed"; }
tail -n 3 /tmp/uninstall.log
[ ! -e ~/.local/bin/songcharter ] && [ ! -e "$home/app" ] && [ -d "$home/runtime/env" ] || die "uninstall (No) left the wrong things"
line /tmp/reinstall.log "$NEW_URL" "$NEW_LINE"
installed_new /tmp/reinstall.log
no_download /tmp/reinstall.log
run /tmp/doctor-quick.log songcharter doctor --quick
tail -n 1 /tmp/doctor-quick.log'
keep /tmp/uninstall.log /tmp/reinstall.log
only "$before" "$base/v$new/install.sh" "$base/v$new/songcharter-$new.tar.gz"

"$CI_PY" packaging/ci/check_no_audio.py "$art"
echo "75-update: ok ($old, then $new over it, and the notice)"
