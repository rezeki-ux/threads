"""Validate a Threads search GraphQL operation (doc_id + variables) by replaying
it against the anonymous /api/graphql endpoint.

This is a diagnostic tool. Anonymous keyword search no longer uses /api/graphql:
it reads the server-rendered /search page, so there is no anonymous search doc_id
to validate. This script remains useful for confirming whether a captured
GraphQL operation (e.g. an authenticated or pagination flow) is still current.

The "do not trust HTTP 200 alone" gate still applies. An operation is only
`valid` when ALL of the following hold:

  1. HTTP 200
  2. the body parses as JSON
  3. there is no "errors" array (a "missing_required_variable_value" / code
     1675012 payload is reported explicitly as a stale operation)
  4. "data" is present and not null
  5. the data tree contains at least one post id (thread_items[].post.pk)

No credentials are read, sent, or stored. The script needs no browser and no
third-party packages (stdlib only).

Usage:
    python validate_operation.py --doc-id 123 --variables '{"query":"$query"}' --query AI
    python validate_operation.py --store --query AI        # validate what the store holds

Exit code 0 means valid; 1 means invalid. Output is JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

GRAPHQL_URL = "https://www.threads.com/api/graphql"
UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

# Mirrors threads.relayProviderVars: the crawler flags that unlock anonymous
# persisted queries. The Go engine adds these automatically, so validation must
# include them to test the exact request the engine will send.
RELAY_PROVIDER_VARS = {
    "__relay_internal__pv__BarcelonaIsLoggedInrelayprovider": False,
    "__relay_internal__pv__BarcelonaIsInternalUserrelayprovider": False,
    "__relay_internal__pv__BarcelonaIsCrawlerrelayprovider": True,
    "__relay_internal__pv__BarcelonaOptionalCookiesEnabledrelayprovider": True,
    "__relay_internal__pv__BarcelonaIsLoggedOutrelayprovider": True,
}

STALE_CODE = 1675012


def substitute(template: dict, query: str, search_type: str = "") -> dict:
    """Expand a variables template: replace $query/$type/$search_type placeholders."""
    out: dict = {}
    for k, v in template.items():
        if isinstance(v, str):
            if v == "$query":
                out[k] = query
                continue
            if v in ("$type", "$search_type"):
                if search_type:
                    out[k] = search_type
                continue
        out[k] = v
    if "query" not in out:
        out["query"] = query
    return out


def walk_post_ids(data, _depth: int = 0) -> list:
    """Recursively collect post ids from thread_items[].post.pk/id."""
    if _depth > 30 or data is None:
        return []
    ids: list = []
    if isinstance(data, dict):
        items = data.get("thread_items")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("post"), dict):
                    post = item["post"]
                    for key in ("pk", "id"):
                        v = post.get(key)
                        if v:
                            ids.append(str(v))
                            break
        for value in data.values():
            ids.extend(walk_post_ids(value, _depth + 1))
    elif isinstance(data, list):
        for item in data:
            ids.extend(walk_post_ids(item, _depth + 1))
    return ids


def replay(doc_id: str, variables: dict, timeout: int = 30) -> dict:
    """POST the persisted query and return status/body. Raises nothing."""
    merged = dict(RELAY_PROVIDER_VARS)
    merged.update(variables)
    form = urllib.parse.urlencode(
        {
            "lsd": "t",
            "doc_id": doc_id,
            "variables": json.dumps(merged, separators=(",", ":")),
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=form,
        method="POST",
        headers={
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "X-FB-LSD": "t",
            "X-IG-App-ID": "238260118697367",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return {"status": resp.status, "content_type": resp.headers.get("Content-Type", ""), "body": body}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "content_type": e.headers.get("Content-Type", ""), "body": e.read()}
    except urllib.error.URLError as e:
        return {"valid": False, "reason": f"network error: {e.reason}", "status": None}


def validate(doc_id: str, variables: dict, query: str = "", search_type: str = "", timeout: int = 30) -> dict:
    """Validate a search operation. Returns a dict with `valid: bool` plus detail."""
    if not doc_id:
        return {"valid": False, "reason": "empty doc_id"}

    result = replay(doc_id, variables, timeout)
    status = result.get("status")
    if status != 200:
        result["valid"] = False
        result["reason"] = f"HTTP {status}"
        result.pop("body", None)
        return result

    parsed = None
    try:
        parsed = json.loads(result["body"])
    except (ValueError, UnicodeDecodeError):
        parsed = None

    if parsed is None:
        result["valid"] = False
        result["reason"] = "non-JSON response"
        result.pop("body", None)
        return result

    errors = parsed.get("errors") if isinstance(parsed, dict) else None
    if errors:
        messages = [e.get("message", "") for e in errors if isinstance(e, dict)]
        codes = [e.get("code") for e in errors if isinstance(e, dict)]
        if any(c == STALE_CODE for c in codes) or any(
            "missing_required_variable_value" in (m or "") for m in messages
        ):
            reason = "stale operation (missing_required_variable_value)"
        else:
            reason = "graphql errors: " + "; ".join(m for m in messages if m)[:200]
        result["valid"] = False
        result["reason"] = reason
        result.pop("body", None)
        return result

    data = parsed.get("data") if isinstance(parsed, dict) else None
    if data is None:
        result["valid"] = False
        result["reason"] = "data is null"
        result.pop("body", None)
        return result

    post_ids = walk_post_ids(data)
    if not post_ids:
        result["valid"] = False
        result["reason"] = "no post ids in data"
        result.pop("body", None)
        return result

    result.pop("body", None)
    result["valid"] = True
    result["reason"] = "ok"
    result["post_ids"] = post_ids[:5]
    result["post_count"] = len(post_ids)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--doc-id", help="doc_id to validate (defaults to the store)")
    ap.add_argument("--variables", help='variables template JSON, e.g. \'{"query":"$query"}\'')
    ap.add_argument("--query", default="AI", help="search keyword to substitute")
    ap.add_argument("--search-type", default="", help="optional --type value")
    ap.add_argument("--store", action="store_true", help="load doc_id+variables from the operation store")
    args = ap.parse_args(argv)

    doc_id = args.doc_id
    variables: dict | None = None
    if args.variables:
        try:
            variables = json.loads(args.variables)
        except ValueError as e:
            print(json.dumps({"valid": False, "reason": f"bad --variables JSON: {e}"}, indent=2))
            return 1

    if args.store or not doc_id:
        import operation_store  # local module

        search = operation_store.get_search()
        doc_id = doc_id or search.get("doc_id", "")
        if variables is None:
            variables = search.get("variables") or {}

    if not doc_id:
        print(json.dumps({"valid": False, "reason": "no doc_id provided and none in store"}, indent=2))
        return 1

    variables = substitute(variables or {"query": "$query"}, args.query, args.search_type)
    result = validate(doc_id, variables, args.query, args.search_type)
    print(json.dumps(result, indent=2))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
