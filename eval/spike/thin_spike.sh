#!/usr/bin/env bash
# eval/spike/thin_spike.sh AUDIO [OUT]: the M6 spike on the guitar engine thinning fast runs (docs/work-orders/
# M5-99-later.md, "Fast runs thinned by the guitar engine"): Fretformer 2 Expert takes of one song under several
# engine settings ("arms"), 4 seeds each, for scoring later per 30-s window against the song's human charts.
#
# Run it on the GPU through eval/gpu.sh thin-spike AUDIO (detached, survives closing the terminal). Each take is a
# folder OUT/<arm>/seed_<seed>/ with notes.chart and autochart_run/summary.json (the settings and the devices used);
# the take's song.ogg is deleted, so OUT holds no audio. Resumable: a take with a summary is kept. At the end
# OUT/thin_spike_results.zip holds the charts and the summaries only: send that back.
#
# Env: ARMS   space-separated name:settings, settings a comma list of T=<temperature> and <knob>=<0..6>
#             (knobs: speed chords hopos taps movement; speed is the density knob; unset knobs stay "auto")
#             default "base:T=0.95 hot:T=1.05 dense5:speed=5 dense6:speed=6"
#      SEEDS  default "20260609 101 202 303" (eval/takes.py's)
#      AC_DEVICE  default cuda; ALLOW_CPU=1 keeps a take whose transcriber ran on the CPU (else the run stops)
#      SONGCHARTER_AUTOCHART  the autochart install (default eval/tools/autochart), EVAL_PY its Python (for the
#             CUDA library path; default .venv/bin/python)
#
# The driver is a copy of the install's ac_headless.cjs made in OUT with the knobs enabled (the patch below), so the
# install's own driver, which songcharter's take cache keys hash, is never changed. All takes share one work folder,
# so the separation and the beat map are made once.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
[ $# -ge 1 ] || { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
AUDIO="$(realpath "$1")"; [ -f "$AUDIO" ] || { echo "thin_spike: no such file: $1" >&2; exit 2; }
OUT="$(realpath -m "${2:-$REPO/eval/data/runs/thin_spike}")"
INST="$(realpath "${SONGCHARTER_AUTOCHART:-$REPO/eval/tools/autochart}")"
PY="${EVAL_PY:-$REPO/.venv/bin/python}"
ARMS="${ARMS:-base:T=0.95 hot:T=1.05 dense5:speed=5 dense6:speed=6}"
SEEDS="${SEEDS:-20260609 101 202 303}"
DEVICE="${AC_DEVICE:-cuda}"
for f in "$INST/ac_headless.cjs" "$INST/models/fretformer-v2/manifest.json"; do
  [ -f "$f" ] || { echo "thin_spike: missing $f (run eval/tools/autochart/setup.sh)" >&2; exit 2; }
done
mkdir -p "$OUT"
LOG="$OUT/thin_spike.log"
say() { echo "$(date '+%F %T') $*" | tee -a "$LOG"; }

# The patched driver: the knobs from AC_KNOBS ("speed=5,chords=2"), knobsActive when one is set (the app's rule,
# src/data/generationSettings.js), and the knobs recorded in the summary. Each replacement must apply exactly once.
DRIVER="$OUT/ac_knobs.cjs"
node - "$INST/ac_headless.cjs" "$DRIVER" <<'EOF'
const fs = require("fs");
const [src, dst] = process.argv.slice(2);
let s = fs.readFileSync(src, "utf8");
const swap = (from, to) => {
  const n = s.split(from).length - 1;
  if (n < 1) { console.error(`thin_spike: the driver changed; patch target not found: ${from}`); process.exit(2); }
  s = s.split(from).join(to);
};
swap('const knobs = Object.fromEntries((generator.capabilities.descriptorKnobs || []).map((k) => [k, null]));',
  'const knobs = Object.fromEntries((generator.capabilities.descriptorKnobs || []).map((k) => [k, null]));\n' +
  '  for (const kv of String(process.env.AC_KNOBS || "").split(",").map((x) => x.trim()).filter(Boolean)) {\n' +
  '    const [k, v] = kv.split("=").map((x) => x.trim());\n' +
  '    if (!(k in knobs)) fail(`unknown knob ${k} (this model has: ${Object.keys(knobs).join(", ")})`);\n' +
  '    const n = Number.parseInt(v, 10);\n' +
  '    if (!Number.isInteger(n) || n < 0 || n > 6) fail(`knob ${k}: ${v} is not 0..6`);\n' +
  '    knobs[k] = n;\n' +
  '  }\n' +
  '  const knobsActive = Object.values(knobs).some((v) => v != null);');
swap('knobsActive: false', 'knobsActive');
swap('inputSha256: sha, seed, temperature, topP,', 'inputSha256: sha, seed, temperature, topP, knobs, knobsActive,');
s = s.replace('const HERE = __dirname;', `const HERE = ${JSON.stringify(require("path").dirname(src))};`);
fs.writeFileSync(dst, s);
EOF

if [ "$DEVICE" = cuda ]; then
  libs=$("$PY" -I -c "import sys; sys.path.insert(0, sys.argv[1]); from songcharter.engines.autochart import cuda_library_path; print(':'.join(cuda_library_path()))" "$REPO" 2>/dev/null || true)
  [ -n "$libs" ] && export LD_LIBRARY_PATH="$libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export AUTOCHART_ONNX_TRANSCRIBER_DEVICE="${AUTOCHART_ONNX_TRANSCRIBER_DEVICE:-cuda}"
  say "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
fi
WORK="$OUT/work"; mkdir -p "$WORK"
say "thin spike: $(basename "$AUDIO"), arms: $ARMS; seeds: $SEEDS; device $DEVICE"

for arm in $ARMS; do
  name=${arm%%:*}; settings=${arm#*:}
  temp=0.95; knobs=
  IFS=, read -ra parts <<< "$settings"
  for p in "${parts[@]}"; do
    case "$p" in T=*) temp=${p#T=} ;; "") ;; *) knobs="${knobs:+$knobs,}$p" ;; esac
  done
  for seed in $SEEDS; do
    take="$OUT/$name/seed_$seed"
    if [ -s "$take/autochart_run/summary.json" ] && [ -s "$take/notes.chart" ]; then say "$name seed $seed: kept"; continue; fi
    rm -rf "$take"; mkdir -p "$(dirname "$take")"
    t0=$(date +%s)
    if ! AC_SEED=$seed AC_DIFFICULTIES=expert AC_DEVICE=$DEVICE AC_TEMPERATURE=$temp AC_KNOBS=$knobs \
         AC_APP_ROOT="$INST/src" AC_MODELS="$INST/models" AC_TITLE=take AC_ARTIST=spike \
         node "$DRIVER" --audio "$AUDIO" --out "$take" --work "$WORK" > "$OUT/last_take.json" 2>> "$LOG"; then
      say "$name seed $seed: FAILED (the log above); stopping"; exit 1
    fi
    rm -f "$take/song.ogg"
    dev=$(node -e 'const s=require(process.argv[1]); console.log((s.runs||[]).map(r=>(r.devices||{}).transcriber||"?").join(","))' "$take/autochart_run/summary.json")
    tok=$(node -e 'const s=require(process.argv[1]); console.log((s.runs||[]).map(r=>`${r.nTokens} tokens, ${r.noteLines} notes`).join(";"))' "$take/autochart_run/summary.json")
    say "$name seed $seed: T=$temp knobs=${knobs:-auto}: $tok, transcriber on $dev, $(( $(date +%s) - t0 )) s"
    if [ "$DEVICE" != cpu ] && [ "$dev" != "$DEVICE" ] && [ "${ALLOW_CPU:-0}" != 1 ]; then
      say "the transcriber did not run on $DEVICE; stopping (ALLOW_CPU=1 to keep going)"; exit 1
    fi
  done
done

( cd "$OUT" && rm -f thin_spike_results.zip && find . -path ./work -prune -o \( -name notes.chart -o -name summary.json -o -name thin_spike.log \) -print \
    | sed 's|^\./||' | "$PY" -I -c "import sys, zipfile; z = zipfile.ZipFile('thin_spike_results.zip', 'w', zipfile.ZIP_DEFLATED); [z.write(l.strip()) for l in sys.stdin if l.strip()]" )
say "done: $OUT/thin_spike_results.zip ($(du -h "$OUT/thin_spike_results.zip" | cut -f1)): send this file back"
