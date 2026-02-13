import { AetherClient, computeEventId, generateKeypair, signEventId } from '../../sdk/typescript/src';

async function main(): Promise<void> {
  const client = new AetherClient();
  await client.connect(['ws://127.0.0.1:8082/v1/ws']);

  client.onEvent((event) => {
    console.log('event', event);
  });

  await client.subscribe('sub-1', { kinds: [1] });

  const { privateKey, publicKey } = await generateKeypair();
  const content = Buffer.from('hello');
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
    content: 'hello',
    sig: Buffer.from(sig).toString('hex'),
  });

  await new Promise((resolve) => setTimeout(resolve, 1000));
}

void main();
