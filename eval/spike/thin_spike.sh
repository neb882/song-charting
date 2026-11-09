#!/usr/bin/env bash
# eval/spike/thin_spike.sh AUDIO...: the M6 spike on the guitar engine thinning fast runs (docs/work-orders/
# M5-99-later.md, "Fast runs thinned by the guitar engine"): Fretformer 2 Expert takes of one song or more under
# several engine settings ("arms"), 4 seeds each, for scoring later per 30-s window against the songs' human charts.
#
# Run it on the GPU through eval/gpu.sh thin-spike [--app] AUDIO... (detached, survives closing the terminal). The
# files run one after the other. Each take is a folder OUT/<label>/<arm>/seed_<seed>/ with notes.chart and
# autochart_run/summary.json (the settings and the devices used); <label> is a built set's song id for its input.wav
# (eval/data/refs/<id>/input.wav: <id>), else "song" (song_2, song_3, ... for a second and a third). The take's
# song.ogg is deleted; the engine's work folder, OUT/work, keeps its copy of each input and the separation.
# Resumable: a take is kept only when its summary says it is what this run would make (the input's SHA-256, the
# seed, the temperature, the knobs, and the transcriber on AC_DEVICE); any other is made again, with the reason in
# the log. At the end OUT/thin_spike_results.zip
# holds this run's charts and summaries only, each summary copied field by field (numbers, hashes and short names: no
# path, no message), checked for this PC's home folder and user name and by check_no_audio.py: send that back. The
# log, OUT/thin_spike.log, stays here; its lines write the home folder as ~.
#
# Env: ARMS   space-separated name:settings, settings a comma list of T=<temperature> and <knob>=<0..6>
#             (knobs: speed chords hopos taps movement; speed is the density knob; unset knobs stay "auto")
#             default "base:T=0.95 hot:T=1.05 dense5:speed=5 dense6:speed=6"
#      SEEDS  default "20260609 101 202 303" (eval/takes.py's; commas work too)
#      AC_DEVICE  default cuda; the run stops after a take whose transcriber ran on another device (always: gpu.sh's
#             ALLOW_CPU=1 skips only its check before the start)
#      SPIKE_OUT  OUT (default eval/data/runs/thin_spike)
#      SONGCHARTER_AUTOCHART  the autochart install (default eval/tools/autochart; gpu.sh --app: the app's), EVAL_PY
#             its Python (for the CUDA library path and the zip; default .venv/bin/python), node the first on PATH
#
# The driver is a copy of the install's ac_headless.cjs made in OUT with the knobs enabled (the patch below), so the
# install's own driver, which songcharter's take cache keys hash, is never changed. All takes share one work folder,
# so each song's separation and beat map are made once.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
[ $# -ge 1 ] || { sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
# TEXT with the home folder written ~ (eval/gpu.sh's tilde), so a line pasted back carries no user name
tilde() { local text=$1 t='~'; if [ -n "${HOME:-}" ] && [ "$HOME" != / ]; then text=${text//"$HOME"/$t}; fi; printf '%s' "$text"; }
tilde_lines() { local line; while IFS= read -r line || [ -n "$line" ]; do tilde "$line"; echo; done; }
AUDIOS=() LABELS=()
declare -A taken=()
for a in "$@"; do
  [ -f "$a" ] || { echo "thin_spike: no such file: $(tilde "$a")" >&2; exit 2; }
  a="$(realpath "$a")"
  d="$(basename "$(dirname "$a")")" label=song
  if [ "$(basename "$a")" = input.wav ] && [[ $d =~ ^[a-z][a-z0-9_]*$ ]]; then label=$d; fi
  k=1 l=$label
  while [ -n "${taken[$l]:-}" ]; do k=$((k + 1)); l=${label}_$k; done
  taken[$l]=1; AUDIOS+=("$a"); LABELS+=("$l")
done
OUT="$(realpath -m "${SPIKE_OUT:-$REPO/eval/data/runs/thin_spike}")"
INST="$(realpath "${SONGCHARTER_AUTOCHART:-$REPO/eval/tools/autochart}")"
PY="${EVAL_PY:-$REPO/.venv/bin/python}"
ARMS="${ARMS:-base:T=0.95 hot:T=1.05 dense5:speed=5 dense6:speed=6}"
SEEDS="${SEEDS:-20260609 101 202 303}"; SEEDS="${SEEDS//,/ }"
DEVICE="${AC_DEVICE:-cuda}"
for f in "$INST/ac_headless.cjs" "$INST/models/fretformer-v2/manifest.json"; do
  [ -f "$f" ] || { echo "thin_spike: missing $(tilde "$f") (run eval/tools/autochart/setup.sh)" >&2; exit 2; }
done
mkdir -p "$OUT"
LOG="$OUT/thin_spike.log"
say() { echo "$(date '+%F %T') $(tilde "$*")" | tee -a "$LOG"; }

# The patched driver: the knobs from AC_KNOBS ("speed=5,chords=2"), knobsActive when one is set (the app's rule,
# src/data/generationSettings.js), and the knobs recorded in the summary. Each replacement must apply exactly once.
DRIVER="$OUT/ac_knobs.cjs"
node - "$INST/ac_headless.cjs" "$DRIVER" <<'EOF'
const fs = require("fs");
const [src, dst] = process.argv.slice(2);
let s = fs.readFileSync(src, "utf8");
const swap = (from, to) => {
  const n = s.split(from).length - 1;
  if (n !== 1) {
    console.error(`thin_spike: the driver changed; patch target found ${n} times, not once: ${from}`);
    process.exit(2);
  }
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
swap('const HERE = __dirname;', `const HERE = ${JSON.stringify(require("path").dirname(src))};`);
fs.writeFileSync(dst, s);
EOF

if [ "$DEVICE" = cuda ]; then
  libs=$("$PY" -I -B -c "import sys; sys.path.insert(0, sys.argv[1]); from songcharter.engines.autochart import cuda_library_path; print(':'.join(cuda_library_path()))" "$REPO" 2>/dev/null || true)
  [ -n "$libs" ] && export LD_LIBRARY_PATH="$libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export AUTOCHART_ONNX_TRANSCRIBER_DEVICE="${AUTOCHART_ONNX_TRANSCRIBER_DEVICE:-cuda}"
  say "LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
fi
WORK="$OUT/work"; mkdir -p "$WORK"
say "thin spike: ${LABELS[*]}; arms: $ARMS; seeds: $SEEDS; device $DEVICE"

# SUMMARY SHA SEED T KNOBS DEVICE -> the ways the summary differs from them, comma-separated (none: an empty line)
DIFFERS='
const [f, sha, seed, temp, knobs, device] = process.argv.slice(1);
const s = require(f), have = s.knobs || {}, why = [];
const want = Object.fromEntries(knobs.split(",").filter(Boolean).map((kv) => kv.split("=").map((x) => x.trim()))
  .map(([k, v]) => [k, Number.parseInt(v, 10)]));
if (s.inputSha256 !== sha) why.push("another input");
if (s.seed !== Number(seed)) why.push("another seed");
if (s.temperature !== Number(temp)) why.push("another temperature");
if ([...new Set([...Object.keys(have), ...Object.keys(want)])].some((k) => (have[k] ?? null) !== (want[k] ?? null)))
  why.push("other knobs");
const runs = s.runs || [];
if (!runs.length || runs.some((r) => (r.devices || {}).transcriber !== device)) why.push(`the transcriber not on ${device}`);
console.log(why.join(", "));'
TAKES=()   # this run's take folders, relative to OUT: what the zip holds
for i in "${!AUDIOS[@]}"; do
  AUDIO=${AUDIOS[$i]} label=${LABELS[$i]}
  sha=$(sha256sum "$AUDIO" | cut -d' ' -f1)
  for arm in $ARMS; do
    name=${arm%%:*}; settings=${arm#*:}
    temp=0.95; knobs=
    IFS=, read -ra parts <<< "$settings"
    for p in "${parts[@]}"; do
      case "$p" in T=*) temp=${p#T=} ;; "") ;; *) knobs="${knobs:+$knobs,}$p" ;; esac
    done
    for seed in $SEEDS; do
      take="$OUT/$label/$name/seed_$seed"
      TAKES+=("$label/$name/seed_$seed")
      if [ -s "$take/autochart_run/summary.json" ] && [ -s "$take/notes.chart" ]; then
        # what differs between the take's summary and what this run would make; nothing: the take is kept
        why=$(node -e "$DIFFERS" "$take/autochart_run/summary.json" "$sha" "$seed" "$temp" "$knobs" "$DEVICE" 2>/dev/null \
              || echo "its summary cannot be read")
        if [ -z "$why" ]; then say "$label $name seed $seed: kept"; continue; fi
        say "$label $name seed $seed: made again ($why)"
      fi
      rm -rf "$take"; mkdir -p "$(dirname "$take")"
      t0=$(date +%s)
      # the driver's log goes into ours as it comes, with the home folder as ~; its summary (stdout) to last_take.json
      if ! AC_SEED=$seed AC_DIFFICULTIES=expert AC_DEVICE=$DEVICE AC_TEMPERATURE=$temp AC_KNOBS=$knobs \
           AC_APP_ROOT="$INST/src" AC_MODELS="$INST/models" AC_TITLE=take AC_ARTIST=spike \
           node "$DRIVER" --audio "$AUDIO" --out "$take" --work "$WORK" 2>&1 > "$OUT/last_take.json" \
           | tilde_lines >> "$LOG"; then
        say "$label $name seed $seed: FAILED (the log above); stopping"; exit 1
      fi
      rm -f "$take/song.ogg"
      dev=$(node -e 'const s=require(process.argv[1]); console.log((s.runs||[]).map(r=>(r.devices||{}).transcriber||"?").join(","))' "$take/autochart_run/summary.json")
      tok=$(node -e 'const s=require(process.argv[1]); console.log((s.runs||[]).map(r=>`${r.nTokens} tokens, ${r.noteLines} notes`).join(";"))' "$take/autochart_run/summary.json")
      say "$label $name seed $seed: T=$temp knobs=${knobs:-auto}: $tok, transcriber on $dev, $(( $(date +%s) - t0 )) s"
      if [ "$dev" != "$DEVICE" ]; then
        say "the transcriber did not run on $DEVICE; stopping"; exit 1
      fi
    done
  done
done

# The zip: this run's takes, each notes.chart as the engine wrote it and its summary copied field by field. Then a
# guard reads the finished zip back in lower case, as eval/gpu.sh results' does: this PC's home folder (or its real
# path), a Windows user folder (/mnt/x/users/, x:\users), a \\wsl$ path, or the user name as a whole word stops it;
# so does check_no_audio.py. A stopped zip is deleted, and so is the one before it, so no stale zip is left to send.
ZIP="$OUT/thin_spike_results.zip"
rm -f "$ZIP" "$ZIP.part"
if ! "$PY" -I - "$OUT" "$ZIP.part" "${HOME:-}" "${USER:-}" "${TAKES[@]}" <<'EOF' | tilde_lines | tee -a "$LOG"; then
import json, os, re, sys, zipfile
out, part, home, user, *takes = sys.argv[1:]
NAME = re.compile(r"[A-Za-z0-9_.+ -]{1,40}")
HEX = re.compile(r"[0-9a-f]{64}")
DROP = object()


def copy(v):
    """numbers, booleans, nulls, short names and SHA-256s, in lists and maps; any other string (a path, a message)
    is dropped"""
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return v if NAME.fullmatch(v) or HEX.fullmatch(v) else DROP
    if isinstance(v, list):
        return [c for c in map(copy, v) if c is not DROP]
    if isinstance(v, dict):
        kept = {k: copy(x) for k, x in v.items() if isinstance(k, str) and NAME.fullmatch(k)}
        return {k: c for k, c in kept.items() if c is not DROP}
    return DROP


with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
    for t in takes:
        z.write(os.path.join(out, t, "notes.chart"), f"{t}/notes.chart")
        with open(os.path.join(out, t, "autochart_run", "summary.json"), encoding="utf-8") as f:
            z.writestr(f"{t}/autochart_run/summary.json", json.dumps(copy(json.load(f)), indent=1) + "\n")


def norm(s):
    return re.sub(r"[\s_-]+", " ", s.lower()).strip()


places = {p.lower() for p in (home, os.path.realpath(home) if home else "") if len(p) > 1}
users = sorted({norm(u) for u in (user, os.path.basename(home.rstrip("/"))) if len(norm(u)) >= 3}, key=len,
               reverse=True)
USER = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, users)) + r")(?!\w)") if users else None
PATHS = re.compile(r"/mnt/[a-z]/users/|(?<![a-z])[a-z]:[\\/]+users[\\/]|[\\/]{2,}wsl(?:\$|\.localhost)")
stops = []
with zipfile.ZipFile(part) as z:
    for n in z.namelist():
        text = (n + "\n" + z.read(n).decode("utf-8", "surrogateescape")).lower()
        why = (["path"] if PATHS.search(text) or any(p in text for p in places) else []) + \
            (["user name"] if USER and USER.search(norm(text)) else [])
        if why:
            stops.append(f"  {n}: {', '.join(why)}")
if stops:
    print("thin_spike: no zip made, the guard stopped it (these lines hold no name: send them as they are):", *stops,
          sep="\n")
    sys.exit(1)
print(f"thin_spike: {len(takes)} takes zipped")
EOF
  rm -f "$ZIP.part"; exit 1
fi
if ! (cd "$OUT" && "$PY" -I "$REPO/packaging/ci/check_no_audio.py" thin_spike_results.zip.part) | tee -a "$LOG"; then
  rm -f "$ZIP.part"; say "the zip would hold audio (above): no zip made"; exit 1
fi
mv "$ZIP.part" "$ZIP"
say "done: $ZIP ($(du -h "$ZIP" | cut -f1)): send this file back"
