#!/bin/bash
# run_arm.sh ARM: builds part A's arm ARM (a patched worktree of main) over the references, the stress set and the
# 20-song set into <shm>/m7/ARM-<set>, scores each, keeps summary/scores and each song's notes.chart+report.json
# in <shm>/m7-Akeep/ARM (raw: they hold ids and hashes; analyze.py extracts labelled numbers), deletes the build. Resumable per set (a DONE marker). Prints progress lines.
set -u
ARM=$1; S=<scratchpad>/m7/m7-01/A
export SONGCHARTER_GOLDEN=$DEV/golden
export SONGCHARTER_SCAN_CHART=<wt>/base-main/tools/scan-chart/scan.cjs
export SONGCHARTER_AUTOCHART=<checkout>/eval/tools/autochart
export SONGCHARTER_ALLIN1_PYTHON=$DEV/allin1/bin/python SONGCHARTER_HEAVY_MIN_FREE_GB=1
PY=<checkout>/.venv/bin/python; G=$SONGCHARTER_GOLDEN; C=<shm>/m7/code-$ARM
mkdir -p <shm>/m7
if [ ! -d $C ]; then git -C <wt>/orch worktree add --detach $C 72f5679 >/dev/null 2>&1 || { echo "ARM $ARM worktree FAILED"; exit 1; }
  $PY $S/scripts/patch_arm.py $C $ARM || { echo "ARM $ARM patch FAILED"; exit 1; }; fi
cd $C
for set in refs stress set20; do
  K=<shm>/m7-Akeep/$ARM/$set; [ -f $K/DONE ] && { echo "ARM $ARM $set already done"; continue; }
  a=$(df --output=avail -k / | tail -1); [ "$a" -lt 500000 ] && { echo "ARM $ARM DISK LOW $a KB: refusing"; exit 1; }
  O=<shm>/m7/$ARM-$set; [ -f $O/summary.json ] || rm -rf $O; t0=$(date +%s)
  case $set in
    refs)   ( export EVAL_DATA=$DEV/eval; $S/scripts/gr.sh $PY --code $C --out $O --threads 2 --rerun bass ) > <shm>/m7/$ARM-$set.log 2>&1 ;;
    stress) ( export EVAL_DATA=$DEV/eval; $S/scripts/gr.sh $PY --code $C --refs $EVAL_DATA/stress --work $G/stress-work --out $O --threads 2 --rerun bass \
              && <checkout>/tools/heavy.sh $PY eval/stress.py score $O ) > <shm>/m7/$ARM-$set.log 2>&1 ;;
    set20)  ( export EVAL_DATA=$DEV/eval-set20 STRESS_JSON=$DEV/eval-set20/set20.json STRESS_LOCAL=$DEV/eval-set20/stress.local.json
              $S/scripts/gr.sh $PY --code $C --refs $EVAL_DATA/stress --work $G/set20-work --out $O --threads 2 --rerun bass \
              && <checkout>/tools/heavy.sh $PY eval/stress.py score $O ) > <shm>/m7/$ARM-$set.log 2>&1 ;;
  esac
  rc=$?; echo "ARM $ARM $set exit $rc in $(( $(date +%s)-t0 ))s"
  [ $rc -eq 0 ] || exit 1
  mkdir -p $K; cp -r $O/summary.json $O/scores $O/stress_scores $K/ 2>/dev/null; cp $O/stress_scores.json $K/ 2>/dev/null
  i=0; for d in $(ls -d $O/*/ | sort); do [ -f $d/notes.chart ] || continue; i=$((i+1)); n=$(basename $d); [ $set = set20 ] && n=$(printf 's%02d' $i)
    mkdir -p $K/songs/$n; cp $d/notes.chart $K/songs/$n/
    python3 -c "import json,sys;d=json.load(open(sys.argv[1]));json.dump({k:d.get(k) for k in ('grid','tempo_map')},open(sys.argv[2],'w'))" $d/report.json $K/songs/$n/report.min.json; done
  echo $(( $(date +%s)-t0 )) > $K/DONE; rm -rf $O
done
echo "ARM $ARM DONE"; df -h / | tail -1
