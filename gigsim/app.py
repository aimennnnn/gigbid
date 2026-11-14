"""GigSim: a small freelance-marketplace simulator (REST API + seed data).

The instructor's GigSim was not distributed with the starter kit, so this is our own
stand-in built to the assignment's description: jobs, clients with histories, Connects,
proposals, messages, rate limits and occasional errors. Each client has hidden
preferences and decides (by a fixed, repeatable rule) whether to reply, interview or hire.

GigBid never imports this package. It only talks to it over HTTP, through the
Marketplace MCP server.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import sqlite3
import threading
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

SEED = Path(__file__).with_name("seed")
GENERIC = ("dear hiring manager", "dear sir", "hello sir", "i am a passionate", "i am very interested", "i hope you are doing well")


def load(name: str):
    return json.loads((SEED / name).read_text(encoding="utf-8"))


class World:
    """All simulator state. Jobs and clients come from seed files; the rest lives in SQLite."""

    def __init__(self) -> None:
        self.policy = load("policy.json")
        self.history = load("jobs_history.json")
        self.stream = load("jobs_stream.json")
        self.jobs = {j["job_id"]: j for j in load("jobs_dev.json") + self.stream}
        self.clients = {c["client_id"]: c for c in load("clients.json")}
        self.hidden = load("hidden.json")
        self.stream_ids = [j["job_id"] for j in self.stream]
        self.lock = threading.Lock()
        self.db = sqlite3.connect(os.getenv("GIGSIM_DB", ":memory:"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            create table if not exists proposals(id text primary key, user text, job_id text, cover_letter text,
                amount real, answers text, status text, connects int, created real);
            create table if not exists messages(id integer primary key autoincrement, thread_id text, user text,
                sender text, text text, created real);
            create table if not exists events(id integer primary key autoincrement, user text, proposal_id text,
                job_id text, type text, created real);
            create table if not exists idem(key text primary key, response text);
            create table if not exists kv(k text primary key, v text);""")
        self.started = time.time()
        self.hits: dict[str, list[float]] = {}
        self.rng = random.Random(7)

    # -- small helpers
    def q(self, sql: str, *args) -> list[dict]:
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return [dict(r) for r in cur.fetchall()]

    def kv(self, key: str, default):
        rows = self.q("select v from kv where k=?", key)
        return json.loads(rows[0]["v"]) if rows else default

    def set_kv(self, key: str, value) -> None:
        self.q("insert or replace into kv values(?,?)", key, json.dumps(value))

    def released(self) -> int:
        """Stream jobs appear over time: some at start, then one per GIGSIM_STREAM_SECONDS."""
        auto = 10 + int((time.time() - self.started) / float(os.getenv("GIGSIM_STREAM_SECONDS", "120")))
        return min(len(self.stream_ids), max(auto, self.kv("released", 0)))

    def visible(self, job_id: str) -> bool:
        return job_id in self.jobs and (job_id not in self.stream_ids or self.stream_ids.index(job_id) < self.released())

    def balance(self, user: str) -> int:
        return self.kv(f"connects:{user}", self.policy["connects"]["weekly_grant"])

    def event(self, user: str, pid: str, job_id: str, kind: str) -> None:
        self.q("insert into events(user,proposal_id,job_id,type,created) values(?,?,?,?,?)", user, pid, job_id, kind, time.time())

    def say(self, thread: str, user: str, sender: str, text: str) -> None:
        self.q("insert into messages(thread_id,user,sender,text,created) values(?,?,?,?,?)", thread, user, sender, text, time.time())


W: World | None = None


def world() -> World:
    global W
    if W is None:
        W = World()
    return W


def reset_world() -> None:
    global W
    W = None


def roll(*parts: str) -> float:
    """A repeatable 'random' number in [0,1): same inputs always give the same answer."""
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def client_score(job: dict, hid: dict, letter: str, amount: float) -> float:
    """How much this job's client likes a proposal, from their hidden preferences."""
    prefs, low = hid["prefs"], letter.lower()
    words = len(letter.split())
    score = 0.3 * sum(s.lower() in low for s in prefs["must_have"]) / len(prefs["must_have"])
    score += 0.2 if amount <= prefs["budget_ceiling"] else -0.3
    score += 0.15 if (not prefs["wants_result"] or re.search(r"\d", letter)) else 0.0
    score += -0.2 if (prefs["dislikes_generic"] and low.lstrip().startswith(GENERIC)) else 0.15
    topic = {w for w in re.findall(r"[a-z]{5,}", job["title"].lower() + " " + job["description"].lower()[:300])}
    score += 0.1 if len(topic & set(re.findall(r"[a-z]{5,}", low))) >= 4 else 0.0
    score += 0.1 if 60 <= words <= W.policy["proposal"]["max_words"] else 0.0
    return max(0.0, min(1.0, score))


def client_decides(user: str, pid: str, job: dict, letter: str, amount: float) -> None:
    w, hid, thread = world(), world().hidden[job["job_id"]], f"t-{pid}"
    r = roll(job["job_id"], hashlib.sha256(letter.encode()).hexdigest(), str(round(amount)))
    if r < 0.9:
        w.event(user, pid, job["job_id"], "viewed")
    if hid["scam"]:
        w.event(user, pid, job["job_id"], "replied")
        w.say(thread, user, "client", "Great profile. Let us continue on WhatsApp +1 555 0100, I will pay you directly outside the platform.")
        return
    p = client_score(job, hid, letter, amount)
    if r >= p:
        if r > 0.95:
            w.event(user, pid, job["job_id"], "lost")
        return
    w.event(user, pid, job["job_id"], "replied")
    if r < p * 0.6:
        w.event(user, pid, job["job_id"], "interview")
        w.say(thread, user, "client", "Thanks, this looks relevant. Can we do a 30 minute call this week? What times work for you?")
    elif amount > hid["true_value"]:
        w.say(thread, user, "client", f"I like the proposal but the price is a bit high for us. Could you do it for ${round(amount * 0.8)}?")
    else:
        w.say(thread, user, "client", "Thanks for the proposal. How exactly would you approach this, and what do you need from us to start?")
    if r < p * 0.3:
        w.set_kv(f"hire:{pid}", True)       # hired after the freelancer answers


# ---------------------------------------------------------------- API

app = FastAPI(title="GigSim", version="1.0")


def tokens() -> dict[str, str]:
    return dict(p.split(":") for p in os.getenv("GIGSIM_TOKENS", "dev-token:reviewer").split(","))


def auth(request: Request, authorization: str = Header(default="")) -> str:
    """Bearer token -> user id, then the per-user rate limit, then the occasional 503."""
    token = authorization.removeprefix("Bearer ").strip()
    user = tokens().get(token) or (token[3:] if token.startswith("gs-") and len(token) > 3 else None)   # gs-<user>: one account per GigBid user
    if not user:
        raise HTTPException(401, "invalid token")
    w, now = world(), time.time()
    limit = int(os.getenv("GIGSIM_RATE_LIMIT", str(w.policy["rate_limit_per_minute"])))
    hits = [t for t in w.hits.get(user, []) if now - t < 60]
    if len(hits) >= limit:
        raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": str(int(60 - (now - hits[0])) + 1)})
    w.hits[user] = hits + [now]
    if w.rng.random() < float(os.getenv("GIGSIM_ERROR_RATE", "0.03")):
        raise HTTPException(503, "temporary marketplace error")
    return user


def idempotent(key: str | None, make):
    """Same Idempotency-Key -> same stored response, and the action runs only once."""
    w = world()
    if key and (rows := w.q("select response from idem where key=?", key)):
        return JSONResponse(json.loads(rows[0]["response"]), headers={"Idempotent-Replay": "true"})
    result = make()
    if key:
        w.q("insert or ignore into idem values(?,?)", key, json.dumps(result))
    return result


@app.get("/health")
def health():
    return {"status": "ok", "service": "gigsim", "policy_version": world().policy["version"]}


@app.get("/policy")
def policy(user: str = Depends(auth)):
    return world().policy


@app.get("/jobs")
def search_jobs(q: str = "", category: str | None = None, posted_after: str | None = None,
                limit: int = 20, offset: int = 0, user: str = Depends(auth)):
    w, terms = world(), [t for t in re.findall(r"\w+", q.lower()) if len(t) > 2]
    found = []
    for j in w.jobs.values():
        if not w.visible(j["job_id"]) or (category and j["category"] != category) or (posted_after and j["posted_at"] < posted_after):
            continue
        text = (j["title"] + " " + j["description"] + " " + " ".join(j["skills"])).lower()
        hits = sum(t in text for t in terms)
        if not terms or hits:
            found.append((hits, j["posted_at"], j))
    found.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return {"total": len(found), "jobs": [j for _, _, j in found[offset:offset + min(limit, 50)]]}


@app.get("/jobs/{job_id}")
def get_job(job_id: str, user: str = Depends(auth)):
    if not world().visible(job_id):
        raise HTTPException(404, "job not found")
    return world().jobs[job_id]


@app.get("/clients/{client_id}")
def get_client(client_id: str, user: str = Depends(auth)):
    if client_id not in world().clients:
        raise HTTPException(404, "client not found")
    return world().clients[client_id]


@app.get("/market/stats")
def market_stats(category: str, skills: str = "", user: str = Depends(auth)):
    """Price statistics from closed historical jobs (what clients actually paid)."""
    want = {s.strip().lower() for s in skills.split(",") if s.strip()}
    rows = [j for j in world().history if j["category"] == category and "hired_amount" in j]
    close = [j for j in rows if want & {s.lower() for s in j["skills"]}] if want else rows
    amounts = sorted(j["hired_amount"] for j in (close if len(close) >= 10 else rows))
    pick = lambda f: amounts[int(f * (len(amounts) - 1))] if amounts else None  # noqa: E731
    return {"category": category, "n": len(amounts), "matched_on_skills": len(close) >= 10,
            "p25": pick(0.25), "p50": pick(0.5), "p75": pick(0.75)}


@app.get("/connects")
def connects(user: str = Depends(auth)):
    return {"balance": world().balance(user), "weekly_grant": world().policy["connects"]["weekly_grant"]}


class ProposalIn(BaseModel):
    job_id: str
    cover_letter: str = Field(min_length=1, max_length=5000)
    amount: float = Field(gt=0)
    screening_answers: dict[str, str] = {}


@app.post("/proposals")
def create_draft(body: ProposalIn, idempotency_key: str | None = Header(default=None), user: str = Depends(auth)):
    w = world()
    if not w.visible(body.job_id):
        raise HTTPException(404, "job not found")

    def make():
        pid = "p-" + hashlib.sha256(f"{user}{body.job_id}{time.time()}".encode()).hexdigest()[:10]
        cost = w.jobs[body.job_id]["connects_cost"]
        w.q("insert into proposals values(?,?,?,?,?,?,?,?,?)", pid, user, body.job_id, body.cover_letter, body.amount,
            json.dumps(body.screening_answers), "draft", cost, time.time())
        w.event(user, pid, body.job_id, "drafted")
        return {"proposal_id": pid, "status": "draft", "connects_cost": cost}
    return idempotent(idempotency_key, make)


@app.post("/proposals/{pid}/submit")
def submit(pid: str, idempotency_key: str | None = Header(default=None), user: str = Depends(auth)):
    w = world()

    def make():
        rows = w.q("select * from proposals where id=? and user=?", pid, user)
        if not rows:
            raise HTTPException(404, "proposal not found")
        p = rows[0]
        if p["status"] != "draft":
            raise HTTPException(409, f"proposal already {p['status']}")
        if len(p["cover_letter"].split()) > w.policy["proposal"]["max_words"]:
            raise HTTPException(422, "cover letter longer than the platform allows")
        left = w.balance(user) - p["connects"]
        if left < 0:
            raise HTTPException(402, "not enough Connects")
        w.set_kv(f"connects:{user}", left)
        w.q("update proposals set status='submitted' where id=?", pid)
        w.event(user, pid, p["job_id"], "submitted")
        client_decides(user, pid, w.jobs[p["job_id"]], p["cover_letter"], p["amount"])
        return {"proposal_id": pid, "status": "submitted", "connects_spent": p["connects"], "connects_balance": left}
    return idempotent(idempotency_key, make)


@app.get("/proposals")
def proposals(user: str = Depends(auth)):
    return w_rows("select id as proposal_id, job_id, amount, status, connects, cover_letter from proposals where user=? order by created", user)


def w_rows(sql: str, *args):
    return world().q(sql, *args)


@app.get("/messages")
def messages(thread_id: str | None = None, user: str = Depends(auth)):
    if thread_id:
        return w_rows("select * from messages where user=? and thread_id=? order by id", user, thread_id)
    return w_rows("select * from messages where user=? order by id", user)


class MessageIn(BaseModel):
    thread_id: str
    text: str = Field(min_length=1, max_length=3000)


@app.post("/messages")
def send_message(body: MessageIn, idempotency_key: str | None = Header(default=None), user: str = Depends(auth)):
    w = world()

    def make():
        pid = body.thread_id.removeprefix("t-")
        rows = w.q("select * from proposals where id=? and user=?", pid, user)
        if not rows:
            raise HTTPException(404, "thread not found")
        w.say(body.thread_id, user, "freelancer", body.text)
        if w.kv(f"hire:{pid}", False):
            w.set_kv(f"hire:{pid}", False)
            w.event(user, pid, rows[0]["job_id"], "hired")
            w.say(body.thread_id, user, "client", "That works for us. I am sending the offer now, welcome aboard.")
        return {"thread_id": body.thread_id, "status": "sent"}
    return idempotent(idempotency_key, make)


@app.get("/events")
def events(since_id: int = 0, user: str = Depends(auth)):
    return w_rows("select * from events where user=? and id>? order by id", user, since_id)


@app.post("/admin/release")
def release(n: int = 5):
    w = world()
    w.set_kv("released", min(len(w.stream_ids), w.released() + n))
    return {"released": w.released()}
