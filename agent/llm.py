"""The one place models are called.

`ask(node, variables, Schema)` loads that node's prompt file, calls the model the
config assigns to that node, and returns a validated Pydantic object plus the tokens used.
Untrusted text (job posts, client messages) is always wrapped in <untrusted_...> tags.

GIGBID_LLM=fake swaps the model for simple rules (agent/fake_llm.py), so tests and CI
run with no API key and no network.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from agent.settings import get_settings

PROMPTS = Path(__file__).with_name("prompts")
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


def render(variables: dict, untrusted: tuple[str, ...]) -> str:
    """Each variable becomes a tagged block; untrusted ones get an <untrusted_...> tag."""
    blocks = []
    for name, value in variables.items():
        text = value if isinstance(value, str) else json.dumps(value, indent=1, default=str)
        if name in untrusted:
            text = text.replace("</untrusted_", "<\\/untrusted_")       # the text cannot close its own tag
            blocks.append(f"<untrusted_{name}>\n{text}\n</untrusted_{name}>")
        else:
            blocks.append(f"<{name}>\n{text}\n</{name}>")
    return "\n\n".join(blocks)


async def _chat(model: str, system: str, user: str, timeout: float) -> tuple[str, int]:
    profile = get_settings().profile
    key = os.getenv(profile["api_key_env"], "")
    if not key:
        raise LLMError(f"{profile['api_key_env']} is not set")
    async with httpx.AsyncClient(timeout=timeout) as http:
        r = await http.post(f"{profile['base_url']}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                            json={"model": model, "temperature": 0.2, "response_format": {"type": "json_object"},
                                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    if r.status_code >= 400:
        raise LLMError(f"model call failed ({r.status_code}): {r.text[:200]}")
    body = r.json()
    return body["choices"][0]["message"]["content"], body.get("usage", {}).get("total_tokens", 0)


async def ask(node: str, variables: dict, schema: type[T], untrusted: tuple[str, ...] = ()) -> tuple[T, int]:
    """Returns (validated object, tokens used). Retries, then falls back to the cheap model."""
    if os.getenv("GIGBID_LLM", "").lower() == "fake":
        from agent import fake_llm
        return schema.model_validate(getattr(fake_llm, node)(variables)), 0

    cfg = get_settings().node(node)
    system = ((PROMPTS / f"{node}.md").read_text(encoding="utf-8")
              + "\n\nJSON schema:\n" + json.dumps(schema.model_json_schema()))
    user, tokens, last = render(variables, untrusted), 0, ""
    models = [cfg["model_name"]] * (cfg["retries"] + 1) + [cfg["fallback_model_name"]]
    for attempt, model in enumerate(models):
        try:
            text, used = await asyncio.wait_for(_chat(model, system, user, cfg["timeout_s"]), cfg["timeout_s"] + 5)
            tokens += used
            return schema.model_validate_json(text), tokens
        except ValidationError as e:                 # model answered, but not in the agreed shape
            last = f"bad JSON shape: {str(e)[:200]}"
            user += f"\n\nYour last reply did not match the schema ({last}). Reply with valid JSON only."
        except (LLMError, httpx.HTTPError, asyncio.TimeoutError, KeyError) as e:
            last = f"{type(e).__name__}: {e}"
            await asyncio.sleep(min(2 ** attempt, 8))
    raise LLMError(f"{node}: no valid answer after {len(models)} attempts ({last})")
