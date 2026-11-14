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
import re
import time
from pathlib import Path
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from agent.settings import get_settings

PROMPTS = Path(__file__).with_name("prompts")
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


class RateLimited(LLMError):
    def __init__(self, wait: float):
        super().__init__(f"rate limited, retry in {wait:.0f}s")
        self.wait = wait


_used: dict[str, list[tuple[float, int]]] = {}       # model -> (time, tokens) for the last minute


async def _pace(provider: dict, model: str, need: int) -> None:
    """Stay under the provider's tokens-per-minute cap: wait until this call fits."""
    limit, model = provider.get("tpm_limit", 0), f"{provider['name']}/{model}"
    while limit:
        now = time.monotonic()
        recent = [(t, n) for t, n in _used.get(model, []) if now - t < 60]
        _used[model] = recent
        if not recent or sum(n for _, n in recent) + need <= limit:
            break
        await asyncio.sleep(max(0.5, 60 - (now - recent[0][0])))
    _used.setdefault(model, []).append((time.monotonic(), need))


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


def providers() -> list[dict]:
    """Providers that can be used right now, in order. GIGBID_PROVIDER=name forces one."""
    profile = get_settings().profile
    found = []
    for p in [profile] + profile.get("backup_providers", []):
        url = os.getenv(p["base_url_env"], "") if "base_url_env" in p else p["base_url"]
        key = os.getenv(p["api_key_env"], "") if p.get("api_key_env") else "none"
        if url and key:
            found.append({**p, "base_url": url.rstrip("/"), "key": key})
    forced = os.getenv("GIGBID_PROVIDER", "")
    return [p for p in found if p["name"] == forced] if forced else found


async def _chat(provider: dict, model: str, system: str, user: str, timeout: float) -> tuple[str, int]:
    await _pace(provider, model, (len(system) + len(user)) // 4 + 600)   # rough size: 4 characters per token, plus the reply
    async with httpx.AsyncClient(timeout=timeout) as http:
        r = await http.post(f"{provider['base_url']}/chat/completions", headers={"Authorization": f"Bearer {provider['key']}"},
                            json={"model": model, "temperature": 0, "response_format": {"type": "json_object"},
                                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                                  **provider.get("extra", {})})
    if r.status_code == 429:
        m = re.search(r"try again in ([\d.]+)(ms|s)", r.text)
        wait = float(r.headers.get("retry-after") or (float(m.group(1)) / (1000 if m.group(2) == "ms" else 1) if m else 10))
        raise RateLimited(wait)
    if r.status_code >= 400:
        raise LLMError(f"{provider['name']} call failed ({r.status_code}): {r.text[:200]}")
    body = r.json()
    text = body["choices"][0]["message"]["content"] or ""
    return text[text.find("{"):text.rfind("}") + 1], body.get("usage", {}).get("total_tokens", 0)   # tolerate ```json fences


async def ask(node: str, variables: dict, schema: type[T], untrusted: tuple[str, ...] = ()) -> tuple[T, int]:
    """Returns (validated object, tokens used). Retries, then falls back to the cheap model."""
    if os.getenv("GIGBID_LLM", "").lower() == "fake":
        from agent import fake_llm
        return schema.model_validate(getattr(fake_llm, node)(variables)), 0

    cfg = get_settings().node(node)
    system = ((PROMPTS / f"{node}.md").read_text(encoding="utf-8")
              + "\n\nJSON schema:\n" + json.dumps(schema.model_json_schema(), separators=(",", ":")))
    user, tokens, last = render(variables, untrusted), 0, ""
    sizes = [cfg["model"]] * (cfg["retries"] + 1) + ["fallback"]      # small/strong, then the cheap fallback
    usable = providers()
    if not usable:
        raise LLMError("no model provider is configured: set an API key in .env")
    waits, attempt, pi = 0, 0, 0
    while attempt < len(sizes):
        provider = usable[pi]
        model = provider["models"][sizes[attempt]]
        try:
            text, used = await asyncio.wait_for(_chat(provider, model, system, user, cfg["timeout_s"]), cfg["timeout_s"] + 65)
            tokens += used
            return schema.model_validate_json(text), tokens
        except RateLimited as e:                     # not a failure: use the next provider, or wait as told
            if e.wait > 2 and pi + 1 < len(usable):
                pi += 1
                continue
            waits += 1
            if waits > 5:
                raise LLMError(f"{node}: still rate limited after {waits} waits") from e
            await asyncio.sleep(min(e.wait + 1, 45))
            continue
        except ValidationError as e:                 # model answered, but not in the agreed shape
            last = f"bad JSON shape: {str(e)[:200]}"
            user += f"\n\nYour last reply did not match the schema ({last}). Reply with valid JSON only."
            attempt += 1
        except (LLMError, httpx.HTTPError, asyncio.TimeoutError, KeyError) as e:
            last = f"{type(e).__name__}: {e}"
            if pi > 0:                               # a backup provider failed (no credit, unknown model): drop it
                usable.pop(pi)
                pi = 0
                continue
            await asyncio.sleep(min(2 ** attempt, 8))
            attempt += 1
    raise LLMError(f"{node}: no valid answer after {len(sizes)} attempts ({last})")
