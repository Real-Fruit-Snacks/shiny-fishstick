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
