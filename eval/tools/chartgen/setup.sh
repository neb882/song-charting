#!/usr/bin/env bash
# setup.sh - install Mechazawa/chartgen (idempotent). Does not run chartgen code.
# Upstream pins (requirements.txt) installed --no-deps with the lyrics packages left out (lyrics are off).
# GPU: TORCH_INDEX=https://download.pytorch.org/whl/cu128 (RTX 50-series needs CUDA 12.8+ builds).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMIT=383d50c03695b7abdec7b451ecd34c0920b4f932
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cpu}"
[ -d "$HERE/src/.git" ] || git clone https://github.com/Mechazawa/chartgen "$HERE/src"
git -C "$HERE/src" checkout -q "$COMMIT"
[ -x "$HERE/venv/bin/python" ] || uv venv --python 3.13 "$HERE/venv"
P=(--python "$HERE/venv/bin/python")
uv pip install "${P[@]}" --index-url "$TORCH_INDEX" "torch==2.9.1"
uv pip install "${P[@]}" --no-deps -r "$HERE/req_nolyrics.txt"
uv pip install "${P[@]}" --no-deps "basic-pitch==0.4.0"
uv pip install "${P[@]}" six importlib-resources flatbuffers protobuf absl-py standard-aifc standard-sunau \
  standard-chunk audioop-lts blinker itsdangerous werkzeug
SP=$("$HERE/venv/bin/python" -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
echo "$HERE/src" > "$SP/chartgen_src.pth"
"$HERE/fetch_models.sh"
echo "setup ok"
