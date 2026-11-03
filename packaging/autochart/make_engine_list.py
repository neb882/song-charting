"""Write (or check) the file list of autochart's engine at the commit songcharter pins.

    python packaging/autochart/make_engine_list.py <autochart checkout>            # writes engine-files.sha256
    python packaging/autochart/make_engine_list.py <autochart checkout> --check    # exit 1 if the list differs

Every PC fetches autochart (AGPL) from its own repository as GitHub's archive of the pinned commit; songcharter never
ships it. GitHub does not promise that an archive's bytes stay the same, so its files are checked one by one against
this list instead: `<sha256>  <size>  <path>` per tracked file, from the commit's blobs (`git ls-files -s`, `git
cat-file`), sorted by path. The commit has no export-ignore, LFS or symlink entries, so its archive holds exactly
these files with these bytes. The first-launch setup (songcharter.runtime) and the WebGPU spike
(packaging/spike/spike-webgpu.ps1) read it.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

COMMIT = "b5a41e8e44db84d4c7288c946cf35aa2264dcbf5"   # engines/autochart.py's install (eval/tools/autochart/setup.sh)
LIST = Path(__file__).with_name("engine-files.sha256")


def git(checkout: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(checkout), *args], check=True, capture_output=True).stdout


def entries(checkout: Path) -> list[str]:
    """The list's lines for the pinned commit, read from the checkout's object store."""
    head = git(checkout, "rev-parse", "HEAD").decode().strip()
    if head != COMMIT:
        raise SystemExit(f"{checkout} is at {head}, not the pinned {COMMIT}")
    lines = []
    for row in git(checkout, "ls-files", "-s", "-z").split(b"\0"):
        if not row:
            continue
        meta, path = row.split(b"\t", 1)
        mode, blob, _stage = meta.decode().split()
        if mode not in ("100644", "100755"):
            raise SystemExit(f"{path.decode()} has mode {mode}: the archive would not hold it as a plain file")
        data = git(checkout, "cat-file", "blob", blob)
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {len(data)}  {path.decode('utf-8')}")
    return sorted(lines, key=lambda line: line.split("  ", 2)[2])


def render(lines: list[str]) -> str:
    return (f"# autochart {COMMIT}: <sha256>  <size>  <path> of every file in its archive "
            f"(packaging/autochart/make_engine_list.py)\n" + "\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    text = render(entries(Path(argv[0])))
    if "--check" in argv[1:]:
        same = LIST.is_file() and LIST.read_text(encoding="utf-8") == text
        print(f"{LIST}: {'matches' if same else 'DIFFERS from'} the checkout")
        return 0 if same else 1
    LIST.write_text(text, encoding="utf-8", newline="\n")
    print(f"{LIST}: {len(text.splitlines()) - 1} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
