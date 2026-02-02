import { bech32 } from "bech32";

export const BECH32_PRIV_PREFIX = "nsec";
export const BECH32_PUB_PREFIX = "npub";

export function encodeHex(data: Uint8Array): string {
  return Buffer.from(data).toString("hex");
}

export function decodeHex(value: string): Uint8Array {
  return Uint8Array.from(Buffer.from(value, "hex"));
}

export function encodeBech32(data: Uint8Array, prefix: string): string {
  const words = bech32.toWords(Buffer.from(data));
  return bech32.encode(prefix, words);
}

export function decodeBech32(value: string): { prefix: string; data: Uint8Array } {
  const { prefix, words } = bech32.decode(value);
  return { prefix, data: Uint8Array.from(bech32.fromWords(words)) };
}

export function encodePrivateBech32(data: Uint8Array): string {
  return encodeBech32(data, BECH32_PRIV_PREFIX);
}

export function encodePublicBech32(data: Uint8Array): string {
  return encodeBech32(data, BECH32_PUB_PREFIX);
}

export function decodePrivateBech32(value: string): Uint8Array {
  const decoded = decodeBech32(value);
  if (decoded.prefix !== BECH32_PRIV_PREFIX) {
    throw new Error("invalid bech32 private key prefix");
  }
  return decoded.data;
}

export function decodePublicBech32(value: string): Uint8Array {
  const decoded = decodeBech32(value);
  if (decoded.prefix !== BECH32_PUB_PREFIX) {
    throw new Error("invalid bech32 public key prefix");
  }
  return decoded.data;
}
