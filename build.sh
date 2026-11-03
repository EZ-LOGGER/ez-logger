#!/bin/bash
set -e

PYTHON=/opt/homebrew/bin/python3.11
APP_PATH="dist/EZ Logger.app"
ZIP_PATH="dist/EZLogger.zip"
SIGN_ID="Developer ID Application: Zachary Keding (3XQ36X2RC9)"
KEYCHAIN_PROFILE="ez-logger-notarize"

# Parse flags
SIGN=false
for arg in "$@"; do
  case $arg in
    --sign) SIGN=true ;;
  esac
done

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

if [ ! -d "$APP_PATH" ]; then
    echo "❌ Build failed. Check the output above for errors."
    exit 1
fi

echo "✅ Build successful!"
echo ""

# ── Sign + Notarize (only with --sign flag) ───────────────────────
if [ "$SIGN" = true ]; then
    echo "🔏 Signing the app..."
    codesign --deep --force --options runtime \
      --sign "$SIGN_ID" \
      "$APP_PATH"
    echo "✅ Signed."
    echo ""

    echo "📦 Zipping for notarization..."
    ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
    echo "✅ Zipped."
    echo ""

    echo "📤 Submitting to Apple for notarization..."
    echo "   (This takes 1-5 minutes)"
    xcrun notarytool submit "$ZIP_PATH" \
      --keychain-profile "$KEYCHAIN_PROFILE" \
      --wait
    echo ""

    echo "📎 Stapling notarization ticket..."
    xcrun stapler staple "$APP_PATH"
    echo "✅ Stapled."
    echo ""

    rm -f "$ZIP_PATH"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Signed, notarized, and ready to distribute."
    echo "  Drag 'EZ Logger.app' from dist/ to share."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Drag 'EZ Logger.app' from the dist/"
    echo "  folder into your /Applications folder."
    echo "  Then launch from Spotlight. 🏀 appears in menubar."
    echo ""
    echo "  To build a signed distributable version:"
    echo "  bash build.sh --sign"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
fi

echo ""
open dist/
