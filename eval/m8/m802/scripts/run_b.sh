#!/bin/bash
# run_b.sh PHASE LABEL...: build_b.py PHASE for each label as a tools/heavy.sh job; refuses under 0.5 GB free on /.
# Appends to B/build.log (labels only); B/<PHASE>.DONE at the end.
M=$(dirname "$(dirname "$(readlink -f "$0")")"); LOG=$M/B/build.log; ph=$1; shift
cd <checkout> || exit 2
for l in "$@"; do
  free_kb=$(df -Pk / | awk 'NR==2{print $4}'); [ "$free_kb" -lt 524288 ] && { echo "$(date -u +%T) REFUSED disk before $l" >> $LOG; exit 1; }
  shm_kb=$(du -sk <shm>/m8 | cut -f1); [ "$shm_kb" -gt 900000 ] && { echo "$(date -u +%T) REFUSED shm before $l" >> $LOG; exit 1; }
  echo "$(date -u +%T) start $ph $l" >> $LOG
  SONGCHARTER_HEAVY_MIN_FREE_GB=1 tools/heavy.sh .venv/bin/python $M/scripts/build_b.py $ph $l >> $LOG 2> >(tail -c 1500 > $M/B/err.$ph.$l) || echo "$(date -u +%T) FAILED $ph $l" >> $LOG
done
echo "$(date -u +%T) DONE $ph" >> $LOG; touch $M/B/$ph.DONE
