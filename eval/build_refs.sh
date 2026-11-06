#!/usr/bin/env bash
# build_refs.sh [--set refs|stress] [test song audio]
# Downloads the human charts of a set from Chorus Encore (.sng packages hold the chart, song.ini and the audio) and
# builds each one's folder: input.wav (the stems summed; an empty or unopenable stem is skipped and named in
# build_meta.json), input.mp3, ref/ (the chart with vocals and lyrics removed, song.ini, a stub song.ogg),
# ref_notes.json and offset_check.json; then the set's songs.json.
#   --set refs (the default): refs.json's songs into <data>/refs/<id>/. With an argument, also <data>/refs/test_song/
#     from that audio file.
#   --set stress: eval/stress.json's songs (the stress set, docs/DESIGN.md 3.3), whose md5s, titles and charters are
#     in the owner's list outside the repository, $STRESS_LOCAL (default <data>/stress.local.json): the primary chart
#     of each into <data>/stress/<id>/, every other chart into <data>/stress/<id>/alt/<md5>/. $STRESS_JSON stands in
#     for eval/stress.json (the tests).
# ONLY="id1 id2" limits the songs. A folder whose ref_notes.json exists is not built again.
# The downloads are other people's work: they stay in <data>/ (git-ignored) and are used only for scoring.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${EVAL_DATA:-$HERE/data}"
PY="${EVAL_PY:-$HERE/.venv/bin/python}"
SET=refs
if [ "${1:-}" = "--set" ]; then SET="${2:-}"; shift 2 || true; fi
case "$SET" in
  refs) LIST="$HERE/refs.json" ;;
  stress)
    [ $# -eq 0 ] || { echo "build_refs.sh: --set stress takes no test song" >&2; exit 2; }
    mkdir -p "$DATA/stress"
    LIST="$DATA/stress/stress_set.json"   # the merged list: md5s and titles, outside the repository
    "$PY" -I "$HERE/stress.py" songs --json --local "${STRESS_LOCAL:-$DATA/stress.local.json}" \
      ${STRESS_JSON:+--set "$STRESS_JSON"} > "$LIST.part" </dev/null
    mv "$LIST.part" "$LIST" ;;
  *) echo "build_refs.sh: --set is refs or stress, not '$SET'" >&2; exit 2 ;;
esac
mkdir -p "$DATA/sng" "$DATA/unpacked" "$DATA/$SET"
# The list is read on fd 3 and every helper gets stdin from /dev/null: an ffmpeg that reads its stdin (the helpers'
# ffmpeg once did) would otherwise eat the list's next lines, so a fresh machine built only the first song.
while IFS=$'\t' read -r id md5 role <&3; do
  case " ${ONLY:-$id} " in *" $id "*) ;; *) continue;; esac   # ONLY="id1 id2" limits the set
  sng="$DATA/sng/$md5.sng"
  if [ ! -s "$sng" ]; then
    curl -fL --retry 3 -o "$sng.part" "https://files.enchor.us/$md5.sng" </dev/null && mv "$sng.part" "$sng"
  fi
  if [ "$SET" = refs ]; then dest="$DATA/refs/$id"; unp="$DATA/unpacked/$id"
  elif [ "$role" = primary ]; then dest="$DATA/stress/$id"; unp="$DATA/unpacked/stress/$id/$md5"
  else dest="$DATA/stress/$id/alt/$md5"; unp="$DATA/unpacked/stress/$id/$md5"; fi
  if [ ! -s "$dest/ref_notes.json" ]; then
    rm -rf "$unp"
    "$PY" -I "$HERE/refs/sng_unpack.py" "$sng" "$unp" >/dev/null </dev/null
    "$PY" -I "$HERE/refs/build_ref.py" "$unp" "$dest" "$md5" >/dev/null </dev/null
    "$PY" -I "$HERE/refs/offset_check.py" "$dest" > "$dest/offset_check.json" </dev/null
    if [ "$SET" = stress ]; then rm -rf "$unp"; fi   # the package stays in sng/; its unpacked lyrics need not
  fi
  echo "ok $id${role:+ $role}"   # the id only: a stress set's md5s stay in its local list
done 3< <("$PY" -I -c "import json,sys
for r in json.load(open(sys.argv[1])):
    print(r['id'], r['md5'], 'primary', sep='\t')
    for a in r.get('alts') or []: print(r['id'], a['md5'], 'alt', sep='\t')" "$LIST")
"$PY" -I "$HERE/refs/make_songs_json.py" "$DATA/$SET" "$LIST" </dev/null
if [ "$SET" = refs ] && [ $# -ge 1 ]; then
  T="$DATA/refs/test_song"; mkdir -p "$T"
  ext="${1##*.}"; cp "$1" "$T/input.${ext,,}"
  ffmpeg -nostdin -v error -y -i "$1" -map 0:a:0 -ac 2 -ar 44100 -c:a pcm_s16le "$T/input.wav" </dev/null  # gapless
  echo "ok test_song"
fi
