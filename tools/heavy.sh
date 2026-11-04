#!/bin/sh
# tools/heavy.sh COMMAND [ARGS...]: one heavy job at a time (the full suite, a golden run, an install, a real chart)
# on a dev machine that several agents share. Agents can't see each other's jobs, so every heavy command queues on one
# lock: this waits while another job holds it, and says which. eval/golden.py's `run` takes the same lock itself.
# [docs/PIPELINE.md, Long runs: a golden run's guitar engine was killed for memory while two suites ran beside it.]
#
# It refuses (exit 2) to start with under $SONGCHARTER_HEAVY_MIN_FREE_GB of disk free in the current folder (default
# 5; 0 skips the check). $SONGCHARTER_HEAVY_LOCK moves the lock (default /dev/shm/songcharter-heavy.lock), or is "off".
# Inside a job it already holds the lock for, it runs the command at once. The command's exit status is this script's.
set -u
[ $# -gt 0 ] || { echo "usage: tools/heavy.sh COMMAND [ARGS...]" >&2; exit 2; }
[ -n "${SONGCHARTER_HEAVY_HELD:-}" ] && exec "$@"

min=${SONGCHARTER_HEAVY_MIN_FREE_GB:-5}
if [ "$min" != 0 ]; then
    free=$(df -Pk . | awk 'NR == 2 { print int($4 / 1048576) }')
    if [ "${free:-0}" -lt "$min" ]; then
        echo "heavy.sh: ${free:-?} GB free here, under $min GB: free some first (or SONGCHARTER_HEAVY_MIN_FREE_GB=0)" >&2
        exit 2
    fi
fi

lock=${SONGCHARTER_HEAVY_LOCK:-/dev/shm/songcharter-heavy.lock}
[ "$lock" = off ] && exec "$@"
exec 9>>"$lock" || exit 2
if ! flock -n 9; then
    echo "heavy.sh: waiting for $lock, held by: $(cat "$lock.who" 2>/dev/null || echo '?')" >&2
    flock 9 || exit 2
fi
echo "$$ $(date -u +%Y-%m-%dT%H:%M:%SZ) $*" > "$lock.who"
export SONGCHARTER_HEAVY_HELD=1
exec "$@"
