"""Structured hand-offs (C3).

Agents never pass free text to each other for anything a later step decides on.
Each agent returns one of these Pydantic objects, so a wrong or missing field
fails loudly at the hand-off instead of silently in a later node.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Score = Annotated[float, Field(ge=0.0, le=1.0)]   # a number between 0 and 1


# ---- shared pieces -------------------------------------------------------

class EvidenceItem(BaseModel):
    """One piece of portfolio evidence returned by the Portfolio MCP server."""
    id: str
    type: Literal["cv", "case", "repo", "review", "proposal"]
    source: str                      # file or repo the text came from
    text: str
    title: str = ""
    skills: list[str] = []
    date: str | None = None
    outcome: Literal["won", "replied", "ignored"] | None = None   # proposals only
    score: float = 0.0               # retrieval score


class Requirement(BaseModel):
    text: str
    must_have: bool = True


# ---- Job Analyst ---------------------------------------------------------

class JobSpec(BaseModel):
    job_id: str
    title: str
    category: str = "other"
    deliverables: list[str] = []
    requirements: list[Requirement] = []
    skills: list[str] = []
    budget_min: float | None = None
    budget_max: float | None = None
    budget_type: Literal["fixed", "hourly", "unknown"] = "unknown"
    timeline: str | None = None
    screening_questions: list[str] = []
    hidden_needs: list[str] = []     # things the client wants but did not say outright


# ---- Risk Assessor -------------------------------------------------------

RiskFlag = Literal[
    "scam", "free_work", "off_platform", "prompt_injection",
    "new_client", "low_hire_rate", "unverified_payment", "vague_scope",
]


class RiskReport(BaseModel):
    job_id: str
    risk_score: Score        # 0 = safe, 1 = certain scam
    client_quality: Score    # 0 = bad client, 1 = great client
    flags: list[RiskFlag] = []
    reasons: list[str] = []
    injected_text: str | None = None  # the planted instruction, quoted, if one was found


# ---- Fit Matcher ---------------------------------------------------------

class RequirementMatch(BaseModel):
    requirement: str
    evidence_ids: list[str] = []
    status: Literal["supported", "partly", "unsupported"]
    reason: str = ""


class FitReport(BaseModel):
    job_id: str
    fit_score: Score
    matches: list[RequirementMatch] = []
    reasons: list[str] = []


# ---- Decision node -------------------------------------------------------

class BidDecision(BaseModel):
    job_id: str
    action: Literal["bid", "watch", "skip"]
    reasons: list[str]


# ---- Pricing Strategist --------------------------------------------------

class PriceQuote(BaseModel):
    job_id: str
    amount: float = Field(gt=0)
    price_type: Literal["fixed", "hourly"]
    connects_cost: int = Field(ge=0)
    worth_connects: bool
    rationale: str
    market_low: float | None = None
    market_high: float | None = None


# ---- Proposal Writer + claim verification --------------------------------

class Claim(BaseModel):
    text: str                         # one sentence from the proposal
    evidence_ids: list[str] = []
    status: Literal["supported", "partly", "unsupported", "unchecked"] = "unchecked"


class WriterOutput(BaseModel):
    """What the writer model returns; the node turns it into a ProposalDraft."""
    cover_letter: str
    screening_answers: dict[str, str] = {}
    claims: list[Claim] = []


class VerifiedClaims(BaseModel):
    claims: list[Claim]


class ProposalDraft(BaseModel):
    job_id: str
    cover_letter: str
    screening_answers: dict[str, str] = {}
    claims: list[Claim] = []
    revision: int = 0


# ---- Critic --------------------------------------------------------------

class Critique(BaseModel):
    approved: bool
    grounding_ok: bool
    personalised: bool
    length_ok: bool
    comments: list[str] = []


# ---- Compliance Guard ----------------------------------------------------

class ComplianceVerdict(BaseModel):
    passed: bool
    violations: list[str] = []        # which policy rule was broken, and where
    removed: list[str] = []           # text the guard took out (contacts, guarantees...)
    cleaned_text: str | None = None


# ---- Client Liaison ------------------------------------------------------

Intent = Literal["question", "negotiation", "interview_request", "scam_signal", "other"]


class ReplyDraft(BaseModel):
    thread_id: str
    intent: Intent
    text: str
    interview_slots: list[str] = []
