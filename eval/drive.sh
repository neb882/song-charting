#!/usr/bin/env bash
# drive.sh: run each tool on every reference song, then the test song, one job at a time, and score each run.
# Resumable: runs that already have a score (or, for the test song, a chart) are skipped.
#   TOOLS="autochart strum chartgen"   which tools, in order
#   AC_DEVICE / STRUM_DEVICE           cpu (default) or cuda; chartgen picks the GPU by itself
#   MEM_WAIT_MB                        wait for this much free RAM before each job (optional)
#   SKIP="strum:test_song ..."         tool:song pairs to leave out
# On an NVIDIA machine, start it through gpu.sh, which checks the GPU and runs it detached.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${EVAL_DATA:-$HERE/data}"
PY="${EVAL_PY:-$HERE/.venv/bin/python}"
TOOLS="${TOOLS:-autochart strum chartgen}"
mkdir -p "$DATA/runs"
LOG="$DATA/runs/driver.log"
SONGS="$(python3 -c "import json,sys; print(' '.join(s['id'] for s in json.load(open(sys.argv[1]))))" "$DATA/refs/songs.json")"
[ -f "$DATA/refs/test_song/input.wav" ] && SONGS="$SONGS test_song"
log() { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }
for tool in $TOOLS; do
  for id in $SONGS; do
    out="$DATA/runs/$tool/$id"; mkdir -p "$DATA/runs/$tool"
    if [ "$id" = test_song ]; then { [ -f "$out/notes.chart" ] || [ -f "$out/notes.mid" ]; } && continue
    else [ -f "$out.score.json" ] && continue; fi
    case " ${SKIP:-} " in *" $tool:$id "*) log "SKIP  $tool $id"; continue ;; esac
    if [ -n "${MEM_WAIT_MB:-}" ]; then
      while [ "$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)" -lt "$MEM_WAIT_MB" ]; do sleep 20; done
    fi
    log "START $tool $id"
    rm -rf "$out"
    case $tool in
      autochart) AC_DIFFICULTIES=all timeout 3h "$HERE/tools/autochart/run.sh" "$DATA/refs/$id/input.wav" "$out" > "$out.log" 2>&1 ;;
      strum)     STRUM_MODE="${STRUM_MODE:-as_shipped}" timeout 3h "$HERE/tools/strum/run.sh" "$DATA/refs/$id/input.wav" "$out" > "$out.log" 2>&1 ;;
      chartgen)  CG_NAME=$id timeout 3h "$HERE/tools/chartgen/run.sh" "$DATA/refs/$id/input.wav" "$out" > "$out.log" 2>&1 ;;
    esac
    rc=$?
    case $rc in 137) note=" (killed: most likely out of memory)" ;; 124) note=" (timed out after 3 h)" ;; *) note= ;; esac
    log "END   $tool $id rc=$rc$note $(grep -o 'CPU seconds: [0-9.]*' "$out.log" | tail -1) $(grep -o 'wall incl. lock wait: [0-9.]*s' "$out.log" | tail -1)"
    if [ $rc -eq 0 ] && [ "$id" != test_song ]; then
      "$PY" -I "$HERE/scorer/score.py" --ref "$DATA/refs/$id" --cand "$out" --input "$DATA/refs/$id/input.wav" --out "$out.score.json" > "$out.score.txt" 2>&1
      log "SCORE $tool $id rc=$? $(tail -1 "$out.score.txt" | cut -c1-300)"
    fi
  done
done
"$PY" -I "$HERE/scorecard.py" "$DATA" | tee "$DATA/runs/SCORECARD.md"
log "ALL DONE"
