# M4-00b: the CUDA 13 provider spike

**Not a build order: a check the owner runs** in their existing WSL on the 5070. About 20 minutes, no songcharter
install. **It must pass before wave 1 ends.** The script is already written and committed:
`packaging/spike/cuda13-provider.sh`.

## Intent

The WSL plan puts the guitar on CUDA by giving onnxruntime-node 1.27.0's CUDA provider the CUDA 13 libraries that
the cu132 torch lane installs, plus `nvidia-curand` (M4-00, finding 4).

That rests on two things:
- the provider's needed-library list (`readelf`);
- the wheels' file lists.

No run backs it:
- `eval/gpu.sh` (lines 22–44) put CUDA 12 libraries and a separate cuDNN on the path for the earlier 5070 runs, so
  they are no evidence for CUDA 13;
- this container has no GPU.

M4-01 and M4-02 build on the result, so it is checked before their wave ends.

## What the script does

1. **uv 0.13.5:** its GitHub release tarball, checked against the published `.sha256`.
2. **A venv** with `torch==2.15.0+cu132` and `nvidia-curand==10.4.4.72`, about 3.2 GB of downloads and 5.3 GB on
   disk [here].
3. **Node and onnxruntime-node:**
   - Node 24.19.0 (autochart's pin, by SHA-256);
   - onnxruntime-node 1.27.0 by songcharter's lock of autochart's dependencies (`npm ci --ignore-scripts`, both
     files by SHA-256);
   - onnxruntime-node's own installer, run explicitly. It fetches the CUDA provider from NuGet (212 MB). npm 11.17
     ran it on `npm ci` too, but warned that install scripts are "not yet covered by allowScripts" [here].
   - The provider files are checked against their SHA-256.
4. **The model:** Fretformer 2's transcriber encoder (`encoder_fp32.onnx`, 122 MB), by the SHA-256 in autochart's
   catalog.
5. **One session** with `executionProviders: ["cuda"]` and ORT's verbose log:
   - `LD_LIBRARY_PATH` = the venv's `nvidia/cu13/lib` and `nvidia/cudnn/lib`, plus `/usr/lib/wsl/lib`;
   - five runs on 64 beats of input;
   - ORT's "Node placements" lines say where every node ran;
   - then the same on the CPU, for a comparison.
6. **The verdict:** `cuda13-result.json`, in the folder and copied to Windows' Downloads.
   - **PASS** (exit 0): the session ran, with nodes on `CUDAExecutionProvider`.
   - **FAIL** (exit 1), in a banner, in these cases:
     - a library the provider could not load (its name, from ORT);
     - a session that ran with no node on CUDA, a silent CPU fallback;
     - an inference error.
   - **Exit 2:** setup failed (network or disk). "Run the same command again to continue."

## Tested here (no GPU) [here]

- **The CPU path** (`--device cpu --skip-torch`): PASS. 392 nodes on the CPU, a median of about 43 ms a run. The
  provider's files match their SHA-256 after the explicit installer.
- **The failure path** (`--device cuda --skip-torch`): exit 1, with the banner "FAIL: the CUDA session did not run:
  … libcublasLt.so.13: cannot open shared object file". `missing_libraries` lists all seven.
- **The real cu132 venv** (`--device cuda`):
  - all seven CUDA 13 libraries are found in `nvidia/cu13/lib` and `nvidia/cudnn/lib` ("missing: nothing");
  - the provider gets past all of them, and fails only on `libcuda.so.1`, the GPU driver's library, which WSL gives
    in `/usr/lib/wsl/lib`;
  - torch reports CUDA 13.2.
- **Not testable here:** the PASS on a GPU, and the "no node on CUDA" branch. That branch parses ORT's
  "Node(s) placed on [X]. Number of nodes: N" lines; only the "All nodes placed on [CPUExecutionProvider]" form was
  seen here.

## The owner's steps

1. Open your existing Ubuntu (WSL) on the 5070. `nvidia-smi` must show driver 580 or newer.
2. Paste:
   ```
   curl -fsSLO https://raw.githubusercontent.com/neb882/song-charting/main/packaging/spike/cuda13-provider.sh && bash cuda13-provider.sh
   ```
   This works once `m4-plan` is on GitHub's `main`. Before that, use `m4-plan` in place of `main` in the URL, once
   that branch is pushed.
3. It takes about 20 minutes (most of it the 3.2 GB download) and needs 8 GB free in WSL. It ends with PASS or FAIL.
4. Send `cuda13-result.json` (also copied to your Windows Downloads). On a FAIL, also send `~/scspike-cuda13/logs`
   zipped.
5. Delete the folder: `rm -rf ~/scspike-cuda13`.

## What a FAIL changes (M4-00, section 6)

- **The library path is wrong or incomplete** (the error names a library):
  - add the missing wheel to the cu132 extra, or add the folder it lands in to `cuda_library_path`;
  - run the spike again;
  - M4-01 and M4-02 change by a line or two.
- **The CUDA 13 build cannot run in WSL on this driver at all:**
  - **(a)** onnxruntime-node from an earlier release whose NuGet provider is CUDA 12, with CUDA 12 wheels in a small
    side environment, as `gpu.sh` assembled them. The pin must stay compatible with autochart's engine at b5a41e8,
    which uses `^1.27.0`; check that first.
  - **(b)** the guitar on the CPU in v0.1, which is 1 take by the existing rule (about 3.6 min a take for a 7-min
    song on the dev container's CPU). The 8-minute target then probably fails, and the owner decides whether v0.1
    ships so.
- **The director decides between (a) and (b)** with the owner, before wave 2 starts.

## Done means

- [Hardware] The owner's `cuda13-result.json` says PASS, with `CUDAExecutionProvider` nodes.
- The director records the numbers: the CUDA and CPU medians, and the CPU nodes left on a CUDA session.
- They go in PROGRESS and in M4-02's report.

## Depends on

Nothing. It runs while wave 1 builds.
