(() => {
  const EXCLUDED_TAGS = new Set([
    "SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "INPUT", "TEXTAREA", "SELECT",
    "OPTION", "BUTTON", "IFRAME", "OBJECT", "EMBED",
  ]);

  function sanitizePageText(value, limit = 12000) {
    const max = Number.isFinite(limit) ? Math.max(0, Math.floor(limit)) : 12000;
    return String(value ?? "")
      .replace(/\r\n?/g, "\n")
      .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
      .split("\n")
      .map((line) => line.replace(/[^\S\n]+/g, " ").trim())
      .filter(Boolean)
      .join("\n")
      .slice(0, max);
  }

  function shouldExcludeElement(tagName, attributes = {}) {
    const tag = String(tagName || "").toUpperCase();
    return EXCLUDED_TAGS.has(tag)
      || Boolean(attributes.hidden)
      || String(attributes["aria-hidden"] || "").toLowerCase() === "true"
      || (Object.prototype.hasOwnProperty.call(attributes, "contenteditable")
        && String(attributes.contenteditable).toLowerCase() !== "false");
  }

  function parseTaskRequest(text, now = Date.now()) {
    const source = String(text || "").trim();
    const duration = source.match(/\b(?:every|each)\s+(\d+)\s*(seconds?|secs?|minutes?|mins?)\b/i);
    const intervalSec = duration
      ? Number(duration[1]) * (/^m/i.test(duration[2]) ? 60 : 1)
      : 30;
    if (/\b(?:refresh|reload)\b/i.test(source)) {
      if (!duration) return { error: "Please say how often Jeff should refresh, for example: every 2 minutes." };
      if (!Number.isFinite(intervalSec) || intervalSec < 30) return { error: "Jeff can refresh no more often than every 30 seconds." };
      if (intervalSec > 86400) return { error: "Choose a refresh interval of one day or less." };
      return { type: "refresh", intervalSec, expiresMinutes: 120, createdAt: now };
    }
    if (/\b(?:monitor|watch)\b|\btell me when\b/i.test(source) && /\b(?:change|changes|changed|update|updates)\b/i.test(source)) {
      if (duration && intervalSec < 30) return { error: "Jeff checks for changes no more often than every 30 seconds." };
      const targetMatch = source.match(/\belement\s+["“']?(.+?)["”']?(?:\s+(?:for\s+)?(?:changes?|updates?))?\s*$/i);
      return {
        type: "monitor", intervalSec: duration ? intervalSec : 30, expiresMinutes: 120, createdAt: now,
        targetText: targetMatch ? targetMatch[1].replace(/["“”']+$/g, "").trim().slice(0, 120) : "",
      };
    }
    return null;
  }

  function parsePageAction(text) {
    const match = String(text || "").trim().match(/^\s*(highlight|scroll to)\s+["“]?(.+?)["”]?\s*[.!?]*\s*$/i);
    if (!match || match[2].length < 2 || match[2].length > 120) return null;
    return { type: match[1].toLowerCase() === "highlight" ? "highlight" : "scroll", target: match[2] };
  }

  function normalizeForComparison(text) {
    return sanitizePageText(text)
      .split("\n")
      .filter((line) => !/\b(advertisement|sponsored content|sponsored|cookie preferences)\b/i.test(line))
      .map((line) => line.replace(/\b\d{1,2}:\d{2}(?::\d{2})?\b/g, "").replace(/\b20\d{2}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?Z?)?\b/g, ""))
      .join("\n")
      .replace(/\s+/g, " ")
      .trim()
      .toLocaleLowerCase();
  }

  function changedExcerpt(previous, current, limit = 600) {
    const before = String(previous || "");
    const after = String(current || "");
    let start = 0;
    while (start < before.length && start < after.length && before[start] === after[start]) start += 1;
    let endBefore = before.length;
    let endAfter = after.length;
    while (endBefore > start && endAfter > start && before[endBefore - 1] === after[endAfter - 1]) {
      endBefore -= 1; endAfter -= 1;
    }
    if (start === before.length && start === after.length) return "";
    const excerptStart = Math.max(0, start - Math.floor(limit / 4));
    return after.slice(excerptStart, Math.min(after.length, endAfter + Math.floor(limit / 2))).slice(0, limit).trim()
      || "The page content changed.";
  }

  function validTaskRules(task, { now = Date.now(), taskCount = 0, maxTasks = 5 } = {}) {
    if (taskCount >= maxTasks) return { ok: false, reason: "Jeff can run at most " + maxTasks + " tasks at once." };
    if (!task || !["refresh", "monitor"].includes(task.type)) return { ok: false, reason: "That task is not supported." };
    if (!Number.isFinite(task.intervalSec) || task.intervalSec < 30) return { ok: false, reason: "Task interval must be at least 30 seconds." };
    if (!Number.isFinite(task.expiresMinutes) || task.expiresMinutes < 1 || task.expiresMinutes > 1440) {
      return { ok: false, reason: "Choose an expiry between 1 minute and 24 hours." };
    }
    if (task.createdAt && task.createdAt > now + 60_000) return { ok: false, reason: "Task start time is invalid." };
    return { ok: true };
  }

  globalThis.JeffLogic = Object.freeze({
    sanitizePageText, shouldExcludeElement, parseTaskRequest, parsePageAction,
    normalizeForComparison, changedExcerpt, validTaskRules,
  });
})();
