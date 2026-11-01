"""Thin launcher for STRUM's scripts/batch_pipeline.py (unmodified source).

What it changes, and nothing else:
  1. torch.load is forced to weights_only=True (restricted unpickler) with an
     allowlist of the plain types the published checkpoints contain (numpy
     dtype/scalar/ndarray, fractions.Fraction, demucs HTDemucs class ref).
     Tensors loaded are identical; arbitrary pickle code can't run.
  2. Unless STRUM_ALLOW_NET_METADATA=1, the MusicBrainz / iTunes metadata and
     album-art lookups are stubbed out (they only affect song.ini text and
     album.png, never notes).
Device: STRUM auto-selects cuda if available else cpu; there is no GPU here,
so every model runs on CPU via its own map_location=device.

usage: strum_launch.py <strum repo root> <input dir> <output dir> [extra batch_pipeline args]
"""
import fractions
import os
import sys
from pathlib import Path

import numpy as np
import torch

repo = Path(sys.argv[1]).resolve()
in_dir, out_dir = sys.argv[2], sys.argv[3]
extra = sys.argv[4:]

# ---- 1. safe torch.load ---------------------------------------------------
import demucs.htdemucs  # noqa: E402  (PyPI demucs; class reference in its .th package)

SAFE = [np.dtype, np._core.multiarray.scalar, np._core.multiarray._reconstruct, np.ndarray,
        fractions.Fraction, demucs.htdemucs.HTDemucs]
SAFE += [type(np.dtype(t)) for t in ("float64", "float32", "float16", "int64", "int32", "bool")]
torch.serialization.add_safe_globals(SAFE)
_orig_load = torch.load


def _safe_load(*a, **kw):
    kw["weights_only"] = True
    return _orig_load(*a, **kw)


torch.load = _safe_load

# ---- import STRUM's pipeline module (same sys.path setup it does itself) ----
sys.path.insert(0, str(repo))
sys.path.insert(0, str(repo / "scripts"))
import batch_pipeline as bp  # noqa: E402

# ---- 2. no third-party metadata lookups (optional) -------------------------
if os.environ.get("STRUM_ALLOW_NET_METADATA", "0") != "1":
    bp.BatchPipeline._quick_musicbrainz_check = lambda self, artist, title: False
    bp.BatchPipeline._fetch_musicbrainz_metadata = (
        lambda self, artist, title: {"album": "", "year": "", "genre": ""})
    bp.BatchPipeline._fetch_itunes_art = lambda self, artist, title, output_path: False

sys.argv = [str(repo / "scripts" / "batch_pipeline.py"), in_dir, out_dir, *extra]
bp.main()
