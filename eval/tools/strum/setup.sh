#!/usr/bin/env bash
# setup.sh - reproduce the STRUM install used by run.sh (idempotent).
# Does NOT execute any STRUM code: clone, pip installs, weight downloads,
# symlinks, and restoring 2 YAMLs from checkpoint metadata (weights_only=True).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STRUM_COMMIT=9f420cb6550284d15188e9b69f27614ee62fa731
REPO="$HERE/src_dl/strum"

# 1. source, pinned
if [ ! -d "$REPO/.git" ]; then
  mkdir -p "$HERE/src_dl"; git clone https://github.com/opria123/strum "$REPO"
fi
git -C "$REPO" checkout -q "$STRUM_COMMIT"

# 2. venv: Python 3.12 (README: 3.11+; classifiers 3.11/3.12). torch/torchaudio
#    2.11.0 CPU wheels (torchaudio has no build for torch>2.11). Everything else
#    resolved as of 2026-05-11 (day after STRUM's last commit). basic-pitch is
#    installed --no-deps + onnxruntime: its TensorFlow<2.15.1 pin has no Py3.12
#    wheel, and STRUM's guitar_hybrid_v2 docstring names the ONNX backend.
#    wandb (pyproject dep) is training-only and not installed.
[ -x "$HERE/venv/bin/python" ] || uv venv --python 3.12 "$HERE/venv"
# GPU: TORCH_INDEX=https://download.pytorch.org/whl/cu128 (RTX 50-series needs CUDA 12.8+ builds)
TORCH_INDEX="${TORCH_INDEX:-https://download.pytorch.org/whl/cpu}"
uv pip install --python "$HERE/venv/bin/python" --index-url "$TORCH_INDEX" "torch==2.11.0" "torchaudio==2.11.0"
uv pip install --python "$HERE/venv/bin/python" --exclude-newer 2026-05-11T00:00:00Z -r "$HERE/req_pypi.txt"
uv pip install --python "$HERE/venv/bin/python" --no-deps "basic-pitch==0.4.0"

# 3. weights (HF opria123/strum @ 6f8997f), sha256-checked, flattened layout
"$HERE/fetch_weights.sh"
(cd "$HERE/weights_hf" && sha256sum -c --quiet ../weights_hf.sha256)
H="$HERE/weights_hf"; C="$REPO/checkpoints"; mkdir -p "$C"
ln_() { mkdir -p "$(dirname "$C/$2")"; ln -sfn "$H/$1" "$C/$2"; }
for d in drums_v14/best.pt drums_mc_onset/best.pt drums_phase3/best.pt \
         drums_cymbal_onset/best_union_f1.pt tom_refinement_demucs/best.pt; do ln_ "drums/$d" "$d"; done
for d in onset_classifier onset_classifier_v4 onset_classifier_v6 onset_classifier_v12_clean \
         onset_classifier_v12c_community onset_classifier_v15 onset_classifier_v16 onset_classifier_v17; do
  ln_ "drums_classifier_ensemble/$d/best_f1.pt" "$d/best_f1.pt"; done
ln_ guitar/guitar_v2_onset/best.pt guitar_v2/guitar_v2_onset/best.pt
ln_ guitar/fret_mapper_v4.pt fret_mapper_v4.pt
ln_ section_classifier/best.pt section_classifier/best.pt

# 4. htdemucs_6s weights for demucs (TORCH_HOME), hash in file name checked
mkdir -p "$HERE/torch_home/hub/checkpoints"
TH="$HERE/torch_home/hub/checkpoints/5c90dfd2-34c22ccb.th"
[ -s "$TH" ] || curl -fsSL -o "$TH" https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/5c90dfd2-34c22ccb.th
sha256sum "$TH" | grep -q '^34c22ccb' || { echo "htdemucs_6s hash mismatch" >&2; exit 1; }

# 5. runtime roots (cwd for STRUM's relative configs/ + checkpoints/ paths)
mkdir -p "$HERE/rt/as_shipped" "$HERE/rt/fixed/configs"
ln -sfn "$REPO/configs" "$HERE/rt/as_shipped/configs"
ln -sfn "$REPO/checkpoints" "$HERE/rt/as_shipped/checkpoints"
for f in "$REPO"/configs/*; do ln -sfn "$f" "$HERE/rt/fixed/configs/$(basename "$f")"; done
ln -sfn "$REPO/checkpoints" "$HERE/rt/fixed/checkpoints"
(cd /tmp && "$HERE/venv/bin/python" -I "$HERE/wrap/restore_configs.py" "$REPO/checkpoints" "$HERE/rt/fixed/configs")
echo "setup ok"
