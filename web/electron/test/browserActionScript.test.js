"use strict";

const assert = require("node:assert/strict");
const { it } = require("node:test");
const { JSDOM } = require("jsdom");
const { buildBrowserActionScript } = require("../src/browserActionScript");

it("snapshots the DOM, resolves refs, types literal text and rejects superseded refs", () => {
  const dom = new JSDOM('<button>Save</button><input aria-label="Name">', {
    url: "https://example.com",
    runScripts: "outside-only",
  });
  try {
    const { window } = dom;
    // JSDOM has no layout; provide visible bounds for the real DOM walk.
    for (const el of window.document.querySelectorAll("*")) {
      el.getBoundingClientRect = () => ({ width: 100, height: 40 });
      el.scrollIntoView = () => {};
    }
    const snapshot = JSON.parse(window.eval(buildBrowserActionScript("snapshot")));
    assert.match(snapshot.tree, /button "Save" \[ref=1\]/);
    assert.match(snapshot.tree, /textbox "Name" \[ref=2\]/);
    let clicks = 0;
    window.document.querySelector("button").addEventListener("click", () => clicks++);
    window.eval(buildBrowserActionScript("click", { ref: 1, snapshot_id: snapshot.snapshot_id }));
    assert.equal(clicks, 1);
    const input = window.document.querySelector("input");
    const events = [];
    for (const event of ["input", "change"])
      input.addEventListener(event, () => events.push(event));
    const text = 'hello "world"\n☀';
    window.eval(buildBrowserActionScript("type", { selector: 'input[aria-label="Name"]', text }));
    assert.equal(input.value, text.replace("\n", ""));
    assert.deepEqual(events, ["input", "change"]);
    window.eval(buildBrowserActionScript("snapshot"));
    assert.throws(
      () =>
        window.eval(
          buildBrowserActionScript("click", {
            ref: 1,
            snapshot_id: snapshot.snapshot_id,
          }),
        ),
      /superseded/,
    );
    assert.equal(clicks, 1);
  } finally {
    dom.window.close();
  }
});

it("rejects unknown actions, non-data arguments and out-of-range references", () => {
  for (const [action, args] of [
    ["evaluate", {}],
    ["snapshot", { js: "1 + 1" }],
    ["click", null],
    ["click", { ref: -1 }],
    ["click", { ref: Infinity }],
    ["click", { ref: "1" }],
    ["click", {}],
    ["type", { selector: "input", text: {} }],
    ["click", { selector: "x".repeat(4097) }],
  ])
    assert.throws(() => buildBrowserActionScript(action, args));
});

it("accepts text and snapshot identifiers at their size limits", () => {
  assert.doesNotThrow(() => buildBrowserActionScript("type", { ref: 1, text: "x".repeat(100000) }));
  assert.throws(
    () => buildBrowserActionScript("type", { ref: 1, text: "x".repeat(100001) }),
    /text must/,
  );
  assert.doesNotThrow(() =>
    buildBrowserActionScript("click", { ref: 1, snapshot_id: "x".repeat(128) }),
  );
  assert.throws(
    () => buildBrowserActionScript("click", { ref: 1, snapshot_id: "x".repeat(129) }),
    /snapshot_id must/,
  );
});
