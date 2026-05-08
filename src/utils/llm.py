"""Anthropic API wrapper with retries, JSON parsing, and prompt caching.

Set LLM_MODE=mock in env (or call set_mock(True)) to use the deterministic
mock instead of real Claude calls. Useful for cheap end-to-end testing.
"""
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from config.settings import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    CLAUDE_MODEL_PREMIUM,
    CLAUDE_MAX_TOKENS,
)
from utils.logging_utils import get_logger

logger = get_logger("llm")

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
except ImportError:
    anthropic = None
    _client = None

_MOCK_MODE = os.getenv("LLM_MODE", "").lower() == "mock"


def set_mock(enabled: bool) -> None:
    global _MOCK_MODE
    _MOCK_MODE = enabled


def is_mock() -> bool:
    return _MOCK_MODE


class LLMError(RuntimeError):
    pass


def _client_or_raise():
    if _client is None:
        raise LLMError(
            "Anthropic client not initialized. Set ANTHROPIC_API_KEY in env / .env "
            "and `pip install anthropic`."
        )
    return _client


def call(
    user: str,
    system: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    cache_system: bool = True,
    retries: int = 3,
) -> str:
    """Call Claude. Returns raw text. Caches the system prompt by default."""
    if _MOCK_MODE:
        from utils import mock_llm
        return mock_llm.call(user, system=system)
    client = _client_or_raise()
    model = model or CLAUDE_MODEL
    max_tokens = max_tokens or CLAUDE_MAX_TOKENS

    sys_blocks: Optional[List[Dict[str, Any]]] = None
    if system:
        block: Dict[str, Any] = {"type": "text", "text": system}
        if cache_system:
            block["cache_control"] = {"type": "ephemeral"}
        sys_blocks = [block]

    last_err = None
    for attempt in range(retries):
        try:
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": user}],
            }
            if sys_blocks:
                kwargs["system"] = sys_blocks
            resp = client.messages.create(**kwargs)
            return resp.content[0].text
        except Exception as e:
            last_err = e
            wait = 2 ** attempt
            logger.warning(f"LLM call failed (attempt {attempt+1}/{retries}): {e}. Sleeping {wait}s.")
            time.sleep(wait)
    raise LLMError(f"LLM call failed after {retries} retries: {last_err}")


def call_premium(user: str, system: Optional[str] = None, **kwargs) -> str:
    return call(user, system=system, model=CLAUDE_MODEL_PREMIUM, **kwargs)


_JSON_RE = re.compile(r"\{[\s\S]*\}|\[[\s\S]*\]")


def call_json(user: str, system: Optional[str] = None, **kwargs) -> Any:
    """Like call(), but parses the response as JSON. Tolerates ```json fences and prose around it."""
    if _MOCK_MODE:
        from utils import mock_llm
        return mock_llm.call_json(user, system=system)
    raw = call(user, system=system, **kwargs)
    return parse_json_blob(raw)


def parse_json_blob(raw: str) -> Any:
    if "```json" in raw:
        raw = raw.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in raw:
        parts = raw.split("```")
        if len(parts) >= 3:
            raw = parts[1]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = _JSON_RE.search(raw)
        if not m:
            raise
        return json.loads(m.group(0))


def is_available() -> bool:
    return _MOCK_MODE or _client is not None
