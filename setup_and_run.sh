#!/bin/bash
# Setup script: creates a virtual environment, installs dependencies, and runs the app
# Usage: bash setup_and_run.sh

set -e

VENV_DIR="venv"

# Remove old venv if it exists to start fresh
if [ -d "$VENV_DIR" ]; then
    echo "=== Removing old virtual environment ==="
    rm -rf "$VENV_DIR"
fi

echo "=== Creating virtual environment ==="
python3 -m venv "$VENV_DIR"

echo "=== Activating virtual environment ==="
source "$VENV_DIR/bin/activate"

echo "=== Upgrading pip and core packages ==="
pip install --upgrade pip setuptools wheel typing_extensions

echo "=== Installing dependencies ==="
pip install -r requirements.txt

echo ""
echo "=== Starting the app ==="
echo "Open http://127.0.0.1:8050 in your browser"
echo ""
python app.py
