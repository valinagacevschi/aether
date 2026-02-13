export type EventFilter = {
  kinds?: Set<number>;
  pubkeyPrefixes?: Uint8Array[];
  tags?: Set<string>;
  since?: number;
  until?: number;
};

export function normalizeFilter(raw: Record<string, unknown>): EventFilter {
  const kinds = normalizeKinds(raw.kinds);
  const pubkeyPrefixes = normalizePubkeyPrefixes(raw.pubkey_prefixes);
  const tags = normalizeTags(raw.tags);
  const since = normalizeInt(raw.since);
  const until = normalizeInt(raw.until);
  return { kinds, pubkeyPrefixes, tags, since, until };
}

export function matchEvent(event: Record<string, unknown>, filter: EventFilter): boolean {
  const kind = parseIntField(event.kind, "kind");
  const createdAt = parseIntField(event.created_at, "created_at");
  const pubkey = parseHexOrBytes(event.pubkey, "pubkey", 32);
  const tags = parseTags(event.tags);

  if (filter.kinds && !filter.kinds.has(kind)) {
    return false;
  }
  if (filter.pubkeyPrefixes && !filter.pubkeyPrefixes.some((prefix) => startsWith(pubkey, prefix))) {
    return false;
  }
  if (filter.tags && !hasTags(tags, filter.tags)) {
    return false;
  }
  if (filter.since !== undefined && createdAt < filter.since) {
    return false;
  }
  if (filter.until !== undefined && createdAt > filter.until) {
    return false;
  }
  return true;
}

type Tag = { key: string; values: string[] };

function normalizeKinds(raw: unknown): Set<number> | undefined {
  if (raw === undefined || raw === null) {
    return undefined;
  }
  if (!Array.isArray(raw)) {
    throw new Error("kinds must be array");
  }
  return new Set(raw.map((value) => parseIntField(value, "kind")));
}

function normalizePubkeyPrefixes(raw: unknown): Uint8Array[] | undefined {
  if (raw === undefined || raw === null) {
    return undefined;
  }
  if (!Array.isArray(raw)) {
    throw new Error("pubkey_prefixes must be array");
  }
  return raw.map((value) => parseHexOrBytes(value, "pubkey_prefix", 16));
}

function normalizeTags(raw: unknown): Set<string> | undefined {
  if (raw === undefined || raw === null) {
    return undefined;
  }
  const tags = new Set<string>();
  if (Array.isArray(raw)) {
    for (const entry of raw) {
      if (!Array.isArray(entry) || entry.length !== 2) {
        throw new Error("tag filter entries must be [key, value]");
      }
      tags.add(`${String(entry[0])}:${String(entry[1])}`);
    }
    return tags;
  }
  if (typeof raw === "object") {
    for (const [key, values] of Object.entries(raw as Record<string, unknown>)) {
      if (!Array.isArray(values)) {
        throw new Error("tag values must be array");
      }
      for (const value of values) {
        tags.add(`${key}:${String(value)}`);
      }
    }
    return tags;
  }
  throw new Error("tags must be array or object");
}

function parseHexOrBytes(value: unknown, field: string, size: number): Uint8Array {
  if (value instanceof Uint8Array) {
    if (value.length !== size) {
      throw new Error(`${field} must be ${size} bytes`);
    }
    return value;
  }
  if (typeof value === "string") {
    const bytes = Uint8Array.from(Buffer.from(value, "hex"));
    if (bytes.length !== size) {
      throw new Error(`${field} must be ${size} bytes`);
    }
    return bytes;
  }
  throw new Error(`${field} must be hex string or bytes`);
}

function parseIntField(value: unknown, field: string): number {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number(value);
    if (Number.isNaN(parsed)) {
      throw new Error(`${field} must be int`);
    }
    return parsed;
  }
  throw new Error(`${field} must be int`);
}

function parseTags(value: unknown): Tag[] {
  if (value === undefined || value === null) {
    return [];
  }
  if (!Array.isArray(value)) {
    throw new Error("tags must be array");
  }
  return value.map((entry) => {
    if (!Array.isArray(entry) || entry.length === 0) {
      throw new Error("invalid tag entry");
    }
    const [key, ...values] = entry;
    return { key: String(key), values: values.map((v) => String(v)) };
  });
}

function hasTags(tags: Tag[], required: Set<string>): boolean {
  const available = new Set<string>();
  for (const tag of tags) {
    for (const value of tag.values) {
      available.add(`${tag.key}:${value}`);
    }
  }
  for (const entry of required) {
    if (!available.has(entry)) {
      return false;
    }
  }
  return true;
}

function startsWith(value: Uint8Array, prefix: Uint8Array): boolean {
  if (prefix.length > value.length) {
    return false;
  }
  for (let i = 0; i < prefix.length; i += 1) {
    if (value[i] !== prefix[i]) {
      return false;
    }
  }
  return true;
}
