"""Moderated, consent-based reader notes about a public claim.

Server-side optional Supabase backend. No real names or claim text stored
by default; exact normalised claim hashes are used to avoid transferring a
review to a different claim. Nothing appears to other readers until approved
by a newsroom moderator in Supabase's Table Editor.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

MAX_REVIEW_CHARS = 700
MIN_REVIEW_CHARS = 35
ROLES = ("Reader", "Journalist (self-described)")
STATUS = "approved"


class ReviewError(ValueError):
    pass


def claim_key(text: str) -> str:
    normalised = " ".join(str(text or "").casefold().split())
    if len(normalised) < 10:
        raise ReviewError("Enter a full claim before reviewing it.")
    return hashlib.sha256(normalised[:2500].encode("utf-8")).hexdigest()


def safe_supabase_url(url: str) -> str:
    """Keep service-role credentials scoped to official project hosts only."""
    try:
        parts = urllib.parse.urlsplit(str(url or "").strip())
        host = (parts.hostname or "").lower()
        if (parts.scheme != "https" or parts.username or parts.password
            or parts.port not in (None, 443)
            or not re.fullmatch(r"[a-z0-9-]+[.]supabase[.]co", host)):
            raise ReviewError("The approved database project URL is not configured correctly.")
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise ReviewError("Use the project's root Supabase URL.")
    except ValueError as exc:
        raise ReviewError("The approved database URL is invalid.") from exc
    return "https://" + host


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReviewError("The review database returned an unexpected redirect.")


def _request(url: str, api_key: str, *, method: str, body: dict | None = None) -> object:
    if not api_key or "\n" in api_key or "\r" in api_key:
        raise ReviewError("Secure community review storage is not enabled.")
    endpoint = safe_supabase_url(url) + "/rest/v1/rumourprint_reviews"
    if method == "GET":
        raise ReviewError("A review search query is required.")
    request = urllib.request.Request(
        endpoint,
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "apikey": api_key,
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    return _read(request)


def _read(req: urllib.request.Request) -> object:
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=9) as resp:
            content = resp.read(60_001)
            if len(content) > 60_000:
                raise ReviewError("The review service returned too much data.")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as exc:
        raise ReviewError("The reviews service could not complete this request. Please try later.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ReviewError("Could not reach community reviews at the moment.") from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ReviewError("The reviews service returned an unreadable response.") from exc


def approved_reviews(claim: str, url: str, api_key: str, *, getter=None) -> list[dict]:
    """Fetch moderator-approved notes for the exact claim wording only."""
    key = claim_key(claim)
    if getter is None:
        base = safe_supabase_url(url)
        params = urllib.parse.urlencode({
            "select": "review_text,reviewer_role,created_at,source_url",
            "claim_hash": "eq." + key,
            "status": "eq.approved",
            "order": "created_at.desc",
            "limit": "6",
        })
        req = urllib.request.Request(
            base + "/rest/v1/rumourprint_reviews?" + params,
            headers={"apikey": api_key, "Authorization": "Bearer " + api_key},
        )
        if not api_key:
            raise ReviewError("Secure review storage has not been enabled.")
        data = _read(req)
    else:
        data = getter(key)
    if not isinstance(data, list):
        raise ReviewError("The reviews service returned invalid data.")
    items = []
    for entry in data[:6]:
        if not isinstance(entry, dict):
            continue
        role = entry.get("reviewer_role") or "Reader"
        if role not in ROLES:
            role = "Reader"
        source = str(entry.get("source_url") or "").strip()
        items.append({
            "text": str(entry.get("review_text") or "")[:MAX_REVIEW_CHARS],
            "role": role,
            "date": str(entry.get("created_at") or "")[:10],
            "source": source if is_safe_public_link(source) else "",
        })
    return [x for x in items if x["text"]]


def is_safe_public_link(url: str) -> bool:
    if not url:
        return False
    try:
        parts = urllib.parse.urlsplit(url)
        host = (parts.hostname or "").casefold()
        return (parts.scheme == "https" and bool(host)
                and not parts.username and not parts.password
                and parts.port in (None, 443)
                and not host.endswith((".local", ".internal", ".test"))
                and host not in ("localhost", "127.0.0.1", "::1"))
    except ValueError:
        return False


def submit_review(
    claim: str, text: str, role: str, source_url: str,
    url: str, api_key: str, *, sender=None,
) -> str:
    """Submissions are pending and never visible to other readers automatically."""
    key = claim_key(claim)
    note = " ".join(str(text or "").split())
    if not MIN_REVIEW_CHARS <= len(note) <= MAX_REVIEW_CHARS:
        raise ReviewError(f"Your review should be between {MIN_REVIEW_CHARS} and {MAX_REVIEW_CHARS} characters.")
    if role not in ROLES:
        raise ReviewError("Choose a listed review type.")
    source = str(source_url or "").strip()
    if source and (len(source) > 1500 or not is_safe_public_link(source)):
        raise ReviewError("Enter a valid public HTTPS link, or leave that field empty.")
    if re.search(r"(?i)\b(?:password|secret key|api[_ -]?key)\s*[:=]", note):
        raise ReviewError("Remove passwords, access keys and other private credentials.")
    payload = {
        "claim_hash": key,
        "review_text": note,
        "reviewer_role": role,
        "origin": "RUMOURPRINT",
        "source_url": source or None,
        "status": "pending",
    }
    if sender is None:
        _request(url, api_key, method="POST", body=payload)
    else:
        sender(payload)
    return "Sent for FEM moderator review. It will only appear to others if approved."
