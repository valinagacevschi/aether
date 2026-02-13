export class GCounter {
  private counts = new Map<string, number>();

  add(amount: number, replicaId: string): void {
    if (amount < 0) {
      throw new Error("amount must be non-negative");
    }
    const value = this.counts.get(replicaId) ?? 0;
    this.counts.set(replicaId, value + amount);
  }

  update(other: GCounter): void {
    for (const [replicaId, value] of other.counts.entries()) {
      const current = this.counts.get(replicaId) ?? 0;
      if (value > current) {
        this.counts.set(replicaId, value);
      }
    }
  }

  remove(amount: number, _replicaId: string): void {
    if (amount !== 0) {
      throw new Error("G-Counter does not support decrements");
    }
  }

  get value(): number {
    let total = 0;
    for (const value of this.counts.values()) {
      total += value;
    }
    return total;
  }
}

export class PNCounter {
  private positive = new GCounter();
  private negative = new GCounter();

  add(amount: number, replicaId: string): void {
    this.positive.add(amount, replicaId);
  }

  remove(amount: number, replicaId: string): void {
    this.negative.add(amount, replicaId);
  }

  update(other: PNCounter): void {
    this.positive.update(other.positive);
    this.negative.update(other.negative);
  }

  get value(): number {
    return this.positive.value - this.negative.value;
  }
}

export class LWWRegister<T> {
  value: T | null = null;
  timestamp = 0;
  replicaId = "";
  tombstone = false;

  update(value: T, timestamp: number, replicaId: string): void {
    if (timestamp > this.timestamp || (timestamp === this.timestamp && replicaId >= this.replicaId)) {
      this.value = value;
      this.timestamp = timestamp;
      this.replicaId = replicaId;
      this.tombstone = false;
    }
  }

  remove(timestamp: number, replicaId: string): void {
    if (timestamp > this.timestamp || (timestamp === this.timestamp && replicaId >= this.replicaId)) {
      this.value = null;
      this.timestamp = timestamp;
      this.replicaId = replicaId;
      this.tombstone = true;
    }
  }

  add(value: T, timestamp: number, replicaId: string): void {
    this.update(value, timestamp, replicaId);
  }
}

export class ORSet<T> {
  private adds = new Map<T, Set<string>>();
  private removes = new Map<T, Set<string>>();

  add(value: T, tag: string): void {
    const tags = this.adds.get(value) ?? new Set<string>();
    tags.add(tag);
    this.adds.set(value, tags);
  }

  remove(value: T, tags: Iterable<string>): void {
    const removed = this.removes.get(value) ?? new Set<string>();
    for (const tag of tags) {
      removed.add(tag);
    }
    this.removes.set(value, removed);
  }

  update(other: ORSet<T>): void {
    for (const [value, tags] of other.adds.entries()) {
      const existing = this.adds.get(value) ?? new Set<string>();
      for (const tag of tags) {
        existing.add(tag);
      }
      this.adds.set(value, existing);
    }
    for (const [value, tags] of other.removes.entries()) {
      const existing = this.removes.get(value) ?? new Set<string>();
      for (const tag of tags) {
        existing.add(tag);
      }
      this.removes.set(value, existing);
    }
  }

  elements(): Set<T> {
    const visible = new Set<T>();
    for (const [value, tags] of this.adds.entries()) {
      const removed = this.removes.get(value) ?? new Set<string>();
      let present = false;
      for (const tag of tags) {
        if (!removed.has(tag)) {
          present = true;
          break;
        }
      }
      if (present) {
        visible.add(value);
      }
    }
    return visible;
  }
}
