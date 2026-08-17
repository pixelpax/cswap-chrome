#!/usr/bin/env bash
# Removes the cswap-chrome-watch LaunchAgent and its saved state.
set -euo pipefail

LABEL="com.cswap.chrome-watch"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
rm -f "$HOME/Library/Application Support/cswap-chrome/last-account"

echo "Removed LaunchAgent and state."
echo "If you ever loaded the old unpacked extension, remove it at chrome://extensions."
