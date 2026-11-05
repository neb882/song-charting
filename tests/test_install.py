"""packaging/linux/install.sh's decisions, sourced in bash for its functions: the lane from a stand-in nvidia-smi
(each threshold), no silent move of a GPU install to the cpu lane when nvidia-smi fails, no `uv sync` without a lane,
and the usage and template refusals. Then packaging/release/build.sh's three assets, with a stand-in curl for uv's
published SHA-256. The whole install runs in CI (packaging/ci/linux.d/30-install.sh)."""
import hashlib
import io
import json
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
    ("581.57", "12.0", ("cu132", "NVIDIA GeForce RTX 4070, driver 581.57, compute capability 12.0", "")),
    ("581.57", "[N/A]", ("cu132", "NVIDIA GeForce RTX 4070, driver 581.57, compute capability [N/A]", "")),
    ("560.94", "[N/A]", ("cu126", "NVIDIA GeForce RTX 4070, driver 560.94, compute capability [N/A]",
                         "the guitar runs on the CPU: update the NVIDIA driver to 580 or newer, then paste the install "
                         "line again: it switches to the GPU build (about 3 GB)")),
])
def test_the_lane_from_nvidia_smi(tmp_path, driver, cap, want):
    """DESIGN 4.3's table: cu132 from driver 580 and capability 7.5 (12.0 too); cu126 from driver 528 (the guitar on
    the CPU); the cpu lane under 528, or for a capability of 12.0 or more with a driver under 580. A capability
    nvidia-smi cannot read ([N/A]) counts as 7.5 or more."""
    assert lane(tmp_path, GPU.format(driver, cap)) == want


OUT_OF_REACH = ("the GPU is out of reach, not missing, so this is the CPU build: restart Windows (or update the NVIDIA "
                "driver), then paste the install line again: it switches to the GPU build (about 3 GB)")


def test_no_gpu_and_a_gpu_out_of_reach(tmp_path):
    """No nvidia-smi, or one that lists nothing, is no GPU. One that fails (WSL's after a Windows update) is a GPU out
    of reach: a fresh install takes the cpu lane, says why, and warns what to do once the GPU is back (the release
    gate's finding: nothing ever said to rerun); an existing GPU install is never moved to the cpu lane without
    --lane cpu."""
    assert lane(tmp_path) == ("cpu", "no NVIDIA GPU found", "")
    assert lane(tmp_path / "empty", "exit 0") == ("cpu", "no NVIDIA GPU found", "")
    blocked = 'echo "Failed to initialize NVML: GPU access blocked by the operating system"; exit 255'
    assert lane(tmp_path / "fresh", blocked) == (
        "cpu", "nvidia-smi failed, so CUDA cannot run: nvidia-smi failed (exit 255): Failed to initialize NVML: GPU "
               "access blocked by the operating system", OUT_OF_REACH)
    assert lane(tmp_path / "was-cpu", blocked, previous="cpu")[::2] == ("cpu", OUT_OF_REACH)
    p = sourced(tmp_path / "was-gpu", "choose_lane auto; echo chose $lane", blocked, previous="cu132")
    assert p.returncode == 2 and "chose" not in p.stdout
    assert p.stderr.splitlines()[-1] == (
        "songcharter: lane failed: nvidia-smi failed (exit 255): Failed to initialize NVML: GPU access blocked by the "
        "operating system: the GPU is out of reach, not missing, so this cu132 install is not moved to the CPU build. "
        "Restart Windows (or update the NVIDIA driver) and run the same line again; or add --lane cpu to move to the "
        "CPU build. Run the same command again to continue.")
    assert lane(tmp_path / "was-gpu", blocked, previous="cu132", asked="cpu") == (
        "cpu", "asked for with --lane cpu", "")
    from songcharter import device
    assert "asked for with --lane cpu".startswith(device.ASKED_LANE)   # doctor reads it so (no "paste again" note)
    p = sourced(tmp_path / "was-cu126", "choose_lane auto; echo chose $lane", blocked, previous="cu126")
    assert p.returncode == 2 and "chose" not in p.stdout
    assert "the GPU is out of reach, not missing, so this cu126 install is not moved" in p.stderr.splitlines()[-1]
    assert lane(tmp_path / "asked", GPU.format("581.57", "8.9"), asked="cu126")[0] == "cu126"


@pytest.mark.parametrize("before", ["cu126", "cu132"])
def test_the_guard_reads_runtime_json_as_runtime_py_writes_it(tmp_path, before):
    """previous_lane reads runtime.json line by line (sed), so the guard depends on the layout runtime._write_json
    gives it: here the file runtime_record writes and set_allin1 (the memory rule) rewrites, not a hand-written one
    (the release gate's tests-3: with a compact layout every test passed, and a failing nvidia-smi moved a GPU install
    to the cpu lane)."""
    from songcharter import runtime as R
    home = tmp_path / "home"
    (home / "runtime" / "allin1" / "bin").mkdir(parents=True)
    (home / "runtime" / "allin1" / "bin" / "python").write_text("", encoding="utf-8")
    R._write_json(R.runtime_file(home), R.runtime_record(R.Setup(home, tmp_path / "app", before, "a GPU")))
    assert R.set_allin1(home, False)
    assert sourced(tmp_path, 'echo "[$(previous_lane)]"').stdout == f"[{before}]\n"
    blocked = 'echo "Failed to initialize NVML: GPU access blocked by the operating system"; exit 255'
    p = sourced(tmp_path, "choose_lane auto; echo chose $lane", blocked)
    assert p.returncode == 2 and "chose" not in p.stdout, p.stdout
    assert f"the GPU is out of reach, not missing, so this {before} install is not moved" in p.stderr


def test_an_nvidia_smi_that_does_not_answer_is_a_gpu_out_of_reach(tmp_path):
    """A timeout (exit 124) is a GPU out of reach, as songcharter.device counts it: a fresh install says so, a GPU
    install is not moved to cpu."""
    script = 'SMI_TIMEOUT_S=1; choose_lane auto; printf "%s\\n%s\\n" "$lane" "$lane_reason"'
    p = sourced(tmp_path / "fresh", script, "sleep 10")
    assert p.returncode == 0 and p.stdout.split("\n")[:2] == [
        "cpu", "nvidia-smi failed, so CUDA cannot run: nvidia-smi did not answer within 1 s"]
    p = sourced(tmp_path / "gpu", script, "sleep 10", previous="cu132")
    assert p.returncode == 2 and p.stderr.splitlines()[-1].startswith(
        "songcharter: lane failed: nvidia-smi did not answer within 1 s: the GPU is out of reach, not missing")


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
    assert sorted(x.name for x in out.iterdir()) == ["GUIDE.md", "SHA256SUMS", "install.sh", tarball.name]
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    script = (out / "install.sh").read_text(encoding="utf-8")
    guide = (out / "GUIDE.md").read_text(encoding="utf-8")   # M4-07: the guide, its line with install.sh's hash
    line = (f'/v0.1.0-test/install.sh && echo "{sha((out / "install.sh").read_bytes())}  install.sh" | sha256sum -c - '
            "&& bash install.sh\n")
    assert "{{" not in guide and line in guide
    assert 'VERSION="0.1.0-test"' in script and f'APP_SHA256="{digest}"' in script
    assert ('RELEASE_URL="${SONGCHARTER_RELEASE_URL:-https://github.com/neb882/song-charting/releases/download/'
            'v0.1.0-test}"') in script
    assert ('UV_URL="https://github.com/astral-sh/uv/releases/download/0.13.5/uv-x86_64-unknown-linux-gnu.tar.gz"'
            in script and f'UV_SHA256="{UV_SHA256}"' in script and "@VERSION@" not in script)
    notice = "https://github.com/neb882/song-charting/blob/v0.1.0-test/packaging/NOTICE.txt"   # the guide's link
    guide_md = (ROOT / "docs" / "guide" / "windows-wsl.md").read_text(encoding="utf-8")
    assert f'NOTICE_URL="{notice}"' in script and notice.replace("0.1.0-test", "{{VERSION}}") in guide_md
    # the launcher and every call of the install's Python keep a songcharter/ folder in the current one out (-P)
    assert """exec "%s" -P -m songcharter.launch""" in script and '"$py" -m' not in script
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert sums == [f"{hashlib.sha256((out / 'install.sh').read_bytes()).hexdigest()}  install.sh",
                    f"{digest}  {tarball.name}"]
    with tarfile.open(tarball) as t:
        names = t.getnames()
    assert all(n == "songcharter-0.1.0-test" or n.startswith("songcharter-0.1.0-test/") for n in names)
    assert "songcharter-0.1.0-test/pyproject.toml" in names and "songcharter-0.1.0-test/uv.lock" in names
    assert "songcharter-0.1.0-test/NOTICE.txt" in names and "songcharter-0.1.0-test/LICENSE" in names
    stand_in(fake, "id", "echo 0")
    p = subprocess.run(["bash", str(out / "install.sh"), "--yes"], capture_output=True, text=True, env=env, timeout=60)
    assert p.returncode == 2 and p.stderr.splitlines()[-1] == (
        "songcharter: start failed: songcharter installs for your own user: run it as your Ubuntu user, without sudo. "
        "Run the same command again to continue.")
    stand_in(fake, "curl", 'echo "0000  uv-x86_64-unknown-linux-gnu.tar.gz"')
    p = subprocess.run(["bash", str(BUILD), "0.1.0-test", str(out)], capture_output=True, text=True, env=env,
                       timeout=300)
    assert p.returncode == 1 and "published SHA-256 is '0000'" in p.stderr



def test_build_ships_install_sh_and_the_guide_as_head_has_them(tmp_path):
    """A release is HEAD's, like its tarball: an uncommitted edit to install.sh or the guide stays out of dist/ and is
    named on stderr (M4-07's review: the published install.sh and guide once came from the working copy)."""
    import sys
    clone = tmp_path / "clone"
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", "--no-checkout", str(ROOT), str(clone)], check=True)
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", "--detach", head], check=True)   # this checkout's HEAD
    for rel in ("packaging/linux/install.sh", "docs/guide/windows-wsl.md"):
        with open(clone / rel, "a", encoding="utf-8") as f:
            f.write("\nzorp uncommitted\n")
    fake = tmp_path / "fake"
    stand_in(fake, "curl", f'echo "{UV_SHA256}  uv-x86_64-unknown-linux-gnu.tar.gz"')
    env = {"PATH": f"{fake}:/usr/bin:/bin", "HOME": str(tmp_path), "PYTHON": sys.executable}
    out = tmp_path / "dist"
    p = subprocess.run(["bash", str(clone / "packaging" / "release" / "build.sh"), "0.1.0-test", str(out)],
                       capture_output=True, text=True, env=env, timeout=300)
    assert p.returncode == 0, p.stderr
    assert "zorp" not in (out / "install.sh").read_text(encoding="utf-8")
    assert "zorp" not in (out / "GUIDE.md").read_text(encoding="utf-8")
    assert "uncommitted changes are not in the release" in p.stderr
    assert "packaging/linux/install.sh" in p.stderr and "docs/guide/windows-wsl.md" in p.stderr


# ------------------------------------------------------------------------------------------------ the whole install

VERSION = "0.0.0-test"
UV_URL = "https://uv.invalid/0.13.5/uv-x86_64-unknown-linux-gnu.tar.gz"
NOTICE_URL = "https://rel.invalid/blob/v0.0.0-test/packaging/NOTICE.txt"
PYTHON = r'''#!/bin/bash
# the environments' stand-in python: what each helper does is in mode-<module> (ok by default); the closing summary
# (python -P - doctor.json ...) is a stand-in line, or the real one when summary-python names a Python
fake=@FAKE@
if [ "$2" = - ]; then
  if [ -f "$fake/summary-python" ]; then exec "$(cat "$fake/summary-python")" "$@"; fi
  cat >/dev/null; echo "doctor's summary"; exit 0
fi
module=$3
shift 3
mode=$(cat "$fake/mode-$module" 2>/dev/null || echo ok)
home="" flag=""
while [ $# -gt 0 ]; do
  case $1 in --home) home=$2; shift 2 ;; --restart-flag) flag=$2; shift 2 ;; *) shift ;; esac
done
echo "$module $mode" >>"$fake/python.log"
case $mode in
  ok | problems)
    if [ "$module" = songcharter.runtime ]; then   # doctor.json: $fake/doctor.json when there is one
      mkdir -p "$home/runtime" && echo '{"lane": "cpu"}' >"$home/runtime/runtime.json" && echo '{}' >"$home/doctor.json"
      if [ -f "$fake/doctor.json" ]; then cp "$fake/doctor.json" "$home/doctor.json"; fi
    fi
    [ "$mode" = ok ] || exit 1 ;;
  early1) exit 1 ;;
  said2) echo "songcharter: autochart failed: no network. Run the same command again to continue." >&2
         echo "said" >"$SONGCHARTER_FAILURE"; exit 2 ;;
  silent2) echo "usage: an error that says nothing of continuing" >&2; exit 2 ;;
  kill) kill -9 $$ ;;
  changed) touch "$flag" ;;
esac
'''
UV = r'''#!/bin/sh
echo "$1 ${UV_CACHE_DIR:-unset}" >>@FAKE@/uv.log
case $1 in
  --version) echo "uv 0.13.5 (stand-in)" ;;
  python) echo "Python 3.13.17 is already installed" ;;
  sync) mkdir -p "$UV_PROJECT_ENVIRONMENT/bin" && cp @FAKE@/python "$UV_PROJECT_ENVIRONMENT/bin/python" ;;
esac
'''
CURL = r'''#!/bin/sh
# serves @FAKE@/served/<the URL's last part>; a name not there is curl's 22 (HTTP error)
out="" url=""
while [ $# -gt 0 ]; do
  case $1 in
    -o) out=$2; shift 2 ;;
    -C | --retry | --retry-delay | --connect-timeout) shift 2 ;;
    -*) shift ;;
    *) url=$1; shift ;;
  esac
done
echo "$url" >>@FAKE@/curl.log
[ -f "@FAKE@/served/${url##*/}" ] || exit 22
cp "@FAKE@/served/${url##*/}" "$out"
'''


def tar_gz(members: dict[str, tuple[bytes, int]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, (data, mode) in members.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), mode
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class Install:
    """A filled install.sh with a stand-in for everything it runs: curl (serving `served`), uv (inside its own
    release tarball), the environments' python (each helper's behaviour set by `mode`; `real_summary` gives the
    closing summary this Python and songcharter), id (a user, not root), df (100 GB free), sleep (no wait before WSL's
    restart) and, on `wsl`, cmd.exe (it logs its arguments)."""

    def __init__(self, tmp: Path, wsl: bool = False):
        self.fake, self.home, self.dist = tmp / "fake", tmp / "home", tmp / "dist"
        for d in (self.fake / "bin", self.fake / "served", self.home, self.dist):
            d.mkdir(parents=True)
        (self.fake / "python").write_text(PYTHON.replace("@FAKE@", str(self.fake)), encoding="utf-8")
        (self.fake / "python").chmod(0o755)
        for name, body in (("curl", CURL), ("id", "#!/bin/sh\necho 1000\n"), ("sleep", "#!/bin/sh\nexit 0\n"),
                           ("df", "#!/bin/sh\nprintf 'Avail\\n100000000000\\n'\n"),
                           ("cmd.exe", f'#!/bin/sh\necho "$*" >>{self.fake}/cmd.log\n')):
            if name != "cmd.exe" or wsl:
                (self.fake / "bin" / name).write_text(body.replace("@FAKE@", str(self.fake)), encoding="utf-8")
                (self.fake / "bin" / name).chmod(0o755)
        self.uv = tar_gz({"uv-x86_64-unknown-linux-gnu/uv": (UV.replace("@FAKE@", str(self.fake)).encode(), 0o755)})
        self.app = tar_gz({f"songcharter-{VERSION}/pyproject.toml": (b"[project]\n", 0o644),
                           f"songcharter-{VERSION}/NOTICE.txt": (b"the licences\n", 0o644)})
        self.serve("uv-x86_64-unknown-linux-gnu.tar.gz", self.uv)
        (self.dist / f"songcharter-{VERSION}.tar.gz").write_bytes(self.app)
        script = INSTALL.read_text(encoding="utf-8")
        for key, value in (("VERSION", VERSION), ("APP_SHA256", sha(self.app)), ("RELEASE_URL", "https://rel.invalid"),
                           ("NOTICE_URL", NOTICE_URL), ("UV_URL", UV_URL), ("UV_SHA256", sha(self.uv))):
            script = script.replace(f"@{key}@", value)
        (self.dist / "install.sh").write_text(script, encoding="utf-8")
        self.env = {"PATH": f"{self.fake / 'bin'}:/usr/bin:/bin", "HOME": str(self.home), "LC_ALL": "C.UTF-8",
                    "UV_CACHE_DIR": str(self.home / ".cache" / "uv-shared"),   # the person's, for every uv project
                    **({"WSL_DISTRO_NAME": "Ubuntu-26.04"} if wsl else {})}

    def serve(self, name: str, data: bytes) -> None:
        (self.fake / "served" / name).write_bytes(data)

    def mode(self, module: str, mode: str) -> None:
        (self.fake / f"mode-songcharter.{module}").write_text(mode, encoding="utf-8")

    def real_summary(self, doctor: dict) -> None:
        """The closing summary from this Python's songcharter.device, of `doctor` as step 8's doctor.json."""
        import sys
        (self.fake / "summary-python").write_text(sys.executable, encoding="utf-8")
        (self.fake / "doctor.json").write_text(json.dumps(doctor), encoding="utf-8")
        self.env["PYTHONPATH"] = str(ROOT)

    def log(self, name: str) -> list[str]:
        path = self.fake / name
        return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []

    def run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(self.dist / "install.sh"), "--lane", "cpu", "--yes", *args],
                              capture_output=True, text=True, env=self.env, timeout=120, stdin=subprocess.DEVNULL)

    @property
    def share(self) -> Path:
        return self.home / ".local" / "share" / "songcharter"

    @property
    def launcher(self) -> Path:
        return self.home / ".local" / "bin" / "songcharter"


def last(p: subprocess.CompletedProcess) -> str:
    return (p.stderr.strip().splitlines() or [""])[-1]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_a_release_installs_with_stand_ins(tmp_path):
    """The ten steps through to the launcher; a rerun downloads nothing; a complete .part is used as it is. Every uv
    call has songcharter's own cache, runtime/uv-cache, over the person's $UV_CACHE_DIR (the release gate's finding:
    uninstall once deleted the person's whole uv cache)."""
    i = Install(tmp_path)
    p = i.run("--from", str(i.dist))
    assert p.returncode == 0, p.stderr
    ours = i.share / "runtime" / "uv-cache"
    assert i.log("uv.log") == [f"--version {ours}", f"python {ours}", f"sync {ours}", f"sync {ours}"]
    assert f"songcharter {VERSION} is installed (lane cpu: asked for with --lane cpu)." in p.stdout
    assert i.launcher.read_text(encoding="utf-8") == (
        f'#!/bin/sh\nexec "{i.share}/runtime/env/bin/python" -P -m songcharter.launch "$@"\n')
    assert (i.share / "runtime" / "state" / "install.done").read_text() == f"version={VERSION}\nlane=cpu\n"
    assert i.log("curl.log") == [UV_URL] and (i.share / "app" / VERSION / "pyproject.toml").is_file()
    assert i.run("--from", str(i.dist)).returncode == 0 and len(i.log("curl.log")) == 1
    (i.share / "bin" / "uv").unlink()
    (i.share / "runtime" / "state" / "downloads" / "uv.tar.gz.part").write_bytes(i.uv)   # a download that finished
    assert i.run("--from", str(i.dist)).returncode == 0 and len(i.log("curl.log")) == 1


def test_the_prompt_names_the_licences_and_enter_goes_on(tmp_path):
    """Without --yes, step 5 names the licences before "Continue? [Y/n]": on a first install the release's
    NOTICE.txt (its URL: the app that holds a copy is downloaded only after the answer, the release gate's finding),
    once the app is here its own copy. No stops the install, exit 1, before any download; Enter, as the guide says,
    goes on."""
    i = Install(tmp_path)

    def answer(text: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(i.dist / "install.sh"), "--lane", "cpu", "--from", str(i.dist)],
                              input=text, capture_output=True, text=True, env=i.env, timeout=120)

    def prompt(notice: str) -> str:
        return f"Licences: {notice} (some of the models are for non-commercial use only)\nContinue? [Y/n] "

    p = answer("n\n")
    assert p.returncode == 1 and p.stdout.endswith(prompt(NOTICE_URL) + "songcharter: stopped; nothing was "
                                                   "downloaded.\n"), p.stdout
    assert i.log("curl.log") == [] and list((i.share / "app").iterdir()) == [] and not i.launcher.exists()
    p = answer("\n")
    assert p.returncode == 0 and prompt(NOTICE_URL) in p.stdout, p.stdout + p.stderr
    assert i.launcher.is_file() and (i.share / "app" / VERSION / "pyproject.toml").is_file()
    here = i.share / "app" / VERSION / "NOTICE.txt"
    p = answer("n\n")   # a rerun: the app is here, with its copy
    assert p.returncode == 1 and prompt(str(here)) in p.stdout and here.read_text() == "the licences\n", p.stdout


@pytest.mark.parametrize("served", ["wrong", "truncated"])
def test_a_download_that_is_not_the_pinned_file_fails_the_install(tmp_path, served):
    i = Install(tmp_path)
    bad = b"not uv at all" if served == "wrong" else i.uv[: len(i.uv) // 2]
    i.serve("uv-x86_64-unknown-linux-gnu.tar.gz", bad)
    p = i.run("--from", str(i.dist))
    assert p.returncode == 2 and last(p) == (
        f"songcharter: downloads failed: {UV_URL} has SHA-256 {sha(bad)}, not the pinned {sha(i.uv)}. Run the same "
        "command again to continue.")
    assert list((i.share / "runtime" / "state" / "downloads").iterdir()) == [] and not (i.share / "bin" / "uv").exists()
    assert not i.launcher.exists()


def test_a_release_asset_that_is_not_the_built_one_fails_the_install(tmp_path):
    """From a folder: another tarball, or none. From a URL prefix: another tarball. From nowhere: curl's error."""
    i = Install(tmp_path)
    tarball = i.dist / f"songcharter-{VERSION}.tar.gz"
    tarball.write_bytes(tar_gz({f"songcharter-{VERSION}/evil": (b"!", 0o644)}))
    p = i.run("--from", str(i.dist))
    assert p.returncode == 2 and last(p) == (
        f"songcharter: downloads failed: {tarball} is not the file this install.sh was built with. Run the same "
        "command again to continue.")
    assert not (i.share / "app" / VERSION).exists() and not i.launcher.exists()
    tarball.unlink()
    p = i.run("--from", str(i.dist))
    assert p.returncode == 2 and f"{i.dist} has no {tarball.name}" in last(p)
    i.serve(tarball.name, b"another tarball")
    p = i.run("--from", "https://mirror.invalid/v0")
    assert p.returncode == 2 and last(p).startswith(
        f"songcharter: downloads failed: https://mirror.invalid/v0/{tarball.name} has SHA-256 "
        f"{sha(b'another tarball')}, not the pinned {sha(i.app)}.")
    (i.fake / "served" / tarball.name).unlink()
    p = i.run()   # the release URL, which serves nothing here
    assert p.returncode == 2 and last(p).startswith(
        f"songcharter: downloads failed: could not download https://rel.invalid/{tarball.name}.")
    i.serve(tarball.name, i.app)
    assert i.run("--from", "https://mirror.invalid/v0").returncode == 0
    assert i.log("curl.log")[-1] == f"https://mirror.invalid/v0/{tarball.name}"


@pytest.mark.parametrize("module, mode, line", [
    ("runtime", "kill", "songcharter: setup failed: python -m songcharter.runtime setup stopped before it finished "
                        "(killed by signal 9 (KILL): perhaps Linux ran out of memory). Run the same command again to "
                        "continue."),
    ("runtime", "silent2", "songcharter: setup failed: python -m songcharter.runtime setup stopped before it finished "
                           "(exit 2). Run the same command again to continue."),
    ("runtime", "said2", "songcharter: autochart failed: no network. Run the same command again to continue."),
    ("runtime", "early1", "songcharter: setup failed: python -m songcharter.runtime setup exited 1 before doctor ran "
                          "(its error is above). Run the same command again to continue."),
    ("wslsetup", "kill", "songcharter: windows failed: python -m songcharter.wslsetup apply stopped before it "
                         "finished (killed by signal 9 (KILL): perhaps Linux ran out of memory). Run the same command "
                         "again to continue."),
])
def test_a_helper_that_fails_ends_the_install_with_the_line(tmp_path, module, mode, line):
    """Steps 8 and 9: any end but 0 and 1 (a signal such as the out-of-memory killer's, an exit with no line, the
    helper's own line, said once) and setup's 1 before doctor ran (doctor.json not this run's) stop the install
    before the launcher, with the one last line."""
    i = Install(tmp_path, wsl=module == "wslsetup")
    i.mode(module, mode)
    p = i.run("--from", str(i.dist))
    assert p.returncode == 2 and last(p) == line, p.stderr
    assert p.stderr.count("Run the same command again") == 1
    assert not i.launcher.exists() and "is installed" not in p.stdout


def test_doctors_problems_still_install_and_a_changed_wslconfig_restarts_wsl(tmp_path):
    i = Install(tmp_path, wsl=True)
    i.mode("runtime", "problems")   # doctor.json written by this run, exit 1: installed, exit 1
    p = i.run("--from", str(i.dist))
    assert p.returncode == 1 and i.launcher.is_file() and "is installed" in p.stdout
    assert "WSL restarts now" not in p.stdout and not any("--shutdown" in c for c in i.log("cmd.log"))
    i.mode("runtime", "ok")
    i.mode("wslsetup", "changed")   # .wslconfig changed: the restart line, then wsl.exe --shutdown
    p = i.run("--from", str(i.dist))
    assert p.returncode == 0 and p.stdout.rstrip().endswith(
        "WSL restarts now so the new memory setting takes effect. Then start songcharter from the Start menu.")
    assert i.log("cmd.log")[-1] == "/d /c wsl.exe --shutdown"
    assert not (i.share / "runtime" / "state" / "restart-wsl").exists()


def test_a_first_install_with_the_gpu_out_of_reach_ends_with_what_to_do(tmp_path):
    """The lane's warning is said at step 2 and again after the install's last line, where the person reads."""
    i = Install(tmp_path)
    stand_in(i.fake / "bin", "nvidia-smi", 'echo "Failed to initialize NVML: GPU access blocked"; exit 255')
    p = i.run("--from", str(i.dist), "--lane", "auto")
    assert p.returncode == 0, p.stderr
    lines = p.stdout.splitlines()
    assert lines.count(f"warning: {OUT_OF_REACH}") == 2 and lines[lines.index(
        f"songcharter {VERSION} is installed (lane cpu: nvidia-smi failed, so CUDA cannot run: nvidia-smi failed (exit "
        "255): Failed to initialize NVML: GPU access blocked).") + 1] == f"warning: {OUT_OF_REACH}"


def test_what_runtime_holds_counts_as_here_already(tmp_path):
    """A rerun or a lane change counts what songcharter's runtime/ holds, uv's cache in it included, toward the space
    it needs (the review's F-1): with 4 GB in runtime/uv-cache, 6 GB free is enough for the cpu lane's 8 GB; without
    that credit it would be refused for space it already has."""
    i = Install(tmp_path)
    cache = i.share / "runtime" / "uv-cache"
    cache.mkdir(parents=True)
    with open(cache / "a-wheel.whl", "wb") as f:
        f.truncate(4 * 10 ** 9)   # sparse: its apparent size is what du -b counts
    (i.fake / "bin" / "df").write_text(f"#!/bin/sh\nprintf 'Avail\\n{6 * 10 ** 9}\\n'\n", encoding="utf-8")
    p = i.run("--from", str(i.dist))
    assert p.returncode == 0, p.stdout + p.stderr
    assert "lane cpu needs about 8 GB (the downloads unpacked, and 5 GB of work folders); 4.0 GB of it is here " \
        "already" in p.stdout


@pytest.mark.parametrize("free_gb, ok", [(7, False), (9, True)])
def test_the_cpu_lane_needs_8_gb_free(tmp_path, free_gb, ok):
    """2.8 GB installed (M4-05's CI) and 5 GB of work folders: 7 GB free is refused, 9 GB installs. What is
    already here counts only from songcharter's own folders: 20 GB in the person's uv caches is not songcharter's."""
    i = Install(tmp_path)
    for other in (i.home / ".cache" / "uv", i.home / ".cache" / "uv-shared"):
        other.mkdir(parents=True)
        with open(other / "another-project.whl", "wb") as f:
            f.truncate(20 * 10 ** 9)   # sparse: its apparent size is what du -b counts
    (i.fake / "bin" / "df").write_text(f"#!/bin/sh\nprintf 'Avail\\n{free_gb * 1024 ** 3}\\n'\n", encoding="utf-8")
    p = i.run("--from", str(i.dist))
    assert (p.returncode == 0) is ok, p.stdout + p.stderr
    assert "lane cpu needs about 8 GB" in p.stdout
    assert ("not enough free disk" in p.stdout + p.stderr) is not ok


# ------------------------------------------------------------------------------------------------ the closing summary

UNDER_8 = 7618   # WSL's MemTotal in MB (2^20 bytes): 7.99e9 bytes, just under device.MIN_WSL_MEMORY's 8e9 (the skeptic's)
MEMORY_PROBLEM = "problem: WSL has 7.4 GB of memory, under 8 GB"
CLOSING = "WSL's memory is measured again after the restart."


def doctor(home: Path, monkeypatch, total_mb: int = UNDER_8, free_mb: int = 50_000, wsl: bool = True,
           wslconfig_gb: int | None = None) -> dict:
    """doctor.json as step 8 writes it, with its problems and notes from device.findings: no GPU, the cpu lane, WSL
    (with interop, Windows' RAM 15.4 GiB, .wslconfig none or `wslconfig_gb`) or plain Linux, WSL's MemTotal and the
    free disk as given."""
    from songcharter import device
    monkeypatch.setenv("HOME", str(home))   # the disk problem names the home folder, as on the install's own
    asked = None if wslconfig_gb is None else wslconfig_gb * 2 ** 30
    r = {"songcharter": "0.0.0-test", "written": "2026-11-05T12:00:00+0000", "platform": "Linux-test",
         "python": {"version": "3.13.17", "executable": "/opt/test/python"},
         "wsl": {"distro": "Ubuntu-26.04", "windows_build": "10.0.26100.1000", "interop": True, "windows_ram_mb": 15770,
                 "wslconfig": {"path": "C:\\Users\\someone\\.wslconfig", "exists": asked is not None,
                               "memory_bytes": asked, "swap_bytes": None, "localhost_forwarding": None,
                               "networking_mode": None},
                 "memory_matches_config": device.memory_matches(total_mb, asked),
                 "documents": {"registry": None, "windows": None, "linux": None}} if wsl else None,
         "gpu": None, "gpu_error": "nvidia-smi not found", "torch": {"installed": True, "version": "2.15.0+cpu",
                                                                    "cuda": None},
         "device": {"chosen": "cpu", "reason": "no NVIDIA GPU found"}, "guitar_device": "cpu", "guitar_reason": "no GPU",
         "cpu": {"logical": 4, "threads_default": 3},
         "ram": {"total_mb": total_mb, "available_mb": total_mb - 800, "swap_total_mb": 2048, "swap_free_mb": 2048},
         "disk": {"home_free_mb": free_mb, "windows_c_free_mb": 90_000 if wsl else None},
         "components": {"ffmpeg": {"ok": True, "version": "n9"}, "allin1": {"ok": True, "package": "all-in-one-infer",
                                                                            "version": "3.1.0", "cuda": False,
                                                                            "python": "/opt/test/allin1"}},
         "install": {"lane": "cpu", "lane_reason": "asked for with --lane cpu"}}
    r["problems"], r["notes"] = device.findings(r)
    r["ok"] = not r["problems"]
    return r


def summary(p: subprocess.CompletedProcess) -> list[str]:
    """The closing summary's lines: after "launcher:", to the verdict, and the closing line when it follows."""
    lines = p.stdout.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("launcher: "))
    end = next(i for i, line in enumerate(lines) if line.startswith("doctor: ") and i > start)
    return lines[start + 1:end + (2 if lines[end + 1:end + 2] == [CLOSING] else 1)]


def test_a_restart_leaves_the_memory_doctor_measured_before_it_out_of_the_summary(tmp_path, monkeypatch):
    """The advisor's finding 7 on the release candidate and its skeptic: step 8's doctor measured WSL's memory before
    step 9 wrote .wslconfig, which applies at the restart that follows, so on a PC whose WSL has just under 8 GB the
    summary said "WSL has 7.4 GB of memory, under 8 GB" and "doctor: 1 problem", and install.sh exited 1, five
    seconds before the restart that cures it. With step 9's flag: no memory problem, no memory note ("under 11 GB:
    allin1 is left out"), not "no .wslconfig", the closing line, exit 0; the other notes stay. With no flag (here a
    rerun after an interrupted restart: .wslconfig kept at 12 GB, not yet in force), all of it, and exit 1."""
    i = Install(tmp_path, wsl=True)
    r = doctor(i.home, monkeypatch)
    assert any(p.startswith(MEMORY_PROBLEM[9:]) for p in r["problems"]) and len(r["problems"]) == 1
    assert any("under 11 GB: allin1 is left out" in n for n in r["notes"])
    i.real_summary(r)
    i.mode("runtime", "problems")   # setup's exit 1: doctor found the problem
    i.mode("wslsetup", "changed")   # step 9 wrote .wslconfig: its flag
    p = i.run("--from", str(i.dist))
    assert p.returncode == 0, p.stdout + p.stderr
    lines = summary(p)
    assert lines[-2:] == ["doctor: OK", CLOSING], lines
    assert not any(line.startswith("problem:") or "11 GB" in line or "no .wslconfig" in line for line in lines), lines
    assert lines[1] == "WSL: Ubuntu-26.04 on Windows 10.0.26100.1000, interop on; Windows RAM 15.4 GB; .wslconfig: " \
                       "just written"
    assert "note: CPU mode: no NVIDIA GPU found" in lines and "note: the guitar runs on the CPU: no GPU" in lines
    assert "RAM: 7.4 GB, 6.7 GB available; swap 0.0 of 2.0 GB used" in lines   # what was measured, as it was
    assert p.stdout.rstrip().endswith("WSL restarts now so the new memory setting takes effect. Then start songcharter "
                                      "from the Start menu.")
    assert i.log("cmd.log")[-1] == "/d /c wsl.exe --shutdown"

    j = Install(tmp_path / "kept", wsl=True)
    r = doctor(j.home, monkeypatch, wslconfig_gb=12)   # .wslconfig asks for 12 GB, WSL has 7.4: not restarted yet
    j.real_summary(r)
    j.mode("runtime", "problems")
    p = j.run("--from", str(j.dist))   # step 9 keeps .wslconfig: no flag, no restart
    assert p.returncode == 1, p.stdout + p.stderr
    lines = summary(p)
    assert lines[-1] == "doctor: 1 problem" and CLOSING not in p.stdout and "WSL restarts now" not in p.stdout
    assert [line for line in lines if line.startswith("problem:")] == [f"problem: {r['problems'][0]}"]
    assert lines[-1 - len(r["notes"]):-1] == [f"note: {n}" for n in r["notes"]]   # the note under 11 GB among them
    assert any("but .wslconfig asks for 12.0 GB: restart WSL" in n for n in r["notes"])
    assert lines[1].endswith("; .wslconfig memory 12.0 GB: not in force")
    assert not any("--shutdown" in c for c in j.log("cmd.log"))


def test_a_restart_keeps_the_disk_problem_in_the_summary(tmp_path, monkeypatch):
    """With the flag, only what doctor said of WSL's memory goes: a disk problem is printed, and install.sh exits 1
    for it, with the closing line."""
    i = Install(tmp_path, wsl=True)
    r = doctor(i.home, monkeypatch, free_mb=4000)
    assert len(r["problems"]) == 2
    i.real_summary(r)
    i.mode("runtime", "problems")
    i.mode("wslsetup", "changed")
    p = i.run("--from", str(i.dist))
    assert p.returncode == 1, p.stdout + p.stderr
    lines = summary(p)
    assert [line for line in lines if line.startswith("problem:")] == [
        f"problem: only 3.9 GB free in WSL ({i.home}): a chart needs 6 GB"]
    assert lines[-2:] == ["doctor: 1 problem", CLOSING] and i.log("cmd.log")[-1] == "/d /c wsl.exe --shutdown"


@pytest.mark.parametrize("free_mb", [4000, 50_000])
def test_plain_linux_has_the_summary_as_it_was(tmp_path, monkeypatch, free_mb):
    """No WSL, so no flag: the summary is doctor.json's as it is, with no closing line, and the exit status is
    setup's (1 with a problem)."""
    i = Install(tmp_path)
    r = doctor(i.home, monkeypatch, free_mb=free_mb, wsl=False)
    i.real_summary(r)
    i.mode("runtime", "problems" if r["problems"] else "ok")
    p = i.run("--from", str(i.dist))
    assert p.returncode == (1 if r["problems"] else 0), p.stdout + p.stderr
    lines = summary(p)
    assert lines[1] == "WSL: no" and CLOSING not in p.stdout
    assert [line for line in lines if line.startswith(("problem:", "note:"))] == (
        [f"problem: {x}" for x in r["problems"]] + [f"note: {x}" for x in r["notes"]])
    assert lines[-1] == ("doctor: 1 problem" if r["problems"] else "doctor: OK")


def test_a_restart_also_leaves_out_the_old_wslconfigs_memory(tmp_path, monkeypatch):
    """The review's m3: .wslconfig asks for 10 GB, not yet in force (WSL has 7.4), and step 9 raises it to 12 GB
    (its flag): the note "but .wslconfig asks for 10.0 GB: restart WSL" names the file step 9 has just replaced and
    asks for the restart that follows, so it is left out with the rest of what doctor said of WSL's memory."""
    i = Install(tmp_path, wsl=True)
    r = doctor(i.home, monkeypatch, wslconfig_gb=10)
    assert any("but .wslconfig asks for 10.0 GB: restart WSL" in n for n in r["notes"])
    i.real_summary(r)
    i.mode("runtime", "problems")
    i.mode("wslsetup", "changed")
    p = i.run("--from", str(i.dist))
    assert p.returncode == 0, p.stdout + p.stderr
    lines = summary(p)
    assert lines[-2:] == ["doctor: OK", CLOSING] and not any("asks for" in line for line in lines), lines
    assert lines[1].endswith("; Windows RAM 15.4 GB; .wslconfig: just written"), lines[1]   # not the old 10 GB


def test_a_summary_that_crashes_leaves_setups_exit_status(tmp_path, monkeypatch):
    """The review's m2: with the flag, the summary's exit status is doctor's verdict only when it is 0 or 1; a
    summary that crashes (here doctor.json with no "python") exits 3 with its traceback, and install.sh keeps
    setup's status (0 here), not "doctor found problems"."""
    i = Install(tmp_path, wsl=True)
    i.real_summary({"ok": True, "problems": [], "notes": [], "components": None})
    i.mode("wslsetup", "changed")
    p = i.run("--from", str(i.dist))
    assert p.returncode == 0, p.stdout + p.stderr
    assert "KeyError: 'python'" in p.stderr and "is installed" in p.stdout and CLOSING not in p.stdout
    assert i.log("cmd.log")[-1] == "/d /c wsl.exe --shutdown"
