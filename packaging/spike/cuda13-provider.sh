#!/usr/bin/env bash
# cuda13-provider.sh: the M4-00b spike (docs/work-orders/M4-00b-cuda13-spike.md).
#
# Does onnxruntime-node 1.27.0's CUDA provider, which autochart's engine uses for the guitar, run in WSL on the CUDA 13
# libraries that songcharter's cu132 torch lane brings (plus nvidia-curand), with no CUDA toolkit and no separate cuDNN?
# The provider needs libcublasLt.so.13, libcublas.so.13, libcudart.so.13, libnvrtc.so.13, libcufft.so.12,
# libcurand.so.10, libcudnn.so.9 and the driver's libcuda.so.1 (readelf). eval/gpu.sh's earlier 5070 runs put CUDA 12
# libraries on the path, so they are no evidence for this.
#
# It needs no songcharter install and changes nothing outside --dir (default ~/scspike-cuda13; delete it afterwards):
#   1. uv 0.13.5 (its release tarball, checked against the published SHA-256);
#   2. a venv with torch 2.15.0+cu132 and nvidia-curand 10.4.4.72 (about 3.2 GB of downloads);
#   3. Node 24.19.0 and onnxruntime-node 1.27.0 by autochart's lock (npm ci; its install script fetches the CUDA
#      provider from NuGet, 212 MB), the provider's files checked by SHA-256;
#   4. Fretformer 2's transcriber encoder (122 MB), checked by SHA-256;
#   5. one session with executionProviders ["cuda"] and LD_LIBRARY_PATH = the venv's nvidia/cu13/lib and
#      nvidia/cudnn/lib plus /usr/lib/wsl/lib, as songcharter will set it; ORT's own log says where each node runs;
#      then the same on the CPU for a comparison;
#   6. a verdict, and cuda13-result.json (in --dir, and copied to Windows' Downloads when run in WSL).
# Exit 0: PASS (the session ran on CUDA). Exit 1: FAIL, with the reason in capitals. Exit 2: setup failed (network,
# disk): run it again, it resumes.
#
# usage: bash cuda13-provider.sh [--dir DIR] [--device cuda|cpu] [--skip-torch]
#   --device cpu      only the CPU path (for testing this script on a machine without a GPU)
#   --skip-torch      no torch venv (testing only: then --device cuda must FAIL on the missing libraries)
set -euo pipefail

DIR="${HOME}/scspike-cuda13"
DEVICE=cuda
SKIP_TORCH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --device) DEVICE="$2"; shift 2 ;;
    --skip-torch) SKIP_TORCH=1; shift ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
done
case "$DEVICE" in cuda|cpu) ;; *) echo "--device is cuda or cpu" >&2; exit 2 ;; esac

# ---------------------------------------------------------------------------------------------------- pins
UV_URL=https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-unknown-linux-gnu.tar.gz
UV_SHA=f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f
NODE_URL=https://nodejs.org/dist/v24.19.0/node-v24.19.0-linux-x64.tar.gz
NODE_SHA=f625d97cd707df4ff96254916fbc5ff014f09c09effe5a1e0ca8f6d41a8789d4
REPO_RAW=https://raw.githubusercontent.com/neb882/song-charting/77b2afda5051cd955649d46db0b8da6abf02b2d2/eval/tools/autochart
PKG_SHA=5a16ddfbcb50646079048d03ec4780987f17f833ffd50c52fe065c26887f3598
LOCK_SHA=1593a1a4399d5f62cde438ae0e340fa65bf4c469f02599aa086e44798a330564
CUDA_EP_SHA=0d3171e422fc7b554cb05af69009b519beec03d6084ebe924782307b29338f39
SHARED_EP_SHA=c6a12593396095f5670160e284c35d1700b7708cf3037b7042e2a5200ccae772
MODEL_URL=https://huggingface.co/Dvaro/autochart-models/resolve/8a88855d745f0b508f68ac606d7cbdac2878c87d/fretformer-v2/encoder_fp32.onnx
MODEL_SHA=e22f643816ea313e7f06892bc5dd50e3726d9f0c8193f95a14524283f99f98c1
NEEDED="libcublasLt.so.13 libcublas.so.13 libcudart.so.13 libnvrtc.so.13 libcufft.so.12 libcurand.so.10 libcudnn.so.9"

export UV_CACHE_DIR="$DIR/uv-cache" UV_PYTHON_INSTALL_DIR="$DIR/python" UV_HTTP_TIMEOUT=300 UV_HTTP_RETRIES=5
mkdir -p "$DIR/downloads" "$DIR/logs"
LOG="$DIR/logs"
START=$(date +%s)

step() { printf '\n== %s\n' "$*"; }
setup_failed() { printf '\nsetup failed: %s\nRun the same command again to continue.\n' "$*" >&2; exit 2; }
fail() { printf '\n%s\n' "############################################################" >&2
         printf 'FAIL: %s\n' "$*" >&2
         printf '%s\n' "############################################################" >&2; }

fetch() {  # fetch URL DEST SHA256: through DEST.part, resumed, then checked
  local url=$1 dest=$2 sha=$3
  if [ -f "$dest" ] && [ "$(sha256sum "$dest" | cut -c1-64)" = "$sha" ]; then echo "  have $(basename "$dest")"; return; fi
  echo "  downloading $url"
  curl -fL --retry 5 --retry-delay 5 --connect-timeout 30 --progress-bar -C - -o "$dest.part" "$url" \
    || { rm -f "$dest.part"; curl -fL --retry 5 --retry-delay 5 --progress-bar -o "$dest.part" "$url"; } \
    || setup_failed "could not download $url"
  [ "$(sha256sum "$dest.part" | cut -c1-64)" = "$sha" ] || { rm -f "$dest.part"; setup_failed "$url did not match its SHA-256"; }
  mv "$dest.part" "$dest"
}

# ---------------------------------------------------------------------------------------------------- 0. the machine
step "the machine"
IN_WSL=no; grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null && IN_WSL=yes
SMI=$(command -v nvidia-smi || true); [ -z "$SMI" ] && [ -x /usr/lib/wsl/lib/nvidia-smi ] && SMI=/usr/lib/wsl/lib/nvidia-smi
GPU=""; DRIVER=""
if [ -n "$SMI" ]; then
  Q=$("$SMI" --query-gpu=name,driver_version,compute_cap --format=csv,noheader 2>/dev/null | head -n 1 || true)
  GPU=$(echo "$Q" | cut -d, -f1 | xargs); DRIVER=$(echo "$Q" | cut -d, -f2 | xargs)
fi
echo "  WSL: $IN_WSL; GPU: ${GPU:-none}; driver: ${DRIVER:-none}"
if [ "$DEVICE" = cuda ] && [ -z "$GPU" ]; then echo "  warning: no NVIDIA GPU visible (nvidia-smi): the CUDA check will fail"; fi
if [ -n "$DRIVER" ] && [ "${DRIVER%%.*}" -lt 580 ] 2>/dev/null; then
  echo "  warning: driver $DRIVER is older than 580; CUDA 13 libraries need 580 or newer"
fi
FREE=$(df -Pk "$DIR" | awk 'NR==2 {print int($4/1048576)}')
NEED=8; [ "$SKIP_TORCH" = 1 ] && NEED=1
[ "$FREE" -ge "$NEED" ] || setup_failed "$DIR has ${FREE} GB free; the spike needs $NEED GB"

# ---------------------------------------------------------------------------------------------------- 1. uv
step "uv 0.13.5"
UV="$DIR/bin/uv"
if [ ! -x "$UV" ]; then
  fetch "$UV_URL" "$DIR/downloads/uv.tar.gz" "$UV_SHA"
  mkdir -p "$DIR/bin"
  tar -xzf "$DIR/downloads/uv.tar.gz" -C "$DIR/bin" --strip-components=1 uv-x86_64-unknown-linux-gnu/uv
fi
"$UV" --version

# ---------------------------------------------------------------------------------------------------- 2. the venv
step "a venv with torch 2.15.0+cu132 and nvidia-curand 10.4.4.72"
PY="$DIR/venv/bin/python"
[ -x "$PY" ] || "$UV" venv -q --python 3.13 "$DIR/venv" || setup_failed "uv venv"
LIBDIRS=""
if [ "$SKIP_TORCH" = 0 ]; then
  "$UV" pip install --python "$PY" --index-strategy unsafe-best-match \
      --extra-index-url https://download.pytorch.org/whl/cu132 "torch==2.15.0+cu132" "nvidia-curand==10.4.4.72" \
    || setup_failed "uv pip install"
  SITE=$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  for d in "$SITE/nvidia/cu13/lib" "$SITE/nvidia/cudnn/lib"; do [ -d "$d" ] && LIBDIRS="$LIBDIRS${LIBDIRS:+:}$d"; done
else
  echo "  skipped (--skip-torch)"
fi
[ -d /usr/lib/wsl/lib ] && LIBDIRS="$LIBDIRS${LIBDIRS:+:}/usr/lib/wsl/lib"
MISSING=""
for lib in $NEEDED; do
  found=no; IFS=: read -r -a dirs <<< "$LIBDIRS"
  for d in "${dirs[@]}"; do [ -n "$d" ] && [ -e "$d/$lib" ] && found=yes; done
  [ $found = yes ] || MISSING="$MISSING $lib"
done
LIBCUDA=no; [ -e /usr/lib/wsl/lib/libcuda.so.1 ] && LIBCUDA=yes
echo "  library path: ${LIBDIRS:-none}"
echo "  missing from it:${MISSING:- nothing}; libcuda.so.1 from the Windows driver: $LIBCUDA"
TORCH_JSON='null'
if [ "$SKIP_TORCH" = 0 ]; then
  TORCH_JSON=$("$PY" - <<'EOF' 2>/dev/null || echo 'null'
import json, torch
r = {"version": torch.__version__, "cuda": torch.version.cuda, "available": torch.cuda.is_available()}
if r["available"]:
    try:
        x = torch.randn(512, 512, device="cuda"); (x @ x).sum().item(); r["matmul"] = True
        r["device"] = torch.cuda.get_device_name(0)
    except Exception as e:
        r["matmul"] = False; r["error"] = str(e).splitlines()[0][:200]
print(json.dumps(r))
EOF
)
  echo "  torch: $TORCH_JSON"
fi

# ---------------------------------------------------------------------------------------------------- 3. Node and onnxruntime-node
step "Node 24.19.0 and onnxruntime-node 1.27.0"
NODE="$DIR/node/bin/node"
if [ ! -x "$NODE" ]; then
  fetch "$NODE_URL" "$DIR/downloads/node.tar.gz" "$NODE_SHA"
  mkdir -p "$DIR/node"; tar -xzf "$DIR/downloads/node.tar.gz" -C "$DIR/node" --strip-components=1
fi
echo "  node $("$NODE" --version)"
ORT_DIR="$DIR/ort"; mkdir -p "$ORT_DIR"
fetch "$REPO_RAW/package.json" "$ORT_DIR/package.json" "$PKG_SHA"
fetch "$REPO_RAW/package-lock.json" "$ORT_DIR/package-lock.json" "$LOCK_SHA"
BIN="$ORT_DIR/node_modules/onnxruntime-node/bin/napi-v6/linux/x64"
if [ ! -f "$BIN/libonnxruntime_providers_cuda.so" ] || [ "$(sha256sum "$BIN/libonnxruntime_providers_cuda.so" | cut -c1-64)" != "$CUDA_EP_SHA" ]; then
  # npm ci without install scripts (npm 11 warns about them, and a later npm may block them), then onnxruntime-node's own
  # installer, run explicitly: it fetches the CUDA provider (NuGet Microsoft.ML.OnnxRuntime.Gpu.Linux 1.27.0, 212 MB)
  (cd "$ORT_DIR" && PATH="$DIR/node/bin:$PATH" "$NODE" "$DIR/node/lib/node_modules/npm/bin/npm-cli.js" ci --omit=dev \
      --ignore-scripts --no-audit --no-fund) || setup_failed "npm ci (onnxruntime-node)"
  (cd "$ORT_DIR/node_modules/onnxruntime-node" && PATH="$DIR/node/bin:$PATH" "$NODE" script/install.js \
      --onnxruntime-node-install=cuda12) || setup_failed "onnxruntime-node's CUDA provider download (NuGet)"
fi
EP_OK=no
if [ -f "$BIN/libonnxruntime_providers_cuda.so" ] \
   && [ "$(sha256sum "$BIN/libonnxruntime_providers_cuda.so" | cut -c1-64)" = "$CUDA_EP_SHA" ] \
   && [ "$(sha256sum "$BIN/libonnxruntime_providers_shared.so" | cut -c1-64)" = "$SHARED_EP_SHA" ]; then EP_OK=yes; fi
echo "  CUDA provider present and matching its SHA-256: $EP_OK"

# ---------------------------------------------------------------------------------------------------- 4. the model
step "Fretformer 2's transcriber encoder"
MODEL="$DIR/downloads/encoder_fp32.onnx"
fetch "$MODEL_URL" "$MODEL" "$MODEL_SHA"

# ---------------------------------------------------------------------------------------------------- 5. the sessions
cat > "$DIR/run.cjs" <<'EOF'
// One session of the transcriber encoder on the given provider, then 5 runs on 64 beats of input; prints one JSON line.
const ort = require(process.argv[2]);
const [model, device] = [process.argv[3], process.argv[4]];
(async () => {
  const t0 = Date.now();
  const s = await ort.InferenceSession.create(model, { executionProviders: [device], logSeverityLevel: 0, logVerbosityLevel: 0 });
  const created = Date.now() - t0;
  const nb = 64, n = nb * 6 * 80 * 32, mel = new Float32Array(n);
  for (let i = 0; i < n; i++) mel[i] = Math.sin(i * 0.001);
  const feeds = { beat_mel: new ort.Tensor("float32", mel, [1, nb, 6, 80, 32]),
                  beat_mask: new ort.Tensor("bool", new Uint8Array(nb).fill(1), [1, nb]) };
  const runs = [];
  for (let k = 0; k < 5; k++) { const a = Date.now(); await s.run(feeds); runs.push(Date.now() - a); }
  console.log(JSON.stringify({ device, ok: true, create_ms: created, run_ms: runs }));
})().catch((e) => { console.log(JSON.stringify({ device, ok: false, error: String((e && e.message) || e).split("\n")[0] })); process.exit(1); });
EOF

session() {  # session DEVICE: runs run.cjs, ORT's log to logs/session-DEVICE.log; prints its JSON line
  local dev=$1
  LD_LIBRARY_PATH="$LIBDIRS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" "$NODE" "$DIR/run.cjs" \
    "$ORT_DIR/node_modules/onnxruntime-node" "$MODEL" "$dev" 2> "$LOG/session-$dev.log" | tail -n 1 || true
}
placements() {  # placements LOG: "<provider>=<nodes> ..." from ORT's "Node placements" lines
  grep -o -E '(All nodes|Node\(s\)) placed on \[[A-Za-z]+\]\. Number of nodes: [0-9]+' "$1" \
    | sed -E 's/.*\[([A-Za-z]+)\]\. Number of nodes: ([0-9]+)/\1=\2/' | sort -u | tr '\n' ' ' || true
}

VERDICT=PASS; REASON=""
CUDA_JSON='null'; CUDA_PLACE=""
if [ "$DEVICE" = cuda ]; then
  step "the CUDA session"
  if [ -n "$MISSING" ]; then
    VERDICT=FAIL; REASON="the CUDA 13 libraries are not all on the path (missing:$MISSING)"
  fi
  CUDA_JSON=$(session cuda); CUDA_JSON=${CUDA_JSON:-'{"device":"cuda","ok":false,"error":"no output"}'}
  CUDA_PLACE=$(placements "$LOG/session-cuda.log")
  echo "  $CUDA_JSON"
  echo "  node placements: ${CUDA_PLACE:-none logged}"
  LOADERR=$(grep -o -E 'Failed to load library[^]]*' "$LOG/session-cuda.log" | head -n 1 | sed -E 's#/[^ ]*/##' || true)
  if ! echo "$CUDA_JSON" | grep -q '"ok":true'; then
    VERDICT=FAIL; REASON="the CUDA session did not run: ${LOADERR:-$(echo "$CUDA_JSON" | sed -E 's/.*"error":"([^"]*)".*/\1/')}"
  elif ! echo "$CUDA_PLACE" | grep -q -E 'CUDAExecutionProvider=[1-9]'; then
    VERDICT=FAIL; REASON="the session ran, but no node was placed on CUDA (it fell back to the CPU): ${CUDA_PLACE:-no placement logged}"
  fi
fi
step "the CPU session (for comparison)"
CPU_JSON=$(session cpu); CPU_JSON=${CPU_JSON:-'{"device":"cpu","ok":false,"error":"no output"}'}
CPU_PLACE=$(placements "$LOG/session-cpu.log")
echo "  $CPU_JSON"
echo "  node placements: ${CPU_PLACE:-none logged}"
if [ "$DEVICE" = cpu ] && ! echo "$CPU_JSON" | grep -q '"ok":true'; then VERDICT=FAIL; REASON="the CPU session did not run"; fi

# ---------------------------------------------------------------------------------------------------- 6. the result
RESULT="$DIR/cuda13-result.json"
SP_DEVICE=$DEVICE SP_VERDICT=$VERDICT SP_REASON=$REASON SP_WSL=$IN_WSL SP_GPU=$GPU SP_DRIVER=$DRIVER \
SP_TORCH=$TORCH_JSON SP_LIBDIRS=$LIBDIRS SP_MISSING=$MISSING SP_LIBCUDA=$LIBCUDA SP_EP=$EP_OK \
SP_CUDA=$CUDA_JSON SP_CUDA_PLACE=$CUDA_PLACE SP_CPU=$CPU_JSON SP_CPU_PLACE=$CPU_PLACE \
SP_SECONDS=$(( $(date +%s) - START )) "$PY" - "$RESULT" <<'EOF'
import json, os, sys
e = os.environ
def j(text):
    try: return json.loads(text)
    except Exception: return text or None
r = {"spike": "cuda13-provider", "version": 1, "device_asked": e["SP_DEVICE"], "verdict": e["SP_VERDICT"],
     "reason": e["SP_REASON"], "wsl": e["SP_WSL"] == "yes", "gpu": e["SP_GPU"] or None, "driver": e["SP_DRIVER"] or None,
     "torch": j(e["SP_TORCH"]), "library_path": [d for d in e["SP_LIBDIRS"].split(":") if d],
     "missing_libraries": e["SP_MISSING"].split(), "libcuda_from_driver": e["SP_LIBCUDA"] == "yes",
     "cuda_provider_sha256_ok": e["SP_EP"] == "yes",
     "cuda_session": j(e["SP_CUDA"]), "cuda_placements": e["SP_CUDA_PLACE"].split(),
     "cpu_session": j(e["SP_CPU"]), "cpu_placements": e["SP_CPU_PLACE"].split(), "seconds": int(e["SP_SECONDS"])}
c, p = r["cuda_session"], r["cpu_session"]
if isinstance(c, dict) and isinstance(p, dict) and c.get("ok") and p.get("ok"):
    med = lambda xs: sorted(xs[1:])[len(xs[1:]) // 2]
    r["median_run_ms"] = {"cuda": med(c["run_ms"]), "cpu": med(p["run_ms"])}
    r["cpu_over_cuda"] = round(med(p["run_ms"]) / max(med(c["run_ms"]), 1), 1)
json.dump(r, open(sys.argv[1], "w"), indent=1)
EOF
if [ "$IN_WSL" = yes ] && command -v cmd.exe >/dev/null 2>&1; then
  WINHOME=$(cd /mnt/c && cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')
  if [ -n "$WINHOME" ] && [ -d "$(wslpath "$WINHOME")/Downloads" ]; then
    cp "$RESULT" "$(wslpath "$WINHOME")/Downloads/" && echo "copied to $WINHOME\\Downloads\\cuda13-result.json"
  fi
fi

echo
if [ "$VERDICT" = PASS ]; then
  if [ "$DEVICE" = cuda ]; then
    echo "PASS: onnxruntime-node's CUDA provider ran on the cu132 lane's CUDA 13 libraries ($CUDA_PLACE)."
  else
    echo "PASS (CPU path only: CUDA was not tried; run without --device cpu on the GPU PC)."
  fi
  echo "Send $RESULT. Then delete $DIR (rm -rf $DIR)."
  exit 0
fi
fail "$REASON"
echo "Send $RESULT and the folder $LOG (zip it). Then delete $DIR." >&2
exit 1
