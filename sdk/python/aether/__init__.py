"""Aether Python SDK."""

from .client import Client
from .crypto import Tag, compute_event_id, generate_keypair, normalize_tags, sign, verify
from .tools import Tool, dispatch_tool_call, dispatch_tool_call_sync, to_anthropic_tool, to_generic_tool, to_openai_tool

__all__ = [
    "Client",
    "Tag",
    "compute_event_id",
    "generate_keypair",
    "normalize_tags",
    "sign",
    "verify",
    "Tool",
    "dispatch_tool_call",
    "dispatch_tool_call_sync",
    "to_anthropic_tool",
    "to_generic_tool",
    "to_openai_tool",
    "__version__",
]

__version__ = "0.1.0"
