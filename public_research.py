"""Public-friendly multi-source research, with honest coverage limits.

All provider queries are explicit actions. Neither news search nor public web
search covers every published article. Source links are discovery leads, never
a truth verdict. Provider credentials are only read from server secrets.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from gdelt_research import search_gdelt
from evidence import suggest_query, search_news, search_fact_checks, safe_link, EvidenceError

NEWS_MAX = 90
SEARCH_QUERIES = 3
WEB_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
SOCIAL_DOMAINS = {
    "X": ("x.com", "twitter.com"),
    "Facebook": ("facebook.com", "fb.com"),
    "Instagram": ("instagram.com",),
}
PROVENANCE_OPTIONS = ("WhatsApp", "Instagram", "X", "Facebook", "Spoken rumour", "Somewhere else")
EXCLUDE_DOMAINS = ("accounts.google.com", "support.google.com")
STOPNAMES = {"Breaking", "Urgent", "Viral", "Message", "According", "Please", "Forward", "Today", "Yesterday", "The"}
SOURCE_KINDS = ("news", "web", "fact_check")


class PublicSearchError(ValueError):
    pass


def automatic_terms(claim: str) -> str:
    return suggest_query(claim)[:160]


def suggest_names(claim: str) -> list[str]:
    """Weak, transparent named-phrase suggestions; no account identity assertions."""
    matches = re.findall(
        r"\b(?:[A-Z][a-zA-Z'-]{2,}|[A-Z]{2,})(?:\s+(?:of|the|and|for|[A-Z][a-zA-Z'-]{2,}|[A-Z]{2,})){1,5}",
        str(claim or "")[:2500],
    )
    result = []
    for candidate in matches:
        candidate = " ".join(candidate.split()).strip(" .,")
        if (len(candidate) >= 7 and candidate.split()[0] not in STOPNAMES
                and candidate.casefold() not in [x.casefold() for x in result]):
            result.append(candidate[:90])
    return result[:5]


def query_variants(claim: str) -> list[str]:
    claim = " ".join(str(claim or "").split())[:2500]
    if not claim:
        return []
    suggestions = automatic_terms(claim)
    # Use multiple searches, avoiding long literal messages that news indexing misses.
    tokens = suggestions.split()
    alternatives = [
        suggestions,
        " ".join(tokens[:5]),
        " ".join(tokens[-5:]) if len(tokens) >= 7 else " ".join(tokens[:3]),
    ]
    names = suggest_names(claim)
    if names and len(tokens) >= 4:
        alternatives[2] = names[0] + " " + " ".join(tokens[-3:])
    unique = []
    for candidate in alternatives:
        candidate = candidate.strip()[:170]
        if len(candidate) >= 3 and candidate.casefold() not in [x.casefold() for x in unique]:
            unique.append(candidate)
    return unique[:SEARCH_QUERIES]


def _brave_get(query: str, key: str, *, limit: int = 20) -> dict:
    if not key:
        raise PublicSearchError("Broad web search key is not configured.")
    params = urllib.parse.urlencode({"q": query[:450], "count": min(limit, 20), "safesearch": "moderate"})
    req = urllib.request.Request(
        WEB_ENDPOINT + "?" + params,
        headers={"Accept": "application/json", "X-Subscription-Token": key,
                 "User-Agent": "Rumourprint-AI/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = response.read(1_200_001)
            if len(payload) > 1_200_000:
                raise PublicSearchError("The search provider returned too much data.")
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise PublicSearchError("Unexpected web search response.")
            return data
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            msg = "Broad web search credential was rejected."
        elif exc.code == 403:
            msg = "Broad web search access is unavailable for this project."
        elif exc.code == 429:
            msg = "Broad web search has reached its usage limit."
        else:
            msg = f"Broad web search unavailable (HTTP {exc.code})."
        raise PublicSearchError(msg) from exc
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        raise PublicSearchError("Broad web search could not be completed.") from exc


def web_hits(query: str, key: str, *, requester=None, limit=20) -> list[dict]:
    getter = requester or _brave_get
    raw = getter(query, key, limit=limit)
    items = (raw.get("web") or {}).get("results") or []
    output = []
    for item in items[:limit]:
        url = safe_link(item.get("url", ""))
        title = str(item.get("title") or "").strip()[:220]
        if not url or not title:
            continue
        host = (urllib.parse.urlparse(url).hostname or "").casefold()
        if host in EXCLUDE_DOMAINS:
            continue
        output.append({
            "title": re.sub(r"<[^>]+>", "", title),
            "url": url,
            "publisher": host.removeprefix("www."),
            "date": str(item.get("age") or "Date not supplied")[:70],
            "description": re.sub(r"<[^>]+>", "", str(item.get("description") or ""))[:300],
            "type": "web",
        })
    return output


def _dedupe(results: list[dict], limit: int) -> list[dict]:
    seen, output = set(), []
    for item in results:
        url = str(item.get("url") or "").split("#", 1)[0].rstrip("/")
        # Ignore tracking query when comparing otherwise identical links.
        key = url.split("?", 1)[0].casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def investigate_text(
    claim: str, *, brave_key: str = "", fact_key: str = "",
    news_search=None, web_search=None, check_search=None, gdelt_search=None,
) -> dict:
    """Bounded, multi-query research. Always reports actual providers and errors."""
    claim = " ".join(str(claim or "").split())[:2500]
    if len(claim) < 10:
        raise PublicSearchError("Please enter a statement with at least ten characters.")
    queries = query_variants(claim)
    status, results = [], []
    rss_func = news_search or search_news
    web_func = web_search or web_hits

    def do_news(index: int, q: str) -> tuple[int, list[dict]]:
        # First is Uganda-focused, second looks globally in English, third Uganda again.
        region = ("UG", "WORLD", "UG")[min(index, 2)]
        try:
            return index, rss_func(q, limit=14, region=region)
        except TypeError:
            # Support older injectable/testing stubs; the actual backend has region support.
            return index, rss_func(q, limit=14)

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(do_news, i, q): ("Google News", q) for i, q in enumerate(queries)}
        for future in as_completed(futures):
            provider, q = futures[future]
            try:
                index, hits = future.result()
                for hit in hits:
                    hit = dict(hit)
                    hit["query"] = q
                    hit["provider"] = provider
                    hit["_order"] = index
                    results.append(hit)
                status.append({"provider": provider, "query": q, "count": len(hits), "error": ""})
            except (EvidenceError, PublicSearchError, OSError) as exc:
                status.append({"provider": provider, "query": q, "count": 0, "error": str(exc)})
    # Keep the first most-specific search first, not thread arrival order.
    results.sort(key=lambda x: x.get("_order", 10))

    # Independent world-news index; a separate source from Google News.
    # Do not call real network endpoints during injected offline tests.
    if gdelt_search is not None or (news_search is None and web_search is None):
        try:
            gdelt_func = gdelt_search or search_gdelt
            global_hits = gdelt_func(queries[0], limit=25)
            results.extend(dict(x, provider="GDELT world news index", query=queries[0]) for x in global_hits)
            status.append({"provider": "GDELT world news index", "query": queries[0],
                           "count": len(global_hits), "error": ""})
        except (ValueError, OSError) as exc:
            status.append({"provider": "GDELT world news index", "query": queries[0],
                           "count": 0, "error": "Additional global news index could not be searched right now."})

    if brave_key:
        for q in queries[:2]:
            try:
                broad = web_func(q, brave_key, limit=20)
                results.extend(dict(x, provider="Independent web search", query=q) for x in broad)
                status.append({"provider": "Independent web search", "query": q, "count": len(broad), "error": ""})
            except (PublicSearchError, OSError, ValueError) as exc:
                status.append({"provider": "Independent web search", "query": q, "count": 0, "error": str(exc)})
    else:
        status.append({"provider": "Independent web search", "query": "",
                       "count": 0, "error": "Not enabled by this app's administrator."})

    checks = []
    if fact_key:
        try:
            check_func = check_search or search_fact_checks
            checks = check_func(queries[0], fact_key)
            status.append({"provider": "Published fact-checks", "query": queries[0], "count": len(checks), "error": ""})
        except (EvidenceError, OSError) as exc:
            status.append({"provider": "Published fact-checks", "query": queries[0], "count": 0, "error": str(exc)})

    return {
        "claim": claim,
        "keywords": automatic_terms(claim),
        "queries": queries,
        "articles": _dedupe(results, NEWS_MAX),
        "reviews": _dedupe(checks, 8),
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": ("Searches multiple keyword variations in Google News and GDELT, with independent web search "
                  "and published fact-checks when enabled. Some stories and private/unindexed posts "
                  "cannot be found. A result is not a verdict."),
    }


def _social_platform(url: str) -> str:
    host = (urllib.parse.urlparse(url).hostname or "").casefold().removeprefix("www.")
    for name, domains in SOCIAL_DOMAINS.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return name
    return ""


def _is_post_link(url: str, platform: str) -> bool:
    p = urllib.parse.urlsplit(url).path.casefold()
    if platform == "X":
        return bool(re.search(r"/[a-z0-9_]{1,15}/status/\d{8,22}", p))
    if platform == "Instagram":
        return bool(re.search(r"/(?:p|reel|tv)/[a-z0-9_-]+", p))
    if platform == "Facebook":
        return any(x in p for x in ("/posts/", "/permalink/", "/videos/", "/story.php")) or "story_fbid=" in url
    return False


def social_discovery(
    claim: str, *, brave_key: str = "", web_search=None,
) -> dict:
    """Returns only indexed post URLs; no unsupported assertion of account identity."""
    term = automatic_terms(claim)
    names = suggest_names(claim)
    q = " ".join(term.split()[:5])
    search_links = {
        "X": "https://x.com/search?" + urllib.parse.urlencode({"q": q, "f": "live"}),
        "Facebook": "https://www.google.com/search?" + urllib.parse.urlencode({"q": f"site:facebook.com {q}"}),
        "Instagram": "https://www.google.com/search?" + urllib.parse.urlencode({"q": f"site:instagram.com {q}"}),
    }
    results, warnings = [], []
    if brave_key:
        func = web_search or web_hits
        for domain in ("x.com", "facebook.com", "instagram.com"):
            try:
                hits = func(f"site:{domain} {q}", brave_key, limit=12)
                for hit in hits:
                    platform = _social_platform(hit["url"])
                    if platform and _is_post_link(hit["url"], platform):
                        results.append({**hit, "platform": platform,
                                        "status": "Indexed public post — authorship not verified"})
            except (PublicSearchError, ValueError, OSError) as exc:
                warnings.append(str(exc))
    else:
        warnings.append("Automatic cross-platform web search is not configured; use the search links below.")
    return {"posts": _dedupe(results, 35), "search_links": search_links,
            "possible_names": names, "warnings": warnings,
            "scope": "Indexed public posts only. Private, deleted or unindexed posts cannot be searched. "
                     "Search indexes cannot authenticate real-world account ownership."}
