#!/bin/bash
# build_all.sh MAX_MIN LABEL...: build_song.py for each label (as a tools/heavy.sh job) once gen.log says its takes are
# done (skips labels whose arms/<label>.json has f3); stops starting after MAX_MIN minutes. Appends to build.log; DONE.
C=$(dirname "$(readlink -f "$0")"); LOG=$C/build.log; max=$1; shift; t0=$(date +%s)
export EVAL_DATA=$DEV/eval SONGCHARTER_GOLDEN=$DEV/golden SONGCHARTER_AUTOCHART=<checkout>/eval/tools/autochart SONGCHARTER_ALLIN1_PYTHON=$DEV/allin1/bin/python SONGCHARTER_HEAVY_MIN_FREE_GB=1
for l in "$@"; do
  grep -q '"q05"' $C/arms/$l.json 2>/dev/null && continue
  until grep -q "^$l scratch" $C/gen.log; do
    [ $(( ($(date +%s) - t0) / 60 )) -ge "$max" ] && { echo "$(date -u +%T) STOP time, waiting for $l" >> $LOG; exit 0; }
    sleep 30; done
  [ $(( ($(date +%s) - t0) / 60 )) -ge "$max" ] && { echo "$(date -u +%T) STOP time, next $l" >> $LOG; exit 0; }
  free_kb=$(df -Pk / | awk 'NR==2{print $4}'); [ "$free_kb" -lt 524288 ] && { echo "REFUSED disk" >> $LOG; exit 1; }
  echo "$(date -u +%T) start $l" >> $LOG
  cd <checkout> && tools/heavy.sh <checkout>/.venv/bin/python $C/build_song.py $l >> $LOG 2> >(tail -c 2000 > $C/build.$l.err) || echo "$(date -u +%T) FAILED $l" >> $LOG
done
echo "$(date -u +%T) DONE" >> $LOG
