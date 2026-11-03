#!/bin/bash
set -e

PYTHON=/opt/homebrew/bin/python3.11

echo ""
echo "🏀 EZ Logger — App Builder"
echo "====================================="
echo ""

# ── Check Python ──────────────────────────────────────────────────
if ! command -v $PYTHON &>/dev/null; then
    echo "❌ Homebrew Python 3.11 not found at $PYTHON"
    echo "   Install with: brew install python@3.11"
    exit 1
fi

echo "✅ Found: $($PYTHON --version)"
echo ""

# ── Install packages ──────────────────────────────────────────────
echo "📦 Installing required packages..."
$PYTHON -m pip install --quiet rumps pyobjc py2app
echo "✅ Packages installed."
echo ""

# ── Clean previous build ──────────────────────────────────────────
echo "🧹 Cleaning previous build..."
rm -rf build dist
echo ""

# ── Build the .app ────────────────────────────────────────────────
echo "🔨 Building EZ Logger.app..."
echo "   (This takes 1-3 minutes)"
echo ""
$PYTHON setup.py py2app 2>&1 | grep -v "^$" | tail -20

echo ""

# ── Check result ──────────────────────────────────────────────────
APP_PATH="dist/EZ Logger.app"
if [ -d "$APP_PATH" ]; then
    echo "✅ Build successful!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Drag 'EZ Logger.app' from the dist/"
    echo "  folder into your /Applications folder."
    echo "  Then launch from Spotlight. 🏀 appears in menubar."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    open dist/
else
    echo "❌ Build failed. Check the output above for errors."
fi
