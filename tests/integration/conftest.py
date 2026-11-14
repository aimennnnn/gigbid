"""Whole-system fixtures: GigSim + all three MCP servers + the bid graph, in one process, no network."""
import httpx
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

import gigsim.app as gigsim
from agent.graphs.bid_graph import build_bid_graph
from agent.mcp_client import ToolBox
from agent.nodes.base import Deps
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.server import build_server as market
from mcp_servers.portfolio.server import build_server as portfolio
from mcp_servers.workspace.server import build_server as workspace


@pytest.fixture
def system(monkeypatch, tmp_path):
    monkeypatch.setenv("GIGBID_LLM", "fake")
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    gigsim.reset_world()
    ports = {}

    def port_for(user):
        return ports.setdefault(user, GigSimAdapter(base_url="http://gigsim", token=f"gs-{user}", backoff=0,
                                                    transport=httpx.ASGITransport(app=gigsim.app)))
    servers = {"marketplace": market(port_for, audit_path=str(tmp_path / "m.jsonl")),
               "portfolio": portfolio(audit_path=str(tmp_path / "p.jsonl")),
               "workspace": workspace(store_path=str(tmp_path / "w.json"), audit_path=str(tmp_path / "w.jsonl"))}
    deps = Deps(ToolBox(servers), InMemoryStore())
    saver = InMemorySaver()

    class System:
        pass
    s = System()
    s.deps, s.saver, s.servers, s.port_for, s.tmp = deps, saver, servers, port_for, tmp_path
    s.graph = build_bid_graph(deps, saver)
    s.start = lambda job_id, persona="ml", user="aimen": {"user_id": user, "persona": persona, "job_id": job_id,
                                                           "profile": {"min_budget": 400}}
    s.cfg = lambda thread: {"configurable": {"thread_id": thread, "trace_id": f"trace-{thread}"}}
    yield s
    gigsim.reset_world()
