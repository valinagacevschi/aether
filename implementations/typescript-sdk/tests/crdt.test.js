const assert = require("node:assert/strict");
const test = require("node:test");

const { GCounter, PNCounter, LWWRegister, ORSet } = require("../dist/crdt");

test("gcounter", () => {
  const counter = new GCounter();
  counter.add(2, "a");
  counter.add(1, "b");
  assert.equal(counter.value, 3);
});

test("pncounter", () => {
  const counter = new PNCounter();
  counter.add(3, "a");
  counter.remove(1, "a");
  assert.equal(counter.value, 2);
});

test("lwwregister", () => {
  const reg = new LWWRegister();
  reg.update("a", 1, "a");
  reg.update("b", 1, "b");
  assert.equal(reg.value, "b");
  reg.remove(2, "a");
  assert.equal(reg.tombstone, true);
});

test("orset", () => {
  const set = new ORSet();
  set.add("x", "t1");
  set.add("x", "t2");
  set.remove("x", ["t1"]);
  assert.deepEqual([...set.elements()].sort(), ["x"]);
});
