#!/bin/bash
# One-time setup: download Sparkle framework and generate signing keys.
# Run once per machine before building a signed release.
set -e

SPARKLE_VERSION="2.10.1"
SPARKLE_URL="https://github.com/sparkle-project/Sparkle/releases/download/${SPARKLE_VERSION}/Sparkle-${SPARKLE_VERSION}.tar.xz"
SCRATCH=$(mktemp -d)
DEST="$(dirname "$0")/Sparkle"

echo "⬇️  Downloading Sparkle ${SPARKLE_VERSION}..."
curl -L -o "$SCRATCH/sparkle.tar.xz" "$SPARKLE_URL"

echo "📦 Extracting..."
mkdir -p "$SCRATCH/extracted"
tar -xf "$SCRATCH/sparkle.tar.xz" -C "$SCRATCH/extracted"

rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$SCRATCH/extracted/Sparkle.framework" "$DEST/"
cp -R "$SCRATCH/extracted/bin"               "$DEST/"
rm -rf "$SCRATCH"

echo "✅ Sparkle framework ready at Sparkle/"
echo ""
echo "🔑 Checking for existing signing keys..."
if security find-generic-password -s "ed25519" -a "EZ Logger" &>/dev/null 2>&1; then
    echo "   Keys already exist in Keychain — skipping."
else
    echo "   Generating new Ed25519 key pair..."
    ./Sparkle/bin/generate_keys
    echo ""
    echo "⚠️  Copy the SUPublicEDKey value above into setup.py's plist dict."
fi
echo ""
echo "Done. Run 'bash build.sh --sign' to build a signed release."
