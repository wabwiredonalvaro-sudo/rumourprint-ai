"""Original-public-X-post research, with strict author-ID attribution and human review.

Supports X API v2 profile resolution, recent/full-archive search (if permitted),
and single-post lookup using a server-configured X_BEARER_TOKEN.

X is a third-party source, not proof of a person's identity. Account ownership
must be corroborated outside the platform; posts can be satirical, quoted,
edited, deleted or context-dependent. No claim is automatically declared true.
"""
from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
import json
import re
from urllib import error, parse, request

from evidence import suggest_query

API_BASE = "https://api.x.com"
MAX_RESPONSE_BYTES = 900_000
HANDLE_PATTERN = re.compile(r"[A-Za-z0-9_]{1,15}\Z")
POST_PATH_PATTERN = re.compile(r"/([A-Za-z0-9_]{1,15})/status/(\d{8,22})/?\Z")
USER_FIELDS = "name,username,description,protected,verified"
POST_FIELDS = "author_id,created_at,referenced_tweets,lang"
TEXT_STOP = {
    "a", "an", "and", "are", "been", "by", "for", "from", "has",
    "have", "in", "is", "it", "of", "on", "or", "said", "says",
    "that", "the", "their", "they", "this", "to", "was", "were",
    "will", "with",
}
NEGATIONS = {"not", "no", "never", "false", "denied", "didnt", "isnt", "wasnt", "hasnt", "doesnt"}


class SocialLookupError(ValueError):
    """Safe, user-facing errors. Never include auth headers or token values."""


def clean_handle(raw: str) -> str:
    handle = str(raw or "").strip().removeprefix("@")
    if not HANDLE_PATTERN.fullmatch(handle):
        raise SocialLookupError("Enter a valid X handle: 1–15 English letters, digits or underscores (e.g. @example).")
    return handle


def _terms(value: str, limit: int = 4) -> list[str]:
    selected, seen = [], set()
    for word in re.findall(r"[^\W_]{3,}", str(value or "").casefold()[:500], flags=re.UNICODE):
        if word in TEXT_STOP or word in seen:
            continue
        seen.add(word)
        selected.append(word)
        if len(selected) == limit:
            break
    return selected


def make_x_search_url(handle: str, claim: str) -> str:
    """Plain browser search. Availability depends on user's X login/search view."""
    handle = clean_handle(handle)
    keywords = " ".join(_terms(suggest_query(claim), 3))
    query = f"from:{handle} {keywords}".strip()
    return "https://x.com/search?" + parse.urlencode({"q": query, "f": "live"})



def make_other_platform_search_url(platform: str, name: str, claim: str) -> str:
    """External discovery only; indexed snippets cannot prove account attribution."""
    sites = {
        "Facebook": "facebook.com",
        "Instagram": "instagram.com",
        "LinkedIn": "linkedin.com",
    }
    if platform not in sites:
        raise SocialLookupError("Unsupported social discovery platform.")
    subject = re.sub(r"[^\w\s.'-]", " ", str(name or ""))[:90].strip()
    keywords = " ".join(_terms(suggest_query(claim), 4))
    query = " ".join(x for x in [f"site:{sites[platform]}", subject, keywords] if x)
    return "https://www.google.com/search?" + parse.urlencode({"q": query})


def make_x_api_query(handle: str, claim: str) -> str:
    """Prevent external search operators from escaping the trusted from: filter."""
    handle = clean_handle(handle)
    terms = _terms(suggest_query(claim), 4)
    if not terms:
        return f"from:{handle} -is:retweet"
    return f"from:{handle} ({' OR '.join(terms)}) -is:retweet"


def parse_x_post_url(raw: str) -> dict:
    value = str(raw or "").strip()
    try:
        url = parse.urlsplit(value)
        host = (url.hostname or "").casefold()
        port = url.port
    except ValueError as exc:
        raise SocialLookupError("This X post URL is invalid.") from exc
    if (
        url.scheme != "https"
        or host not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com", "mobile.twitter.com"}
        or port not in (None, 443)
        or url.username or url.password
    ):
        raise SocialLookupError("Use a direct HTTPS link to an X post (x.com/.../status/...).")
    match = POST_PATH_PATTERN.fullmatch(url.path)
    if not match:
        raise SocialLookupError("Paste the original X post link, not a profile or search-results page.")
    username, post_id = match.groups()
    return {
        "username_in_url": username,
        "post_id": post_id,
        "url": f"https://x.com/{username}/status/{post_id}",
    }


def _request_json(path: str, params: dict, token: str) -> dict:
    """Only app-controlled X API endpoints; bounded network and no redirects."""
    if not token or any(c in token for c in "\r\n"):
        raise SocialLookupError("An X developer API token has not been configured.")
    allowed = (
        re.fullmatch(r"/2/users/by/username/[A-Za-z0-9_]{1,15}", path)
        or re.fullmatch(r"/2/tweets/\d{8,22}", path)
        or path in ("/2/tweets/search/recent", "/2/tweets/search/all")
    )
    if not allowed:
        raise SocialLookupError("Unsupported X API operation.")
    endpoint = API_BASE + path + ("?" + parse.urlencode(params) if params else "")
    headers = {
        "Authorization": "Bearer " + token.strip(),
        "Accept": "application/json",
        "User-Agent": "RUMOURPRINT-AI/0.9 (journalism research)",
    }
    try:
        opener = request.build_opener(_NoRedirect)
        with opener.open(request.Request(endpoint, headers=headers), timeout=12) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise SocialLookupError("X returned more data than this check can safely process.")
            data = json.loads(content.decode("utf-8"))
            if not isinstance(data, dict):
                raise SocialLookupError("X returned an unexpected response.")
            if data.get("errors") and not data.get("data"):
                raise SocialLookupError("X could not complete the request for the selected account or post.")
            return data
    except error.HTTPError as exc:
        if exc.code == 401:
            raise SocialLookupError("X rejected the API token. The administrator must check credentials.") from exc
        if exc.code == 403:
            raise SocialLookupError("X denied this endpoint. Check developer permissions, API credits and access tier.") from exc
        if exc.code == 404:
            raise SocialLookupError("X could not find that public account or post.") from exc
        if exc.code == 429:
            raise SocialLookupError("X API rate limit reached. Try again after the limit resets.") from exc
        raise SocialLookupError(f"X API request failed (HTTP {exc.code}).") from exc
    except error.URLError as exc:
        raise SocialLookupError("Could not contact X API. Check connectivity or try again.") from exc
    except (TimeoutError, OSError) as exc:
        raise SocialLookupError("X did not respond in time. Try again later.") from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SocialLookupError("X returned an unreadable response.") from exc


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SocialLookupError("The X API redirected the request unexpectedly; request blocked.")


def _profile_from_api(handle: str, token: str, transport) -> dict:
    user_response = transport(
        f"/2/users/by/username/{handle}",
        {"user.fields": USER_FIELDS},
        token,
    )
    user = user_response.get("data")
    if not isinstance(user, dict) or not str(user.get("id", "")).isdigit():
        raise SocialLookupError("X did not return a public profile for this handle.")
    if str(user.get("username", "")).casefold() != handle.casefold():
        raise SocialLookupError("X returned a different handle than the requested account.")
    if user.get("protected"):
        raise SocialLookupError("This is a protected account. Private posts cannot be searched.")
    return {
        "id": str(user["id"]),
        "name": str(user.get("name") or handle)[:130],
        "username": str(user["username"]),
        "profile_url": "https://x.com/" + handle,
        "premium_badge": bool(user.get("verified")),
        "identity_status": "Not independently verified",
    }


def _extract_post(post: dict, profile: dict) -> dict | None:
    if not isinstance(post, dict):
        return None
    if str(post.get("author_id", "")) != profile["id"]:
        return None
    post_id = str(post.get("id", ""))
    if not re.fullmatch(r"\d{8,22}", post_id):
        return None
    refs = post.get("referenced_tweets") or []
    if any(isinstance(x, dict) and x.get("type") == "retweeted" for x in refs):
        # A retweet by the account does not establish authorship of the text.
        return None
    text = str(post.get("text") or "").strip()[:2800]
    if not text:
        return None
    kind = "Reply" if any(isinstance(x, dict) and x.get("type") == "replied_to" for x in refs) else (
        "Quote post" if any(isinstance(x, dict) and x.get("type") == "quoted" for x in refs) else "Original account post"
    )
    return {
        "id": post_id,
        "author_id": str(post["author_id"]),
        "text": text,
        "published_at": str(post.get("created_at") or "Date unavailable")[:40],
        "url": f"https://x.com/{profile['username']}/status/{post_id}",
        "kind": kind,
    }


def _normalise(value: str) -> str:
    return " ".join(re.findall(r"\w+", str(value or "").casefold(), flags=re.UNICODE))


def compare_post_wording(claim: str, post: str) -> dict:
    """Compare only *wording*. Never infer the author's intent or truth of claim."""
    claim_normalised, post_normalised = _normalise(claim), _normalise(post)
    if not claim_normalised or not post_normalised:
        return {"label": "Not enough text", "score": 0}
    cwords, pwords = set(_terms(claim, 150)), set(_terms(post, 300))
    overlap = len(cwords & pwords) / max(1, len(cwords))
    sequence = SequenceMatcher(a=claim_normalised, b=post_normalised, autojunk=False).ratio()
    lexical = 100 * max(sequence, overlap * 0.8)
    polarity_changes = bool(set(claim_normalised.split()) & NEGATIONS) != bool(set(post_normalised.split()) & NEGATIONS)
    # Quoted/denied/parody statements need human contextual interpretation.
    if claim_normalised == post_normalised and not polarity_changes:
        label = "Matching wording on account"
    elif overlap >= 0.78 or sequence >= 0.76:
        label = "Potentially related post — check full context"
    elif overlap >= 0.36 or sequence >= 0.43:
        label = "Partial topic overlap — review manually"
    else:
        label = "No clear wording match"
    if polarity_changes and label == "Matching wording on account":
        label = "Potentially related post — check full context"
    return {"label": label, "score": round(min(100, lexical), 1)}


def search_account_posts(
    handle: str, claim: str, token: str, *, archive: bool = False, transport=None,
) -> dict:
    """One X user lookup + one bounded result page. No paginated or bulk harvesting."""
    handle = clean_handle(handle)
    if len(str(claim).strip()) < 8:
        raise SocialLookupError("Enter a specific claim or quotation to search.")
    transport = transport or _request_json
    profile = _profile_from_api(handle, token, transport)
    path = "/2/tweets/search/all" if archive else "/2/tweets/search/recent"
    query = make_x_api_query(handle, claim)
    payload = transport(
        path,
        {"query": query, "tweet.fields": POST_FIELDS, "max_results": 10},
        token,
    )
    if payload.get("errors"):
        raise SocialLookupError("X reported incomplete search results; no reliable conclusion can be drawn.")
    posts = []
    for item in payload.get("data", [])[:10]:
        parsed = _extract_post(item, profile)
        if parsed:
            parsed["comparison"] = compare_post_wording(claim, parsed["text"])
            posts.append(parsed)
    posts.sort(key=lambda p: p["comparison"]["score"], reverse=True)
    return {
        "mode": "Full archive" if archive else "Recent 7 days",
        "query": query,
        "account": profile,
        "posts": posts,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "coverage": "At most 10 posts returned from one search page; not an exhaustive account history.",
        "finding": (
            "Possible matching account post(s) found — verify the quotation and account ownership"
            if any(p["comparison"]["score"] >= 40 for p in posts) else
            "No sufficiently matching public post identified in this limited query"
        ),
    }


def verify_post_link(handle: str, raw_url: str, claim: str, token: str, *, transport=None) -> dict:
    """Compare a direct post's immutable author ID against the current account ID."""
    handle = clean_handle(handle)
    post_ref = parse_x_post_url(raw_url)
    transport = transport or _request_json
    profile = _profile_from_api(handle, token, transport)
    payload = transport(
        f"/2/tweets/{post_ref['post_id']}",
        {"tweet.fields": POST_FIELDS},
        token,
    )
    post_data = payload.get("data")
    if not isinstance(post_data, dict):
        raise SocialLookupError("X did not return that public post; it may be deleted, unavailable or restricted.")
    if str(post_data.get("id", "")) != post_ref["post_id"]:
        raise SocialLookupError("X returned a different post ID than the supplied link.")
    owner_matches = str(post_data.get("author_id", "")) == profile["id"]
    parsed = _extract_post(post_data, profile) if owner_matches else None
    return {
        "mode": "Direct post",
        "post_url": post_ref["url"],
        "account": profile,
        "owner_matches": owner_matches,
        "post": parsed,
        "finding": (
            "The X API attributes this post to the specified account ID — check wording and identity"
            if owner_matches else "X attributes this post to a DIFFERENT account ID"
        ),
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "comparison": compare_post_wording(claim, parsed["text"]) if parsed else None,
    }


def _short_quote(text: str, limit: int = 25) -> str:
    words = str(text or "").split()
    return " ".join(words[:limit]) + ("…" if len(words) > limit else "")


def social_evidence_brief(
    handle: str,
    claim: str,
    result: dict | None,
    notes: str = "",
    account_confirmed: bool = False,
) -> str:
    handle = clean_handle(handle)
    lines = [
        "# RUMOURPRINT AI — Original X-account statement research",
        "",
        f"Prepared: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"Claim: {str(claim or '').strip()[:2000]}",
        f"Account examined: @{handle}",
        f"Account ownership independently checked by journalist: {'YES — self-reported by reviewer' if account_confirmed else 'NO'}",
        "Final statement attribution: PENDING EDITORIAL REVIEW",
        "",
        "An X blue/Premium checkmark alone does not establish the identity of an account owner.",
        "No result may reflect limited access, search coverage, edited/deleted posts or API errors.",
    ]
    if result:
        lines.extend(["", f"Mode: {result.get('mode', 'Unknown')}",
                      f"Checked: {result.get('checked_at', 'Unknown')}",
                      f"Finding: {result.get('finding', 'Unresolved')}"])
        if result.get("query"):
            lines.append("X search syntax: " + result["query"])
        if result.get("coverage"):
            lines.append("Coverage warning: " + result["coverage"])
        posts = result.get("posts", [])
        if result.get("post"):
            posts = [result["post"]]
        for i, p in enumerate(posts[:10], 1):
            lines += [
                f"Post {i}: {p['url']}",
                f"Published: {p['published_at']} | Type: {p['kind']}",
                f"Extract: “{_short_quote(p['text'])}”",
                f"Text comparison: {p['comparison']['label'] if 'comparison' in p else 'Manual review required'}",
            ]
        if result.get("post_url") and not posts:
            lines.append("Investigated original URL: " + result["post_url"])
    lines.extend(["", "## Journalist's notes", str(notes or "No reviewer notes provided.")[:3000],
                  "", "Verify the account from an independently controlled official website or on-record confirmation, "
                  "open each original post, and check quotation, chronology, edits and thread context."])
    return "\n".join(lines)
