import { chacha20poly1305 } from "@noble/ciphers/chacha";
import { hkdf } from "@noble/hashes/hkdf";
import { sha256 } from "@noble/hashes/sha256";
import { x25519 } from "@noble/curves/ed25519";

export function generateKeypair(): { privateKey: Uint8Array; publicKey: Uint8Array } {
  const privateKey = x25519.utils.randomPrivateKey();
  const publicKey = x25519.getPublicKey(privateKey);
  return { privateKey, publicKey };
}

export function deriveSharedKey(privateKey: Uint8Array, peerPublicKey: Uint8Array): Uint8Array {
  const shared = x25519.getSharedSecret(privateKey, peerPublicKey);
  return hkdf(sha256, shared, undefined, "aether-noise", 32);
}

export class NoiseSession {
  private key: Uint8Array;
  private sendCounter = 0;

  constructor(key: Uint8Array) {
    this.key = key;
  }

  encrypt(plaintext: Uint8Array): Uint8Array {
    const nonce = this.nonce(this.sendCounter);
    const cipher = chacha20poly1305(this.key, nonce);
    const ciphertext = cipher.encrypt(plaintext);
    const counter = this.counterPrefix(this.sendCounter);
    this.sendCounter += 1;
    const out = new Uint8Array(counter.length + ciphertext.length);
    out.set(counter, 0);
    out.set(ciphertext, counter.length);
    return out;
  }

  decrypt(payload: Uint8Array): Uint8Array {
    if (payload.length < 8) {
      throw new Error("noise payload too short");
    }
    const counter = bytesToNumber(payload.slice(0, 8));
    const nonce = this.nonce(counter);
    const cipher = chacha20poly1305(this.key, nonce);
    return cipher.decrypt(payload.slice(8));
  }

  private nonce(counter: number): Uint8Array {
    const nonce = new Uint8Array(12);
    nonce.set(numberToBytes(counter), 4);
    return nonce;
  }

  private counterPrefix(counter: number): Uint8Array {
    return numberToBytes(counter);
  }
}

function numberToBytes(value: number): Uint8Array {
  const out = new Uint8Array(8);
  let v = BigInt(value);
  for (let i = 7; i >= 0; i -= 1) {
    out[i] = Number(v & 0xffn);
    v >>= 8n;
  }
  return out;
}

function bytesToNumber(bytes: Uint8Array): number {
  let v = 0n;
  for (const b of bytes) {
    v = (v << 8n) + BigInt(b);
  }
  return Number(v);
}
