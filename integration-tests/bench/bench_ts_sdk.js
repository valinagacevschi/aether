const { AetherClient } = require("../../sdk/typescript/dist/client");
const { computeEventId, generateKeypair, signEventId } = require("../../sdk/typescript/dist/crypto");

async function main() {
  const url = process.argv[2] || "ws://127.0.0.1:9000";
  const count = Number(process.argv[3] || 100);
  const { privateKey, publicKey } = await generateKeypair();
  const client = new AetherClient();
  await client.connect([url]);

  const start = Date.now();
  for (let idx = 0; idx < count; idx += 1) {
    const createdAt = idx + 1;
    const content = `bench-${idx}`;
    const eventId = computeEventId({
      pubkey: publicKey,
      createdAt,
      kind: 1,
      tags: [],
      content: Buffer.from(content),
    });
    const sig = await signEventId(eventId, privateKey);
    const event = {
      event_id: Buffer.from(eventId).toString("hex"),
      pubkey: Buffer.from(publicKey).toString("hex"),
      kind: 1,
      created_at: createdAt,
      tags: [],
      content,
      sig: Buffer.from(sig).toString("hex"),
    };
    await client.publish(event);
  }
  const elapsed = (Date.now() - start) / 1000;
  console.log(`published ${count} events in ${elapsed.toFixed(3)}s (${(count / elapsed).toFixed(1)} ev/s)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
