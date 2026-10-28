"""Retrieve Google Lens results through SerpApi, with optional cited AI Overview.

Results are external research leads, never a validated fabrication verdict.
No original-source, identity, capture-date or AI-pixel-percentage inference.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import html
import io
import ipaddress
import json
import re
import secrets
from urllib import error, parse, request
import warnings

from image_provenance import MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES, SUPPORTED

API_BASE = "https://serpapi.com"
MAX_RESPONSE_BYTES = 2_000_000
MAX_SEARCH_BYTES = 480_000  # Provider limit is 500 KB; leave room for interpretation.
TIMEOUT = 20


class ImageSearchError(ValueError):
    """Safe public error: never include provider responses, credentials or URLs."""


def prepare_search_image(content: bytes) -> dict:
    """Validate, orient and strip metadata from a bounded search derivative."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise ImageSearchError("Choose a JPG, PNG or WebP image up to 8 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as original:
                if original.format not in SUPPORTED or original.width * original.height > MAX_IMAGE_PIXELS:
                    raise ImageSearchError("Choose a supported image smaller than 24 million pixels.")
                original.verify()
            with Image.open(io.BytesIO(content)) as original:
                oriented = ImageOps.exif_transpose(original).convert("RGBA")
                oriented.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                clean = Image.new("RGB", oriented.size, "white")
                clean.paste(oriented, mask=oriented.getchannel("A"))
            out = io.BytesIO()
            clean.save(out, format="PNG", optimize=True)
            data, mime = out.getvalue(), "image/png"
            if len(data) > MAX_SEARCH_BYTES:
                for edge in (1600, 1200, 900, 640):
                    clean.thumbnail((edge, edge), Image.Resampling.LANCZOS)
                    for quality in (88, 72, 55):
                        out = io.BytesIO()
                        clean.save(out, format="JPEG", quality=quality, optimize=True)
                        data, mime = out.getvalue(), "image/jpeg"
                        if len(data) <= MAX_SEARCH_BYTES:
                            break
                    if len(data) <= MAX_SEARCH_BYTES:
                        break
            if len(data) > MAX_SEARCH_BYTES:
                raise ImageSearchError("Unable to prepare a search copy within the provider's size limit.")
    except ImageSearchError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        raise ImageSearchError("The image could not be read safely. Choose a valid JPG, PNG or WebP.") from None
    return {"content": data, "mime": mime, "dimensions": clean.size,
            "sha256": sha256(content).hexdigest(), "search_sha256": sha256(data).hexdigest()}


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request_json(path: str, params: dict | None = None, body: bytes | None = None,
                  content_type: str = "application/json") -> dict:
    if path not in {"/image", "/search.json"}:
        raise ImageSearchError("Unsupported image-search operation.")
    url = API_BASE + path + ("?" + parse.urlencode(params) if params else "")
    req = request.Request(url, data=body, headers={
        "Accept": "application/json", "Content-Type": content_type,
        "User-Agent": "RUMOURPRINT-AI image research",
    })
    try:
        with request.build_opener(_NoRedirect).open(req, timeout=TIMEOUT) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ImageSearchError("The image-search response exceeded the size limit.")
        payload = json.loads(raw)
        if not isinstance(payload, dict) or payload.get("error"):
            raise ImageSearchError("The provider could not complete this image-search request. Check its dashboard and quota.")
        metadata = payload.get("search_metadata") or {}
        if (not isinstance(metadata, dict)
                or (path == "/search.json" and metadata.get("status") != "Success")):
            raise ImageSearchError("The image-search provider did not return a completed result.")
        return payload
    except error.HTTPError as exc:
        message = {
            401: "The image-search key was rejected. Ask the administrator to check it.",
            403: "The image-search provider refused this request. Check account access.",
            429: "The image-search quota or rate limit was reached. Try later.",
        }.get(exc.code, "The image-search provider is unavailable. Try later.")
        raise ImageSearchError(message) from None
    except (error.URLError, TimeoutError, OSError, ValueError) as exc:
        if isinstance(exc, ImageSearchError):
            raise
        raise ImageSearchError("Image search could not finish. Check the connection and try later.") from None


def _upload_image(prepared: dict, api_key: str) -> str:
    boundary = "rp_" + secrets.token_hex(16)
    extension = "png" if prepared["mime"] == "image/png" else "jpg"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"api_key\"\r\n\r\n{api_key}\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"search.{extension}\"\r\n"
        f"Content-Type: {prepared['mime']}\r\n\r\n"
    ).encode() + prepared["content"] + f"\r\n--{boundary}--\r\n".encode()
    result = _request_json("/image", body=body, content_type="multipart/form-data; boundary=" + boundary)
    image_id = result.get("image_id")
    if not isinstance(image_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,1024}", image_id):
        raise ImageSearchError("The provider did not return a usable upload identifier.")
    return image_id


def public_link(value: object) -> str:
    """Validate returned links for display only; never fetch source-page URLs."""
    if not isinstance(value, str) or len(value) > 8000 or any(c.isspace() for c in value):
        return ""
    try:
        url = parse.urlsplit(value)
        host = (url.hostname or "").lower().rstrip(".")
        if (url.scheme != "https" or not host or url.username or url.password
                or url.port not in (None, 443) or "." not in host
                or host.endswith((".local", ".internal", ".localhost"))):
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            if not re.fullmatch(r"[a-z0-9.-]+", host):
                return ""
        return value
    except ValueError:
        return ""


def _text(value: object, limit: int = 1200) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", str(value or "")))[:limit]


def _matches(payload: dict, field: str) -> list[dict]:
    rows, seen = [], set()
    values = payload.get(field, [])
    if not isinstance(values, list):
        raise ImageSearchError("The image-search response format was not recognised.")
    for item in values[:100]:
        if not isinstance(item, dict):
            continue
        link = public_link(item.get("link"))
        if not link or link in seen:
            continue
        seen.add(link)
        thumb = public_link(item.get("thumbnail"))
        host = parse.urlsplit(thumb).hostname or ""
        # Thumbnail requests use only the provider or Google's image proxy.
        if not (host == "serpapi.com" or re.fullmatch(r"encrypted-tbn\d*\.gstatic\.com", host)):
            thumb = ""
        rows.append({"url": link, "title": _text(item.get("title"), 250),
                     "source": _text(item.get("source"), 120), "thumbnail": thumb,
                     "date_reported": _text(item.get("date"), 100)})
        if len(rows) == 12:
            break
    return rows


def _overview(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {"blocks": [], "references": []}
    references = []
    raw_refs = payload.get("references") or []
    for item in raw_refs[:30] if isinstance(raw_refs, list) else []:
        if not isinstance(item, dict) or not public_link(item.get("link")):
            continue
        index = item.get("index")
        if type(index) is not int or not 0 <= index < 100:
            continue
        references.append({"index": index, "url": public_link(item["link"]),
                           "title": _text(item.get("title"), 250), "source": _text(item.get("source"), 120)})
    allowed = {r["index"] for r in references}
    blocks = []

    def collect(nodes, inherited=(), depth=0):
        if depth > 5 or not isinstance(nodes, list):
            return
        for node in nodes[:30]:
            if not isinstance(node, dict) or len(blocks) >= 20:
                continue
            indexes = node.get("reference_indexes", inherited)
            indexes = [i for i in indexes if type(i) is int and i in allowed] if isinstance(indexes, (list, tuple)) else []
            snippet = _text(node.get("snippet"), 2000)
            if snippet:
                title = _text(node.get("title"), 150)
                blocks.append({"text": (title + ": " if title else "") + snippet, "reference_indexes": indexes})
            collect(node.get("text_blocks"), indexes, depth + 1)
            collect(node.get("list"), indexes, depth + 1)

    collect(payload.get("text_blocks"))
    return {"blocks": blocks, "references": references}


def search_image(content: bytes, api_key: str, query: str = "", include_overview: bool = True) -> dict:
    """One upload, one Lens search, at most one overview and one exact search.

    Fetch a returned overview token immediately (it expires after one minute).
    Never follow arbitrary provider-returned API URLs or export raw responses.
    """
    api_key = str(api_key or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,200}", api_key):
        raise ImageSearchError("Image search needs an administrator-configured SerpApi key.")
    query = str(query or "").strip()
    if len(query) > 500:
        raise ImageSearchError("Additional search words must be 500 characters or fewer.")
    prepared = prepare_search_image(content)
    image_id = _upload_image(prepared, api_key)
    base = {"engine": "google_lens", "image_id": image_id, "api_key": api_key,
            "hl": "en", "auto_crop": "false", "safe": "active"}
    all_results = _request_json("/search.json", {**base, "type": "all", **({"q": query} if query else {})})
    overview_payload = all_results.get("ai_overview") or {}
    notices = []
    overview_status = "Not requested"
    overview = {"blocks": [], "references": []}
    if include_overview:
        overview = _overview(overview_payload)
        token = overview_payload.get("page_token") if isinstance(overview_payload, dict) else None
        if not overview["blocks"] and isinstance(token, str) and 0 < len(token) <= 24000:
            try:
                overview_response = _request_json("/search.json", {
                    "engine": "google_ai_overview", "page_token": token, "api_key": api_key,
                })
                overview = _overview(overview_response.get("ai_overview"))
            except ImageSearchError:
                notices.append("The AI Overview could not be retrieved; other search results are shown below.")
        overview_status = "Retrieved" if overview["blocks"] else "Unavailable"
    exact, exact_status = [], "Completed"
    try:
        exact_result = _request_json("/search.json", {**base, "type": "exact_matches"})
        exact = _matches(exact_result, "exact_matches")
    except ImageSearchError:
        exact_status = "Unavailable"
        notices.append("The exact-match lookup could not finish; do not interpret this as no matches.")
    visual = _matches(all_results, "visual_matches")
    return {"sha256": prepared["sha256"], "search_sha256": prepared["search_sha256"],
            "search_dimensions": prepared["dimensions"], "query": query,
            "provider": "Google Lens results via SerpApi (third-party service)",
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "exact_matches": exact, "exact_status": exact_status, "visual_matches": visual,
            "overview": overview, "overview_status": overview_status, "notices": notices,
            "original_source": "Not established", "authenticity": "Not established",
            "manual_review": True}


def search_summary(result: dict) -> str:
    if result["exact_matches"]:
        return "Google Lens returned candidate exact matches. Inspect the linked pages to check earlier uses and context. Original source and authenticity remain unverified."
    if result["visual_matches"]:
        return "Google Lens returned visually related images. Similar clothing, faces or backgrounds do not establish a shared original or prove manipulation."
    if result["exact_status"] != "Completed":
        return "Image source search is incomplete. Origin and authenticity remain unverified."
    return "No image matches were returned by these lookups. This does not establish that the picture is original, authentic or fabricated."


def image_source_report(result: dict) -> str:
    lines = ["# RUMOURPRINT AI — Image source research", result["provider"],
             "Human editorial review required; no fabrication verdict has been established.",
             "Checked at: " + result["checked_at"], "Original SHA-256: " + result["sha256"],
             "Search-copy SHA-256: " + result["search_sha256"], "Additional search words: " + (result["query"] or "None"),
             "Original source: Not established", "Authenticity: Not established", search_summary(result),
             "", "## Google's AI Overview (external automated assessment)", "Status: " + result["overview_status"]]
    for block in result["overview"]["blocks"]:
        refs = " ".join(f"[{i + 1}]" for i in block["reference_indexes"])
        lines.append(block["text"] + (" " + refs if refs else " [no supporting link returned for this passage]"))
    for ref in result["overview"]["references"]:
        lines.append(f"[{ref['index'] + 1}] {ref['title']} — {ref['url']}")
    for label, key in (("Candidate exact matches", "exact_matches"), ("Visual matches (similarity only)", "visual_matches")):
        lines.extend(["", "## " + label])
        for match in result[key]:
            lines.append(f"- {match['title']} — {match['url']} | Search-reported date (unverified): {match['date_reported'] or 'Not returned'}")
    lines.extend(["", *result["notices"], "Google results and AI Overview availability may differ from a browser search."])
    return "\n".join(lines)
