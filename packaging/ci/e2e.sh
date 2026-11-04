#!/usr/bin/env bash
# e2e.sh (M4-05): what the friend does, from nothing, in an Ubuntu container: one phase per call, each started by
# linux.d/50-e2e.sh with `docker exec`, so the hook can cut the container's network between two phases from outside.
#
#   bash /ci/e2e.sh prepare        as root: the WSL image's tools (curl ca-certificates git xz-utils) and the user friend
#   bash /ci/e2e.sh PHASE          as friend, with HOME=/home/friend; PHASE, in the hook's order:
#     install        the install killed once its log shows the uv sync downloading, then run again: exit 0, the cpu
#                    lane with "no NVIDIA GPU found"; its times and the disk it takes (du -sh)
#     doctor         `songcharter doctor --json`: exit 0, wsl null, guitar_device cpu, components.allin1.ok true
#     doctor-gpu     the same with fake-nvidia-smi first on PATH as nvidia-smi: gpu.name NVIDIA GeForce RTX 4070, and
#                    device.reason "this install's torch has no CUDA (the cpu lane)"
#     doctor-quick   `songcharter doctor --quick` exits 0 (the older Ubuntus, after their install)
#     clip           make_clip.py's 30-s clip, charted on the CPU into "Jörg's Söngs/Clip": exit 0, check_gate.py
#                    passes; the stage times from pipeline.json
#     guards         ui_guards.py against `songcharter ui --no-browser --port 8799`, on a clip of its own (32 s), so
#                    its cache is cold and the guitar's take sends its `take` event: the clip phase's is cached
#     offline        (the hook has cut the network) the clip into a new folder, and a clip never charted (34 s) into
#                    another, so every stage runs offline too: each exits 0 and passes check_gate.py
#     uninstall-keep `songcharter uninstall` answering No, then the install again: exit 0, nothing downloaded (no fetch
#                    line, no uv download), under 3 minutes
#     uninstall-all  `songcharter uninstall` answering Yes: ~/.local/share/songcharter, ~/.cache/songcharter and the
#                    launcher are gone
#
# Each check is printed and timed ("-- <check>", then "-- <check>: ok in N s"); a failing one prints its log's last
# lines and exits 1. Everything the hook collects goes to ~/e2e/, outside the install, so it outlives the uninstall:
# logs/, doctor*.json, runtime.json, clip/ (report.json, pipeline.json, the preview's overview), ui-guards.json, and
# figures.txt (one `name=value` line per figure: the times and sizes the work order asks for). Never audio: the clips
# stay in ~/clips/. /dist holds the release assets (build.sh's), /ci packaging/ci.
set -euo pipefail

phase=${1:-}
if [ $# -ne 1 ]; then
  echo "usage: e2e.sh prepare|install|doctor|doctor-gpu|doctor-quick|clip|guards|offline|uninstall-keep|uninstall-all" >&2
  exit 2
fi

home=$HOME/.local/share/songcharter
py=$home/runtime/env/bin/python
launcher=$HOME/.local/bin/songcharter
songs="$HOME/Jörg's Söngs"   # a Songs folder with non-ASCII letters, an apostrophe and a space
clips=$HOME/clips
e2e=$HOME/e2e
logs=$e2e/logs
export PATH="$HOME/.local/bin:$PATH"
CPU_LANE="this install's torch has no CUDA (the cpu lane)"   # songcharter.device.CPU_LANE
GPU_NAME="NVIDIA GeForce RTX 4070"                          # fake-nvidia-smi's

current="e2e.sh $phase"
trap 'code=$?; if [ $code -ne 0 ]; then echo "-- $current: FAILED (exit $code)"; fi' EXIT

die() { echo "e2e: $*" >&2; exit 1; }

check() {   # NAME COMMAND...: one check, printed and timed
  local name=$1 start=$SECONDS
  shift
  current=$name
  echo "-- $name"
  "$@"
  echo "-- $name: ok in $((SECONDS - start)) s"
  current="e2e.sh $phase"
}

logged() {   # LOG COMMAND...: COMMAND's output into LOG; when it fails, LOG's last lines and its exit status
  local log=$1 code=0
  shift
  "$@" >"$log" 2>&1 || code=$?
  if [ $code -ne 0 ]; then
    echo "e2e: $* exited $code; the last lines of $log:"
    tail -n 40 "$log"
  fi
  return $code
}

figure() {   # NAME VALUE: a figure for the report, printed and kept in figures.txt
  echo "figure: $1=$2"
  printf '%s=%s\n' "$1" "$2" >>"$e2e/figures.txt"
}

json_check() {   # FILE PYTHON-EXPRESSIONS...: each must be true of the JSON in FILE (bound to r), else exit 1
  "$py" - "$@" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
bad = []
for expr in sys.argv[2:]:
    try:
        ok = eval(expr, {}, {"r": r})
    except Exception as e:  # noqa: BLE001  a missing key is a failed check
        ok, expr = False, f"{expr} ({type(e).__name__}: {e})"
    print(f"  {'ok' if ok else 'FAIL'}: {expr}")
    bad += [] if ok else [expr]
sys.exit(1 if bad else 0)
PY
}

clip() {   # PATH SECONDS: make_clip.py's clip, made by the installed Python
  mkdir -p "$(dirname "$1")"
  "$py" /ci/make_clip.py "$1" "$2"
}

chart() {   # CLIP SONG-FOLDER LOG: `songcharter chart` on the CPU, then check_gate.py
  logged "$3" songcharter chart "$1" --out "$2" --device cpu
  "$py" /ci/check_gate.py "$2"
}

stages() {   # LOG DEST: the chart whose log is LOG: its stage times from pipeline.json, which goes to DEST/ with the song
  # folder's report.json and the preview's overview (a PNG)
  "$py" - "$1" "$2" <<'PY'
import json, re, shutil, sys
from pathlib import Path
log, dest = Path(sys.argv[1]), Path(sys.argv[2])
text = log.read_text(encoding="utf-8", errors="replace")
work = re.search(r"^work folder: (.+?) \(", text, re.M)
folder = re.search(r"^song folder: (.+)$", text, re.M)
if not work or not folder:
    sys.exit(f"e2e: no 'work folder:' or 'song folder:' line in {log}")
work, folder = Path(work.group(1)), Path(folder.group(1))
p = json.loads((work / "pipeline.json").read_text(encoding="utf-8"))
dest.mkdir(parents=True, exist_ok=True)
shutil.copyfile(work / "pipeline.json", dest / "pipeline.json")
shutil.copyfile(folder / "report.json", dest / "report.json")
overview = (p.get("preview") or {}).get("overview")
if overview and Path(overview).is_file():
    shutil.copyfile(overview, dest / Path(overview).name)
print("stage times: " + ", ".join(f"{s['stage']} {s['seconds']:.1f} s{' (cached)' if s.get('cached') else ''}"
                                  for s in p["stages"]) + f"; total {p.get('total_seconds')} s")
PY
}

no_download() {   # LOG: the install's log shows no download: no fetch line (runtime.py's), none of uv's, none of its own
  local found=0
  if grep -nE "^fetch " "$1"; then echo "e2e: fetch downloaded"; found=1; fi
  if grep -nE "Download(ing|ed) " "$1"; then echo "e2e: uv downloaded"; found=1; fi
  if grep -nE "^downloading " "$1"; then echo "e2e: install.sh downloaded"; found=1; fi
  [ $found -eq 0 ] || exit 1
  echo "nothing downloaded"
}

# ------------------------------------------------------------------------------------------------ the phases

prepare() {   # as root
  [ "$(id -u)" -eq 0 ] || die "prepare runs as root"
  grep -m1 PRETTY_NAME /etc/os-release
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq curl ca-certificates git xz-utils >/dev/null
  id friend >/dev/null 2>&1 || useradd -m friend
  echo "friend: $(id friend)"
}

install_killed() {
  local log=$logs/install-1.log start=$SECONDS pid killed=0 code=0
  setsid bash /dist/install.sh --from /dist --lane auto --yes >"$log" 2>&1 &
  pid=$!
  for _ in $(seq 1 4800); do   # 20 min
    if awk '/^== \[7\/10\]/ { s = 1 } s && /Downloading/ { f = 1 } END { exit !f }' "$log"; then
      kill -TERM -- "-$pid"
      killed=1
      break
    fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
  wait "$pid" || code=$?
  tail -n 3 "$log"
  [ $killed -eq 1 ] || die "the install never showed a download in its uv sync (exit $code)"
  [ $code -ne 0 ] || die "the killed install exited 0"
  tail -n 1 "$log" | grep -q "failed: .*Run the same command again to continue.$" ||
    die "the killed install's last line is not the failure line"
  figure install_killed_after_s $((SECONDS - start))
}

install_again() {
  local start=$SECONDS
  logged "$logs/install-2.log" bash /dist/install.sh --from /dist --lane auto --yes
  figure install_rerun_s $((SECONDS - start))
  tail -n 4 "$logs/install-2.log"
  cp "$home/runtime/runtime.json" "$e2e/runtime.json"
  json_check "$home/runtime/runtime.json" 'r["lane"] == "cpu"' '"no NVIDIA GPU found" in r["lane_reason"]'
  local p size
  for p in "$home" "$HOME/.cache/uv" "$HOME/.cache/songcharter"; do
    size=$(du -sh -- "$p" | cut -f1)
    echo "du -sh $p: $size"
    figure "du_${p#"$HOME/"}" "$size"
  done
  size=$(du -shc -- "$home" "$HOME/.cache/uv" "$HOME/.cache/songcharter" | tail -n 1 | cut -f1)
  figure du_all_three_hardlinks_once "$size"
}

phase_install() {
  rm -rf "$e2e"
  mkdir -p "$logs"
  local start=$SECONDS
  check "the install, killed during its uv sync" install_killed
  check "the install again" install_again
  figure install_total_s $((SECONDS - start))
}

doctor_cpu() {
  logged "$logs/doctor.log" songcharter doctor --json /tmp/d.json
  cat "$logs/doctor.log"
  cp /tmp/d.json "$e2e/doctor.json"
  json_check /tmp/d.json 'r["wsl"] is None' 'r["guitar_device"] == "cpu"' 'r["components"]["allin1"]["ok"] is True'
}

doctor_gpu() {
  mkdir -p "$HOME/fakebin"
  cp /ci/fake-nvidia-smi "$HOME/fakebin/nvidia-smi"
  chmod 755 "$HOME/fakebin/nvidia-smi"
  echo "nvidia-smi: $(PATH="$HOME/fakebin:$PATH" command -v nvidia-smi)"
  PATH="$HOME/fakebin:$PATH" logged "$logs/doctor-gpu.log" songcharter doctor --json /tmp/d-gpu.json
  cat "$logs/doctor-gpu.log"
  cp /tmp/d-gpu.json "$e2e/doctor-gpu.json"
  json_check /tmp/d-gpu.json "r['gpu']['name'] == '$GPU_NAME'" "r['device']['reason'] == \"$CPU_LANE\""
}

doctor_quick() {
  logged "$logs/doctor-quick.log" songcharter doctor --quick
  cat "$logs/doctor-quick.log"
}

phase_clip() {
  check "make_clip.py's 30-s clip" clip "$clips/clip.wav" 30
  mkdir -p "$songs"
  local start=$SECONDS
  check "the clip, charted into $songs/Clip" chart "$clips/clip.wav" "$songs/Clip" "$logs/clip.log"
  figure clip_chart_s $((SECONDS - start))
  check "the clip's stage times" stages "$logs/clip.log" "$e2e/clip"
}

guards() {
  local code=0
  "$py" /ci/ui_guards.py --cmd "songcharter ui --no-browser --port 8799" --clip "$clips/Söng for the page.wav" \
    --server-log "$logs/ui-server.log" --report "$e2e/ui-guards.json" || code=$?
  mkdir -p "$logs/ui"
  cp "$home"/logs/*.log "$logs/ui/" 2>/dev/null || true
  return $code
}

phase_guards() {
  check "a clip of its own for the page (32 s, a cold cache)" clip "$clips/Söng for the page.wav" 32
  local start=$SECONDS
  check "the page: guards, cancel at the first take, the same job again, SIGTERM" guards
  figure guards_s $((SECONDS - start))
}

no_network() {
  if curl -sS --max-time 15 -o /dev/null https://pypi.org/simple/ 2>"$logs/offline-curl.log"; then
    die "curl reached https://pypi.org: the network is not cut"
  fi
  echo "no network: $(head -c 200 "$logs/offline-curl.log")"
}

phase_offline() {
  check "the network is cut" no_network
  local start=$SECONDS
  check "the clip, offline, into $songs/Clip offline" chart "$clips/clip.wav" "$songs/Clip offline" \
    "$logs/offline.log"
  figure offline_chart_s $((SECONDS - start))
  check "its stage times" stages "$logs/offline.log" "$e2e/offline"
  check "a clip never charted (34 s)" clip "$clips/new clip.wav" 34
  start=$SECONDS
  check "the new clip, offline, into $songs/New clip offline" chart "$clips/new clip.wav" "$songs/New clip offline" \
    "$logs/offline-new.log"
  figure offline_new_chart_s $((SECONDS - start))
  check "its stage times (none cached)" stages "$logs/offline-new.log" "$e2e/offline-new"
}

uninstall_keep() {
  printf 'n\n' | logged "$logs/uninstall-keep.log" songcharter uninstall
  cat "$logs/uninstall-keep.log"
  [ ! -e "$launcher" ] || die "the launcher is still there"
  [ ! -e "$home/app" ] || die "$home/app is still there"
  [ -d "$home/runtime/env" ] || die "No deleted $home/runtime/env"
}

reinstall() {
  local start=$SECONDS took
  logged "$logs/install-3.log" bash /dist/install.sh --from /dist --lane auto --yes
  took=$((SECONDS - start))
  figure reinstall_s $took
  tail -n 2 "$logs/install-3.log"
  no_download "$logs/install-3.log"
  [ $took -lt 180 ] || die "the reinstall took $took s, not under 3 minutes"
}

uninstall_all() {
  printf 'y\n' | logged "$logs/uninstall-all.log" songcharter uninstall
  cat "$logs/uninstall-all.log"
  local gone left=0
  for gone in "$home" "$HOME/.cache/songcharter" "$launcher"; do
    if [ -e "$gone" ]; then echo "e2e: $gone is still there"; left=1; else echo "gone: $gone"; fi
  done
  [ -e "$HOME/.cache/uv" ] && echo "(uv's cache $HOME/.cache/uv is still there)" || echo "gone too: $HOME/.cache/uv"
  [ $left -eq 0 ] || exit 1
}

case $phase in
  prepare) prepare ;;
  install) phase_install ;;
  doctor) check "doctor" doctor_cpu ;;
  doctor-gpu) check "doctor with a GPU on PATH (fake-nvidia-smi)" doctor_gpu ;;
  doctor-quick) check "doctor --quick" doctor_quick ;;
  clip) phase_clip ;;
  guards) phase_guards ;;
  offline) phase_offline ;;
  uninstall-keep)
    check "uninstall, keeping the downloads" uninstall_keep
    check "the install again, with nothing to download" reinstall
    ;;
  uninstall-all) check "uninstall, deleting everything" uninstall_all ;;
  *) echo "e2e.sh: unknown phase $phase" >&2; exit 2 ;;
esac
