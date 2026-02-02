"""Proof-of-work helpers for relay validation."""

from __future__ import annotations


def leading_zero_bits(data: bytes) -> int:
    count = 0
    for byte in data:
        if byte == 0:
            count += 8
            continue
        for bit in range(7, -1, -1):
            if byte & (1 << bit):
                return count
            count += 1
    return count


def meets_difficulty(event_id: bytes, difficulty: int) -> bool:
    if difficulty <= 0:
        return True
    return leading_zero_bits(event_id) >= difficulty


def validate_pow(event_id: bytes, difficulty: int) -> None:
    if difficulty <= 0:
        return
    if not meets_difficulty(event_id, difficulty):
        raise ValueError("pow difficulty not met")
