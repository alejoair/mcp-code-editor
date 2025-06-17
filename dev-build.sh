#!/bin/bash
# Development and testing script for mcp-code-editor

set -e

echo "=== MCP Code Editor - Development Script ==="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate

# Install/upgrade build tools
echo "Installing build tools..."
pip install --upgrade pip setuptools wheel twine build

# Install development dependencies
echo "Installing development dependencies..."
pip install -r requirements.txt

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info/

# Build the package
echo "Building package..."
python -m build

# Check the built package
echo "Checking package..."
twine check dist/*

echo ""
echo "=== Build complete! ==="
echo "Files created in dist/:"
ls -la dist/

echo ""
echo "To upload to PyPI:"
echo "1. Test PyPI: twine upload --repository testpypi dist/*"
echo "2. Real PyPI: twine upload dist/*"
