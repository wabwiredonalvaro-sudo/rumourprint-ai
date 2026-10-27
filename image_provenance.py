"""Cautious local image provenance review.

No pixel-level AI-percentage claim. C2PA can verify asserted origin/edit history
when signed metadata exists; EXIF is user-editable and never proof of authenticity.
No uploads are sent to third-party detector APIs.
"""
from __future__ import annotations

from hashlib import sha256
import io
import json
import warnings


class ImageReviewError(ValueError):
    pass


MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
SUPPORTED = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
AI_TERMS = (
    "trainedalgorithmicmedia", "compositesynthetic",
    "algorithmicmedia", "c2pa.ai-disclosure", "generativeai",
    "generative ai", "ai-generated", "ai generated",
)


def _extract_actions(manifest: dict) -> list[str]:
    found = []
    for assertion in manifest.get("assertions") or []:
        if not isinstance(assertion, dict):
            continue
        label = str(assertion.get("label", ""))
        data = assertion.get("data") or {}
        if not isinstance(data, dict):
            continue
        if "actions" in label:
            for action in data.get("actions") or []:
                if isinstance(action, dict):
                    # A c2pa.edited action means editing, NOT necessarily generative AI.
                    fragments = [
                        str(action.get("action", "")),
                        str(action.get("digitalSourceType", "")),
                        str(action.get("softwareAgent", ""))[:100],
                    ]
                    found.append(" | ".join(x for x in fragments if x))
        elif "ai-disclosure" in label:
            found.append("AI disclosure asserted in Content Credentials")
    return found[:30]


def analyse_image(content: bytes, filename: str = "") -> dict:
    from PIL import Image, ExifTags, UnidentifiedImageError

    if not content:
        raise ImageReviewError("Upload a JPG, PNG or WEBP image.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ImageReviewError("Image exceeds the 8 MB upload limit.")
    # Pillow enforces its own pixel thresholds; do not disable bomb checks.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as img:
                if img.format not in SUPPORTED:
                    raise ImageReviewError("Supported image formats: JPG, PNG and WEBP.")
                if img.width * img.height > MAX_IMAGE_PIXELS:
                    raise ImageReviewError("Image is too large to examine safely.")
                img.verify()
            with Image.open(io.BytesIO(content)) as img:
                exif = img.getexif()
                metadata = {
                    str(ExifTags.TAGS.get(tag, tag)): str(value)[:250]
                    for tag, value in exif.items()
                    if str(ExifTags.TAGS.get(tag, tag)) in
                       {"Make", "Model", "Software", "DateTime", "DateTimeOriginal", "Artist", "Copyright"}
                }
                for key in ("Software", "Description"):
                    if key in img.info and key not in metadata:
                        metadata[key] = str(img.info[key])[:250]
                size = (img.width, img.height)
                detected_type = img.format
    except ImageReviewError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageReviewError("Image could not be read safely. Please upload a valid photo.") from exc

    result = {
        "filename": (filename or "image")[:100],
        "sha256": sha256(content).hexdigest(),
        "format": detected_type,
        "dimensions": size,
        "metadata": metadata,
        "c2pa_status": "Not detected",
        "issuer": None,
        "actions": [],
        "finding": "Not established",
        "reason": "No independently verified AI origin information is available.",
        "ai_percentage": None,
        "manual_review": True,
    }

    software = str(metadata.get("Software", ""))
    if software:
        result["metadata_note"] = (
            "A software tag is present. It can show an editing workflow, "
            "but it can be changed and does not establish whether AI was used."
        )
    else:
        result["metadata_note"] = "No meaningful editing software field was found. Missing metadata does not establish authenticity."

    try:
        from c2pa import Reader

        with Reader(SUPPORTED[detected_type], io.BytesIO(content)) as reader:
            store = json.loads(reader.json())
            manifests = store.get("manifests") or {}
            active_id = store.get("active_manifest")
            manifest = manifests.get(active_id) or {}
            if manifest:
                state = reader.get_validation_state() or ""
                result["c2pa_status"] = "Found — " + (str(state) or "validation status not supplied")
                result["issuer"] = (manifest.get("signature_info") or {}).get("issuer")
                result["actions"] = _extract_actions(manifest)
                validation = store.get("validation_status") or []
                if validation or any(z in str(state).lower() for z in ("invalid", "error", "rejected")):
                    result["reason"] = "Content Credentials were found but reported validation problems; assertions are not reliable proof."
                    result["finding"] = "C2PA validation issues"
                else:
                    disclosed_ai = any(
                        term in (" ".join(result["actions"])).casefold()
                        for term in AI_TERMS
                    )
                    edited = any(
                        "c2pa.edited" in line.casefold() or "c2pa.opened" in line.casefold()
                        for line in result["actions"]
                    )
                    history = (" ".join(result["actions"])).casefold()
                    if disclosed_ai:
                        if "composite" in history or (edited and "c2pa.created" not in history):
                            result["finding"] = "AI-assisted or composite edit declared"
                        elif "trainedalgorithmicmedia" in history and "c2pa.created" in history:
                            result["finding"] = "AI-generated origin declared"
                        else:
                            result["finding"] = "AI use declared — extent unclear"
                        result["reason"] = (
                            "The active Content Credentials include an AI-related creation or editing declaration. "
                            "This describes declared provenance, not an independent pixel-level detector. "
                            "Check the issuer, validation status and full action history."
                        )
                    elif edited:
                        result["finding"] = "Editing history declared"
                        result["reason"] = (
                            "Content Credentials describe a modification. "
                            "That does not establish AI editing."
                        )
                    else:
                        result["finding"] = "Provenance information found"
                        result["reason"] = (
                            "Content Credentials are present. Their assertions must be reviewed; "
                            "no explicit AI-generation declaration was found."
                        )
    except ImportError:
        result["c2pa_status"] = "Validator unavailable"
        result["reason"] = "C2PA validation library is not available in this deployment."
    except Exception as exc:
        # Errors include ordinary images with no embedded manifest.
        # Never infer synthetic/real from the absence of Content Credentials.
        result["c2pa_status"] = "Not available or unreadable"
        result["reason"] = "No usable validated Content Credentials were retrieved. This is not evidence that the image is real or AI-generated."

    return result


def image_report(data: dict, notes: str = "") -> str:
    return "\n".join([
        "# RUMOURPRINT AI — Image provenance review",
        "Human review required — this is NOT an AI-generation detector",
        f"File: {data['filename']}",
        f"SHA-256: {data['sha256']}",
        f"Format: {data['format']}",
        f"Dimensions: {data['dimensions'][0]} × {data['dimensions'][1]}",
        f"C2PA: {data['c2pa_status']}",
        f"Signer: {data.get('issuer') or 'Not available'}",
        f"Finding: {data['finding']}",
        f"Explanation: {data['reason']}",
        f"Software metadata: {data['metadata'].get('Software', 'Not recorded')}",
        "AI-generated pixel percentage: NOT MEASURABLE",
        "A visually convincing synthetic image can have no metadata; authentic images can be heavily edited.",
        "", "Declared actions:",
        *(("- " + item) for item in data["actions"]),
        "", "Journalist's notes:", (notes or "Not provided")[:2500],
    ])
