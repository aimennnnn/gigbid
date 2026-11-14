"""Compliance Guard: enforces the policy pack. Rules in code first, then the model.
It removes contact details and guarantees, and can block with a reason the UI shows."""
from pathlib import Path

from agent.guards import scan_text
from agent.handoffs import ComplianceVerdict
from agent.llm import ask
from agent.nodes.base import Deps
from agent.settings import get_settings


def policy_text() -> str:
    folder = Path(get_settings()["rules"]["policy_pack_dir"])
    return "\n\n".join(f.read_text(encoding="utf-8") for f in sorted(folder.glob("*.md")))


async def check(text: str) -> tuple[ComplianceVerdict, int]:
    rules = scan_text(text)
    verdict, tokens = await ask("compliance", {"text": rules["cleaned"], "policy": policy_text()}, ComplianceVerdict)
    verdict.violations = rules["violations"] + rules["blocked"] + [v for v in verdict.violations if v not in rules["violations"] + rules["blocked"]]
    verdict.removed = rules["violations"] + verdict.removed
    verdict.cleaned_text = scan_text(verdict.cleaned_text or rules["cleaned"])["cleaned"]      # the model's rewrite is re-checked too
    verdict.passed = verdict.passed and not rules["blocked"] and bool(verdict.cleaned_text.strip())
    return verdict, tokens


async def run(deps: Deps, state: dict, config: dict) -> dict:
    edited = (state.get("approval") or {}).get("action") == "edit"
    text = state["approval"]["text"] if edited else state["drafts"][-1].cover_letter
    verdict, tokens = await check(text)
    out = {"compliance": verdict, "tokens_used": tokens}
    if not verdict.passed:
        out["status"] = "needs_attention"
        out["errors"] = [f"compliance blocked: {'; '.join(verdict.violations)}"]
    return out
