"""Typed models mirroring the Go engine's JSON contract.

Field names match the Go JSON tags 1:1 so `from_dict` can map them directly.
Every model keeps `raw` (the original JSON object) so metadata Threads adds in
the future is never silently dropped — the DB layer stores it as JSONB.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


def _from_dict(cls: type[T], data: dict) -> T:
    """Build a dataclass from a dict, mapping same-named keys and keeping raw."""
    names = {f.name for f in dataclasses.fields(cls)}
    kwargs = {k: v for k, v in data.items() if k in names}
    kwargs["raw"] = data
    return cls(**kwargs)  # type: ignore[call-arg]


@dataclass
class Profile:
    id: str = ""
    username: str = ""
    name: str = ""
    biography: str = ""
    profile_pic_url: str = ""
    is_verified: bool = False
    is_private: bool = False
    external_url: str = ""
    follower_count: int = 0
    following_count: int = 0
    url: str = ""
    fetched_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        return _from_dict(cls, data)

    def to_db_row(self) -> dict[str, Any]:
        """A PostgreSQL-ready profile row keyed by platform + external id."""
        return {
            "platform": "threads",
            "external_id": self.id,
            "username": self.username,
            "name": self.name,
            "biography": self.biography,
            "profile_pic_url": self.profile_pic_url,
            "is_verified": self.is_verified,
            "is_private": self.is_private,
            "external_url": self.external_url,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
            "url": self.url,
            "raw_payload": self.raw,
            "fetched_at": self.fetched_at,
        }


@dataclass
class Post:
    id: str = ""
    shortcode: str = ""
    text: str = ""
    media_type: str = ""
    media_urls: list[str] = field(default_factory=list)
    permalink: str = ""
    canonical_url: str = ""
    username: str = ""
    user_id: str = ""
    author_name: str = ""
    author_verified: bool = False
    author_avatar_url: str = ""
    timestamp: str = ""
    like_count: int = 0
    reply_count: int = 0
    repost_count: int = 0
    reshare_count: int = 0
    quote_count: int = 0
    is_quote_post: bool = False
    is_reply: bool = False
    quoted_post_id: str = ""
    reply_to_id: str = ""
    reply_to_username: str = ""
    mentions: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    width: int = 0
    height: int = 0
    is_paid_partnership: bool = False
    has_audio: bool = False
    has_media: bool = False
    fetched_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Post":
        return _from_dict(cls, data)

    def to_db_row(self) -> dict[str, Any]:
        """A PostgreSQL-ready row. `external_id` is the Threads post id, never
        the permalink; `raw_payload` preserves the full record as JSONB."""
        return {
            "platform": "threads",
            "external_id": self.id,
            "shortcode": self.shortcode,
            "text": self.text,
            "username": self.username,
            "user_id": self.user_id,
            "author_name": self.author_name,
            "author_verified": self.author_verified,
            "author_avatar_url": self.author_avatar_url,
            "timestamp": self.timestamp,
            "permalink": self.permalink,
            "canonical_url": self.canonical_url,
            "media_type": self.media_type,
            "media_urls": self.media_urls,
            "like_count": self.like_count,
            "reply_count": self.reply_count,
            "repost_count": self.repost_count,
            "quote_count": self.quote_count,
            "is_reply": self.is_reply,
            "reply_to_id": self.reply_to_id or None,
            "reply_to_username": self.reply_to_username or None,
            "quoted_post_id": self.quoted_post_id or None,
            "is_quote_post": self.is_quote_post,
            "mentions": self.mentions,
            "hashtags": self.hashtags,
            "width": self.width or None,
            "height": self.height or None,
            "is_paid_partnership": self.is_paid_partnership,
            "has_audio": self.has_audio,
            "parent_id": None,
            "root_id": None,
            "raw_payload": self.raw,
            "fetched_at": self.fetched_at,
        }


@dataclass
class Reply(Post):
    parent_id: str = ""
    root_id: str = ""

    def to_db_row(self) -> dict[str, Any]:
        row = super().to_db_row()
        row["parent_id"] = self.parent_id
        row["root_id"] = self.root_id
        return row


@dataclass
class SearchResult(Post):
    query: str = ""
    searched_at: str = ""
