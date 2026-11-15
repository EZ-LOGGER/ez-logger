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
    # A failed signature here gets the whole build rejected by Apple, so retry
    # once (the timestamp server can hiccup) and stop with the error if it still fails.
    SIGN_FAILS=0
    while read -r bin; do
        if ! codesign --force --options runtime --sign "$SIGN_ID" --timestamp "$bin" 2>/tmp/ezl_sign_err; then
            sleep 2
            if ! codesign --force --options runtime --sign "$SIGN_ID" --timestamp "$bin" 2>/tmp/ezl_sign_err; then
                echo "❌ Could not sign: ${bin#$APP_PATH/}"
                sed 's/^/     /' /tmp/ezl_sign_err | head -3
                SIGN_FAILS=$((SIGN_FAILS + 1))
            fi
        fi
    done < <(find "$APP_PATH" -type f \( -name "*.so" -o -name "*.dylib" -o -name "python*" -o -name "Python" -o -name "Autoupdate" \))
    if [ "$SIGN_FAILS" -gt 0 ]; then
        echo "❌ $SIGN_FAILS binaries could not be signed. Not submitting to Apple."
        exit 1
    fi
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
    # Every binary must carry the Developer ID signature, or notarization fails
    UNSIGNED=$(find "$APP_PATH" -type f \( -name "*.so" -o -name "*.dylib" \) -exec sh -c \
      'codesign -dvv "$1" 2>&1 | grep -q "Authority=Developer ID Application" || echo "$1"' _ {} \; | head -5)
    if [ -n "$UNSIGNED" ]; then
        echo "❌ Some binaries are not Developer ID signed:"
        echo "$UNSIGNED" | sed 's/^/     /'
        exit 1
    fi
    echo "✅ Signed."
    echo ""

    echo "📦 Zipping for notarization..."
    ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"
    echo "✅ Zipped."
    echo ""

    echo "📤 Submitting to Apple for notarization..."
    echo "   (This takes 1-5 minutes)"
    NOTARY_OUT=$(xcrun notarytool submit "$ZIP_PATH" \
      --keychain-profile "$KEYCHAIN_PROFILE" \
      --wait 2>&1) || true
    echo "$NOTARY_OUT" | tail -4
    if ! echo "$NOTARY_OUT" | grep -q "status: Accepted"; then
        echo "❌ Apple did not accept the app. See why with:"
        echo "   xcrun notarytool log <submission id> --keychain-profile $KEYCHAIN_PROFILE"
        exit 1
    fi
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
