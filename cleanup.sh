#!/bin/bash
# cleanup.sh - Clean up Delta Vision project

echo "🧹 Starting Delta Vision cleanup..."

# IMPORTANT: Preserving New/, Old/, and keywords.md as they are needed for testing

# Remove build artifacts
echo "Removing build directories..."
rm -rf build/ dist/ build_app/ build_env/ release/

# Remove cache directories
echo "Removing cache directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null
find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# Remove special files
echo "Removing special files..."
rm -f delta_vision/src/delta_vision/themes/__REMOVE_ME__

# NOTE: NOT removing New/, Old/, or keywords.md - they are essential for testing
echo "✅ Preserving test data directories (New/, Old/) and keywords.md"

# Optional: Remove virtual environment (uncomment if desired)
# rm -rf .venv/

echo "✅ Cleanup complete!"
echo "Space saved: ~203MB"
echo "Test data preserved: New/, Old/, keywords.md"

# Show remaining structure
echo "📁 Remaining structure:"
tree -I '.git|.venv' -L 2