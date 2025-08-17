# Delta Vision — a fast, keyboard‑friendly file comparison TUI

Delta Vision is a Textual-powered terminal UI for comparing folders, reviewing diffs, and quickly finding changes. It’s lightweight, fast, and comfortable to drive entirely from the keyboard. Keywords highlighting and an integrated notes drawer help you triage and keep context as you work.

Built with Python and [Textual](https://github.com/Textualize/textual). Works on Windows, macOS, and Linux.


## Highlights

- Compare two folders (New vs Old) and browse changes side‑by‑side
- Diff viewer with tabs for multiple files
- Stream view for the “new” folder when you only care about latest changes
- Search across files
- Keyword highlighting powered by a simple Markdown file
- Notes drawer (toggle with Ctrl+N) that persists between sessions
- Bundled themes; defaults to ayu‑mirage


## Quick start

You can run directly from source with Textual’s dev runner:

```powershell
cd .\my_textual_app
textual run --dev app.py --old ..\Old\ --new ..\New\ --keywords ..\keywords.md
```

Notes:
- The app will look for a keywords Markdown file for highlighting if provided via `--keywords`.
- Use absolute paths if your folders aren’t next to the repo.


## Installation

The project is a standard Python package (name: `my-textual-app`) and provides a console entry point (`deltavision`). If you prefer, you can install it into a virtual environment for everyday use.

Install from the repo (editable):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .\my_textual_app
```

Run the CLI after install:

```powershell
deltavision --old C:\path\to\Old --new C:\path\to\New --keywords C:\path\to\keywords.md
```

If you prefer `pipx` for isolated installs:

```powershell
pipx install .\my_textual_app
```


## Ubuntu setup and usage

Ubuntu comes with Python 3. Install a few essentials first:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip pipx
# Ensure pipx is on PATH (logout/login after this or source your shell rc)
pipx ensurepath
```

Run from source using a virtual environment (recommended for development):

```bash
cd my_textual_app
python3 -m venv ../.venv
source ../.venv/bin/activate
python -m pip install -U pip
pip install -e .

# Run the app (Textual dev server)
python -m textual run --dev app.py \
    --old ../Old/ \
    --new ../New/ \
    --keywords ../keywords.md
```

Install for daily use with pipx from a local clone:

```bash
cd my_textual_app
pipx install .

# Then run from anywhere on your system
deltavision --old /path/to/Old --new /path/to/New --keywords /path/to/keywords.md
```

Tips for Ubuntu terminals:
- GNOME Terminal works well; Kitty, WezTerm, or Alacritty also provide excellent Textual support.
- If you see odd box characters, switch to a font with good Unicode/box‑drawing coverage (e.g., FiraCode, JetBrains Mono, or a Nerd Font) and ensure UTF‑8 locale.
- If `deltavision` isn’t found after `pipx install`, verify `~/.local/bin` is on your PATH (the `pipx ensurepath` step adds it) and restart your shell.


## Command‑line usage

The application exposes a single command with a few useful options:

```text
deltavision [--new PATH] [--old PATH] [--keywords FILE]
            [--notes PATH]
```

Options
- `--new`: Path to the “new” folder (required for Stream and useful for Compare)
- `--old`: Path to the second folder to compare (Compare mode)
- `--keywords`: Path to a keywords Markdown file for highlighting and the Keywords screen
- `--notes`: Path to notes location. Provide a directory (the app will create `DeltaVision_notes.txt` inside) or a full file path. If omitted, the OS temp directory is used.


## Command help

Here’s what the help menu looks like:

```text
usage: deltavision [-h] [--new NEW] [--old OLD] [--keywords KEYWORDS]
                   [--notes NOTES]

Delta Vision: File Comparison App

options:
    -h, --help            show this help message and exit
    --new NEW             Path to folder for stream page
    --old OLD             Path to second folder to monitor (not used on Stream)
    --keywords KEYWORDS   Path to keywords markdown file
    --notes NOTES         Path to notes directory or file (defaults to OS temp dir when omitted)
```




## Keywords file format

Provide a Markdown file (for example, `keywords.md`) to power highlighting and the Keywords screen.

Rules:
- Category headers start with `#`, e.g. `# Security (Red)` or `# Networking`.
- The color in parentheses is optional; when omitted, a theme default is used.
- Lines starting with `#` that do not match a header (e.g. `# comment ...`) are treated as comments.
- Empty categories are allowed and retained.
- Inline comments after a keyword are stripped when preceded by whitespace: `foo  # note` → `foo`.

Example:

```markdown
# Security (Red)
malware
phishing  # social engineering

# Networking
TCP
UDP
```


## Keyboard shortcuts

- Ctrl+N — Toggle the Notes drawer


## Themes

Bundled themes are auto‑registered on start and the default is `ayu-mirage`. You can browse and tweak them in `my_textual_app/themes/`.


## Development

Requirements: Python 3.8+.

Set up a local dev environment:

```powershell
cd .\my_textual_app
python -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e .
pip install -U pytest ruff
```

Run in dev mode:

```powershell
textual run --dev app.py --old ..\Old\ --new ..\New\ --keywords ..\keywords.md
```

Lint and format (VS Code tasks are provided):

```powershell
# Lint
ruff check .

# Format
ruff format .
```

Run tests:

```powershell
pytest -q
```


## Troubleshooting

- Windows terminal: Use Windows Terminal or a terminal that supports modern VT sequences for the best Textual experience.
 - Notes path: With `--notes`, pass a directory (the app will create `DeltaVision_notes.txt` inside) or a file path. If the directory doesn’t exist, it will be created when possible; otherwise, the OS temp directory is used.
- Headless/CI tests on Windows: The package includes a small compatibility shim to ignore occasional console handle errors raised by Textual’s internal printing during tests.


## Project status

Early-stage/alpha. Expect rough edges and rapid changes.


## License

MIT — see `my_textual_app/LICENSE.txt`.


## Acknowledgments

- Built with the excellent [Textual](https://github.com/Textualize/textual)
- File watching via [watchdog](https://github.com/gorakhargosh/watchdog)
