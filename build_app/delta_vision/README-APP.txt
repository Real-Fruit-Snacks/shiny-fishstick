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
