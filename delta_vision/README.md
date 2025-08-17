# My Textual App

A professional Textual-based Python application.

## Install and run

Install from PyPI or source; all dependencies are bundled in the package (Textual, watchdog, websockets), so a single install is enough:

```bash
pip install deltavision
```

Run the CLI:

```bash
deltavision --new /path/to/New --old /path/to/Old --keywords /path/to/keywords.md
```

For an all-in-one binary (no Python needed), you can build with PyInstaller:

```bash
pip install pyinstaller
pyinstaller -y delta_vision/packaging/deltavision.spec
# Output in dist/deltavision/
```

## Remote server/client

Run as a server that accepts multiple remote clients (a new PTY/Textual session per client):

```bash
python -m delta_vision --server --port 8765
```

Connect as a client:

```bash
python -m delta_vision --client --host 127.0.0.1 --port 8765
```

If neither flag is specified, the app runs locally as a normal TUI.

## Keywords file format

Provide a markdown file (e.g. `keywords.md`) to power highlighting and the Keywords screen.

Rules:
- Category headers start with `#`, e.g. `# Security (Red)` or `# Networking`.
- The color in parentheses is optional; when omitted, a default theme color is used.
- Lines starting with `#` that do not match a header (e.g. `# comment ...`) are treated as comments.
- Empty categories are allowed and retained.
- Inline comments after a keyword are stripped when preceded by whitespace: `foo  # note` -> `foo`.

Example:

```
# Security (Red)
malware
phishing  # social engineering

# Networking
TCP
UDP
```
