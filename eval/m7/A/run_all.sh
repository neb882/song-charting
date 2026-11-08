#!/bin/bash
# run_all.sh: part A's four arms in turn (run_arm.sh each), then a line ALLDONE or FAILED.
for a in base A1 A2 A3; do <scratchpad>/m7/m7-01/A/scripts/run_arm.sh $a || { echo "FAILED $a"; exit 1; }; done; echo ALLDONE
