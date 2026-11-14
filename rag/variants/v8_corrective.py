"""V8 corrective retrieval: a small LangGraph loop that checks its own evidence.

    retrieve -> grade --(enough good evidence, or out of tries)--> END
                  \\--(weak or none)--> retrieve again, a different way

- grade: the reranker scores every hit against the query; hits under corrective.min_score are dropped.
- re-query: try 1 searches by exact keywords (BM25), try 2 searches a pool of candidates twice as wide.
- refuse: if nothing passes after the last try, the answer is an empty list. Empty means
  "the portfolio does not prove this", so the writer has nothing to build a claim on.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Callable, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.settings import get_settings
from rag.variants import v3_rerank

HOW = ["normal", "keyword", "wide"]       # how each try searches


class State(TypedDict, total=False):
    query: str
    tries: int
    found: list[tuple[dict, float]]       # what the latest search returned
    kept: list[tuple[dict, float]]        # evidence that passed the grade, over all tries


def retrieve(state: State, config: RunnableConfig) -> dict:
    run = config["configurable"]["run"]                      # the variant's own search, passed in by the retriever
    return {"found": run(state["query"], HOW[state.get("tries", 0)])}


def grade(state: State) -> dict:
    cfg = get_settings()["rag"]["corrective"]
    kept, have = list(state.get("kept", [])), {item["id"] for item, _ in state.get("kept", [])}
    marks = v3_rerank.scores(state["query"], [item for item, _ in state["found"]])
    for (item, score), mark in zip(state["found"], marks):
        if mark >= cfg["min_score"] and item["id"] not in have:
            kept.append((item, score))
    return {"kept": kept, "tries": state.get("tries", 0) + 1}


def enough(state: State) -> str:
    cfg = get_settings()["rag"]["corrective"]
    done = len(state["kept"]) >= cfg["min_keep"] or state["tries"] > cfg["max_requeries"] or state["tries"] >= len(HOW)
    return END if done else "retrieve"


@lru_cache
def graph():
    g = StateGraph(State)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", enough, ["retrieve", END])
    return g.compile()


def search(query: str, run: Callable[[str, str], list[tuple[dict, float]]]) -> list[tuple[dict, float]]:
    """run(query, how) is one plain search. Returns only evidence that passed the grade (may be empty)."""
    return graph().invoke({"query": query, "tries": 0, "kept": []}, {"configurable": {"run": run}})["kept"]
