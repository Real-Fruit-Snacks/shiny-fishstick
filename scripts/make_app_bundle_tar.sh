#!/usr/bin/env bash
set -euo pipefail

# make_app_bundle_tar.sh - Build a tarball that looks like the app directory (delta_vision/)
# but includes an embedded virtual environment so users need no external downloads.
# Output: release/deltavision-<version>-linux-app.tar.gz (root folder inside is delta_vision/)

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

STAGE_ROOT="build_app"
STAGE_DIR="${STAGE_ROOT}/delta_vision"
STAGE_ABS="${ROOT_DIR}/${STAGE_DIR}"
VENV_DIR="${STAGE_DIR}/.venv"
VENV_PY="${STAGE_ABS}/.venv/bin/python"

rm -rf "${STAGE_DIR}" "${STAGE_ROOT}"
mkdir -p "${STAGE_DIR}"

printf '\n==> Copying application tree into staging...\n'
# Copy the app folder as-is, excluding common junk
rsync -a --delete \
  --exclude '.venv' \
  --exclude 'build' \
  --exclude 'dist' \
  --exclude '**/__pycache__' \
  --exclude '**/*.pyc' \
  --exclude '**/*.pyo' \
  --exclude '**/.pytest_cache' \
  --exclude '**/*.log' \
  "delta_vision/" "${STAGE_DIR}/"

# Create venv inside app dir
printf '\n==> Creating embedded virtual environment at %s...\n' "${VENV_DIR}"
PYBIN="python3"
if [[ -x .venv/bin/python ]]; then
  PYBIN=".venv/bin/python"
fi
"${PYBIN}" -m venv --copies "${VENV_DIR}"
VENV_PY="${STAGE_ABS}/.venv/bin/python"

# Install the app (and deps) into the embedded venv, from the staged copy
printf "\n==> Installing app into the embedded env (this step uses the builder's internet, end users will be offline)...\n"
"${VENV_PY}" -m pip install -U pip >/dev/null
(
  cd "${STAGE_DIR}"
  "${VENV_PY}" -m pip install . >/dev/null
)

# Launcher that preserves the standard layout; it always uses the embedded venv
cat > "${STAGE_DIR}/run.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P)"
"${DIR}/.venv/bin/python" -m delta_vision "$@"
SH
chmod +x "${STAGE_DIR}/run.sh"

# Readme for the app-style bundle
cat > "${STAGE_DIR}/README-APP.txt" <<'TXT'
Delta Vision - app-style bundle (includes embedded Python environment)

This tarball looks like a normal application directory (delta_vision/) and
includes a hidden .venv with all dependencies preinstalled. No internet or
extra installs are needed on the target machine.

Usage (Linux):
  tar -xzf deltavision-<version>-linux-app.tar.gz
  cd delta_vision
  ./run.sh --new /path/to/New --old /path/to/Old \
    --keywords /path/to/keywords.md

Server / Client:
  ./run.sh --server --port 8765 ...
  ./run.sh --client --host 1.2.3.4 --port 8765

Notes:
  - The embedded .venv contains its own Python interpreter and packages.
  - You can inspect/edit the source under this folder; run.sh always uses .venv.
  - If you edit the code and want to reinstall into .venv, run:
      ./.venv/bin/pip install -e .
TXT

# Package it with delta_vision/ as root
mkdir -p release
OUT_TAR="release/deltavision-${VERSION}-linux-app.tar.gz"
(
  cd "${STAGE_ROOT}"
  tar -czf "../${OUT_TAR}" delta_vision
)

printf '\nApp-style tarball created:\n  %s\n' "${OUT_TAR}"
sha256sum "${OUT_TAR}" || shasum -a 256 "${OUT_TAR}" || true
