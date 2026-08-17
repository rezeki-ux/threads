"""Read/write the Threads operation store (JSON).

DEPRECATED for anonymous search: anonymous keyword search no longer uses a
GraphQL doc_id — it reads the server-rendered /search page. The Go binary no
longer reads this store. It is retained only as a diagnostic/experimentation
tool for authenticated or pagination GraphQL flows.

The store carries only non-sensitive metadata: doc_id, an optional operation
name, a variables template, timestamps, and a status. It never carries cookies,
sessions, CSRF tokens, or any other credential.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_FILE = Path.home() / ".local" / "share" / "th" / "threads_operations.json"


def store_path() -> Path:
    """The store path, honoring THREADS_OPERATIONS_FILE (same as Go)."""
    return Path(os.environ.get("THREADS_OPERATIONS_FILE", DEFAULT_FILE))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load() -> dict:
    path = store_path()
    if not path.exists():
        return {"search": {}}
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save(data: dict) -> Path:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return path


def get_search() -> dict:
    """The current search operation, or an empty dict."""
    return load().get("search", {}) or {}


def update_search(
    *,
    doc_id: str,
    operation_name: str = "",
    variables: dict | None = None,
    status: str = "valid",
    discovered_at: str | None = None,
) -> Path:
    """Record a (validated) search operation and return the store path."""
    data = load()
    data["search"] = {
        "doc_id": doc_id,
        "operation_name": operation_name,
        "variables": variables or {"query": "$query"},
        "discovered_at": discovered_at or _now(),
        "last_validated_at": _now(),
        "status": status,
    }
    return save(data)


def mark_stale() -> Path:
    """Mark the current search operation stale after the Go engine reports a
    rotated doc_id, so discovery knows a refresh is required."""
    data = load()
    search = data.get("search", {})
    if search:
        search["status"] = "invalid"
        data["search"] = search
    return save(data)
