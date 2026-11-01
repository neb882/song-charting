#!/usr/bin/env bash
# run.sh <input audio file> <output folder>
#
# Runs STRUM (github.com/opria123/strum @ 9f420cb, weights HF opria123/strum @
# 6f8997f) end to end on CPU via its own full pipeline, scripts/batch_pipeline.py
# (htdemucs_6s separation -> drums V14 onset + classifier ensemble + phase3 +
# tom refinement; guitar/bass hybrid V2 onset CRNN + basic-pitch(ONNX) + rule
# fret mapping -> notes.mid, song.ini, song.ogg). Vocals OFF (--no-vocals, no
# Whisper, no lyrics); keys OFF (upstream default).
#
# Writes a Clone Hero folder: notes.mid, song.ini, song.ogg (+ strum_run/ with
# the log, batch_results.json and meta.json). The heavy part runs under the
# shared CPU lock. Prints CPU seconds. Exits non-zero on failure, including a
# partial failure (an instrument stage raising) unless STRUM_ALLOW_PARTIAL=1.
#
# IMPORTANT: STRUM trims the first phase_offset_ms of the audio when it writes
# song.ogg and shifts every note by the same amount (tick 0 = first downbeat).
# Chart time t therefore corresponds to input-audio time t + phase_offset_ms.
# meta.json records phase_offset_ms so a scorer can map back.
#
# Env knobs:
#   STRUM_MODE=fixed (default)  restore the 2 ensemble YAMLs missing upstream
#                               (V4, V17) from the checkpoints' embedded config
#   STRUM_MODE=as_shipped       run exactly what the public repo ships (V4/V17
#                               skipped -> Crash class has no model weight)
#   STRUM_ALLOW_NET_METADATA=1  keep upstream MusicBrainz/iTunes lookups
#   STRUM_KEEP_WORK=1           keep the work dir (stems are deleted upstream)
#   any upstream STRUM_* variable is passed through unchanged.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCK="${EVAL_LOCK:-$(cd "$HERE/../.." && pwd)/data/run.lock}"
PY="$HERE/venv/bin/python"
REPO="$HERE/src_dl/strum"
MODE="${STRUM_MODE:-fixed}"
RT="$HERE/rt/$MODE"
STRUM_COMMIT=9f420cb6550284d15188e9b69f27614ee62fa731
WEIGHTS_REV=6f8997f53c6eb04e0cb38f679c593d27ae89ab7f

if [ $# -ne 2 ]; then echo "usage: $0 <input audio file> <output folder>" >&2; exit 2; fi
IN="$(realpath "$1")"
OUT="$(realpath -m "$2")"
[ -f "$IN" ] || { echo "input not found: $IN" >&2; exit 2; }
[ -x "$PY" ] || { echo "venv missing: $PY" >&2; exit 2; }
[ -d "$RT/configs" ] && [ -e "$RT/checkpoints/drums_v14/best.pt" ] || {
  echo "runtime root $RT incomplete (STRUM_MODE=$MODE); see $HERE/setup.sh" >&2; exit 2; }
case "${IN,,}" in *.wav|*.mp3|*.ogg|*.flac|*.m4a) ;; *) echo "unsupported extension: $IN" >&2; exit 2;; esac

WORK="$HERE/runs/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$WORK/in" "$WORK/out"
# Stage input under a neutral name: STRUM derives artist/title from the file
# name ("A - B" triggers MusicBrainz lookups); "input" -> "Unknown Artist - input".
EXT="${IN##*.}"; EXT="${EXT,,}"
ln -s "$IN" "$WORK/in/input.$EXT"
LOG="$WORK/strum.log"
TIMES="$WORK/times.txt"

export TORCH_HOME="$HERE/torch_home"      # htdemucs_6s weights cached here
export PYTHONDONTWRITEBYTECODE=1
export WANDB_MODE=disabled
export TF_CPP_MIN_LOG_LEVEL=3

# bash `time` counts user+sys of every reaped descendant (python + ffmpeg);
# waiting on the lock costs no CPU.
TIMEFORMAT='%U %S %R'
set +e
{ time (cd "$RT" && flock "$LOCK" "$PY" -I "$HERE/wrap/strum_launch.py" "$REPO" \
      "$WORK/in" "$WORK/out" --no-vocals --device "${STRUM_DEVICE:-cpu}" >"$LOG" 2>&1) ; } 2>"$TIMES"
rc=$?
set -e
read -r USER_S SYS_S REAL_S < <(tail -n 1 "$TIMES")
CPU_S=$(awk -v u="$USER_S" -v s="$SYS_S" 'BEGIN{printf "%.2f", u+s}')
echo "strum CPU seconds: ${CPU_S} (user ${USER_S}, sys ${SYS_S}); wall incl. lock wait: ${REAL_S}s; exit ${rc}" >&2

SONG_DIR="$WORK/out/Unknown Artist - input"
fail() { echo "strum FAILED: $1 (work dir kept: $WORK; log: $LOG)" >&2; tail -n 25 "$LOG" >&2 || true; exit "${2:-1}"; }
[ $rc -eq 0 ] || fail "pipeline exit $rc" $rc
[ -f "$WORK/out/batch_results.json" ] || fail "no batch_results.json"
for f in notes.mid song.ini song.ogg; do [ -s "$SONG_DIR/$f" ] || fail "missing $f"; done

# Post-run checks + meta (light; no lock). Also refuses any vocals/lyrics track.
set +e
"$PY" -I - "$WORK" "$SONG_DIR" "$MODE" "$CPU_S" "$USER_S" "$SYS_S" "$REAL_S" \
      "$IN" "$STRUM_COMMIT" "$WEIGHTS_REV" "${STRUM_ALLOW_PARTIAL:-0}" <<'PYEOF'
import json, re, sys
from pathlib import Path
import mido
work, song, mode, cpu, us, ss, real, src, commit, wrev, allow_partial = sys.argv[1:]
work, song = Path(work), Path(song)
log = (work / "strum.log").read_text(errors="replace")
res = json.loads((work / "out" / "batch_results.json").read_text())[0]
m = re.search(r"BPM \(grid-aligned\):\s*([\d.]+)\s+phase_offset=([\-\d.]+)ms", log)
bpm_grid = float(m.group(1)) if m else None
phase = float(m.group(2)) if m else 0.0
applied = re.search(r"Phase align: shifting charts by -([\d.]+)ms", log)
ens = re.search(r"Loaded (\d+) ensemble models", log)
mid = mido.MidiFile(song / "notes.mid")
tracks = {}
for t in mid.tracks:
    name = next((msg.name for msg in t if msg.type == "track_name"), "")
    tracks[name] = sum(1 for msg in t if msg.type == "note_on" and msg.velocity > 0)
problems = []
if any("VOCAL" in n.upper() or "HARM" in n.upper() for n in tracks):
    problems.append("vocals track present (should be off)")
if "Could not load drums models" in log or "Drums models not loaded" in log:
    problems.append("drum models failed to load")
for pat in (r"⚠ (Drums|Guitar|Bass)[^\n]*failed[^\n]*", r"Traceback \(most recent call last\)"):
    for mm in re.finditer(pat, log):
        problems.append(mm.group(0)[:200])
if res.get("error"):
    problems.append("batch_results error: " + str(res["error"]))
warn = [l.strip() for l in log.splitlines() if "skipped" in l or "missing" in l.lower()]
meta = {
    "tool": "STRUM", "strum_commit": commit, "weights_hf_revision": wrev,
    "mode": mode, "input": src, "phase_offset_ms": phase,
    "phase_shift_applied": bool(applied), "tempo_bpm_grid_aligned": bpm_grid,
    "audio_written": "song.ogg = input with first phase_offset_ms trimmed (ffmpeg -ss), libvorbis q6",
    "chart_time_to_input_time": "t_input = t_chart + phase_offset_ms/1000",
    "ensemble_models_loaded": int(ens.group(1)) if ens else None,
    "midi_tracks_note_on_counts": tracks,
    "batch_result": res, "upstream_warnings": warn[:40], "problems": problems,
    "cpu_seconds": float(cpu), "user_seconds": float(us), "sys_seconds": float(ss),
    "wall_seconds_incl_lock_wait": float(real),
}
(work / "meta.json").write_text(json.dumps(meta, indent=2))
print(json.dumps({k: meta[k] for k in ("phase_offset_ms", "tempo_bpm_grid_aligned",
      "ensemble_models_loaded", "midi_tracks_note_on_counts", "problems")}), file=sys.stderr)
sys.exit(3 if (problems and allow_partial != "1") else 0)
PYEOF
chk=$?
set -e
[ $chk -eq 0 ] || fail "post-run checks (see problems in $WORK/meta.json)" $chk

mkdir -p "$OUT/strum_run"
cp -f "$SONG_DIR"/notes.mid "$SONG_DIR"/song.ini "$SONG_DIR"/song.ogg "$OUT/"
for a in "$SONG_DIR"/album.*; do [ -e "$a" ] && cp -f "$a" "$OUT/"; done
cp -f "$LOG" "$WORK/meta.json" "$WORK/out/batch_results.json" "$OUT/strum_run/"
if [ "${STRUM_KEEP_WORK:-0}" != "1" ]; then rm -rf "$WORK"; fi
echo "$OUT"
