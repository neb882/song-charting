#!/usr/bin/env bash
# Download STRUM weights from HF opria123/strum at a pinned revision.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REV=6f8997f53c6eb04e0cb38f679c593d27ae89ab7f
DEST="$HERE/weights_hf"
mkdir -p "$DEST"
FILES=(
README.md
drums/drums_cymbal_onset/best_union_f1.pt
drums/drums_mc_onset/best.pt
drums/drums_phase3/best.pt
drums/drums_v14/best.pt
drums/tom_refinement_demucs/best.pt
drums_classifier_ensemble/onset_classifier/best_f1.pt
drums_classifier_ensemble/onset_classifier_v12_clean/best_f1.pt
drums_classifier_ensemble/onset_classifier_v12c_community/best_f1.pt
drums_classifier_ensemble/onset_classifier_v15/best_f1.pt
drums_classifier_ensemble/onset_classifier_v16/best_f1.pt
drums_classifier_ensemble/onset_classifier_v17/best_f1.pt
drums_classifier_ensemble/onset_classifier_v4/best_f1.pt
drums_classifier_ensemble/onset_classifier_v6/best_f1.pt
guitar/fret_mapper_v4.pt
guitar/guitar_v2_onset/best.pt
section_classifier/best.pt
)
for f in "${FILES[@]}"; do
  if [ -s "$DEST/$f" ]; then continue; fi
  mkdir -p "$DEST/$(dirname "$f")"
  curl -fsSL --retry 5 -C - -o "$DEST/$f.part" "https://huggingface.co/opria123/strum/resolve/$REV/$f"
  mv "$DEST/$f.part" "$DEST/$f"
  echo "got $f $(stat -c %s "$DEST/$f")"
done
echo DONE
