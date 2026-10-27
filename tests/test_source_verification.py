import io

import pytest

from source_verification import (
    ArticleAccessError,
    compare_article_evidence,
    fetch_article,
    validate_article_url,
    evidence_report,
)


def example_article(text: str) -> dict:
    url = "https://news.mak.ac.ug/2026/news-story"
    return {"url": url, "domain": "news.mak.ac.ug", "text": text}


def test_supported_provisional_assessment_has_real_source_quote_and_url():
    claim = "Makerere University suspended final examinations on 12 November 2026."
    article = example_article(
        "Official announcement. Makerere University suspended final examinations on 12 November 2026. "
        "The university will publish a new timetable after consultation with faculty representatives."
    )
    r = compare_article_evidence(claim, [article])
    assert r["status"] == "Supported"
    assert r["requires_review"] is True
    assert r["citations"][0]["url"] == article["url"]
    assert len(r["citations"][0]["excerpt"].split()) <= 24
    assert "PRELIMINARY" in evidence_report(claim, [article], r, "Checked the university source")


def test_contradicted_provisional_for_explicit_denial_same_subject():
    claim = "Makerere University suspended examinations across Kampala."
    article = example_article(
        "The institution published a direct clarification. "
        "Makerere University has not suspended examinations across Kampala. "
        "Students were advised to consult official timetables instead."
    )
    result = compare_article_evidence(claim, [article])
    assert result["status"] == "Contradicted"


def test_reported_rumour_is_not_evidence_of_support():
    claim = "Makerere University suspended final examinations on 12 November 2026."
    article = example_article(
        "An unverified rumour claimed Makerere University suspended final examinations on 12 November 2026. "
        "The university has urged readers to rely on official announcements."
    )
    result = compare_article_evidence(claim, [article])
    assert result["status"] == "Insufficient Evidence"


def test_unrelated_article_cannot_make_true_false_claim():
    claim = "Makerere University suspended final examinations on 12 November 2026."
    article = example_article(
        "The school held an event on Saturday. A drama competition attracted visitors "
        "from several different districts and institutions."
    )
    result = compare_article_evidence(claim, [article])
    assert result["status"] == "Insufficient Evidence"


@pytest.mark.parametrize("url", [
    "http://news.mak.ac.ug/article", "https://127.0.0.1/admin",
    "https://news.mak.ac.ug.evil.net/redirect",
    "https://metadata.google.internal/compute", "https://news.google.com/rss/articles/id",
    "https://news.mak.ac.ug:4443/private",
    "https://user:pass@news.mak.ac.ug/a",
])
def test_rejects_untrusted_or_internal_article_urls(url):
    with pytest.raises(ArticleAccessError):
        validate_article_url(url)


def test_extracts_a_mocked_supported_publisher_article():
    html = b"<html><body><article><p>Makerere University has announced the results.</p></article></body></html>"
    text = ("Makerere University published a statement setting out the graduation dates. " * 3)
    url = "https://news.mak.ac.ug/2026/graduation"
    result = fetch_article(
        url, downloader=lambda src: (html, src, "text/html"),
        extractor=lambda data, source_url: text
    )
    assert result["url"] == url
    assert "graduation" in result["text"]


def test_blocks_publisher_redirect_to_internal_host():
    url = "https://news.mak.ac.ug/2026/graduation"
    with pytest.raises(ArticleAccessError):
        fetch_article(
            url, downloader=lambda src: (b"example" * 100, "http://127.0.0.1", "text/html"),
            extractor=lambda data, source_url: "A" * 200
        )


def test_short_or_paywall_article_does_not_claim_evidence():
    with pytest.raises(ArticleAccessError):
        fetch_article(
            "https://news.mak.ac.ug/a",
            downloader=lambda src: (b"x" * 100, src, "text/html"),
            extractor=lambda data, source_url: "Please subscribe."
        )
