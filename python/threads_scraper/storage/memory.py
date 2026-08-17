"""In-memory Repository for tests and offline development.

Not for production (no persistence), but it exercises the exact same interface
and idempotency semantics as the PostgreSQL repository.
"""

from __future__ import annotations

import copy
from typing import Any

from .base import Repository


class InMemoryRepository(Repository):
    def __init__(self) -> None:
        self._posts: dict[tuple[str, str], dict[str, Any]] = {}
        self._profiles: dict[tuple[str, str], dict[str, Any]] = {}
        self.migrated = False

    def migrate(self) -> None:
        self.migrated = True

    def _key(self, row: dict[str, Any]) -> tuple[str, str]:
        return (row["platform"], row["external_id"])

    def upsert_post(self, row: dict[str, Any]) -> None:
        # Store a deep copy so later mutation of the caller's dict (or the raw
        # payload) cannot corrupt what we persisted.
        self._posts[self._key(row)] = copy.deepcopy(row)

    def upsert_profile(self, row: dict[str, Any]) -> None:
        self._profiles[self._key(row)] = copy.deepcopy(row)

    def count_posts(self, platform: str | None = None, external_id: str | None = None) -> int:
        if platform is None and external_id is None:
            return len(self._posts)
        n = 0
        for (p, e) in self._posts:
            if (platform is None or p == platform) and (external_id is None or e == external_id):
                n += 1
        return n

    def get_post(self, platform: str, external_id: str) -> dict[str, Any] | None:
        return self._posts.get((platform, external_id))
