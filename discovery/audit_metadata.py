"""Audit helper (2): dump nested object structures for mentions/hashtags, links,
bio links, and reply authorship. Evidence only; no credentials."""

from __future__ import annotations

import json
import re
import urllib.request

UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
BASE = "https://www.threads.com"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def sjs_blocks(html: str):
    return re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S)


def walk_all(data, depth=0, acc=None):
    if acc is None:
        acc = []
    if depth > 40 or data is None:
        return acc
    if isinstance(data, dict):
        acc.append(data)
        for v in data.values():
            walk_all(v, depth + 1, acc)
    elif isinstance(data, list):
        for it in data:
            walk_all(it, depth + 1, acc)
    return acc


def collect(html, needle):
    out = []
    for raw in sjs_blocks(html):
        if needle not in raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        out.extend(walk_all(data))
    return out


def dump_profile_links():
    objs = collect(fetch(f"{BASE}/@zuck"), "follower_count")
    for o in objs:
        if "username" in o and "bio_links" in o:
            print("BIO_LINKS:", json.dumps(o.get("bio_links"), ensure_ascii=False))
            print("is_private field:", o.get("text_post_app_is_private"))
            return


def dump_post_nested():
    objs = collect(fetch(f"{BASE}/@zuck/post/Db2wI-DilLt"), "like_count")
    for o in objs:
        if "pk" in o and "text_post_app_info" in o:
            tpi = o["text_post_app_info"]
            if isinstance(tpi, dict):
                print("TEXT_FRAGMENTS:", json.dumps(tpi.get("text_fragments"), ensure_ascii=False)[:500])
                print("SHARE_INFO:", json.dumps(tpi.get("share_info"), ensure_ascii=False)[:500])
                print("LINK_PREVIEW_ATTACHMENT:", json.dumps(tpi.get("link_preview_attachment"), ensure_ascii=False)[:300])
                print("IS_REPLY:", tpi.get("is_reply"))
                print("CANONICAL_URL:", o.get("canonical_url"))
                print("IS_PAID_PARTNERSHIP:", o.get("is_paid_partnership"))
                print("HAS_AUDIO:", o.get("has_audio"))
                print("ORIGINAL WxH:", o.get("original_width"), o.get("original_height"))
                print("USERTAGS:", json.dumps(o.get("usertags"), ensure_ascii=False)[:300])
                print("DETECTED_LANGUAGE:", o.get("detected_language"))
            return


def dump_reply():
    # a known reply from an earlier search run
    objs = collect(fetch(f"{BASE}/search?q=AI"), "like_count")
    for o in objs:
        if "pk" not in o or "text_post_app_info" not in o:
            continue
        tpi = o.get("text_post_app_info") or {}
        rta = tpi.get("reply_to_author")
        if rta:
            print("REPLY_TO_AUTHOR:", json.dumps(rta, ensure_ascii=False))
            print("IS_REPLY flag:", tpi.get("is_reply"))
            return
    print("(no reply found in this window)")


if __name__ == "__main__":
    print("=== PROFILE bio_links ===")
    dump_profile_links()
    print("\n=== POST nested ===")
    dump_post_nested()
    print("\n=== REPLY author ===")
    dump_reply()
