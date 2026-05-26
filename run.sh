#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# LectureLens — Linux / macOS launcher
# Author : Shivam Aggarwal  |  github.com/aggarwal-shiv
# ─────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python)"

if [ -z "$PY" ]; then
    echo "❌  Python 3 not found. Please install Python 3.9+ from https://python.org"
    exit 1
fi

VER=$("$PY" -c "import sys; print(sys.version_info[:2])")
echo "🔍 LectureLens — using Python at: $PY  ($VER)"

# Check tkinter
if ! "$PY" -c "import tkinter" 2>/dev/null; then
    echo ""
    echo "⚠  tkinter not found. Install it with:"
    echo "   Ubuntu/Debian : sudo apt install python3-tk"
    echo "   Fedora        : sudo dnf install python3-tkinter"
    echo "   macOS         : brew install python-tk"
    echo ""
fi

# First-run: install deps if any are missing
if ! "$PY" -c "import cv2, PIL, numpy" 2>/dev/null; then
    echo ""
    echo "📦  First run detected — installing dependencies…"
    "$PY" "$SCRIPT_DIR/LectureLens.py" --install
    echo ""
fi

# Launch
"$PY" "$SCRIPT_DIR/LectureLens.py" "$@"
