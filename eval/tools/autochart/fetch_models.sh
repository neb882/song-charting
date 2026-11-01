#!/bin/bash
# Download the Fretformer 2 component (the app's default generator) from the
# Hugging Face revision the app pins, then verify every file's size + SHA-256
# against autochart's own engine/catalog.json. Bundled license files are copied
# from the app's engine/licenses (the app does the same: source "bundled-license").
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/src"
MODELS="$HERE/models"
REV=8a88855d745f0b508f68ac606d7cbdac2878c87d
BASE="https://huggingface.co/Dvaro/autochart-models/resolve/$REV"
COMPONENT="${1:-fretformer-2-onnx}"
mkdir -p "$MODELS"
python3 -I - "$SRC/engine/catalog.json" "$COMPONENT" > "$MODELS/.filelist.$COMPONENT" <<'PY'
import json, sys
cat = json.load(open(sys.argv[1]))
comps = cat["components"]; comps = comps if isinstance(comps, list) else list(comps.values())
comp = next(c for c in comps if c["id"] == sys.argv[2])
for f in comp["files"]:
    print(f["source"], f["path"], f["size"], f["sha256"])
PY
while read -r source path size sha; do
  dest="$MODELS/$path"; mkdir -p "$(dirname "$dest")"
  if [ "$source" = "bundled-license" ]; then
    cp "$SRC/engine/$path" "$dest"
  elif [ ! -s "$dest" ] || [ "$(stat -c %s "$dest")" != "$size" ]; then
    curl -sS -L --fail --retry 3 --max-time 1800 -o "$dest.part" "$BASE/$path"
    mv "$dest.part" "$dest"
  fi
  got_size=$(stat -c %s "$dest"); got_sha=$(sha256sum "$dest" | cut -d' ' -f1)
  if [ "$got_size" != "$size" ] || [ "$got_sha" != "$sha" ]; then
    echo "CHECKSUM MISMATCH $path size=$got_size sha=$got_sha expected $size $sha" >&2; exit 1
  fi
  echo "ok $source $path $size $sha"
done < "$MODELS/.filelist.$COMPONENT"
curl -sS -L --fail -o "$MODELS/HF_README_$REV.md" "$BASE/README.md"
echo "revision $REV verified ($COMPONENT)"
