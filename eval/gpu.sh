#!/usr/bin/env bash
# gpu.sh: run the comparison on an NVIDIA GPU as a standalone job, the way Overclock's `render.ts video` runs: you
# start it in your own terminal, and no Claude session has to stay connected while it works.
#   eval/gpu.sh check     the GPU, CUDA inside each tool, and the memory WSL sees; fails if a tool would fall back to CPU
#   eval/gpu.sh start     check, then run drive.sh detached: it survives closing the terminal and a Claude crash
#   eval/gpu.sh status    running or not, the latest driver.log lines, GPU and memory now
#   eval/gpu.sh stop      stop the run; finished jobs are kept, and `start` carries on from there
#   eval/gpu.sh takes [SET ...]   check, then run eval/takes.py detached for each set in turn (refs, the default;
#                         stress; set20): 4 autochart Expert takes of every song (no scoring), then `results`
#   eval/gpu.sh build SET [TEST_SONG]   build a set's eval data (eval/build_refs.sh; the 20-song set's in SET20_DATA)
#   eval/gpu.sh thin-spike AUDIO...   (--app: check the app's autochart first) then run eval/spike/thin_spike.sh
#                         detached on each file in turn: Expert takes under several engine settings (M6's spike on fast
#                         runs; its header has the settings); $RUNS/thin_spike/thin_spike_results.zip to send back
#   eval/gpu.sh results   zip the scores, the test-song charts and every set's takes to send back: structured files
#                         only (no log, no audio), the 20-song set's songs by their labels, checked by a guard
# --app (check, takes, build, thin-spike; or SONGCHARTER_APP=1): the installed songcharter's Python, Node, scan-chart,
#      ffmpeg and autochart (SONGCHARTER_HOME, default ~/.local/share/songcharter) in place of eval/.venv and
#      eval/tools; the check is then autochart's only (eval/README.md, GPU takes with the installed app).
# Env: TOOLS (default "autochart chartgen strum", so STRUM's long test song runs last), SKIP (e.g. "strum:test_song"),
#      MEM_WAIT_MB (default 4000), EVAL_DATA, EVAL_PY, SET20_DATA (default $EVAL_DATA/set20), SEEDS, SONGS (ids or
#      labels, for one set), WINDOWS_PROFILE (the Windows profile results writes %USERPROFILE%; default Windows'
#      own), ALLOW_CPU=1 (start even if the check fails), and thin_spike.sh's ARMS, SEEDS and AC_DEVICE.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${EVAL_DATA:-$HERE/data}"
RUNS="$DATA/runs"
PIDFILE="$RUNS/gpu_run.pid"
T="$HERE/tools"
APP_HOME="${SONGCHARTER_HOME:-$HOME/.local/share/songcharter}"
APP="${SONGCHARTER_APP:-0}"   # 1: --app
NO_AUDIO="$HERE/../packaging/ci/check_no_audio.py"
DRIVER_RE='^(/[^ ]*/)?bash [^ ]*drive\.sh'   # a running driver itself, not a command line that mentions it

mem_mb() { awk -v k="$1:" '$1 == k {print int($2/1024)}' /proc/meminfo; }
# TEXT with the home folder written ~: every path printed, so a line pasted back carries no user name
tilde() { local text=$1 t='~'; if [ -n "${HOME:-}" ] && [ "$HOME" != / ]; then text=${text//"$HOME"/$t}; fi; printf '%s' "$text"; }
tilde_lines() { local line; while IFS= read -r line || [ -n "$line" ]; do tilde "$line"; echo; done; }

# onnxruntime-node's CUDA provider needs cuDNN 9 (libcudnn.so.9) and the CUDA 12 libraries. WSL's driver gives libcuda
# (/usr/lib/wsl/lib); the CUDA toolkit, if installed, gives the CUDA 12 libraries (/usr/local/cuda/lib64); cuDNN comes
# from a pip wheel: autochart's own tools/autochart/cudnn_venv first (kept apart from the torch tools on purpose),
# else a tool's or conda's nvidia-cudnn wheel. This prints the folders to prepend to LD_LIBRARY_PATH for autochart
# only, and fails when no cuDNN 9 is found.
# That CUDA 12 path predates a later finding: the provider of onnxruntime-node 1.27.0 (autochart's lock) needs CUDA 13
# (libcublas.so.13, libcudart.so.13, libnvrtc.so.13, libcufft.so.12, libcurand.so.10) and cuDNN 9, so the runs made
# with this path are no evidence for it (docs/work-orders/M4-00-plan.md, finding 4). M4-00b's spike
# (packaging/spike/cuda13-provider.sh) checks the CUDA 13 path, the cu132 torch lane's wheels plus nvidia-curand;
# songcharter itself gives autochart's node that path (engines/autochart.py, cuda_library_path).
cuda_libs() {
  local dirs=() c d
  if ! ldconfig -p 2>/dev/null | grep -q 'libcudnn\.so\.9 '; then
    c=
    for d in "$T"/autochart/cudnn_venv/lib/python3*/site-packages/nvidia/cudnn/lib \
             "$T"/strum/venv/lib/python3*/site-packages/nvidia/cudnn/lib \
             "$T"/chartgen/venv/lib/python3*/site-packages/nvidia/cudnn/lib \
             "$HOME"/miniconda3/lib/python3*/site-packages/nvidia/cudnn/lib; do   # in this order (ls would sort)
      ls "$d"/libcudnn.so.9* >/dev/null 2>&1 && { c=$d; break; }
    done
    [ -n "$c" ] || return 1
    dirs+=("$c")
    # without a CUDA toolkit, the same wheel set's other nvidia libraries (cublas, cudart, ...) are needed too
    [ -d /usr/local/cuda/lib64 ] || dirs+=($(ls -d "$(dirname "$(dirname "$c")")"/*/lib))
  fi
  for c in /usr/local/cuda/lib64 /usr/lib/wsl/lib; do [ -d "$c" ] && dirs+=("$c"); done
  (IFS=:; echo "${dirs[*]}")
}
running() { [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

# --app: the installed songcharter's tools for the eval scripts, from its runtime.json: its Python as EVAL_PY (unless
# set), its Node first on PATH and its scan-chart (build_ref.py runs `node` and scan.cjs), and `ffmpeg` on PATH: the
# system's when there is one, else the app's (imageio-ffmpeg's), linked as $DATA/bin/ffmpeg. takes.py --app takes
# autochart and the rest of the launcher's environment from the same runtime.json itself; the thin spike, which runs
# the driver itself, gets the app's autochart and ffmpeg as APP_AUTOCHART and APP_FFMPEG (not exported).
app_env() {
  local py="$APP_HOME/runtime/env/bin/python" record="$APP_HOME/runtime/runtime.json" vals node scan ff ac
  if [ ! -x "$py" ] || [ ! -f "$record" ]; then
    echo "no installed songcharter at $(tilde "$APP_HOME") (runtime/env/bin/python, runtime/runtime.json): install it, or set SONGCHARTER_HOME"
    return 1
  fi
  vals=$("$py" -I -c 'import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
print(r.get("node") or "", r.get("scan_chart") or "", r.get("ffmpeg") or "", r.get("autochart") or "", sep="\n")' "$record") || return 1
  { read -r node; read -r scan; read -r ff; read -r ac; } <<< "$vals"
  APP_AUTOCHART=${ac:-$APP_HOME/runtime/autochart} APP_FFMPEG=$ff
  export EVAL_PY="${EVAL_PY:-$py}"
  if [ -n "$node" ]; then export PATH="$(dirname "$node"):$PATH"; fi
  if [ -n "$scan" ]; then export SONGCHARTER_SCAN_CHART="${SONGCHARTER_SCAN_CHART:-$scan}"; fi
  if ! command -v ffmpeg >/dev/null && [ -n "$ff" ]; then
    mkdir -p "$DATA/bin" && ln -sf "$ff" "$DATA/bin/ffmpeg" && export PATH="$DATA/bin:$PATH"
  fi
}

# Imports torch in a tool's venv and runs one matmul on the GPU, so a CPU-only build or a missing kernel shows up here
# rather than an hour into a run.
TORCH_CHECK='
import torch
if not torch.cuda.is_available():
    raise SystemExit(f"torch {torch.__version__}: CUDA not available (a CPU-only build, or the driver is not visible)")
cap = torch.cuda.get_device_capability(0)
arch = f"sm_{cap[0]}{cap[1]}"
try:
    x = torch.randn(512, 512, device="cuda"); (x @ x).sum().item()
except Exception as e:
    raise SystemExit(f"torch {torch.__version__}: a GPU op failed ({str(e).splitlines()[0]}); reinstall with TORCH_INDEX=https://download.pytorch.org/whl/cu128")
listed = "" if arch in torch.cuda.get_arch_list() else ", not in the build (running through PTX)"
print(f"ok: torch {torch.__version__}, CUDA {torch.version.cuda}, {torch.cuda.get_device_name(0)} ({arch}{listed})")
'

check() {   # [SET ...]: the reference set must be built only for refs (the default)
  local bad=0
  echo "== GPU"
  if command -v nvidia-smi >/dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv,noheader
  else
    echo "nvidia-smi not found: no NVIDIA driver is visible (in WSL, install or update the Windows NVIDIA driver)"; bad=1
  fi
  if [ "$APP" = 1 ]; then
    echo "== the installed app's autochart (the takes need no strum or chartgen)"
    if app_env; then "$EVAL_PY" "$HERE/takes.py" --app --check --device cuda || bad=1; else bad=1; fi
    check_memory || bad=1
    case " ${*:-refs} " in *" refs "*) [ -f "$DATA/refs/songs.json" ] || { echo "no reference set: build it first (eval/gpu.sh build --app refs TEST_SONG)"; bad=1; } ;; esac
    return $bad
  fi
  echo "== CUDA inside each tool"
  for tool in strum chartgen; do
    local py="$T/$tool/venv/bin/python"
    if [ ! -x "$py" ]; then echo "$tool: not installed (run $(tilde "$T/$tool/setup.sh") with TORCH_INDEX=.../cu128)"; bad=1; continue; fi
    local out; out=$(cd /tmp && "$py" -I -c "$TORCH_CHECK" 2>&1) || bad=1
    echo "$tool: $(tilde "$(echo "$out" | tail -n 1)")"
  done
  if [ -d "$T/autochart/node_modules/onnxruntime-node" ]; then
    if find "$T/autochart/node_modules/onnxruntime-node" -name 'libonnxruntime_providers_cuda.so*' | grep -q .; then
      echo "autochart: ok: onnxruntime-node has its CUDA provider (each run's log names the device it used)"
      local libs
      if libs=$(cuda_libs); then
        echo "autochart: CUDA libraries for its runs: $(tilde "$libs")"
      else
        echo "autochart: no cuDNN 9 (libcudnn.so.9) on the system or in a tool venv: its CUDA provider would fail to load"; bad=1
      fi
    else
      echo "autochart: onnxruntime-node has no CUDA provider, so it would run on CPU (reinstall with ONNXRUNTIME_NODE_INSTALL_CUDA=v12)"; bad=1
    fi
  else
    echo "autochart: not installed (run $(tilde "$T/autochart/setup.sh"))"; bad=1
  fi
  check_memory
  case " ${*:-refs} " in *" refs "*) [ -f "$DATA/refs/songs.json" ] || { echo "no reference set: run eval/build_refs.sh first"; bad=1; } ;; esac
  return $bad
}

check_memory() {   # warnings only
  echo "== memory (as WSL sees it)"
  local total swap
  total=$(mem_mb MemTotal); swap=$(mem_mb SwapTotal)
  echo "RAM ${total} MB, $(mem_mb MemAvailable) MB available; swap ${swap} MB"
  if [ "$total" -lt 15000 ]; then
    echo "warning: WSL has less than 15 GB. By default it gets half of Windows' RAM. STRUM and chartgen on a 7-minute song"
    echo "         can run out, and the kernel then kills processes (this job first, see oom_score_adj below). To give WSL"
    echo "         more, see 'Memory' in eval/README.md."
  fi
}

_run() {
  echo $$ > "$PIDFILE"
  # If memory runs out, the kernel should kill this job (it resumes), not Claude or Remote Control. Raising your own
  # oom_score_adj needs no privileges; every child inherits it.
  echo 500 > /proc/self/oom_score_adj 2>/dev/null || true
  local dev=cuda; command -v nvidia-smi >/dev/null || dev=cpu
  echo "$(date '+%F %T') gpu run started (devices: $dev)"
  local sampler=
  if [ $dev = cuda ]; then
    nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw --format=csv,noheader -l 5 \
      >> "$RUNS/gpu_samples.csv" 2>/dev/null &
    sampler=$!
  fi
  AC_DEVICE=$dev STRUM_DEVICE=$dev MEM_WAIT_MB="${MEM_WAIT_MB:-4000}" TOOLS="${TOOLS:-autochart chartgen strum}" \
    SKIP="${SKIP:-}" "$HERE/drive.sh"
  local rc=$?
  [ -n "$sampler" ] && kill "$sampler" 2>/dev/null
  results
  echo "$(date '+%F %T') gpu run finished (drive.sh exit $rc)"
  rm -f "$PIDFILE"
}

_takes() {   # SET ...: takes.py for each set in turn, then results
  echo $$ > "$PIDFILE"
  echo 500 > /proc/self/oom_score_adj 2>/dev/null || true
  echo "$(date '+%F %T') takes run started (sets: $*$([ "$APP" = 1 ] && echo ', the installed app'))"
  local py libs rc=0 s app=() sampler=
  if [ "$APP" = 1 ]; then
    # the CUDA libraries come from the app's own Python (songcharter.engines.autochart), not from cuda_libs
    app_env || { rm -f "$PIDFILE"; return 2; }
    py=$EVAL_PY
    app=(--app)
  else
    py="${EVAL_PY:-$HERE/.venv/bin/python}"
    libs=$(cuda_libs) && [ -n "$libs" ] && export LD_LIBRARY_PATH="$libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    echo "LD_LIBRARY_PATH=$(tilde "${LD_LIBRARY_PATH:-}")"
  fi
  if command -v nvidia-smi >/dev/null; then
    nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,power.draw --format=csv,noheader -l 5 \
      >> "$RUNS/gpu_samples.csv" 2>/dev/null &
    sampler=$!
  fi
  for s in "$@"; do
    EVAL_DATA="$DATA" "$py" "$HERE/takes.py" --set "$s" ${app[@]+"${app[@]}"} --device cuda ${SEEDS:+--seeds "$SEEDS"} \
      ${SONGS:+--songs "$SONGS"} || rc=$?
  done
  [ -n "$sampler" ] && kill "$sampler" 2>/dev/null
  results
  echo "$(date '+%F %T') takes run finished (exit $rc)"
  rm -f "$PIDFILE"
}

takes() {   # [SET ...]
  [ $# -gt 0 ] || set -- refs
  local s py
  for s in "$@"; do
    case "$s" in refs|stress|set20) ;; *) echo "eval/gpu.sh takes: a set is refs, stress or set20, not '$s'"; exit 2 ;; esac
  done
  if running; then echo "already running (pid $(cat "$PIDFILE")): eval/gpu.sh status"; exit 1; fi
  if ! check "$@"; then
    [ "${ALLOW_CPU:-0}" = 1 ] || { echo; echo "check failed: not starting (ALLOW_CPU=1 to start anyway)"; exit 1; }
  fi
  if [ "$APP" = 1 ]; then app_env || exit 1; py=$EVAL_PY; else py="${EVAL_PY:-$HERE/.venv/bin/python}"; fi
  for s in "$@"; do   # the songs each set finds, by their labels, before anything detaches
    echo "== the $s set"
    EVAL_DATA="$DATA" "$py" "$HERE/takes.py" --set "$s" --dry-run ${SEEDS:+--seeds "$SEEDS"} ${SONGS:+--songs "$SONGS"} \
      || { echo; echo "the $s set has no song to take: not starting (build it first: eval/README.md)"; exit 1; }
  done
  mkdir -p "$RUNS"
  SONGCHARTER_APP=$APP setsid nohup "$0" _takes "$@" >> "$RUNS/gpu_run.log" 2>&1 < /dev/null &
  for _ in 1 2 3 4 5 6 7 8 9 10; do running && break; sleep 0.5; done
  if running; then
    echo; echo "started (pid $(cat "$PIDFILE")). Follow it with: eval/gpu.sh status   (or: tail -f $(tilde "$RUNS/takes/takes.log"))"
    echo "Keep one Ubuntu window open while it runs: WSL may shut down when the last one closes."
  else
    echo "did not start; see $(tilde "$RUNS/gpu_run.log"):"; tail -n 20 "$RUNS/gpu_run.log" | tilde_lines; exit 1
  fi
}

_thin() {   # AUDIO...: thin_spike.sh on the files, with --app on the app's autochart, Node, Python and ffmpeg
  echo $$ > "$PIDFILE"
  echo 500 > /proc/self/oom_score_adj 2>/dev/null || true
  echo "$(date '+%F %T') thin spike started ($# files$([ "$APP" = 1 ] && echo ', the installed app'))"
  local rc=0
  if [ "$APP" != 1 ]; then
    SPIKE_OUT="$RUNS/thin_spike" "$HERE/spike/thin_spike.sh" "$@" || rc=$?
  elif app_env; then   # EVAL_PY and the app's Node first on PATH; its autochart and ffmpeg (FFMPEG wins, as in the app)
    SPIKE_OUT="$RUNS/thin_spike" SONGCHARTER_AUTOCHART="$APP_AUTOCHART" AUTOCHART_FFMPEG_PATH="${FFMPEG:-$APP_FFMPEG}" \
      "$HERE/spike/thin_spike.sh" "$@" || rc=$?
  else
    rc=2
  fi
  echo "$(date '+%F %T') thin spike finished (exit $rc)"
  rm -f "$PIDFILE"
}

# The thin spike checks its own device: it stops after a take whose transcriber did not run on CUDA (the spike's
# CUDA library path is songcharter's, not cuda_libs above). With --app, takes' check of the app's autochart runs
# first (takes.py --app --check: the lane, the CUDA provider, the CUDA 13 and cuDNN libraries), so a setup that would
# fall back to the CPU stops here rather than after the first take. AC_DEVICE=cpu needs no GPU (a dry run).
thin_spike() {   # AUDIO...
  local f dev=${AC_DEVICE:-cuda} files=()
  [ $# -gt 0 ] || { echo "usage: eval/gpu.sh thin-spike [--app] AUDIO... (the songs' audio files)"; exit 2; }
  for f in "$@"; do
    [ -f "$f" ] || { echo "eval/gpu.sh thin-spike: no such file: $(tilde "$f")"; exit 2; }
    files+=("$(realpath "$f")")
  done
  if running; then echo "already running (pid $(cat "$PIDFILE")): eval/gpu.sh status"; exit 1; fi
  if [ "$dev" = cuda ]; then
    command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader \
      || { echo "no nvidia-smi: is the GPU visible in WSL?"; exit 1; }
  fi
  if [ "$APP" = 1 ]; then
    app_env || exit 2
    echo "== the installed app's autochart"
    if ! "$EVAL_PY" "$HERE/takes.py" --app --check --device "$dev"; then
      [ "${ALLOW_CPU:-0}" = 1 ] || { echo; echo "check failed: not starting (ALLOW_CPU=1 to start anyway)"; exit 1; }
    fi
  fi
  mkdir -p "$RUNS"
  SONGCHARTER_APP=$APP setsid nohup "$0" _thin "${files[@]}" >> "$RUNS/gpu_run.log" 2>&1 < /dev/null &
  for _ in 1 2 3 4 5 6 7 8 9 10; do running && break; sleep 0.5; done
  if running; then
    echo; echo "started (pid $(cat "$PIDFILE")). Follow it with: eval/gpu.sh status   (or: tail -f $(tilde "$RUNS/thin_spike/thin_spike.log"))"
    echo "Keep one Ubuntu window open while it runs: WSL may shut down when the last one closes."
  else
    echo "did not start; see $(tilde "$RUNS/gpu_run.log"):"; tail -n 20 "$RUNS/gpu_run.log" | tilde_lines; exit 1
  fi
}

start() {
  if running; then echo "already running (pid $(cat "$PIDFILE")): eval/gpu.sh status"; exit 1; fi
  if pgrep -f "$DRIVER_RE" >/dev/null; then
    echo "another drive.sh is running; stop it first:"; pgrep -af "$DRIVER_RE"; exit 1
  fi
  if ! check; then
    [ "${ALLOW_CPU:-0}" = 1 ] || { echo; echo "check failed: not starting (ALLOW_CPU=1 to start anyway)"; exit 1; }
  fi
  mkdir -p "$RUNS"
  # setsid: its own session, so closing the terminal (SIGHUP) or a crashed Claude session doesn't take it down
  setsid nohup "$0" _run >> "$RUNS/gpu_run.log" 2>&1 < /dev/null &
  for _ in 1 2 3 4 5 6 7 8 9 10; do running && break; sleep 0.5; done
  if running; then
    echo; echo "started (pid $(cat "$PIDFILE")). Follow it with: eval/gpu.sh status   (or: tail -f $(tilde "$RUNS/driver.log"))"
    echo "Keep one Ubuntu window open while it runs: WSL may shut down when the last one closes."
  else
    echo "did not start; see $(tilde "$RUNS/gpu_run.log"):"; tail -n 20 "$RUNS/gpu_run.log" | tilde_lines; exit 1
  fi
}

status() {
  if running; then echo "running (pid $(cat "$PIDFILE"))"; else echo "not running"; fi
  [ -f "$RUNS/driver.log" ] && { echo "--- driver.log"; tail -n "${N:-12}" "$RUNS/driver.log" | tilde_lines; }
  [ -f "$RUNS/takes/takes.log" ] && { echo "--- takes.log"; tail -n "${N:-12}" "$RUNS/takes/takes.log" | tilde_lines; }
  [ -f "$RUNS/thin_spike/thin_spike.log" ] && { echo "--- thin_spike.log"; tail -n "${N:-12}" "$RUNS/thin_spike/thin_spike.log" | tilde_lines; }
  local oom; oom=$(grep -c 'rc=137' "$RUNS/driver.log" 2>/dev/null)
  [ "${oom:-0}" -gt 0 ] && echo "note: $oom job(s) ended with rc=137 (killed, most likely out of memory)"
  echo "---"
  command -v nvidia-smi >/dev/null && \
    nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader | sed 's/^/GPU now: /'
  echo "RAM available: $(mem_mb MemAvailable) of $(mem_mb MemTotal) MB"
}

stop() {
  if ! running; then echo "not running"; return; fi
  kill -TERM -- "-$(cat "$PIDFILE")" 2>/dev/null || kill -TERM "$(cat "$PIDFILE")"
  rm -f "$PIDFILE"
  echo "stopped; the same command (start, or takes with its sets) carries on from the first unfinished job"
}

# The zip to send back, structured files only, never a log, a traceback or audio: drive.sh's scores and the test-song
# charts, gpu_samples.csv, runs/takes/takes.jsonl (takes.py's records), and every set's takes: each take's notes.chart
# and song.ini as the engine wrote them, and its take.json and autochart_run/summary.json (as summary.json) copied field by field
# (numbers, hashes and short names: no path, no message). A stress or 20-song set's take folders go in under their
# labels (runs/takes/<set>/labels.json, which stays here; a song folder it does not name is left out), with the set's
# set.json. In the text files this PC's home folder is written ~ and the Windows profile %USERPROFILE%
# ($WINDOWS_PROFILE, else Windows' own, through cmd.exe). The guard then reads the finished zip, apart from the scrub:
# a member that holds a 20-song id as a whole word in any case, an md5 of the stress or 20-song lists, or the home
# folder or the Windows profile in any case stops it, and so does check_no_audio.py. A stopped zip is deleted, and
# so is the one before it, so no stale zip is left to send.
results() {
  local zip="$DATA/gpu_results.zip" win winp
  rm -f "$zip" "$zip.part"
  win=${WINDOWS_PROFILE:-$(cd /mnt/c 2>/dev/null && cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')}
  winp=
  if [ -n "$win" ]; then
    if command -v wslpath >/dev/null; then winp=$(wslpath "$win" 2>/dev/null); fi
    if [ -z "$winp" ] && [[ $win == [A-Za-z]:\\* ]]; then   # C:\Users\X -> /mnt/c/Users/X, as wslpath gives it
      winp="/mnt/${win:0:1}"; winp="${winp,,}${win:2}"; winp=${winp//\\//}
    fi
  fi
  python3 -I - "$RUNS" "$zip.part" "$HOME" "$win" "$winp" "${USER:-}" "${STRESS_LOCAL:-$DATA/stress.local.json}" \
    "${SET20_DATA:-$DATA/set20}/stress.local.json" <<'EOF' || { rm -f "$zip.part"; return 1; }
import glob, json, os, re, sys, time, zipfile
runs, out, home, win, winp, user, *lists = sys.argv[1:]
SCORES = ["SCORECARD.md", "gpu_samples.csv", "*/*.score.json", "*/*.score.txt", "*/test_song/notes.chart",
          "*/test_song/notes.mid", "*/test_song/song.ini", "takes/takes.jsonl"]   # drive.sh's and takes.py's own
TEXT = ["notes.chart", "song.ini"]   # a take's files as the engine writes them (chart data)

# a field-by-field copy: numbers, hashes and short names; anything else (a path, a message) is dropped
NUM = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else None
NAME_RX = re.compile(r"[A-Za-z0-9_.+ -]{1,40}")
NAME = lambda v: v if isinstance(v, str) and NAME_RX.fullmatch(v) else None
HEX = lambda v: v if isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) else None
LIST = lambda f: lambda v: [x for x in map(f, v) if x is not None] if isinstance(v, list) else None
MAP = lambda f: lambda v: {k: f(x) for k, x in v.items() if NAME(k) and f(x) is not None} if isinstance(v, dict) \
    else None
OBJ = lambda spec: lambda v: {k: g(v[k]) for k, g in spec.items() if k in v and g(v[k]) is not None} \
    if isinstance(v, dict) else None
PIECE = OBJ({**{k: NUM for k in ("start_s", "keep_from_s", "last_note_s", "nTokens", "nBeats", "seconds")},
             "devices": MAP(NAME), "cut_short": NAME})
RUN = OBJ({**{k: NUM for k in ("exitCode", "wallSeconds", "nTokens", "nBeats", "generationSeconds", "noteLines",
                               "tempoBpm", "audioDuration")},
           **{k: NAME for k in ("difficulty", "signal", "killedFor", "status", "failedStage")},
           "devices": MAP(NAME), "cachedStages": LIST(NAME)})
SUMMARY = OBJ({**{k: NAME for k in ("generatorId", "engineVersion")}, "inputSha256": HEX,
               **{k: NUM for k in ("seed", "temperature", "topP", "maxTokens", "timeoutS", "stallS")},
               "difficulties": LIST(NAME), "runs": LIST(RUN),
               "stitch": OBJ({"cut_short": NAME, "device": NAME, "cut_at_s": NUM, "last_note_s": NUM,
                              "ended": NAME, "pieces": LIST(PIECE)})})
TAKE = OBJ({"inputSha256": HEX, "seed": NUM, "difficulties": LIST(NAME), "temperature": NUM, "topP": NUM,
            "engineVersion": NAME, "install": HEX})


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


members = {}   # name in the zip -> (bytes, mtime)


def add_file(name, path):
    with open(path, "rb") as f:
        members[name] = (f.read(), os.path.getmtime(path))


def add_take(prefix, folder):
    for f in TEXT:
        if os.path.isfile(os.path.join(folder, f)):
            add_file(f"{prefix}/{f}", os.path.join(folder, f))
    for f, spec, to in (("take.json", TAKE, "take.json"), ("autochart_run/summary.json", SUMMARY, "summary.json")):
        copy = spec(read_json(os.path.join(folder, f)))
        if copy:   # the summary as seed_<s>/summary.json: no fixed word in a member's path the guard could take for a name
            members[f"{prefix}/{to}"] = (json.dumps(copy, indent=1).encode(), os.path.getmtime(os.path.join(folder, f)))


for p in SCORES:
    for f in glob.glob(os.path.join(runs, p)):
        add_file("gpu_results/" + os.path.relpath(f, runs), f)
for take in glob.glob(os.path.join(runs, "takes", "*", "seed_*")):   # the reference set's: runs/takes/<id>/seed_<s>/
    add_take("gpu_results/" + os.path.relpath(take, runs), take)
hidden, left = set(), 0   # the ids that are not labels
for name in ("stress", "set20"):
    d = os.path.join(runs, "takes", name)
    if not os.path.isdir(d):
        continue
    labels = read_json(os.path.join(d, "labels.json"))
    if not isinstance(labels, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in labels.items()):
        labels = {}
    label_of = {sid: label for label, sid in labels.items()}
    hidden |= {sid for sid, label in label_of.items() if sid != label}
    for entry in sorted(os.listdir(d)):
        if not os.path.isdir(os.path.join(d, entry)):
            continue
        if entry not in label_of:
            left += 1
            continue
        for take in sorted(glob.glob(os.path.join(d, entry, "seed_*"))):
            add_take(f"gpu_results/takes/{name}/{label_of[entry]}/{os.path.basename(take)}", take)
    if os.path.isfile(os.path.join(d, "set.json")):
        add_file(f"gpu_results/takes/{name}/set.json", os.path.join(d, "set.json"))

places = [v for v in {home, win, win.replace("\\", "\\\\"), winp} if len(v) > 1]
tilde = [(re.compile(re.escape(v) + r"(?![A-Za-z0-9_.-])"), "~" if v == home else "%USERPROFILE%")
         for v in sorted(places, key=len, reverse=True)]


def scrub(data):
    text = data.decode("utf-8", "surrogateescape")
    for rx, to in tilde:
        text = rx.sub(lambda m: to, text)
    return text.encode("utf-8", "surrogateescape")


with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for name, (data, mtime) in sorted(members.items()):
        info = zipfile.ZipInfo(name, time.localtime(max(mtime, 315619200))[:6])   # 1980-01-02: zip's first date
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, scrub(data))

# the guard, apart from the scrub: the finished zip read back, each member's name and text in lower case, and once
# more with runs of spaces, hyphens and underscores read as one space. It stops on: a 20-song id, or a title, artist
# or charter of the stress or 20-song lists, as a whole word in that form; this PC's user name as a whole word; an
# md5 of the lists, or a run of 8 or more hex digits that starts one; a Windows user folder (/mnt/x/users/,
# x:\users or x:/users), a \\wsl$ or \\wsl.localhost path, the home folder or the Windows profile. It names the
# member (by label) and the kind of hit, never the text.
def norm(s):
    return re.sub(r"[\s_-]+", " ", s.lower()).strip()


PUBLIC = set()   # the stress set's ids and labels: committed (eval/stress.json), so a name that is one is not checked
for name in ("stress", "set20"):
    labels = read_json(os.path.join(runs, "takes", name, "labels.json"))
    if isinstance(labels, dict):
        PUBLIC |= {norm(k) for k in labels if isinstance(k, str)}
        PUBLIC |= {norm(v) for k, v in labels.items() if name == "stress" and isinstance(v, str)}


def words(kind, values):   # (kind, a whole-word pattern over normalized text), for names of 3 characters or more
    vs = sorted({norm(v) for v in values if isinstance(v, str) and len(norm(v)) >= 3} - PUBLIC, key=len, reverse=True)
    return [(kind, re.compile(r"(?<!\w)(?:" + "|".join(re.escape(v) for v in vs) + r")(?!\w)"))] if vs else []


md5s, names = set(), {"title": [], "artist": [], "charter": []}
for path in lists:
    for song in read_json(path) or []:
        if not isinstance(song, dict):
            continue
        alts = [a for a in song.get("alts") or [] if isinstance(a, dict)]
        md5s |= {m.lower() for m in [song.get("md5")] + [a.get("md5") for a in alts] if isinstance(m, str)}
        for kind in names:
            names[kind] += [song.get(kind)] + [a.get(kind) for a in alts]
users = {u for u in (user, os.path.basename(home.rstrip("/"))) if len(u) >= 2}
checks = words("id", hidden) + [w for kind, vs in names.items() for w in words(kind, vs)] + words("user name", users)
PATHS = re.compile(r"/mnt/[a-z]/users/|(?<![a-z])[a-z]:[\\/]+users[\\/]|[\\/]{2,}wsl(?:\$|\.localhost)")
lowered = [v.lower() for v in places]
HEXRUN = re.compile(r"(?<![0-9a-f])[0-9a-f]{8,32}(?![0-9a-f])")
stops = []
with zipfile.ZipFile(out) as z:
    for n in z.namelist():
        text = (n + "\n" + z.read(n).decode("utf-8", "surrogateescape")).lower()
        flat = norm(text)
        why = [kind for kind, rx in checks if rx.search(flat)]
        if any(m in text for m in md5s) or any(any(m.startswith(r) for m in md5s) for r in HEXRUN.findall(text)):
            why.append("md5")
        if PATHS.search(text) or any(v in text for v in lowered):
            why.append("path")
        if why:
            named = norm(n)   # the member, with any name in its own path masked
            hits = [(kind, rx) for kind, rx in checks if rx.search(named)]
            for kind, rx in hits:
                named = rx.sub(f"<{kind}>", named)
            stops.append(f"{named if hits else n}: {', '.join(dict.fromkeys(why))}")
if stops:
    print("results: no zip made, the guard stopped it (these lines hold no name: send them as they are):",
          *(f"  {s}" for s in stops), sep="\n")
    sys.exit(1)
print(f"results: {len(members)} files" + (f"; {left} song folders left out (no labels.json names them)" if left else ""))
EOF
  if ! (cd "$DATA" && python3 -I "$NO_AUDIO" gpu_results.zip.part); then
    rm -f "$zip.part"; echo "results: the zip would hold audio (above): no zip made"; return 1
  fi
  mv "$zip.part" "$zip"
  echo "$(tilde "$zip"): $(( $(stat -c %s "$zip") / 1024 )) KB"
  # also drop a copy in the Windows Downloads folder, ready to attach in the Claude app
  if [ -n "$winp" ] && [ -d "$winp/Downloads" ]; then
    cp "$zip" "$winp/Downloads/" && echo "copied to your Windows Downloads folder as gpu_results.zip"
  fi
}

# eval/build_refs.sh for one set, with --app on the installed app's Python, Node, scan-chart and ffmpeg (app_env). The
# stress and 20-song sets' output goes through takes.py --scrub: their songs by label, every md5 as <md5>.
build() {   # SET [TEST_SONG]
  local set="${1:-}" d py f
  [ $# -gt 0 ] && shift
  if [ "$APP" = 1 ]; then app_env || exit 2; fi
  py="${EVAL_PY:-$HERE/.venv/bin/python}"
  export EVAL_PY="$py"
  set -o pipefail
  case "$set" in
    refs) EVAL_DATA="$DATA" "$HERE/build_refs.sh" "$@" ;;
    stress)
      [ $# -eq 0 ] || { echo "eval/gpu.sh build stress: takes no test song"; exit 2; }
      EVAL_DATA="$DATA" "$HERE/build_refs.sh" --set stress 2>&1 | EVAL_DATA="$DATA" "$py" "$HERE/takes.py" --set stress --scrub ;;
    set20)
      [ $# -eq 0 ] || { echo "eval/gpu.sh build set20: takes no test song"; exit 2; }
      d="${SET20_DATA:-$DATA/set20}"
      for f in set20.json stress.local.json; do
        [ -f "$d/$f" ] || { echo "no $(tilde "$d/$f"): the 20-song set's two lists go there (eval/README.md)"; exit 2; }
      done
      EVAL_DATA="$d" STRESS_JSON="$d/set20.json" STRESS_LOCAL="$d/stress.local.json" "$HERE/build_refs.sh" --set stress 2>&1 \
        | EVAL_DATA="$DATA" SET20_DATA="$d" "$py" "$HERE/takes.py" --set set20 --scrub ;;
    *) echo "usage: eval/gpu.sh build [--app] refs [TEST_SONG] | stress | set20"; exit 2 ;;
  esac
}

cmd="${1:-}"
[ $# -gt 0 ] && shift
args=()
for a in "$@"; do if [ "$a" = --app ]; then APP=1; else args+=("$a"); fi; done
set -- ${args[@]+"${args[@]}"}
case "$cmd" in
  check) check "$@" ;;
  start)
    [ "$APP" = 1 ] && { echo "eval/gpu.sh start runs the eval tools (strum, chartgen, autochart): --app is for check, takes, build and thin-spike"; exit 2; }
    start ;;
  status) status ;;
  stop) stop ;;
  results) results ;;
  takes) takes "$@" ;;
  build) build "$@" ;;
  thin-spike) thin_spike "$@" ;;
  _thin) _thin "$@" ;;
  _run) _run ;;
  _takes) _takes "$@" ;;
  *) sed -n '2,/^set -u/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 2 ;;
esac
