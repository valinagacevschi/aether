import WebSocket from "ws";

import { EventFilter, matchEvent, normalizeFilter } from "./filters";

export type AetherEvent = Record<string, unknown>;
export type PublishResult = Record<string, boolean>;
export type EventHandler = (event: AetherEvent) => void;

type ConnectionState = {
  url: string;
  socket: WebSocket | null;
  subscriptions: Map<string, EventFilter>;
  reconnectAttempts: number;
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
        state.socket.send(JSON.stringify({ type: "publish", event }));
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
      state.socket.send(
        JSON.stringify({ type: "subscribe", sub_id: subscriptionId, filters: [rawFilter] })
      );
    }
  }

  async unsubscribe(subscriptionId: string): Promise<void> {
    for (const state of this.connections.values()) {
      if (!state.socket || state.socket.readyState !== WebSocket.OPEN) {
        continue;
      }
      state.subscriptions.delete(subscriptionId);
      state.socket.send(JSON.stringify({ type: "unsubscribe", sub_id: subscriptionId }));
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
    });
    socket.on("close", () => {
      if (state.socket === socket) {
        state.socket = null;
      }
      void this.scheduleReconnect(state);
    });
    socket.on("message", (data) => this.handleMessage(state, data.toString()));
    socket.on("error", () => void this.scheduleReconnect(state));
  }

  private async scheduleReconnect(state: ConnectionState): Promise<void> {
    state.reconnectAttempts += 1;
    const delay = Math.min(60000, 2 ** state.reconnectAttempts * 1000);
    await new Promise((resolve) => setTimeout(resolve, delay));
    await this.connectOne(state);
  }

  private handleMessage(state: ConnectionState, raw: string): void {
    const message = JSON.parse(raw) as { type?: string; event?: AetherEvent };
    if (message.type !== "event" || !message.event) {
      return;
    }
    for (const flt of state.subscriptions.values()) {
      if (matchEvent(message.event, flt)) {
        for (const handler of this.eventHandlers) {
          handler(message.event);
        }
        break;
      }
    }
  }
}
