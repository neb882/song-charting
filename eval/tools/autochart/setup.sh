#!/usr/bin/env bash
# setup.sh - install dvar0/autochart's engine for headless runs (idempotent). Does not run autochart code.
# GPU: run.sh with AC_DEVICE=cuda. onnxruntime-node needs its CUDA provider on Linux; if the engine log says
# "falling back to CPU", reinstall onnxruntime-node with its CUDA option (see the onnxruntime-node README) or try
# AC_DEVICE=webgpu.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMIT=b5a41e8e44db84d4c7288c946cf35aa2264dcbf5
[ -d "$HERE/src/.git" ] || git clone https://github.com/dvar0/autochart "$HERE/src"
git -C "$HERE/src" checkout -q "$COMMIT"
(cd "$HERE" && npm ci --no-audit --no-fund)
"$HERE/fetch_models.sh"
echo "setup ok"
