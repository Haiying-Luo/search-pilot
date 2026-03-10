"""
Google Search tool using Serper API.

Requires SERPER_API_KEY environment variable (used as fallback).
Free-tier API keys are tried first; exhausted keys (HTTP 403) are
automatically skipped for the rest of the process lifetime.
"""

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Free-tier API key pool — add keys here as needed.
# Keys that return 403 are marked dead and never retried.
# ---------------------------------------------------------------------------
_FREE_KEY_POOL: list[str] = [
    "your_free_api_key_1",
    "your_free_api_key_2",
]

_dead_keys: set[str] = set()


def _get_ordered_keys() -> list[str]:
    """Return keys to try in order: alive free keys first, then env key."""
    keys = [k for k in _FREE_KEY_POOL if k not in _dead_keys]
    env_key = os.getenv("SERPER_API_KEY")
    if env_key and env_key not in _dead_keys:
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
        return "Error: No available Serper API keys (all exhausted and SERPER_API_KEY not set)"

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
if os.getenv("SERPER_API_KEY") or _FREE_KEY_POOL:
    SEARCH_ENGINE_TOOLS = [search_engine]
