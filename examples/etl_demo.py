"""End-to-end ETL demo: Threads -> Go engine -> Python -> repository.

Run (from the repo root):

    python examples/etl_demo.py

Binary resolution follows runner.py: THREADS_BINARY -> threads.exe -> go run.

By default this uses the in-memory repository (no database server needed). To
use PostgreSQL, set the connection string and this script switches to the real
repository:

    set THREADS_DATABASE_URL=postgresql://user:pass@localhost:5432/db
    python examples/etl_demo.py

No Threads credentials are involved: scraping is anonymous.
"""

from __future__ import annotations

import os

from threads_scraper import InMemoryRepository, PostgresRepository, ThreadsScraper

POST_URL = "https://www.threads.com/@zuck/post/Db2wI-DilLt"


def repository():
    url = os.environ.get("THREADS_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if url:
        repo = PostgresRepository(url)
        repo.migrate()
        print("using PostgreSQL repository")
        return repo
    print("using in-memory repository (no THREADS_DATABASE_URL set)")
    return InMemoryRepository()


def main() -> None:
    scraper = ThreadsScraper()
    repo = repository()

    for row in scraper.search("AI", limit=10):
        repo.upsert_post(row.to_db_row())

    profile = scraper.profile("zuck")
    repo.upsert_profile(profile.to_db_row())

    for row in scraper.feed("zuck", limit=20):
        repo.upsert_post(row.to_db_row())

    post = scraper.post(POST_URL)
    repo.upsert_post(post.to_db_row())

    for row in scraper.replies(POST_URL, limit=20):
        repo.upsert_post(row.to_db_row())

    print(f"stored {repo.count_posts()} posts")

    sample = repo.get_post("threads", post.id)
    if sample:
        print("sample post:", sample["username"], "|", (sample["text"] or "")[:40])
        print("raw_payload preserved:", "raw_payload" in sample)


if __name__ == "__main__":
    main()
