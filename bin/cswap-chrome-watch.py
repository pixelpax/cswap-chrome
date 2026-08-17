#!/usr/bin/env python3
"""cswap-chrome-watch

When the cswap CLI account changes, open the account-switch page in Chrome and
post a macOS notification — so you can re-sign the Claude-in-Chrome extension
into the matching account.

Why it's this modest: Anthropic's Claude-in-Chrome extension holds its OWN
account, established by a full SSO / credential login and decoupled from the
claude.ai web-session cookie. Nothing outside that extension can switch it —
not a cookie swap, not a token swap. So this tool doesn't try. It just NOTICES
the switch (by watching ~/.claude.json) and puts the switch-account page in
front of you. Standard library only; meant to run under a launchd LaunchAgent.
"""

import json
import os
import subprocess
import time

# Page opened on an account change. Anthropic's extension re-auths via Google
# SSO, so this defaults to the Google account chooser. Override via the
# CSWAP_CHROME_URL env var (the installer sets it in the launchd plist).
DEFAULT_URL = "https://accounts.google.com/"
POLL_INTERVAL = 2.0
STATE_FILE = os.path.expanduser("~/Library/Application Support/cswap-chrome/last-account")


def claude_json_path():
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    return os.path.join(cfg, ".claude.json") if cfg else os.path.expanduser("~/.claude.json")


def read_active_email():
    try:
        with open(claude_json_path()) as f:
            d = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None  # missing or mid-write; retry next poll
    oa = d.get("oauthAccount")
    return oa.get("emailAddress") if isinstance(oa, dict) else None


def read_state():
    try:
        with open(STATE_FILE) as f:
            return f.read().strip() or None
    except OSError:
        return None


def write_state(email):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        f.write(email or "")


def chrome_running():
    return subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True).returncode == 0


def notify(title, message):
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    subprocess.run(["osascript", "-e", script], check=False)


def open_switch_page(email):
    url = os.environ.get("CSWAP_CHROME_URL", DEFAULT_URL)
    notify("cswap switched account", f"Now {email}. Switch the Claude extension to match.")
    subprocess.run(["open", "-a", "Google Chrome", url], check=False)


def check_and_maybe_prompt(last):
    """Read the active account; if it changed, prompt (while Chrome is up) and
    return the new last-seen value. Only prompt while Chrome is running, so an
    overnight burst of switches coalesces into one prompt the next time Chrome
    is open, and we never launch Chrome unbidden at 3am."""
    email = read_active_email()
    if email and email != last and chrome_running():
        open_switch_page(email)
        write_state(email)
        return email
    return last


def main():
    last = read_state()
    mtime = 0.0
    while True:
        try:
            m = os.path.getmtime(claude_json_path())
        except OSError:
            m = 0.0
        if m != mtime:
            mtime = m
            last = check_and_maybe_prompt(last)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
