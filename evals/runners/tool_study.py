"""R&D question A: does tool granularity change agent behaviour?

HYPOTHESIS (written before any run, 15 Nov): with fine-grained tools (one tool per action, each with
its own input schema) the model fills in arguments correctly at least 10 points more often than with
coarse tools (one tool per server, an `action` name and a free `params` object), and picks the right
action about as often. The price is input tokens: the fine set costs at least twice as many per task.

Setup: 40 tasks with a known correct tool and arguments (evals/datasets/tool_tasks.jsonl). The model
sees the task and one of two descriptions of the SAME 17 MCP tools:
  fine    17 tools, real names, descriptions and input schemas, read from the running servers
  coarse   3 tools (marketplace, portfolio, workspace): {"action": <one of the server's tools>, "params": {...}},
           where the description lists each action in one line and gives no per-action schema
The model is the "small" one (the size that does routing in the app), through the same client as the agents.

    uv run python -m evals.runners.tool_study          writes evals/results/tool_study.json

Scores: tool-selection accuracy (right tool, or right server + action), argument accuracy (right tool
AND every expected argument present with the expected value), tokens and seconds per task.
An expected key ending in "~" is free text: every word of the expected value must appear in what the model gave.
"""
from __future__ import annotations

import asyncio
import json
import re
import tempfile
import time
from typing import Any

from pydantic import BaseModel

from agent.llm import USAGE, ask
from evals.runners.common import ROOT, mean, save


class ToolChoice(BaseModel):
    tool: str
    arguments: dict[str, Any] = {}


async def tool_sets() -> dict[str, list[dict]]:
    from mcp_servers.marketplace.server import build_server as market
    from mcp_servers.portfolio.server import build_server as portfolio
    from mcp_servers.workspace.server import build_server as workspace
    tmp = tempfile.mkdtemp()
    servers = {"marketplace": market(lambda user: None, audit_path=f"{tmp}/m.jsonl"), "portfolio": portfolio(audit_path=f"{tmp}/p.jsonl"),
               "workspace": workspace(store_path=f"{tmp}/w.json", audit_path=f"{tmp}/w.jsonl")}
    fine, coarse = [], []
    for name, server in servers.items():
        tools = await server.list_tools()
        fine += [{"name": t.name, "description": t.description, "input": t.inputSchema} for t in tools]
        actions = "; ".join(f"{t.name}: {(t.description or '').split('.')[0].strip()}" for t in tools)
        coarse.append({"name": name, "description": f"Everything on the {name} server. Set action to one of these. {actions}.",
                       "input": {"type": "object", "required": ["action"], "properties": {
                           "action": {"type": "string", "enum": [t.name for t in tools]},
                           "params": {"type": "object", "description": "The inputs of the chosen action."}}}})
    return {"fine": fine, "coarse": coarse}


def same(expected: Any, given: Any, free_text: bool) -> bool:
    def norm(x: Any) -> Any:
        return x.strip().lower() if isinstance(x, str) else x
    if free_text:
        return isinstance(given, str) and all(w in given.lower() for w in re.findall(r"[\w.]+", str(expected).lower()))
    if isinstance(expected, list):
        return isinstance(given, list) and sorted(map(norm, expected)) == sorted(map(norm, given))
    if isinstance(expected, bool) or isinstance(given, bool):
        return expected is given
    if isinstance(expected, (int, float)):
        try:
            return float(given) == float(expected)
        except (TypeError, ValueError):
            return False
    return norm(expected) == norm(given)


def grade(task: dict, choice: ToolChoice, kind: str) -> dict:
    """Was the right tool picked, and were the expected arguments filled in?"""
    if kind == "fine":
        picked, args = choice.tool == task["tool"], choice.arguments
    else:
        picked = choice.tool == task["server"] and choice.arguments.get("action") == task["tool"]
        args = choice.arguments.get("params") if isinstance(choice.arguments.get("params"), dict) else {}
    wrong = [k.rstrip("~") for k, v in task["arguments"].items() if not same(v, args.get(k.rstrip("~")), k.endswith("~"))]
    return {"tool_ok": picked, "args_ok": picked and not wrong, "wrong_arguments": wrong if picked else []}


def summary(rows: list[dict]) -> dict:
    return {"tasks": len(rows), "failed_calls": sum(bool(r["error"]) for r in rows),
            "tool_selection_accuracy": mean([float(r["tool_ok"]) for r in rows]),
            "argument_accuracy": mean([float(r["args_ok"]) for r in rows]),
            "tokens_per_task": mean([r["tokens"] for r in rows]), "tokens_in_per_task": mean([r["tokens_in"] for r in rows]),
            "seconds_per_task": mean([r["seconds"] for r in rows])}


async def run() -> None:
    tasks = [json.loads(line) for line in (ROOT / "evals" / "datasets" / "tool_tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    sets, out = await tool_sets(), {}
    for kind, tools in sets.items():
        rows = []
        for n, task in enumerate(tasks, start=1):
            mark, t0, error, choice = len(USAGE), time.perf_counter(), "", ToolChoice(tool="")
            try:
                choice, _ = await ask("tool_picker", {"task": task["task"], "tools": tools}, ToolChoice)
            except Exception as e:                       # a failed call is a wrong answer, not a crash
                error = f"{type(e).__name__}: {e}"[:200]
            used = USAGE[mark:]
            rows.append({"id": task["id"], "expected": f"{task['server']}.{task['tool']}", "chose": choice.tool, "given": choice.arguments,
                         "error": error, "seconds": round(time.perf_counter() - t0, 2),
                         "tokens_in": sum(u["tokens_in"] for u in used), "tokens": sum(u["tokens_in"] + u["tokens_out"] for u in used),
                         **grade(task, choice, kind)})
            print(f"[{kind} {n}/{len(tasks)}] {task['id']} {task['tool']:22} tool={'ok ' if rows[-1]['tool_ok'] else 'NO '} "
                  f"args={'ok' if rows[-1]['args_ok'] else 'NO'}" + (f"  ERROR {error[:70]}" if error else ""))
        out[kind] = {"tools_shown": len(tools), "overall": summary(rows),
                     "by_server": {s: summary([r for r in rows if r["expected"].startswith(s)]) for s in ("marketplace", "portfolio", "workspace")},
                     "wrong": [r for r in rows if not r["args_ok"]]}
        o = out[kind]["overall"]
        print(f"{kind}: tool selection={o['tool_selection_accuracy']}  arguments={o['argument_accuracy']}  "
              f"tokens per task={o['tokens_per_task']}  seconds per task={o['seconds_per_task']}  failed calls={o['failed_calls']}")
    save("tool_study", {"tasks": len(tasks), "sets": out})


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run())
