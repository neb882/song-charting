#!/bin/bash
# gen_all.sh MAX_MIN LABEL...: gen_one.py for each label in order, each a tools/heavy.sh job, waiting for 6 GB RAM free
# and refusing under 0.5 GB disk; stops starting songs after MAX_MIN minutes. Appends to gen.log; DONE line at the end.
C=$(dirname "$(readlink -f "$0")"); LOG=$C/gen.log; max=$1; shift; t0=$(date +%s)
export EVAL_DATA=$DEV/eval SONGCHARTER_GOLDEN=$DEV/golden SONGCHARTER_AUTOCHART=<checkout>/eval/tools/autochart SONGCHARTER_HEAVY_MIN_FREE_GB=1 PYTHONPATH=<wt>/orch
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 NUMBA_NUM_THREADS=2
for l in "$@"; do
  if [ $(( ($(date +%s) - t0) / 60 )) -ge "$max" ]; then echo "$(date -u +%T) STOP time, next $l" >> $LOG; exit 0; fi
  while [ "$(free -m | awk '/Mem:/{print $7}')" -lt 6144 ]; do sleep 30; done
  free_kb=$(df -Pk / | awk 'NR==2{print $4}'); if [ "$free_kb" -lt 524288 ]; then echo "$(date -u +%T) REFUSED disk" >> $LOG; exit 1; fi
  echo "$(date -u +%T) start $l" >> $LOG
  cd <checkout> && tools/heavy.sh <checkout>/.venv/bin/python $C/gen_one.py $l >> $LOG 2> >(tail -c 2000 > $C/gen.$l.err) || echo "$(date -u +%T) FAILED $l" >> $LOG
done
echo "$(date -u +%T) DONE $*" >> $LOG
