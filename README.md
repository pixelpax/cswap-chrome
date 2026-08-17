# cswap-chrome

When the [`cswap`](https://pypi.org/project/claude-swap/) CLI switches your
active Claude account, this **opens the account-switch page in Chrome and posts
a macOS notification**, so you can re-sign Anthropic's **Claude-in-Chrome**
extension into the matching account without having to notice the mismatch
yourself.

macOS + Chrome only.

## Why it only *prompts* (and doesn't switch the extension for you)

The Claude-in-Chrome extension holds its **own account**, established by a full
SSO / credential login and **decoupled from the claude.ai web-session cookie**.
You switch it by opening the extension, hitting *switch account*, and logging in
via SSO. Nothing outside the extension can do that for you — not a cookie swap,
not a token swap — because it's an intentional authentication boundary.

So this tool doesn't fight that. It watches `~/.claude.json` for the active
account (`oauthAccount.emailAddress`), and when it changes it just puts the
switch-account page in front of you. The one manual SSO click stays yours; the
"remembering to do it" part is automated.

> Earlier versions tried to swap the claude.ai cookie from a companion
> extension, on the assumption that the cookie *was* the extension's identity.
> It isn't — that approach was abandoned. See the git history if curious.

## Install

```sh
./install.sh                       # opens the Google account chooser on a switch
./install.sh 'https://your/page'   # or point it at whatever page you prefer
```

That registers a launchd **LaunchAgent** (`com.cswap.chrome-watch`) that runs a
tiny Python poller. It survives reboots and login; there's nothing to babysit.
It only ever launches Chrome-facing actions **while Chrome is already running**,
so an overnight `cswap` rotation won't pop Chrome open at 3am — the prompt waits
until Chrome is next up and then fires once for the latest account.

Re-run `./install.sh 'URL'` any time to change the page it opens.

## What it does on a switch

1. Posts a notification: "cswap switched account — Now &lt;email&gt;."
2. Opens the configured page in Chrome.

You then hit *switch account* in the Claude extension and do the SSO login.

## Uninstall

```sh
./uninstall.sh
```

Removes the LaunchAgent and the saved state. (Also remove any leftover unpacked
`cswap-chrome` extension from `chrome://extensions` if you ever loaded the old
version.)

## Files

- `bin/cswap-chrome-watch.py` — the poller/notifier (stdlib only).
- `com.cswap.chrome-watch.plist.template` — LaunchAgent template.
- `install.sh` / `uninstall.sh` — register / remove the agent.

Logs: `~/Library/Logs/cswap-chrome-watch.log`. State (last-seen account):
`~/Library/Application Support/cswap-chrome/last-account`.
