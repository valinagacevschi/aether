export type InvoiceAttachment = {
  invoice: string;
  memo?: string;
  amount_msat?: number;
};

export function serializeAttachment(attachment: InvoiceAttachment): Record<string, unknown> {
  const payload: Record<string, unknown> = { invoice: attachment.invoice };
  if (attachment.memo) {
    payload.memo = attachment.memo;
  }
  if (attachment.amount_msat !== undefined) {
    payload.amount_msat = attachment.amount_msat;
  }
  return payload;
}

export function parseAttachment(payload: Record<string, unknown>): InvoiceAttachment {
  const invoice = payload.invoice;
  if (typeof invoice !== "string" || invoice.length === 0) {
    throw new Error("invoice is required");
  }
  const memo = payload.memo;
  if (memo !== undefined && typeof memo !== "string") {
    throw new Error("memo must be string");
  }
  const amount = payload.amount_msat;
  if (amount !== undefined && typeof amount !== "number") {
    throw new Error("amount_msat must be number");
  }
  return { invoice, memo, amount_msat: amount };
}
