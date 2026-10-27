"""Bounded publisher-article extraction and conservative, review-only claim comparison.

Source text is not a verdict. All assessments are *preliminary* and must
be accepted or rejected by a journalist after viewing the linked source.
Never fetch arbitrary URLs: an explicit public-publisher allowlist blocks
internal services, cloud metadata endpoints, redirect pivots and SSRF.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
import urllib.error
import urllib.parse
import urllib.request

MAX_ARTICLE_BYTES = 1_800_000
MAX_ARTICLE_CHARS = 24_000
MAX_CLAIM_CHARS = 2500
MAX_EXCERPT_WORDS = 23
PUBLISHERS = (
    "news.mak.ac.ug", "mak.ac.ug",
    "monitor.co.ug", "newvision.co.ug", "nilepost.co.ug",
    "observer.ug", "ugandaradionetwork.net", "softpower.ug",
    "independent.co.ug", "chimpreports.com", "pmldaily.com",
    "bbc.com", "bbc.co.uk", "reuters.com", "apnews.com",
    "africacheck.org", "fullfact.org", "factcheck.org",
    "who.int", "un.org", "worldbank.org",
    "statehouse.go.ug", "parliament.go.ug", "bou.or.ug",
)
STOP = {
    "the", "a", "an", "of", "on", "and", "or", "for", "from", "to",
    "in", "at", "with", "by", "is", "are", "was", "were",
    "be", "been", "has", "have", "had", "this", "that", "its",
    "it", "as", "after", "before", "said", "says", "say",
}
NEGATIONS = {"not", "never", "no", "denied", "false", "didnt", "doesnt", "isnt", "wasnt", "hasnt", "havent"}
UNCERTAINTY = {"may", "might", "could", "possibly", "alleged", "allegedly", "rumour", "rumor", "claimed"}
QUOTE_CONTEXT = {"rumour", "rumor", "claimed", "alleged", "false", "fake", "debunked", "misleading", "denied"}


class ArticleAccessError(ValueError):
    pass


def validate_article_url(url: str) -> str:
    value = (url or "").strip()
    if len(value) > 1500:
        raise ArticleAccessError("The source URL is too long.")
    try:
        parts = urllib.parse.urlsplit(value)
        host = (parts.hostname or "").rstrip(".").casefold()
        port = parts.port
    except ValueError as exc:
        raise ArticleAccessError("Invalid article URL.") from exc
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        raise ArticleAccessError("Only ordinary HTTPS publisher URLs are supported.")
    if not host or not any(host == p or host.endswith("." + p) for p in PUBLISHERS):
        raise ArticleAccessError(
            "This source is not on the supported publisher list. Open it manually, "
            "or provide a direct supported publisher URL, not a Google News redirect."
        )
    return value


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_article_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_download(url: str) -> tuple[bytes, str, str]:
    opener = urllib.request.build_opener(_CheckedRedirect)
    request = urllib.request.Request(
        url, headers={"User-Agent": "RUMOURPRINT-EvidenceDesk/1.0 (+public research)", "Accept": "text/html"}
    )
    try:
        with opener.open(request, timeout=9) as response:
            final_url = validate_article_url(response.geturl())
            mime = (response.headers.get("Content-Type") or "").lower()
            if "text/html" not in mime and "application/xhtml+xml" not in mime:
                raise ArticleAccessError("This URL does not return an HTML article.")
            data = response.read(MAX_ARTICLE_BYTES + 1)
            if len(data) > MAX_ARTICLE_BYTES:
                raise ArticleAccessError("This article exceeds the safe extraction limit.")
            return data, final_url, mime
    except ArticleAccessError:
        raise
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise ArticleAccessError("The publisher blocked or did not respond to article extraction. Open the source manually.") from exc


def _default_extract(payload: bytes, url: str) -> str:
    from trafilatura import extract

    return extract(
        payload, url=url, output_format="txt",
        include_comments=False, favor_precision=True
    ) or ""


def fetch_article(url: str, *, downloader=None, extractor=None) -> dict:
    """Return publisher URL + article text or a transparent failure."""
    url = validate_article_url(url)
    payload, final_url, _mime = (downloader or _default_download)(url)
    final_url = validate_article_url(final_url)
    if len(payload) > MAX_ARTICLE_BYTES:
        raise ArticleAccessError("The article exceeds the safe extraction limit.")
    try:
        raw = (extractor or _default_extract)(payload, final_url)
    except ArticleAccessError:
        raise
    except Exception as exc:
        raise ArticleAccessError("The article could not be extracted; open it in your browser.") from exc
    raw = re.sub(r"\s+", " ", str(raw or "")).strip()[:MAX_ARTICLE_CHARS]
    if len(raw) < 100:
        raise ArticleAccessError("No substantial article body was extracted; this publisher may block automated reading.")
    return {"url": final_url, "domain": urllib.parse.urlsplit(final_url).hostname, "text": raw}


def _words(text: str) -> list[str]:
    text = (text or "").lower().replace("’", "'")
    return re.findall(r"\b[a-z0-9]+\b", text)


def _content(text: str) -> set[str]:
    return {w for w in _words(text) if len(w) > 2 and w not in STOP and w not in NEGATIONS}


def _negated(text: str) -> bool:
    normalized = re.sub(r"[’']", "", (text or "").lower())
    return bool(set(_words(normalized)) & NEGATIONS)


def _excerpt(sentence: str) -> str:
    words = sentence.split()
    return " ".join(words[:MAX_EXCERPT_WORDS]) + ("…" if len(words) > MAX_EXCERPT_WORDS else "")


def _sentences(text: str) -> list[str]:
    # Split on sentence-ending punctuation only; preserve figures with commas and decimals.
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])", text)
    if len(pieces) < 2:
        pieces = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in pieces if len(p.strip()) > 24][:250]


def _rank(claim: str, sentence: str) -> float:
    c = _content(claim)
    s = _content(sentence)
    if not c or not s:
        return 0.0
    overlap = len(c & s) / len(c)
    return round(overlap, 4)


def compare_article_evidence(claim: str, articles: list[dict]) -> dict:
    """Conservative passage matching, *not* an entailment model or final verdict.

    Supported/Contradicted only for nearly complete matching propositions;
    qualifiers, quotations and uncertain situations yield Insufficient Evidence.
    """
    claim = re.sub(r"\s+", " ", claim or "").strip()[:MAX_CLAIM_CHARS]
    if len(_content(claim)) < 3:
        return {"status": "Insufficient Evidence", "reason": "Enter a specific, detailed claim.", "citations": [], "requires_review": True}
    candidates = []
    for article in articles[:5]:
        url = validate_article_url(article["url"])
        for sentence in _sentences(article.get("text", "")):
            relevance = _rank(claim, sentence)
            if relevance < 0.42:
                continue
            lower = sentence.casefold()
            claim_numbers = set(re.findall(r"\b\d[\d,.]*\b", claim))
            text_numbers = set(re.findall(r"\b\d[\d,.]*\b", sentence))
            contradictory_polarity = (_negated(claim) != _negated(sentence))
            hedge = set(_words(sentence)) & (UNCERTAINTY | QUOTE_CONTEXT)
            near_exact = relevance >= 0.88 and (not claim_numbers or claim_numbers <= text_numbers)
            contradiction = (
                relevance >= 0.88 and contradictory_polarity
                and (not claim_numbers or claim_numbers <= text_numbers)
            )
            classification = "Insufficient Evidence"
            if contradiction and not hedge:
                classification = "Contradicted"
            elif near_exact and not contradictory_polarity and not hedge:
                classification = "Supported"
            candidates.append({
                "url": url, "domain": article.get("domain") or urllib.parse.urlsplit(url).hostname,
                "excerpt": _excerpt(sentence),
                "relevance": relevance, "signal": classification,
                "numbers_differ": bool(claim_numbers and text_numbers and claim_numbers != text_numbers),
            })
    candidates.sort(key=lambda x: x["relevance"], reverse=True)
    # Avoid inventing certainty from mixed or conflicting reporting.
    top = candidates[:5]
    strong = [x for x in top if x["relevance"] >= 0.88]
    statuses = {x["signal"] for x in strong if x["signal"] != "Insufficient Evidence"}
    if len(statuses) == 1 and strong:
        status = next(iter(statuses))
        reason = "Preliminary close-match passage; verify chronology, context, attribution and whether it is quoted as a rumour."
    else:
        status = "Insufficient Evidence"
        reason = "No unambiguous matching passage, or sources conflict. A matching headline or quotation is not verification."
    return {"status": status, "reason": reason, "citations": top, "requires_review": True}


def evidence_report(claim: str, articles: list[dict], result: dict, notes: str, decision: str = "Pending") -> str:
    from datetime import datetime, timezone
    parts = [
        "# RUMOURPRINT AI — Source comparison report",
        f"Prepared: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "Automated assessment: PRELIMINARY ONLY — human review required",
        f"Claim: {claim.strip()[:2500]}",
        f"Preliminary assessment: {result['status']}",
        f"Review state: {decision}",
        f"Method: {result['reason']}",
        "", "## Exact passages and source URLs",
    ]
    if not result["citations"]:
        parts.append("No usable cited passages extracted.")
    for i, cite in enumerate(result["citations"], 1):
        parts.extend([
            f"[{i}] {cite['domain']}",
            f"URL: {cite['url']}",
            f"Exact extract (up to {MAX_EXCERPT_WORDS} words): “{cite['excerpt']}”",
            f"Comparison: {cite['signal']} (text-overlap score {cite['relevance']:.2f}; not truth probability)",
        ])
    parts += ["", "## Reviewer notes", notes.strip()[:3000] or "No notes entered.",
              "", "No percentage is a probability that the statement is true. Reopen original sources; check who made each assertion and when."]
    return "\n".join(parts)
