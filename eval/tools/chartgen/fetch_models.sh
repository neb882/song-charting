#!/usr/bin/env bash
# fetch_models.sh - download chartgen's stem-separator weights (data only, no code run)
# into this folder, pinned to a Hugging Face revision and verified by sha256.
#   BS-Rofo-SW-Fixed.ckpt  <- huggingface.co/enerjazzer/BS-ROFO-SW-Fixed @ REV
#   (the URL bs-roformer-infer 0.1.5 uses; sha256/size from its data/checksums.json)
# Config: bs-roformer-infer ships BS-Rofo-SW-Fixed.yaml inside the package and
# copies that one; we do the same.
# Basic Pitch's ONNX model ships inside the basic-pitch wheel; the prominence
# and solo models ship inside the chartgen repo. Lyrics models are not fetched
# (lyrics are turned off).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REV=a443a2985534b3bc815ef54a5d446c6a0390f974
SHA=24e7d35ee9c64415673d3fd33e06a67cac2c103c5df6267ba1576459c775916e
SIZE=699412152
DIR="$HERE/models/bs-roformer/roformer-model-bs-roformer-sw-by-jarredou"
mkdir -p "$DIR"
CK="$DIR/BS-Rofo-SW-Fixed.ckpt"
if [ ! -f "$CK" ] || [ "$(stat -c %s "$CK")" != "$SIZE" ]; then
  curl -fL --retry 3 -o "$CK.part" "https://huggingface.co/enerjazzer/BS-ROFO-SW-Fixed/resolve/$REV/BS-Rofo-SW-Fixed.ckpt"
  mv "$CK.part" "$CK"
fi
echo "$SHA  $CK" | sha256sum -c -
cp "$HERE"/venv/lib/python3.*/site-packages/bs_roformer/configs/BS-Rofo-SW-Fixed.yaml "$DIR/BS-Rofo-SW-Fixed.yaml"
echo "models ready in $HERE/models"
