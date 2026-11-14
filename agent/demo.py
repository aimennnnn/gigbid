"""Run ONE real job through the bid graph and stop at the approval step. Nothing is sent.

    uv run python -m agent.demo                 (uses the real model from .env)
    uv run python -m agent.demo dev-web-003 web (job id, persona)

Starts GigSim and the MCP servers inside this process, so nothing else needs to be running.
"""
import asyncio
import logging
import sys
import tempfile
import time

import httpx
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore


async def main(job_id: str, persona: str) -> None:
    import gigsim.app as gigsim
    from agent.graphs.bid_graph import build_bid_graph
    from agent.mcp_client import ToolBox
    from agent.nodes.base import Deps
    from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
    from mcp_servers.marketplace.server import build_server as market
    from mcp_servers.portfolio.server import build_server as portfolio

    tmp = tempfile.mkdtemp()
    port = GigSimAdapter(base_url="http://gigsim", token="gs-demo", transport=httpx.ASGITransport(app=gigsim.app))
    deps = Deps(ToolBox({"marketplace": market(lambda u: port, audit_path=f"{tmp}/m.jsonl"),
                         "portfolio": portfolio(audit_path=f"{tmp}/p.jsonl")}), InMemoryStore())
    graph, cfg = build_bid_graph(deps, InMemorySaver()), {"configurable": {"thread_id": f"demo-{job_id}"}}
    start, t0 = {"user_id": "demo", "persona": persona, "job_id": job_id, "profile": {"min_budget": 400}}, time.time()
    async for update in graph.astream(start, cfg, stream_mode="updates"):
        for name in update:
            print(f"  [{time.time() - t0:5.1f}s] {name}")
    snap = await graph.aget_state(cfg)
    s = snap.values
    print("\nJOB      :", s["job"]["title"])
    if s.get("errors"):
        print("ERRORS   :", *s["errors"], sep="\n  ")
    if s.get("decision"):
        print("DECISION :", s["decision"].action, "-", "; ".join(s["decision"].reasons))
    if s.get("fit"):
        print("FIT      :", s["fit"].fit_score, *[f"{m.status:11} {m.requirement[:60]} {m.evidence_ids}" for m in s["fit"].matches], sep="\n  ")
    if s.get("risk"):
        print("RISK     :", s["risk"].risk_score, s["risk"].flags)
    if s.get("price"):
        print("PRICE    :", s["price"].rationale)
    if snap.next == ("approval",):
        p = snap.tasks[0].interrupts[0].value
        print("\nDRAFT (waiting for approval, nothing sent):\n", p["draft"])
        print("\nCLAIMS   :", *[f"{c['status']}: {c['text'][:90]} {c['evidence_ids']}" for c in p["claims"]], sep="\n  ")
        print("REMOVED  :", p["removed_claims"] or "none")
        print("DRY RUN  :", p["dry_run"]["connects_cost"], "Connects, balance after", p["dry_run"]["connects_balance_after"])
    print(f"\nstatus={s.get('status')}  tokens={s.get('tokens_used', 0)}  seconds={time.time() - t0:.1f}")


if __name__ == "__main__":
    load_dotenv()
    logging.disable(logging.WARNING)
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "dev-ml-000", sys.argv[2] if len(sys.argv) > 2 else "ml"))
