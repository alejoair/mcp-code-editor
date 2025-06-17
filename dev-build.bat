@echo off
REM Development and testing script for mcp-code-editor (Windows)

echo === MCP Code Editor - Development Script ===

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade build tools
echo Installing build tools...
pip install --upgrade pip setuptools wheel twine build

REM Install development dependencies
echo Installing development dependencies...
pip install -r requirements.txt

REM Clean previous builds
echo Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist
for /d %%i in (*.egg-info) do rmdir /s /q "%%i"

REM Build the package
echo Building package...
python -m build

REM Check the built package
echo Checking package...
twine check dist/*

echo.
echo === Build complete! ===
echo Files created in dist/:
dir dist\

echo.
echo To upload to PyPI:
echo 1. Test PyPI: twine upload --repository testpypi dist/*
echo 2. Real PyPI: twine upload dist/*

pause
