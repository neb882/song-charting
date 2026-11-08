#!/bin/bash
# run_extract.sh: extract.py over the 23 songs (env M8T_* and SONGCHARTER_SCAN_CHART set by the caller); prints extract.py's lines.
cd "$(dirname "$0")"
for l in r01 r02 r03 r04 r05 r06 break pm2 sooth troop s01 s02 s03 s04 s05 s06 s07 s08 s09 s10 s11 s12 s13; do
  "$M8T_PY" extract.py $l || echo "$l FAILED"
done
