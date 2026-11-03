#!/usr/bin/env bash
# install.sh: songcharter in WSL2 (or plain Linux), from its GitHub release, for this user, with no sudo (M4-03).
#
#   bash install.sh [--lane auto|cpu|cu126|cu132] [--yes] [--from DIR|URL] [--windows-ram-gb N]
#
# Ten steps, each with a header: where it runs (WSL or not), the torch lane (from nvidia-smi, at every run), free
# disk, WSL's memory, what will be downloaded (then "Continue? [Y/n]" unless --yes), uv and Python and the app, the
# two environments (songcharter's and allin1's, with `uv sync --frozen` on exactly one lane), the rest (python -m
# songcharter.runtime setup: Node, scan-chart, autochart and its models, the pipeline's models, runtime.json,
# doctor.json), the Windows side (python -m songcharter.wslsetup apply: .wslconfig and the Start-menu shortcut), and
# the launcher, ~/.local/bin/songcharter. On plain Linux the Windows steps are skipped.
#
#   * Rerunnable: every step checks what is there first, downloads go through .part files (resumed), and a failure
#     ends with "songcharter: <step> failed: <one line>. Run the same command again to continue." (exit 2). A rerun
#     picks the lane again, so a new driver moves the install to the GPU build.
#   * --from takes the release assets (this script's tarball) from a folder or a URL prefix, for CI;
#     $SONGCHARTER_RELEASE_URL replaces the release URL prefix (M4-07's check runs the guide's line against a local
#     server). $SONGCHARTER_HOME moves the install (default ~/.local/share/songcharter).
#   * packaging/release/build.sh fills in the @...@ values below; this file in the repository is the template.
#   * Needs bash, curl or wget, tar, xz and sha256sum, which Ubuntu's WSL image ships. Refuses to run as root.
set -Eeuo pipefail

VERSION="@VERSION@"
APP_SHA256="@APP_SHA256@"
RELEASE_URL="${SONGCHARTER_RELEASE_URL:-@RELEASE_URL@}"
UV_URL="@UV_URL@"
UV_SHA256="@UV_SHA256@"
UV_VERSION=0.13.5
PYTHON_VERSION=3.13.17
WSL_NVIDIA_SMI=/usr/lib/wsl/lib/nvidia-smi   # WSL's, from the Windows driver [doc: NVIDIA's WSL guide]
SMI_TIMEOUT_S=15                             # songcharter.device's: a slower nvidia-smi is a GPU out of reach
GB=1000000000
# free disk each lane needs, in GB: the downloads unpacked plus the work folders' 5 GB [decision; M4-05, M4-08 measure]
need_gb() { case $1 in cpu) echo 6 ;; *) echo 15 ;; esac; }
# what each lane downloads, in GB: the Python packages, then the rest (Node, autochart and its models, the CUDA
# provider on a GPU lane, the pipeline's models) [here: the locks' wheel sizes; M4-05 confirms]
packages_gb() { case $1 in cpu) echo 0.45 ;; cu126) echo 3.9 ;; cu132) echo 3.2 ;; esac; }
REST_GB=1

step=start
fail() {   # the one last line of a failure, then exit 2
  trap - ERR
  echo "songcharter: $step failed: $*. Run the same command again to continue." >&2
  exit 2
}
on_error() { fail "'$2' exited $1"; }
header() { step=$1; echo; echo "== [$2/10] $3"; }
have() { command -v "$1" >/dev/null 2>&1; }
trim() { local s=$1; s=${s#"${s%%[![:space:]]*}"}; printf '%s' "${s%"${s##*[![:space:]]}"}"; }
gb() { awk -v b="$1" 'BEGIN { printf "%.1f", b / 1e9 }'; }

usage() {
  echo "usage: bash install.sh [--lane auto|cpu|cu126|cu132] [--yes] [--from DIR|URL] [--windows-ram-gb N]"
}

# ------------------------------------------------------------------------------------------------ helpers

sha_of() { sha256sum "$1" | cut -d' ' -f1; }

download() {   # URL DEST SHA256: DEST, checked against SHA256, through DEST.part (resumed when it holds a start)
  local url=$1 dest=$2 sha=$3 part=$2.part
  if [ -f "$dest" ] && [ "$(sha_of "$dest")" = "$sha" ]; then return 0; fi
  rm -f "$dest"
  mkdir -p "$(dirname "$dest")"
  if [ -s "$part" ] && [ "$(sha_of "$part")" = "$sha" ]; then mv -f "$part" "$dest"; return 0; fi
  echo "downloading $url"
  if have curl; then
    curl -fL --retry 5 --retry-delay 3 --connect-timeout 30 -C - -o "$part" "$url" ||
      { rm -f "$part"; curl -fL --retry 5 --retry-delay 3 --connect-timeout 30 -o "$part" "$url"; } ||
      fail "could not download $url"
  elif have wget; then
    wget -c -t 5 -T 60 -O "$part" "$url" || fail "could not download $url"
  else
    fail "neither curl nor wget is installed (sudo apt install curl)"
  fi
  local got
  got=$(sha_of "$part")
  if [ "$got" != "$sha" ]; then rm -f "$part"; fail "$url has SHA-256 $got, not the pinned $sha"; fi
  mv -f "$part" "$dest"
}

asset() {   # NAME DEST SHA256: a release asset, from --from (a folder or a URL prefix) or the release
  if [ -n "$from" ] && [ -d "$from" ]; then
    [ -f "$from/$1" ] || fail "$from has no $1"
    cp -f "$from/$1" "$2.part"
    [ "$(sha_of "$2.part")" = "$3" ] || { rm -f "$2.part"; fail "$from/$1 is not the file this install.sh was built with"; }
    mv -f "$2.part" "$2"
  else
    download "${from:-$RELEASE_URL}/$1" "$2" "$3"
  fi
}

win_cmd() {   # ARGS...: cmd.exe through WSL's interop, run from /mnt/c so it does not warn about a UNC folder
  [ -n "$cmd_exe" ] || return 1
  (cd /mnt/c 2>/dev/null || cd /; timeout 10 "$cmd_exe" /d "$@")
}

previous_lane() {   # the lane in runtime.json, if there is one
  sed -n 's/^ *"lane": *"\([a-z0-9]*\)".*/\1/p' "$home/runtime/runtime.json" 2>/dev/null | head -n 1 || true
}

choose_lane() {   # ASKED (auto or a lane): sets lane, lane_reason and lane_warning; refuses a silent move to cpu
  local asked=$1 smi="" out="" code=0 name="" driver="" cap="" major=0 cap10=-1 state
  lane_warning=""
  smi=$(command -v nvidia-smi || true)
  if [ -z "$smi" ] && [ -x "$WSL_NVIDIA_SMI" ]; then smi=$WSL_NVIDIA_SMI; fi
  if [ -z "$smi" ]; then
    state=missing
  else
    out=$(timeout "$SMI_TIMEOUT_S" "$smi" --query-gpu=name,driver_version,compute_cap --format=csv,noheader,nounits \
      2>&1) || code=$?
    if [ "$code" -eq 124 ]; then
      state=failed   # a timeout too: songcharter.device counts it as a GPU out of reach
      out="nvidia-smi did not answer within $SMI_TIMEOUT_S s"
    elif [ "$code" -ne 0 ]; then
      state=failed   # there but failing: a GPU it cannot reach (songcharter.device's SMI_FAILED), not no GPU
      out="nvidia-smi failed (exit $code): $(printf '%s' "$out" | tr -s '\r\n\t ' ' ' | cut -c1-200)"
    elif [ -z "$(printf '%s' "$out" | tr -d '[:space:]')" ]; then
      state=none
    else
      state=ok
      IFS=, read -r name driver cap _ <<<"$(printf '%s\n' "$out" | head -n 1)"
      name=$(trim "$name"); driver=$(trim "$driver"); cap=$(trim "$cap")
      major=${driver%%.*}
      if [[ $major =~ ^[0-9]+$ ]]; then major=$((10#$major)); else major=0; fi
      if [[ $cap =~ ^([0-9]+)\.([0-9])$ ]]; then cap10=$((10#${BASH_REMATCH[1]} * 10 + BASH_REMATCH[2])); fi
    fi
  fi
  if [ "$asked" != auto ]; then
    lane=$asked lane_reason="asked for with --lane $asked"
    return 0
  fi
  case $state in
    missing | none) lane=cpu lane_reason="no NVIDIA GPU found" ;;
    failed)
      local before
      before=$(previous_lane)
      if [ "$before" = cu126 ] || [ "$before" = cu132 ]; then
        fail "$out: the GPU is out of reach, not missing, so this $before install is not moved to the CPU build. Restart Windows (or update the NVIDIA driver) and run the same line again; or add --lane cpu to move to the CPU build"
      fi
      lane=cpu lane_reason="nvidia-smi failed, so CUDA cannot run: $out"
      ;;
    ok)
      if [ "$major" -lt 528 ]; then
        lane=cpu lane_reason="$name with driver $driver: update the NVIDIA driver to 528 or newer, then paste the install line again"
      elif [ "$major" -ge 580 ] && { [ "$cap10" -ge 75 ] || [ "$cap10" -lt 0 ]; }; then
        lane=cu132 lane_reason="$name, driver $driver, compute capability ${cap:-unknown}"
      elif [ "$cap10" -ge 120 ]; then
        lane=cpu lane_reason="$name (compute capability $cap) needs a 580 or newer driver, and this one is $driver (the cu126 build has no kernels for it): update the NVIDIA driver to 580 or newer, then paste the install line again"
      else
        lane=cu126 lane_reason="$name, driver $driver, compute capability $cap"
        if [ "$major" -lt 580 ]; then
          lane_warning="the guitar runs on the CPU: update the NVIDIA driver to 580 or newer, then paste the install line again: it switches to the GPU build (about 3 GB)"
        else
          lane_warning="the guitar runs on the CPU: compute capability $cap is under 7.5, which the GPU build for the guitar (cu132) needs"
        fi
      fi
      ;;
  esac
}

helper() {   # WHAT COMMAND...: one of the install's Python helpers (steps 8 and 9), its exit status in helper_code
  # 0 and 1 come back. Any other end (an error, a bug, a signal such as the out-of-memory killer's SIGKILL) ends the
  # install with the one failure line: the helper's own, when it wrote it to $SONGCHARTER_FAILURE as it printed it
  # last, else this one.
  local what=$1 failure=$state/failure
  shift
  rm -f "$failure"
  helper_code=0
  SONGCHARTER_FAILURE=$failure "$@" || helper_code=$?
  case $helper_code in 0 | 1) return 0 ;; esac
  if [ -s "$failure" ]; then trap - ERR; exit "$helper_code"; fi
  local why="exit $helper_code"
  if [ "$helper_code" -gt 128 ]; then
    local sig=$((helper_code - 128))
    why="killed by signal $sig ($(kill -l "$sig" 2>/dev/null || echo ?))"
    if [ "$sig" -eq 9 ]; then why="$why: perhaps Linux ran out of memory"; fi
  fi
  fail "$what stopped before it finished ($why)"
}

sync_env() {   # WHAT PROJECT ENVIRONMENT [OPTIONS...]: `uv sync --frozen` of one environment on the chosen lane
  case ${lane:-} in
    cpu | cu126 | cu132) ;;
    *) fail "no torch lane is chosen (${lane:-none}): it is cpu, cu126 or cu132. Without one, uv sync would install PyPI's CUDA torch (about 3 GB), and allin1 would have no torchaudio" ;;
  esac
  local what=$1 project=$2 env=$3
  shift 3
  echo "$what: $env (lane $lane)"
  UV_PROJECT_ENVIRONMENT="$env" "$uv" sync --project "$project" --frozen --no-dev --managed-python \
    --python "$PYTHON_VERSION" --extra "$lane" "$@" || fail "uv sync of $what exited $? (its error is above)"
}

# ------------------------------------------------------------------------------------------------ the steps

main() {
  local lane_asked=auto yes=0 ram_gb=${SONGCHARTER_WINDOWS_RAM_GB:-}
  from=""
  while [ $# -gt 0 ]; do
    case $1 in
      --lane) [ $# -ge 2 ] || { usage >&2; exit 2; }; lane_asked=$2; shift 2 ;;
      --lane=*) lane_asked=${1#*=}; shift ;;
      --yes | -y) yes=1; shift ;;
      --from) [ $# -ge 2 ] || { usage >&2; exit 2; }; from=${2%/}; shift 2 ;;
      --from=*) from=${1#*=}; from=${from%/}; shift ;;
      --windows-ram-gb) [ $# -ge 2 ] || { usage >&2; exit 2; }; ram_gb=$2; shift 2 ;;
      --windows-ram-gb=*) ram_gb=${1#*=}; shift ;;
      -h | --help) usage; exit 0 ;;
      *) usage >&2; echo "songcharter: unknown option $1" >&2; exit 2 ;;
    esac
  done
  case $lane_asked in auto | cpu | cu126 | cu132) ;; *) usage >&2; exit 2 ;; esac
  trap 'on_error $? "$BASH_COMMAND"' ERR
  trap 'echo; fail interrupted' INT TERM
  case $VERSION in @*) fail "this is install.sh's template: make the release with packaging/release/build.sh" ;; esac
  [ "$(id -u)" -ne 0 ] || fail "songcharter installs for your own user: run it as your Ubuntu user, without sudo"
  for tool in tar xz sha256sum; do have "$tool" || fail "$tool is not installed (sudo apt install xz-utils coreutils tar)"; done

  home=${SONGCHARTER_HOME:-$HOME/.local/share/songcharter}
  local runtime=$home/runtime state=$home/runtime/state dl=$home/runtime/state/downloads
  local app=$home/app/$VERSION launcher=$HOME/.local/bin/songcharter
  local cache=${XDG_CACHE_HOME:-$HOME/.cache} uv=$home/bin/uv py=$home/runtime/env/bin/python
  local uv_cache=${UV_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/uv}
  mkdir -p "$home/bin" "$home/app" "$dl"
  echo "songcharter $VERSION: the install, into $home"

  header where 1 "Where am I"
  in_wsl=0 cmd_exe=""
  if [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null; then in_wsl=1; fi
  if [ $in_wsl -eq 1 ]; then
    cmd_exe=$(command -v cmd.exe || true)
    if [ -z "$cmd_exe" ] && [ -x /mnt/c/Windows/System32/cmd.exe ]; then cmd_exe=/mnt/c/Windows/System32/cmd.exe; fi
    if [ -n "$cmd_exe" ] && win_cmd /c "exit 0" >/dev/null 2>&1; then
      echo "WSL (${WSL_DISTRO_NAME:-?}), with Windows interop"
    else
      cmd_exe=""
      echo "WSL (${WSL_DISTRO_NAME:-?}), but Windows interop is off: .wslconfig and the Start-menu shortcut are left to you"
    fi
  else
    echo "plain Linux: the Windows steps (WSL's memory, .wslconfig, the Start-menu shortcut) are skipped"
  fi

  header lane 2 "The torch lane"
  choose_lane "$lane_asked"
  local before
  before=$(previous_lane)
  echo "lane $lane: $lane_reason"
  if [ -n "$lane_warning" ]; then echo "warning: $lane_warning"; fi
  if [ -n "$before" ] && [ "$before" != "$lane" ]; then echo "the lane changes: $before → $lane (uv swaps torch and the CUDA wheels)"; fi

  header disk 3 "Disk"
  local need present=0 free_home free_c="" left there=()
  need=$(($(need_gb "$lane") * GB))
  for p in "$runtime" "$uv_cache" "$cache/songcharter"; do if [ -e "$p" ]; then there+=("$p"); fi; done
  if [ ${#there[@]} -gt 0 ]; then
    present=$({ du -scb -- "${there[@]}" 2>/dev/null || true; } | tail -n 1 | cut -f1)
    [[ $present =~ ^[0-9]+$ ]] || present=0
  fi
  left=$((need > present ? need - present : 0))
  free_home=$(df -B1 --output=avail -- "$HOME" | tail -n 1 | tr -d ' ')
  if [ $in_wsl -eq 1 ] && [ -d /mnt/c ]; then free_c=$(df -B1 --output=avail -- /mnt/c 2>/dev/null | tail -n 1 | tr -d ' ' || true); fi
  echo "lane $lane needs about $(need_gb "$lane") GB (the downloads unpacked, and 5 GB of work folders); $(gb "$present") GB of it is here already"
  local on_c=""
  if [ -n "$free_c" ]; then on_c=", $(gb "$free_c") GB on C: (where WSL's disk grows)"; fi
  echo "free: $(gb "$free_home") GB in $HOME$on_c"
  if [ "$free_home" -lt "$left" ] || { [ -n "$free_c" ] && [ "$free_c" -lt "$left" ]; }; then
    fail "not enough free disk: $(gb "$left") GB more are needed, and there are $(gb "$free_home") GB free in $HOME${free_c:+ and $(gb "$free_c") GB on C:}"
  fi

  if [ $in_wsl -eq 1 ]; then
    header memory 4 "WSL's memory"
    local total wslconfig="unknown (no Windows interop)" profile
    total=$(awk '/^MemTotal:/ { printf "%.1f", $2 * 1024 / 1e9 }' /proc/meminfo)
    if [ -n "$cmd_exe" ]; then
      profile=$(win_cmd /u /c "echo %USERPROFILE%" 2>/dev/null | iconv -f UTF-16LE -t UTF-8 2>/dev/null | tr -d '\r\n' || true)
      profile=$(wslpath -u "$profile" 2>/dev/null || true)
      if [ -z "$profile" ]; then wslconfig="unknown (%USERPROFILE% not found)"
      elif [ -f "$profile/.wslconfig" ]; then wslconfig="$profile/.wslconfig exists"
      else wslconfig="none yet"; fi
    fi
    echo "WSL has $total GB of memory; .wslconfig: $wslconfig"
    echo "after the downloads, WSL's memory is set to Windows' RAM less 4 GB (12 GB on a 16 GB PC), with 8 GB of swap"
  fi

  header plan 5 "What will be downloaded"
  local total_gb
  total_gb=$(awk -v a="$(packages_gb "$lane")" -v b=$REST_GB 'BEGIN { printf "%.1f", a + b }')
  echo "about $total_gb GB: the Python packages for lane $lane ($(packages_gb "$lane") GB), then Node, autochart and its models$([ "$lane" = cpu ] || echo ", the CUDA provider") and the pipeline's models (about $REST_GB GB)"
  awk -v g="$total_gb" 'BEGIN { printf "time: about %d min at 25 Mbit/s, %d min at 100 Mbit/s (less when an earlier run got part of it)\n", g * 8000 / 25 / 60 + 0.5, g * 8000 / 100 / 60 + 0.5 }'
  if [ $yes -ne 1 ]; then
    local answer=""
    printf 'Continue? [Y/n] '
    read -r answer || answer=""
    case $answer in [nN]*) echo "songcharter: stopped; nothing was downloaded."; exit 1 ;; esac
  fi

  header downloads 6 "uv, Python and the app"
  export UV_HTTP_TIMEOUT=300 UV_HTTP_RETRIES=5 UV_PYTHON_INSTALL_DIR="$runtime/python"
  if [ -x "$uv" ] && [ "$("$uv" --version 2>/dev/null | cut -d' ' -f2)" = "$UV_VERSION" ]; then
    echo "uv $UV_VERSION: already here"
  else
    download "$UV_URL" "$dl/uv.tar.gz" "$UV_SHA256"
    rm -rf "$dl/uv.x"
    mkdir -p "$dl/uv.x"
    tar -xzf "$dl/uv.tar.gz" -C "$dl/uv.x" --strip-components=1
    [ -x "$dl/uv.x/uv" ] || fail "uv's tarball holds no uv"
    mv -f "$dl/uv.x/uv" "$uv"
    rm -rf "$dl/uv.x" "$dl/uv.tar.gz"
    echo "uv: $("$uv" --version)"
  fi
  if [ -f "$app/.release-sha256" ] && [ "$(cat "$app/.release-sha256")" = "$APP_SHA256" ]; then
    echo "songcharter $VERSION: already here"
  else
    local tarball=songcharter-$VERSION.tar.gz
    asset "$tarball" "$dl/$tarball" "$APP_SHA256"
    rm -rf "$app.part"
    mkdir -p "$app.part"
    tar -xzf "$dl/$tarball" -C "$app.part" --strip-components=1
    echo "$APP_SHA256" >"$app.part/.release-sha256"
    rm -rf "$app"
    mv "$app.part" "$app"
    rm -f "$dl/$tarball"
    echo "songcharter $VERSION: in $app"
  fi
  for old in "$home/app"/*; do [ "$old" = "$app" ] || rm -rf -- "$old"; done
  "$uv" python install --no-bin "$PYTHON_VERSION" || fail "uv python install $PYTHON_VERSION exited $?"

  header environments 7 "The environments (uv sync)"
  sync_env "songcharter's environment" "$app" "$runtime/env" --no-editable --extra app
  sync_env "allin1's environment" "$app/packaging/allin1" "$runtime/allin1"

  header setup 8 "Node, scan-chart, autochart and the models"
  # -P: songcharter from the install's environment, never from a songcharter/ folder in the current one
  local code doctor_before
  doctor_before=$(stat -c %y "$home/doctor.json" 2>/dev/null || echo none)
  export PYTHONUNBUFFERED=1
  helper "python -m songcharter.runtime setup" "$py" -P -m songcharter.runtime setup --home "$home" --app "$app" \
    --lane "$lane" --lane-reason "$lane_reason"
  code=$helper_code
  # 1 is doctor's problems only when doctor.json is this run's (its mtime, to the nanosecond); else Python's own 1
  if [ "$code" -eq 1 ] && [ "$(stat -c %y "$home/doctor.json" 2>/dev/null || echo none)" = "$doctor_before" ]; then
    fail "python -m songcharter.runtime setup exited 1 before doctor ran (its error is above)"
  fi

  local flag=$state/restart-wsl
  rm -f "$flag"
  if [ $in_wsl -eq 1 ]; then
    header windows 9 "The Windows side: WSL's memory and the Start-menu shortcut"
    local args=(apply --home "$home" --launcher "$launcher" --restart-flag "$flag")
    if [ $yes -eq 1 ]; then args+=(--yes); fi
    if [ -n "$ram_gb" ]; then args+=(--windows-ram-gb "$ram_gb"); fi
    helper "python -m songcharter.wslsetup apply" "$py" -P -m songcharter.wslsetup "${args[@]}"
  fi

  header launcher 10 "The launcher"
  mkdir -p "$(dirname "$launcher")" "$state"
  printf '#!/bin/sh\nexec "%s" -P -m songcharter.launch "$@"\n' "$py" >"$launcher.part"
  chmod 755 "$launcher.part"
  mv -f "$launcher.part" "$launcher"
  printf 'version=%s\nlane=%s\n' "$VERSION" "$lane" >"$state/install.done.part"
  mv -f "$state/install.done.part" "$state/install.done"
  echo "launcher: $launcher"
  "$py" -P - "$home/doctor.json" <<'PY' || true
import json, sys
from songcharter import device
r = json.load(open(sys.argv[1], encoding="utf-8"))
print("\n".join(device.summary(r)))
n = len(r["problems"])
print("doctor: OK" if r["ok"] else f"doctor: {n} problem{'s' * (n != 1)}")
PY
  echo
  if [ -n "$before" ] && [ "$before" != "$lane" ]; then echo "lane changed: $before → $lane"; fi
  echo "songcharter $VERSION is installed (lane $lane: $lane_reason)."
  if [ $in_wsl -eq 1 ]; then echo "Start it from the Start menu (songcharter), or type songcharter in Ubuntu."
  else echo "Start it by typing songcharter."; fi
  case ":$PATH:" in
    *":$(dirname "$launcher"):"*) ;;
    *) echo "($(dirname "$launcher") is not on PATH in this window yet: open a new window first, or run $launcher.)" ;;
  esac
  if [ -f "$flag" ]; then
    rm -f "$flag"
    echo "WSL restarts now so the new memory setting takes effect. Then start songcharter from the Start menu."
    sleep 5   # time to read it: the shutdown closes this window
    win_cmd /c wsl.exe --shutdown || true
  fi
  trap - ERR
  exit "$code"   # 1 when doctor found problems (listed above)
}

# run unless sourced (the tests source it for its functions)
if ! (return 0 2>/dev/null); then
  main "$@"
fi
