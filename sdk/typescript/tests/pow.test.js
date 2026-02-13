const assert = require("node:assert/strict");
const test = require("node:test");

const { computePowNonce, meetsDifficulty } = require("../dist/pow");

test("pow helper meets difficulty", () => {
  const { nonce, eventId } = computePowNonce({
    pubkey: Buffer.from("01".repeat(32), "hex"),
    createdAt: 1,
    kind: 1,
    tags: Buffer.from([0, 0]),
    content: Buffer.from(""),
    difficulty: 4,
  });
  assert.equal(typeof nonce, "number");
  assert.equal(meetsDifficulty(eventId, 4), true);
});
