"""
Google Search tool using Serper API.

Reads keys from environment variables:
- SERPER_API_KEYS: optional key pool (comma/newline/space separated)
- SERPER_API_KEY: optional single fallback key

Exhausted keys (HTTP 400/403 JSON) are automatically skipped for the
rest of the process lifetime.
"""

import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keys that return 400/403 (quota exhausted/invalid) are marked dead and never
# retried for the rest of the process lifetime.
# ---------------------------------------------------------------------------
_dead_keys: set[str] = set()


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    placeholder_markers = (
        "your",
        "replace_me",
        "example",
        "placeholder",
        "xxxx",
        "changeme",
    )
    return any(marker in lowered for marker in placeholder_markers)


def _is_valid_serper_key(value: str) -> bool:
    """Best-effort format check for Serper API keys."""
    key = value.strip()
    if not key:
        return False
    if _looks_like_placeholder(key):
        return False
    # Serper keys are typically long opaque tokens; keep this rule permissive.
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{20,}", key))


def _parse_serper_pool(raw_value: str | None) -> list[str]:
    """Parse SERPER_API_KEYS into a de-duplicated key list preserving order."""
    if not raw_value:
        return []

    parts = re.split(r"[\s,;]+", raw_value.strip())
    seen: set[str] = set()
    keys: list[str] = []
    for part in parts:
        key = part.strip()
        if not key or key in seen:
            continue
        if not _is_valid_serper_key(key):
            masked = (key[:6] + "..." + key[-4:]) if len(key) > 12 else key
            logger.warning(
                "[Serper] Ignoring invalid key in SERPER_API_KEYS: %s "
                "(check .env formatting or placeholder values)",
                masked,
            )
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _configured_key_pool() -> list[str]:
    """Return key pool from env var SERPER_API_KEYS."""
    return _parse_serper_pool(os.getenv("SERPER_API_KEYS"))


def _get_ordered_keys() -> list[str]:
    """Return keys to try in order: pool keys first, then single fallback key."""
    keys = [k for k in _configured_key_pool() if k not in _dead_keys]
    env_key = os.getenv("SERPER_API_KEY")
    if env_key:
        if not _is_valid_serper_key(env_key):
            masked = (env_key[:6] + "..." + env_key[-4:]) if len(env_key) > 12 else env_key
            logger.warning(
                "[Serper] Ignoring invalid SERPER_API_KEY: %s "
                "(check .env formatting or placeholder value)",
                masked,
            )
        elif env_key not in _dead_keys and env_key not in keys:
            keys.append(env_key)
    return keys


def _do_search(api_key: str, payload: dict) -> requests.Response:
    """Fire a single Serper request; caller handles status codes."""
    return requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------

def search_engine(
    query: str,
    num_results: int = 20,
    language: str = "en",
) -> str:
    """
    Search the web using Google via Serper API. Returns formatted search results including titles, URLs, snippets, answer boxes, and knowledge graph data.

    Args:
        query: The search query string (use Chinese keywords for Chinese questions, English for English questions).
        num_results: Number of results to return (default: 20).
        language: Language code for results, e.g. 'en' for English, 'zh-cn' for Chinese (default: 'en').

    Returns:
        Formatted search results text with titles, URLs, and snippets.
    """
    keys = _get_ordered_keys()
    if not keys:
        return "Error: No available Serper API keys (all exhausted and neither SERPER_API_KEYS nor SERPER_API_KEY is set)"

    payload = {"q": query, "num": num_results, "hl": language}
    last_error = ""

    for key in keys:
        try:
            resp = _do_search(key, payload)

            if resp.status_code in (400, 403):
                masked = key[:6] + "..." + key[-4:]
                content_type = resp.headers.get("content-type", "")
                if resp.status_code == 403 and "text/html" in content_type:
                    # HTML 403 = network-level block (e.g. GFW), not key issue
                    logger.warning(f"[Serper] Network block (HTML 403)")
                # 400 = quota exhausted / invalid key, 403 JSON = quota exhausted
                logger.warning(f"[Serper] Key {masked} returned {resp.status_code}, marking as dead")
                _dead_keys.add(key)
                continue

            resp.raise_for_status()
            data = resp.json()
            return _format_results(query, data, num_results)

        except requests.exceptions.Timeout:
            last_error = "Request timed out"
        except requests.exceptions.RequestException as e:
            last_error = str(e)
        except json.JSONDecodeError:
            last_error = "Failed to parse API response"

    return f"Error: All Serper API keys failed. Last error: {last_error}"


# ---------------------------------------------------------------------------
# Result formatter (extracted for clarity)
# ---------------------------------------------------------------------------

def _format_results(query: str, data: dict, num_results: int) -> str:
    results = []
    for item in data.get("organic", [])[:num_results]:
        result = {
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        }
        if "date" in item:
            result["date"] = item["date"]
        results.append(result)

    answer_box = data.get("answerBox")
    knowledge_graph = data.get("knowledgeGraph")

    lines = [
        f"Search Query: {query}",
        f"Results Found: {len(results)}",
        "-" * 50,
    ]

    if answer_box:
        lines.append("\n[Answer Box]")
        if answer_box.get("title"):
            lines.append(f"Title: {answer_box['title']}")
        answer = answer_box.get("answer", answer_box.get("snippet", ""))
        if answer:
            lines.append(f"Answer: {answer}")
        lines.append("")

    if knowledge_graph:
        lines.append("\n[Knowledge Graph]")
        if knowledge_graph.get("title"):
            lines.append(f"Title: {knowledge_graph['title']}")
        if knowledge_graph.get("type"):
            lines.append(f"Type: {knowledge_graph['type']}")
        if knowledge_graph.get("description"):
            lines.append(f"Description: {knowledge_graph['description']}")
        lines.append("")

    lines.append("\n[Search Results]")
    for i, r in enumerate(results, 1):
        lines.append(f"\n{i}. {r['title']}")
        lines.append(f"   URL: {r['link']}")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        if r.get("date"):
            lines.append(f"   Date: {r['date']}")

    return "\n".join(lines)


SEARCH_ENGINE_TOOLS = []
if _configured_key_pool() or os.getenv("SERPER_API_KEY"):
    SEARCH_ENGINE_TOOLS = [search_engine]
