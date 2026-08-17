"""PostgreSQL repository backed by psycopg (v3).

All SQL is parameterized (no string interpolation of values), so user data
cannot inject SQL. The connection string is read from THREADS_DATABASE_URL (or
the standard DATABASE_URL), never hardcoded.

Upserts key on (platform, external_id), so re-scraping the same post updates the
row instead of duplicating it.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import psycopg
from psycopg.types.json import Jsonb

from .base import Repository

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Column order must match POST_INSERT_SQL placeholders and POST_UPSERT params.
_POST_COLUMNS = (
    "platform",
    "external_id",
    "shortcode",
    "text",
    "username",
    "user_id",
    "author_name",
    "author_verified",
    "author_avatar_url",
    "timestamp",
    "permalink",
    "canonical_url",
    "media_type",
    "media_urls",
    "like_count",
    "reply_count",
    "repost_count",
    "quote_count",
    "is_reply",
    "reply_to_id",
    "reply_to_username",
    "quoted_post_id",
    "is_quote_post",
    "mentions",
    "hashtags",
    "width",
    "height",
    "is_paid_partnership",
    "has_audio",
    "parent_id",
    "root_id",
    "raw_payload",
    "fetched_at",
)

_PROFILE_COLUMNS = (
    "platform",
    "external_id",
    "username",
    "name",
    "biography",
    "profile_pic_url",
    "is_verified",
    "is_private",
    "external_url",
    "follower_count",
    "following_count",
    "url",
    "raw_payload",
    "fetched_at",
)

_POST_INSERT_SQL = (
    "INSERT INTO posts (" + ", ".join(_POST_COLUMNS) + ") VALUES ("
    + ", ".join(["%s"] * len(_POST_COLUMNS)) + ")"
)

_POST_UPSERT_SQL = _POST_INSERT_SQL + (
    " ON CONFLICT (platform, external_id) DO UPDATE SET "
    + ", ".join(
        f"{col} = EXCLUDED.{col}"
        for col in _POST_COLUMNS
        if col not in ("platform", "external_id")
    )
)

_PROFILE_UPSERT_SQL = (
    "INSERT INTO profiles (" + ", ".join(_PROFILE_COLUMNS) + ") VALUES ("
    + ", ".join(["%s"] * len(_PROFILE_COLUMNS)) + ")"
    " ON CONFLICT (platform, external_id) DO UPDATE SET "
    + ", ".join(
        f"{col} = EXCLUDED.{col}"
        for col in _PROFILE_COLUMNS
        if col not in ("platform", "external_id")
    )
)

_JSONB_FIELDS = {"media_urls", "mentions", "hashtags", "raw_payload"}


def _to_dt(value: str | None) -> datetime | None:
    """Convert an ISO-8601 string (with or without trailing Z) to a datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _params(columns: Sequence[str], row: dict[str, Any]) -> list[Any]:
    out: list[Any] = []
    for col in columns:
        value = row.get(col)
        if col == "timestamp" or col == "fetched_at":
            out.append(_to_dt(value))
        elif col in _JSONB_FIELDS:
            out.append(Jsonb(value))
        else:
            out.append(value)
    return out


class PostgresRepository(Repository):
    def __init__(self, conninfo: str | None = None) -> None:
        self.conninfo = conninfo or os.environ.get("THREADS_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not self.conninfo:
            raise ValueError(
                "no database URL: set THREADS_DATABASE_URL or pass conninfo to PostgresRepository"
            )

    def _connect(self):
        return psycopg.connect(self.conninfo)

    def migrate(self) -> None:
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.execute(schema)
            conn.commit()

    def upsert_post(self, row: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(_POST_UPSERT_SQL, _params(_POST_COLUMNS, row))
            conn.commit()

    def upsert_profile(self, row: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(_PROFILE_UPSERT_SQL, _params(_PROFILE_COLUMNS, row))
            conn.commit()

    def count_posts(self, platform: str | None = None, external_id: str | None = None) -> int:
        sql = "SELECT count(*) FROM posts"
        params: list[Any] = []
        clauses = []
        if platform is not None:
            clauses.append("platform = %s")
            params.append(platform)
        if external_id is not None:
            clauses.append("external_id = %s")
            params.append(external_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._connect() as conn:
            return conn.execute(sql, params).fetchone()[0]

    def get_post(self, platform: str, external_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM posts WHERE platform = %s AND external_id = %s",
                (platform, external_id),
            )
            row = cur.fetchone()
        return dict(row) if row else None
