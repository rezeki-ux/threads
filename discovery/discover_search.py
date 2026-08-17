"""Discover the current Threads search GraphQL operation using Scrapling.

NOTE (verified finding): anonymous keyword search no longer uses the anonymous
/api/graphql persisted-query (doc_id) path. The Threads search page serves
keyword results as SERVER-RENDERED HTML for the crawler user agent at:

    https://www.threads.com/search?q=<query>

with the same `thread_items[].post` structure the Go SSR parser already reads.
The Go engine now uses that SSR path as the primary search mechanism, so this
GraphQL discovery layer is no longer required for basic anonymous search.

This script is retained for two future uses:
  1. discovering an authenticated /session GraphQL operation, and
  2. finding the pagination ("Recent"/cursor) operation that extends search past
     the SSR window.

It opens the anonymous search page in a real browser, captures requests to
/api/graphql (and /ajax/bz), extracts doc_id + variables, validates the best
candidate by replaying it, and writes the winner to the operation store. It
does NOT store credentials.

Usage:
    python discover_search.py [query] [--store FILE] [--headful]

Requires a working Scrapling browser engine (camoufox/playwright). On first run
Scrapling downloads its browser.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.parse import parse_qsl

import operation_store
import validate_operation

SEARCH_URL = "https://www.threads.com/search?q={query}"

DROP_VAR_PREFIX = "__relay_internal__"
SENSITIVE_SUBSTRINGS = (
    "session", "csrf", "cookie", "authorization", "token", "dtsg", "password", "secret",
)


def _classify_variables(variables: dict, query: str) -> dict | None:
    """Return a cleaned, reusable variables template, or None if not a search op.

    Rejects profile/post operations (userID/postID) and drops relay-provider
    flags (the Go engine re-adds them) and any sensitive keys. The literal query
    value is replaced with the "$query" placeholder.
    """
    if not isinstance(variables, dict):
        return None
    if "query" not in variables:
        return None
    if "userID" in variables or "postID" in variables:
        return None
    cleaned: dict = {}
    for k, v in variables.items():
        if k.startswith(DROP_VAR_PREFIX):
            continue
        if any(s in k.lower() for s in SENSITIVE_SUBSTRINGS):
            continue
        if isinstance(v, str) and v == query:
            v = "$query"
        cleaned[k] = v
    cleaned.setdefault("query", "$query")
    return cleaned


def _graphql_requests(page) -> list:
    """Register a Playwright response listener and return a list accumulator.

    Each captured entry holds the doc_id, the parsed variables, an optional
    friendly name, and the HTTP status of the /api/graphql request.
    """
    captured: list = []

    def on_response(resp):
        if "/api/graphql" not in resp.url:
            return
        try:
            post = resp.request.post_data or ""
            form = dict(parse_qsl(post))
            doc_id = form.get("doc_id", "")
            variables: dict = {}
            if form.get("variables"):
                try:
                    variables = json.loads(form["variables"])
                except ValueError:
                    variables = {}
            captured.append(
                {
                    "url": resp.url,
                    "doc_id": doc_id,
                    "variables": variables,
                    "friendly_name": form.get("fb_api_req_friendly_name", ""),
                    "status": resp.status,
                }
            )
        except Exception:
            return

    page.on("response", on_response)
    return captured


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query", nargs="?", default="AI", help="keyword to discover for (default: AI)")
    ap.add_argument("--store", default=None, help="operation store path (default: THREADS_OPERATIONS_FILE or ~/.local/share/th)")
    ap.add_argument("--headful", action="store_true", help="show the browser window (default: headless)")
    args = ap.parse_args(argv)

    if args.store:
        os.environ["THREADS_OPERATIONS_FILE"] = args.store

    try:
        from scrapling.fetchers import DynamicFetcher
    except Exception as e:  # pragma: no cover - environment dependent
        print(f"[discover] Scrapling unavailable: {e}", file=sys.stderr)
        print("[discover] run `pip install -r discovery/requirements.txt` and `scrapling install`", file=sys.stderr)
        return 1

    captured: list = []

    def setup(page):
        captured.extend(_graphql_requests(page))

    def action(page):
        # Search results render client-side. If no search query fired on load,
        # nudge the search input.
        page.wait_for_timeout(2000)
        if not any(c.get("variables", {}).get("query") for c in captured):
            try:
                page.keyboard.type(args.query)
                page.keyboard.press("Enter")
                page.wait_for_timeout(3000)
            except Exception:
                pass

    print(f"[discover] opening search page for {args.query!r}", file=sys.stderr)
    DynamicFetcher.fetch(
        SEARCH_URL.format(query=args.query),
        page_setup=setup,
        page_action=action,
        headless=not args.headful,
        network_idle=True,
        timeout=45000,
        wait=3000,
    )

    print(f"[discover] captured {len(captured)} /api/graphql request(s)", file=sys.stderr)

    candidates = []
    for c in captured:
        cleaned = _classify_variables(c["variables"], args.query)
        if cleaned is None or not c["doc_id"]:
            continue
        candidates.append(
            {
                "doc_id": c["doc_id"],
                "operation_name": c["friendly_name"],
                "variables": cleaned,
                "status": c["status"],
            }
        )

    if not candidates:
        print(json.dumps({"valid": False, "reason": "no search operation found"}, indent=2))
        return 1

    print(f"[discover] {len(candidates)} search candidate(s)", file=sys.stderr)

    for cand in candidates:
        result = validate_operation.validate(cand["doc_id"], cand["variables"], args.query)
        cand["validation"] = result
        if result.get("valid"):
            path = operation_store.update_search(
                doc_id=cand["doc_id"],
                operation_name=cand["operation_name"],
                variables=cand["variables"],
                status="valid",
            )
            print(
                json.dumps(
                    {
                        "valid": True,
                        "doc_id": cand["doc_id"],
                        "operation_name": cand["operation_name"],
                        "variables": cand["variables"],
                        "post_ids": result.get("post_ids", []),
                        "store": str(path),
                    },
                    indent=2,
                )
            )
            return 0

    print(json.dumps({"valid": False, "reason": "no candidate passed validation", "candidates": candidates}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
