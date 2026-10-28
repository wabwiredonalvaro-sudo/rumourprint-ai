"""Offline tests for external Lens research; no network or private images."""
from copy import deepcopy
from hashlib import sha256
import io
import json
from urllib import error

from PIL import Image, PngImagePlugin
import pytest

import image_source_search as search


def picture(size=(120, 80), metadata=False):
    out = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text("PrivateSource", "not-for-provider")
    Image.new("RGB", size, "green").save(out, format="PNG", pnginfo=info)
    return out.getvalue()


def complete(**fields):
    return {"search_metadata": {"status": "Success"}, **fields}


OVERVIEW = {
    "text_blocks": [{"type": "list", "reference_indexes": [7], "list": [
        {"snippet": "This appears to be a composite; verify the cited report."},
        {"text_blocks": [{"snippet": "An uncited claim is not proof.", "reference_indexes": [99]}]},
    ]}],
    "references": [
        {"index": 7, "title": "Example fact check", "link": "https://example.org/fact-check", "source": "Example"},
        {"index": 99, "title": "Invalid source", "link": "javascript:alert(1)"},
    ],
}


def install_provider(monkeypatch, *, exact_error=False, overview_error=False):
    calls = []

    def provider(path, params=None, body=None, content_type="application/json"):
        calls.append({"path": path, "params": params, "body": body})
        if path == "/image":
            assert b"not-for-provider" not in body
            return {"image_id": "temporary-image-123"}
        if params["engine"] == "google_ai_overview":
            if overview_error:
                raise search.ImageSearchError("Provider failed")
            return complete(ai_overview=deepcopy(OVERVIEW))
        if params["type"] == "exact_matches":
            if exact_error:
                raise search.ImageSearchError("Provider failed")
            return complete(exact_matches=[
                {"title": "Earlier use", "link": "https://example.org/old-use", "date": "2 years ago"},
            ])
        return complete(
            ai_overview={"page_token": "short-lived-token", "serpapi_link": "https://evil.example/steal-key"},
            visual_matches=[
                {"title": "<b>Similar shirt</b>", "link": "https://example.org/shop", "thumbnail": "https://encrypted-tbn1.gstatic.com/image"},
                {"title": "Duplicate", "link": "https://example.org/shop"},
                {"title": "Unsafe", "link": "https://127.0.0.1/admin"},
            ],
        )

    monkeypatch.setattr(search, "_request_json", provider)
    return calls


def test_search_copy_removes_metadata_and_preserves_original_hash():
    original = picture(metadata=True)
    result = search.prepare_search_image(original)
    assert result["sha256"] == sha256(original).hexdigest()
    assert b"not-for-provider" in original and b"not-for-provider" not in result["content"]
    with Image.open(io.BytesIO(result["content"])) as image:
        assert image.size == (120, 80)
        assert not image.getexif() and not image.info


def test_large_noisy_image_is_bounded_for_provider_upload():
    out = io.BytesIO()
    Image.effect_noise((2100, 1800), 100).convert("RGB").save(out, format="PNG")
    result = search.prepare_search_image(out.getvalue())
    assert len(result["content"]) <= search.MAX_SEARCH_BYTES
    assert max(result["dimensions"]) <= 1600


def test_orientation_is_applied_before_metadata_is_removed():
    image = Image.new("RGB", (40, 20), "blue")
    exif = Image.Exif()
    exif[274] = 6
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    result = search.prepare_search_image(out.getvalue())
    assert result["dimensions"] == (20, 40)


@pytest.mark.parametrize("content", [b"", b"not-an-image", b"%PDF-1.7", b"x" * (8 * 1024 * 1024 + 1)])
def test_invalid_upload_cannot_start_provider_requests(monkeypatch, content):
    calls = install_provider(monkeypatch)
    with pytest.raises(search.ImageSearchError):
        search.search_image(content, "fake-key-12345")
    assert calls == []


def test_search_uses_lens_and_immediate_overview_then_image_only_exact_lookup(monkeypatch):
    calls = install_provider(monkeypatch)
    result = search.search_image(picture(metadata=True), "fake-key-12345", "original photograph")
    assert len(calls) == 4
    assert [call["params"]["engine"] for call in calls[1:]] == ["google_lens", "google_ai_overview", "google_lens"]
    assert calls[1]["params"]["q"] == "original photograph"
    assert "q" not in calls[3]["params"]
    assert calls[3]["params"]["type"] == "exact_matches"
    assert all(call["path"] in {"/image", "/search.json"} for call in calls)
    assert result["overview"]["blocks"][0]["reference_indexes"] == [7]
    assert result["overview"]["blocks"][1]["reference_indexes"] == []
    assert len(result["visual_matches"]) == 1
    assert result["visual_matches"][0]["title"] == "Similar shirt"
    assert result["original_source"] == result["authenticity"] == "Not established"
    report = search.image_source_report(result)
    assert "[8] Example fact check" in report
    assert "[no supporting link returned for this passage]" in report
    assert "2 years ago" in report and "unverified" in report
    assert all(secret not in report for secret in ("fake-key-12345", "temporary-image-123", "short-lived-token", "evil.example"))


def test_no_overview_request_when_user_disables_it(monkeypatch):
    calls = install_provider(monkeypatch)
    result = search.search_image(picture(), "fake-key-12345", include_overview=False)
    assert len(calls) == 3 and result["overview_status"] == "Not requested"
    assert not result["overview"]["blocks"]


def test_unavailable_overview_and_exact_failure_preserve_visual_leads(monkeypatch):
    calls = install_provider(monkeypatch, exact_error=True, overview_error=True)
    result = search.search_image(picture(), "fake-key-12345")
    assert len(calls) == 4
    assert result["exact_status"] == result["overview_status"] == "Unavailable"
    assert len(result["notices"]) == 2 and result["visual_matches"]
    assert "prove manipulation" in search.search_summary(result)


def test_empty_results_are_inconclusive_and_do_not_invent_an_overview(monkeypatch):
    def empty(path, params=None, **kwargs):
        return {"image_id": "temporary-image"} if path == "/image" else complete()

    monkeypatch.setattr(search, "_request_json", empty)
    result = search.search_image(picture(), "fake-key-12345")
    assert result["overview_status"] == "Unavailable"
    assert "does not establish" in search.search_summary(result)
    assert result["manual_review"] is True


def test_links_and_thumbnails_cannot_reference_local_resources_or_other_schemes():
    for link in ("javascript:alert(1)", "https://localhost/x", "https://127.0.0.1/x", "https://10.1.1.1/x", "https://user:pass@example.org/x"):
        assert not search.public_link(link)
    rows = search._matches({"visual_matches": [{"link": "https://example.org/article", "thumbnail": "https://other.example/tracking"}]}, "visual_matches")
    assert len(rows) == 1 and rows[0]["thumbnail"] == ""


def test_transport_redacts_credential_bearing_exception(monkeypatch):
    class Opener:
        def open(self, req, timeout):
            raise error.HTTPError(req.full_url, 401, "secret-fake-key-12345", {}, None)

    monkeypatch.setattr(search.request, "build_opener", lambda *args: Opener())
    with pytest.raises(search.ImageSearchError) as caught:
        search._request_json("/search.json", {"api_key": "secret-fake-key-12345"})
    assert "secret-fake-key" not in str(caught.value)
    assert "rejected" in str(caught.value)
    assert search._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example") is None


@pytest.mark.parametrize("raw", [b"not json", b"[]", b"{}", json.dumps({"error": "secret-fake-key"}).encode(), json.dumps({"search_metadata": {"status": "Processing"}}).encode()])
def test_transport_rejects_incomplete_or_malformed_search_responses(monkeypatch, raw):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return raw

    class Opener:
        def open(self, req, timeout):
            return Response()

    monkeypatch.setattr(search.request, "build_opener", lambda *args: Opener())
    with pytest.raises(search.ImageSearchError) as caught:
        search._request_json("/search.json", {"api_key": "secret-fake-key"})
    assert "secret-fake-key" not in str(caught.value)
