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
#   eval/gpu.sh thin-spike AUDIO   run eval/spike/thin_spike.sh detached: Expert takes of one song under several engine
#                         settings (M6's spike on fast runs; its header has the settings); results in $RUNS/thin_spike
#   eval/gpu.sh results   zip the scores, the logs, the test-song charts and every set's takes' charts to send back
#                         (no audio: check_no_audio.py; the 20-song set's songs by their labels only)
# --app (check, takes, build; or SONGCHARTER_APP=1): the installed songcharter's Python, Node, scan-chart, ffmpeg and
#      autochart (SONGCHARTER_HOME, default ~/.local/share/songcharter) in place of eval/.venv and eval/tools; the
#      check is then autochart's only (eval/README.md, GPU takes with the installed app).
# Env: TOOLS (default "autochart chartgen strum", so STRUM's long test song runs last), SKIP (e.g. "strum:test_song"),
#      MEM_WAIT_MB (default 4000), EVAL_DATA, EVAL_PY, SET20_DATA (default $EVAL_DATA/set20), SEEDS, SONGS (ids or
#      labels, for one set), ALLOW_CPU=1 (start even if the check fails).
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
# autochart and the rest of the launcher's environment from the same runtime.json itself.
app_env() {
  local py="$APP_HOME/runtime/env/bin/python" record="$APP_HOME/runtime/runtime.json" vals node scan ff
  if [ ! -x "$py" ] || [ ! -f "$record" ]; then
    echo "no installed songcharter at $APP_HOME (runtime/env/bin/python, runtime/runtime.json): install it, or set SONGCHARTER_HOME"
    return 1
  fi
  vals=$("$py" -I -c 'import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
print(r.get("node") or "", r.get("scan_chart") or "", r.get("ffmpeg") or "", sep="\n")' "$record") || return 1
  { read -r node; read -r scan; read -r ff; } <<< "$vals"
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
    echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
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
  echo "stopped; the same command (start, or takes with its sets) carries on from the first unfinished job"
}

# The zip to send back: the scores, the logs, the test-song charts, and every set's takes (each take's notes.chart,
# song.ini, take.json and autochart_run/*.json; never audio, and check_no_audio.py must pass on the zip). A stress or
# 20-song set's take folders go in under their labels (runs/takes/<set>/labels.json, which stays here; a song folder
# it does not name is left out), and in every file each such id is replaced by its label, this PC's home folder by ~
# and the Windows profile by %USERPROFILE%. A zip still holding an id is not made. Without a zip, no stale one is left.
results() {
  local zip="$DATA/gpu_results.zip" win= winp=
  rm -f "$zip" "$zip.part"
  win=$(cd /mnt/c 2>/dev/null && cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')
  if [ -n "$win" ] && command -v wslpath >/dev/null; then winp=$(wslpath "$win" 2>/dev/null); fi
  python3 -I - "$RUNS" "$zip.part" "$HOME" "$win" "$winp" <<'EOF' || { rm -f "$zip.part"; return 1; }
import glob, json, os, re, sys, time, zipfile
runs, out, home, win, winp = sys.argv[1:6]
TAKE = ["notes.chart", "song.ini", "take.json", "autochart_run/*.json"]   # a take's files: never audio
pats = ["SCORECARD.md", "driver.log", "gpu_run.log", "gpu_samples.csv", "*/*.score.json", "*/*.score.txt", "*/*.log",
        "*/test_song/notes.chart", "*/test_song/notes.mid", "*/test_song/song.ini", "takes/takes.log",
        *(f"takes/*/seed_*/{p}" for p in TAKE)]   # the reference set's takes: runs/takes/<id>/seed_<seed>/
files = {}   # the name in the zip -> the file
for p in pats:
    for f in glob.glob(os.path.join(runs, p)):
        files[os.path.join("gpu_results", os.path.relpath(f, runs))] = f
hidden, left = {}, 0   # id -> label, for the ids that are not labels
for name in ("stress", "set20"):
    d = os.path.join(runs, "takes", name)
    if not os.path.isdir(d):
        continue
    try:
        with open(os.path.join(d, "labels.json"), encoding="utf-8") as f:
            labels = json.load(f)
    except (OSError, ValueError):
        labels = {}
    if not isinstance(labels, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in labels.items()):
        labels = {}
    label_of = {sid: label for label, sid in labels.items()}
    hidden.update({sid: label for sid, label in label_of.items() if sid != label})
    for entry in sorted(os.listdir(d)):
        song = os.path.join(d, entry)
        if not os.path.isdir(song):
            continue
        if entry not in label_of:
            left += 1
            continue
        for p in TAKE:
            for f in glob.glob(os.path.join(song, "seed_*", p)):
                files[os.path.join("gpu_results", "takes", name, label_of[entry], os.path.relpath(f, song))] = f
    if os.path.isfile(os.path.join(d, "set.json")):
        files[os.path.join("gpu_results", "takes", name, "set.json")] = os.path.join(d, "set.json")
ids = re.compile("(?<![A-Za-z0-9_])(" + "|".join(re.escape(i) for i in sorted(hidden, key=len, reverse=True))
                 + ")(?![A-Za-z0-9_])") if hidden else None
paths = [(re.compile(re.escape(v) + r"(?![A-Za-z0-9_.-])"), to)
         for v, to in sorted({(win.replace("\\", "\\\\"), "%USERPROFILE%"), (win, "%USERPROFILE%"),
                              (winp, "%USERPROFILE%"), (home, "~")}, key=lambda vt: -len(vt[0])) if len(v) > 1]


def scrub(text):
    for rx, to in paths:
        text = rx.sub(lambda m: to, text)
    return ids.sub(lambda m: hidden[m.group(1)], text) if ids else text


with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for name, f in sorted(files.items()):
        with open(f, "rb") as fh:
            data = scrub(fh.read().decode("utf-8", "surrogateescape")).encode("utf-8", "surrogateescape")
        info = zipfile.ZipInfo(scrub(name), time.localtime(max(os.path.getmtime(f), 315619200))[:6])
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, data)
if ids:   # the guard: nothing that names a 20-song song by its id leaves this PC
    with zipfile.ZipFile(out) as z:
        bad = [n for n in z.namelist() if ids.search(n) or ids.search(z.read(n).decode("utf-8", "surrogateescape"))]
    if bad:
        sys.exit(f"results: {len(bad)} files still hold an id that is not a label: no zip made")
print(f"results: {len(files)} files" + (f"; {left} song folders left out (no labels.json names them)" if left else ""))
EOF
  if ! python3 -I "$NO_AUDIO" "$zip.part"; then
    rm -f "$zip.part"; echo "results: the zip would hold audio (above): no zip made"; return 1
  fi
  mv "$zip.part" "$zip"
  echo "$zip: $(( $(stat -c %s "$zip") / 1024 )) KB"
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
        [ -f "$d/$f" ] || { echo "no $d/$f: the 20-song set's two lists go there (eval/README.md)"; exit 2; }
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
    [ "$APP" = 1 ] && { echo "eval/gpu.sh start runs the eval tools (strum, chartgen, autochart): --app is for check, takes and build"; exit 2; }
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
