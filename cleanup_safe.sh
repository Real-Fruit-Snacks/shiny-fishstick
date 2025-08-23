#!/bin/bash
# cleanup_safe.sh - SAFER Clean up Delta Vision project
# This version preserves build_app/ which contains unique source code

echo "🧹 Starting SAFE Delta Vision cleanup..."
echo "⚠️  PRESERVING build_app/ - contains unique source code (notes_drawer.py)"

# IMPORTANT: Preserving New/, Old/, and keywords.md as they are needed for testing
# ALSO PRESERVING: build_app/ (contains different source code)

# Remove CONFIRMED SAFE build artifacts
echo "Removing confirmed safe build directories..."
rm -rf build/ dist/

# ASK before removing these (not in .gitignore)
echo ""
echo "⚠️  The following directories are NOT in .gitignore:"
echo "   - build_env/ ($(du -sh build_env/ 2>/dev/null | cut -f1) or not found)"
echo "   - release/ ($(du -sh release/ 2>/dev/null | cut -f1) or not found)"
echo ""
read -p "Remove build_env/ and release/? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Removing build_env/ and release/..."
    rm -rf build_env/ release/
else
    echo "Keeping build_env/ and release/"
fi

# Remove cache directories (always safe)
echo "Removing cache directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# Remove special files
echo "Removing special files..."
rm -f delta_vision/src/delta_vision/themes/__REMOVE_ME__

# Summary
echo ""
echo "✅ Safe cleanup complete!"
echo "✅ Preserved: New/, Old/, keywords.md, build_app/"
echo "🗑️  Removed: build/, dist/, cache directories"

# Show what's left
echo ""
echo "📁 Remaining structure:"
tree -I '.git|.venv' -L 2 2>/dev/null || echo "tree command not available"