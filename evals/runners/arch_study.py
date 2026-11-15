"""R&D question C: one agent, a supervisor, or the hand-built graph?

HYPOTHESIS (written before the baselines were run, 15 Nov; the graph's own numbers were already known from
decision_eval): on the bid-or-skip decision the hand-built graph has the best F1, by at least 5 points over both
baselines, and uses the fewest tokens per job, because its thresholds are code and it makes a fixed three model
calls. The single ReAct agent comes second on F1 and uses at least 1.5 times the graph's tokens (it re-reads the
whole conversation at every tool call). The supervisor is the slowest and uses the most tokens (hand-off turns)
and is not more accurate than the single agent.

Same task, same jobs, same model, same MCP tools: say "bid" or "skip" for a dev job, and whether it is a scam.
  graph       the bid graph, stopped before the Writer (exactly what decision_eval measures)
  react       ONE agent: langgraph.prebuilt.create_react_agent, one prompt, two tools
  supervisor  langgraph-supervisor: a supervisor hands the job to a risk agent and a fit agent, then decides
The two baselines get the graph's decision rules as text (agent/prompts/arch_rules.md); the graph has them as code.
Tools go through the same ToolBox, so allowlists, timeouts and the audit log still apply.

    uv run python -m evals.runners.arch_study                 10 jobs per persona, all three
    uv run python -m evals.runners.arch_study --only react    one architecture

Writes evals/results/arch_study.json after every architecture, so a run that is cut short keeps what finished.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
import warnings
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from agent.llm import PROMPTS, USAGE, providers, render
from agent.settings import get_settings
from evals.runners.common import System, dev_rows, mean, percentile, save
from evals.runners.decision_eval import prf

warnings.filterwarnings("ignore", message=".*create_react_agent.*")     # LangGraph 1.x points to a newer name; this is the ReAct agent the brief asks for
FLOOR = 400                                  # the same min_budget the graph is given in the evals (System.start)
JOB_TIMEOUT_S = 420


def prompt(name: str, rules: bool = True) -> str:
    text = (PROMPTS / f"arch_{name}.md").read_text(encoding="utf-8")
    return text + ("\n" + (PROMPTS / "arch_rules.md").read_text(encoding="utf-8") if rules else "")


class FakeChat(BaseChatModel):
    """Stand-in for tests and CI (GIGBID_LLM=fake): calls each of its tools once, then answers by a keyword rule."""
    tool_names: list[str] = []

    def bind_tools(self, tools: Any, **kwargs: Any) -> FakeChat:
        return FakeChat(tool_names=[getattr(t, "name", None) or t["function"]["name"] for t in tools])

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        text = "\n".join(str(m.content) for m in messages)
        done = {m.name for m in messages if isinstance(m, ToolMessage)}
        for name in self.tool_names:
            if name not in done:
                found = re.search(r'"client_id": "([^"]+)"', text) if name == "get_client_history" else re.search(r'"skills": \[\s*"([^"]+)"', text)
                args = {"get_client_history": {"client_id": found.group(1) if found else ""},
                        "search_evidence": {"requirement": found.group(1) if found else "python"}}.get(name, {})
                msg = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{len(messages)}"}])
                break
        else:
            post = text[text.rfind("<untrusted_job_post>\n"):text.rfind("</untrusted_job_post>")].lower()      # the post only, not the prompts
            scam = bool(re.search(r"telegram|whatsapp|unpaid|free sample|gift card", post))
            msg = AIMessage(content=json.dumps({"action": "skip" if scam else "bid", "scam": scam, "reason": "stand-in rule"}))
        msg.usage_metadata = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        return ChatResult(generations=[ChatGeneration(message=msg)])


def chat_model() -> BaseChatModel:
    """The same provider and model the graph's analysis nodes use (the "small" one)."""
    if os.getenv("GIGBID_LLM", "").lower() == "fake":
        return FakeChat()
    from langchain_openai import ChatOpenAI
    p = providers()[0]
    return ChatOpenAI(model=p["models"]["small"], base_url=p["base_url"], api_key=p["key"], temperature=0,
                      timeout=300, max_retries=1, extra_body=p.get("extra") or None)


class Meter(BaseCallbackHandler):
    """Counts model calls, tool calls and tokens for one job, including calls made inside worker agents."""

    def __init__(self) -> None:
        self.llm_calls, self.tool_calls, self.tokens_in, self.tokens_out = 0, 0, 0, 0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self.llm_calls += 1
        used = getattr(response.generations[0][0].message, "usage_metadata", None) or {}
        self.tokens_in += used.get("input_tokens", 0)
        self.tokens_out += used.get("output_tokens", 0)

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self.tool_calls += 1


def make_tools(system: System, row: dict, user: str) -> tuple[Any, Any]:
    """The two MCP tools the baselines may use, as LangChain tools. Calls go through the ToolBox."""
    box = system.bid_deps.toolbox

    @tool
    async def get_client_history(client_id: str) -> str:
        """The client's record on the marketplace: jobs posted, hires, money spent, payment verified, reviews. Use it to judge risk."""
        try:
            return json.dumps(await box.call("risk", "marketplace", "get_client_history", {"client_id": client_id}, user=user))
        except Exception as e:                                   # the agent sees the error and can carry on
            return f"tool error: {type(e).__name__}: {e}"[:300]

    @tool
    async def search_evidence(requirement: str) -> str:
        """Search the freelancer's own portfolio for proof of ONE requirement (a skill or a kind of project). Returns up to 3 items."""
        try:
            r = await box.call("matcher", "portfolio", "search_evidence",
                               {"requirement": requirement, "k": 3, "persona": row["persona"],
                                "filters": {"types": get_settings()["rag"]["evidence_types"]}}, user=user)
            return json.dumps([{"id": i["id"], "title": i["title"], "skills": i["skills"], "text": i["text"][:400]} for i in r["items"]])
        except Exception as e:
            return f"tool error: {type(e).__name__}: {e}"[:300]

    return get_client_history, search_evidence


def verdict(text: str) -> dict | None:
    """The agent's last message must be {"action", "scam", "reason"}. Anything else is a failed job."""
    try:
        v = json.loads(text[text.find("{"):text.rfind("}") + 1])
        return v if v.get("action") in ("bid", "skip") and isinstance(v.get("scam"), bool) else None
    except (ValueError, AttributeError):
        return None


def build(arch: str, system: System, row: dict, user: str):
    from langgraph.prebuilt import create_react_agent
    model, (history, evidence) = chat_model(), make_tools(system, row, user)
    if arch == "react":
        return create_react_agent(model, [history, evidence], prompt=prompt("react"))
    from langgraph_supervisor import create_supervisor
    workers = [create_react_agent(model, [history], name="risk_agent", prompt=prompt("risk_agent", rules=False)),
               create_react_agent(model, [evidence], name="fit_agent", prompt=prompt("fit_agent", rules=False))]
    return create_supervisor(workers, model=model, prompt=prompt("supervisor"), output_mode="last_message").compile()


async def one_baseline(arch: str, system: System, row: dict) -> dict:
    meter, user = Meter(), f"arch-{arch}-{row['job_id']}"
    task = render({"freelancer": {"persona": row["persona"], "min_budget": FLOOR}, "job_post": row["job"]}, untrusted=("job_post",))
    out = await asyncio.wait_for(build(arch, system, row, user).ainvoke(
        {"messages": [("user", task)]}, {"callbacks": [meter], "recursion_limit": 40}), JOB_TIMEOUT_S)
    v = verdict(str(out["messages"][-1].content))
    if v is None:
        raise ValueError(f"no verdict in the last message: {str(out['messages'][-1].content)[:120]!r}")
    return {"said_bid": v["action"] == "bid", "said_scam": v["scam"], "reason": str(v.get("reason", ""))[:100],
            "tokens": meter.tokens_in + meter.tokens_out, "llm_calls": meter.llm_calls, "tool_calls": meter.tool_calls}


async def one_graph(system: System, row: dict) -> dict:
    mark, block = len(USAGE), get_settings()["thresholds"]["risk_block"]
    s = await system.bid.ainvoke(System.start(row, f"arch-graph-{row['job_id']}"), {"configurable": {"thread_id": f"arch-{row['job_id']}"}},
                                 interrupt_before=["writer"])
    if s.get("errors"):
        raise ValueError("; ".join(s["errors"])[:200])
    d, risk, used = s.get("decision"), s.get("risk"), USAGE[mark:]
    return {"said_bid": bool(d and d.action == "bid" and s.get("status") != "skipped"), "said_scam": bool(risk and risk.risk_score >= block),
            "reason": "; ".join(d.reasons)[:100] if d else "", "tokens": sum(u["tokens_in"] + u["tokens_out"] for u in used),
            "llm_calls": len(used), "tool_calls": None}


def summary(rows: list[dict]) -> dict:
    took, calls = [r["seconds"] for r in rows], [r["tool_calls"] for r in rows if r["tool_calls"] is not None]
    return {"jobs": len(rows), "failed": sum(bool(r["error"]) for r in rows),
            "bid_or_skip": prf(rows, "said_bid", "gold_bid"), "scam": prf(rows, "said_scam", "gold_scam"),
            "p50_s": percentile(took, 50), "p95_s": percentile(took, 95), "tokens_per_job": mean([r["tokens"] for r in rows]),
            "llm_calls_per_job": mean([r["llm_calls"] for r in rows]), "tool_calls_per_job": mean(calls)}


async def run(limit: int, only: list[str]) -> None:
    rows, system, out = dev_rows(limit), System(), {}
    for arch in only:
        done = []
        for n, r in enumerate(rows, start=1):
            t0, got, error = time.perf_counter(), {"said_bid": False, "said_scam": False, "reason": "", "tokens": 0, "llm_calls": 0, "tool_calls": 0}, ""
            try:
                got = await (one_graph(system, r) if arch == "graph" else one_baseline(arch, system, r))
            except Exception as e:                               # a failed job counts as "skip", and is reported
                error = f"{type(e).__name__}: {e}"[:160]
            done.append({"job_id": r["job_id"], "kind": r["kind"], "gold_bid": r["gold_action"] == "bid", "gold_scam": r["gold_scam"],
                         **got, "error": error, "seconds": round(time.perf_counter() - t0, 2)})
            print(f"[{arch} {n}/{len(rows)}] {r['job_id']} {r['kind']:13} gold={r['gold_action']:4} said={'bid ' if got['said_bid'] else 'skip'} "
                  f"{done[-1]['seconds']:6.1f}s {got['tokens']:6d} tok" + (f"  ERROR {error}" if error else ""), flush=True)
        out[arch] = {"overall": summary(done),
                     "wrong": [{k: r[k] for k in ("job_id", "kind", "gold_bid", "said_bid", "gold_scam", "said_scam", "reason", "error")}
                               for r in done if r["said_bid"] != r["gold_bid"] or r["said_scam"] != r["gold_scam"] or r["error"]]}
        save("arch_study", {"jobs": len(rows), "architectures": out})
        print(f"-----SUMMARY {arch} {json.dumps(out[arch]['overall'])}", flush=True)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="first N jobs per persona")
    ap.add_argument("--only", nargs="+", default=["react", "supervisor", "graph"], choices=["react", "supervisor", "graph"])
    args = ap.parse_args(argv)
    asyncio.run(run(args.limit, args.only))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
