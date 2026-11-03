#!/usr/bin/env bash
# run-hooks.sh: runs the Linux CI hooks (the `linux` job of .github/workflows/ci.yml, after the suite).
#
#   bash packaging/ci/run-hooks.sh linux
#
# Runs every packaging/ci/linux.d/*.sh in name order (bytewise), each as `bash -euo pipefail <hook>` from the
# repository's root with stdin from /dev/null, and prints a header per hook and its time. Stops at the first hook that
# exits non-zero, and exits with its code. Exits 2, running nothing, when linux.d is missing or holds anything but
# README.txt and *.sh files. The hook contract (the numbering, the CI_* variables) is linux.d/README.txt.
#
# Before the first hook it sets what the caller did not (so it also runs by hand): CI_PY (python3 on PATH), CI_TMP and
# CI_ART (under $RUNNER_TEMP, or /tmp), and CI_CLIP ($CI_TMP/clip.wav), all absolute. It makes the two folders, and
# writes the 30-s clip with make_clip.py, unless CI_CLIP names another file that exists.
set -euo pipefail

platform=${1:-}
if [ "$platform" != linux ] || [ $# -ne 1 ]; then
  echo "usage: run-hooks.sh linux" >&2
  exit 2
fi
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=$(cd "$here/../.." && pwd)
dir="$here/$platform.d"

# The hooks: the *.sh files directly in linux.d. Anything else there but README.txt (another extension, no extension,
# a hidden file, a folder) is a hook in the wrong shape, which would otherwise be skipped without a word: exit 2.
if [ ! -d "$dir" ]; then
  echo "run-hooks: no hook folder $dir" >&2
  exit 2
fi
hooks=()
stray=()
while IFS= read -r -d '' entry; do
  name=${entry##*/}
  if [ "$name" = README.txt ] && [ -f "$entry" ]; then
    continue
  elif [[ $name == [!.]*.sh ]] && [ -f "$entry" ]; then
    hooks+=("$entry")
  else
    stray+=("$platform.d/$name")
  fi
done < <(find "$dir" -mindepth 1 -maxdepth 1 -print0 | LC_ALL=C sort -z)
if [ ${#stray[@]} -ne 0 ]; then
  printf 'run-hooks: not a hook: %s\n' "${stray[@]}" >&2
  echo "run-hooks: a hook is a NN-name.sh file directly in $platform.d, and README.txt the only other entry" >&2
  exit 2
fi

base=${RUNNER_TEMP:-/tmp}
: "${CI_PY:=$(command -v python3 || true)}"
if [ -z "$CI_PY" ]; then
  echo "run-hooks: no CI_PY, and no python3 on PATH" >&2
  exit 2
fi
: "${CI_TMP:=$base/ci-tmp}"
: "${CI_ART:=$base/ci-artifacts}"
mkdir -p "$CI_TMP" "$CI_ART"
CI_TMP=$(cd "$CI_TMP" && pwd)   # absolute: the hooks run from the repository's root
CI_ART=$(cd "$CI_ART" && pwd)
: "${CI_CLIP:=$CI_TMP/clip.wav}"
CI_CLIP=$(realpath -m -- "$CI_CLIP")
export CI_PY CI_TMP CI_ART CI_CLIP
if [ ! -f "$CI_CLIP" ] || [ "$CI_CLIP" = "$CI_TMP/clip.wav" ]; then
  "$CI_PY" "$here/make_clip.py" "$CI_CLIP" 30
fi
echo "CI_PY=$CI_PY"
echo "CI_TMP=$CI_TMP"
echo "CI_ART=$CI_ART"
echo "CI_CLIP=$CI_CLIP"

if [ ${#hooks[@]} -eq 0 ]; then
  echo "no Linux hooks"
  exit 0
fi

cd "$root"
done_list=()
for hook in "${hooks[@]}"; do
  name=$platform.d/$(basename "$hook")
  echo
  echo "==== hook $name"
  start=$SECONDS
  code=0
  bash -euo pipefail "$hook" </dev/null || code=$?
  took=$((SECONDS - start))
  if [ $code -ne 0 ]; then
    echo "==== hook $name FAILED (exit $code) after ${took} s"
    echo "hooks passed before it: ${done_list[*]:-none}"
    exit $code
  fi
  echo "==== hook $name ok in ${took} s"
  done_list+=("$(basename "$hook") ${took}s")
done
echo
echo "all ${#hooks[@]} Linux hooks passed: ${done_list[*]}"
