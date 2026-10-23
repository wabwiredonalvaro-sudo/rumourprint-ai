"""RUMOURPRINT Stage 3: evidence *discovery*, not automated truth checking.

Only two fixed HTTPS endpoints are requested; no user-supplied URLs are fetched.
Fact-check API results include published reviewers' ratings for potentially
related claims; neither news search results nor ratings prove a new claim.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

NEWS_URL = "https://news.google.com/rss/search"
FACTCHECK_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
MAX_RESPONSE_BYTES = 2_000_000
USER_AGENT = "RumourprintResearch/0.4.1 (newsroom educational prototype)"


class EvidenceError(Exception):
    """A readable external-service error."""


def clean_text(text: object, max_len: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:max_len]


def suggest_query(claim: str) -> str:
    """Provide an *editable* short search term, no false claim extraction."""
    words = re.findall(r"[\w’'-]+", clean_text(claim, 1300), re.UNICODE)
    remove = {"breaking", "urgent", "viral", "please", "share", "forward", "message", "reportedly", "according", "everyone", "this", "just", "now", "that", "following", "after", "the", "and", "has", "have", "been", "from", "with", "said", "some", "there", "their", "were", "was", "are"}
    selected = [w for w in words if w.casefold() not in remove and len(w) > 2]
    return " ".join(selected[:10])[:180] or clean_text(claim, 180)


def _get(url: str, params: dict[str, str | int], *, timeout: int = 11) -> bytes:
    address = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(address, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise EvidenceError(f"Service returned HTTP {response.status}.")
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise EvidenceError("Source returned more data than expected.")
            return payload
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 401, 403):
            # Never display the provider URL or raw error body: it may expose the API key.
            if url == FACTCHECK_URL:
                if exc.code == 400:
                    raise EvidenceError("Fact-check API returned HTTP 400. Confirm the key is valid and the API request is permitted.") from exc
                if exc.code == 401:
                    raise EvidenceError("Fact-check API returned HTTP 401. Check the API key and its restrictions.") from exc
                raise EvidenceError("Fact-check API returned HTTP 403. Enable Fact Check Tools API for the key's Google Cloud project, and check key restrictions/quota.") from exc
            raise EvidenceError(f"News provider rejected the request (HTTP {exc.code}). Try again later.") from exc
        if exc.code == 429:
            raise EvidenceError("The source rate limit was reached. Try again later.") from exc
        raise EvidenceError(f"External source returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EvidenceError("Couldn't reach the live source. Check your internet connection and try again.") from exc


def safe_link(url: object) -> str:
    """Only link HTTPS/HTTP URLs with a hostname. Never render injected protocols."""
    value = str(url or "").strip()
    try:
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            return ""
        if parsed.hostname.casefold() in ("localhost", "127.0.0.1", "::1"):
            return ""
    except ValueError:
        return ""
    return value[:1800]


def _iso_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return clean_text(raw, 24)[:10]


def broaden_query(query: str) -> str:
    """A transparent, simpler search for when an exact long query yields no headlines."""
    words = re.findall(r"[\w’'-]+", clean_text(query, 200), re.UNICODE)
    # Keep a few distinctive early words and preserve original term order.
    stop = {"has", "been", "following", "after", "all", "the", "an", "a", "to", "for", "with", "under", "directive", "emergency", "government", "reportedly", "announced"}
    short = [w for w in words if w.casefold() not in stop and len(w) > 2][:4]
    return " ".join(short) if short else " ".join(words[:3])


def search_news(query: str, *, limit: int = 8, transport=_get) -> list[dict]:
    """Search indexed news *headlines*, not full-text evidence or endorsements."""
    query = clean_text(query, 200)
    if len(query) < 3:
        raise EvidenceError("Enter at least three characters to search live news.")
    raw = transport(NEWS_URL, {"q": query, "hl": "en-UG", "gl": "UG", "ceid": "UG:en"})
    try:
        tree = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise EvidenceError("The news provider returned an invalid feed.") from exc
    if tree.tag != "rss":
        raise EvidenceError("The news provider did not return its expected RSS feed.")
    out, seen = [], set()
    for item in tree.findall("./channel/item"):
        title = clean_text(item.findtext("title"), 300)
        url = safe_link(item.findtext("link"))
        publisher = clean_text(item.findtext("source"), 100)
        date = _iso_date(item.findtext("pubDate") or "")
        if not title or not url or url in seen:
            continue
        seen.add(url)
        out.append({"type": "news", "title": title, "publisher": publisher or "News publisher not supplied", "url": url,
                    "date": date, "claim": "", "rating": "", "description": "Indexed news headline; article not independently evaluated."})
        if len(out) >= limit:
            break
    return out


def search_fact_checks(query: str, api_key: str, *, limit: int = 8, transport=_get) -> list[dict]:
    """Return public fact-check articles. Ratings belong to original reviewers."""
    query, api_key = clean_text(query, 200), api_key.strip()
    if len(query) < 3:
        raise EvidenceError("Enter a search term for published fact checks.")
    if not api_key:
        raise EvidenceError("Enter a Google Fact Check Tools API key or search news without one.")
    raw = transport(FACTCHECK_URL, {"query": query, "key": api_key, "pageSize": min(25, max(3, limit * 2))})
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise EvidenceError("Fact-check provider returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise EvidenceError("Fact-check provider returned an unexpected response.")
    out, seen = [], set()
    for claim in data.get("claims", []):
        if not isinstance(claim, dict):
            continue
        for review in claim.get("claimReview", []):
            url = safe_link(review.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            pub = review.get("publisher") or {}
            out.append({
                "type": "fact_check", "title": clean_text(review.get("title") or claim.get("text"), 300),
                "publisher": clean_text(pub.get("name") or pub.get("site") or "Fact-check publisher", 100),
                "url": url, "date": clean_text(review.get("reviewDate"), 30)[:10],
                "claim": clean_text(claim.get("text"), 500),
                "rating": clean_text(review.get("textualRating"), 150),
                "description": "Published review about a potentially related claim. Verify it addresses this precise claim and date.",
            })
            if len(out) >= limit:
                return out
    return out


def build_brief(claim: str, search_term: str, news: list[dict], checks: list[dict], notes: str = "") -> str:
    """Downloadable, source-linked research brief — deliberately no AI verdict."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["# RUMOURPRINT AI — Evidence research brief", "", f"Prepared: {now}", "Status: UNDER INVESTIGATION — NO AUTOMATED TRUTH VERDICT", "", "## Submitted claim", clean_text(claim, 2500), "", f"Search terms: {clean_text(search_term, 200)}", "", "## Published fact-check reviews"]
    if not checks:
        lines.append("No fact-check results collected. This does not establish the claim is true or false.")
    for idx, item in enumerate(checks, 1):
        lines += [f"{idx}. {item['title']} — {item['publisher']} ({item['date'] or 'date unavailable'})", f"   - URL: {item['url']}", f"   - Claim reviewed: {item['claim'] or 'Not supplied'}", f"   - Publisher's rating: {item['rating'] or 'Not supplied'}", "   - The review may assess a different or older version of this claim."]
    lines += ["", "## News headlines for follow-up"]
    if not news:
        lines.append("No news headlines collected. Search results are not a measure of truth.")
    for idx, item in enumerate(news, 1):
        lines += [f"{idx}. {item['title']} — {item['publisher']} ({item['date'] or 'date unavailable'})", f"   - URL: {item['url']}", "   - Headline only; open and verify the underlying article and its evidence."]
    lines += ["", "## Journalist's notes", clean_text(notes, 4000) or "No reviewer notes provided.", "", "## Editorial safeguards", "- Verify the original claim, exact date, location and source before publication.", "- Prefer primary records and on-record confirmations over headlines or search ranking.", "- Fact-check ratings belong to their named publishers; do not transfer them to a differently worded claim.", "- Absence of search results never proves truth or falsehood.", "- Remove private and identifying information before uploading claims to a public search service.", ""]
    return "\n".join(lines)
