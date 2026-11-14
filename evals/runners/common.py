"""Shared by every eval runner: the dev set, result files, and a whole GigBid system in one process."""
from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent.settings import get_settings

sys.stdout.reconfigure(line_buffering=True)      # show each progress line at once, also inside a notebook
ROOT = Path(__file__).resolve().parents[2]
PERSONAS = ["ml", "web", "data"]


def out_dir() -> Path:
    d = Path(os.getenv("EVAL_OUT", ROOT / "evals" / "results"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def dev_rows(limit: int | None = None) -> list[dict]:
    """Dev set rows with the job post attached. limit = first N jobs of each persona."""
    jobs = {j["job_id"]: j for j in json.loads((ROOT / "gigsim/seed/jobs_dev.json").read_text(encoding="utf-8"))}
    rows = []
    for p in PERSONAS:
        lines = (ROOT / f"evals/datasets/dev_{p}.jsonl").read_text(encoding="utf-8").splitlines()
        rows += [json.loads(line) | {"job": jobs[json.loads(line)["job_id"]]} for line in lines[:limit]]
    return rows


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def meta() -> dict:
    """Written into every result file, so each number says how it was produced."""
    from agent.llm import providers
    from rag.index.embed import embedder, fake
    s = get_settings()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except OSError:
        commit = ""
    if os.getenv("GIGBID_LLM", "").lower() == "fake":
        llm = "fake (rule-based stand-in, no model)"
    else:
        llm = ", ".join(f"{p['name']}: {p['models']['small']} / {p['models']['strong']}" for p in providers()) or "none configured"
    return {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_commit": commit,
            "embeddings": embedder().name, "reranker": "word overlap (offline stand-in)" if fake() else s.profile["reranker"],
            "llm": llm, "machine": f"{platform.system()} {platform.machine()}, {os.cpu_count()} CPU cores, {platform.processor()}".strip(", ")}


def save(name: str, data: dict) -> Path:
    path = out_dir() / f"{name}.json"
    path.write_text(json.dumps({"meta": meta()} | data, indent=1), encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    return path


def settings_used() -> dict:
    """The settings a retrieval result depends on. A saved result is only reused if these are unchanged."""
    s = get_settings()
    return {"rag": s["rag"], "embeddings": s.profile["embeddings"], "reranker": s.profile["reranker"],
            "stand_in_models": os.getenv("GIGBID_RAG_MODELS", "")}


def saved(name: str, jobs: int) -> dict:
    """Checkpoint: the finished parts of an earlier, interrupted run of the same eval with the same settings and jobs."""
    path = out_dir() / f"{name}.json"
    if not path.exists():
        return {}
    old = json.loads(path.read_text(encoding="utf-8"))
    same = old.get("settings") == json.loads(json.dumps(settings_used())) and old.get("jobs") == jobs
    return old.get("done", {}) if same else {}


def cost_usd(usage: list[dict]) -> float:
    """List-price cost of some model calls (rows from agent.llm.USAGE). Unlisted models cost 0."""
    prices = get_settings()["prices_usd_per_mtok"]
    total = 0.0
    for u in usage:
        cin, cout = prices.get(u["provider"], {}).get(u["model"], [0, 0])
        total += (u["tokens_in"] * cin + u["tokens_out"] * cout) / 1_000_000
    return total


class System:
    """GigSim, the three MCP servers and both graphs in this process. No network except the model."""

    def __init__(self) -> None:
        import tempfile

        import httpx
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.store.memory import InMemoryStore

        import gigsim.app as gigsim
        from agent.graphs.bid_graph import build_bid_graph
        from agent.graphs.conversation_graph import build_conversation_graph
        from agent.mcp_client import ToolBox
        from agent.nodes.base import Deps
        from mcp_servers.marketplace.adapters.gigsim import GigSimAdapter
        from mcp_servers.marketplace.server import build_server as market
        from mcp_servers.portfolio.server import build_server as portfolio
        from mcp_servers.workspace.server import build_server as workspace

        if get_settings().marketplace != "gigsim":
            raise SystemExit("evals only run against GigSim: they approve proposals automatically")
        os.environ["GIGSIM_ERROR_RATE"] = "0"                    # a fixed, repeatable run: no random 503s
        os.environ["GIGSIM_RATE_LIMIT"] = "100000"
        logging.disable(logging.WARNING)                         # keep the progress lines readable
        gigsim.reset_world()
        tmp, self.ports = tempfile.mkdtemp(), {}

        def port_for(user: str):
            return self.ports.setdefault(user, GigSimAdapter(base_url="http://gigsim", token=f"gs-{user}",
                                                             transport=httpx.ASGITransport(app=gigsim.app)))
        self.port_for = port_for
        deps = Deps(ToolBox({"marketplace": market(port_for, audit_path=f"{tmp}/m.jsonl"),
                             "portfolio": portfolio(audit_path=f"{tmp}/p.jsonl"),
                             "workspace": workspace(store_path=f"{tmp}/w.json", audit_path=f"{tmp}/w.jsonl")}), InMemoryStore())
        saver = InMemorySaver()
        self.bid, self.talk = build_bid_graph(deps, saver), build_conversation_graph(deps, saver)

    @staticmethod
    def start(row: dict, user: str) -> dict:
        return {"user_id": user, "persona": row["persona"], "job_id": row["job_id"], "profile": {"min_budget": 400}}
