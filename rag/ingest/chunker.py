"""Chunker (B1): cut one evidence item into fixed-size pieces of text.

Every chunk keeps the item's metadata (persona, type, project, skills, date, client
industry, outcome), so a search can filter on it and a hit can be traced to its item.
"""
from __future__ import annotations

META = ("persona", "type", "project", "skills", "date", "client_industry", "outcome")


def chunks(item: dict, size: int, overlap: int) -> list[dict]:
    """Fixed chunks of `size` words; each one repeats the last `overlap` words of the one before."""
    words, step, out = item["text"].split(), size - overlap, []
    for n, start in enumerate(range(0, max(len(words) - overlap, 1), step)):
        out.append({"id": f"{item['id']}#{n}", "item_id": item["id"], "text": " ".join(words[start:start + size]),
                    **{k: item[k] for k in META}})
    return out
