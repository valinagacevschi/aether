export type AetherEvent = Record<string, unknown>;

export class AetherClient {
  private url: string | null = null;

  async connect(url: string): Promise<void> {
    this.url = url;
  }

  async publish(event: AetherEvent): Promise<void> {
    if (!this.url) {
      throw new Error("Client not connected");
    }

    void event;
  }
}
