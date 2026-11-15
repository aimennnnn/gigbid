"""Request and response models. The TypeScript client in apps/web/src/lib/api is generated from these."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    username: str
    password: str


class Session(BaseModel):
    token: str
    user: str
    onboarded: bool


class Profile(BaseModel):
    persona: Literal["ml", "web", "data"] | None = None
    min_budget: float = Field(default=400, ge=0)
    weekly_connects_budget: int = Field(default=60, ge=0)
    categories: list[Literal["ml", "web", "data"]] = []
    saved_searches: list[str] = []
    autonomy: Literal["approve_everything"] = "approve_everything"      # GigBid can never send without approval
    marketplace: Literal["gigsim"] = "gigsim"


class Me(BaseModel):
    user: str
    profile: Profile
    connects_balance: int | None = None
    connects_spent: int = 0


class InboxJob(BaseModel):
    job_id: str
    title: str
    category: str
    budget_min: float | None = None
    budget_max: float | None = None
    posted_at: str | None = None
    connects_cost: int | None = None
    state: Literal["new", "analysing", "analysed", "skipped_by_you"]
    status: str | None = None                 # the graph's status: skipped, awaiting_approval, submitted, ...
    thread_id: str | None = None
    fit: float | None = None
    risk: float | None = None
    risk_flags: list[str] = []
    action: Literal["bid", "watch", "skip"] | None = None
    price: float | None = None
    reasons: list[str] = []


class Inbox(BaseModel):
    jobs: list[InboxJob]
    total: int


class RunSummary(BaseModel):
    thread_id: str
    kind: str
    job_id: str
    persona: str
    started: float
    running: bool
    steps: int


class RunEvent(BaseModel):
    seq: int
    at: float
    node: str
    seconds: float | None = None
    status: str | None = None
    errors: list[str] = []
    tokens: int = 0
    waiting: bool = False
    done: bool = False


class TraceLine(BaseModel):
    server: str
    ts: float
    tool: str
    arguments: Any = None
    result: Any = None


class RunDetail(BaseModel):
    run: RunSummary
    events: list[RunEvent]
    trace_id: str
    trace: list[TraceLine]
    status: str | None = None
    tokens: int = 0


class JobDetail(BaseModel):
    """Everything the job detail screen shows. The inner objects are the agents' hand-offs (agent/handoffs.py)."""
    job: dict[str, Any]
    thread_id: str | None = None
    running: bool = False
    status: str | None = None
    job_spec: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    fit: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = []
    price: dict[str, Any] | None = None
    decision: dict[str, Any] | None = None
    errors: list[str] = []


class Studio(BaseModel):
    """The proposal studio: the pending approval payload, or the final state once it is decided."""
    thread_id: str
    job_id: str
    job_title: str
    running: bool
    status: str | None = None
    pending: bool
    draft: str | None = None
    screening_answers: dict[str, str] = {}
    claims: list[dict[str, Any]] = []
    evidence: dict[str, dict[str, Any]] = {}
    removed_claims: list[str] = []
    risk: dict[str, Any] | None = None
    price: dict[str, Any] | None = None
    critique: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None
    dry_run: dict[str, Any] | None = None
    submission: dict[str, Any] | None = None
    outcome: str | None = None
    errors: list[str] = []


class ApprovalIn(BaseModel):
    action: Literal["approve", "edit", "reject"]
    text: str | None = Field(default=None, max_length=5000)       # the edited letter, for "edit"
    reason: str | None = Field(default=None, max_length=500)      # why, for "reject"


class Started(BaseModel):
    thread_id: str
    running: bool


class Card(BaseModel):
    thread_id: str
    job_id: str
    title: str
    category: str
    amount: float | None = None
    stage: str
    events: list[str] = []


class Pipeline(BaseModel):
    stages: list[str]
    cards: list[Card]


class ChatMessage(BaseModel):
    sender: str
    text: str
    created: float | None = None


class Suggested(BaseModel):
    thread_id: str
    running: bool
    pending: bool
    status: str | None = None
    intent: str | None = None
    draft: str | None = None
    interview_slots: list[str] = []
    compliance: dict[str, Any] | None = None
    errors: list[str] = []


class Conversation(BaseModel):
    thread_id: str
    job_id: str
    title: str
    messages: list[ChatMessage]
    needs_reply: bool
    suggested: Suggested | None = None


class Conversations(BaseModel):
    threads: list[Conversation]


class CategoryStats(BaseModel):
    category: str
    submitted: int
    replied: int
    hired: int
    reply_rate: float | None = None
    hire_rate: float | None = None


class Analytics(BaseModel):
    by_category: list[CategoryStats]
    connects_spent: int
    replies: int
    hires: int
    proposals: int
    tokens_per_proposal: float | None = None
    seconds_per_proposal: float | None = None
    top_rejection_reasons: list[tuple[str, int]]


class Memory(BaseModel):
    kind: str
    key: str
    text: str


class Memories(BaseModel):
    items: list[Memory]


class Health(BaseModel):
    ok: bool
    marketplace: Literal["ok", "unavailable"]
    degraded: dict[str, str] = {}
    llm: str
