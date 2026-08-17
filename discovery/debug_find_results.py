"""Find which request actually carries the rendered search results.

Captures every response, recording url, method, status, body length, and whether
the body contains the search-result markers (a known result username/text, and
the "thread_items" key). No credentials are printed.

Usage:
    python debug_find_results.py [query]
"""

from __future__ import annotations

import json
import sys
from urllib.parse import parse_qsl

from scrapling.fetchers import DynamicFetcher

MARKERS = ("aicreatormentor", "thread_items", '"post":')


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "AI"
    captured: list = []

    def setup(page):
        def on_response(resp):
            try:
                body = resp.body()
                text = body.decode("utf-8", "replace")
            except Exception:
                text = ""
            hits = [m for m in MARKERS if m in text]
            captured.append(
                {
                    "method": resp.request.method,
                    "url": resp.url[:180],
                    "status": resp.status,
                    "body_len": len(text),
                    "hits": hits,
                }
            )

        page.on("response", on_response)

    print(f"[debug] search?q={query}", file=sys.stderr)
    DynamicFetcher.fetch(
        f"https://www.threads.com/search?q={query}&serp_type=default",
        page_setup=setup,
        headless=True,
        network_idle=True,
        timeout=45000,
        wait=6000,
    )

    interesting = [c for c in captured if c["hits"] or "graphql" in c["url"] or "ajax/bz" in c["url"]]
    print(f"[debug] captured {len(captured)} responses; {len(interesting)} interesting", file=sys.stderr)
    for c in interesting:
        print(json.dumps(c, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
