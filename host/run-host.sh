#!/bin/sh
# cswap-chrome native host launcher.
# Chrome launches this with a minimal PATH, so locate a python3 explicitly
# then exec the host script that lives next to this file.
DIR=$(cd "$(dirname "$0")" && pwd)
for PY in "$(command -v python3 2>/dev/null)" /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
  if [ -n "$PY" ] && [ -x "$PY" ]; then
    exec "$PY" "$DIR/cswap_chrome_host.py"
  fi
done
echo "cswap-chrome: python3 not found" >&2
exit 1
