const DEFAULT_BLOCKED = [
  "paypal.com", "stripe.com", "venmo.com", "cash.app", "wise.com",
  "bankofamerica.com", "chase.com", "wellsfargo.com", "citi.com", "capitalone.com",
  "usbank.com", "discover.com", "americanexpress.com", "ally.com", "schwab.com",
  "mail.google.com", "gmail.com", "outlook.live.com", "outlook.office.com", "outlook.com", "mail.yahoo.com", "yahoo.com", "mail.icloud.com", "mail.proton.me",
  "accounts.google.com", "accounts.apple.com", "login.live.com",
  "1password.com", "lastpass.com", "bitwarden.com", "dashlane.com", "keepersecurity.com",
];
const BASE = {
  paused: false,
  name: "Jason",
  language: "Auto",
  theme: "system",
  token: "",
  allowedHosts: [],
  blockedHosts: DEFAULT_BLOCKED,
  position: null,
  tasks: [],
};

async function settings() {
  const values = await browser.storage.local.get(BASE);
  return { ...BASE, ...values };
}

const MAX_TASKS = 5;
const taskAlarm = (id) => "jeff-task:" + id;
async function readTasks() {
  const config = await settings();
  return config.tasks.filter((task) => task && task.id);
}
async function updateTasks(tasks) {
  await browser.storage.local.set({ tasks });
  await browser.action.setBadgeText({ text: tasks.some((task) => task.lastChange) ? "!" : tasks.length ? String(tasks.length) : "" });
}
async function stopTask(id, reason = "") {
  const all = await readTasks();
  const removed = all.find((task) => task.id === id);
  const tasks = all.filter((task) => task.id !== id);
  await browser.alarms.clear(taskAlarm(id));
  if (removed?.type === "monitor") browser.tabs.sendMessage(removed.tabId, { type: "jeff:monitor-stop", taskId: id }).catch(() => {});
  await updateTasks(tasks);
  if (removed && reason) {
    await browser.notifications.create({
      type: "basic", title: reason === "expired" ? "Jeff task finished" : "Jeff task stopped",
      message: reason === "expired" ? "A Jeff task reached its expiry time." : reason,
      iconUrl: browser.runtime.getURL("icons/icon-48.png"),
    });
  }
}
async function stopAllTasks(reason = "") {
  const tasks = await readTasks();
  await Promise.all(tasks.map((task) => browser.alarms.clear(taskAlarm(task.id))));
  for (const task of tasks) {
    if (task.type === "monitor") browser.tabs.sendMessage(task.tabId, { type: "jeff:monitor-stop", taskId: task.id }).catch(() => {});
  }
  await updateTasks([]);
  if (reason && tasks.length) await browser.notifications.create({
    type: "basic", title: "Jeff tasks stopped", message: reason, iconUrl: browser.runtime.getURL("icons/icon-48.png"),
  });
}

function hostMatches(host, rule) {
  const normalized = rule.trim().toLowerCase().replace(/^\*\./, "");
  return normalized && (host === normalized || host.endsWith(`.${normalized}`));
}

function blockedReason(url, config) {
  let host;
  try { host = new URL(url).hostname.toLowerCase(); } catch (_) { return "Jeff cannot open this browser page."; }
  if (config.blockedHosts.some((rule) => hostMatches(host, rule))) return "Jeff is paused on this protected site.";
  if (config.allowedHosts.length && !config.allowedHosts.some((rule) => hostMatches(host, rule))) {
    return "This site is not in your Jeff allow list.";
  }
  return "";
}

browser.action.onClicked.addListener(async (tab) => {
  if (!tab?.id || tab.incognito) return;
  const config = await settings();
  let reason = blockedReason(tab.url || "", config);
  if (reason) {
    await browser.notifications.create({
      type: "basic", title: "Jeff did not open", message: reason,
      iconUrl: browser.runtime.getURL("icons/icon-48.png"),
    });
    return;
  }
  try {
    await browser.scripting.executeScript({ target: { tabId: tab.id }, files: ["logic.js", "content.js"] });
  } catch (error) {
    await browser.notifications.create({
      type: "basic", title: "Jeff cannot open this page",
      message: "Firefox protects this page from extensions. Try a regular website tab.",
      iconUrl: browser.runtime.getURL("icons/icon-48.png"),
    });
  }
});

browser.runtime.onMessage.addListener(async (message, sender) => {
  if (message?.type === "jeff:get-settings") {
    const config = await settings();
    return {
      name: config.name,
      language: config.language,
      theme: config.theme,
      paused: config.paused,
      allowedHosts: config.allowedHosts,
      blockedHosts: config.blockedHosts,
      position: config.position,
      tokenConfigured: Boolean(config.token),
      extensionOrigin: new URL(browser.runtime.getURL("/options.html")).origin,
    };
  }
  if (message?.type === "jeff:update-settings") {
    const config = await settings();
    const update = {};
    if (typeof message.name === "string") update.name = message.name.trim().slice(0, 80) || "Boss";
    if (["Auto", "English", "French", "Mauritian Kreol (experimental)"].includes(message.language)) update.language = message.language;
    if (["system", "light", "dark"].includes(message.theme)) update.theme = message.theme;
    if (typeof message.token === "string") update.token = message.token.trim().slice(0, 512);
    if (typeof message.paused === "boolean") update.paused = message.paused;
    if (Array.isArray(message.allowedHosts)) update.allowedHosts = message.allowedHosts.filter((x) => typeof x === "string").slice(0, 100);
    if (Array.isArray(message.blockedHosts)) update.blockedHosts = message.blockedHosts.filter((x) => typeof x === "string").slice(0, 100);
    if (message.position && Number.isFinite(message.position.x) && Number.isFinite(message.position.y)) {
      update.position = { x: message.position.x, y: message.position.y };
    }
    await browser.storage.local.set(update);
    if (update.paused) await stopAllTasks("Jeff was paused in the companion settings.");
    else if (update.blockedHosts || update.allowedHosts) {
      const refreshed = { ...config, ...update };
      const tasks = await readTasks();
      for (const task of tasks) {
        if (blockedReason(task.pageUrl, refreshed)) await stopTask(task.id, "A site privacy rule changed, so Jeff stopped this task.");
      }
    }
    return { ok: true, tokenConfigured: Boolean(update.token ?? config.token) };
  }
  if (message?.type === "jeff:bridge-health") {
    const config = await settings();
    if (!config.token) return { ok: false, error: "Add your bridge token in Jeff settings." };
    try {
      const response = await fetch("http://127.0.0.1:8765/health", {
        headers: { Authorization: `Bearer ${config.token}` },
        credentials: "omit",
        cache: "no-store",
      });
      const data = await response.json();
      return { ...data, reachable: response.ok, technical: response.ok ? "" : (data.error || `HTTP ${response.status}`) };
    } catch (error) {
      return { ok: false, reachable: false, error: "The local Jeff bridge is not reachable.", technical: String(error) };
    }
  }
  if (message?.type === "jeff:chat") {
    const config = await settings();
    if (config.paused) return { ok: false, error: "Jeff is paused everywhere. Resume him in settings first.", technical: "Global pause is enabled." };
    if (!config.token) return { ok: false, error: "Add your bridge token in Jeff settings.", technical: "JEFF_BRIDGE_TOKEN is not configured in the extension." };
    try {
      const response = await fetch("http://127.0.0.1:8765/chat", {
        method: "POST",
        headers: { Authorization: `Bearer ${config.token}`, "Content-Type": "application/json" },
        body: JSON.stringify(message.payload),
        credentials: "omit",
        cache: "no-store",
      });
      const data = await response.json();
      if (!response.ok) {
        const lowerError = String(data.error || "").toLowerCase();
        const friendly = response.status === 401
          ? "Jeff could not authenticate with the local bridge. Check the token in settings."
          : response.status === 503
            ? lowerError.includes("model") && lowerError.includes("not found")
              ? "Jeff cannot find the selected chat model. Pull it in Ollama or choose an installed model."
              : "Ollama is not ready. Start Ollama and check the selected model."
            : "Jeff could not process that message. Check the details and try again.";
        return { ok: false, error: friendly, technical: data.error || `HTTP ${response.status}` };
      }
      return { ok: true, reply: data.reply };
    } catch (error) {
      return { ok: false, error: "Jeff could not reach the local bridge. Start it and try again.", technical: String(error) };
    }
  }
  if (message?.type === "jeff:save-position") {
    await browser.storage.local.set({ position: message.position });
    return { ok: true };
  }
  if (message?.type === "jeff:list-tasks") {
    return { tasks: (await readTasks()).filter((task) => task.expiresAt > Date.now() && task.tabId === sender.tab?.id) };
  }
  if (message?.type === "jeff:start-task") {
    const config = await settings();
    if (config.paused) return { ok: false, error: "Jeff is paused everywhere." };
    if (!sender.tab?.id || sender.tab.incognito) return { ok: false, error: "This tab is not available to Jeff." };
    const reason = blockedReason(message.pageUrl || sender.tab.url || "", config);
    if (reason) return { ok: false, error: reason };
    const tasks = (await readTasks()).filter((task) => task.expiresAt > Date.now());
    const candidate = {
      ...message.task,
      id: crypto.randomUUID(),
      tabId: sender.tab.id,
      pageUrl: String(message.pageUrl || "").slice(0, 2000),
      pageTitle: String(message.pageTitle || "").slice(0, 300),
      createdAt: Date.now(),
      expiresAt: Date.now() + Number(message.task.expiresMinutes) * 60_000,
      lastChange: null,
    };
    const validation = JeffLogic.validTaskRules(candidate, { taskCount: tasks.length, maxTasks: MAX_TASKS });
    if (!validation.ok) return { ok: false, error: validation.reason };
    tasks.push(candidate);
    await updateTasks(tasks);
    await browser.alarms.create(taskAlarm(candidate.id), {
      delayInMinutes: candidate.intervalSec / 60,
      periodInMinutes: candidate.intervalSec / 60,
    });
    if (candidate.type === "monitor") {
      try {
        await browser.tabs.sendMessage(candidate.tabId, { type: "jeff:monitor-start", taskId: candidate.id, targetText: candidate.targetText || "" });
      } catch (error) {
        await stopTask(candidate.id);
        return { ok: false, error: "Jeff could not start monitoring this page. Keep the tab open and try again.", technical: String(error) };
      }
    }
    return { ok: true, task: candidate };
  }
  if (message?.type === "jeff:stop-task") {
    await stopTask(message.taskId);
    return { ok: true };
  }
  if (message?.type === "jeff:monitor-changed") {
    const tasks = (await readTasks()).filter((task) => task.expiresAt > Date.now());
    const task = tasks.find((item) => item.id === message.taskId && item.type === "monitor" && item.tabId === sender.tab?.id);
    if (!task || typeof message.excerpt !== "string") return { ok: false };
    task.lastChange = message.excerpt.slice(0, 600);
    await updateTasks(tasks);
    await browser.notifications.create({
      type: "basic", title: "Jeff noticed a page change",
      message: (task.pageTitle || "The monitored page") + " changed. Open Jeff to review it.",
      iconUrl: browser.runtime.getURL("icons/icon-48.png"),
    });
    return { ok: true };
  }
  if (message?.type === "jeff:clear-change") {
    const tasks = (await readTasks()).filter((task) => task.expiresAt > Date.now());
    const task = tasks.find((item) => item.id === message.taskId && item.tabId === sender.tab?.id);
    if (task) task.lastChange = null;
    await updateTasks(tasks);
    return { ok: true };
  }
});

browser.runtime.onInstalled.addListener(async () => {
  const saved = await browser.storage.local.get(null);
  const defaults = Object.fromEntries(Object.entries(BASE).filter(([key]) => !(key in saved)));
  if (Object.keys(defaults).length) await browser.storage.local.set(defaults);
});

browser.alarms.onAlarm.addListener(async (alarm) => {
  if (!alarm.name.startsWith("jeff-task:")) return;
  const id = alarm.name.slice("jeff-task:".length);
  const tasks = await readTasks();
  const task = tasks.find((item) => item.id === id);
  if (!task) { await browser.alarms.clear(alarm.name); return; }
  if (task.expiresAt <= Date.now()) { await stopTask(task.id, "expired"); return; }
  if (task.type === "refresh") {
    try { await browser.tabs.reload(task.tabId); }
    catch (_) { await stopTask(task.id, "Firefox could not refresh the tab, so Jeff stopped the task."); }
  } else if (task.type === "monitor") {
    try { await browser.tabs.sendMessage(task.tabId, { type: "jeff:monitor-sample", taskId: task.id }); }
    catch (_) { await stopTask(task.id, "Jeff lost access to the page. Reopen the widget to start monitoring again."); }
  }
});

browser.tabs.onRemoved.addListener(async (tabId) => {
  const tasks = (await readTasks()).filter((task) => task.expiresAt > Date.now());
  await Promise.all(tasks.filter((task) => task.tabId === tabId).map((task) => stopTask(task.id)));
});

browser.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (!changeInfo.url) return;
  const tasks = (await readTasks()).filter((task) => task.expiresAt > Date.now());
  for (const task of tasks.filter((item) => item.tabId === tabId)) {
    let originChanged = false;
    try { originChanged = new URL(task.pageUrl).origin !== new URL(changeInfo.url).origin; } catch (_) { originChanged = true; }
    if (task.type === "monitor" || originChanged) {
      await stopTask(task.id, "The page navigated, so Jeff stopped its task.");
    }
  }
});

browser.runtime.onStartup.addListener(() => {
  // Tab identifiers can be reused after a restart; never resume a task on a different page.
  stopAllTasks("Firefox restarted; tasks do not resume automatically.");
});

