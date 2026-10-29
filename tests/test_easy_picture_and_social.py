"""Picture review is intentionally cautious and never assigns a face identity."""
import io
from PIL import Image
import pytest

from picture_research import (
    human_picture_story, read_words_in_picture,
    reverse_picture_search, PictureResearchError,
)
from social_search import public_x_posts


def make_photo():
    b = io.BytesIO()
    Image.new("RGB", (72, 38), color=(255, 255, 255)).save(b, format="PNG")
    return b.getvalue()


def test_human_wording_does_not_claim_metadata_proves_camera_history():
    meta = {
        "metadata": {"Make": "Canon", "Model": "EOS 6D Mark II",
                     "Software": "Adobe Photoshop 2026"},
        "finding": "Not established", "c2pa_status": "Not detected", "actions": [],
    }
    story = " ".join(human_picture_story(meta))
    assert "Canon EOS 6D Mark II" in story
    assert "Adobe Photoshop" in story
    assert "can be changed" in story
    assert "not proof" in story.lower() or "isn't proof" in story.lower()
    assert "generated using Photoshop" not in story


def test_no_file_information_must_be_inconclusive():
    meta = {"metadata": {}, "finding": "Not established", "c2pa_status": "Not detected"}
    story = " ".join(human_picture_story(meta))
    assert "does not tell us which camera" in story
    assert "does not mean the picture was never edited" in story


def test_ocr_can_return_readable_message_without_external_api():
    class FakeOutput:
        txts = ["UGANDA POLICE FORCE", "issued a statement"]
        scores = [0.99, 0.88]
    class FakeEngine:
        def __call__(self, image):
            assert image.size == (72, 38)
            return FakeOutput()
    out = read_words_in_picture(make_photo(), engine=FakeEngine())
    assert "UGANDA POLICE FORCE" in out["text"]
    assert out["found"] is True
    assert "server" in out["method"]


def test_reverse_matching_requires_explicit_key():
    with pytest.raises(PictureResearchError):
        reverse_picture_search(make_photo(), "")


def test_reverse_matching_only_surfaces_pages_and_not_identity():
    payload = {"responses":[{"webDetection":{
        "pagesWithMatchingImages":[
            {"url":"https://publisher.example.org/photo", "pageTitle":"<b>Original photograph</b>"},
            {"url":"https://publisher.example.org/photo", "pageTitle":"Duplicate"},
            {"url":"http://127.0.0.1/private", "pageTitle":"Blocked"}
        ],
        "bestGuessLabels":[{"label":"press conference"}],
    }}]}
    out = reverse_picture_search(make_photo(), "DEMO-KEY",
        transport=lambda content, key: payload)
    assert len(out["pages"]) == 1
    assert out["pages"][0]["title"] == "Original photograph"
    assert "proof" in out["note"]


def test_reverse_matching_limits_upload_size():
    with pytest.raises(PictureResearchError):
        reverse_picture_search(b"x" * (2_000_001), "DEMO-KEY")


def test_public_x_query_produces_direct_links_to_posts_and_no_face_identity():
    def fake_send(path, params, key):
        assert path == "/2/tweets/search/recent"
        assert params["max_results"] == 20
        assert key == "DEMO"
        return {"includes":{"users":[{"id":"12345","username":"sample","name":"Sample Official"}]},
                "data":[{"id":"1980000000000000000","author_id":"12345",
                         "text":"Police spokesperson announced a press statement.",
                         "created_at":"2026-10-29T09:00:00Z"}]}
    out = public_x_posts("Police spokesperson announced a press statement",
                         token="DEMO", transport=fake_send)
    assert out["posts"][0]["url"]=="https://x.com/sample/status/1980000000000000000"
    assert "not independently verified" in out["posts"][0]["identity"]


def test_no_x_api_key_does_not_fabricate_posts():
    out=public_x_posts("Police spokesperson announced a press statement",token="")
    assert not out["posts"]
    assert "not configured" in out["coverage"]
