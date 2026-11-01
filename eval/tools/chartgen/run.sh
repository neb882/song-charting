#!/usr/bin/env bash
# run.sh <input audio file> <output folder>
#
# Runs Mechazawa/chartgen's normal CLI pipeline (python -m chartgen) on CPU and
# writes a Clone Hero song folder to <output folder>: notes.chart, song.ini and
# the audio chartgen staged (song.mp3/.ogg/.opus copied as-is, anything else -
# e.g. WAV - transcoded to song.opus at 48 kHz), plus album.png if the input has
# embedded art. Run logs go to <output folder>/chartgen_run/.
#
# Settings: chartgen defaults (16th grid, BS-RoFormer SW six-stem separation,
# followed-instrument timeline, taps, solos, HOPOs, star power, sections, ...)
# with ONE change: --no-lyrics (no LRCLIB lookup, no faster-whisper vocal
# transcription). Lyric/phrase events are also stripped from notes.chart if any
# appear; their text is never printed.
#
# A fresh chartgen cache dir is used per run, so stems/transcriptions are never
# reused and the CPU time is that of a cold run (models are pre-fetched by
# fetch_models.sh; the separator still loads its 700 MB checkpoint each run).
#
# The heavy part runs under the shared CPU lock. Prints CPU seconds (user+sys
# of chartgen and every child it reaps; lock waiting costs none). Exits
# non-zero on failure.
#
# Env knobs: CG_NAME (song title, default: input file stem), CG_ARTIST
# (default "Unknown"), CG_KEEP_WORK=1 keeps the per-run work dir.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="${EVAL_LOCK:-$(cd "$HERE/../.." && pwd)/data/run.lock}"
PY="$HERE/venv/bin/python"
CKPT="$HERE/models/bs-roformer/roformer-model-bs-roformer-sw-by-jarredou/BS-Rofo-SW-Fixed.ckpt"

if [ $# -ne 2 ]; then echo "usage: $0 <input audio file> <output folder>" >&2; exit 2; fi
IN="$(realpath "$1")"
OUT="$(realpath -m "$2")"
[ -f "$IN" ] || { echo "input not found: $IN" >&2; exit 2; }
[ -x "$PY" ] || { echo "venv missing: $PY" >&2; exit 2; }
[ -f "$CKPT" ] || { echo "separator weights missing: run $HERE/fetch_models.sh" >&2; exit 2; }

WORK="$HERE/runs/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$WORK/out" "$WORK/cache" "$(dirname "$LOCK")"
TIMES="$WORK/times.txt"
LOG="$WORK/chartgen.log"

# Keep every model/cache path inside this folder; nothing goes to ~/.cache.
export BS_ROFORMER_MODELS_PATH="$HERE/models/bs-roformer"
export CHARTGEN_CACHE_DIR="$WORK/cache"
export TORCH_HOME="$HERE/models/torch"          # only used if chartgen falls back to Demucs
export NUMBA_CACHE_DIR="$HERE/models/numba_cache"
export XDG_CACHE_HOME="$HERE/models/xdg_cache"
export PYTHONUNBUFFERED=1

NAME="${CG_NAME:-$(basename "${IN%.*}")}"
ARTIST="${CG_ARTIST:-Unknown}"
CMD=("$PY" -I -m chartgen "$IN" -o "$WORK/out" --no-lyrics --name "$NAME" --artist "$ARTIST")
printf '%q ' "${CMD[@]}" > "$WORK/cmd.txt"; echo >> "$WORK/cmd.txt"

cd "$WORK"
TIMEFORMAT='%U %S %R'
set +e
{ time ( flock "$LOCK" "${CMD[@]}" 2>&1 | tee "$LOG"; exit "${PIPESTATUS[0]}" ) ; } 2> "$TIMES"
rc=$?
set -e

read -r USER_S SYS_S REAL_S < <(tail -n 1 "$TIMES")
CPU_S=$(awk -v u="$USER_S" -v s="$SYS_S" 'BEGIN{printf "%.2f", u+s}')
echo "chartgen CPU seconds: ${CPU_S} (user ${USER_S}, sys ${SYS_S}); wall incl. lock wait: ${REAL_S}s; exit ${rc}" >&2

fail() { echo "run.sh: $*" >&2; echo "work dir kept: $WORK" >&2; exit 1; }
[ "$rc" -eq 0 ] || fail "chartgen exited with $rc (log: $LOG)"

mapfile -t SONGS < <(find "$WORK/out" -mindepth 1 -maxdepth 1 -type d ! -name _downloads)
[ "${#SONGS[@]}" -eq 1 ] || fail "expected one song folder in $WORK/out, found ${#SONGS[@]}"
SONG="${SONGS[0]}"
[ -f "$SONG/notes.chart" ] || fail "no notes.chart in $SONG"
[ -f "$SONG/song.ini" ] || fail "no song.ini in $SONG"
ls "$SONG"/song.* >/dev/null 2>&1 || fail "no song.* audio in $SONG"

mkdir -p "$OUT"
cp -a "$SONG"/. "$OUT"/

# Vocals are out of scope: drop any lyric/phrase events (there should be none
# with --no-lyrics). Count only; never print their text.
NLYR=$(grep -cE '= E "(lyric |phrase_start|phrase_end)' "$OUT/notes.chart" || true)
if [ "${NLYR:-0}" -gt 0 ]; then
  sed -i -E '/= E "(lyric |phrase_start|phrase_end)/d' "$OUT/notes.chart"
fi
echo "lyric/phrase events removed from notes.chart: ${NLYR:-0}" >&2

mkdir -p "$OUT/chartgen_run"
cp "$LOG" "$WORK/cmd.txt" "$OUT/chartgen_run/"
printf '{"cpu_seconds": %s, "user_seconds": %s, "sys_seconds": %s, "wall_seconds_incl_lock_wait": %s, "exit": %s, "lyric_events_removed": %s, "chartgen_commit": "%s"}\n' \
  "$CPU_S" "$USER_S" "$SYS_S" "$REAL_S" "$rc" "${NLYR:-0}" \
  "$(git -C "$HERE/src" rev-parse HEAD 2>/dev/null || echo unknown)" > "$OUT/chartgen_run/cputime.json"

[ "${CG_KEEP_WORK:-0}" = "1" ] || rm -rf "$WORK"
echo "song folder: $OUT" >&2
