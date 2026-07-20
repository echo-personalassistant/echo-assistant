"""
DuckDuckGo HTML scraping utility.

Two agent-callable functions:
    ddg_search(query, max_results)  - search DuckDuckGo, return titles/URLs/snippets
    fetch_page_text(url, max_chars) - fetch a URL and return stripped plaintext

No API key required. Uses only stdlib + requests.
Registered as agent tools only when ENABLE_WEB_SEARCH = True in config.py.
"""

from __future__ import annotations

import html as html_module
import re
import urllib.parse
from html.parser import HTMLParser

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}

_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)


# ── HTML tag stripper ─────────────────────────────────────────────────────────

class _TagStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = False
        if tag in ("p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def get_text(self) -> str:
        raw = "".join(self._parts)
        lines = [ln.strip() for ln in raw.splitlines()]
        lines = [ln for ln in lines if ln]
        return "\n".join(lines)


def _strip_html(markup: str) -> str:
    parser = _TagStripper()
    parser.feed(markup)
    return html_module.unescape(parser.get_text())


# ── DuckDuckGo result parser ──────────────────────────────────────────────────

class _DDGParser(HTMLParser):
    """Extract result titles, URLs, and snippets from DDG HTML response."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict] = []
        self._current: dict | None = None
        self._capture_title = False
        self._capture_snippet = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr_dict = dict(attrs)
        cls = attr_dict.get("class", "")

        if tag == "div" and "result__body" in cls:
            self._current = {"title": "", "url": "", "snippet": ""}

        if self._current is not None:
            if tag == "a" and "result__a" in cls:
                href = attr_dict.get("href", "")
                # DDG wraps real URLs in a redirect — extract via uddg param
                parsed = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed.query)
                real = qs.get("uddg", [href])[0]
                self._current["url"] = urllib.parse.unquote(real)
                self._capture_title = True

            if tag == "a" and "result__snippet" in cls:
                self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._capture_title = False
            self._capture_snippet = False
        if tag == "div" and self._current and self._current.get("title"):
            self.results.append(self._current)
            self._current = None

    def handle_data(self, data: str) -> None:
        if self._capture_title and self._current is not None:
            self._current["title"] += data
        elif self._capture_snippet and self._current is not None:
            self._current["snippet"] += data


# ── Public tool functions ─────────────────────────────────────────────────────

def ddg_search(query: str, max_results: int = 5) -> str:
    """
    Search DuckDuckGo and return result titles, URLs, and snippets.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 5, max 10).

    Returns:
        Formatted string with numbered results.
    """
    max_results = min(int(max_results), 10)
    url = "https://html.duckduckgo.com/html/"
    params = {"q": query}

    try:
        resp = _SESSION.get(url, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"Search failed: {exc}"

    parser = _DDGParser()
    parser.feed(resp.text)

    results = parser.results[:max_results]
    if not results:
        return "No results found. DuckDuckGo may have changed its HTML structure."

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r["title"].strip()
        url_str = r["url"]
        snippet = r["snippet"].strip()
        lines.append(f"[{i}] {title}")
        lines.append(f"    URL: {url_str}")
        if snippet:
            lines.append(f"    {snippet}")
        lines.append("")

    return "\n".join(lines)


def fetch_page_text(url: str, max_chars: int = 8000) -> str:
    """
    Fetch a webpage and return its text content (HTML tags stripped).

    Args:
        url: The URL to fetch.
        max_chars: Maximum characters to return (default 8000).

    Returns:
        Plain text content of the page, truncated if necessary.
    """
    try:
        resp = _SESSION.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"Failed to fetch {url}: {exc}"

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        return f"Unsupported content type: {content_type}"

    text = _strip_html(resp.text)

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[...truncated at {max_chars} chars]"

    return text


# ── Tool schemas ──────────────────────────────────────────────────────────────

TOOL_SCHEMAS_WEB_SEARCH = [
    {
        "type": "function",
        "function": {
            "name": "ddg_search",
            "description": (
                "Search the web using DuckDuckGo. Returns result titles, URLs, and snippets. "
                "Use this to find up-to-date information, documentation, or news."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (1-10, default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page_text",
            "description": (
                "Fetch a webpage and return its plain text content. "
                "Use after ddg_search to read the full content of a result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to return (default 8000).",
                    },
                },
                "required": ["url"],
            },
        },
    },
]
