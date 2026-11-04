#!/usr/bin/env bash
# 50-e2e.sh (M4-05): before anything reaches the friend, CI does what he will do, on his Ubuntu (26.04), from nothing,
# on the cpu lane (the runner has no GPU): install from the release assets as a plain user, doctor, chart a song, use
# the page, cancel a run, chart offline, uninstall and reinstall. The clip is made by code (make_clip.py), never a
# recording.
#   1. packaging/release/build.sh's assets into $CI_TMP/dist;
#   2. `docker run ubuntu:26.04` (sc-e2e) with /dist and /ci (packaging/ci) read-only, and `e2e.sh prepare` as root;
#   3. e2e.sh's phases as friend, each a `docker exec`: install, doctor, doctor-gpu, clip, guards; then the network is
#      cut from outside (docker network disconnect bridge) for `offline` and `uninstall-keep` (whose reinstall must
#      download nothing: with no network, any download fails it), and given back; then uninstall-all (e2e.sh says what
#      each checks);
#   4. the install alone (prepare, install, doctor-quick) on ubuntu:24.04, which must pass, and on ubuntu:22.04, which
#      is reported and never fails the hook (the guide's `wsl --update` makes a fresh install 26.04; an older WSL can
#      still give the friend 22.04, M4-00's finding 1);
#   5. each container's ~/e2e (logs, doctor.json, runtime.json, the clip's report.json, pipeline.json and preview
#      overview, ui-guards.json, figures.txt) into $CI_ART/e2e/<ubuntu>/ once check_no_audio.py has passed it, and the
#      container removed, before the next one starts (each install takes about 5 GB of the runner's disk).
# Containers run with --init, so orphans are reaped as WSL's init reaps them: a process the cancel killed whose parent
# went first is then gone, not left as a zombie of `sleep`.
# Run by packaging/ci/run-hooks.sh with bash -euo pipefail; uses CI_PY, CI_TMP and CI_ART, git, curl and Docker.
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
art="$CI_ART/e2e"
dist="$CI_TMP/dist"
mkdir -p "$art"
running=()

collect() {   # CONTAINER NAME: its ~/e2e into $art/NAME, once check_no_audio.py has passed it (else 1, and nothing kept)
  local tmp="$CI_TMP/e2e-$2"
  rm -rf "$tmp"
  if ! docker cp "$1:/home/friend/e2e" "$tmp" >/dev/null 2>&1; then
    echo "50-e2e: $1 has no ~/e2e to collect"
    return 0
  fi
  if ! "$CI_PY" packaging/ci/check_no_audio.py "$tmp"; then
    echo "50-e2e: $1's ~/e2e holds audio (above): not kept"
    rm -rf "$tmp"
    return 1
  fi
  rm -rf "${art:?}/$2"
  mv "$tmp" "$art/$2"
  if [ -f "$art/$2/figures.txt" ]; then
    echo "50-e2e: $2's figures:"
    sed 's/^/  /' "$art/$2/figures.txt"
  fi
}

remove() {   # CONTAINER NAME: collected, then removed; collect's status
  local code=0 left=() c
  collect "$1" "$2" || code=$?
  docker rm -f "$1" >/dev/null 2>&1 || true
  for c in "${running[@]+"${running[@]}"}"; do [ "$c" = "$1:$2" ] || left+=("$c"); done
  running=("${left[@]+"${left[@]}"}")
  return $code
}

finish() {   # on any exit: what is still running is collected and removed
  local code=$? c
  for c in "${running[@]+"${running[@]}"}"; do remove "${c%%:*}" "${c#*:}" || code=1; done
  exit $code
}
trap finish EXIT

start() {   # CONTAINER IMAGE NAME: the container, prepared (as root)
  echo
  echo "== $1: $2"
  docker rm -f "$1" >/dev/null 2>&1 || true
  docker run -d --init --name "$1" -v "$dist:/dist:ro" -v "$PWD/packaging/ci:/ci:ro" "$2" sleep infinity >/dev/null
  running+=("$1:$3")
  docker exec "$1" bash /ci/e2e.sh prepare
}

phase() {   # CONTAINER PHASE: one of e2e.sh's phases, as friend, timed
  local start=$SECONDS code=0
  echo
  echo "== $1: $2"
  docker exec -u friend -e HOME=/home/friend -w /home/friend "$1" bash /ci/e2e.sh "$2" || code=$?
  if [ $code -ne 0 ]; then
    echo "== $1: $2 FAILED (exit $code) after $((SECONDS - start)) s"
    return $code
  fi
  echo "== $1: $2 ok in $((SECONDS - start)) s"
}

disk() { echo "50-e2e: disk: $(df -h --output=avail,size / | tail -n 1 | awk '{ print $1 " free of " $2 }')"; }

disk
PYTHON="$CI_PY" bash packaging/release/build.sh "0.1.0-ci-$(git rev-parse --short HEAD)" "$dist"

# --- Ubuntu 26.04: everything
c=sc-e2e
start $c ubuntu:26.04 26.04
for p in install doctor doctor-gpu clip guards; do phase $c $p; done
docker network disconnect bridge $c
echo "50-e2e: the network of $c is cut"
code=0
for p in offline uninstall-keep; do   # the reinstall too: with no network, any download fails it
  phase $c $p || { code=$?; break; }
done
docker network connect bridge $c
echo "50-e2e: the network of $c is back"
[ $code -eq 0 ] || exit $code
phase $c uninstall-all
disk
remove $c 26.04

# --- Ubuntu 24.04: the install alone, which must pass
c=sc-e2e-24.04
start $c ubuntu:24.04 24.04
phase $c install
phase $c doctor-quick
disk
remove $c 24.04

# --- Ubuntu 22.04: the install alone, reported
c=sc-e2e-22.04
older=ok
if ! start $c ubuntu:22.04 22.04; then
  older="FAILED at prepare"
elif ! phase $c install; then
  older="FAILED at install"
elif ! phase $c doctor-quick; then
  older="FAILED at doctor --quick"
fi
remove $c 22.04
echo
echo "50-e2e: Ubuntu 22.04's install: $older (reported only: it does not fail this hook)"
echo "50-e2e: ok (Ubuntu 26.04 end to end, 24.04's install; 22.04's install $older)"
