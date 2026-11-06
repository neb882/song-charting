#!/usr/bin/env bash
# 30-install.sh (M4-03): the install from the release assets, as the friend runs it, in ubuntu:26.04 as a plain user.
#   1. the shortcut's and the Windows side's tests with LnkParse3 (added to $CI_PY with uv: the suite ran without it);
#   2. packaging/release/build.sh's assets, given to the install as a folder (--from);
#   3. in `docker run ubuntu:26.04`, after `apt-get install -y curl ca-certificates git xz-utils` (the WSL image's
#      tools) and `useradd -m friend`, as friend:
#      - the install with --lane auto, killed during its uv sync, then run again: exit 0, and the cpu lane with "no
#        NVIDIA GPU found" (the runner has no nvidia-smi);
#      - `songcharter doctor` exits 0;
#      - the clip ($CI_CLIP), charted on the CPU, passes check_gate.py;
#      - uninstall answering No, then the install again: exit 0, with no download (no uv "Downloading" line, no fetch
#        line);
#      - uninstall answering Yes: ~/.local/share/songcharter, ~/.cache/songcharter and the launcher are gone.
#   4. the noise check (M5-08), on the logs of the install that ran to its end and of the reinstall: no npm warning
#      ("npm warn", or "WARN"), no hub or Python warning ("Warning:"), no "unauthenticated", no carriage return (a bar
#      redrawn in place) and no bar character (█, ▏-▉). The check is tried on lines it must flag and on quiet ones
#      first. The killed install's log is not checked: it has curl's meter for uv's tarball (install.sh's download).
# The logs, runtime.json, doctor.json and the clip's report.json go to $CI_ART/30-install (no audio).
# Run by packaging/ci/run-hooks.sh with bash -euo pipefail; uses CI_PY, CI_TMP, CI_ART and CI_CLIP, uv and Docker.
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
art="$CI_ART/30-install"
dist="$CI_TMP/dist"
mkdir -p "$art"

NOISE=$'npm warn|WARN|[Ww]arning:|unauthenticated|\r|█|▏|▎|▍|▌|▋|▊|▉'   # alternatives, not a bracket: any locale
noisy() {   # FILE...: prints each line that is noise (with its file and number); true when there is one
  grep -naE -- "$NOISE" "$@"
}
quiet() {   # FILE...: the logs are there and have no noise, else the hook fails
  local f
  for f in "$@"; do [ -s "$f" ] || { echo "30-install: $f is missing or empty"; exit 1; }; done
  if noisy "$@"; then echo "30-install: the install's log has noise, above (M5-08)"; exit 1; fi
  echo "30-install: no noise in $*"
}
probe="$CI_TMP/noise-probe.log"
for line in "npm warn deprecated fluent-ffmpeg@2.1.3" "npm WARN old npm" "Warning: You are sending unauthenticated" \
  "UserWarning: a Python warning" "warning: \`VIRTUAL_ENV=/x\` does not match the project environment path" \
  "unauthenticated requests" $'a bar\rredrawn' "50%|█████     | 1/2" "▏" "▉"; do
  printf '%s\n' "$line" >"$probe"
  noisy "$probe" >/dev/null || { echo "30-install: the noise check misses: $line"; exit 1; }
  if (quiet "$probe") >/dev/null; then echo "30-install: the noise check passes a log with: $line"; exit 1; fi
done
printf '%s\n' "fetch htdemucs_6s, file 2 of 2: done, 84 MB" "added 19 packages in 2s" "the lane changes: cu126 → cu132" \
  >"$probe"
if noisy "$probe"; then echo "30-install: the noise check flags a quiet line"; exit 1; fi
(quiet "$probe") >/dev/null || { echo "30-install: the noise check fails a quiet log"; exit 1; }

uv pip install --python "$CI_PY" --quiet LnkParse3==1.6.0
"$CI_PY" -m pytest -q -rs -p no:cacheprovider --basetemp="$CI_TMP/pt-install" tests/test_winshortcut.py \
  tests/test_wslsetup.py | tee "$art/tests.txt"
if grep -q skipped "$art/tests.txt"; then
  echo "30-install: a shortcut test was skipped"
  exit 1
fi

# HEAD's version, as build.sh wants it (M5-12), with 70-release's suffix
version="$(git show HEAD:songcharter/__init__.py | sed -n 's/^__version__ = "\(.*\)"$/\1/p')-ci-$(git rev-parse --short HEAD)"
PYTHON="$CI_PY" bash packaging/release/build.sh "$version" "$dist"
name="sc-install-$$"
docker run -d --name "$name" -v "$dist:/dist:ro" -v "$PWD/packaging/ci:/ci:ro" -v "$CI_CLIP:/clip.wav:ro" \
  ubuntu:26.04 sleep infinity >/dev/null
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker exec -e DEBIAN_FRONTEND=noninteractive "$name" bash -euo pipefail -c \
  'apt-get update -qq && apt-get install -y -qq curl ca-certificates git xz-utils >/dev/null && useradd -m friend'

friend() {   # NAME SCRIPT: SCRIPT in the container as friend, timed
  local start=$SECONDS
  echo "-- $1"
  docker exec -u friend -e HOME=/home/friend -w /home/friend "$name" bash -euo pipefail -c "$2"
  echo "-- $1: ok in $((SECONDS - start)) s"
}
keep() {   # FILE...: copied from the container into $CI_ART
  for f in "$@"; do docker cp "$name:$f" "$art/" >/dev/null 2>&1 || true; done
}

friend "the install, killed during its uv sync" '
setsid bash /dist/install.sh --from /dist --lane auto --yes >/tmp/install-1.log 2>&1 &
pid=$!
killed=0
for _ in $(seq 1 2400); do
  if sed -n "/^== \[7\/10\]/,\$p" /tmp/install-1.log | grep -q "Downloading"; then
    kill -TERM -- "-$pid"
    killed=1
    break
  fi
  kill -0 "$pid" 2>/dev/null || break
  sleep 0.25
done
code=0
wait "$pid" || code=$?
tail -n 3 /tmp/install-1.log
[ "$killed" -eq 1 ] || { echo "30-install: the install never reached a download in its uv sync"; exit 1; }
[ "$code" -ne 0 ] || { echo "30-install: the killed install exited 0"; exit 1; }
tail -n 1 /tmp/install-1.log | grep -q "failed: .*Run the same command again to continue.$"
echo "killed during the uv sync: exit $code"'
keep /tmp/install-1.log

friend "the install again" '
bash /dist/install.sh --from /dist --lane auto --yes >/tmp/install-2.log 2>&1 || { tail -n 40 /tmp/install-2.log; exit 1; }
tail -n 4 /tmp/install-2.log
grep -q "\"lane\": \"cpu\"" ~/.local/share/songcharter/runtime/runtime.json
grep -q "\"lane_reason\": \"no NVIDIA GPU found\"" ~/.local/share/songcharter/runtime/runtime.json
du -sh ~/.local/share/songcharter ~/.cache/songcharter
du -sh ~/.local/share/songcharter/runtime/uv-cache   # in the home: its own du, as one du counts a file once
[ ! -e ~/.cache/uv ] || { echo "30-install: the install wrote ~/.cache/uv, not its own runtime/uv-cache"; exit 1; }'
keep /tmp/install-2.log /home/friend/.local/share/songcharter/runtime/runtime.json \
  /home/friend/.local/share/songcharter/doctor.json
quiet "$art/install-2.log"

friend "doctor" '~/.local/bin/songcharter doctor --json /tmp/doctor-full.json'
keep /tmp/doctor-full.json

friend "the clip" '
~/.local/bin/songcharter chart /clip.wav --out ~/Songs/Clip --device cpu >/tmp/clip.log 2>&1 || { tail -n 40 /tmp/clip.log; exit 1; }
~/.local/share/songcharter/runtime/env/bin/python /ci/check_gate.py ~/Songs/Clip'
keep /tmp/clip.log /home/friend/Songs/Clip/report.json

friend "uninstall, keeping the downloads, then the install again" '
printf "n\n" | ~/.local/bin/songcharter uninstall
[ ! -e ~/.local/bin/songcharter ] && [ ! -e ~/.local/share/songcharter/app ] && [ -d ~/.local/share/songcharter/runtime/env ]
bash /dist/install.sh --from /dist --lane auto --yes >/tmp/install-3.log 2>&1 || { tail -n 40 /tmp/install-3.log; exit 1; }
if grep -nE "Download(ing|ed) " /tmp/install-3.log; then echo "30-install: uv downloaded on the reinstall"; exit 1; fi
if grep -n "^fetch " /tmp/install-3.log; then echo "30-install: fetch downloaded on the reinstall"; exit 1; fi
echo "the reinstall downloaded nothing"'
keep /tmp/install-3.log
quiet "$art/install-3.log"

friend "uninstall, deleting everything" '
printf "y\n" | ~/.local/bin/songcharter uninstall
for gone in ~/.local/share/songcharter ~/.cache/songcharter ~/.local/bin/songcharter; do
  [ ! -e "$gone" ] || { echo "30-install: $gone is still there"; exit 1; }
done'
echo "30-install: ok"
