// cswap-chrome background service worker.
//
// Bridges chrome.cookies <-> the native host (com.cswap.chrome_host), which
// watches ~/.claude.json and owns account identity. This worker is the dumb
// cookie read/write arm:
//   - captures the claude.ai cookie set whenever the user logs in, and hands
//     it to the host to vault (keyed by the CLI's currently-active account);
//   - applies a stashed cookie set when the host says the active account changed.

const HOST_NAME = "com.cswap.chrome_host";
const CLAUDE_DOMAIN = "claude.ai";
const SESSION_COOKIE = "sessionKey";
const RECONNECT_MS = 3000;
const CAPTURE_DEBOUNCE_MS = 2000;
const APPLY_SUPPRESS_MS = 5000;
const INITIAL_CAPTURE_MS = 3000;

let port = null;
let applying = false; // true while we're writing cookies, to suppress self-triggered capture
let captureTimer = null;

function log(...a) { console.log("[cswap-chrome]", ...a); }
function warn(...a) { console.warn("[cswap-chrome]", ...a); }

function connect() {
  if (port) return;
  try {
    port = chrome.runtime.connectNative(HOST_NAME);
  } catch (e) {
    warn("connectNative threw", e);
    scheduleReconnect();
    return;
  }
  port.onMessage.addListener(onHostMessage);
  port.onDisconnect.addListener(() => {
    const err = chrome.runtime.lastError;
    warn("host disconnected", err && err.message);
    port = null;
    scheduleReconnect();
  });
  log("connected to native host");
  send({ type: "hello" });
  // If the user was already logged in before install (no cookie change to
  // observe), snapshot the current session once the initial sync settles.
  setTimeout(captureNow, INITIAL_CAPTURE_MS);
}

function scheduleReconnect() {
  setTimeout(connect, RECONNECT_MS);
}

function ensureConnected() {
  if (!port) connect();
}

function send(msg) {
  if (!port) { warn("send with no port", msg && msg.type); return; }
  try {
    port.postMessage(msg);
  } catch (e) {
    warn("postMessage failed", e);
    port = null;
    scheduleReconnect();
  }
}

async function onHostMessage(msg) {
  if (!msg || !msg.type) return;
  log("host ->", msg.type, msg.email || "");
  switch (msg.type) {
    case "switch":
      await applyCookies(msg.email, msg.cookies || []);
      break;
    case "need_login":
      notify("cswap-chrome", `Log into claude.ai as ${msg.email} once — I'll remember it.`);
      break;
    case "logged_out":
      log("CLI has no active account; leaving the browser session as-is");
      break;
    case "captured":
      notify("cswap-chrome", `Saved claude.ai session for ${msg.email}`);
      break;
    default:
      log("unknown host message", msg.type);
  }
}

function urlForCookie(c) {
  const host = c.domain && c.domain.startsWith(".") ? c.domain.slice(1) : c.domain;
  return "https://" + host + (c.path || "/");
}

function getClaudeCookies() {
  return chrome.cookies.getAll({ domain: CLAUDE_DOMAIN });
}

async function applyCookies(email, cookies) {
  applying = true;
  try {
    // Clear the current claude.ai cookies, then lay down the stashed set.
    const current = await getClaudeCookies();
    for (const c of current) {
      try {
        await chrome.cookies.remove({ url: urlForCookie(c), name: c.name, storeId: c.storeId });
      } catch (e) {
        warn("remove failed", c.name, e);
      }
    }
    for (const c of cookies) {
      const details = {
        url: urlForCookie(c),
        name: c.name,
        value: c.value,
        path: c.path,
        secure: c.secure,
        httpOnly: c.httpOnly,
        sameSite: c.sameSite,
        storeId: c.storeId,
      };
      // Host-only cookies must be set by url alone; domain cookies carry .domain.
      if (!c.hostOnly && c.domain) details.domain = c.domain;
      // Session cookies have no expiration; only pass a real one.
      if (!c.session && typeof c.expirationDate === "number") details.expirationDate = c.expirationDate;
      try {
        await chrome.cookies.set(details);
      } catch (e) {
        warn("set failed", c.name, e);
      }
    }
    // Reload open claude.ai tabs so the page picks up the new identity.
    const tabs = await chrome.tabs.query({ url: "https://claude.ai/*" });
    for (const t of tabs) {
      try { await chrome.tabs.reload(t.id); } catch (e) { /* tab may be gone */ }
    }
    notify("cswap-chrome", `Switched claude.ai to ${email}`);
    log("applied", cookies.length, "cookies for", email);
  } finally {
    // Keep suppressing for a beat so the resulting onChanged burst doesn't
    // bounce back to the host as a fresh capture.
    setTimeout(() => { applying = false; }, APPLY_SUPPRESS_MS);
  }
}

// Capture path: a real login writes/updates the sessionKey cookie. Debounce,
// then snapshot the whole claude.ai cookie set and hand it to the host.
chrome.cookies.onChanged.addListener((info) => {
  const c = info.cookie;
  if (!c || !c.domain || c.domain.indexOf(CLAUDE_DOMAIN) === -1) return;
  if (c.name !== SESSION_COOKIE) return;
  if (info.removed) return; // logout / eviction — nothing to capture
  if (applying) return;     // our own write
  if (captureTimer) clearTimeout(captureTimer);
  captureTimer = setTimeout(captureNow, CAPTURE_DEBOUNCE_MS);
});

async function captureNow() {
  captureTimer = null;
  if (applying) return;
  const cookies = await getClaudeCookies();
  const hasSession = cookies.some((c) => c.name === SESSION_COOKIE && c.value);
  if (!hasSession) return; // not logged in
  ensureConnected();
  send({ type: "capture", cookies });
  log("sent capture:", cookies.length, "cookies");
}

function notify(title, message) {
  try {
    chrome.notifications.create("", {
      type: "basic",
      iconUrl: chrome.runtime.getURL("icon-128.png"),
      title,
      message,
    });
  } catch (e) {
    warn("notify failed", e);
  }
}

// Heartbeat: MV3 can suspend the worker and drop the native port; the alarm
// wakes us periodically to reconnect if needed.
chrome.alarms.create("heartbeat", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === "heartbeat") ensureConnected();
});

chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);

connect();
