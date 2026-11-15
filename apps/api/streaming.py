"""Server-Sent Events bridge: LangGraph's "updates" stream, node by node, to the browser.

The graph runs in a background task (apps/api/runtime.py) and appends one event per finished node.
This generator replays what the client has not seen (`after`) and then waits for new events, so
opening the stream late, or again after a page refresh, never loses a step.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from apps.api.runtime import Run


async def run_events(run: Run, after: int = 0) -> AsyncIterator[str]:
    sent = after
    while True:
        async with run.changed:
            if len(run.events) <= sent and run.running:
                try:
                    await asyncio.wait_for(run.changed.wait(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
            new = run.events[sent:]
        for e in new:
            yield f"id: {e['seq']}\nevent: step\ndata: {json.dumps(e)}\n\n"
        sent += len(new)
        if not run.running and len(run.events) <= sent:
            return
