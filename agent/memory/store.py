"""Long-term memory on a LangGraph store (InMemoryStore in tests, PostgresStore in Docker).

Two memories per user:
  style    - rules learned from the user's own edits ("never say 'passionate'")
  outcome  - what got replies or hires, per job category
Candidates are counted first and only promoted by agent/memory/promotion_rules.py.
"""
from __future__ import annotations

from langgraph.store.base import BaseStore

from agent.memory.promotion_rules import should_promote_style, should_trust_outcomes, style_rule_from_edit


async def record_edit(store: BaseStore, user: str, before: str, after: str) -> str | None:
    """Count this edit as a candidate. Returns the rule if this edit got it promoted."""
    rule = style_rule_from_edit(before, after)
    if not rule:
        return None
    item = await store.aget((user, "style_candidates"), rule)
    seen = (item.value["seen"] if item else 0) + 1
    await store.aput((user, "style_candidates"), rule, {"seen": seen})
    if should_promote_style(seen) and not await store.aget((user, "style"), rule):
        await store.aput((user, "style"), rule, {"rule": rule, "seen": seen, "source": "user edits"})
        return rule
    return None


async def style_rules(store: BaseStore, user: str) -> list[str]:
    return [i.value["rule"] for i in await store.asearch((user, "style"))]


async def record_outcome(store: BaseStore, user: str, category: str, event: str) -> None:
    """event: submitted | replied | hired. Raw events never go in; only these counters do."""
    item = await store.aget((user, "outcome"), category)
    v = item.value if item else {"category": category, "submitted": 0, "replied": 0, "hired": 0}
    if event in v:
        v[event] += 1
        await store.aput((user, "outcome"), category, v)


async def outcome_notes(store: BaseStore, user: str, category: str) -> list[str]:
    item = await store.aget((user, "outcome"), category)
    if not item or not should_trust_outcomes(item.value["submitted"]):
        return []
    v = item.value
    return [f"In {category} jobs, {v['replied']} of {v['submitted']} of your proposals got a reply and {v['hired']} were hired."]


async def all_memories(store: BaseStore, user: str) -> list[dict]:
    """For the Settings screen: everything GigBid has learned, each deletable."""
    out = [{"kind": "style", "key": i.key, **i.value} for i in await store.asearch((user, "style"))]
    return out + [{"kind": "outcome", "key": i.key, **i.value} for i in await store.asearch((user, "outcome"))]


async def forget(store: BaseStore, user: str, kind: str, key: str) -> None:
    await store.adelete((user, kind), key)
    if kind == "style":
        await store.adelete((user, "style_candidates"), key)
