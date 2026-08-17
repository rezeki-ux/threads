"""LIVE discovery of the anonymous Threads search pagination mechanism.

Fetches the server-rendered search page with the crawler user agent (no browser)
and inspects the embedded JSON for pagination cues (page_info / end_cursor /
has_next_page), then tests candidate continuation mechanisms.

This is diagnostic only: it does not store cookies or credentials.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
BASE = "https://www.threads.com"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def sjs_blocks(html: str):
    return re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S)


def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "AI"
    url = f"{BASE}/search?q={urllib.parse.quote(query)}"
    html = fetch(url)

    print(f"initial url: {url}")
    print(f"html len: {len(html)}")

    cursors = re.findall(r'"end_cursor"\s*:\s*"([^"]*)"', html)
    has_next = re.findall(r'"has_next_page"\s*:\s*(true|false)', html)
    print(f"end_cursor values: {cursors[:8]}")
    print(f"has_next_page values: {has_next[:8]}")

    # find page_info context
    idx = html.find("end_cursor")
    if idx >= 0:
        print("CONTEXT:", html[max(0, idx - 160):idx + 200].replace("\n", " ")[:360])

    # extract any 'page_info' / cursor-like structures from data-sjs
    for raw in sjs_blocks(html):
        if "end_cursor" not in raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue

        def walk(d, depth=0):
            if depth > 30 or d is None:
                return
            if isinstance(d, dict):
                if "page_info" in d and isinstance(d["page_info"], dict):
                    print("PAGE_INFO:", json.dumps(d["page_info"]))
                for v in d.values():
                    walk(v, depth + 1)
            elif isinstance(d, list):
                for it in d:
                    walk(it, depth + 1)

        walk(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
