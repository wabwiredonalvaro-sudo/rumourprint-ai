"""Bounded public X search for user-supplied claims; no identity/official-status guesswork."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote

from social_verification import _request_json, SocialLookupError
from public_research import automatic_terms

MAX_POSTS = 20


def public_x_posts(claim: str, *, token: str, transport=None) -> dict:
    """A single non-paginated request for public posts mentioning keywords."""
    if not token:
        return {
            "posts": [],
            "coverage": "X developer API not configured. Manual public X search is available.",
            "error": "",
        }
    tokens = re.findall(r"[^\W_]{3,}", automatic_terms(claim).casefold(), flags=re.UNICODE)
    # Escape query operators by using only alphanumeric words and simple OR.
    words = list(dict.fromkeys(x for x in tokens if x.isalnum()))[:5]
    if not words:
        return {"posts": [], "coverage": "No usable search words.", "error": ""}
    query = "(" + " OR ".join(words) + ") -is:retweet"
    send = transport or _request_json
    try:
        raw = send(
            "/2/tweets/search/recent",
            {
                "query": query, "tweet.fields": "author_id,created_at,referenced_tweets",
                "expansions": "author_id",
                "user.fields": "id,name,username,verified,protected,description",
                "max_results": MAX_POSTS,
            },
            token,
        )
        users = {
            str(u.get("id")): u
            for u in (raw.get("includes") or {}).get("users") or []
            if isinstance(u, dict)
        }
        posts = []
        for item in raw.get("data") or []:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("id") or "")
            aid = str(item.get("author_id") or "")
            if not re.fullmatch(r"\d{8,22}", pid) or not aid.isdigit():
                continue
            refs = item.get("referenced_tweets") or []
            if any(r.get("type") == "retweeted" for r in refs if isinstance(r, dict)):
                continue
            owner = users.get(aid) or {}
            handle = str(owner.get("username") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
                continue
            txt = str(item.get("text") or "").strip()
            if not txt:
                continue
            posts.append({
                "url": f"https://x.com/{handle}/status/{pid}",
                "profile": f"https://x.com/{handle}",
                "handle": handle,
                "display_name": str(owner.get("name") or handle)[:120],
                "text": txt[:1000],
                "created_at": str(item.get("created_at") or "Date unavailable")[:42],
                "account_id": aid,
                "identity": "Account owner not independently verified",
                "post_kind": "Reply" if any(
                    isinstance(r, dict) and r.get("type") == "replied_to" for r in refs
                ) else "Public post",
            })
        return {
            "posts": posts[:MAX_POSTS],
            "coverage": (
                "Recent public posts returned by X (roughly seven days), maximum 20 posts "
                "from one search page; not a complete social-media archive."
            ),
            "error": "",
            "search_query": query,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    except (SocialLookupError, OSError) as exc:
        return {"posts": [], "coverage": "No X posts retrieved. An empty result is inconclusive.",
                "error": str(exc)}
