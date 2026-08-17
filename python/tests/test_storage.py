"""Integration tests for the storage layer.

Uses the InMemoryRepository (PostgreSQL is not available in this environment),
which exercises the same Repository interface and upsert semantics. The
PostgresRepository is tested for SQL correctness (parameterized, no
interpolation) with a mocked psycopg connection.
"""

from __future__ import annotations

import unittest
from unittest import mock

from threads_scraper import InMemoryRepository, Post, Profile, PostgresRepository
from threads_scraper.storage import postgres as pg


def full_post() -> dict:
    return {
        "id": "42",
        "shortcode": "ABC",
        "text": "hello @zuck #golang",
        "media_type": "TEXT_POST",
        "media_urls": ["http://x/img.jpg"],
        "permalink": "https://www.threads.com/@carol/post/ABC",
        "username": "carol",
        "user_id": "20",
        "author_name": "Carol",
        "author_verified": True,
        "author_avatar_url": "http://x/avatar.jpg",
        "timestamp": "2026-08-15T09:34:51Z",
        "like_count": 5,
        "reply_count": 1,
        "repost_count": 0,
        "quote_count": 0,
        "is_reply": True,
        "reply_to_id": "30",
        "reply_to_username": "alice",
        "quoted_post_id": "999",
        "is_quote_post": True,
        "mentions": ["zuck"],
        "hashtags": ["golang"],
        "width": 1080,
        "height": 1350,
        "is_paid_partnership": False,
        "has_audio": False,
        "canonical_url": "https://www.threads.com/@carol/post/ABC",
        "fetched_at": "2026-08-17T13:56:02Z",
    }


class TestToDbRow(unittest.TestCase):
    def test_all_columns_present(self):
        row = Post.from_dict(full_post()).to_db_row()
        expected = {
            "platform", "external_id", "shortcode", "text", "username", "user_id",
            "author_name", "author_verified", "author_avatar_url", "timestamp",
            "permalink", "media_type", "media_urls", "like_count", "reply_count",
            "repost_count", "quote_count", "is_reply", "reply_to_id",
            "reply_to_username", "quoted_post_id", "is_quote_post", "mentions",
            "hashtags", "width", "height", "is_paid_partnership", "has_audio",
            "canonical_url", "raw_payload", "fetched_at",
        }
        self.assertTrue(expected.issubset(row.keys()), f"missing {expected - row.keys()}")

    def test_raw_payload_preserves_unmapped_fields(self):
        data = {**full_post(), "some_future_field": {"nested": 123}}
        row = Post.from_dict(data).to_db_row()
        self.assertEqual(row["raw_payload"]["some_future_field"], {"nested": 123})

    def test_profile_to_db_row(self):
        row = Profile.from_dict({
            "id": "1", "username": "zuck", "name": "Mark", "is_verified": True,
            "is_private": False, "follower_count": 5, "url": "u",
        }).to_db_row()
        self.assertEqual(row["platform"], "threads")
        self.assertEqual(row["external_id"], "1")


class TestInMemoryRepository(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryRepository()
        self.repo.migrate()

    def test_upsert_is_idempotent(self):
        row = Post.from_dict(full_post()).to_db_row()
        self.repo.upsert_post(row)
        self.repo.upsert_post(row)
        self.repo.upsert_post(row)
        self.assertEqual(self.repo.count_posts(), 1)

    def test_upsert_updates_existing_row(self):
        self.repo.upsert_post(Post.from_dict(full_post()).to_db_row())
        updated = Post.from_dict({**full_post(), "like_count": 999}).to_db_row()
        self.repo.upsert_post(updated)
        stored = self.repo.get_post("threads", "42")
        self.assertEqual(stored["like_count"], 999)
        self.assertEqual(self.repo.count_posts(), 1)

    def test_raw_payload_intact(self):
        data = {**full_post(), "extra_blob": {"keep": True}}
        self.repo.upsert_post(Post.from_dict(data).to_db_row())
        stored = self.repo.get_post("threads", "42")
        self.assertEqual(stored["raw_payload"]["extra_blob"], {"keep": True})
        self.assertEqual(stored["raw_payload"]["id"], "42")

    def test_distinct_external_ids_are_separate(self):
        self.repo.upsert_post(Post.from_dict(full_post()).to_db_row())
        self.repo.upsert_post(Post.from_dict({**full_post(), "id": "43"}).to_db_row())
        self.assertEqual(self.repo.count_posts(), 2)


class TestPostgresSQL(unittest.TestCase):
    def test_upsert_sql_has_no_value_interpolation(self):
        # Values must never be baked into the SQL: the only %-tokens allowed are
        # %s placeholders and the ON CONFLICT column names.
        self.assertNotIn("'", pg._POST_UPSERT_SQL)  # no string literals
        self.assertIn("ON CONFLICT (platform, external_id)", pg._POST_UPSERT_SQL)
        self.assertIn("%s", pg._POST_UPSERT_SQL)

    def test_params_are_ordered_and_jsonb_wrapped(self):
        row = Post.from_dict(full_post()).to_db_row()
        params = pg._params(pg._POST_COLUMNS, row)
        placeholders = pg._POST_INSERT_SQL.count("%s")
        self.assertEqual(len(params), placeholders)
        # jsonb fields are wrapped
        self.assertIsInstance(params[pg._POST_COLUMNS.index("media_urls")], pg.Jsonb)

    def test_upsert_post_executes_with_params(self):
        repo = PostgresRepository.__new__(PostgresRepository)  # bypass __init__
        repo.conninfo = "postgresql://user:pass@host/db"
        fake_conn = mock.MagicMock()
        fake_conn.__enter__.return_value = fake_conn  # support `with ... as conn`
        with mock.patch.object(repo, "_connect", return_value=fake_conn):
            repo.upsert_post(Post.from_dict(full_post()).to_db_row())
        fake_conn.execute.assert_called_once()
        sql, params = fake_conn.execute.call_args[0]
        self.assertIn("ON CONFLICT", sql)
        self.assertIsInstance(params, list)

    def test_missing_conninfo_raises(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                PostgresRepository()


if __name__ == "__main__":
    unittest.main()
