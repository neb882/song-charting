#!/usr/bin/env bash
# gpu.sh: run the comparison on an NVIDIA GPU as a standalone job, the way Overclock's `render.ts video` runs: you
# start it in your own terminal, and no Claude session has to stay connected while it works.
#   eval/gpu.sh check     the GPU, CUDA inside each tool, and the memory WSL sees; fails if a tool would fall back to CPU
#   eval/gpu.sh start     check, then run drive.sh detached: it survives closing the terminal and a Claude crash
#   eval/gpu.sh status    running or not, the latest driver.log lines, GPU and memory now
#   eval/gpu.sh stop      stop the run; finished jobs are kept, and `start` carries on from there
#   eval/gpu.sh takes     check, then run eval/takes.py detached: 4 autochart Expert takes of every song (no scoring)
#   eval/gpu.sh thin-spike AUDIO   run eval/spike/thin_spike.sh detached: Expert takes of one song under several engine
#                         settings (M6's spike on fast runs; its header has the settings); results in $RUNS/thin_spike
#   eval/gpu.sh results   zip the scores, the logs, the test-song charts and the takes' charts (no audio) to send back
# Env: TOOLS (default "autochart chartgen strum", so STRUM's long test song runs last), SKIP (e.g. "strum:test_song"),
#      MEM_WAIT_MB (default 4000), EVAL_DATA, ALLOW_CPU=1 (start even if the check fails).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${EVAL_DATA:-$HERE/data}"
RUNS="$DATA/runs"
PIDFILE="$RUNS/gpu_run.pid"
T="$HERE/tools"
DRIVER_RE='^(/[^ ]*/)?bash [^ ]*drive\.sh'   # a running driver itself, not a command line that mentions it

mem_mb() { awk -v k="$1:" '$1 == k {print int($2/1024)}' /proc/meminfo; }

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

check() {
  local bad=0
  echo "== GPU"
  if command -v nvidia-smi >/dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv,noheader
  else
    echo "nvidia-smi not found: no NVIDIA driver is visible (in WSL, install or update the Windows NVIDIA driver)"; bad=1
  fi
  echo "== CUDA inside each tool"
  for tool in strum chartgen; do
    local py="$T/$tool/venv/bin/python"
    if [ ! -x "$py" ]; then echo "$tool: not installed (run $T/$tool/setup.sh with TORCH_INDEX=.../cu128)"; bad=1; continue; fi
    local out; out=$(cd /tmp && "$py" -I -c "$TORCH_CHECK" 2>&1) || bad=1
    echo "$tool: $(echo "$out" | tail -n 1)"
  done
  if [ -d "$T/autochart/node_modules/onnxruntime-node" ]; then
    if find "$T/autochart/node_modules/onnxruntime-node" -name 'libonnxruntime_providers_cuda.so*' | grep -q .; then
      echo "autochart: ok: onnxruntime-node has its CUDA provider (each run's log names the device it used)"
      local libs
      if libs=$(cuda_libs); then
        echo "autochart: CUDA libraries for its runs: $libs"
      else
        echo "autochart: no cuDNN 9 (libcudnn.so.9) on the system or in a tool venv: its CUDA provider would fail to load"; bad=1
      fi
    else
      echo "autochart: onnxruntime-node has no CUDA provider, so it would run on CPU (reinstall with ONNXRUNTIME_NODE_INSTALL_CUDA=v12)"; bad=1
    fi
  else
    echo "autochart: not installed (run $T/autochart/setup.sh)"; bad=1
  fi
  echo "== memory (as WSL sees it)"
  local total swap
  total=$(mem_mb MemTotal); swap=$(mem_mb SwapTotal)
  echo "RAM ${total} MB, $(mem_mb MemAvailable) MB available; swap ${swap} MB"
  if [ "$total" -lt 15000 ]; then
    echo "warning: WSL has less than 15 GB. By default it gets half of Windows' RAM. STRUM and chartgen on a 7-minute song"
    echo "         can run out, and the kernel then kills processes (this job first, see oom_score_adj below). To give WSL"
    echo "         more, see 'Memory' in eval/README.md."
  fi
  [ -f "$DATA/refs/songs.json" ] || { echo "no reference set: run eval/build_refs.sh first"; bad=1; }
  return $bad
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

_takes() {
  echo $$ > "$PIDFILE"
  echo 500 > /proc/self/oom_score_adj 2>/dev/null || true
  echo "$(date '+%F %T') takes run started"
  local py="${EVAL_PY:-$HERE/.venv/bin/python}" libs
  libs=$(cuda_libs) && [ -n "$libs" ] && export LD_LIBRARY_PATH="$libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
  EVAL_DATA="$DATA" "$py" "$HERE/takes.py" --device cuda ${SEEDS:+--seeds "$SEEDS"} ${SONGS:+--songs "$SONGS"}
  local rc=$?
  results
  echo "$(date '+%F %T') takes run finished (exit $rc)"
  rm -f "$PIDFILE"
}

takes() {
  if running; then echo "already running (pid $(cat "$PIDFILE")): eval/gpu.sh status"; exit 1; fi
  if ! check; then
    [ "${ALLOW_CPU:-0}" = 1 ] || { echo; echo "check failed: not starting (ALLOW_CPU=1 to start anyway)"; exit 1; }
  fi
  mkdir -p "$RUNS"
  setsid nohup "$0" _takes >> "$RUNS/gpu_run.log" 2>&1 < /dev/null &
  for _ in 1 2 3 4 5 6 7 8 9 10; do running && break; sleep 0.5; done
  if running; then
    echo; echo "started (pid $(cat "$PIDFILE")). Follow it with: eval/gpu.sh status   (or: tail -f $RUNS/takes/takes.log)"
    echo "Keep one Ubuntu window open while it runs: WSL may shut down when the last one closes."
  else
    echo "did not start; see $RUNS/gpu_run.log:"; tail -n 20 "$RUNS/gpu_run.log"; exit 1
  fi
}

_thin() {
  echo $$ > "$PIDFILE"
  echo 500 > /proc/self/oom_score_adj 2>/dev/null || true
  echo "$(date '+%F %T') thin spike started"
  "$HERE/spike/thin_spike.sh" "$1" "$RUNS/thin_spike"
  local rc=$?
  echo "$(date '+%F %T') thin spike finished (exit $rc)"
  rm -f "$PIDFILE"
}

# The thin spike checks its own device: it stops after a take whose transcriber did not run on CUDA (the spike's
# CUDA library path is songcharter's, not cuda_libs above).
thin_spike() {
  [ -n "${1:-}" ] && [ -f "$1" ] || { echo "usage: eval/gpu.sh thin-spike AUDIO (the song's audio file)"; exit 2; }
  if running; then echo "already running (pid $(cat "$PIDFILE")): eval/gpu.sh status"; exit 1; fi
  command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader \
    || { echo "no nvidia-smi: is the GPU visible in WSL?"; exit 1; }
  mkdir -p "$RUNS"
  setsid nohup "$0" _thin "$(realpath "$1")" >> "$RUNS/gpu_run.log" 2>&1 < /dev/null &
  for _ in 1 2 3 4 5 6 7 8 9 10; do running && break; sleep 0.5; done
  if running; then
    echo; echo "started (pid $(cat "$PIDFILE")). Follow it with: tail -f $RUNS/thin_spike/thin_spike.log"
    echo "Keep one Ubuntu window open while it runs: WSL may shut down when the last one closes."
  else
    echo "did not start; see $RUNS/gpu_run.log:"; tail -n 20 "$RUNS/gpu_run.log"; exit 1
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
    echo; echo "started (pid $(cat "$PIDFILE")). Follow it with: eval/gpu.sh status   (or: tail -f $RUNS/driver.log)"
    echo "Keep one Ubuntu window open while it runs: WSL may shut down when the last one closes."
  else
    echo "did not start; see $RUNS/gpu_run.log:"; tail -n 20 "$RUNS/gpu_run.log"; exit 1
  fi
}

status() {
  if running; then echo "running (pid $(cat "$PIDFILE"))"; else echo "not running"; fi
  [ -f "$RUNS/driver.log" ] && { echo "--- driver.log"; tail -n "${N:-12}" "$RUNS/driver.log"; }
  [ -f "$RUNS/takes/takes.log" ] && { echo "--- takes.log"; tail -n "${N:-12}" "$RUNS/takes/takes.log"; }
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
  echo "stopped; eval/gpu.sh start carries on from the first unfinished job"
}

results() {
  local zip="$DATA/gpu_results.zip"
  python3 -I - "$RUNS" "$zip" <<'EOF' || return 1
import glob, os, sys, zipfile
runs, out = sys.argv[1:]
pats = ["SCORECARD.md", "driver.log", "gpu_run.log", "gpu_samples.csv", "*/*.score.json", "*/*.score.txt", "*/*.log",
        "*/test_song/notes.chart", "*/test_song/notes.mid", "*/test_song/song.ini",
        "takes/takes.log", "takes/*/seed_*/notes.chart", "takes/*/seed_*/song.ini",
        "takes/*/seed_*/autochart_run/*.json"]   # never audio
files = sorted({f for p in pats for f in glob.glob(os.path.join(runs, p))})
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        z.write(f, os.path.join("gpu_results", os.path.relpath(f, runs)))
print(f"{out}: {len(files)} files, {os.path.getsize(out) // 1024} KB")
EOF
  # also drop a copy in the Windows Downloads folder, ready to attach in the Claude app
  local win
  win=$(cd /mnt/c 2>/dev/null && cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')
  if [ -n "$win" ] && command -v wslpath >/dev/null && [ -d "$(wslpath "$win")/Downloads" ]; then
    cp "$zip" "$(wslpath "$win")/Downloads/" && echo "copied to $win\\Downloads\\gpu_results.zip"
  fi
}

case "${1:-}" in
  check) check ;;
  start) start ;;
  status) status ;;
  stop) stop ;;
  results) results ;;
  takes) takes ;;
  thin-spike) shift; thin_spike "$@" ;;
  _thin) shift; _thin "$@" ;;
  _run) _run ;;
  _takes) _takes ;;
  *) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
