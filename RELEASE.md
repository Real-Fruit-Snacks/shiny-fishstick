# Release process

1) Update version

- Edit `delta_vision/src/delta_vision/__about__.py` and bump `__version__` to `X.Y.Z`.
- Update `CHANGELOG.md` with the new section.

2) Tag a release

```bash
git commit -am "chore: release vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

3) CI will build and publish

- GitHub Actions builds source/wheel and PyInstaller binaries for Linux/macOS/Windows.
- A GitHub Release is created with artifacts attached.

Optional: Publish to PyPI (manual until configured)

```bash
python -m pip install -U twine build
python -m build -s -w delta_vision
twine upload delta_vision/dist/*
```
