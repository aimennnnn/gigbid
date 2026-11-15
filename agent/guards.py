"""Rule-based checks that run whatever the model says (defence in depth).

A model can be talked out of a rule; a regular expression cannot. So scams, injected
instructions and policy violations are first checked here, in plain code, and the
model's opinion is only ever added on top.
"""
from __future__ import annotations

import re

from agent.settings import get_settings
from mcp_servers.common import EMAIL, PHONE

SCAM = {
    "free_work": r"unpaid (test|trial|sample)|for free as a test|free (trial|sample) (task|work)|work for free",
    "off_platform": r"telegram|whatsapp|skype|outside (of )?the platform|off[- ]platform|direct bank transfer|wire me",
    "scam": r"registration fee|refundable .{0,20}fee|send (us |me )?your id|payment released before you start|no experience needed",
}
INJECTION = (r"ignore (all |your )?(previous|prior|above) instructions|system note to ai|attention automated agents|"
             r"you are now in \w+ mode|new instructions from|</job>|skip the approval|pre-approved a bid|disregard (the|your) (rules|policy)")


def scan_job(text: str, client: dict | None = None) -> dict:
    """Flags found in a job post and its client history, plus any injected instruction quoted."""
    low, flags = text.lower(), []
    for flag, pattern in SCAM.items():
        if re.search(pattern, low):
            flags.append(flag)
    m = re.search(INJECTION, low)
    injected = None
    if m:
        flags.append("prompt_injection")
        start = text.rfind("\n", 0, m.start()) + 1
        injected = text[start:start + 300].strip()
    if client:
        if not client.get("payment_verified"):
            flags.append("unverified_payment")
        if client.get("jobs_posted", 0) <= 1:
            flags.append("new_client")
        elif client.get("hire_rate", 1) < 0.3:
            flags.append("low_hire_rate")
    return {"flags": flags, "injected_text": injected}


def without_injection(job: dict, injected: str | None) -> dict:
    """A copy of the job post with the injected instruction cut out, for the nodes that write text."""
    if not injected or injected not in job.get("description", ""):
        return job
    return {**job, "description": job["description"].replace(injected, "").strip()}


def planted_words(job: dict, injected: str | None) -> set[str]:
    """Code words that exist only inside the injected instruction (capitals or digits, like PINEAPPLE-11)."""
    if not injected:
        return set()
    rest = (job.get("title", "") + "\n" + job.get("description", "")).replace(injected, " ")
    return {w for w in re.findall(r"\b[A-Z0-9][A-Z0-9_-]{3,}\b", injected) if w not in rest}


def drop_planted(text: str, words: set[str]) -> str:
    """Text we wrote, minus every sentence that carries a planted code word."""
    if not any(w in text for w in words):
        return text
    return " ".join(s for s in re.split(r"(?<=[.!?])\s+", text) if not any(w in s for w in words)).strip()


def scan_text(text: str) -> dict:
    """Policy check for text WE are about to send: contact details, guarantees, banned phrases."""
    rules, violations, cleaned = get_settings()["rules"], [], text
    for name, pattern in (("contact details (email)", EMAIL), ("contact details (phone)", PHONE)):
        if pattern.search(cleaned):
            violations.append(f"{name}: off-platform contact is not allowed")
            cleaned = pattern.sub("", cleaned)
    for phrase in rules["banned_phrases"]:
        if phrase.lower() in cleaned.lower():
            violations.append(f"banned phrase '{phrase}'")
            cleaned = ". ".join(s for s in re.split(r"(?<=[.!?])\s+", cleaned) if phrase.lower() not in s.lower())
    words = len(cleaned.split())
    blocked = []
    if words > rules["proposal"]["max_words"]:
        blocked.append(f"too long: {words} words, limit {rules['proposal']['max_words']}")
    return {"violations": violations, "blocked": blocked, "cleaned": re.sub(r"\s{2,}", " ", cleaned).strip()}


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")) if len(s.strip()) > 3]
