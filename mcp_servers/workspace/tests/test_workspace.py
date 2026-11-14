import pytest

from mcp_servers.workspace.server import build_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def workspace(tmp_path):
    return build_server(store_path=str(tmp_path / "ws.json"), audit_path=str(tmp_path / "audit.jsonl"))


async def test_slots_are_on_working_days_and_holds_remove_them(workspace, session):
    async with session(workspace) as s:
        slots = (await s.call_tool("get_free_slots", {"date_from": "2026-11-16", "days": 5})).structuredContent["slots"]
        assert slots and all(sl["start"][11:13] >= "10" for sl in slots)
        args = {"start": slots[0]["start"], "title": "Interview: fraud model", "idempotency_key": "hold-key-0001"}
        h1 = (await s.call_tool("create_interview_hold", args)).structuredContent
        h2 = (await s.call_tool("create_interview_hold", args)).structuredContent
        assert h1["status"] == "tentative" and h1["hold_id"] == h2["hold_id"] and h2["replayed"]
        after = (await s.call_tool("get_free_slots", {"date_from": "2026-11-16", "days": 5})).structuredContent["slots"]
        assert slots[0]["start"] not in {sl["start"] for sl in after}
        clash = await s.call_tool("create_interview_hold", args | {"idempotency_key": "hold-key-0002"})
        assert clash.isError


async def test_email_is_only_ever_a_draft(workspace, session):
    async with session(workspace) as s:
        args = {"to": "client@example.com", "subject": "Interview times", "body": "Here are three slots.", "idempotency_key": "mail-key-0001"}
        d1 = (await s.call_tool("create_email_draft", args)).structuredContent
        d2 = (await s.call_tool("create_email_draft", args)).structuredContent
        assert d1["status"] == "draft" and d1["draft_id"] == d2["draft_id"] and d2["replayed"]
        assert (await s.call_tool("create_email_draft", args | {"to": "not-an-email"})).isError
        tools = {t.name: t.annotations for t in (await s.list_tools()).tools}
        assert tools["get_free_slots"].readOnlyHint and not tools["create_email_draft"].destructiveHint
