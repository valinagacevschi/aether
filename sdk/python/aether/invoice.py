"""Invoice attachment helpers for kind 10002."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class InvoiceAttachment:
    invoice: str
    memo: str | None = None
    amount_msat: int | None = None


def serialize_attachment(attachment: InvoiceAttachment) -> dict[str, object]:
    payload: dict[str, object] = {"invoice": attachment.invoice}
    if attachment.memo is not None:
        payload["memo"] = attachment.memo
    if attachment.amount_msat is not None:
        payload["amount_msat"] = attachment.amount_msat
    return payload


def parse_attachment(payload: Mapping[str, object]) -> InvoiceAttachment:
    invoice = payload.get("invoice")
    if not isinstance(invoice, str) or not invoice:
        raise ValueError("invoice is required")
    memo = payload.get("memo")
    amount_msat = payload.get("amount_msat")
    if memo is not None and not isinstance(memo, str):
        raise ValueError("memo must be str")
    if amount_msat is not None and not isinstance(amount_msat, int):
        raise ValueError("amount_msat must be int")
    return InvoiceAttachment(invoice=invoice, memo=memo, amount_msat=amount_msat)
