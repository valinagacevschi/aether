from __future__ import annotations

import pytest

from aether.capabilities import sign_token, verify_chain
from aether.crypto import generate_keypair


def test_verify_chain_passes() -> None:
    issuer_priv, issuer_pub = generate_keypair()
    subject_priv, subject_pub = generate_keypair()
    token1 = sign_token(
        issuer_private_key=issuer_priv,
        subject=subject_pub,
        capability="service:resource:read",
        caveats={"not_before": 0},
    )
    token2 = sign_token(
        issuer_private_key=subject_priv,
        subject=issuer_pub,
        capability="service:resource:read",
        caveats={"not_before": 0},
    )
    verify_chain([token1, token2], now_ns=1)


def test_verify_chain_rejects_expired() -> None:
    issuer_priv, issuer_pub = generate_keypair()
    token1 = sign_token(
        issuer_private_key=issuer_priv,
        subject=issuer_pub,
        capability="service:resource:read",
        caveats={"not_after": 5},
    )
    with pytest.raises(ValueError, match="expired"):
        verify_chain([token1], now_ns=10)


def test_verify_chain_rejects_subject_mismatch() -> None:
    issuer_priv, issuer_pub = generate_keypair()
    other_priv, other_pub = generate_keypair()
    token1 = sign_token(
        issuer_private_key=issuer_priv,
        subject=issuer_pub,
        capability="service:resource:read",
        caveats={},
    )
    token2 = sign_token(
        issuer_private_key=other_priv,
        subject=other_pub,
        capability="service:resource:read",
        caveats={},
    )
    with pytest.raises(ValueError, match="subject mismatch"):
        verify_chain([token1, token2], now_ns=1)
