import { hash as blake3Js } from "blake3";
import { getPublicKey, sign as signJs, verify as verifyJs } from "@noble/ed25519";
import { randomFillSync } from "node:crypto";

import { getWasm } from "./wasm";

export type Tag = {
  key: string;
  values: string[];
};

export async function generateKeypair(): Promise<{ privateKey: Uint8Array; publicKey: Uint8Array }> {
  const privateKey = getRandomValues(new Uint8Array(32));
  const publicKey = await getPublicKey(privateKey);
  return { privateKey, publicKey };
}

export function computeEventId(params: {
  pubkey: Uint8Array;
  createdAt: number;
  kind: number;
  tags: Tag[];
  content: Uint8Array;
}): Uint8Array {
  const { pubkey, createdAt, kind, tags, content } = params;
  const payload = new Uint8Array(
    pubkey.length + 8 + 2 + serializeTags(tags).length + content.length
  );
  let offset = 0;
  payload.set(pubkey, offset);
  offset += pubkey.length;
  payload.set(u64be(createdAt), offset);
  offset += 8;
  payload.set(u16be(kind), offset);
  offset += 2;
  const tagBytes = serializeTags(tags);
  payload.set(tagBytes, offset);
  offset += tagBytes.length;
  payload.set(content, offset);
  const wasm = getWasm();
  if (wasm) {
    return wasm.blake3(payload);
  }
  return toUint8Digest(blake3Js(payload));
}

export async function signEventId(eventId: Uint8Array, privateKey: Uint8Array): Promise<Uint8Array> {
  const wasm = getWasm();
  if (wasm) {
    return wasm.sign(eventId, privateKey);
  }
  return signJs(eventId, privateKey);
}

export async function verifyEventId(
  eventId: Uint8Array,
  signature: Uint8Array,
  publicKey: Uint8Array
): Promise<boolean> {
  const wasm = getWasm();
  if (wasm) {
    return wasm.verify(signature, eventId, publicKey);
  }
  return verifyJs(signature, eventId, publicKey);
}

export function serializeTags(tags: Tag[]): Uint8Array {
  if (tags.length > 0xffff) {
    throw new Error("tags exceeds uint16 length");
  }
  const parts: Uint8Array[] = [];
  parts.push(u16be(tags.length));
  for (const tag of tags) {
    const keyBytes = new TextEncoder().encode(tag.key);
    if (keyBytes.length === 0 || keyBytes.length > 0xff) {
      throw new Error("tag key length invalid");
    }
    parts.push(u8(keyBytes.length), keyBytes);
    if (tag.values.length > 0xffff) {
      throw new Error("tag values exceeds uint16 length");
    }
    parts.push(u16be(tag.values.length));
    for (const value of tag.values) {
      const valueBytes = new TextEncoder().encode(value);
      if (valueBytes.length > 0xffff) {
        throw new Error("tag value exceeds uint16 length");
      }
      parts.push(u16be(valueBytes.length), valueBytes);
    }
  }
  return concat(parts);
}

export function serializeTagsForPow(tags: Tag[]): Uint8Array {
  return serializeTags(tags);
}

function u8(value: number): Uint8Array {
  return Uint8Array.of(value);
}

function u16be(value: number): Uint8Array {
  const buf = new Uint8Array(2);
  buf[0] = (value >> 8) & 0xff;
  buf[1] = value & 0xff;
  return buf;
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

function getRandomValues(buffer: Uint8Array): Uint8Array {
  if (globalThis.crypto?.getRandomValues) {
    return globalThis.crypto.getRandomValues(buffer);
  }
  return randomFillSync(buffer);
}

function toUint8Digest(digest: Uint8Array | string): Uint8Array {
  if (typeof digest === "string") {
    return Uint8Array.from(Buffer.from(digest, "hex"));
  }
  return digest;
}
