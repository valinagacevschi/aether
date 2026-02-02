const { AetherClient } = require("../../implementations/typescript-sdk/dist/client");
const { computeEventId, generateKeypair, signEventId } = require("../../implementations/typescript-sdk/dist/crypto");

async function main() {
  const url = process.argv[2] || "ws://127.0.0.1:9000";
  const kind = Number(process.argv[3] || 1);
  const content = process.argv[4] || "hello";
  const createdAt = Number(process.argv[5] || 1);

  const { privateKey, publicKey } = await generateKeypair();
  const eventId = computeEventId({
    pubkey: publicKey,
    createdAt,
    kind,
    tags: [],
    content: Buffer.from(content),
  });
  const sig = await signEventId(eventId, privateKey);

  const event = {
    event_id: Buffer.from(eventId).toString("hex"),
    pubkey: Buffer.from(publicKey).toString("hex"),
    kind,
    created_at: createdAt,
    tags: [],
    content,
    sig: Buffer.from(sig).toString("hex"),
  };

  const client = new AetherClient();
  await client.connect([url]);
  await client.publish(event);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
