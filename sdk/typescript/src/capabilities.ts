import { hash as blake3Js } from "blake3";
import { getPublicKey, sign as signJs, verify as verifyJs } from "@noble/ed25519";

import { getWasm } from "./wasm";

export type CapabilityToken = {
  issuer: Uint8Array;
  subject: Uint8Array;
  capability: string;
  caveats: Record<string, unknown>;
  sig: Uint8Array;
};

export function computeTokenId(token: CapabilityToken): Uint8Array {
  const payload = serializePayload(token);
  const wasm = getWasm();
  if (wasm) {
    return wasm.blake3(payload);
  }
  return toUint8Digest(blake3Js(payload));
}

export async function signToken(params: {
  issuerPrivateKey: Uint8Array;
  subject: Uint8Array;
  capability: string;
  caveats: Record<string, unknown>;
}): Promise<CapabilityToken> {
  const issuerPublicKey = await getPublicKey(params.issuerPrivateKey);
  const token: CapabilityToken = {
    issuer: issuerPublicKey,
    subject: params.subject,
    capability: params.capability,
    caveats: params.caveats,
    sig: new Uint8Array(),
  };
  const tokenId = computeTokenId(token);
  const wasm = getWasm();
  const signature = wasm
    ? await wasm.sign(tokenId, params.issuerPrivateKey)
    : await signJs(tokenId, params.issuerPrivateKey);
  return {
    issuer: issuerPublicKey,
    subject: params.subject,
    capability: params.capability,
    caveats: params.caveats,
    sig: signature,
  };
}

export async function verifyChain(tokens: CapabilityToken[], nowNs: number): Promise<void> {
  if (!tokens.length) {
    throw new Error("empty capability chain");
  }
  for (let i = 0; i < tokens.length; i += 1) {
    const token = tokens[i];
    const tokenId = computeTokenId(token);
    const wasm = getWasm();
    const ok = wasm
      ? await wasm.verify(token.sig, tokenId, token.issuer)
      : await verifyJs(token.sig, tokenId, token.issuer);
    if (!ok) {
      throw new Error("invalid capability signature");
    }
    enforceCaveats(token, nowNs);
    const next = tokens[i + 1];
    if (next && !equalBytes(token.subject, next.issuer)) {
      throw new Error("capability chain subject mismatch");
    }
  }
}

export async function enforceCapability(
  tokens: CapabilityToken[],
  required: string,
  nowNs: number
): Promise<void> {
  await verifyChain(tokens, nowNs);
  const last = tokens[tokens.length - 1];
  if (!last || last.capability !== required) {
    throw new Error("capability not granted");
  }
}

function enforceCaveats(token: CapabilityToken, nowNs: number): void {
  const notBefore = parseOptionalInt(token.caveats.not_before);
  const notAfter = parseOptionalInt(token.caveats.not_after);
  if (notBefore !== undefined && nowNs < notBefore) {
    throw new Error("capability not yet valid");
  }
  if (notAfter !== undefined && nowNs > notAfter) {
    throw new Error("capability expired");
  }
}

function parseOptionalInt(value: unknown): number | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isNaN(parsed)) {
      throw new Error("caveat must be int");
    }
    return parsed;
  }
  throw new Error("caveat must be int");
}

function serializePayload(token: CapabilityToken): Uint8Array {
  const payload = JSON.stringify({
    issuer: toHex(token.issuer),
    subject: toHex(token.subject),
    capability: token.capability,
    caveats: sortObject(token.caveats),
  });
  return new TextEncoder().encode(payload);
}

function toHex(data: Uint8Array): string {
  return Buffer.from(data).toString("hex");
}

function equalBytes(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) {
    return false;
  }
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) {
      return false;
    }
  }
  return true;
}

function sortObject(value: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(value).sort()) {
    const entry = value[key];
    if (entry && typeof entry === "object" && !Array.isArray(entry)) {
      out[key] = sortObject(entry as Record<string, unknown>);
    } else {
      out[key] = entry;
    }
  }
  return out;
}

function toUint8Digest(digest: Uint8Array | string): Uint8Array {
  if (typeof digest === "string") {
    return Uint8Array.from(Buffer.from(digest, "hex"));
  }
  return digest;
}
