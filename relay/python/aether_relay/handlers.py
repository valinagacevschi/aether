"""Message handlers for relay transports."""

from __future__ import annotations

from typing import Awaitable, Callable, Mapping

from .core import RelayCore

SendFn = Callable[[str, Mapping[str, object]], Awaitable[None]]


async def handle_message(core: RelayCore, connection_id: str, message: Mapping[str, object], send: SendFn) -> None:
    msg_type = message.get("type")
    if msg_type == "publish":
        event = message.get("event")
        if not isinstance(event, dict):
            raise ValueError("publish event must be mapping")
        buffered_events: list[Mapping[str, object]] = []

        async def send_with_buffer(conn_id: str, payload: Mapping[str, object]) -> None:
            if conn_id == connection_id and payload.get("type") == "event":
                buffered_events.append(payload)
                return
            await send(conn_id, payload)

        await core.publish(connection_id, event, send_with_buffer)
        await send(connection_id, {"type": "ack"})
        for payload in buffered_events:
            await send(connection_id, payload)
        return
    if msg_type == "subscribe":
        sub_id = message.get("sub_id")
        filters = message.get("filters", [])
        if not isinstance(sub_id, str):
            raise ValueError("subscribe requires sub_id")
        if not isinstance(filters, list):
            raise ValueError("filters must be list")
        core.subscribe(connection_id, sub_id, filters)
        await send(connection_id, {"type": "subscribed", "sub_id": sub_id})
        return
    if msg_type == "unsubscribe":
        sub_id = message.get("sub_id")
        if not isinstance(sub_id, str):
            raise ValueError("unsubscribe requires sub_id")
        core.unsubscribe(connection_id, sub_id)
        await send(connection_id, {"type": "unsubscribed", "sub_id": sub_id})
        return
    raise ValueError("unknown message type")
