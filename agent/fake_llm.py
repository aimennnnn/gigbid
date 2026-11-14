"""Rule-based stand-ins for every model call. Used when GIGBID_LLM=fake (tests, CI, and
as a zero-cost baseline). Each function takes the same variables the real prompt gets
and returns a dict in the same schema."""
from __future__ import annotations

import re

from agent.guards import scan_text, sentences

WORD = re.compile(r"[a-z0-9][a-z0-9+#.\-]*")


def _words(text: str) -> set[str]:
    return {w for w in WORD.findall(text.lower()) if len(w) > 2}


def analyst(v: dict) -> dict:
    job = v["job_post"]
    skills = job.get("skills") or []
    reqs = [f"Experience with {s}" for s in skills] or [s for s in sentences(job["description"]) if "want" in s.lower()][:2]
    b = job.get("budget", {})
    return {"job_id": job["job_id"], "title": job["title"], "category": job.get("category", "other"),
            "deliverables": [job["title"]], "requirements": [{"text": r, "must_have": True} for r in reqs],
            "skills": skills, "budget_min": b.get("min"), "budget_max": b.get("max"), "budget_type": b.get("type", "unknown"),
            "timeline": f"{job.get('duration_days', '?')} days", "screening_questions": job.get("screening_questions", [])}


def risk(v: dict) -> dict:
    flags = v["rule_findings"]["flags"]
    bad = {"scam": 0.9, "free_work": 0.8, "off_platform": 0.85, "prompt_injection": 0.5, "unverified_payment": 0.3, "new_client": 0.2, "low_hire_rate": 0.25}
    score = max([bad.get(f, 0.1) for f in flags], default=0.05)
    c = v.get("client_history") or {}
    quality = 0.2 if not c.get("payment_verified") else min(1.0, 0.4 + 0.6 * c.get("hire_rate", 0.5))
    return {"job_id": v["job_post"]["job_id"], "risk_score": score, "client_quality": round(quality, 2), "flags": flags,
            "reasons": [f"rule check found: {f}" for f in flags] or ["no warning signs found"],
            "injected_text": v["rule_findings"]["injected_text"]}


def matcher(v: dict) -> dict:
    matches, by_id = [], {e["id"]: e for e in v["evidence"]}
    for r in v["requirements"]:
        want = _words(r["requirement"]) - {"experience", "with", "want"}
        cands = [by_id[i] for i in r["candidate_ids"]]
        good = [e["id"] for e in cands if e["type"] != "proposal" and len(want & _words(e["title"] + " " + e["text"] + " " + " ".join(e.get("skills", [])))) >= max(1, len(want) // 2)]
        status = "supported" if good else "unsupported"
        matches.append({"requirement": r["requirement"], "evidence_ids": good[:3], "status": status,
                        "reason": f"{len(good)} evidence item(s) mention this"})
    done = sum(m["status"] == "supported" for m in matches)
    return {"job_id": v["job_id"], "fit_score": round(done / max(1, len(matches)), 2), "matches": matches,
            "reasons": [f"{done} of {len(matches)} requirements have portfolio evidence"]}


def writer(v: dict) -> dict:
    job, ev = v["job_post"], [e for e in v["evidence"] if e["type"] in ("case", "review", "repo")]
    opening = f"You are looking for help with: {job['title'].lower()}."
    claims, body = [], []
    for e in ev[:1]:
        result = next((re.sub(r"^[#\s]*(Result|Notes)\s+", "", s) for s in sentences(e["text"]) if re.search(r"\d", s) and "date" not in s.lower()), None)
        if result:
            body.append(f"On a similar project, {result[0].lower() + result[1:]}")
            claims.append({"text": body[-1], "evidence_ids": [e["id"]]})
    skills = ", ".join(v["job_spec"].get("skills", [])[:3])
    if skills and ev:
        body.append(f"My work on that project used {skills}.")
        claims.append({"text": body[-1], "evidence_ids": [ev[0]["id"]]})
    close = "What does success look like for you in the first month?"
    letter = " ".join([opening, *body, f"I can deliver this for ${v['price']['amount']:.0f}.", close])
    if any("cut the first sentence" in r for r in v.get("style_rules", [])):
        letter = letter.split(". ", 1)[-1]
    return {"cover_letter": letter, "claims": claims,
            "screening_answers": {q: (body[0] if body else "I would start by agreeing a success measure with you.") for q in v.get("screening_questions", [])}}


def verifier(v: dict) -> dict:
    out, text = [], {e["id"]: e["text"].lower() for e in v["evidence"]}
    for c in v["claims"]:
        nums = re.findall(r"\d[\d,.]*%?", c["text"])
        cited = [i for i in c.get("evidence_ids", []) if i in text]
        hit = [i for i in cited if all(n.rstrip(".,").lower() in text[i] for n in nums)]
        overlap = [i for i in cited if len(_words(c["text"]) & _words(text[i])) >= 3]
        status = "supported" if hit and (nums or overlap) else "partly" if overlap else "unsupported"
        out.append({"text": c["text"], "evidence_ids": hit or overlap, "status": status})
    return {"claims": out}


def critic(v: dict) -> dict:
    letter, lim = v["draft"]["cover_letter"], v["word_limits"]
    grounded = all(c["status"] == "supported" for c in v["draft"]["claims"])
    personal = len(_words(v["job_post"]["title"]) & _words(letter)) >= 2
    n = len(letter.split())
    length = n <= lim["max_words"]
    comments = ([] if grounded else ["remove or fix claims that are not supported"]) + ([] if personal else ["open with the client's problem"]) \
        + ([] if length else [f"too long ({n} words)"])
    return {"approved": grounded and personal and length, "grounding_ok": grounded, "personalised": personal, "length_ok": length, "comments": comments}


def compliance(v: dict) -> dict:
    r = scan_text(v["text"])
    return {"passed": not r["blocked"], "violations": r["violations"] + r["blocked"], "removed": r["violations"], "cleaned_text": r["cleaned"]}


def liaison(v: dict) -> dict:
    last = next((m["text"] for m in reversed(v["messages"]) if m["sender"] == "client"), "").lower()
    if re.search(r"whatsapp|telegram|outside the platform|pay you directly", last):
        intent, text = "scam_signal", "Thanks, but I keep all communication and payment on the platform. Happy to continue here."
    elif re.search(r"\bcall\b|interview|what times|meet", last):
        slots = v.get("slots", [])[:3]
        intent, text = "interview_request", "Happy to talk. I am free at: " + "; ".join(s["start"].replace("T", " ")[:16] for s in slots) + " (Pakistan time). Which suits you?"
    elif re.search(r"price|budget|could you do it for|\$\d", last):
        intent, text = "negotiation", f"I understand the budget concern. The lowest I can do for this scope is ${v['price_floor']:.0f}; I can also reduce scope to fit a smaller budget."
    elif "?" in last:
        intent, text = "question", "Good question. I would start with a short discovery call, agree the success measure, then deliver in weekly steps."
    else:
        intent, text = "other", "Thanks for the update. Let me know how you would like to proceed."
    return {"thread_id": v["thread_id"], "intent": intent, "text": text,
            "interview_slots": [s["start"] for s in v.get("slots", [])[:3]] if intent == "interview_request" else []}
