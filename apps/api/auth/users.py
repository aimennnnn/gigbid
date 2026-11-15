"""Users, sessions and profiles.

Multi-user: anyone can sign up; each user gets their own GigSim account, their own graph threads
and their own memory namespace. Passwords are stored as scrypt hashes in one JSON file.
A reviewer account is created at start-up (password from REVIEWER_PASSWORD, default "reviewer")
with the ML persona preloaded.

Not built: OAuth to live Upwork and the encrypted token store. GigSim needs no OAuth.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from pathlib import Path

from fastapi import Header, HTTPException

PERSONAS = ("ml", "web", "data")
DEFAULT_PROFILE = {"persona": None, "min_budget": 400, "weekly_connects_budget": 60, "categories": [], "saved_searches": [],
                   "autonomy": "approve_everything", "marketplace": "gigsim"}


class Users:
    def __init__(self, path: Path):
        self.path, self.sessions = path, {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.users: dict[str, dict] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if "reviewer" not in self.users:
            self.add("reviewer", os.getenv("REVIEWER_PASSWORD", "reviewer"), persona="ml")

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.users, indent=1), encoding="utf-8")

    @staticmethod
    def _hash(password: str, salt: str) -> str:
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1).hex()

    def add(self, name: str, password: str, persona: str | None = None) -> None:
        if not re.fullmatch(r"[a-z0-9_-]{3,24}", name):
            raise HTTPException(422, "user name: 3 to 24 lower-case letters, digits, - or _")
        if name in self.users:
            raise HTTPException(409, "that user name is taken")
        if len(password) < 6:
            raise HTTPException(422, "password: at least 6 characters")
        salt = secrets.token_hex(16)
        self.users[name] = {"salt": salt, "hash": self._hash(password, salt), "profile": DEFAULT_PROFILE | {"persona": persona}}
        self._save()

    def login(self, name: str, password: str) -> str:
        u = self.users.get(name)
        if not u or not secrets.compare_digest(u["hash"], self._hash(password, u["salt"])):
            raise HTTPException(401, "wrong user name or password")
        token = secrets.token_urlsafe(24)
        self.sessions[token] = name
        return token

    def profile(self, name: str) -> dict:
        return DEFAULT_PROFILE | self.users[name]["profile"]

    def set_profile(self, name: str, changes: dict) -> dict:
        self.users[name]["profile"] = self.profile(name) | changes
        self._save()
        return self.profile(name)


_users: Users | None = None


def users() -> Users:
    global _users
    if _users is None:
        from apps.api.runtime import STATE_DIR
        _users = Users(STATE_DIR / "users.json")
    return _users


def reset_users() -> None:
    global _users
    _users = None


def current_user(authorization: str = Header(default="")) -> str:
    """FastAPI dependency: Bearer session token -> user name. Every query below is scoped by this name."""
    user = users().sessions.get(authorization.removeprefix("Bearer ").strip())
    if not user:
        raise HTTPException(401, "sign in first")
    return user


def onboarded(user: str) -> dict:
    """The user's profile, or 409 if they have not picked a persona yet."""
    profile = users().profile(user)
    if profile["persona"] not in PERSONAS:
        raise HTTPException(409, "finish onboarding first: pick a persona")
    return profile
