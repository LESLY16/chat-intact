"""
Tests for src/web_search.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.web_search import WebSearch, SearchResult


class TestSearchResult(unittest.TestCase):

    def test_to_dict(self):
        r = SearchResult("Title", "https://example.com", "A snippet")
        d = r.to_dict()
        self.assertEqual(d["title"], "Title")
        self.assertEqual(d["url"], "https://example.com")
        self.assertEqual(d["snippet"], "A snippet")

    def test_citation_line(self):
        r = SearchResult("T", "https://x.com", "S")
        line = r.citation_line()
        self.assertIn("T", line)
        self.assertIn("https://x.com", line)
        self.assertIn("S", line)

    def test_repr(self):
        r = SearchResult("T", "https://x.com", "S")
        self.assertIn("T", repr(r))


class TestWebSearch(unittest.TestCase):

    def _make_mock_ddgs(self, results):
        """Return a fake DDGS context manager that yields *results*."""
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text = MagicMock(return_value=results)
        mock_ddgs_cls = MagicMock(return_value=mock_ddgs_instance)
        return mock_ddgs_cls

    def test_unavailable_when_library_missing(self):
        ws = WebSearch()
        ws._available = False
        self.assertFalse(ws.available)
        results = ws.search("hello")
        self.assertEqual(results, [])

    def test_search_returns_results(self):
        ws = WebSearch()
        ws._available = True
        fake_results = [
            {"title": "Foo", "href": "https://foo.com", "body": "Foo body"},
            {"title": "Bar", "href": "https://bar.com", "body": "Bar body"},
        ]
        ws._ddgs = self._make_mock_ddgs(fake_results)

        results = ws.search("test query")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Foo")
        self.assertEqual(results[0].url, "https://foo.com")
        self.assertEqual(results[1].title, "Bar")

    def test_search_empty_returns_empty_list(self):
        ws = WebSearch()
        ws._available = True
        ws._ddgs = self._make_mock_ddgs([])
        results = ws.search("nothing")
        self.assertEqual(results, [])

    def test_search_handles_exception(self):
        ws = WebSearch()
        ws._available = True
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.__enter__ = MagicMock(return_value=mock_ddgs_instance)
        mock_ddgs_instance.__exit__ = MagicMock(return_value=False)
        mock_ddgs_instance.text = MagicMock(side_effect=RuntimeError("network error"))
        ws._ddgs = MagicMock(return_value=mock_ddgs_instance)

        results = ws.search("error query")
        self.assertEqual(results, [])

    def test_format_results_for_prompt_no_results(self):
        ws = WebSearch()
        formatted = ws.format_results_for_prompt([], "some query")
        self.assertIn("no results", formatted.lower())

    def test_format_results_for_prompt_with_results(self):
        ws = WebSearch()
        results = [
            SearchResult("Title A", "https://a.com", "Snippet A"),
            SearchResult("Title B", "https://b.com", "Snippet B"),
        ]
        formatted = ws.format_results_for_prompt(results, "my query")
        self.assertIn("my query", formatted)
        self.assertIn("https://a.com", formatted)
        self.assertIn("Title A", formatted)
        self.assertIn("Snippet B", formatted)
        self.assertIn("cite", formatted.lower())

    def test_max_results_override(self):
        ws = WebSearch(max_results=3)
        ws._available = True
        fake_results = [
            {"title": f"R{i}", "href": f"https://r{i}.com", "body": f"body{i}"}
            for i in range(10)
        ]
        ws._ddgs = self._make_mock_ddgs(fake_results)
        # The DDGS mock doesn't actually filter; we just verify the call is made
        ws.search("query")
        ws._ddgs.return_value.text.assert_called_once_with("query", max_results=3)


if __name__ == "__main__":
    unittest.main()
