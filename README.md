# Delta Vision — fast, keyboard‑friendly file comparison TUI

Delta Vision is a Textual‑powered terminal UI for comparing folders, reviewing diffs, searching, and triaging with keyword highlights and a notes drawer. It runs locally, or as a remote multi‑user server with a simple client.

Works on Linux, macOS, and Windows.


## Install and run

Install from PyPI (recommended):

```bash
pipx install deltavision    # or: pip install deltavision
```

Run locally:

```bash
deltavision --new /path/to/New --old /path/to/Old --keywords /path/to/keywords.md
```

No extras required — networking support is included by default.


## Remote multi‑user (server/client)

Start a server (spawns one PTY/Textual session per client):

```bash
python -m delta_vision --server --port 8765 \
    --new /path/to/New \
    --old /path/to/Old \
    --keywords /path/to/keywords.md
```

Connect from a client terminal:

```bash
python -m delta_vision --client --host 1.2.3.4 --port 8765
```

Environment variables (optional): `DELTA_NEW`, `DELTA_OLD`, `DELTA_KEYWORDS`, `DELTA_NOTES`, `DELTA_MODE`, `DELTA_HOST`, `DELTA_PORT`.


## Features

- Compare two folders (New vs Old), diff viewer with tabs
- Stream view for newest changes, search across files
- Keyword highlighting from a Markdown file
- Notes drawer (Ctrl+N), bundled themes (default ayu‑mirage)


## Build a standalone binary (optional)

You can ship a single self‑contained binary (no Python required):

```bash
pip install pyinstaller
pyinstaller -y delta_vision/packaging/deltavision.spec
```

The binary will be in `dist/deltavision`.


## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e delta_vision
pip install -U pytest ruff
pytest -q
```


## License

MIT — see `delta_vision/LICENSE.txt`.
