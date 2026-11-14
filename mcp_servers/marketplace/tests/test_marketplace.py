import json

import httpx
import pytest

from mcp_servers.common import BearerAuth, mask_pii
from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
from mcp_servers.marketplace.server import build_server

pytestmark = pytest.mark.asyncio
LETTER = "You need a fraud detection model. I built one with Python and XGBoost that caught 81% of fraud. " * 2
JOB = "dev-ml-000"


async def test_tools_carry_the_right_annotations(market, session):
    async with session(market) as s:
        tools = {t.name: t for t in (await s.list_tools()).tools}
    assert tools["search_jobs"].annotations.readOnlyHint is True
    assert tools["create_proposal_draft"].annotations.destructiveHint is False
    assert tools["submit_proposal"].annotations.destructiveHint is True
    assert all(t.outputSchema for t in tools.values()), "every tool declares an output schema"
    for name in ("create_proposal_draft", "submit_proposal", "send_message"):
        assert {"idempotency_key", "dry_run"} <= set(tools[name].inputSchema["properties"])


async def test_search_and_read(market, session):
    async with session(market) as s:
        jobs = (await s.call_tool("search_jobs", {"query": "fraud detection", "category": "ml"})).structuredContent["jobs"]
        assert jobs and "fraud" in (jobs[0]["title"] + jobs[0]["description"]).lower()
        client = (await s.call_tool("get_client_history", {"client_id": jobs[0]["client_id"]})).structuredContent
        assert 0 <= client["hire_rate"] <= 1
        stats = (await s.call_tool("get_market_stats", {"category": "ml", "skills": ["XGBoost"]})).structuredContent
        assert stats["p25"] <= stats["p50"] <= stats["p75"]


async def test_bad_input_is_rejected_by_the_schema(market, session):
    async with session(market) as s:
        r = await s.call_tool("create_proposal_draft", {"job_id": JOB, "cover_letter": "too short", "amount": 500,
                                                        "idempotency_key": "key-00000001"})
    assert r.isError


async def test_dry_run_sends_nothing_and_shows_the_cost(market, session, adapter):
    async with session(market) as s:
        before = (await s.call_tool("get_connects_balance", {})).structuredContent["balance"]
        r = (await s.call_tool("create_proposal_draft", {"job_id": JOB, "cover_letter": LETTER, "amount": 1800,
                                                         "idempotency_key": "key-dry-0001", "dry_run": True})).structuredContent
        assert r["dry_run"] and r["status"] == "preview" and r["would_send"]["cover_letter"] == LETTER
        assert r["connects_cost"] > 0 and r["connects_balance_after"] == before - r["connects_cost"]
        assert (await s.call_tool("get_connects_balance", {})).structuredContent["balance"] == before
    assert await adapter._call("GET", "/proposals") == []


async def test_retried_write_never_submits_or_spends_twice(market, session, adapter):
    args = {"job_id": JOB, "cover_letter": LETTER, "amount": 1800, "idempotency_key": "key-draft-001"}
    async with session(market) as s:
        before = (await s.call_tool("get_connects_balance", {})).structuredContent["balance"]
        d1 = (await s.call_tool("create_proposal_draft", args)).structuredContent
        d2 = (await s.call_tool("create_proposal_draft", args)).structuredContent
        assert d1["id"] == d2["id"] and d2["replayed"] and not d1["replayed"]
        sub = {"draft_id": d1["id"], "job_id": JOB, "idempotency_key": "key-submit-01"}
        s1 = (await s.call_tool("submit_proposal", sub)).structuredContent
        s2 = (await s.call_tool("submit_proposal", sub)).structuredContent
        after = (await s.call_tool("get_connects_balance", {})).structuredContent["balance"]
    assert s1["status"] == "submitted" and s2["replayed"]
    assert before - after == s1["connects_cost"], "Connects spent exactly once"
    assert len(await adapter._call("GET", "/proposals")) == 1


async def test_gigsim_itself_dedupes_on_the_key(adapter):
    """Even if our MCP server restarted and lost its memory, GigSim honours the same key."""
    a = await adapter.create_proposal_draft(JOB, LETTER, 1800, {}, "key-same-0001")
    b = await adapter.create_proposal_draft(JOB, LETTER, 1800, {}, "key-same-0001")
    assert a["proposal_id"] == b["proposal_id"]


def flaky(sim, failures):
    """A transport that fails `failures` times with 503, then behaves."""
    real, state = httpx.ASGITransport(app=sim.app), {"n": 0}

    async def handler(request):
        state["n"] += 1
        if state["n"] <= failures:
            return httpx.Response(503, json={"detail": "temporary"})
        return await real.handle_async_request(request)
    return httpx.MockTransport(handler), state


async def test_retries_with_backoff_then_succeeds(sim):
    transport, state = flaky(sim, 2)
    a = GigSimAdapter(base_url="http://gigsim", token="gs-tester", transport=transport, backoff=0)
    assert (await a.get_job(JOB))["job_id"] == JOB and state["n"] == 3


async def test_marketplace_down_gives_a_clear_error(sim, session, tmp_path):
    transport, _ = flaky(sim, 99)
    a = GigSimAdapter(base_url="http://gigsim", token="gs-tester", transport=transport, backoff=0, retries=2)
    async with session(build_server(lambda u: a, audit_path=str(tmp_path / "a.jsonl"))) as s:
        r = await s.call_tool("get_job", {"job_id": JOB})
    assert r.isError and "marketplace_unavailable" in r.content[0].text


async def test_rate_limiter_stays_under_the_limit(adapter, session, tmp_path):
    server = build_server(lambda u: adapter, audit_path=str(tmp_path / "a.jsonl"), per_minute=2)
    async with session(server) as s:
        ok = [await s.call_tool("get_policy", {}) for _ in range(2)]
        import mcp_servers.common as c
        orig, c.asyncio.sleep = c.asyncio.sleep, (lambda *_: orig(0))     # do not really wait in tests
        try:
            third = await s.call_tool("get_policy", {})
        finally:
            c.asyncio.sleep = orig
    assert not any(r.isError for r in ok) and third.isError and "rate_limited" in third.content[0].text


async def test_audit_log_is_written_with_trace_id_and_masked_pii(market, session, tmp_path):
    async with session(market) as s:
        await s.call_tool("search_jobs", {"query": "mail me at boss@corp.com or +92 300 1234567"},
                          meta={"trace_id": "trace-abc", "user_id": "aimen"})
    line = json.loads((tmp_path / "audit.jsonl").read_text().splitlines()[-1])
    assert line["tool"] == "search_jobs" and line["trace_id"] == "trace-abc" and line["user"] == "aimen"
    assert "boss@corp.com" not in json.dumps(line) and "[email]" in line["arguments"]["query"]


async def test_pii_masking():
    assert mask_pii({"a": "call +1 555 010 0199, card 4242 4242 4242 4242"}) == {"a": "call [phone], card [card]"}


async def test_http_endpoint_needs_a_bearer_token(monkeypatch):
    monkeypatch.setenv("MCP_TOKENS", "secret-token:aimen")

    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=BearerAuth(inner)), base_url="http://mcp") as c:
        assert (await c.post("/mcp")).status_code == 401
        assert (await c.post("/mcp", headers={"Authorization": "Bearer wrong"})).status_code == 401
        assert (await c.post("/mcp", headers={"Authorization": "Bearer secret-token"})).status_code == 200
