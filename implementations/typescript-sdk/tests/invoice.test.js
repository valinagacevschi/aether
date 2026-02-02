const assert = require("node:assert/strict");
const test = require("node:test");

const { parseAttachment, serializeAttachment } = require("../dist/invoice");

test("invoice attachment roundtrip", () => {
  const payload = serializeAttachment({ invoice: "lnbc1...", memo: "test", amount_msat: 123 });
  const parsed = parseAttachment(payload);
  assert.equal(parsed.invoice, "lnbc1...");
  assert.equal(parsed.memo, "test");
  assert.equal(parsed.amount_msat, 123);
});
