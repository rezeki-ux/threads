"""ThreadsScraper — the Python front end over the Go scraping engine.

Every method runs the Go binary in a subprocess, reads JSON from stdout (progress
goes to stderr), and returns typed models. No browser, no Scrapling, no GraphQL
doc_id on this path.

Example:
    from threads_scraper import ThreadsScraper

    scraper = ThreadsScraper()
    results = scraper.search("AI", limit=10)
    profile = scraper.profile("zuck")
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from . import runner
from .exceptions import ThreadsError
from .models import Post, Profile, Reply, SearchResult

log = logging.getLogger("threads_scraper")


class ThreadsScraper:
    """Calls the Go engine and returns typed models."""

    def __init__(self, timeout: float = 120, delay: float = 1.0) -> None:
        self.timeout = timeout
        self.delay = delay

    # -- internals ---------------------------------------------------------

    def _run(self, argv: Sequence[str]) -> list[dict[str, Any]]:
        args = [*argv, "--delay", f"{self.delay}s"]
        out = runner.run(args, timeout=self.timeout)
        try:
            data = json.loads(out)
        except json.JSONDecodeError as exc:
            raise ThreadsError(f"engine returned malformed JSON: {exc}") from exc
        if not isinstance(data, list):
            raise ThreadsError("engine returned non-array JSON")
        return data

    # -- public API --------------------------------------------------------

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        rows = self._run(["search", query, "-n", str(limit), "-o", "json", "--no-cache"])
        return [SearchResult.from_dict(r) for r in rows]

    def profile(self, username_or_url: str) -> Profile:
        rows = self._run(["profile", username_or_url, "-o", "json", "--no-cache"])
        if not rows:
            raise ThreadsError("profile returned no record")
        return Profile.from_dict(rows[0])

    def feed(self, username_or_url: str, limit: int = 20) -> list[Post]:
        rows = self._run(["feed", username_or_url, "-n", str(limit), "-o", "json", "--no-cache"])
        return [Post.from_dict(r) for r in rows]

    def post(self, url_or_id: str) -> Post:
        rows = self._run(["post", url_or_id, "-o", "json", "--no-cache"])
        if not rows:
            raise ThreadsError("post returned no record")
        return Post.from_dict(rows[0])

    def replies(self, url_or_id: str, limit: int = 20) -> list[Reply]:
        rows = self._run(["post", url_or_id, "--replies", "-n", str(limit), "-o", "json", "--no-cache"])
        return [Reply.from_dict(r) for r in rows]
