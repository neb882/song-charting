"""Recreate the two drum-ensemble YAML configs that STRUM's public repo never
committed (configs/onset_classifier_v4.yaml, configs/onset_classifier_v17.yaml),
using the training config embedded in each published checkpoint.

batch_infer_hybrid.load_ensemble() silently skips an ensemble member whose
YAML is missing. Without V17 the Crash class gets no weight (V17 is "SOLO" for
Crash in PER_CLASS_WEIGHTS), so its logit stays 0 -> p=0.5 on every onset.

For the five configs that ARE shipped, the YAML `model:` block equals the
checkpoint-embedded `config['model']` (checked: only diff is an explicit
use_freq_attn: false default in onset_classifier.yaml). load_state_dict(strict)
in STRUM still verifies the architecture matches the weights.

Checkpoints are read with torch.load(weights_only=True) (restricted unpickler).

usage: restore_configs.py <checkpoints dir> <out configs dir>
"""
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

SAFE = [np.dtype, np._core.multiarray.scalar, np._core.multiarray._reconstruct, np.ndarray]
SAFE += [type(np.dtype(t)) for t in ("float64", "float32", "float16", "int64", "int32", "bool")]


def plain(o):
    if isinstance(o, dict):
        return {str(k): plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [plain(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    return o


def main():
    ck_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    with torch.serialization.safe_globals(SAFE):
        for name in ("onset_classifier_v4", "onset_classifier_v17"):
            ck = torch.load(ck_dir / name / "best_f1.pt", map_location="cpu", weights_only=True)
            cfg = plain(ck["config"])
            out = out_dir / f"{name}.yaml"
            hdr = (f"# Restored by eval wrapper from checkpoints/{name}/best_f1.pt ['config']\n"
                   f"# (epoch {ck.get('epoch')}); not part of the upstream repo.\n")
            out.write_text(hdr + yaml.safe_dump(cfg, sort_keys=False))
            print(f"wrote {out}  model={cfg['model']}")


if __name__ == "__main__":
    main()
