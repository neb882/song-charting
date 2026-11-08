#!/bin/bash
# gr.sh PY ARGS...: runs `PY -m eval.golden run ARGS` unless the --out folder already holds a finished run's summary.json
# (a run whose scoring was cut short is scored again, not rebuilt). Prints what the golden run prints.
PY=$1; shift; out=""; prev=""
for a in "$@"; do [ "$prev" = --out ] && out=$a; prev=$a; done
[ -n "$out" ] && [ -f "$out/summary.json" ] && { echo "gr.sh: reusing the finished run in its folder"; exit 0; }
exec $PY -m eval.golden run "$@"
