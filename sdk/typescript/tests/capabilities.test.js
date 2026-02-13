const assert = require("node:assert/strict");
const test = require("node:test");

const { generateKeypair } = require("../dist/crypto");
const { signToken, verifyChain, enforceCapability } = require("../dist/capabilities");

test("capability chain validates", async () => {
  const { privateKey: issuerPriv, publicKey: issuerPub } = await generateKeypair();
  const { privateKey: subjectPriv, publicKey: subjectPub } = await generateKeypair();
  const token1 = await signToken({
    issuerPrivateKey: issuerPriv,
    subject: subjectPub,
    capability: "service:resource:read",
    caveats: { not_before: 0 },
  });
  const token2 = await signToken({
    issuerPrivateKey: subjectPriv,
    subject: issuerPub,
    capability: "service:resource:read",
    caveats: { not_before: 0 },
  });
  await verifyChain([token1, token2], 1);
  await enforceCapability([token1, token2], "service:resource:read", 1);
});
