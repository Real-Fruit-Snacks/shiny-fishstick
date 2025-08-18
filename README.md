# Delta Vision — fast, keyboard‑friendly file comparison TUI

Delta Vision is a Textual‑powered terminal UI for comparing folders, reviewing diffs, searching, and triaging with keyword highlights and a notes drawer. It runs locally, or as a remote multi‑user server with a simple client.

Works on Linux, macOS, and Windows.


## Download and run (no external dependencies)

Grab one of the release artifacts (Linux):

- Standalone (PyInstaller): `deltavision-<version>-Linux.tar.gz`
    - Extract and run the `deltavision` binary.
- App-style untar-and-run (embedded venv): `deltavision-<version>-linux-app.tar.gz`
    - Extract, `cd delta_vision`, and run `./run.sh`.

Examples:

```bash
# Standalone bundle
tar -xzf deltavision-<version>-Linux.tar.gz
./deltavision --new /path/to/New --old /path/to/Old --keywords /path/to/keywords.md

# App-style bundle
tar -xzf deltavision-<version>-linux-app.tar.gz
cd delta_vision
./run.sh --new /path/to/New --old /path/to/Old --keywords /path/to/keywords.md
```


## Remote multi‑user (server/client)

Start a server (spawns one PTY/Textual session per client):

```bash
# Standalone bundle
./deltavision --server --port 8765 \
    --new /path/to/New \
    --old /path/to/Old \
    --keywords /path/to/keywords.md

# App-style bundle
./run.sh --server --port 8765 \
    --new /path/to/New \
    --old /path/to/Old \
    --keywords /path/to/keywords.md
```

Connect from a client terminal:

```bash
# Standalone
./deltavision --client --host 1.2.3.4 --port 8765

# App-style
./run.sh --client --host 1.2.3.4 --port 8765
```

Environment variables (optional): `DELTA_NEW`, `DELTA_OLD`, `DELTA_KEYWORDS`, `DELTA_NOTES`, `DELTA_MODE`, `DELTA_HOST`, `DELTA_PORT`.


## Features

- Compare two folders (New vs Old), diff viewer with tabs
- Stream view for newest changes, search across files
- Keyword highlighting from a Markdown file
- Notes drawer (Ctrl+N), bundled themes (default ayu‑mirage)


## Local developer install (optional)

If you prefer a dev install from source:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e delta_vision
```

Run:

```bash
python -m delta_vision --new /path/to/New --old /path/to/Old --keywords /path/to/keywords.md
```


## Build a local release (maintainers)

Build dependency‑free artifacts locally and compute checksums:

```bash
bash scripts/make_release.sh
```

This produces:

- `release/deltavision-<version>-Linux.tar.gz`
- `release/deltavision-<version>-linux-app.tar.gz`


## License

MIT — see `delta_vision/LICENSE.txt`.
