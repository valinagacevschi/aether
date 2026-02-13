from __future__ import annotations

import pytest

from aether_relay.pow import leading_zero_bits, meets_difficulty, validate_pow


def test_leading_zero_bits() -> None:
    assert leading_zero_bits(b"\x00") == 8
    assert leading_zero_bits(b"\x00\x00") == 16
    assert leading_zero_bits(b"\x10") == 3


def test_meets_difficulty() -> None:
    assert meets_difficulty(b"\x00\x00", 12) is True
    assert meets_difficulty(b"\x10", 4) is False


def test_validate_pow() -> None:
    validate_pow(b"\x00\x00", 8)
    with pytest.raises(ValueError, match="pow difficulty"):
        validate_pow(b"\x10", 4)
