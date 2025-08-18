#!/usr/bin/env bash
set -euo pipefail

# Trigger the GitHub Actions release workflow for a given tag (defaults to latest tag)

TAG="${1:-}"
if [[ -z "$TAG" ]]; then
  TAG=$(git describe --tags --abbrev=0)
fi

echo "Triggering release workflow for tag: $TAG"

gh workflow run release.yml -f tag="$TAG"

echo "Done. Check Actions tab for progress."
