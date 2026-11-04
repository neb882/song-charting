#!/usr/bin/env bash
# e2e.sh (M4-05): what the friend does, from nothing, in an Ubuntu container: one phase per call, each started by
# linux.d/50-e2e.sh with `docker exec`, so the hook can cut the container's network between two phases from outside.
#
#   bash /ci/e2e.sh prepare        as root: the WSL image's tools (curl ca-certificates git xz-utils) and the user friend
#   bash /ci/e2e.sh PHASE          as friend, with HOME=/home/friend; PHASE, in the hook's order:
#     install        the install killed once its log shows the uv sync downloading; run again and killed in step 8
#                    in the middle of a download (the first `fetch` progress line with 100 MB or more still to come);
#                    then run again: it resumes that download (`resuming at`), exits 0, and has the cpu lane with "no
#                    NVIDIA GPU found"; its times and the disk it takes (du -sh). Before it, the entries of ~ to depth
#                    3 are listed (home-before.txt, for uninstall-all)
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
#     uninstall-keep (the network still cut) `songcharter uninstall` answering No: the launcher and the app go, and
#                    runtime/env, the pipeline's models (~/.cache/songcharter/models) and uv's cache stay, each file of
#                    the last two still there; then the install again, offline, so any download fails it: exit 0, no
#                    download line either, under 3 minutes
#     uninstall-all  `songcharter uninstall` answering Yes: ~/.local/share/songcharter, ~/.cache/songcharter and the
#                    launcher are gone, and nothing the install or a chart made stays in ~: no entry to depth 3 that the
#                    install phase's snapshot did not list, but for e2e's own (~/e2e, ~/clips, the Songs folder,
#                    ~/fakebin) and the XDG base folders themselves (~/.cache, ~/.config, ~/.local and the three in it),
#                    which are not songcharter's; what is in them counts
#
# Each check is printed and timed ("-- <check>", then "-- <check>: ok in N s"); a failing one prints its log's last
# lines, then "-- <check>: FAILED (exit N)", and the phase exits non-zero. Everything the hook collects goes to
# ~/e2e/, outside the install, so it outlives the uninstall: logs/, doctor*.json, runtime.json, clip/ (report.json,
# pipeline.json, the preview's overview), ui-guards.json, home-before.txt, and figures.txt (one `name=value` line per
# figure: the times and sizes the work order asks for). Never audio: the clips stay in ~/clips/. /dist holds the
# release assets (build.sh's), /ci packaging/ci.
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

interrupted() {   # LOG FIGURE AWK: the install into LOG, its session killed (TERM) as soon as the awk program AWK, run
  # on LOG every 50 ms, exits 0 (it prints the line it found); then it must end non-zero with its failure line
  local log=$1 name=$2 trigger=$3 start=$SECONDS pid hit="" killed=0 code=0
  setsid bash /dist/install.sh --from /dist --lane auto --yes >"$log" 2>&1 &
  pid=$!
  for _ in $(seq 1 24000); do   # 20 min
    if hit=$(awk "$trigger" "$log"); then
      kill -TERM -- "-$pid" 2>/dev/null && killed=1   # not when it has just ended by itself: then it was not killed
      break
    fi
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.05
  done
  wait "$pid" || code=$?
  [ $killed -eq 1 ] || { tail -n 5 "$log"; die "the install was never killed: it ended first (exit $code)"; }
  echo "killed at: $hit"
  tail -n 2 "$log"
  [ $code -ne 0 ] || die "the killed install exited 0"
  tail -n 1 "$log" | grep -q "failed: .*Run the same command again to continue.$" ||
    die "the killed install's last line is not the failure line"
  figure "$name" $((SECONDS - start))
}

killed_in_sync() {   # the first `Downloading` of uv's sync (step 7)
  interrupted "$logs/install-1.log" install_killed_in_sync_after_s \
    '/^== \[7\/10\]/ { s = 1 } s && /Downloading/ { print; f = 1; exit } END { exit !f }'
}

killed_in_fetch() {   # step 8: the first progress line of runtime.py's fetch ("fetch NAME: DONE of TOTAL MB, RATE MB/s")
  # with 100 MB or more still to come, so the kill lands in the middle of that file even at a runner's 200 MB/s
  interrupted "$logs/install-2.log" install_killed_in_fetch_after_s \
    '/^== \[8\/10\]/ { s = 1 }
     s && /^fetch [^ ]+: [0-9]+ of [0-9]+ MB, / { split($0, w, " "); if (w[5] - w[3] >= 100) { print; f = 1; exit } }
     END { exit !f }'
  local parts
  parts=$(find "$home/runtime" -name "*.part" -printf "%P (%s bytes)\n")
  [ -n "$parts" ] || die "no .part file is left: the kill came after the download had finished"
  echo "left to resume: $parts"
}

install_again() {
  local start=$SECONDS
  logged "$logs/install-3.log" bash /dist/install.sh --from /dist --lane auto --yes
  figure install_resumed_s $((SECONDS - start))
  grep -n "resuming at" "$logs/install-3.log" || die "the rerun resumed no download (no 'resuming at' line)"
  tail -n 4 "$logs/install-3.log"
  cp "$home/runtime/runtime.json" "$e2e/runtime.json"
  json_check "$home/runtime/runtime.json" 'r["lane"] == "cpu"' '"no NVIDIA GPU found" in r["lane_reason"]'
  local p size name
  for p in "$home:du_home" "$HOME/.cache/uv:du_uv_cache" "$HOME/.cache/songcharter:du_songcharter_cache"; do
    name=${p##*:}
    p=${p%:*}
    size=$(du -sh -- "$p" | cut -f1)
    echo "du -sh $p: $size"
    figure "$name" "$size"   # each on its own: what the environments hardlink from uv's cache counts in both
  done
  size=$(du -shc -- "$home" "$HOME/.cache/uv" "$HOME/.cache/songcharter" | tail -n 1 | cut -f1)
  figure du_all_three "$size"   # one du: a file hardlinked between them counts once
}

home_entries() {   # the entries of ~ to depth 3, one per line, sorted bytewise
  find "$HOME" -mindepth 1 -maxdepth 3 | LC_ALL=C sort
}

phase_install() {
  rm -rf "$e2e"
  mkdir -p "$logs"
  home_entries >"$e2e/home-before.txt"
  local start=$SECONDS
  check "the install, killed during its uv sync" killed_in_sync
  check "the install again, killed in the middle of a step-8 download" killed_in_fetch
  check "the install again, resuming that download" install_again
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

files_of() {   # FOLDER: each file under it with its size, sorted (empty when the folder is gone)
  if [ -d "$1" ]; then find "$1" -type f -printf "%P %s\n" | LC_ALL=C sort; fi
}

uninstall_keep() {
  local models=$HOME/.cache/songcharter/models uv_cache=$HOME/.cache/uv
  files_of "$models" >/tmp/models-before.txt
  files_of "$uv_cache" >/tmp/uv-before.txt
  echo "before: $(wc -l </tmp/models-before.txt) files in $models, $(wc -l </tmp/uv-before.txt) in $uv_cache"
  [ -s /tmp/models-before.txt ] && [ -s /tmp/uv-before.txt ] || die "no models or no uv cache to keep"
  printf 'n\n' | logged "$logs/uninstall-keep.log" songcharter uninstall
  cat "$logs/uninstall-keep.log"
  [ ! -e "$launcher" ] || die "the launcher is still there"
  [ ! -e "$home/app" ] || die "$home/app is still there"
  [ -d "$home/runtime/env" ] || die "No deleted $home/runtime/env"
  local what before after
  for what in "models:$models" "uv:$uv_cache"; do
    before=/tmp/${what%%:*}-before.txt after=/tmp/${what%%:*}-after.txt
    files_of "${what#*:}" >"$after"
    if ! cmp -s "$before" "$after"; then
      echo "e2e: No changed ${what#*:} (- before, + after):"
      diff "$before" "$after" | head -n 20 || true
      exit 1
    fi
    echo "kept: ${what#*:} ($(wc -l <"$after") files, each as it was)"
  done
}

reinstall() {   # the network is still cut: any download fails it
  local start=$SECONDS took
  logged "$logs/reinstall.log" bash /dist/install.sh --from /dist --lane auto --yes
  took=$((SECONDS - start))
  figure reinstall_offline_s $took
  tail -n 2 "$logs/reinstall.log"
  no_download "$logs/reinstall.log"
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

nothing_left() {   # no entry of ~ to depth 3 that was not there before the install, but for e2e's own and the XDG
  # base folders themselves (not songcharter's to delete; what is in them is listed on its own, and counts)
  local entry left=()
  while IFS= read -r entry; do
    case $entry in
      "$e2e" | "$e2e"/* | "$clips" | "$clips"/* | "$songs" | "$songs"/* | "$HOME/fakebin" | "$HOME/fakebin"/*) ;;
      "$HOME/.cache" | "$HOME/.config" | "$HOME/.local" | "$HOME/.local/bin" | "$HOME/.local/share" | \
        "$HOME/.local/state") ;;
      *) left+=("$entry") ;;
    esac
  done < <(LC_ALL=C comm -13 "$e2e/home-before.txt" <(home_entries))
  if [ ${#left[@]} -ne 0 ]; then
    echo "e2e: left in ~ after uninstalling everything (not there before the install):"
    for entry in "${left[@]}"; do echo "  $entry ($(du -sh -- "$entry" | cut -f1))"; done
    exit 1
  fi
  echo "nothing new left in ~ (to depth 3), but e2e's own folders and the XDG base folders"
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
    check "the network is still cut" no_network
    check "uninstall, keeping the downloads" uninstall_keep
    check "the install again, offline, with nothing to download" reinstall
    ;;
  uninstall-all)
    check "uninstall, deleting everything" uninstall_all
    check "nothing the install or a chart made is left in ~" nothing_left
    ;;
  *) echo "e2e.sh: unknown phase $phase" >&2; exit 2 ;;
esac
