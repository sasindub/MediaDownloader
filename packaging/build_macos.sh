#!/usr/bin/env bash
# Build Media Downloader.app and wrap it in a DMG.
# Produces an app for the architecture of the machine it runs on.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
ARCH="$(uname -m)"
APP="dist/Media Downloader.app"
DMG="dist/MediaDownloader-macOS-${ARCH}.dmg"
STAGE="dist/dmg"

echo "==> Fetching ffmpeg"
"$PYTHON" packaging/fetch_ffmpeg.py

echo "==> Fetching yt-dlp"
"$PYTHON" packaging/fetch_ytdlp.py

echo "==> Building app"
rm -rf build dist
"$PYTHON" -m PyInstaller --noconfirm --clean packaging/MediaDownloader.spec

echo "==> Ad hoc signing"
# Apple Silicon refuses to launch an unsigned binary outright, with a
# misleading "app is damaged" error. An ad hoc signature is free and
# fixes that. It is not notarisation, so Gatekeeper still warns once.
codesign --force --deep --sign - "$APP"
codesign --verify --verbose=2 "$APP" 2>&1 | sed 's/^/    /'

echo "==> Building DMG"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
cp packaging/READ-ME-FIRST.txt "$STAGE/READ ME FIRST.txt"
ln -s /Applications "$STAGE/Applications"

hdiutil create -volname "Media Downloader" -srcfolder "$STAGE" \
    -ov -format UDZO "$DMG" >/dev/null

rm -rf "$STAGE"
echo
echo "==> Done"
ls -lh "$DMG" | awk '{print "    " $9 "  " $5}'
