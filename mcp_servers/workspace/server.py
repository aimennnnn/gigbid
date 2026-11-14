"""Workspace MCP server (A3): calendar slots, tentative interview holds, email drafts.

This is a documented local mock: the calendar and drafts live in one JSON file instead
of Google Calendar and Gmail. Agents cannot tell the difference, because they only ever
see these MCP tools. Nothing here sends anything: holds are tentative, emails are drafts.

Run:  python -m mcp_servers.workspace.server
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from mcp_servers.common import AuditLog, BearerAuth, caller

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
DRAFT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
IdemKey = Annotated[str, Field(min_length=8, max_length=128, description="Unique key; reusing it returns the first result")]


class Slot(BaseModel):
    start: str = Field(description="ISO datetime, Asia/Karachi local time")
    end: str


class SlotList(BaseModel):
    slots: list[Slot]


class Hold(BaseModel):
    hold_id: str
    start: str
    end: str
    title: str
    status: str = "tentative"
    replayed: bool = False


class EmailDraft(BaseModel):
    draft_id: str
    to: str
    subject: str
    body: str
    status: str = "draft"
    replayed: bool = False


def build_server(store_path: str = "data/processed/workspace.json",
                 audit_path: str = "data/processed/audit/workspace.jsonl", **fastmcp_kw) -> FastMCP:
    mcp = FastMCP("gigbid-workspace", instructions="Calendar availability, tentative interview holds and email drafts. Never sends anything.", **fastmcp_kw)
    store, audit = Path(store_path), AuditLog(audit_path)

    def load(user: str) -> tuple[dict, dict]:
        data = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
        return data, data.setdefault(user, {"holds": {}, "drafts": {}})

    def save(data: dict) -> None:
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def busy(user: str, start: datetime) -> bool:
        """The mock calendar: a repeatable set of 'existing meetings' per user."""
        return int(hashlib.sha256(f"{user}{start.isoformat()}".encode()).hexdigest(), 16) % 3 == 0

    @mcp.tool(annotations=READ)
    def get_free_slots(ctx: Context,
                       date_from: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$", description="First day to look at, YYYY-MM-DD")],
                       days: Annotated[int, Field(ge=1, le=14)] = 5,
                       duration_minutes: Annotated[int, Field(ge=15, le=120)] = 30) -> SlotList:
        """Free calendar slots on working days, 10:00 to 18:00, that do not clash with meetings or holds."""
        user, trace = caller(ctx)
        _, mine = load(user)
        taken = {h["start"] for h in mine["holds"].values()}
        slots, d = [], datetime.fromisoformat(date_from)
        for offset in range(days):
            cur = d + timedelta(days=offset)
            if cur.weekday() >= 5:
                continue
            t = datetime.combine(cur.date(), time(10, 0))
            while t + timedelta(minutes=duration_minutes) <= datetime.combine(cur.date(), time(18, 0)):
                if not busy(user, t) and t.isoformat() not in taken:
                    slots.append(Slot(start=t.isoformat(), end=(t + timedelta(minutes=duration_minutes)).isoformat()))
                t += timedelta(hours=1)
        audit.write(user, "get_free_slots", {"date_from": date_from, "days": days}, {"count": len(slots)}, trace)
        return SlotList(slots=slots[:12])

    @mcp.tool(annotations=DRAFT)
    def create_interview_hold(ctx: Context,
                              start: Annotated[str, Field(description="Slot start from get_free_slots (ISO datetime)")],
                              title: Annotated[str, Field(min_length=3, max_length=120)],
                              idempotency_key: IdemKey,
                              duration_minutes: Annotated[int, Field(ge=15, le=120)] = 30) -> Hold:
        """Put a TENTATIVE hold on the calendar for an interview. It is not an invite and nobody is notified."""
        user, trace = caller(ctx)
        data, mine = load(user)
        if idempotency_key in mine["holds"]:
            return Hold(**mine["holds"][idempotency_key], replayed=True)
        begin = datetime.fromisoformat(start)
        if any(h["start"] == begin.isoformat() for h in mine["holds"].values()) or busy(user, begin):
            raise ValueError("that slot is no longer free; call get_free_slots again")
        hold = Hold(hold_id="hold-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:8], start=begin.isoformat(),
                    end=(begin + timedelta(minutes=duration_minutes)).isoformat(), title=title)
        mine["holds"][idempotency_key] = hold.model_dump(exclude={"replayed"})
        save(data)
        audit.write(user, "create_interview_hold", {"start": start, "title": title}, hold.model_dump(), trace)
        return hold

    @mcp.tool(annotations=DRAFT)
    def create_email_draft(ctx: Context,
                           to: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Recipient email address")],
                           subject: Annotated[str, Field(min_length=1, max_length=200)],
                           body: Annotated[str, Field(min_length=1, max_length=5000)],
                           idempotency_key: IdemKey) -> EmailDraft:
        """Save an email as a DRAFT. It is never sent; the user sends it themselves."""
        user, trace = caller(ctx)
        data, mine = load(user)
        if idempotency_key in mine["drafts"]:
            return EmailDraft(**mine["drafts"][idempotency_key], replayed=True)
        draft = EmailDraft(draft_id="mail-" + hashlib.sha256(idempotency_key.encode()).hexdigest()[:8], to=to, subject=subject, body=body)
        mine["drafts"][idempotency_key] = draft.model_dump(exclude={"replayed"})
        save(data)
        audit.write(user, "create_email_draft", {"to": to, "subject": subject}, {"draft_id": draft.draft_id}, trace)
        return draft

    return mcp


def http_app():
    return BearerAuth(build_server(host="0.0.0.0", stateless_http=True, json_response=True).streamable_http_app())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(http_app(), host="0.0.0.0", port=int(os.getenv("PORT", "8103")))
