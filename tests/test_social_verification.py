"""Offline coverage of original-X-account statement checking (no real API calls)."""
import pytest

from social_verification import (
    SocialLookupError,
    clean_handle,
    compare_post_wording,
    make_x_api_query,
    make_x_search_url,
    parse_x_post_url,
    search_account_posts,
    social_evidence_brief,
    verify_post_link,
)


PROFILE = {"data": {
    "id": "1234567890", "name": "Test Public Official",
    "username": "public_official", "verified": True, "protected": False,
}}
PUBLIC_POST = {
    "id": "1977777777777777777", "author_id": "1234567890",
    "text": "The national assembly postponed its session until next Wednesday.",
    "created_at": "2026-10-27T11:00:00.000Z",
}
OTHER_POST = {
    "id": "1978888888888888888", "author_id": "9999999999",
    "text": "The national assembly postponed its session until next Wednesday.",
    "created_at": "2026-10-27T11:01:00.000Z",
}
CLAIM = "The national assembly postponed its session until next Wednesday."


def fake_transport(path, params, token):
    assert token == "DEMO-SECRET"
    if path.startswith("/2/users/by/username/"):
        return PROFILE
    if path.endswith("/search/recent") or path.endswith("/search/all"):
        assert params["max_results"] == 10
        assert params["query"].startswith("from:public_official ")
        assert "from:other_user" not in params["query"]
        return {"data": [PUBLIC_POST, OTHER_POST]}
    if path.endswith("/1977777777777777777"):
        return {"data": PUBLIC_POST}
    if path.endswith("/1978888888888888888"):
        return {"data": OTHER_POST}
    raise AssertionError("Unexpected mocked X API path: " + path)


def test_search_returns_only_posts_with_matched_x_author_id():
    result = search_account_posts(
        "@public_official", CLAIM, "DEMO-SECRET", transport=fake_transport
    )
    assert result["account"]["id"] == "1234567890"
    assert len(result["posts"]) == 1
    assert result["posts"][0]["id"] == PUBLIC_POST["id"]
    assert result["posts"][0]["url"] == "https://x.com/public_official/status/1977777777777777777"
    assert result["account"]["identity_status"] == "Not independently verified"
    assert result["account"]["premium_badge"] is True
    assert result["posts"][0]["comparison"]["label"] == "Matching wording on account"


def test_full_archive_is_explicit_and_bounded():
    def transport(path, params, token):
        assert path != "/2/tweets/search/recent"
        return fake_transport(path, params, token)
    r = search_account_posts("public_official", CLAIM, "DEMO-SECRET",
                             archive=True, transport=transport)
    assert r["mode"] == "Full archive"
    assert "not an exhaustive" in r["coverage"]


def test_direct_post_author_id_matches_looked_up_account_id():
    url = "https://x.com/public_official/status/1977777777777777777?s=20"
    result = verify_post_link(
        "public_official", url, CLAIM, "DEMO-SECRET", transport=fake_transport
    )
    assert result["owner_matches"] is True
    assert result["post"]["text"] == PUBLIC_POST["text"]
    assert "identity" in result["finding"].lower()


def test_direct_post_from_different_account_rejected_for_attribution():
    url = "https://x.com/other_person/status/1978888888888888888"
    r = verify_post_link("public_official", url, CLAIM, "DEMO-SECRET",
                         transport=fake_transport)
    assert r["owner_matches"] is False
    assert r["post"] is None
    assert "DIFFERENT" in r["finding"]


def test_empty_search_is_not_false_verdict():
    def empty_transport(path, params, token):
        if path.startswith("/2/users/"):
            return PROFILE
        return {"data": []}
    r = search_account_posts("public_official", CLAIM, "DEMO-SECRET",
                             transport=empty_transport)
    assert not r["posts"]
    assert "No sufficiently matching" in r["finding"]
    assert "not an exhaustive" in r["coverage"]


def test_quoted_or_retweeted_post_is_not_attributed_as_original():
    def retweeted_transport(path, params, token):
        if path.startswith("/2/users/"):
            return PROFILE
        return {"data": [dict(PUBLIC_POST, referenced_tweets=[{
            "type": "retweeted", "id": "1970000000000000000"
        }])]}
    r = search_account_posts("public_official", CLAIM, "DEMO-SECRET",
                             transport=retweeted_transport)
    assert not r["posts"]


def test_search_terms_cannot_override_account_filter_with_x_operators():
    q = make_x_api_query("public_official", "from:other_user OR (until:2020) has:links #news")
    assert q.startswith("from:public_official ")
    assert "from:other_user" not in q
    assert "has:links" not in q
    assert "until:" not in q
    assert " -is:retweet" in q


@pytest.mark.parametrize("invalid", [
    "", "name with spaces", "@@john", "handle-more-than-fifteen", "x.com/user",
    "account:name", "alice OR from:bob", "public.ofcl", "a" * 16,
])
def test_invalid_x_handles_blocked(invalid):
    with pytest.raises(SocialLookupError):
        clean_handle(invalid)


@pytest.mark.parametrize("unsafe", [
    "http://x.com/a/status/1977777777777777777",
    "https://x.com.evil.org/a/status/1977777777777777777",
    "https://example.com/a/status/1977777777777777777",
    "https://user:password@x.com/a/status/1977777777777777777",
    "https://x.com:9999/a/status/1977777777777777777",
    "https://x.com/a/status/not-a-post",
    "https://x.com/a",
])
def test_dangerous_or_invalid_post_urls_rejected(unsafe):
    with pytest.raises(SocialLookupError):
        parse_x_post_url(unsafe)


def test_manual_x_search_uses_exact_account_and_encoded_terms():
    url = make_x_search_url("public_official", CLAIM)
    assert url.startswith("https://x.com/search?")
    assert "from%3Apublic_official" in url
    assert "f=live" in url


def test_provenance_statement_brief_is_explicit_about_review():
    r = search_account_posts("public_official", CLAIM, "DEMO-SECRET",
                             transport=fake_transport)
    brief = social_evidence_brief("public_official", CLAIM, r, notes="Checked official profile.", account_confirmed=False)
    assert "PENDING EDITORIAL REVIEW" in brief
    assert "NOT" in brief or "NO" in brief
    assert r["posts"][0]["url"] in brief
    assert "An X blue/Premium checkmark alone" in brief


def test_social_comparison_reports_text_not_truth():
    match = compare_post_wording(CLAIM, CLAIM)
    assert match["label"] == "Matching wording on account"
    assert match["score"] == 100.0
    assert "Potentially related" in compare_post_wording(
        "The national assembly postponed its session until next Wednesday.",
        "The national assembly has NOT postponed its session until next Wednesday."
    )["label"]
