#!/usr/bin/env bash
# Registers the cswap-chrome native messaging host with Chrome (macOS) and
# prints the steps to load the unpacked extension. Idempotent.
set -euo pipefail

DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
HOST_SCRIPT="$DIR/host/run-host.sh"
EXT_ID="jeffcdjdecgpjacfknolgnhkgnanlhdc"
HOST_NAME="com.cswap.chrome_host"

chmod +x "$HOST_SCRIPT" "$DIR/host/cswap_chrome_host.py"

# Register for Chrome (and Chromium / Chrome Beta / Dev if present).
targets=(
  "$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
  "$HOME/Library/Application Support/Google/Chrome Beta/NativeMessagingHosts"
  "$HOME/Library/Application Support/Google/Chrome Dev/NativeMessagingHosts"
  "$HOME/Library/Application Support/Chromium/NativeMessagingHosts"
)

manifest_json() {
  cat <<EOF
{
  "name": "$HOST_NAME",
  "description": "cswap-chrome native host (claude.ai session follower)",
  "path": "$HOST_SCRIPT",
  "type": "stdio",
  "allowed_origins": [ "chrome-extension://$EXT_ID/" ]
}
EOF
}

registered=0
for base in "${targets[@]}"; do
  parent=$(dirname "$base")
  if [ -d "$parent" ]; then
    mkdir -p "$base"
    manifest_json > "$base/$HOST_NAME.json"
    echo "Registered native host: $base/$HOST_NAME.json"
    registered=1
  fi
done

if [ "$registered" -eq 0 ]; then
  echo "No Chrome/Chromium profile dir found. Is Chrome installed for this user?" >&2
fi

cat <<EOF

Next steps:
  1. Open chrome://extensions
  2. Enable "Developer mode" (top-right toggle)
  3. Click "Load unpacked" and select:
       $DIR/extension
  4. Confirm the extension ID shows as:
       $EXT_ID
  5. If the extension was already loaded, click its reload icon so it picks up
     the freshly registered native host.

Then: log into claude.ai in Chrome once per account (with cswap switched to that
account) to teach it. After that, switching cswap moves the browser too.
EOF
