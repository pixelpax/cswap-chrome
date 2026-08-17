#!/usr/bin/env bash
# Installs cswap-chrome-watch as a launchd LaunchAgent: when the cswap CLI
# account changes, it opens the account-switch page in Chrome + notifies.
# Idempotent. Optional arg: the URL to open (default: Google account chooser).
set -euo pipefail

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SCRIPT="$DIR/bin/cswap-chrome-watch.py"
URL="${1:-https://accounts.google.com/}"
LABEL="com.cswap.chrome-watch"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/cswap-chrome-watch.log"
PYTHON="$(command -v python3 || echo /usr/bin/python3)"

chmod +x "$SCRIPT"

# Clean up any leftover native-messaging hosts from the old extension-era design.
for d in "$HOME/Library/Application Support/Google/Chrome" \
         "$HOME/Library/Application Support/Google/Chrome Beta" \
         "$HOME/Library/Application Support/Google/Chrome Dev" \
         "$HOME/Library/Application Support/Chromium"; do
  rm -f "$d/NativeMessagingHosts/com.cswap.chrome_host.json"
done

# Seed the last-seen account to the current one so loading the agent doesn't
# fire a prompt immediately (and reboots stay quiet) — it only reacts to changes.
STATE_DIR="$HOME/Library/Application Support/cswap-chrome"
mkdir -p "$STATE_DIR"
"$PYTHON" - "$STATE_DIR/last-account" <<'PY'
import json, os, sys
p = os.path.expanduser("~/.claude.json")
try:
    e = json.load(open(p)).get("oauthAccount", {}).get("emailAddress") or ""
except Exception:
    e = ""
open(sys.argv[1], "w").write(e)
PY

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
sed -e "s|__PYTHON__|$PYTHON|g" \
    -e "s|__SCRIPT__|$SCRIPT|g" \
    -e "s|__URL__|$URL|g" \
    -e "s|__LOG__|$LOG|g" \
    "$DIR/com.cswap.chrome-watch.plist.template" > "$PLIST"

# Reload the agent.
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"

echo "Installed LaunchAgent: $PLIST"
echo "  opens on account change: $URL"
echo "  log: $LOG"
echo
echo "To change the URL later: ./install.sh 'https://your/page' (re-run)."
echo
echo "One-time cleanup of the old design (only if you loaded it before):"
echo "  Remove the unpacked 'cswap-chrome' extension at chrome://extensions."
