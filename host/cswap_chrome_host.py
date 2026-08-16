#!/usr/bin/env python3
"""cswap-chrome native messaging host.

Watches ~/.claude.json for the active Claude account (oauthAccount.emailAddress)
and drives the companion Chrome extension so the browser's claude.ai session
follows whichever account the cswap CLI is currently switched to.

Per-account claude.ai cookie sets are vaulted in the macOS login Keychain
(service "cswap-chrome", account = the account's email). Nothing sensitive is
written to disk. Standard library only — no pip dependencies.

Protocol (JSON over Chrome native messaging framing):
  extension -> host:
    {"type": "hello"}                      first message on connect
    {"type": "capture", "cookies": [...]}  current claude.ai cookie set
  host -> extension:
    {"type": "switch", "email", "cookies"} apply this stashed set
    {"type": "need_login", "email"}        no stash yet; ask user to log in once
    {"type": "logged_out"}                 CLI has no active account
    {"type": "captured", "email"}          ack of a successful vault
"""

import base64
import json
import os
import struct
import subprocess
import sys
import threading
import time
import traceback

KEYCHAIN_SERVICE = "cswap-chrome"
SESSION_COOKIE = "sessionKey"
POLL_INTERVAL = 1.5

_write_lock = threading.Lock()

# Baseline for the watcher; established in main() before the thread starts so
# that the initial sync is driven by the extension's "hello", not the watcher.
_last_email = [None]
_last_mtime = [0.0]


def log(*a):
    print("[cswap-chrome-host]", *a, file=sys.stderr, flush=True)


def claude_json_path():
    cfg = os.environ.get("CLAUDE_CONFIG_DIR")
    if cfg:
        return os.path.join(cfg, ".claude.json")
    return os.path.expanduser("~/.claude.json")


# ---- native messaging framing ------------------------------------------------

def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) < 4:
        return None  # EOF: Chrome closed the port
    (length,) = struct.unpack("<I", raw_len)
    data = sys.stdin.buffer.read(length)
    if len(data) < length:
        return None
    return json.loads(data.decode("utf-8"))


def send_message(obj):
    data = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    with _write_lock:
        sys.stdout.buffer.write(struct.pack("<I", len(data)))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()


# ---- macOS Keychain vault (via the `security` CLI, no deps) -------------------

def keychain_get(email):
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", email, "-w"],
            capture_output=True, text=True,
        )
    except Exception as e:
        log("keychain get error:", e)
        return None
    if r.returncode != 0:
        return None  # not found
    b64 = r.stdout.strip()
    if not b64:
        return None
    try:
        return json.loads(base64.b64decode(b64).decode("utf-8"))
    except Exception as e:
        log("keychain decode error:", e)
        return None


def keychain_set(email, cookies):
    b64 = base64.b64encode(json.dumps(cookies).encode("utf-8")).decode("ascii")
    try:
        r = subprocess.run(
            ["security", "add-generic-password", "-U",
             "-s", KEYCHAIN_SERVICE, "-a", email, "-w", b64],
            capture_output=True, text=True,
        )
    except Exception as e:
        log("keychain set error:", e)
        return False
    if r.returncode != 0:
        log("keychain set failed:", r.stderr.strip())
        return False
    return True


def session_value(cookies):
    for c in cookies or []:
        if c.get("name") == SESSION_COOKIE:
            return c.get("value")
    return None


# ---- active account ----------------------------------------------------------

def read_active_email():
    p = claude_json_path()
    try:
        with open(p, "r") as f:
            d = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        # File may be missing or mid-write; treat as "unknown" and retry later.
        return None
    oa = d.get("oauthAccount")
    if isinstance(oa, dict):
        return oa.get("emailAddress")
    return None


def state_for_email(email):
    """Message describing the browser state the extension should hold."""
    if not email:
        return {"type": "logged_out"}
    stash = keychain_get(email)
    if stash:
        return {"type": "switch", "email": email, "cookies": stash}
    return {"type": "need_login", "email": email}


# ---- watcher thread ----------------------------------------------------------

def watcher():
    while True:
        try:
            p = claude_json_path()
            try:
                mtime = os.path.getmtime(p)
            except OSError:
                mtime = 0.0
            if mtime != _last_mtime[0]:
                _last_mtime[0] = mtime
                email = read_active_email()
                if email != _last_email[0]:
                    _last_email[0] = email
                    log("active account ->", email)
                    send_message(state_for_email(email))
        except Exception:
            log("watcher error\n" + traceback.format_exc())
        time.sleep(POLL_INTERVAL)


# ---- message handlers --------------------------------------------------------

def handle(msg):
    t = msg.get("type")
    if t == "hello":
        email = read_active_email()
        _last_email[0] = email
        try:
            _last_mtime[0] = os.path.getmtime(claude_json_path())
        except OSError:
            _last_mtime[0] = 0.0
        send_message(state_for_email(email))
    elif t == "capture":
        email = read_active_email()
        if not email:
            log("capture ignored: no active account")
            return
        cookies = msg.get("cookies") or []
        incoming = session_value(cookies)
        if incoming is None:
            log("capture ignored: no sessionKey in payload")
            return
        existing = keychain_get(email)
        if existing and session_value(existing) == incoming:
            log("capture: unchanged for", email)
            return
        if keychain_set(email, cookies):
            send_message({"type": "captured", "email": email})
            log("vaulted session for", email)
    else:
        log("unknown message:", t)


def main():
    # Establish the watcher baseline so it only reacts to *changes* after start;
    # the initial sync is handled by the "hello" round-trip.
    _last_email[0] = read_active_email()
    try:
        _last_mtime[0] = os.path.getmtime(claude_json_path())
    except OSError:
        _last_mtime[0] = 0.0

    threading.Thread(target=watcher, daemon=True).start()

    while True:
        try:
            msg = read_message()
        except Exception:
            log("read error\n" + traceback.format_exc())
            break
        if msg is None:
            break
        try:
            handle(msg)
        except Exception:
            log("handle error\n" + traceback.format_exc())
    log("stdin closed, exiting")


if __name__ == "__main__":
    main()
