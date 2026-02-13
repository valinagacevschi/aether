import WebSocket from "ws";

import { EventFilter, matchEvent, normalizeFilter } from "./filters";
import { NoiseSession, deriveSharedKey, generateKeypair } from "./noise";
import { decodeMessage, encodeMessage } from "./wire";

export type AetherEvent = Record<string, unknown>;
export type PublishResult = Record<string, boolean>;
export type EventHandler = (event: AetherEvent) => void;

type ConnectionState = {
  url: string;
  socket: WebSocket | null;
  subscriptions: Map<string, EventFilter>;
  reconnectAttempts: number;
  format: "json" | "flatbuffers";
  noise: NoiseSession | null;
  noisePriv: Uint8Array | null;
};

export class AetherClient {
  private readonly maxConnections: number;
  private readonly connections = new Map<string, ConnectionState>();
  private readonly eventHandlers: EventHandler[] = [];
  private readonly sessionTickets = new Map<string, string>();

  constructor({ maxConnections = 3 }: { maxConnections?: number } = {}) {
    this.maxConnections = maxConnections;
  }

  async connect(urls: string[]): Promise<void> {
    for (const url of urls.slice(0, this.maxConnections)) {
      const state: ConnectionState = {
        url,
        socket: null,
        subscriptions: new Map(),
        reconnectAttempts: 0,
        format: "json",
        noise: null,
        noisePriv: null,
      };
      this.connections.set(url, state);
      await this.connectOne(state);
    }
  }

  async publish(event: AetherEvent): Promise<PublishResult> {
    const results: PublishResult = {};
    for (const [url, state] of this.connections.entries()) {
      if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
        results[url] = false;
        continue;
      }
      try {
        await this.send(state, { type: "publish", event });
        results[url] = true;
      } catch {
        results[url] = false;
      }
    }
    return results;
  }

  async subscribe(subscriptionId: string, rawFilter: Record<string, unknown>): Promise<void> {
    const flt = normalizeFilter(rawFilter);
    for (const state of this.connections.values()) {
      if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
        continue;
      }
      state.subscriptions.set(subscriptionId, flt);
      await this.send(state, { type: "subscribe", sub_id: subscriptionId, filters: [rawFilter] });
    }
  }

  async unsubscribe(subscriptionId: string): Promise<void> {
    for (const state of this.connections.values()) {
      if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
        continue;
      }
      state.subscriptions.delete(subscriptionId);
      await this.send(state, { type: "unsubscribe", sub_id: subscriptionId });
    }
  }

  onEvent(handler: EventHandler): void {
    this.eventHandlers.push(handler);
  }

  private async connectOne(state: ConnectionState): Promise<void> {
    const headers: Record<string, string> = {};
    const ticket = this.sessionTickets.get(state.url);
    if (ticket) {
      headers["x-session-ticket"] = ticket;
    }
    const socket = new WebSocket(state.url, { headers });
    state.socket = socket;

    socket.on("open", () => {
      const ticket = headers["x-session-ticket"];
      if (ticket) {
        this.sessionTickets.set(state.url, ticket);
      }
      void this.sendHello(state);
    });
    socket.on("close", () => {
      if (state.socket === socket) {
        state.socket = null;
      }
      void this.scheduleReconnect(state);
    });
    socket.on("message", (data) => this.handleMessage(state, data));
    socket.on("error", () => void this.scheduleReconnect(state));
  }

  private async sendHello(state: ConnectionState): Promise<void> {
    if (!state.socket) {
      return;
    }
    const { privateKey, publicKey } = generateKeypair();
    state.noisePriv = privateKey;
    const hello = {
      type: "hello",
      version: 1,
      formats: ["flatbuffers", "json"],
      noise: { required: true, pubkey: Buffer.from(publicKey).toString("hex") },
    };
    state.socket.send(JSON.stringify(hello));
  }

  private async scheduleReconnect(state: ConnectionState): Promise<void> {
    state.reconnectAttempts += 1;
    const delay = Math.min(60000, 2 ** state.reconnectAttempts * 1000);
    await new Promise((resolve) => setTimeout(resolve, delay));
    await this.connectOne(state);
  }

  private handleMessage(state: ConnectionState, data: WebSocket.RawData): void {
    if (typeof data === "string") {
      this.handleDecoded(state, decodeMessage(data, "json"));
      return;
    }
    const bytes = data instanceof Buffer ? new Uint8Array(data) : new Uint8Array(data as ArrayBuffer);
    const decoded = decodeMessage(bytes, state.format);
    this.handleDecoded(state, decoded);
  }

  private handleDecoded(state: ConnectionState, decoded: { msgType: string; payload: Record<string, unknown> }): void {
    if (decoded.msgType === "welcome") {
      const fmt = decoded.payload.format;
      if (fmt === "flatbuffers" || fmt === "json") {
        state.format = fmt;
      }
      const noiseInfo = decoded.payload.noise;
      if (noiseInfo && typeof noiseInfo === "object") {
        const required = (noiseInfo as { required?: boolean }).required;
        const pubkey = (noiseInfo as { pubkey?: string }).pubkey;
        if (required && typeof pubkey === "string" && state.noisePriv) {
          const shared = deriveSharedKey(state.noisePriv, Buffer.from(pubkey, "hex"));
          state.noise = new NoiseSession(shared);
        }
      }
      return;
    }

    if (state.noise) {
      if (decoded.msgType !== "noise") {
        return;
      }
      const payloadHex = decoded.payload.payload_hex;
      if (typeof payloadHex !== "string") {
        return;
      }
      const inner = state.noise.decrypt(Buffer.from(payloadHex, "hex"));
      decoded = decodeMessage(inner, state.format);
    }

    if (decoded.msgType !== "event") {
      return;
    }
    const event = decoded.payload.event as AetherEvent | undefined;
    if (!event) {
      return;
    }
    for (const flt of state.subscriptions.values()) {
      if (matchEvent(event, flt)) {
        for (const handler of this.eventHandlers) {
          handler(event);
        }
        break;
      }
    }
  }

  private async send(state: ConnectionState, payload: Record<string, unknown>): Promise<void> {
    if (!state.socket) {
      return;
    }
    let data = encodeMessage(payload, state.format);
    if (state.noise) {
      const encrypted = state.noise.encrypt(data);
      data = encodeMessage({ type: "noise", payload_hex: Buffer.from(encrypted).toString("hex") }, state.format);
    }
    if (state.format === "json") {
      state.socket.send(Buffer.from(data).toString("utf8"));
    } else {
      state.socket.send(Buffer.from(data));
    }
  }
}
