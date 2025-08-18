Delta Vision v0.2.0

Highlights
- Ship only dependency-free artifacts: users can untar and run without installing anything.
- Includes both a PyInstaller standalone bundle and an app-style tar with embedded virtual environment.

Artifacts
1) Standalone (PyInstaller)
   - File: deltavision-0.2.0-Linux.tar.gz
   - Contains: ./deltavision binary and README-RUN.txt

2) App-style untar-and-run (embedded venv)
   - File: deltavision-0.2.0-linux-app.tar.gz
   - Contains: delta_vision/ directory with .venv and run.sh

Checksums
- SHA256 will be printed during local build in scripts/make_release.sh and posted on Release.

Usage
- Standalone: extract and run
    ./deltavision --new /path/to/New --old /path/to/Old --keywords /path/to/keywords.md

- App-style: extract, then
    cd delta_vision
    ./run.sh --new /path/to/New --old /path/to/Old --keywords /path/to/keywords.md

Remote
- Server: use either artifact
    --server --port 8765
- Client: connect
    --client --host 1.2.3.4 --port 8765

Notes
- Developer artifacts (wheel/sdist/source) are intentionally not published in this release.
