#!/bin/bash
# supervise.sh: waits for a running run_c.sh to end, then reruns it (resumable) until C/build.DONE exists; prints nothing.
M=$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")")
for i in 1 2 3; do
  while pgrep -f "C/scripts/run_c.sh" >/dev/null; do sleep 30; done
  [ -f $M/C/build.DONE ] && exit 0
  $M/C/scripts/run_c.sh
done
