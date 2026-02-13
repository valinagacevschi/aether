import { Builder, ByteBuffer } from "flatbuffers";

export type WireFormat = "json" | "flatbuffers";

export enum MessageType {
  HELLO = 0,
  WELCOME = 1,
  PUBLISH = 2,
  SUBSCRIBE = 3,
  UNSUBSCRIBE = 4,
  EVENT = 5,
  ACK = 6,
  ERROR = 7,
  NOISE = 8,
}

const TYPE_TO_NAME: Record<number, string> = {
  [MessageType.HELLO]: "hello",
  [MessageType.WELCOME]: "welcome",
  [MessageType.PUBLISH]: "publish",
  [MessageType.SUBSCRIBE]: "subscribe",
  [MessageType.UNSUBSCRIBE]: "unsubscribe",
  [MessageType.EVENT]: "event",
  [MessageType.ACK]: "ack",
  [MessageType.ERROR]: "error",
  [MessageType.NOISE]: "noise",
};

const NAME_TO_TYPE: Record<string, number> = Object.fromEntries(
  Object.entries(TYPE_TO_NAME).map(([key, value]) => [value, Number(key)])
);

export type DecodedMessage = {
  msgType: string;
  payload: Record<string, unknown>;
};

export function encodeMessage(payload: Record<string, unknown>, fmt: WireFormat): Uint8Array {
  if (fmt === "json") {
    return new TextEncoder().encode(JSON.stringify(payload));
  }
  return encodeFlatbuffers(payload);
}

export function decodeMessage(raw: Uint8Array | string, fmt: WireFormat): DecodedMessage {
  if (fmt === "json") {
    const text = typeof raw === "string" ? raw : new TextDecoder().decode(raw);
    return decodeJson(text);
  }
  const bytes = typeof raw === "string" ? new TextEncoder().encode(raw) : raw;
  return decodeFlatbuffers(bytes);
}

function decodeJson(text: string): DecodedMessage {
  const payload = JSON.parse(text) as Record<string, unknown>;
  const msgType = payload.type;
  if (typeof msgType !== "string") {
    throw new Error("message type missing");
  }
  return { msgType, payload };
}

function encodeFlatbuffers(payload: Record<string, unknown>): Uint8Array {
  const msgType = payload.type;
  if (typeof msgType !== "string") {
    throw new Error("message type missing");
  }
  const msgTypeId = NAME_TO_TYPE[msgType];
  if (msgTypeId === undefined) {
    throw new Error("unknown message type");
  }
  const body = new TextEncoder().encode(JSON.stringify(payload));
  const builder = new Builder(body.length + 64);
  const payloadVec = builder.createByteVector(body);
  builder.startObject(2);
  builder.addFieldInt8(0, msgTypeId, 0);
  builder.addFieldOffset(1, payloadVec, 0);
  const msg = builder.endObject();
  builder.finish(msg);
  return builder.asUint8Array();
}

function decodeFlatbuffers(raw: Uint8Array): DecodedMessage {
  const bb = new ByteBuffer(raw);
  const table = bb.readInt32(bb.position()) + bb.position();
  const msgTypeOffset = fieldOffset(bb, table, 4);
  if (!msgTypeOffset) {
    throw new Error("message type missing");
  }
  const msgTypeId = bb.readInt8(table + msgTypeOffset);
  const payloadOffset = fieldOffset(bb, table, 6);
  let payloadBytes = new Uint8Array();
  if (payloadOffset) {
    const vec = table + payloadOffset;
    const vecStart = vec + bb.readInt32(vec);
    const length = bb.readInt32(vecStart);
    payloadBytes = raw.slice(vecStart + 4, vecStart + 4 + length);
  }
  const msgType = TYPE_TO_NAME[msgTypeId];
  if (!msgType) {
    throw new Error("unknown message type");
  }
  const payloadRaw = payloadBytes.length ? payloadBytes : new TextEncoder().encode("{}");
  const payload = JSON.parse(new TextDecoder().decode(payloadRaw)) as Record<string, unknown>;
  return { msgType, payload };
}

function fieldOffset(bb: ByteBuffer, table: number, vtableOffset: number): number {
  const vtable = table - bb.readInt32(table);
  const vtableLength = bb.readInt16(vtable);
  if (vtableOffset < vtableLength) {
    return bb.readInt16(vtable + vtableOffset);
  }
  return 0;
}
