#!/usr/bin/env bash
# 70-release.sh (M4-07): the release's files, and the guide's own line run as the friend pastes it.
#   1. packaging/release/build.sh's four files (install.sh, the tarball, SHA256SUMS, GUIDE.md) and nothing else;
#   2. GUIDE.md: no {{ or }} left, and its one install line is exactly the expected one, with the release URL and
#      install.sh's SHA-256, the same as SHA256SUMS's line for it;
#   3. the tarball: NOTICE.txt (packaging/NOTICE.txt as it is) and LICENSE at its root, and check_no_audio.py passes
#      on it;
#   4. a local HTTP server serving the three assets at the release's path (/neb882/song-charting/releases/download/
#      v<version>/), and `docker run --network host ubuntu:26.04` with `apt-get install -y curl ca-certificates
#      xz-utils` (the WSL image's tools) and `useradd -m friend`. As friend, the guide's line exactly as GUIDE.md has
#      it, but for https://github.com/ becoming the local server's address (the one change, checked), and with
#      $SONGCHARTER_RELEASE_URL, install.sh's override for this check, naming the same server for the tarball:
#      - a changed install.sh served: `sha256sum -c` fails, and the installer never runs;
#      - answering No at "Continue? [Y/n]": "install.sh: OK", the line naming NOTICE.txt, exit 1, no tarball fetched;
#      - pressing Enter: the whole install, exit 0, with install.sh and the tarball fetched from the server, and the
#        NOTICE.txt that the prompt named in place and identical to packaging/NOTICE.txt;
#   5. the guide's other commands in Ubuntu, as written, in a login shell (a new Ubuntu window's PATH): `songcharter`
#      (its page answers), `songcharter diagnostics --out diagnostics.zip` (check_no_audio.py passes on the zip) and
#      `songcharter uninstall` answered with Enter (No: the launcher goes, the downloads stay).
# The logs, GUIDE.md and SHA256SUMS go to $CI_ART/70-release (no audio).
# Run by packaging/ci/run-hooks.sh with bash -euo pipefail; uses CI_PY, CI_TMP and CI_ART, git, curl and Docker.
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
art="$CI_ART/70-release"
dist="$CI_TMP/release"
mkdir -p "$art"
version="0.1.0-ci-$(git rev-parse --short HEAD)"
tarball="songcharter-$version.tar.gz"
release_path="neb882/song-charting/releases/download/v$version"
fail() { echo "70-release: $*"; exit 1; }

# --- 1. the four files
rm -rf "$dist"
PYTHON="$CI_PY" bash packaging/release/build.sh "$version" "$dist"
files=$(cd "$dist" && ls -A | LC_ALL=C sort | tr '\n' ' ')
[ "$files" = "GUIDE.md SHA256SUMS install.sh $tarball " ] || fail "build.sh wrote: $files"
cp "$dist/GUIDE.md" "$dist/SHA256SUMS" "$art/"

# --- 2. the guide and its line
if grep -n '{{\|}}' "$dist/GUIDE.md"; then fail "GUIDE.md still has a value to fill in (above)"; fi
install_sha=$(sha256sum "$dist/install.sh" | cut -d' ' -f1)
grep -qx "$install_sha  install.sh" "$dist/SHA256SUMS" || fail "SHA256SUMS has no line $install_sha  install.sh"
lines=$(grep -c 'sha256sum -c' "$dist/GUIDE.md" || true)
[ "$lines" -eq 1 ] || fail "GUIDE.md has $lines lines with sha256sum -c, not 1"
line=$(grep 'sha256sum -c' "$dist/GUIDE.md")
want="curl -fsSLO https://github.com/$release_path/install.sh && echo \"$install_sha  install.sh\" | sha256sum -c - && bash install.sh"
if [ "$line" != "$want" ]; then
  printf 'GUIDE.md: %s\nexpected: %s\n' "$line" "$want"
  fail "the guide's install line is not the expected one"
fi
echo "70-release: GUIDE.md's line has install.sh's SHA-256 $install_sha"

# --- 3. the tarball
members=$(tar -tzf "$dist/$tarball")
for f in NOTICE.txt LICENSE; do
  grep -qx "songcharter-$version/$f" <<<"$members" || fail "the tarball has no $f at its root"
done
tar -xzOf "$dist/$tarball" "songcharter-$version/NOTICE.txt" | cmp -s - packaging/NOTICE.txt ||
  fail "the tarball's NOTICE.txt is not packaging/NOTICE.txt"
"$CI_PY" packaging/ci/check_no_audio.py "$dist/$tarball"

# --- 4. the guide's line against a local server
root="$CI_TMP/release-server"
rm -rf "$root"
mkdir -p "$root/$release_path"
cp "$dist/install.sh" "$dist/$tarball" "$dist/SHA256SUMS" "$root/$release_path/"
port=$("$CI_PY" -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
server_log="$art/server.log"
"$CI_PY" -u -m http.server --bind 127.0.0.1 --directory "$root" "$port" >"$server_log" 2>&1 &
server=$!
name="sc-release-$$"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true; kill "$server" 2>/dev/null || true' EXIT
for _ in $(seq 1 100); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$port/$release_path/SHA256SUMS" 2>/dev/null; then break; fi
  kill -0 "$server" 2>/dev/null || { cat "$server_log"; fail "the local server did not start"; }
  sleep 0.1
done
url="http://127.0.0.1:$port/"
local_line=${line//https:\/\/github.com\//$url}
[ "${local_line/$url/https://github.com/}" = "$line" ] && [ "$local_line" != "$line" ] ||
  fail "the line's one change is not https://github.com/ to $url"
echo "70-release: serving $root at $url"

docker run -d --name "$name" --network host -v "$PWD/packaging/ci:/ci:ro" ubuntu:26.04 sleep infinity >/dev/null
docker exec -e DEBIAN_FRONTEND=noninteractive "$name" bash -euo pipefail -c \
  'apt-get update -qq && apt-get install -y -qq curl ca-certificates xz-utils >/dev/null && useradd -m friend'

friend() {   # NAME SCRIPT: SCRIPT as friend, in a login shell (a new Ubuntu window's PATH), timed
  local start=$SECONDS
  echo "-- $1"
  docker exec -u friend -e HOME=/home/friend -w /home/friend -e SONGCHARTER_RELEASE_URL="$url$release_path" \
    -e LINE="$local_line" -e VERSION="$version" "$name" bash -lc "set -euo pipefail
$2"
  echo "-- $1: ok in $((SECONDS - start)) s"
}
keep() {   # FILE...: copied from the container into $art
  for f in "$@"; do docker cp "$name:$f" "$art/" >/dev/null 2>&1 || true; done
}
served() { grep -c "\"GET /$release_path/$1 HTTP/1.[01]\" 200" "$server_log" || true; }

cp "$dist/install.sh" "$CI_TMP/install.sh.changed"
echo 'touch /tmp/changed-install-ran' >>"$CI_TMP/install.sh.changed"
cp "$CI_TMP/install.sh.changed" "$root/$release_path/install.sh"
friend "the line, with a changed install.sh served" '
code=0
bash -c "$LINE" </dev/null >/tmp/line-changed.log 2>&1 || code=$?
cat /tmp/line-changed.log
[ "$code" -ne 0 ] || { echo "70-release: the line passed a changed install.sh"; exit 1; }
grep -qx "install.sh: FAILED" /tmp/line-changed.log
if [ -e /tmp/changed-install-ran ] || grep -q "the install, into" /tmp/line-changed.log; then
  echo "70-release: the changed install.sh ran"; exit 1
fi
echo "sha256sum -c stopped it: exit $code"'
keep /tmp/line-changed.log
cp "$dist/install.sh" "$root/$release_path/install.sh"
[ "$(served install.sh)" -eq 1 ] || fail "the server did not serve install.sh once"

friend "the line, answering No at Continue?" '
code=0
printf "n\n" | bash -c "$LINE" >/tmp/line-no.log 2>&1 || code=$?
tail -n 4 /tmp/line-no.log
[ "$code" -eq 1 ] || { echo "70-release: exit $code, not 1"; cat /tmp/line-no.log; exit 1; }
grep -qx "install.sh: OK" /tmp/line-no.log
grep -qF "Licences: $HOME/.local/share/songcharter/app/$VERSION/NOTICE.txt (some of the models are for non-commercial use only)" /tmp/line-no.log
grep -q "Continue? \[Y/n\] songcharter: stopped; nothing was downloaded.$" /tmp/line-no.log'
keep /tmp/line-no.log
[ "$(served "$tarball")" -eq 0 ] || fail "the tarball was fetched before the answer"

friend "the line, pressing Enter" '
code=0
printf "\n" | bash -c "$LINE" >/tmp/line-yes.log 2>&1 || code=$?
tail -n 6 /tmp/line-yes.log
[ "$code" -eq 0 ] || { echo "70-release: exit $code, not 0"; tail -n 40 /tmp/line-yes.log; exit 1; }
grep -qx "install.sh: OK" /tmp/line-yes.log
grep -q "^songcharter $VERSION is installed (lane " /tmp/line-yes.log
sha256sum ~/.local/share/songcharter/app/$VERSION/NOTICE.txt'
keep /tmp/line-yes.log
[ "$(served install.sh)" -eq 3 ] && [ "$(served "$tarball")" -eq 1 ] ||
  fail "the server did not serve install.sh 3 times and the tarball once (above: $server_log)"
docker cp "$name:/home/friend/.local/share/songcharter/app/$version/NOTICE.txt" "$CI_TMP/NOTICE.installed" >/dev/null
cmp -s "$CI_TMP/NOTICE.installed" packaging/NOTICE.txt || fail "the installed NOTICE.txt is not packaging/NOTICE.txt"
echo "70-release: the installed NOTICE.txt is packaging/NOTICE.txt"

# --- 5. the guide's other commands, as written
friend "songcharter (the page)" '
songcharter >/tmp/page.log 2>&1 &
pid=$!
address=""
for _ in $(seq 1 600); do
  address=$(sed -n "s|^songcharter is at \(http://[^ ]*\) .*|\1|p" /tmp/page.log | head -n 1)
  [ -z "$address" ] || break
  kill -0 "$pid" 2>/dev/null || { cat /tmp/page.log; echo "70-release: songcharter ended"; exit 1; }
  sleep 0.1
done
[ -n "$address" ] || { cat /tmp/page.log; echo "70-release: songcharter gave no address"; exit 1; }
curl -fsS "$address" | grep -q "<title>songcharter</title>"
kill -TERM "$pid"
wait "$pid"
cat /tmp/page.log'
keep /tmp/page.log

friend "songcharter diagnostics --out diagnostics.zip" '
songcharter diagnostics --out diagnostics.zip | tee /tmp/diagnostics.log
grep -qx "diagnostics: $HOME/diagnostics.zip" /tmp/diagnostics.log
~/.local/share/songcharter/runtime/env/bin/python /ci/check_no_audio.py diagnostics.zip'
keep /tmp/diagnostics.log /home/friend/diagnostics.zip

friend "songcharter uninstall, answered with Enter (No)" '
printf "\n" | songcharter uninstall | tee /tmp/uninstall.log
grep -q "^kept .*: a reinstall downloads nothing$" /tmp/uninstall.log
[ ! -e ~/.local/bin/songcharter ] && [ ! -e ~/.local/share/songcharter/app ] && [ -d ~/.local/share/songcharter/runtime/env ]'
keep /tmp/uninstall.log
"$CI_PY" packaging/ci/check_no_audio.py "$art"
echo "70-release: ok"
