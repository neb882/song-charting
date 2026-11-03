#!/usr/bin/env bash
# 20-device.sh (M4-02): the device checks on ubuntu-latest, with the cpu lane's torch and no GPU.
#   1. wsl.py's and device.py's tests (stand-in Windows programs; no GPU needed);
#   2. `songcharter doctor --quick --json` with a stand-in nvidia-smi first on PATH (an RTX 4070 on driver 581.57):
#      the GPU is parsed, and the device stays on the CPU because this torch has no CUDA, which doctor says.
# Run by packaging/ci/run-hooks.sh with bash -euo pipefail; uses CI_PY, CI_TMP and CI_ART (M4-05a's hook contract).
# doctor may exit 1 here (no autochart engine in this job is a problem): only 2 and 3 fail the hook.
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."

"$CI_PY" -m pytest -q -p no:cacheprovider --basetemp="$CI_TMP/pt-device" tests/test_wsl.py tests/test_device.py

fake="$CI_TMP/fake-gpu"
mkdir -p "$fake" "$CI_ART"
cat > "$fake/nvidia-smi" <<'SMI'
#!/bin/sh
echo "NVIDIA GeForce RTX 4070, 581.57, 12282, 8.9"
SMI
chmod +x "$fake/nvidia-smi"
report="$CI_ART/doctor-fake-gpu.json"
code=0
PATH="$fake:$PATH" "$CI_PY" -m songcharter.cli doctor --quick --json "$report" || code=$?
echo "doctor exited $code"
[ "$code" -le 1 ] || { echo "20-device: doctor failed (exit $code)" >&2; exit 1; }
"$CI_PY" - "$report" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
assert r["gpu"] == {"name": "NVIDIA GeForce RTX 4070", "driver": "581.57", "vram_mb": 12282, "compute_cap": "8.9"}, r["gpu"]
assert r["device"] == {"chosen": "cpu", "reason": "this install's torch has no CUDA (the cpu lane)"}, r["device"]
assert r["torch"]["cuda"] is None and r["wsl"] is None and r["guitar_device"] == "cpu", r
print(f"20-device: ok: {r['gpu']['name']}; device {r['device']['chosen']}: {r['device']['reason']}")
PY
