# cswap-chrome

Keeps Chrome's **claude.ai** session on whichever Claude account the
[`cswap`](https://pypi.org/project/claude-swap/) CLI is currently switched to,
so you don't have to re-log the browser (and the **Claude in Chrome** extension,
whose identity *is* the claude.ai session) every time you rotate accounts.

It's a companion Chrome extension plus a tiny Python native-messaging host. The
host watches `~/.claude.json`, owns account identity, and vaults each account's
claude.ai cookie set in the **macOS Keychain**. The extension is just the
cookie read/write arm.

> macOS + Chrome only, for now. It modifies neither `cswap` nor Anthropic's
> Claude-in-Chrome extension — it just moves cookies.

## How it works

1. The native host reads the active account's email from `~/.claude.json`
   (`oauthAccount.emailAddress`) and polls it for changes.
2. When you're logged into claude.ai, the extension snapshots the full cookie
   set and hands it to the host, which stores it in the Keychain keyed by the
   **currently active CLI account** (service `cswap-chrome`, account = email).
3. When `cswap` switches accounts, the host sees `~/.claude.json` change and, if
   it has a stash for the new account, tells the extension to swap the claude.ai
   cookies and reload any open claude.ai tabs. If there's no stash yet, it asks
   you to log in once.

Because the host watches the file rather than hooking `cswap`, **every** switch
path is followed — manual `cswap switch`, `cswap auto`, and overnight rotation.

## Security model

- Session cookies live only in the macOS Keychain, never in this repo or in
  plaintext on disk.
- The repo contains no tokens or secrets. `key.pem` (the extension's signing
  key, used only to pin a stable extension ID) is git-ignored.
- The extension is scoped to `claude.ai` and talks only to this one native host
  (allow-listed by extension ID).

## Install

```sh
./install.sh
```

Then, as the script prints:

1. Open `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → select the `extension/` directory.
3. Confirm the extension ID is `jeffcdjdecgpjacfknolgnhkgnanlhdc`.

## Teach it your accounts (once each)

For each account: switch `cswap` to it, then log into claude.ai in Chrome. The
extension captures that session and vaults it under the active account. You'll
get a "Saved claude.ai session for &lt;email&gt;" notification. After that,
switching `cswap` moves the browser automatically.

## Known footgun

Captures are tagged with whatever account `cswap` is on **at capture time**. If
your browser is logged into account B while the CLI is on account A when a
capture fires, the tool will vault B's session under A. Fix it by switching
`cswap` to the right account and logging into claude.ai again — the newer
capture overwrites the mistag.

## Open question (live-testing TBD)

Whether Anthropic's Claude-in-Chrome extension picks up the swapped session
**immediately** or needs its own nudge (a claude.ai tab reload — which this tool
already does — or an extension restart). If a reload turns out not to be enough,
a follow-up can add a `chrome.management` disable/enable kick of that extension.

## Uninstall

```sh
rm ~/Library/Application\ Support/Google/Chrome/NativeMessagingHosts/com.cswap.chrome_host.json
```

Remove the unpacked extension from `chrome://extensions`. To purge vaulted
sessions: `security delete-generic-password -s cswap-chrome -a <email>` per
account.
