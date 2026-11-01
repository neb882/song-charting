#!/usr/bin/env bash
# build_refs.sh [test song audio]
# Downloads the reference charts listed in refs.json from Chorus Encore (.sng packages hold the chart, song.ini
# and the audio), and builds <data>/refs/<id>/: input.wav (the stems summed), input.mp3, ref/ (the chart with
# vocals and lyrics removed, song.ini, a stub song.ogg), ref_notes.json and offset_check.json. With an argument,
# also <data>/refs/test_song/ from that audio file.
# The downloads are other people's work: they stay in <data>/ (git-ignored) and are used only for scoring.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${EVAL_DATA:-$HERE/data}"
PY="${EVAL_PY:-$HERE/.venv/bin/python}"
mkdir -p "$DATA/sng" "$DATA/unpacked" "$DATA/refs"
while IFS=$'\t' read -r id md5; do
  case " ${ONLY:-$id} " in *" $id "*) ;; *) continue;; esac   # ONLY="id1 id2" limits the set
  sng="$DATA/sng/$md5.sng"
  if [ ! -s "$sng" ]; then
    curl -fL --retry 3 -o "$sng.part" "https://files.enchor.us/$md5.sng" && mv "$sng.part" "$sng"
  fi
  if [ ! -s "$DATA/refs/$id/ref_notes.json" ]; then
    rm -rf "$DATA/unpacked/$id"
    "$PY" -I "$HERE/refs/sng_unpack.py" "$sng" "$DATA/unpacked/$id" >/dev/null
    "$PY" -I "$HERE/refs/build_ref.py" "$DATA/unpacked/$id" "$DATA/refs/$id" "$md5" >/dev/null
    "$PY" -I "$HERE/refs/offset_check.py" "$DATA/refs/$id" > "$DATA/refs/$id/offset_check.json"
  fi
  echo "ok $id"
done < <(python3 -c "import json,sys; [print(r['id'], r['md5'], sep='\t') for r in json.load(open(sys.argv[1]))]" "$HERE/refs.json")
"$PY" -I "$HERE/refs/make_songs_json.py" "$DATA/refs"
if [ $# -ge 1 ]; then
  T="$DATA/refs/test_song"; mkdir -p "$T"
  ext="${1##*.}"; cp "$1" "$T/input.${ext,,}"
  ffmpeg -v error -y -i "$1" -map 0:a:0 -ac 2 -ar 44100 -c:a pcm_s16le "$T/input.wav"   # gapless decode
  echo "ok test_song"
fi
