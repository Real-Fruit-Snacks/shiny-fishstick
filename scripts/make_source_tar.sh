#!/usr/bin/env bash
set -euo pipefail

# make_source_tar.sh - Create a bog‑standard source tarball of the application directory
# The tarball contains the delta_vision/ project folder exactly as in the repo (no venv, no build artifacts).

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

OUTDIR="release"
NAME="deltavision-${VERSION}-source"
TARBALL="${OUTDIR}/${NAME}.tar.gz"

mkdir -p "${OUTDIR}"

printf '\n==> Building source tarball: %s\n' "${TARBALL}"
# Create tar with the delta_vision/ directory at the root of the archive, excluding common junk
# Note: we use --exclude-vcs-ignores to honor .gitignore where supported; fall back to explicit patterns.
(
  cd .
  tar \
    --exclude-vcs \
    --exclude='.venv' \
    --exclude='**/__pycache__' \
    --exclude='**/*.pyc' \
    --exclude='**/*.pyo' \
    --exclude='**/*.log' \
    --exclude='**/.pytest_cache' \
    --exclude='delta_vision/dist' \
    --exclude='delta_vision/build' \
    -czf "${TARBALL}" delta_vision
)

printf '\nCreated:\n  %s\n' "${TARBALL}"
sha256sum "${TARBALL}" || shasum -a 256 "${TARBALL}" || true
