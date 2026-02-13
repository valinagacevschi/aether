from __future__ import annotations

import pytest

from aether_relay.capabilities import CapabilityToken, enforce_capability, sign_token, verify_chain
from aether_relay.crypto import generate_keypair


def test_verify_chain_passes() -> None:
    issuer_priv, issuer_pub = generate_keypair()
    subject_priv, subject_pub = generate_keypair()
    final_priv, final_pub = generate_keypair()
    token1 = sign_token(
        issuer_private_key=issuer_priv,
        subject=subject_pub,
        capability="service:resource:read",
        caveats={"not_before": 0},
    )
    token2 = sign_token(
        issuer_private_key=subject_priv,
        subject=final_pub,
        capability="service:resource:read",
        caveats={"not_before": 0},
    )

    verify_chain([token1, token2], now_ns=1)


def test_sign_token_sets_issuer_public_key() -> None:
    issuer_priv, issuer_pub = generate_keypair()
    token = sign_token(
        issuer_private_key=issuer_priv,
        subject=issuer_pub,
        capability="service:resource:read",
        caveats={},
    )
    assert token.issuer == issuer_pub


def test_verify_chain_rejects_expired() -> None:
    issuer_priv, issuer_pub = generate_keypair()
    subject_priv, subject_pub = generate_keypair()
    token1 = sign_token(
        issuer_private_key=issuer_priv,
        subject=subject_pub,
        capability="service:resource:read",
        caveats={"not_after": 5},
    )
    with pytest.raises(ValueError, match="expired"):
        verify_chain([token1], now_ns=10)


def test_verify_chain_rejects_usage_limit() -> None:
    issuer_priv, issuer_pub = generate_keypair()
    token = sign_token(
        issuer_private_key=issuer_priv,
        subject=issuer_pub,
        capability="service:resource:read",
        caveats={"max_uses": 1},
    )
    usage = {token_id(token): 1}
    with pytest.raises(ValueError, match="usage exceeded"):
        verify_chain([token], now_ns=1, usage=usage)


def test_enforce_capability_rejects_wrong_capability() -> None:
    issuer_priv, issuer_pub = generate_keypair()
    token = sign_token(
        issuer_private_key=issuer_priv,
        subject=issuer_pub,
        capability="service:resource:read",
        caveats={},
    )
    with pytest.raises(ValueError, match="capability not granted"):
        enforce_capability([token], required="service:resource:write", now_ns=1)


def token_id(token: CapabilityToken) -> bytes:
    from aether_relay.capabilities import compute_token_id

    return compute_token_id(token)
