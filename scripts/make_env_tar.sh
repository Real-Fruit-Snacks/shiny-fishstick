#!/usr/bin/env bash
set -euo pipefail

# make_env_tar.sh - Build a portable environment tarball (no single binary)
# Creates release/deltavision-<version>-linux-env.tar.gz with a venv and run script

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT_DIR"

VERSION=$(python - <<'PY'
from pathlib import Path
import re
p=Path('delta_vision/src/delta_vision/__about__.py').read_text()
m=re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", p)
print(m.group(1))
PY
)

STAGE_DIR="build_env/deltavision-${VERSION}"
VENV_DIR="${STAGE_DIR}/venv"

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}"

# Choose python: prefer project .venv if exists, else system python3
PYBIN="python3"
if [[ -x .venv/bin/python ]]; then
  PYBIN=".venv/bin/python"
fi

printf '\n==> Creating virtual environment (copies) at %s...\n' "${VENV_DIR}"
"${PYBIN}" -m venv --copies "${VENV_DIR}"

printf '\n==> Installing Delta Vision into the env...\n'
"${VENV_DIR}/bin/python" -m pip install -U pip >/dev/null
"${VENV_DIR}/bin/python" -m pip install ./delta_vision >/dev/null

# Create run script
cat > "${STAGE_DIR}/run.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P)"
"${DIR}/venv/bin/python" -m delta_vision "$@"
SH
chmod +x "${STAGE_DIR}/run.sh"

# Create README
cat > "${STAGE_DIR}/README-ENV.txt" <<'TXT'
Delta Vision - environment bundle (no single binary)

Usage (Linux):
  tar -xzf deltavision-<version>-linux-env.tar.gz
  cd deltavision-<version>
  ./run.sh --new /path/to/New --old /path/to/Old \
    --keywords /path/to/keywords.md

Server / Client:
  ./run.sh --server --port 8765 ...
  ./run.sh --client --host 1.2.3.4 --port 8765

Notes:
  - This bundle contains a Python virtual environment with all dependencies.
  - No internet access or extra installs required on target machine.
  - The run.sh script always uses the embedded Python.
TXT

# Tar it up
mkdir -p release
TARBALL="release/deltavision-${VERSION}-linux-env.tar.gz"
(
  cd build_env
  tar -czf "../${TARBALL}" "deltavision-${VERSION}"
)

printf '\nEnv tarball created:\n  %s\n' "${TARBALL}"
sha256sum "${TARBALL}" || shasum -a 256 "${TARBALL}" || true
