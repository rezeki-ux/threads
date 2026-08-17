"""Tests for the threads_scraper Python layer (mocked; no live Threads)."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from threads_scraper import (
    Post,
    Reply,
    SearchResult,
    ThreadsBinaryNotFound,
    ThreadsError,
    ThreadsScraper,
    ThreadsTimeout,
)


def sample_post() -> dict:
    return {
        "id": "42",
        "shortcode": "ABC",
        "text": "hello @zuck #golang",
        "media_type": "TEXT_POST",
        "media_urls": [],
        "permalink": "https://www.threads.com/@carol/post/ABC",
        "username": "carol",
        "user_id": "20",
        "author_name": "Carol",
        "like_count": 5,
        "reply_count": 1,
        "repost_count": 0,
        "quote_count": 0,
        "mentions": ["zuck"],
        "hashtags": ["golang"],
        "fetched_at": "2026-01-01T00:00:00Z",
    }


class TestModels(unittest.TestCase):
    def test_post_from_dict_maps_fields(self):
        p = Post.from_dict(sample_post())
        self.assertEqual(p.id, "42")
        self.assertEqual(p.author_name, "Carol")
        self.assertEqual(p.mentions, ["zuck"])
        self.assertEqual(p.hashtags, ["golang"])

    def test_post_keeps_raw_payload(self):
        p = Post.from_dict(sample_post())
        self.assertEqual(p.raw["text"], "hello @zuck #golang")

    def test_db_row_uses_external_id_not_permalink(self):
        row = Post.from_dict(sample_post()).to_db_row()
        self.assertEqual(row["platform"], "threads")
        self.assertEqual(row["external_id"], "42")
        self.assertIn("raw_payload", row)

    def test_reply_inherits_post_fields(self):
        data = {**sample_post(), "parent_id": "1", "root_id": "1"}
        r = Reply.from_dict(data)
        self.assertEqual(r.id, "42")
        self.assertEqual(r.parent_id, "1")

    def test_search_result_has_query(self):
        data = {**sample_post(), "query": "AI", "searched_at": "2026-01-01T00:00:00Z"}
        s = SearchResult.from_dict(data)
        self.assertEqual(s.query, "AI")
        self.assertEqual(s.id, "42")


class TestRunner(unittest.TestCase):
    def test_resolve_binary_env(self):
        from threads_scraper import runner

        with mock.patch.dict("os.environ", {"THREADS_BINARY": "C:/x/threads.exe"}), \
             mock.patch("os.path.isfile", return_value=True):
            argv, desc = runner.resolve_command()
            self.assertEqual(argv, ["C:/x/threads.exe"])

    def test_resolve_binary_missing(self):
        from threads_scraper import runner

        with mock.patch.dict("os.environ", {"THREADS_BINARY": "C:/missing.exe"}, clear=False), \
             mock.patch.object(runner, "_default_binary", return_value=None), \
             mock.patch.object(runner, "_go_binary", return_value=None), \
             mock.patch("os.path.isfile", return_value=False):
            with self.assertRaises(ThreadsBinaryNotFound):
                runner.resolve_command()

    def test_run_nonzero_exit(self):
        from threads_scraper import runner

        fake = mock.Mock(returncode=3, stdout="", stderr="not found")
        with mock.patch("subprocess.run", return_value=fake):
            with self.assertRaises(ThreadsError) as ctx:
                runner.run(["search", "AI"])
            self.assertEqual(ctx.exception.exit_code, 3)

    def test_run_timeout(self):
        from threads_scraper import runner

        with mock.patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired("cmd", 1)):
            with self.assertRaises(ThreadsTimeout):
                runner.run(["search", "AI"])


class TestScraper(unittest.TestCase):
    def _scraper(self, stdout: str, returncode: int = 0):
        scraper = ThreadsScraper()
        proc = mock.Mock(returncode=returncode, stdout=stdout, stderr="")
        patcher = mock.patch("threads_scraper.runner.subprocess.run", return_value=proc)
        patcher.start()
        self.addCleanup(patcher.stop)
        return scraper

    def test_search_parses_json(self):
        scraper = self._scraper(json.dumps([sample_post()]))
        results = scraper.search("AI", limit=10)
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], SearchResult)

    def test_search_empty_result(self):
        scraper = self._scraper(json.dumps([]))
        self.assertEqual(scraper.search("AI"), [])

    def test_search_malformed_json(self):
        scraper = self._scraper("not json")
        with self.assertRaises(ThreadsError):
            scraper.search("AI")

    def test_profile_returns_profile(self):
        scraper = self._scraper(json.dumps([{"id": "1", "username": "zuck", "url": "u"}]))
        p = scraper.profile("zuck")
        self.assertEqual(p.username, "zuck")


if __name__ == "__main__":
    unittest.main()
