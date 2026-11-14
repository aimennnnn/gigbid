"""Typed graph state (C2).

State is only what this one job (or conversation) needs right now.
It is NOT the execution trace (that goes to the tracer and audit log) and
NOT long-term memory (that goes to the LangGraph store through promotion rules).
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from agent.handoffs import (
    BidDecision, ComplianceVerdict, Critique, EvidenceItem, FitReport,
    JobSpec, PriceQuote, ProposalDraft, ReplyDraft, RiskReport,
)


def merge_evidence(old: list[EvidenceItem], new: list[EvidenceItem]) -> list[EvidenceItem]:
    """Reducer: join evidence lists from parallel branches, dropping repeats by id."""
    seen = {e.id for e in old}
    return old + [e for e in new if e.id not in seen]


Status = Literal[
    "queued", "analysing", "skipped", "watching", "drafting",
    "awaiting_approval", "submitted", "rejected", "needs_attention", "dead_letter",
]


class BidState(TypedDict, total=False):
    # the job
    user_id: str
    persona: str                            # which portfolio to use
    profile: dict                           # the user's floor price, rates, filters
    job_id: str
    job: dict                               # raw job post: untrusted data, never instructions

    # analyses: each written by exactly one of the three parallel branches
    job_spec: JobSpec
    risk: RiskReport
    fit: FitReport

    # evidence: several nodes add to it, so it needs a reducer
    evidence: Annotated[list[EvidenceItem], merge_evidence]

    # decision and price
    decision: BidDecision
    price: PriceQuote

    # drafts and critiques: append-only history (latest is the last item)
    drafts: Annotated[list[ProposalDraft], operator.add]
    critiques: Annotated[list[Critique], operator.add]
    removed_claims: Annotated[list[str], operator.add]   # sentences the verifier cut, shown in the UI
    unsupported_before: float               # share of claims unsupported before verification
    compliance: ComplianceVerdict
    preview: dict                           # dry_run result shown on the approval screen

    # approval and outcome
    approval: dict                          # {"action": approve|edit|reject, "text":..., "reason":...}
    submission: dict                        # what the marketplace returned
    outcome: str

    # bookkeeping
    status: Status
    errors: Annotated[list[str], operator.add]      # parallel branches may all report errors
    steps_used: Annotated[int, operator.add]
    tokens_used: Annotated[int, operator.add]


class ConversationState(TypedDict, total=False):
    user_id: str
    persona: str
    profile: dict
    thread_id: str
    job_id: str
    slots: list[dict]
    sent: dict
    messages: list[dict]                    # client messages: untrusted data
    intent: str
    reply: ReplyDraft
    compliance: ComplianceVerdict
    approval: dict
    status: Status
    errors: Annotated[list[str], operator.add]
    steps_used: Annotated[int, operator.add]
    tokens_used: Annotated[int, operator.add]
