#!/bin/sh
# Builds the shortcut and signs it so iOS accepts it. Run on a Mac signed into iCloud.
# The file name becomes the shortcut's name in the Shortcuts app.
set -eu

cd "$(dirname "$0")/.."
NAME="X Video Downloader"

PYTHONPATH=src python3 -m xvideo_shortcut -o "dist/$NAME.unsigned.shortcut"
shortcuts sign --mode anyone \
  --input "dist/$NAME.unsigned.shortcut" \
  --output "dist/$NAME.shortcut"

echo "Signed: dist/$NAME.shortcut"
echo "Open it on the Mac, or AirDrop it to the iPhone."
