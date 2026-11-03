# 10-lanes (M4-01): the torch lanes. Both locks match their pyproject.toml, every lane of both projects installs from
# wheels alone on Linux x86_64 (packaging/check_wheels.py), and each lane's `uv sync --frozen` plans an install from
# the lock. Then the guard: allin1's cpu lane is installed (about 0.4 GB, into $CI_TMP) and allin1's real probe runs
# in it, so a lane that installs but cannot import fails here. Needs uv 0.13.5 on PATH (the projects' required
# version), the network, and $CI_PY with songcharter and pytest (default python3).
cd "$(dirname "${BASH_SOURCE[0]}")/../../.."   # the repository root
art=${CI_ART:-$(mktemp -d)}
tmp=${CI_TMP:-$(mktemp -d)}
py=${CI_PY:-python3}

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

# the guard. -k probe: the runner's probe tests, and the real one, which skips only without the variable
env="$tmp/lanes/allin1-cpu" log="$art/10-lanes-allin1-cpu-env.txt"
if ! UV_PROJECT_ENVIRONMENT="$env" uv sync --frozen --project packaging/allin1 --extra cpu >"$log" 2>&1; then
  cat "$log"
  exit 1
fi
echo "allin1-cpu: $(grep -E '^Installed' "$log")"
SONGCHARTER_ALLIN1_PYTHON="$env/bin/python" "$py" -m pytest -q -rs -p no:cacheprovider --basetemp="$tmp/lanes/pt" \
  tests/test_engines_sections.py -k probe | tee "$art/10-lanes-allin1-probe.txt"
if grep -q skipped "$art/10-lanes-allin1-probe.txt"; then
  echo "10-lanes: an allin1 probe test was skipped"
  exit 1
fi
