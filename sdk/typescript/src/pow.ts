import { hash as blake3Js } from "blake3";
import { getWasm } from "./wasm";

export function leadingZeroBits(data: Uint8Array): number {
  let count = 0;
  for (const byte of data) {
    if (byte === 0) {
      count += 8;
      continue;
    }
    for (let bit = 7; bit >= 0; bit -= 1) {
      if (byte & (1 << bit)) {
        return count;
      }
      count += 1;
    }
  }
  return count;
}

export function meetsDifficulty(eventId: Uint8Array, difficulty: number): boolean {
  if (difficulty <= 0) {
    return true;
  }
  return leadingZeroBits(eventId) >= difficulty;
}

export function computePowNonce(params: {
  pubkey: Uint8Array;
  createdAt: number;
  kind: number;
  tags: Uint8Array;
  content: Uint8Array;
  difficulty: number;
}): { nonce: number; eventId: Uint8Array } {
  const { pubkey, createdAt, kind, tags, content, difficulty } = params;
  let nonce = 0;
  while (true) {
    const nonceBytes = u64be(nonce);
    const payload = concat([pubkey, u64be(createdAt), u16be(kind), tags, content, nonceBytes]);
    const wasm = getWasm();
    const eventId = wasm ? wasm.blake3(payload) : toUint8Digest(blake3Js(payload));
    if (meetsDifficulty(eventId, difficulty)) {
      return { nonce, eventId };
    }
    nonce += 1;
  }
}

function u16be(value: number): Uint8Array {
  return Uint8Array.of((value >> 8) & 0xff, value & 0xff);
}

function u64be(value: number): Uint8Array {
  const buf = new Uint8Array(8);
  let temp = BigInt(value);
  for (let i = 7; i >= 0; i -= 1) {
    buf[i] = Number(temp & 0xffn);
    temp >>= 8n;
  }
  return buf;
}

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function toUint8Digest(digest: Uint8Array | string): Uint8Array {
  if (typeof digest === "string") {
    return Uint8Array.from(Buffer.from(digest, "hex"));
  }
  return digest;
}
