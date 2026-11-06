#!/usr/bin/env bash
# build.sh: the release assets of songcharter for WSL (M4-03), and the guide (M4-07).
#
#   bash packaging/release/build.sh <version> <out>
#
# <version> is HEAD's __version__, which pyproject.toml's version matches, optionally with a suffix (CI's
# <version>-ci-<sha>); another is refused (exit 2) before anything is written.
# Writes into <out>:
#   songcharter-<version>.tar.gz   `git archive` of HEAD (committed files only), with the prefix songcharter-<version>/,
#                                  and HEAD's packaging/NOTICE.txt added at its root (beside LICENSE);
#                                  check_no_audio.py checks every member before it counts
#   install.sh                     packaging/linux/install.sh with its @...@ values filled in: the version, the
#                                  tarball's SHA-256, the release URL prefix, NOTICE.txt at the release's tag (the
#                                  guide's link, which the licence prompt names on a first install), and uv's release
#                                  tarball with the SHA-256 published beside it (which must be the one pinned here)
#   SHA256SUMS                     both files'
#   GUIDE.md                       docs/guide/windows-wsl.md with {{VERSION}} and {{INSTALL_SHA256}} (install.sh's
#                                  SHA-256) filled in: the friend's guide, and the release's notes
# Needs git, curl and Python 3 ($PYTHON, default python3). The guide's line fetches install.sh from
# https://github.com/neb882/song-charting/releases/download/v<version>/ and checks it by SHA-256.
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "usage: build.sh <version> <out>" >&2
  exit 2
fi
version=$1 out=$2
if ! [[ $version =~ ^[0-9][0-9A-Za-z.+-]*$ ]]; then
  echo "build.sh: the version is digits, letters, '.', '+' and '-', starting with a digit, not '$version'" >&2
  exit 2
fi
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
# The version is HEAD's (M5-12): its dotted-integer part (0.2.0 of 0.2.0 or 0.2.0-ci-<sha>) must be that of HEAD's
# __version__ (songcharter/__init__.py) and of pyproject.toml's version. Else the app reports another version than
# its release, and its update notice offers the friend the release he already has. CI's -ci-<sha> suffix may follow.
base() { if [[ $1 =~ ^[0-9]+(\.[0-9]+)* ]]; then echo "${BASH_REMATCH[0]}"; fi; }
head_init=$(git -C "$root" cat-file blob HEAD:songcharter/__init__.py | sed -n 's/^__version__ = "\(.*\)"$/\1/p')
head_project=$(git -C "$root" cat-file blob HEAD:pyproject.toml |
  sed -n '/^\[project\]$/,/^\[/s/^version = "\(.*\)"$/\1/p')
want=$(base "$head_init")
if [ -z "$want" ] || [ "$(base "$version")" != "$want" ] || [ "$(base "$head_project")" != "$want" ]; then
  echo "build.sh: $version is not HEAD's version: its songcharter/__init__.py says '$head_init' and its" \
    "pyproject.toml '$head_project'. Build that version (a suffix such as -ci-<sha> may follow it), or bump both" \
    "(then uv lock) and commit first" >&2
  exit 2
fi
python=${PYTHON:-python3}
UV_VERSION=0.13.5
UV_URL=https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-x86_64-unknown-linux-gnu.tar.gz
UV_SHA256=f68d291c75783122dad58ab77def0e13f3233f358731db5d6d7e8715603b928f   # its .sha256 on 2026-11-03 [here]
RELEASE_URL=https://github.com/neb882/song-charting/releases/download/v$version
NOTICE_URL=https://github.com/neb882/song-charting/blob/v$version/packaging/NOTICE.txt   # as the guide links it
tarball=songcharter-$version.tar.gz

mkdir -p "$out"
out=$(cd "$out" && pwd)
rm -f "$out/$tarball" "$out/install.sh" "$out/SHA256SUMS" "$out/GUIDE.md"
# NOTICE.txt as HEAD has it, like the rest of the tarball: --add-file takes a file, named by its basename
notice=$(mktemp -d)
trap 'rm -rf "$notice"' EXIT
git -C "$root" cat-file blob HEAD:packaging/NOTICE.txt >"$notice/NOTICE.txt"
# install.sh and the guide from HEAD too, so the release never carries an edit the tag does not hold (M4-07's review)
git -C "$root" cat-file blob HEAD:packaging/linux/install.sh >"$notice/install.sh"
git -C "$root" cat-file blob HEAD:docs/guide/windows-wsl.md >"$notice/windows-wsl.md"
dirty=$(git -C "$root" status --porcelain --untracked-files=no)
if [ -n "$dirty" ]; then
  printf 'build.sh: built from HEAD; these uncommitted changes are not in the release:\n%s\n' "$dirty" >&2
fi
git -C "$root" archive --format=tar.gz --prefix="songcharter-$version/" --add-file="$notice/NOTICE.txt" \
  -o "$out/$tarball.part" HEAD
"$python" "$root/packaging/ci/check_no_audio.py" "$out/$tarball.part"
mv -f "$out/$tarball.part" "$out/$tarball"
app_sha=$(sha256sum "$out/$tarball" | cut -d' ' -f1)

published=$(curl -fsSL --retry 3 "$UV_URL.sha256" | cut -d' ' -f1)
if [ "$published" != "$UV_SHA256" ]; then
  echo "build.sh: uv $UV_VERSION's published SHA-256 is '$published', not the pinned $UV_SHA256" >&2
  exit 1
fi

sed -e "s|@VERSION@|$version|g" -e "s|@APP_SHA256@|$app_sha|g" -e "s|@RELEASE_URL@|$RELEASE_URL|g" \
  -e "s|@NOTICE_URL@|$NOTICE_URL|g" -e "s|@UV_URL@|$UV_URL|g" -e "s|@UV_SHA256@|$published|g" "$notice/install.sh" \
  >"$out/install.sh.part"
if grep -n '@[A-Z0-9_]*@' "$out/install.sh.part"; then
  echo "build.sh: install.sh still has a value to fill in (above)" >&2
  exit 1
fi
mv -f "$out/install.sh.part" "$out/install.sh"
(cd "$out" && sha256sum install.sh "$tarball" >SHA256SUMS)
install_sha=$(sha256sum "$out/install.sh" | cut -d' ' -f1)
sed -e "s|{{VERSION}}|$version|g" -e "s|{{INSTALL_SHA256}}|$install_sha|g" "$notice/windows-wsl.md" \
  >"$out/GUIDE.md.part"
if grep -n '{{\|}}' "$out/GUIDE.md.part"; then
  echo "build.sh: the guide still has a value to fill in (above)" >&2
  exit 1
fi
mv -f "$out/GUIDE.md.part" "$out/GUIDE.md"
echo "build.sh: songcharter $version in $out"
cat "$out/SHA256SUMS"
