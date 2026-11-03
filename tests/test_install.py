"""packaging/linux/install.sh's decisions, sourced in bash for its functions: the lane from a stand-in nvidia-smi
(each threshold), no silent move of a GPU install to the cpu lane when nvidia-smi fails, no `uv sync` without a lane,
and the usage and template refusals. Then packaging/release/build.sh's three assets, with a stand-in curl for uv's
published SHA-256. The whole install runs in CI (packaging/ci/linux.d/30-install.sh)."""
import hashlib
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "packaging" / "linux" / "install.sh"
BUILD = ROOT / "packaging" / "release" / "build.sh"
UV_SHA256 = "f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f"


def stand_in(folder: Path, name: str, body: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    (folder / name).chmod(0o755)


def sourced(tmp_path: Path, script: str, smi: str | None = None, previous: str | None = None):
    """`script` run in bash after sourcing install.sh, with nvidia-smi (when given) the only one on PATH and a home
    whose runtime.json has the lane `previous`."""
    fake = tmp_path / "fake"
    fake.mkdir(parents=True, exist_ok=True)
    if smi is not None:
        stand_in(fake, "nvidia-smi", smi)
    home = tmp_path / "home"
    if previous:
        (home / "runtime").mkdir(parents=True, exist_ok=True)
        (home / "runtime" / "runtime.json").write_text(f'{{\n "version": 1,\n "lane": "{previous}",\n "x": 1\n}}\n',
                                                       encoding="utf-8")
    prelude = f'source "{INSTALL}"; home="{home}"; WSL_NVIDIA_SMI=/nonexistent; step=lane; '
    return subprocess.run(["bash", "-c", prelude + script], capture_output=True, text=True, timeout=60,
                          env={"PATH": f"{fake}:/usr/bin:/bin", "HOME": str(tmp_path), "LC_ALL": "C.UTF-8"})


def lane(tmp_path, smi=None, previous=None, asked="auto"):
    p = sourced(tmp_path, f'choose_lane {asked}; printf "%s\\n%s\\n%s\\n" "$lane" "$lane_reason" "$lane_warning"',
                smi, previous)
    assert p.returncode == 0, p.stderr
    return tuple(p.stdout.split("\n")[:3])


GPU = 'echo "NVIDIA GeForce RTX 4070, {}, {}"'


@pytest.mark.parametrize("driver, cap, want", [
    ("581.57", "8.9", ("cu132", "NVIDIA GeForce RTX 4070, driver 581.57, compute capability 8.9", "")),
    ("580.82.07", "7.5", ("cu132", "NVIDIA GeForce RTX 4070, driver 580.82.07, compute capability 7.5", "")),
    ("560.94", "8.9", ("cu126", "NVIDIA GeForce RTX 4070, driver 560.94, compute capability 8.9",
                       "the guitar runs on the CPU: update the NVIDIA driver to 580 or newer, then paste the install "
                       "line again: it switches to the GPU build (about 3 GB)")),
    ("528.02", "6.1", ("cu126", "NVIDIA GeForce RTX 4070, driver 528.02, compute capability 6.1",
                       "the guitar runs on the CPU: update the NVIDIA driver to 580 or newer, then paste the install "
                       "line again: it switches to the GPU build (about 3 GB)")),
    ("581.57", "6.1", ("cu126", "NVIDIA GeForce RTX 4070, driver 581.57, compute capability 6.1",
                       "the guitar runs on the CPU: compute capability 6.1 is under 7.5, which the GPU build for the "
                       "guitar (cu132) needs")),
    ("527.99", "8.9", ("cpu", "NVIDIA GeForce RTX 4070 with driver 527.99: update the NVIDIA driver to 528 or newer, "
                              "then paste the install line again", "")),
    ("575.10", "12.0", ("cpu", "NVIDIA GeForce RTX 4070 (compute capability 12.0) needs a 580 or newer driver, and "
                               "this one is 575.10 (the cu126 build has no kernels for it): update the NVIDIA driver "
                               "to 580 or newer, then paste the install line again", "")),
])
def test_the_lane_from_nvidia_smi(tmp_path, driver, cap, want):
    """DESIGN 4.3's table: cu132 from driver 580 and capability 7.5; cu126 from driver 528 (the guitar on the CPU);
    the cpu lane under 528, or for a capability of 12.0 or more with a driver under 580."""
    assert lane(tmp_path, GPU.format(driver, cap)) == want


def test_no_gpu_and_a_gpu_out_of_reach(tmp_path):
    """No nvidia-smi, or one that lists nothing, is no GPU. One that fails (WSL's after a Windows update) is a GPU out
    of reach: a fresh install takes the cpu lane and says why; an existing GPU install is never moved to the cpu lane
    without --lane cpu."""
    assert lane(tmp_path) == ("cpu", "no NVIDIA GPU found", "")
    assert lane(tmp_path / "empty", "exit 0") == ("cpu", "no NVIDIA GPU found", "")
    blocked = 'echo "Failed to initialize NVML: GPU access blocked by the operating system"; exit 255'
    assert lane(tmp_path / "fresh", blocked) == (
        "cpu", "nvidia-smi failed, so CUDA cannot run: nvidia-smi failed (exit 255): Failed to initialize NVML: GPU "
               "access blocked by the operating system", "")
    assert lane(tmp_path / "was-cpu", blocked, previous="cpu")[0] == "cpu"
    p = sourced(tmp_path / "was-gpu", "choose_lane auto; echo chose $lane", blocked, previous="cu132")
    assert p.returncode == 2 and "chose" not in p.stdout
    assert p.stderr.splitlines()[-1] == (
        "songcharter: lane failed: nvidia-smi failed (exit 255): Failed to initialize NVML: GPU access blocked by the "
        "operating system: the GPU is out of reach, not missing, so this cu132 install is not moved to the CPU build. "
        "Restart Windows (or update the NVIDIA driver) and run the same line again; or add --lane cpu to move to the "
        "CPU build. Run the same command again to continue.")
    assert lane(tmp_path / "was-gpu", blocked, previous="cu132", asked="cpu") == (
        "cpu", "asked for with --lane cpu", "")
    assert lane(tmp_path / "asked", GPU.format("581.57", "8.9"), asked="cu126")[0] == "cu126"


def test_no_uv_sync_without_a_lane(tmp_path):
    """With no lane, `uv sync` would install PyPI's CUDA torch and leave allin1 without torchaudio: refused before uv
    runs."""
    stand_in(tmp_path / "bin", "uv", f'touch "{tmp_path}/uv-ran"')
    for chosen in ("", "cu999"):
        p = sourced(tmp_path, f'lane="{chosen}"; uv="{tmp_path}/bin/uv"; step=environments; sync_env x /app /env')
        assert p.returncode == 2 and not (tmp_path / "uv-ran").exists()
        assert p.stderr.splitlines()[-1].startswith(
            f"songcharter: environments failed: no torch lane is chosen ({chosen or 'none'}): it is cpu, cu126 or "
            "cu132. Without one, uv sync would install PyPI's CUDA torch")
    p = sourced(tmp_path, f'lane=cpu; uv="{tmp_path}/bin/uv"; sync_env x /app /env')
    assert p.returncode == 0 and (tmp_path / "uv-ran").exists()


def test_usage_and_the_template(tmp_path):
    def run(*args):
        return subprocess.run(["bash", str(INSTALL), *args], capture_output=True, text=True, timeout=60,
                              env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)})

    p = run("--bogus")
    assert p.returncode == 2 and "unknown option --bogus" in p.stderr
    assert run("--lane", "cu999").returncode == 2
    p = run("--yes")
    assert p.returncode == 2 and p.stderr.splitlines()[-1] == (
        "songcharter: start failed: this is install.sh's template: make the release with "
        "packaging/release/build.sh. Run the same command again to continue.")


def in_git() -> bool:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True).returncode == 0


@pytest.mark.skipif(not in_git(), reason="build.sh archives the git checkout's HEAD")
def test_build_writes_the_three_assets(tmp_path):
    """The tarball (HEAD, with its prefix), install.sh with every value filled in, SHA256SUMS of both; the filled
    install.sh then refuses root (a stand-in id). A published SHA-256 of uv that is not the pinned one stops it."""
    import sys
    fake = tmp_path / "fake"
    stand_in(fake, "curl", f'echo "{UV_SHA256}  uv-x86_64-unknown-linux-gnu.tar.gz"')
    env = {"PATH": f"{fake}:/usr/bin:/bin", "HOME": str(tmp_path), "PYTHON": sys.executable}
    out = tmp_path / "dist"
    p = subprocess.run(["bash", str(BUILD), "0.1.0-test", str(out)], capture_output=True, text=True, env=env,
                       timeout=300)
    assert p.returncode == 0, p.stderr
    tarball = out / "songcharter-0.1.0-test.tar.gz"
    assert sorted(x.name for x in out.iterdir()) == ["SHA256SUMS", "install.sh", tarball.name]
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    script = (out / "install.sh").read_text(encoding="utf-8")
    assert 'VERSION="0.1.0-test"' in script and f'APP_SHA256="{digest}"' in script
    assert ('RELEASE_URL="${SONGCHARTER_RELEASE_URL:-https://github.com/neb882/song-charting/releases/download/'
            'v0.1.0-test}"') in script
    assert ('UV_URL="https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-unknown-linux-gnu.tar.gz"'
            in script and f'UV_SHA256="{UV_SHA256}"' in script and "@VERSION@" not in script)
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert sums == [f"{hashlib.sha256((out / 'install.sh').read_bytes()).hexdigest()}  install.sh",
                    f"{digest}  {tarball.name}"]
    with tarfile.open(tarball) as t:
        names = t.getnames()
    assert all(n == "songcharter-0.1.0-test" or n.startswith("songcharter-0.1.0-test/") for n in names)
    assert "songcharter-0.1.0-test/pyproject.toml" in names and "songcharter-0.1.0-test/uv.lock" in names
    stand_in(fake, "id", "echo 0")
    p = subprocess.run(["bash", str(out / "install.sh"), "--yes"], capture_output=True, text=True, env=env, timeout=60)
    assert p.returncode == 2 and p.stderr.splitlines()[-1] == (
        "songcharter: start failed: songcharter installs for your own user: run it as your Ubuntu user, without sudo. "
        "Run the same command again to continue.")
    stand_in(fake, "curl", 'echo "0000  uv-x86_64-unknown-linux-gnu.tar.gz"')
    p = subprocess.run(["bash", str(BUILD), "0.1.0-test", str(out)], capture_output=True, text=True, env=env,
                       timeout=300)
    assert p.returncode == 1 and "published SHA-256 is '0000'" in p.stderr
