#!/bin/bash
# run_pipe.sh: pipe.py for the 15 remaining takes, one after the other (each assemble queued through tools/heavy.sh).
W=$(dirname "$(dirname "$(readlink -f "$0")")")
cd $W
for arm in base hot dense5 dense6; do for seed in 20260609 101 202 303; do
  [ -f out/pipe/${arm}_${seed}.json ] && continue
  EVAL_DATA=$DEV/eval PYTHONDONTWRITEBYTECODE=1 <checkout>/.venv/bin/python -I scripts/pipe.py $arm $seed >> out/pipe.log 2>&1 || echo "FAILED $arm $seed" >> out/pipe.log
done; done
echo DONE >> out/pipe.log
