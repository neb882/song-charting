#!/usr/bin/env bash
# run.sh <input audio file> <output folder>
# Runs dvar0/autochart's real engine (Fretformer 2: htdemucs_6s -> fine-tuned
# Beat This -> Fretformer 2, onnxruntime-node, CPU) headless and writes a Clone
# Hero song folder: notes.chart, song.ini, song.ogg (+ autochart_run/ logs).
# The heavy part runs under the shared CPU lock. Prints CPU seconds. Exits
# non-zero on failure. Env knobs: see ac_headless.cjs (AC_DIFFICULTIES, AC_SEED,
# AC_MAX_TOKENS, AC_TIMEOUT_S, AC_STALL_S, AC_TITLE, AC_ARTIST, AC_KEEP_WORK).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="${EVAL_LOCK:-$(cd "$HERE/../.." && pwd)/data/run.lock}"

if [ $# -ne 2 ]; then echo "usage: $0 <input audio file> <output folder>" >&2; exit 2; fi
IN="$(realpath "$1")"
OUT="$(realpath -m "$2")"
[ -f "$IN" ] || { echo "input not found: $IN" >&2; exit 2; }
[ -f "$HERE/models/fretformer-v2/manifest.json" ] || { echo "models missing: run $HERE/fetch_models.sh" >&2; exit 2; }
[ -d "$HERE/node_modules/onnxruntime-node" ] || { echo "onnxruntime-node missing: run npm install in $HERE" >&2; exit 2; }

WORK="$HERE/runs/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$WORK" "$(dirname "$LOCK")"
TIMES="$WORK/times.txt"

# bash's `time` counts user+sys of every reaped descendant (node wrapper,
# engine process, ffmpeg); waiting on the lock costs no CPU.
TIMEFORMAT='%U %S %R'
set +e
exec 3>&2
{ time flock "$LOCK" node "$HERE/ac_headless.cjs" --audio "$IN" --out "$OUT" --work "$WORK" 2>&3 ; } 2>"$TIMES"
rc=$?
exec 3>&-
set -e

read -r USER_S SYS_S REAL_S < <(tail -n 1 "$TIMES")
CPU_S=$(awk -v u="$USER_S" -v s="$SYS_S" 'BEGIN{printf "%.2f", u+s}')
echo "autochart CPU seconds: ${CPU_S} (user ${USER_S}, sys ${SYS_S}); wall incl. lock wait: ${REAL_S}s; exit ${rc}" >&2
if [ -d "$OUT/autochart_run" ]; then
  printf '{"cpu_seconds": %s, "user_seconds": %s, "sys_seconds": %s, "wall_seconds_incl_lock_wait": %s, "exit": %s}\n' \
    "$CPU_S" "$USER_S" "$SYS_S" "$REAL_S" "$rc" > "$OUT/autochart_run/cputime.json"
fi
if [ "${AC_KEEP_WORK:-0}" != "1" ] && [ $rc -eq 0 ]; then rm -rf "$WORK"; fi
if [ $rc -ne 0 ]; then echo "autochart FAILED (work dir kept: $WORK)" >&2; exit $rc; fi
for f in notes.chart song.ini song.ogg; do
  [ -s "$OUT/$f" ] || { echo "autochart: missing $OUT/$f" >&2; exit 1; }
done
echo "$OUT"
