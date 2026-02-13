"""Aether relay package."""

from aether_relay.crypto import (
    Tag,
    compute_event_id,
    generate_keypair,
    normalize_tags,
    sign,
    verify,
)

__all__ = [
    "Tag",
    "compute_event_id",
    "generate_keypair",
    "normalize_tags",
    "sign",
    "verify",
    "__version__",
]
__version__ = "0.1.0"
