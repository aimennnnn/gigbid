"""One GigBid system for the API process: GigSim, the three MCP servers and both graphs.

The API never runs a graph inside a web request. A request starts a run as a background task and
returns its thread id; the run's node-by-node progress is kept here and streamed to the browser
(apps/api/streaming.py). A paused run (waiting for approval) lives in the LangGraph checkpointer,
so a page refresh, or another browser, finds the same pending approval.

State is kept on disk in SQLite files under data/processed/app/ (set GIGBID_PERSIST=0 for memory only):
graph checkpoints, long-term memory, GigSim's world and the list of runs. So an API restart loses
nothing: a pending approval is still pending, and a run that was cut off mid-way is picked up from
its last checkpoint. (Postgres and a Redis worker, the Part E versions of this, are not built.)
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiosqlite
import httpx
from fastapi.encoders import jsonable_encoder
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.store.memory import InMemoryStore
from langgraph.store.sqlite.aio import AsyncSqliteStore
from langgraph.types import Command

import gigsim.app as gigsim
from agent.graphs.bid_graph import build_bid_graph
from agent.graphs.conversation_graph import build_conversation_graph
from agent.mcp_client import ToolBox
from agent.memory.store import record_outcome
from agent.nodes.base import Deps
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.server import build_server as market
from mcp_servers.portfolio.server import build_server as portfolio
from mcp_servers.workspace.server import build_server as workspace

STATE_DIR = Path(os.getenv("GIGBID_STATE_DIR", "data/processed/app"))
STAGES = ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]


@dataclass
class Run:
    thread_id: str
    user: str
    kind: str                      # "bid" (one per job) or "talk" (one per client message)
    job_id: str
    persona: str
    started: float = field(default_factory=time.time)
    events: list[dict] = field(default_factory=list)
    running: bool = False
    changed: asyncio.Condition = field(default_factory=asyncio.Condition)
    marketplace_thread: str = ""   # talk runs: the GigSim thread they answer

    def summary(self) -> dict:
        return {"thread_id": self.thread_id, "kind": self.kind, "job_id": self.job_id, "persona": self.persona,
                "started": self.started, "running": self.running, "steps": len(self.events)}


def persistent() -> bool:
    return os.getenv("GIGBID_PERSIST", "1") == "1"


class Runtime:
    @classmethod
    async def create(cls) -> Runtime:
        """Open the stores (on disk unless GIGBID_PERSIST=0), build the system, and pick up where the last process stopped."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if not persistent():
            return cls(InMemorySaver(), InMemoryStore())
        os.environ.setdefault("GIGSIM_DB", str(STATE_DIR / "gigsim.db"))    # read by GigSim when its world is first built
        saver = AsyncSqliteSaver(await aiosqlite.connect(STATE_DIR / "graphs.db"))
        store = AsyncSqliteStore(await aiosqlite.connect(STATE_DIR / "memory.db", isolation_level=None))   # the store opens its own transactions
        await saver.setup()
        await store.setup()
        rt = cls(saver, store)
        rt.connections = [saver.conn, store.conn]
        await rt.recover()
        return rt

    def __init__(self, saver, store) -> None:
        os.environ.setdefault("GIGSIM_RATE_LIMIT", "600")           # the UI polls; GigSim's default limit is for one agent
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.index = STATE_DIR / "runs.json"
        self.connections: list = []                                 # SQLite files to close on shutdown
        self.audit = {name: STATE_DIR / "audit" / f"{name}.jsonl" for name in ("marketplace", "portfolio", "workspace")}
        self.ports: dict[str, GigSimAdapter] = {}
        self.deps = Deps(ToolBox({
            "marketplace": market(self.port_for, audit_path=str(self.audit["marketplace"])),
            "portfolio": portfolio(audit_path=str(self.audit["portfolio"])),
            "workspace": workspace(store_path=str(STATE_DIR / "workspace.json"), audit_path=str(self.audit["workspace"]))}),
            store)
        self.graphs = {"bid": build_bid_graph(self.deps, saver), "talk": build_conversation_graph(self.deps, saver)}
        self.runs: dict[str, Run] = {}
        self.skipped: dict[str, dict[str, str]] = {}                # user -> job_id -> reason (skipped by hand in the inbox)
        self.seen_events: dict[str, set[int]] = {}                  # user -> marketplace event ids already counted
        self.tasks: set[asyncio.Task] = set()

    # ---- surviving a restart -----------------------------------------------
    def save_index(self) -> None:
        """Which runs exist, and their steps so far. The graph state itself is in the checkpointer."""
        if persistent():
            runs = [{"thread_id": r.thread_id, "user": r.user, "kind": r.kind, "job_id": r.job_id, "persona": r.persona,
                     "started": r.started, "marketplace_thread": r.marketplace_thread, "events": r.events} for r in self.runs.values()]
            self.index.write_text(json.dumps({"runs": runs, "skipped": self.skipped,
                                              "seen_events": {u: sorted(ids) for u, ids in self.seen_events.items()}}), encoding="utf-8")

    async def recover(self) -> None:
        """After a restart: reload the runs, and continue any run that was cut off between two nodes."""
        if not self.index.exists():
            return
        saved = json.loads(self.index.read_text(encoding="utf-8"))
        self.skipped = saved.get("skipped", {})
        self.seen_events = {u: set(ids) for u, ids in saved.get("seen_events", {}).items()}
        for r in saved.get("runs", []):
            run = self.runs[r["thread_id"]] = Run(r["thread_id"], r["user"], r["kind"], r["job_id"], r["persona"], started=r["started"],
                                                  events=r["events"], marketplace_thread=r.get("marketplace_thread", ""))
            snap = await self.graphs[run.kind].aget_state(self.cfg(run))
            if snap.next and snap.next != ("approval",):           # stopped mid-way: carry on from the last checkpoint
                self._go(run, None)

    # ---- marketplace -------------------------------------------------------
    def port_for(self, user: str) -> GigSimAdapter:
        """One GigSim account per GigBid user (tenant scoping): its own Connects, proposals and messages."""
        return self.ports.setdefault(user, GigSimAdapter(base_url="http://gigsim", token=f"gs-{user}",
                                                         transport=httpx.ASGITransport(app=gigsim.app)))

    # ---- runs --------------------------------------------------------------
    def cfg(self, run: Run) -> dict:
        return {"configurable": {"thread_id": run.thread_id, "trace_id": run.thread_id}}

    def mine(self, user: str, thread_id: str) -> Run | None:
        run = self.runs.get(thread_id)
        return run if run and run.user == user else None

    def start_bid(self, user: str, job_id: str, profile: dict) -> Run:
        """Idempotent: asking twice for the same job returns the run that already exists."""
        thread = f"{user}:{job_id}"
        if thread in self.runs:
            return self.runs[thread]
        run = self.runs[thread] = Run(thread, user, "bid", job_id, profile["persona"])
        self._go(run, {"user_id": user, "persona": profile["persona"], "job_id": job_id,
                       "profile": {"min_budget": profile["min_budget"]}})
        return run

    def start_talk(self, user: str, marketplace_thread: str, message_count: int, job_id: str, profile: dict) -> Run:
        thread = f"{user}:talk:{marketplace_thread}:{message_count}"
        if thread in self.runs:
            return self.runs[thread]
        run = self.runs[thread] = Run(thread, user, "talk", job_id, profile["persona"], marketplace_thread=marketplace_thread)
        self._go(run, {"user_id": user, "persona": profile["persona"], "thread_id": marketplace_thread,
                       "profile": {"min_budget": profile["min_budget"]}})
        return run

    def resume(self, run: Run, answer: dict) -> None:
        self._go(run, Command(resume=answer))

    def _go(self, run: Run, graph_input) -> None:
        run.running = True
        task = asyncio.create_task(self._stream(run, graph_input))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _stream(self, run: Run, graph_input) -> None:
        """Drive the graph and turn LangGraph's "updates" stream into the run's event list."""
        graph, t0 = self.graphs[run.kind], time.time()
        try:
            async for update in graph.astream(graph_input, self.cfg(run), stream_mode="updates"):
                for name, out in update.items():
                    if name == "__interrupt__":
                        await self._emit(run, {"node": "approval", "waiting": True, "seconds": round(time.time() - t0, 2)})
                        continue
                    out = out or {}
                    await self._emit(run, {"node": name, "seconds": round(time.time() - t0, 2), "status": out.get("status"),
                                           "errors": out.get("errors", []), "tokens": out.get("tokens_used", 0)})
        except Exception as e:                                       # a run must never take the API down
            await self._emit(run, {"node": "error", "errors": [f"{type(e).__name__}: {e}"], "seconds": round(time.time() - t0, 2)})
        finally:
            run.running = False
            await self._emit(run, {"node": "end", "done": True, "seconds": round(time.time() - t0, 2)})

    async def _emit(self, run: Run, event: dict) -> None:
        async with run.changed:
            run.events.append({"seq": len(run.events) + 1, "at": round(time.time(), 2), **event})
            run.changed.notify_all()
        self.save_index()

    async def state(self, run: Run) -> dict:
        """The run's graph state as plain JSON, plus the pending approval payload if it is paused."""
        snap = await self.graphs[run.kind].aget_state(self.cfg(run))
        pending = None
        if snap.next == ("approval",) and snap.tasks and snap.tasks[0].interrupts:
            pending = snap.tasks[0].interrupts[0].value
        return {"values": jsonable_encoder(snap.values), "pending": jsonable_encoder(pending), "next": list(snap.next)}

    def trace(self, run: Run) -> list[dict]:
        """Every MCP tool call of this run, from the three audit logs, by trace id."""
        lines = []
        for server, path in self.audit.items():
            if path.exists():
                for raw in path.read_text(encoding="utf-8").splitlines():
                    row = json.loads(raw) if raw.startswith("{") and raw.endswith("}") else {}
                    if row.get("trace_id") == run.thread_id:
                        lines.append({"server": server, "ts": row["ts"], "tool": row["tool"], "arguments": row.get("arguments"),
                                      "result": row.get("result")})
        return sorted(lines, key=lambda r: r["ts"])

    # ---- marketplace events -> pipeline and outcome memory -------------------
    async def sync_events(self, user: str) -> list[dict]:
        """Read the marketplace's events and count each new reply or hire once for outcome memory."""
        events = await self.port_for(user).list_events()
        seen = self.seen_events.setdefault(user, set())
        for e in events:
            if e["id"] not in seen:
                seen.add(e["id"])
                run = self.runs.get(f"{user}:{e['job_id']}")
                if run and e["type"] in ("replied", "hired"):
                    values = (await self.state(run))["values"]
                    await record_outcome(self.deps.store, user, values.get("job", {}).get("category", "other"), e["type"])
                    self.save_index()
        return events


_runtime: Runtime | None = None


async def runtime() -> Runtime:
    """FastAPI dependency: the one system of this process, built on first use."""
    global _runtime
    if _runtime is None:
        _runtime = await Runtime.create()
    return _runtime


async def close_runtime() -> None:
    """Shut the system down: close the SQLite files and forget GigSim's world. What is on disk stays, so the
    next runtime() call is the same as a process restart (the restart test uses exactly this)."""
    global _runtime
    if _runtime is not None:
        for conn in _runtime.connections:
            await conn.close()
    gigsim.reset_world()
    _runtime = None
