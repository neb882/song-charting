#!/bin/bash
# mkprior.sh: lays today's earlier runs (v031, gate3-final-stress, set20-main) out as an arm "prior" in <shm>/m7-Akeep
# (songs/<label>/notes.chart + report.min.json, scores), for comparing the rebuilt base arm with them. Prints nothing.
G=$DEV/golden; K=<shm>/m7-Akeep/prior
for pair in refs:v031 stress:gate3-final-stress set20:set20-main; do set=${pair%%:*}; O=$G/${pair#*:}; D=$K/$set; mkdir -p $D
  [ -d $O/scores ] && cp -r $O/scores $D/; [ -d $O/stress_scores ] && cp -r $O/stress_scores $D/
  i=0; for d in $(ls -d $O/*/ | sort); do [ -f $d/notes.chart ] || continue; i=$((i+1)); n=$(basename $d); [ $set = set20 ] && n=$(printf 's%02d' $i)
    mkdir -p $D/songs/$n; cp $d/notes.chart $D/songs/$n/
    python3 -c "import json,sys;d=json.load(open(sys.argv[1]));json.dump({k:d.get(k) for k in ('grid','tempo_map')},open(sys.argv[2],'w'))" $d/report.json $D/songs/$n/report.min.json; done
  touch $D/DONE; done
