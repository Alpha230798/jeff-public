const test = require("node:test");
const assert = require("node:assert/strict");
require("./logic.js");

test("sanitizes page text and enforces the visible text cap", () => {
  assert.equal(JeffLogic.sanitizePageText("  First\r\n\n  second\tline\u0000 "), "First\nsecond line");
  assert.equal(JeffLogic.sanitizePageText("123456", 4), "1234");
});

test("page text filter excludes controls and hidden content", () => {
  for (const tag of ["INPUT", "TEXTAREA", "SELECT", "OPTION", "SCRIPT", "BUTTON"]) {
    assert.equal(JeffLogic.shouldExcludeElement(tag), true, tag);
  }
  assert.equal(JeffLogic.shouldExcludeElement("DIV", { hidden: true }), true);
  assert.equal(JeffLogic.shouldExcludeElement("SPAN", { "aria-hidden": "true" }), true);
  assert.equal(JeffLogic.shouldExcludeElement("DIV", { contenteditable: "true" }), true);
  assert.equal(JeffLogic.shouldExcludeElement("DIV", { contenteditable: "" }), true);
  assert.equal(JeffLogic.shouldExcludeElement("DIV", { contenteditable: "false" }), false);
  assert.equal(JeffLogic.shouldExcludeElement("ARTICLE"), false);
});

test("parses only supported refresh and monitor tasks with a 30 second floor", () => {
  assert.equal(JeffLogic.parseTaskRequest("refresh this page every 2 minutes").intervalSec, 120);
  assert.equal(JeffLogic.parseTaskRequest("monitor this page for changes").type, "monitor");
  assert.equal(JeffLogic.parseTaskRequest('monitor element "Stock price" for changes').targetText, "Stock price");
  assert.match(JeffLogic.parseTaskRequest("reload every 5 seconds").error, /30 seconds/);
  assert.equal(JeffLogic.parseTaskRequest("buy this item"), null);
});

test("parses literal page targets instead of model generated selectors", () => {
  assert.deepEqual(JeffLogic.parsePageAction('highlight "Delivery date"'), { type: "highlight", target: "Delivery date" });
  assert.deepEqual(JeffLogic.parsePageAction("scroll to Shipping information"), { type: "scroll", target: "Shipping information" });
  assert.equal(JeffLogic.parsePageAction("click Continue"), null);
});

test("normalizes trivial monitor noise and returns a bounded change excerpt", () => {
  assert.equal(
    JeffLogic.normalizeForComparison("Price 12:30\nSponsored content\nUSD 10"),
    JeffLogic.normalizeForComparison("Price 18:55\nUSD 10"),
  );
  assert.equal(JeffLogic.changedExcerpt("price was ten dollars", "price is now twelve dollars"), "price is now twelve dollars");
  assert.equal(JeffLogic.changedExcerpt("same", "same"), "");
});

test("enforces task count, interval, and expiry rules", () => {
  const valid = { type: "refresh", intervalSec: 30, expiresMinutes: 120 };
  assert.equal(JeffLogic.validTaskRules(valid).ok, true);
  assert.equal(JeffLogic.validTaskRules(valid, { taskCount: 5 }).ok, false);
  assert.equal(JeffLogic.validTaskRules({ ...valid, intervalSec: 10 }).ok, false);
  assert.equal(JeffLogic.validTaskRules({ ...valid, expiresMinutes: 1441 }).ok, false);
});
