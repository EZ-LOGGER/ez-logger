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
    echo "🔏 Signing all binaries inside the app..."
    # 1. Individual binaries (including Sparkle's Autoupdate plain binary)
    find "$APP_PATH" -type f \( -name "*.so" -o -name "*.dylib" -o -name "python*" -o -name "Python" -o -name "Autoupdate" \) | while read -r bin; do
        codesign --force --options runtime \
          --sign "$SIGN_ID" \
          --timestamp \
          "$bin" 2>/dev/null || true
    done
    # 2. XPC service bundles inside Sparkle (must be signed before the framework)
    find "$APP_PATH" -name "*.xpc" -type d | while read -r xpc; do
        codesign --force --options runtime \
          --sign "$SIGN_ID" \
          --timestamp \
          "$xpc" 2>/dev/null || true
    done
    # 3. Helper app bundles inside Sparkle (Autoupdate.app etc.)
    find "$APP_PATH" -path "*/Sparkle.framework/*" -name "*.app" -type d | while read -r helper; do
        codesign --force --options runtime \
          --sign "$SIGN_ID" \
          --timestamp \
          "$helper" 2>/dev/null || true
    done
    # 4. Framework bundles
    find "$APP_PATH" -name "*.framework" -type d | while read -r fw; do
        codesign --force --options runtime \
          --sign "$SIGN_ID" \
          --timestamp \
          "$fw" 2>/dev/null || true
    done
    # 5. Main executable and app bundle last
    codesign --force --options runtime \
      --sign "$SIGN_ID" \
      --timestamp \
      "$APP_PATH/Contents/MacOS/EZ Logger"
    codesign --force --options runtime \
      --sign "$SIGN_ID" \
      --timestamp \
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

    echo "💿 Creating .dmg..."
    APP_VERSION=$($PYTHON -c "import re; m=re.search(r'APP_VERSION\s*=\s*\"([^\"]+)\"', open('renamer.py').read()); print(m.group(1))")
    DMG_PATH="dist/EZLogger-${APP_VERSION}.dmg"
    rm -f "$DMG_PATH"
    create-dmg \
      --volname "EZ Logger" \
      --window-pos 200 120 \
      --window-size 600 400 \
      --icon-size 100 \
      --icon "EZ Logger.app" 175 190 \
      --hide-extension "EZ Logger.app" \
      --app-drop-link 425 190 \
      "$DMG_PATH" \
      "$APP_PATH"
    echo "✅ DMG created: $DMG_PATH"
    echo ""

    echo "📋 Generating appcast.xml..."
    ./Sparkle/bin/generate_appcast \
      --download-url-prefix "https://github.com/EZ-LOGGER/ez-logger/releases/download/v${APP_VERSION}/" \
      -o appcast.xml \
      dist/
    echo "✅ appcast.xml updated."
    echo ""

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  ✅ Signed, notarized, and ready to distribute."
    echo ""
    echo "  Next steps:"
    echo "  1. git add appcast.xml && git commit -m 'Release v${APP_VERSION}' && git push"
    echo "  2. gh release create v${APP_VERSION} '${DMG_PATH}' --title 'EZ Logger v${APP_VERSION}'"
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
