#!/bin/bash
# run_c.sh: build_c.py for each of the 23 labels as one tools/heavy.sh job each; refuses under 0.5 GB free on / or
# with <shm>/m8 over 900 MB. Appends labels and seconds to C/build.log; C/build.DONE at the end.
M=$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")"); LOG=$M/C/build.log
cd <checkout> || exit 2
for l in all_the_small_things creep drunk_drivers kimochi_warui lucretia take_me_out break pm2 sooth troop s01 s02 s03 s04 s05 s06 s07 s08 s09 s10 s11 s12 s13; do
  free_kb=$(df -Pk / | awk 'NR==2{print $4}'); [ "$free_kb" -lt 524288 ] && { echo "$(date -u +%T) REFUSED disk before $l" >> $LOG; exit 1; }
  shm_kb=$(du -sk <shm>/m8 | cut -f1); [ "$shm_kb" -gt 900000 ] && { echo "$(date -u +%T) REFUSED shm before $l" >> $LOG; exit 1; }
  echo "$(date -u +%T) start $l" >> $LOG
  SONGCHARTER_HEAVY_MIN_FREE_GB=1 tools/heavy.sh .venv/bin/python $M/C/scripts/build_c.py $l >> $LOG 2>&1 || echo "$(date -u +%T) FAILED $l" >> $LOG
done
echo "$(date -u +%T) DONE" >> $LOG; touch $M/C/build.DONE
