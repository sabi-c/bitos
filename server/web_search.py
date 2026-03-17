"""Web search tool for the BITOS agent.

Tries DuckDuckGo (no API key), falls back to Brave Search API if configured.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def web_search(query: str, num_results: int = 5) -> list[dict[str, str]]:
    """Search the web and return results.

    Returns list of {"title", "url", "snippet"} dicts.
    Tries DuckDuckGo first (free, no key), then Brave Search API.
    """
    num_results = max(1, min(num_results, 10))

    # 1. Try DuckDuckGo
    result = _search_duckduckgo(query, num_results)
    if result is not None:
        return result

    # 2. Try Brave Search API
    brave_key = os.environ.get("BRAVE_API_KEY", "")
    if brave_key:
        result = _search_brave(query, num_results, brave_key)
        if result is not None:
            return result

    # 3. No search backend available
    logger.warning("web_search: no search backend available")
    return [{"error": "No search backend available. Install duckduckgo-search or set BRAVE_API_KEY."}]


def _search_duckduckgo(query: str, num_results: int) -> list[dict[str, str]] | None:
    """Search using duckduckgo-search library."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.debug("web_search: duckduckgo-search not installed")
        return None

    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=num_results))

        results = []
        for item in raw:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("href", item.get("link", "")),
                "snippet": item.get("body", item.get("snippet", "")),
            })
        logger.info("web_search_ddg: query=%s results=%d", query[:60], len(results))
        return results
    except Exception as exc:
        logger.warning("web_search_ddg_error: %s", exc)
        return None


def _search_brave(query: str, num_results: int, api_key: str) -> list[dict[str, str]] | None:
    """Search using Brave Search API."""
    try:
        import httpx
    except ImportError:
        logger.debug("web_search: httpx not available for Brave Search")
        return None

    try:
        resp = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": num_results},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            })
        logger.info("web_search_brave: query=%s results=%d", query[:60], len(results))
        return results
    except Exception as exc:
        logger.warning("web_search_brave_error: %s", exc)
        return None


def web_search_tool_handler(tool_input: dict) -> str:
    """Handle the web_search tool call from the agent. Returns JSON string."""
    query = tool_input.get("query", "").strip()
    if not query:
        return json.dumps({"error": "query is required"})

    num_results = tool_input.get("num_results", 5)
    results = web_search(query, num_results=num_results)
    return json.dumps({"results": results, "query": query, "count": len(results)})
