"""Loaders (B1): read one persona's portfolio folder into evidence items.

One item = one thing a freelancer could point at: the CV, a case study, a repo,
a client review or a past proposal. Every item carries metadata (persona, type,
project, skills, date, client industry and, for proposals, the outcome).
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

PERSONAS_DIR = Path(os.getenv("PERSONAS_DIR", Path(__file__).resolve().parents[2] / "data" / "personas"))


def _front_matter(text: str) -> tuple[dict, str]:
    """Split '---\\nkey: value\\n---\\nbody' into (metadata, body)."""
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        return {}, text
    meta = dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)
    if "skills" in meta:
        meta["skills"] = [s.strip() for s in meta["skills"].strip("[]").split(",")]
    return meta, m.group(2)


def _item(persona, kind, key, title, text, source, **meta) -> dict:
    return {"id": f"{persona}:{kind}:{key}", "persona": persona, "type": kind, "title": title, "text": text.strip(),
            "source": source, "project": meta.get("project"), "skills": meta.get("skills", []),
            "date": meta.get("date"), "client_industry": meta.get("client_industry"),
            "outcome": meta.get("outcome"), "parts": meta.get("parts", {})}


@lru_cache
def load_items(persona: str) -> tuple[dict, ...]:
    base = PERSONAS_DIR / persona
    if not base.is_dir():
        raise FileNotFoundError(f"no portfolio for persona '{persona}' in {PERSONAS_DIR}")
    items = [_item(persona, "cv", "cv", "CV", (base / "cv.md").read_text(encoding="utf-8"), "cv.md")]
    for f in sorted((base / "case_studies").glob("*.md")):
        meta, body = _front_matter(f.read_text(encoding="utf-8"))
        items.append(_item(persona, "case", f.stem, body.splitlines()[0].lstrip("# "), body,
                           f"case_studies/{f.name}", project=f.stem, **{k: meta.get(k) for k in ("skills", "date", "client_industry")}))
    for d in sorted(p for p in (base / "repos").glob("*") if p.is_dir()):
        parts = {str(f.relative_to(d)).replace("\\", "/"): f.read_text(encoding="utf-8") for f in sorted(d.rglob("*")) if f.is_file()}
        text = "\n\n".join(f"## {name}\n{body}" for name, body in parts.items())
        items.append(_item(persona, "repo", d.name, f"Repository {d.name}", text, f"repos/{d.name}", project=d.name, parts=parts))
    for r in json.loads((base / "reviews.json").read_text(encoding="utf-8")):
        items.append(_item(persona, "review", r["id"], f"Client review ({r['rating']}/5)", r["text"], "reviews.json",
                           project=r["project"], date=r["date"], client_industry=r["client_industry"]))
    for p in json.loads((base / "past_proposals.json").read_text(encoding="utf-8")):
        items.append(_item(persona, "proposal", p["id"], f"Past proposal: {p['job_title']}", p["text"], "past_proposals.json",
                           project=p["project"], date=p["date"], client_industry=p["client_industry"], outcome=p["outcome"]))
    return tuple(items)


def get_item(item_id: str) -> dict | None:
    persona = item_id.split(":", 1)[0]
    try:
        return next((i for i in load_items(persona) if i["id"] == item_id), None)
    except FileNotFoundError:
        return None


def list_personas() -> list[str]:
    return sorted(p.name for p in PERSONAS_DIR.iterdir() if (p / "cv.md").exists())
