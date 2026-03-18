"""
Web search module – queries DuckDuckGo and returns structured results
with title, URL, and snippet for each hit.

Results are formatted both as a list of dicts (for programmatic use) and
as a ready-to-paste citation block (for the AI prompt).
"""

from __future__ import annotations

import time
from typing import List, Optional

import config


class SearchResult:
    """A single web search result."""

    __slots__ = ("title", "url", "snippet")

    def __init__(self, title: str, url: str, snippet: str) -> None:
        self.title = title
        self.url = url
        self.snippet = snippet

    def to_dict(self) -> dict:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}

    def citation_line(self) -> str:
        return f"• {self.title}\n  {self.url}\n  {self.snippet}"

    def __repr__(self) -> str:
        return f"SearchResult(title={self.title!r}, url={self.url!r})"


class WebSearch:
    """
    Thin wrapper around the DuckDuckGo search API (via the
    ``duckduckgo-search`` library).  Falls back gracefully when the
    library is unavailable.
    """

    def __init__(self, max_results: int = config.SEARCH_MAX_RESULTS) -> None:
        self._max_results = max_results
        self._ddgs = None
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            from duckduckgo_search import DDGS
            self._ddgs = DDGS
            return True
        except ImportError:
            return False

    @property
    def available(self) -> bool:
        return self._available

    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Perform a web search and return a list of :class:`SearchResult`.

        Parameters
        ----------
        query:
            The search query string.
        max_results:
            Override the default maximum number of results.
        """
        if not self._available:
            return []

        limit = max_results or self._max_results
        results: List[SearchResult] = []

        try:
            with self._ddgs() as ddgs:
                for r in ddgs.text(query, max_results=limit):
                    results.append(
                        SearchResult(
                            title=r.get("title", ""),
                            url=r.get("href", ""),
                            snippet=r.get("body", ""),
                        )
                    )
        except Exception:
            pass

        return results

    def format_results_for_prompt(
        self, results: List[SearchResult], query: str
    ) -> str:
        """
        Return a formatted block suitable for inclusion in an AI prompt.
        """
        if not results:
            return f"[Web search for '{query}' returned no results.]"

        lines = [f"Web search results for: {query!r}", ""]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.title}")
            lines.append(f"   URL: {r.url}")
            lines.append(f"   {r.snippet}")
            lines.append("")
        lines.append(
            "Please use the above sources in your answer and cite the URLs."
        )
        return "\n".join(lines)
