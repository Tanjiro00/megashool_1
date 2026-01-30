from __future__ import annotations

"""
Tool registry and resilient web search helper for the agents.

Design goals:
- Prefer DuckDuckGo via duckduckgo_search when available.
- Handle DDG rate limits gracefully (retry, switch backend, fall back).
- Provide network fallbacks (DDG instant answers, optional SearX, StackOverflow).
- Never throw: always return an empty list on failure.
"""

from typing import Dict, List, Tuple
import json
import os
import time
import urllib.parse
import urllib.request

SEARCH_TOOL_NAME = "web_search"
_CACHE: dict[Tuple[str, int], List[Dict[str, str]]] = {}
_CACHE_LIMIT = 32


def _tavily_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Preferred search via Tavily if TAVILY_API_KEY is present."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return []
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        data = client.search(query=query, max_results=max_results, search_depth="advanced")
        hits = data.get("results", []) if isinstance(data, dict) else data
    except Exception:
        # Lightweight HTTP fallback
        try:
            payload = json.dumps({"api_key": api_key, "query": query, "max_results": max_results}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                hits = data.get("results", [])
        except Exception:
            return []
    results: List[Dict[str, str]] = []
    for item in hits[:max_results]:
        results.append(
            {
                "title": item.get("title", "") or item.get("url", ""),
                "link": item.get("url", ""),
                "snippet": item.get("content", "") or item.get("snippet", ""),
            }
        )
    return results


def _ddg_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Primary search using duckduckgo_search with backends and retries."""
    try:
        from duckduckgo_search import DDGS
    except Exception:
        return []

    backends = ["html", "lite", "auto"]
    for backend in backends:
        for attempt in range(2):
            try:
                results: List[Dict[str, str]] = []
                with DDGS() as ddgs:  # type: ignore[operator]
                    for item in ddgs.text(query, backend=backend, max_results=max_results):  # type: ignore[attr-defined]
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "link": item.get("href") or item.get("url") or "",
                                "snippet": item.get("body", ""),
                            }
                        )
                if results:
                    return results
            except Exception as e:
                msg = str(e).lower()
                if "ratelimit" in msg or "429" in msg or "forbidden" in msg:
                    time.sleep(1.0)
                    continue
                continue
    return []


def _ddg_api(query: str, max_results: int) -> List[Dict[str, str]]:
    """Fallback: DuckDuckGo Instant Answer JSON API."""
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_html=1&skip_disambig=1"
        with urllib.request.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    results: List[Dict[str, str]] = []
    related = data.get("RelatedTopics", []) or []
    for item in related[:max_results]:
        if "Text" in item and "FirstURL" in item:
            results.append({"title": item.get("Text", ""), "link": item.get("FirstURL", ""), "snippet": item.get("Text", "")})
        if "Topics" in item:
            for sub in item["Topics"][:max_results]:
                if "Text" in sub and "FirstURL" in sub and len(results) < max_results:
                    results.append({"title": sub.get("Text", ""), "link": sub.get("FirstURL", ""), "snippet": sub.get("Text", "")})
        if len(results) >= max_results:
            break
    if not results and data.get("Heading") and data.get("Abstract"):
        results.append(
            {
                "title": data.get("Heading", ""),
                "link": data.get("AbstractURL", "") or data.get("Redirect", ""),
                "snippet": data.get("Abstract", ""),
            }
        )
    return results


def _searx_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Optional SearXNG fallback; set SEARX_URL to enable."""
    base = os.getenv("SEARX_URL", "").strip().rstrip("/")
    if not base:
        return []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"{base}/search?q={q}&format=json&categories=general&language=en"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [
            {
                "title": item.get("title", ""),
                "link": item.get("url", ""),
                "snippet": item.get("content", ""),
            }
            for item in data.get("results", [])[:max_results]
            if item.get("url")
        ]
    except Exception:
        return []


def _so_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Last-resort fallback using StackOverflow search API."""
    try:
        q = urllib.parse.quote_plus(query)
        url = (
            "https://api.stackexchange.com/2.3/search/advanced?"
            f"order=desc&sort=relevance&q={q}&site=stackoverflow&pagesize={max_results}"
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return [
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("title", ""),
            }
            for item in data.get("items", [])[:max_results]
        ]
    except Exception:
        return []


def search_tool(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Web search helper with layered fallbacks to handle rate limits/blocking."""

    key = (query.strip().lower(), max_results)
    if key in _CACHE:
        return _CACHE[key]

    for provider in (_tavily_search, _ddg_search, _ddg_api, _searx_search, _so_search):
        results = provider(query, max_results)
        if results:
            trimmed = results[:max_results]
            _CACHE[key] = trimmed
            if len(_CACHE) > _CACHE_LIMIT:
                _CACHE.pop(next(iter(_CACHE)))
            return trimmed

    _CACHE[key] = []
    return []


def list_tools():
    """Return tools available to CrewAI agents."""

    return [search_tool]
