"""The three analysis agents run in parallel and write to the same state.
This proves the reducers merge their writes instead of crashing or overwriting."""
from langgraph.graph import END, START, StateGraph

from agent.handoffs import EvidenceItem, FitReport, JobSpec, RiskReport
from agent.state import BidState, merge_evidence


def ev(i):
    return EvidenceItem(id=i, type="case_study", source="x.md", text="t")


def test_merge_evidence_drops_duplicates():
    assert [e.id for e in merge_evidence([ev("a")], [ev("a"), ev("b")])] == ["a", "b"]


def test_parallel_branches_merge_into_one_state():
    def analyst(s):
        return {"job_spec": JobSpec(job_id="j1", title="t"), "steps_used": 1}

    def risk(s):
        return {"risk": RiskReport(job_id="j1", risk_score=0.1, client_quality=0.9),
                "steps_used": 1, "errors": ["risk: slow"]}

    def matcher(s):
        return {"fit": FitReport(job_id="j1", fit_score=0.8), "evidence": [ev("a"), ev("b")],
                "steps_used": 1}

    g = StateGraph(BidState)
    for name, fn in [("analyst", analyst), ("risk", risk), ("matcher", matcher)]:
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    out = g.compile().invoke({"job_id": "j1", "evidence": [ev("a")]})

    assert out["job_spec"].title == "t" and out["risk"].risk_score == 0.1 and out["fit"].fit_score == 0.8
    assert [e.id for e in out["evidence"]] == ["a", "b"]
    assert out["steps_used"] == 3 and out["errors"] == ["risk: slow"]
