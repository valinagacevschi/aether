const { AetherClient } = require("../../implementations/typescript-sdk/dist/client");

async function main() {
  const url = process.argv[2] || "ws://127.0.0.1:9000";
  const kind = Number(process.argv[3] || 1);
  const timeoutMs = Number(process.argv[4] || 5000);

  const client = new AetherClient();
  await client.connect([url]);

  let done = false;
  client.onEvent(() => {
    done = true;
    process.exit(0);
  });

  await client.subscribe("sub-1", { kinds: [kind] });

  setTimeout(() => {
    if (!done) {
      console.error("timed out waiting for event");
      process.exit(1);
    }
  }, timeoutMs);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
