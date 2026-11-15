"""R&D question C harness: the three architectures run on the same jobs with stand-in models (no network)."""
import json

import pytest

from evals.runners import arch_study


def test_verdict_accepts_only_the_agreed_json():
    assert arch_study.verdict('ok {"action": "bid", "scam": false, "reason": "fits"}')["action"] == "bid"
    assert arch_study.verdict('{"action": "maybe", "scam": false}') is None
    assert arch_study.verdict("I think you should bid") is None


@pytest.mark.asyncio
async def test_single_agent_supervisor_and_graph_all_decide_the_same_jobs(monkeypatch, tmp_path):
    monkeypatch.setenv("GIGBID_LLM", "fake")
    monkeypatch.setenv("GIGBID_RAG_MODELS", "fake")
    monkeypatch.setenv("EVAL_OUT", str(tmp_path))
    await arch_study.run(1, ["react", "supervisor", "graph"])
    out = json.loads((tmp_path / "arch_study.json").read_text(encoding="utf-8"))
    assert out["jobs"] == 3 and set(out["architectures"]) == {"react", "supervisor", "graph"}
    for name, a in out["architectures"].items():
        assert a["overall"]["failed"] == 0, name
    react, sup = out["architectures"]["react"]["overall"], out["architectures"]["supervisor"]["overall"]
    assert react["tool_calls_per_job"] == 2 and react["llm_calls_per_job"] == 3          # two tools, then the verdict
    assert sup["llm_calls_per_job"] > react["llm_calls_per_job"]                         # hand-offs cost extra model calls
