"""threads_scraper — a thin, typed Python client over the Go Threads engine.

    from threads_scraper import ThreadsScraper

    scraper = ThreadsScraper()
    results = scraper.search("AI", limit=10)
    profile = scraper.profile("zuck")
    posts = scraper.feed("zuck", limit=10)
    post = scraper.post("https://www.threads.com/@zuck/post/Db2wI-DilLt")
    replies = scraper.replies("https://www.threads.com/@zuck/post/Db2wI-DilLt", limit=10)

Binary resolution (see runner.py):
    THREADS_BINARY=/path/to/threads.exe      (compiled, preferred)
    ...else threads.exe in the repo root
    THREADS_GO_BINARY=C:\\...\\go.exe         (then `go run .\\cmd\\th`)

Set these environment variables only when the defaults do not apply.
"""

from .client import ThreadsScraper
from .exceptions import (
    ThreadsBinaryNotFound,
    ThreadsError,
    ThreadsScraperError,
    ThreadsTimeout,
)
from .models import Post, Profile, Reply, SearchResult
from .storage import InMemoryRepository, PostgresRepository, Repository

__all__ = [
    "ThreadsScraper",
    "Post",
    "Profile",
    "Reply",
    "SearchResult",
    "Repository",
    "InMemoryRepository",
    "PostgresRepository",
    "ThreadsScraperError",
    "ThreadsBinaryNotFound",
    "ThreadsError",
    "ThreadsTimeout",
]
