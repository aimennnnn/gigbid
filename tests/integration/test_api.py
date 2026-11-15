"""The web API end to end, in one process with stand-in models: sign in, inbox, a run that pauses for
approval, approve / edit / reject, the pipeline, a client reply, degraded mode and tenant scoping."""
import asyncio

import httpx
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def api(monkeypatch, tmp_path):
    monkeypatch.setenv("GIGBID_LLM", "fake")
    monkeypatch.setenv("GIGBID_RAG_MODELS", "fake")
    monkeypatch.setenv("GIGSIM_ERROR_RATE", "0")
    monkeypatch.setenv("GIGBID_STATE_DIR", str(tmp_path))
    import apps.api.runtime as runtime
    from apps.api.auth.users import reset_users
    monkeypatch.setattr(runtime, "STATE_DIR", tmp_path)
    runtime.reset_runtime()
    reset_users()
    from apps.api.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api") as client:
        yield client
    runtime.reset_runtime()
    reset_users()


async def sign_in(api, name="reviewer", password="reviewer") -> dict:
    r = await api.post("/api/auth/login", json={"username": name, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


async def settled(api, h, thread: str) -> dict:
    """Wait until the run stops or pauses, then return its detail."""
    for _ in range(200):
        d = (await api.get(f"/api/runs/{thread}", headers=h)).json()
        if not d["run"]["running"]:
            return d
        await asyncio.sleep(0.02)
    raise AssertionError("run did not settle")


async def a_draft(api, h) -> str:
    """Analyse the newest jobs and return the thread id of one that is waiting for approval."""
    started = (await api.post("/api/jobs/analyse-new?limit=10", headers=h)).json()
    assert started, "the inbox had jobs to analyse"
    for s in started:
        if (await settled(api, h, s["thread_id"]))["status"] == "awaiting_approval":
            return s["thread_id"]
    raise AssertionError("no analysed job reached the approval step")


async def test_inbox_needs_a_session_and_ranks_analysed_jobs_first(api):
    assert (await api.get("/api/jobs")).status_code == 401
    h = await sign_in(api)
    inbox = (await api.get("/api/jobs", headers=h)).json()
    assert inbox["total"] > 0 and all(j["state"] == "new" and not j["job_id"].startswith("dev-") for j in inbox["jobs"])
    await a_draft(api, h)
    first = (await api.get("/api/jobs", headers=h)).json()["jobs"][0]
    assert first["state"] == "analysed" and first["action"] == "bid" and first["fit"] is not None and first["price"] > 0


async def test_approving_in_the_api_resumes_the_graph_and_submits_once(api):
    h = await sign_in(api)
    thread = await a_draft(api, h)
    studio = (await api.get(f"/api/proposals/{thread}", headers=h)).json()
    assert studio["pending"] and studio["draft"] and studio["dry_run"] and studio["claims"]
    assert all(set(c["evidence_ids"]) <= set(studio["evidence"]) for c in studio["claims"]), "every claim shows its evidence"
    assert (await api.get(f"/api/proposals/{thread}", headers=h)).json()["pending"], "a second read (page refresh) still finds it"
    assert (await api.post(f"/api/approvals/{thread}", json={"action": "approve"}, headers=h)).status_code == 200
    assert (await settled(api, h, thread))["status"] == "submitted"
    assert (await api.post(f"/api/approvals/{thread}", json={"action": "approve"}, headers=h)).status_code == 409
    cards = (await api.get("/api/pipeline", headers=h)).json()["cards"]
    assert [c["stage"] for c in cards if c["thread_id"] == thread][0] in ("submitted", "viewed", "replied", "interview", "hired", "lost")
    assert (await api.get("/api/me", headers=h)).json()["connects_spent"] > 0
    stats = (await api.get("/api/analytics", headers=h)).json()
    assert stats["proposals"] == 1 and stats["connects_spent"] > 0


async def test_reject_needs_a_reason_and_edit_needs_text(api):
    h = await sign_in(api)
    thread = await a_draft(api, h)
    assert (await api.post(f"/api/approvals/{thread}", json={"action": "reject"}, headers=h)).status_code == 422
    assert (await api.post(f"/api/approvals/{thread}", json={"action": "edit"}, headers=h)).status_code == 422
    assert (await api.post(f"/api/approvals/{thread}", json={"action": "reject", "reason": "price too low"}, headers=h)).status_code == 200
    assert (await settled(api, h, thread))["status"] == "rejected"
    reasons = (await api.get("/api/analytics", headers=h)).json()["top_rejection_reasons"]
    assert any("price too low" in r[0] for r in reasons)


async def test_an_edited_draft_is_what_gets_submitted(api):
    h = await sign_in(api)
    thread = await a_draft(api, h)
    draft = (await api.get(f"/api/proposals/{thread}", headers=h)).json()["draft"]
    edited = draft.split(". ", 1)[1]
    assert (await api.post(f"/api/approvals/{thread}", json={"action": "edit", "text": edited}, headers=h)).status_code == 200
    assert (await settled(api, h, thread))["status"] == "submitted"
    assert (await api.get(f"/api/proposals/{thread}", headers=h)).json()["draft"].startswith(edited[:40])


async def test_run_stream_replays_every_step_and_the_trace_lists_tool_calls(api):
    h = await sign_in(api)
    thread = await a_draft(api, h)
    body = (await api.get(f"/api/runs/{thread}/stream", headers=h)).text
    nodes = [line.split('"node": "')[1].split('"')[0] for line in body.splitlines() if line.startswith("data:")]
    assert nodes[0] == "load_job" and {"analyst", "risk", "matcher", "writer", "verifier", "approval"} <= set(nodes) and nodes[-1] == "end"
    detail = (await api.get(f"/api/runs/{thread}", headers=h)).json()
    assert {t["tool"] for t in detail["trace"]} >= {"get_job", "search_evidence", "create_proposal_draft"}


async def test_a_client_reply_is_drafted_and_only_sent_after_approval(api):
    h = await sign_in(api)
    for s in (await api.post("/api/jobs/analyse-new?limit=10", headers=h)).json():
        if (await settled(api, h, s["thread_id"]))["status"] == "awaiting_approval":
            await api.post(f"/api/approvals/{s['thread_id']}", json={"action": "approve"}, headers=h)
            await settled(api, h, s["thread_id"])
    threads = [t for t in (await api.get("/api/messages", headers=h)).json()["threads"] if t["needs_reply"]]
    if not threads:
        pytest.skip("no simulated client replied in this world")
    t = threads[0]
    run = (await api.post(f"/api/messages/{t['thread_id']}/suggest", headers=h)).json()["thread_id"]
    await settled(api, h, run)
    again = next(x for x in (await api.get("/api/messages", headers=h)).json()["threads"] if x["thread_id"] == t["thread_id"])
    assert again["title"] != t["thread_id"] and again["job_id"], "the thread is shown under its job's title"
    assert again["suggested"]["pending"] and again["suggested"]["draft"] and len(again["messages"]) == len(t["messages"]), "nothing sent yet"
    await api.post(f"/api/approvals/{run}", json={"action": "approve"}, headers=h)
    await settled(api, h, run)
    after = next(x for x in (await api.get("/api/messages", headers=h)).json()["threads"] if x["thread_id"] == t["thread_id"])
    assert any(m["sender"] == "freelancer" for m in after["messages"])


async def test_marketplace_down_is_a_503_the_ui_can_show_and_health_reports_it(api):
    h = await sign_in(api)
    await api.post("/api/dev/marketplace?down=true")
    r = await api.get("/api/jobs", headers=h)
    assert r.status_code == 503 and r.json() == {"detail": "marketplace unavailable", "degraded": True}
    assert (await api.get("/api/health", headers=h)).json()["marketplace"] == "unavailable"
    await api.post("/api/dev/marketplace?down=false")
    assert (await api.get("/api/jobs", headers=h)).status_code == 200


async def test_users_cannot_see_each_others_runs_and_must_onboard_first(api):
    h = await sign_in(api)
    thread = await a_draft(api, h)
    r = await api.post("/api/auth/signup", json={"username": "second", "password": "secret-pass"})
    other = {"Authorization": f"Bearer {r.json()['token']}"}
    assert r.json()["onboarded"] is False and (await api.get("/api/jobs", headers=other)).status_code == 409
    assert (await api.put("/api/me/profile", json={"persona": "web", "min_budget": 500}, headers=other)).status_code == 200
    assert (await api.get("/api/jobs", headers=other)).status_code == 200
    assert (await api.get(f"/api/runs/{thread}", headers=other)).status_code == 404
    assert (await api.get(f"/api/proposals/{thread}", headers=other)).status_code == 404
    assert (await api.get("/api/runs", headers=other)).json() == []
