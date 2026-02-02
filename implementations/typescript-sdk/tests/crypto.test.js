const assert = require("node:assert/strict");
const test = require("node:test");

const { computeEventId, generateKeypair, signEventId, verifyEventId } = require("../dist/crypto");

test("sign/verify roundtrip", async () => {
  const { privateKey, publicKey } = await generateKeypair();
  const eventId = computeEventId({
    pubkey: publicKey,
    createdAt: 1,
    kind: 1,
    tags: [],
    content: Buffer.from("hello"),
  });
  const sig = await signEventId(eventId, privateKey);
  const ok = await verifyEventId(eventId, sig, publicKey);
  assert.equal(ok, true);
});
