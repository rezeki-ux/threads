"""Deep diagnostic: capture request bodies and response bodies for the Threads
search page's data endpoints (/ajax/bz, /api/graphql, /ajax/qm, etc.).

Prints NON-SENSITIVE info only. post_data values matching credential keys are
redacted to [REDACTED]. This is read-only and separate from discover_search.py.

Usage:
    python debug_network.py [query]
"""

from __future__ import annotations

import json
import sys
from urllib.parse import parse_qsl

from scrapling.fetchers import DynamicFetcher

SENSITIVE_SUBSTRINGS = (
    "session", "csrf", "cookie", "authorization", "token", "dtsg", "password", "secret",
)
TARGET_SUBSTRINGS = ("/ajax/bz", "/api/graphql", "/ajax/qm", "/ajax/bulk-route-definitions")


def redact(value: str) -> str:
    return "[REDACTED]" if any(s in value.lower() for s in SENSITIVE_SUBSTRINGS) else value


def summarize(value: str, needle: str, limit: int = 300) -> str:
    return value[:limit] + ("..." if len(value) > limit else "")


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "AI"
    captured: list = []

    def setup(page):
        def on_response(resp):
            url = resp.url
            if not any(t in url for t in TARGET_SUBSTRINGS):
                return
            try:
                req = resp.request
                post = req.post_data or ""
                has_query = query in post
                # redact sensitive keys in post_data before storing
                redacted_post = redact(post)
                try:
                    body = resp.body()
                    body_len = len(body)
                    text = body.decode("utf-8", "replace")
                    has_query_resp = query in text
                    has_thread = "thread_items" in text or '"post"' in text
                except Exception:
                    body_len = -1
                    has_query_resp = False
                    has_thread = False
                captured.append(
                    {
                        "url": url,
                        "method": req.method,
                        "status": resp.status,
                        "content_type": resp.headers.get("content-type", ""),
                        "post_data_has_query": has_query,
                        "post_data_len": len(post),
                        "post_data": redacted_post[:400] + ("..." if len(redacted_post) > 400 else ""),
                        "body_length": body_len,
                        "body_has_query": has_query_resp,
                        "body_has_thread_items": has_thread,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                captured.append({"url": url, "error": str(exc)})

        page.on("response", on_response)

    print(f"[debug] opening search?q={query}", file=sys.stderr)
    response = DynamicFetcher.fetch(
        f"https://www.threads.com/search?q={query}&serp_type=default",
        page_setup=setup,
        headless=True,
        network_idle=True,
        timeout=45000,
        wait=4000,
    )

    print(f"[debug] page status={response.status} html_len={len(response.body)}", file=sys.stderr)
    print(f"[debug] captured {len(captured)} target request(s)", file=sys.stderr)
    for i, entry in enumerate(captured):
        print(f"--- {i} ---")
        print(json.dumps(entry, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
