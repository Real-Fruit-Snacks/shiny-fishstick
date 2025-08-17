#!/usr/bin/env bash
set -euo pipefail

# make_release.sh - Build local release artifacts without CI
# Produces:
# - delta_vision/dist/*.whl and *.tar.gz (sdist, wheel)
# - release/deltavision-<version>-Linux.tar.gz (standalone bundle)

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

# Ensure venv if desired
if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

printf '\n==> Building sdist and wheel...\n'
python -m pip install -U pip build >/dev/null
python -m build -s -w delta_vision

# Build standalone bundle (Linux)
printf '\n==> Building standalone bundle (PyInstaller)...\n'
pip install -U pyinstaller ./delta_vision >/dev/null
pyinstaller -y delta_vision/packaging/deltavision.spec >/dev/null

# Add quick start README
cat > dist/README-RUN.txt <<'TXT'
Delta Vision - standalone bundle

Usage:
  ./deltavision --new /path/to/New --old /path/to/Old \
    --keywords /path/to/keywords.md

Notes:
  - No additional dependencies required.
  - Server: ./deltavision --server --port 8765 ...
  - Client: ./deltavision --client --host 1.2.3.4 --port 8765
TXT

# Package tarball
mkdir -p release
TARBALL="release/deltavision-${VERSION}-Linux.tar.gz"
(
  cd dist
  tar -czf "../${TARBALL}" deltavision README-RUN.txt
)

printf '\nArtifacts:\n'
ls -1 delta_vision/dist/* | sed 's/^/  /'
ls -1 release/* | sed 's/^/  /'

printf '\nDone.\n'
