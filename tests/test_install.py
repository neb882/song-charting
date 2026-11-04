"""packaging/linux/install.sh's decisions, sourced in bash for its functions: the lane from a stand-in nvidia-smi
(each threshold), no silent move of a GPU install to the cpu lane when nvidia-smi fails, no `uv sync` without a lane,
and the usage and template refusals. Then packaging/release/build.sh's three assets, with a stand-in curl for uv's
published SHA-256. The whole install runs in CI (packaging/ci/linux.d/30-install.sh)."""
import hashlib
import io
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
    p = sourced(tmp_path / "was-cu126", "choose_lane auto; echo chose $lane", blocked, previous="cu126")
    assert p.returncode == 2 and "chose" not in p.stdout
    assert "the GPU is out of reach, not missing, so this cu126 install is not moved" in p.stderr.splitlines()[-1]
    assert lane(tmp_path / "asked", GPU.format("581.57", "8.9"), asked="cu126")[0] == "cu126"


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
PYTHON = r'''#!/bin/bash
# the environments' stand-in python: what each helper does is in mode-<module> (ok by default)
fake=@FAKE@
if [ "$2" = - ]; then cat >/dev/null; echo "doctor's summary"; exit 0; fi
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
    if [ "$module" = songcharter.runtime ]; then
      mkdir -p "$home/runtime" && echo '{"lane": "cpu"}' >"$home/runtime/runtime.json" && echo '{}' >"$home/doctor.json"
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
    release tarball), the environments' python (each helper's behaviour set by `mode`), id (a user, not root), df
    (100 GB free) and, on `wsl`, cmd.exe (it logs its arguments)."""

    def __init__(self, tmp: Path, wsl: bool = False):
        self.fake, self.home, self.dist = tmp / "fake", tmp / "home", tmp / "dist"
        for d in (self.fake / "bin", self.fake / "served", self.home, self.dist):
            d.mkdir(parents=True)
        (self.fake / "python").write_text(PYTHON.replace("@FAKE@", str(self.fake)), encoding="utf-8")
        (self.fake / "python").chmod(0o755)
        for name, body in (("curl", CURL), ("id", "#!/bin/sh\necho 1000\n"),
                           ("df", "#!/bin/sh\nprintf 'Avail\\n100000000000\\n'\n"),
                           ("cmd.exe", f'#!/bin/sh\necho "$*" >>{self.fake}/cmd.log\n')):
            if name != "cmd.exe" or wsl:
                (self.fake / "bin" / name).write_text(body.replace("@FAKE@", str(self.fake)), encoding="utf-8")
                (self.fake / "bin" / name).chmod(0o755)
        self.uv = tar_gz({"uv-x86_64-unknown-linux-gnu/uv": (UV.replace("@FAKE@", str(self.fake)).encode(), 0o755)})
        self.app = tar_gz({f"songcharter-{VERSION}/pyproject.toml": (b"[project]\n", 0o644)})
        self.serve("uv-x86_64-unknown-linux-gnu.tar.gz", self.uv)
        (self.dist / f"songcharter-{VERSION}.tar.gz").write_bytes(self.app)
        script = INSTALL.read_text(encoding="utf-8")
        for key, value in (("VERSION", VERSION), ("APP_SHA256", sha(self.app)), ("RELEASE_URL", "https://rel.invalid"),
                           ("UV_URL", UV_URL), ("UV_SHA256", sha(self.uv))):
            script = script.replace(f"@{key}@", value)
        (self.dist / "install.sh").write_text(script, encoding="utf-8")
        self.env = {"PATH": f"{self.fake / 'bin'}:/usr/bin:/bin", "HOME": str(self.home), "LC_ALL": "C.UTF-8",
                    **({"WSL_DISTRO_NAME": "Ubuntu-26.04"} if wsl else {})}

    def serve(self, name: str, data: bytes) -> None:
        (self.fake / "served" / name).write_bytes(data)

    def mode(self, module: str, mode: str) -> None:
        (self.fake / f"mode-songcharter.{module}").write_text(mode, encoding="utf-8")

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
    """The ten steps through to the launcher; a rerun downloads nothing; a complete .part is used as it is."""
    i = Install(tmp_path)
    p = i.run("--from", str(i.dist))
    assert p.returncode == 0, p.stderr
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
    """Without --yes, step 5 names the licences (NOTICE.txt, at the root of the app the tarball unpacks to) before
    "Continue? [Y/n]". No stops the install, exit 1, before any download; Enter, as the guide says, goes on."""
    i = Install(tmp_path)

    def answer(text: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(i.dist / "install.sh"), "--lane", "cpu", "--from", str(i.dist)],
                              input=text, capture_output=True, text=True, env=i.env, timeout=120)

    prompt = (f"Licences: {i.share}/app/{VERSION}/NOTICE.txt (some of the models are for non-commercial use only)\n"
              "Continue? [Y/n] ")
    p = answer("n\n")
    assert p.returncode == 1 and p.stdout.endswith(prompt + "songcharter: stopped; nothing was downloaded.\n"), p.stdout
    assert i.log("curl.log") == [] and list((i.share / "app").iterdir()) == [] and not i.launcher.exists()
    p = answer("\n")
    assert p.returncode == 0 and prompt in p.stdout, p.stdout + p.stderr
    assert i.launcher.is_file() and (i.share / "app" / VERSION / "pyproject.toml").is_file()


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


@pytest.mark.parametrize("free_gb, ok", [(7, False), (9, True)])
def test_the_cpu_lane_needs_8_gb_free(tmp_path, free_gb, ok):
    """2.8 GB installed (M4-05's CI) and 5 GB of work folders: 7 GB free is refused, 9 GB installs."""
    i = Install(tmp_path)
    (i.fake / "bin" / "df").write_text(f"#!/bin/sh\nprintf 'Avail\\n{free_gb * 1024 ** 3}\\n'\n", encoding="utf-8")
    p = i.run("--from", str(i.dist))
    assert (p.returncode == 0) is ok, p.stdout + p.stderr
    assert "lane cpu needs about 8 GB" in p.stdout
    assert ("not enough free disk" in p.stdout + p.stderr) is not ok
