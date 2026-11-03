# 10-lanes (M4-01): the torch lanes. Both locks match their pyproject.toml, every lane of both projects installs from
# wheels alone on Linux x86_64 (packaging/check_wheels.py), and each lane's `uv sync --frozen` plans an install from
# the lock. Needs uv 0.13.5 on PATH (the projects' required version) and the network; installs nothing.
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."   # the repository root
art=${CI_ART:-$(mktemp -d)}
tmp=${CI_TMP:-$(mktemp -d)}

uv --version
uv lock --check
uv lock --check --project packaging/allin1
uv run --no-project --with packaging python packaging/check_wheels.py | tee "$art/10-lanes-wheels.txt"

sync() {   # NAME ARGS...: `uv sync --frozen --dry-run ARGS` into an environment that does not exist (a fresh install)
  local name=$1 log="$art/10-lanes-$1.txt"
  shift
  if ! UV_PROJECT_ENVIRONMENT="$tmp/lanes/$name" uv sync --frozen --dry-run "$@" >"$log" 2>&1; then
    cat "$log"
    return 1
  fi
  echo "$name: $(grep -E '^Would (download|install)' "$log" | paste -sd ',' | sed 's/,/, /g')"
}
for lane in cpu cu126 cu132; do
  sync "app-$lane" --extra "$lane" --extra app
  sync "allin1-$lane" --project packaging/allin1 --extra "$lane"
done
