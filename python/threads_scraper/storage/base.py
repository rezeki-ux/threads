"""Repository interface and the normalized DB row definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Repository(ABC):
    """A storage sink for scraped Threads records.

    Implementations must be idempotent: upserting the same (platform, external_id)
    twice must not create a duplicate row.
    """

    @abstractmethod
    def migrate(self) -> None:
        """Create or update the schema."""

    @abstractmethod
    def upsert_post(self, row: dict[str, Any]) -> None:
        """Insert or update one post row keyed by (platform, external_id)."""

    @abstractmethod
    def upsert_profile(self, row: dict[str, Any]) -> None:
        """Insert or update one profile row keyed by (platform, external_id)."""

    @abstractmethod
    def count_posts(self, platform: str | None = None, external_id: str | None = None) -> int:
        """Number of stored posts (optionally filtered) — for idempotency checks."""

    @abstractmethod
    def get_post(self, platform: str, external_id: str) -> dict[str, Any] | None:
        """Fetch one stored post row, or None."""
