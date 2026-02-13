const assert = require("node:assert/strict");
const test = require("node:test");

const { encodeMessage, decodeMessage } = require("../dist/wire");

test("json wire roundtrip", () => {
  const payload = { type: "publish", event: { kind: 1 } };
  const raw = encodeMessage(payload, "json");
  const decoded = decodeMessage(new TextDecoder().decode(raw), "json");
  assert.equal(decoded.msgType, "publish");
  assert.equal(decoded.payload.event.kind, 1);
});

test("flatbuffers wire roundtrip", () => {
  const payload = { type: "subscribe", sub_id: "abc", filters: [{ kinds: [1] }] };
  const raw = encodeMessage(payload, "flatbuffers");
  const decoded = decodeMessage(raw, "flatbuffers");
  assert.equal(decoded.msgType, "subscribe");
  assert.equal(decoded.payload.sub_id, "abc");
});
