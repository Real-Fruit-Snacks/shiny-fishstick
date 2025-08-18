# Delta Vision v0.1.3

Highlights
- Untar-and-run app bundle (embedded .venv) – no external installs.
- CLI flags (--port/--host) now take precedence over env.
- Keywords screen scanning stability: throttled and conditional rescans to reduce flicker.

Artifacts
- App bundle (untar and run): deltavision-0.1.3-linux-app.tar.gz
  - sha256: 5f1ba41f18dc19373cdcd51c5d158545cc436a8fea095b26b497485d331cf903
- Standalone (PyInstaller): deltavision-0.1.3-Linux.tar.gz
  - sha256: 11f7fb7c117c3b52de21e9803ef629fa40a2a30fe46061747941fd3af8c422d2
- Source (bog standard tree): deltavision-0.1.3-source.tar.gz
  - sha256: d451daba6e5bd247bddb8b1873978898e47b0fc52572bd57fe22bb3d1a28a845
- Python packages: wheel/sdist in delta_vision/dist/

Try it
```bash
# 1) Untar-and-run app bundle (no installs needed)
tar -xzf deltavision-0.1.3-linux-app.tar.gz
cd delta_vision
./run.sh                    # local mode
./run.sh --server --host 0.0.0.0 --port 8000
./run.sh --client --host <server-ip> --port 8000

# 2) PyInstaller bundle
# Extract and run the 'deltavision' binary inside.
```

Notes
- To use textual run, pass flags after --, or use env: DELTA_MODE, DELTA_HOST, DELTA_PORT.
- Server spawns per-client PTY-backed sessions; Ctrl+C/D behave as expected; resize is synced.
- If you hit issues, open an issue with the exact artifact name and your OS info.
