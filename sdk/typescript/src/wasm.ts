export type WasmCrypto = {
  blake3: (data: Uint8Array) => Uint8Array;
  sign: (data: Uint8Array, privateKey: Uint8Array) => Promise<Uint8Array>;
  verify: (signature: Uint8Array, data: Uint8Array, publicKey: Uint8Array) => Promise<boolean>;
};

let wasmImpl: WasmCrypto | null = null;

export function registerWasm(impl: WasmCrypto): void {
  wasmImpl = impl;
}

export function getWasm(): WasmCrypto | null {
  return wasmImpl;
}
