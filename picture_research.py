"""Public-friendly picture checks: local OCR + provenance, optional reverse-web search.

No face recognition, no invented AI-generated pixel percentages. Searching by
picture requires deliberate consent because Google Vision receives the bytes.
"""
from __future__ import annotations

import base64
import html
from io import BytesIO
import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from evidence import safe_link
from image_provenance import analyse_image, ImageReviewError

VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
MAX_VISION_BYTES = 2_000_000  # quota + base64 request protection
MAX_OCR_CHARS = 2000


class PictureResearchError(ValueError):
    pass


def human_picture_story(info: dict) -> list[str]:
    """Explain what the file *reports* in plain language, without inventing history."""
    metadata = info.get("metadata") or {}
    make = str(metadata.get("Make") or "").strip()
    model = str(metadata.get("Model") or "").strip()
    software = str(metadata.get("Software") or "").strip()
    timestamp = str(metadata.get("DateTimeOriginal") or metadata.get("DateTime") or "").strip()
    result = []
    if make or model:
        device = " ".join(v for v in [make, model] if v)
        result.append("The picture's file information lists " + device[:110] + " as the camera or device. "
                      "File information can be changed, so this isn't proof by itself.")
    else:
        result.append("This copy does not tell us which camera or phone took the picture.")
    if software:
        result.append("The file lists " + software[:110] + " as software used on it. "
                      "That may mean it was edited, saved or exported using that software; "
                      "it does not prove exactly which changes were made.")
    else:
        result.append("No editing software is named in the available file information. "
                      "That does not mean the picture was never edited.")
    if timestamp:
        result.append("A date recorded in this file is " + timestamp[:30] + ". "
                      "The date may have been edited and is not a verified capture time.")
    actions = " ".join(str(x) for x in info.get("actions") or [])
    finding = str(info.get("finding") or "")
    credentials = str(info.get("c2pa_status") or "")
    if "declared" in finding.casefold() and "found" in credentials.casefold():
        if "AI-generated origin" in finding:
            result.append("A digital creation record declares that AI was used to generate this picture. "
                          "Check the record and its signer before relying on it.")
        elif "AI-assisted" in finding:
            result.append("A digital creation record declares that AI helped create or edit this picture. "
                          "It does not say what percentage was changed.")
        elif "Editing history" in finding:
            result.append("A digital creation record says this picture was edited, "
                          "but does not establish that AI was involved.")
    elif "validation issues" in finding.casefold():
        result.append("A digital creation record was present but could not be trusted because validation raised problems.")
    else:
        result.append("We could not confirm how this picture was originally made. "
                      "Missing digital records do not prove it is authentic or AI-generated.")
    return result[:5]


def read_words_in_picture(image_bytes: bytes, *, engine=None) -> dict:
    """OCR on the app server. Does not upload images to an outside provider."""
    if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
        raise PictureResearchError("Choose an image smaller than 8 MB.")
    try:
        from PIL import Image
        with Image.open(BytesIO(image_bytes)) as picture:
            if picture.width * picture.height > 24_000_000:
                raise PictureResearchError("Please use a smaller picture.")
            image = picture.convert("RGB")
        if engine is None:
            from rapidocr import RapidOCR
            engine = RapidOCR()
        output = engine(image)
        fragments = getattr(output, "txts", None) or []
        confidence = list(getattr(output, "scores", None) or [])
        # Short unreliable snippets are excluded, but OCR may still make mistakes.
        text = " ".join(
            " ".join(str(fragment).split())
            for index, fragment in enumerate(fragments)
            if len(str(fragment).strip()) >= 3
            and (not confidence or index >= len(confidence) or float(confidence[index]) >= 0.42)
        )[:MAX_OCR_CHARS].strip()
        return {"text": text, "found": bool(text), "method": "Read on this app's server",
                "note": "Computer-read text can contain mistakes, especially in screenshots, Luganda or blurry pictures."}
    except PictureResearchError:
        raise
    except ImportError as exc:
        raise PictureResearchError("Picture text reading is unavailable in this installation.") from exc
    except Exception as exc:
        raise PictureResearchError("Could not read words from this picture. Try a sharper screenshot.") from exc


def _extract_matching(response: dict) -> dict:
    annotation = (response.get("responses") or [{}])[0]
    error = annotation.get("error")
    if error:
        raise PictureResearchError("The picture matching service declined this request.")
    web = annotation.get("webDetection") or {}
    results, seen = [], set()
    for item in web.get("pagesWithMatchingImages") or []:
        url = safe_link(item.get("url"))
        if not url or url.casefold() in seen:
            continue
        seen.add(url.casefold())
        results.append({
            "url": url,
            "title": html.unescape(re.sub(r"<[^>]+>", "", str(item.get("pageTitle") or "")))[:160]
                     or (urlsplit(url).hostname or "Web page"),
            "type": "A web page where Google found a matching or similar image",
        })
        if len(results) >= 15:
            break
    best_guesses = [
        str(x.get("label") or "")[:90]
        for x in web.get("bestGuessLabels") or []
        if str(x.get("label") or "").strip()
    ][:4]
    # This is not a face identification operation; never assert identities.
    return {
        "pages": results,
        "hints": best_guesses,
        "note": ("These are possible picture matches or related pages, not proof of the "
                 "original photographer, first upload, person pictured or whether it was altered."),
    }


def reverse_picture_search(image_bytes: bytes, key: str, *, transport=None) -> dict:
    """Google Vision WEB_DETECTION; bytes sent to Google only after user opts in."""
    if not key:
        raise PictureResearchError("Matching picture search isn't enabled yet by the app administrator.")
    if not image_bytes or len(image_bytes) > MAX_VISION_BYTES:
        raise PictureResearchError("For online picture matching, choose a JPG or PNG smaller than 2 MB.")
    if transport:
        return _extract_matching(transport(image_bytes, key))
    body = json.dumps({
        "requests": [{
            "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
            "features": [{"type": "WEB_DETECTION", "maxResults": 15}],
        }]
    }).encode("utf-8")
    req = urllib.request.Request(
        VISION_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/json", "X-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=13) as resp:
            raw = resp.read(1_200_001)
            if len(raw) > 1_200_000:
                raise PictureResearchError("The matching-picture service returned too much data.")
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise PictureResearchError("The matching-picture service returned unexpected data.")
            return _extract_matching(parsed)
    except urllib.error.HTTPError as exc:
        # Never expose a credential or an untrusted raw provider error to visitors.
        if exc.code in (400, 401, 403):
            raise PictureResearchError("Online picture matching is not authorised for this app. Contact the administrator.") from exc
        if exc.code == 429:
            raise PictureResearchError("Online picture matching has reached its usage limit.") from exc
        raise PictureResearchError(f"Online picture matching is unavailable (HTTP {exc.code}).") from exc
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        raise PictureResearchError("Could not contact the online picture matching service.") from exc
