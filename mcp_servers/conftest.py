"""Shared test fixtures: a fresh in-memory GigSim and an in-memory MCP client (no network)."""
import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

import gigsim.app as gigsim
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.server import build_server


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    monkeypatch.setenv("GIGSIM_DB", ":memory:")
    gigsim.reset_world()
    yield gigsim
    gigsim.reset_world()


@pytest.fixture
def adapter(sim):
    return GigSimAdapter(base_url="http://gigsim", token="gs-tester", backoff=0,
                         transport=httpx.ASGITransport(app=sim.app))


@pytest.fixture
def market(adapter, tmp_path):
    return build_server(lambda user: adapter, audit_path=str(tmp_path / "audit.jsonl"))


@pytest.fixture
def session():
    """Use as:  async with session(server) as s: ..."""
    return lambda server: connect(server._mcp_server)
