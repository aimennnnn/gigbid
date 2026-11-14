"""Shared plumbing for every node: dependencies, and one wrapper that gives each node
a timeout, error capture and step counting (C7)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore

from agent.llm import LLMError, timeout_scale
from agent.mcp_client import ToolBox, ToolRejected, ToolUnavailable
from agent.settings import get_settings


@dataclass
class Deps:
    toolbox: ToolBox
    store: BaseStore


def ids(state: dict, config: dict) -> dict:
    """user and trace id for tool calls: the same trace id goes to every MCP server."""
    c = config.get("configurable", {})
    return {"user": state.get("user_id", "local"), "trace_id": c.get("trace_id") or c.get("thread_id", "")}


def node(name: str, fn, deps: Deps, critical: bool = False):
    """Wrap a node function. A failure never crashes the graph: it is written into state.
    If the node is critical (the job cannot continue without it) the job is dead-lettered."""
    timeout = get_settings()["nodes"].get(name, {}).get("timeout_s", 30) * 4 * timeout_scale()

    async def wrapped(state: dict, config: RunnableConfig) -> dict:
        try:
            out = await asyncio.wait_for(fn(deps, state, config), timeout) or {}
        except ToolUnavailable as e:
            out = {"errors": [f"{name}: {e}"]} | ({"status": "dead_letter"} if critical else {})
        except (ToolRejected, LLMError, asyncio.TimeoutError, PermissionError, ValueError) as e:
            out = {"errors": [f"{name}: {type(e).__name__}: {e}"]} | ({"status": "dead_letter"} if critical else {})
        return out | {"steps_used": 1}
    wrapped.__name__ = name
    return wrapped
