# Aether Python SDK

Python client for the Aether protocol (relay pub/sub, crypto helpers, CRDTs).

## Install

```
git clone https://github.com/valinagacevschi/aether
cd aether/sdk/python
pip install -e .
```

Or from PyPI (when available):

```
pip install aether-protocol
```

## Quickstart

```python
import asyncio
from aether.client import Client

async def main() -> None:
    client = Client()
    await client.connect(["ws://localhost:8080"])
    await client.publish({"kind": 1, "content": "hello"})

asyncio.run(main())
```
