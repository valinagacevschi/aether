const assert = require("node:assert/strict");
const test = require("node:test");

const { matchEvent, normalizeFilter } = require("../dist/filters");

test("filter matches event", () => {
  const filter = normalizeFilter({ kinds: [1], tags: [["c", "alpha"]] });
  const event = {
    pubkey: Buffer.from("01".repeat(32), "hex"),
    kind: 1,
    created_at: 10,
    tags: [["c", "alpha"]],
    content: "",
  };
  assert.equal(matchEvent(event, filter), true);
});

test("filter normalizes since/until ints", () => {
  const filter = normalizeFilter({ since: "10", until: 20 });
  assert.equal(filter.since, 10);
  assert.equal(filter.until, 20);
});
