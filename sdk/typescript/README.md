# Aether TypeScript SDK

TypeScript/Node client for the Aether protocol.

## Install

From repo:

```bash
git clone https://github.com/valinagacevschi/aether
cd aether/sdk/typescript
npm install
```

From npm (when available):

```bash
npm install @aether-protocol/sdk
```

## Build

```bash
npm run build
```

## Quickstart

```ts
import { AetherClient, computeEventId, generateKeypair, signEventId } from '@aether-protocol/sdk';

async function main() {
  const client = new AetherClient();
  await client.connect(['ws://127.0.0.1:9000']);

  const { privateKey, publicKey } = await generateKeypair();
  const content = Buffer.from('{"name":"agent-1"}');
  const eventId = computeEventId({
    pubkey: publicKey,
    createdAt: 1,
    kind: 1,
    tags: [],
    content,
  });
  const sig = await signEventId(eventId, privateKey);
  await client.publish({
    event_id: Buffer.from(eventId).toString('hex'),
    pubkey: Buffer.from(publicKey).toString('hex'),
    kind: 1,
    created_at: 1,
    tags: [],
    content: content.toString('utf-8'),
    sig: Buffer.from(sig).toString('hex'),
  });
}

main();
```
