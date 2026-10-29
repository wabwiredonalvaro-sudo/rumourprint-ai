"""Community notes are exact-claim-matched and never published before moderation."""
import pytest

from community_reviews import (
    claim_key, approved_reviews, submit_review, ReviewError,
    safe_supabase_url, is_safe_public_link,
)


CLAIM = "Makerere University has changed examinations for November 2026."


def test_equivalent_whitespace_has_same_review_key():
    assert claim_key(CLAIM) == claim_key("  MAKERERE UNIVERSITY  HAS CHANGED EXAMINATIONS FOR NOVEMBER 2026. ")


def test_different_claim_never_inherits_other_review():
    assert claim_key(CLAIM) != claim_key("Makerere University has cancelled all examinations in November 2026.")


def test_review_is_pending_and_reviewer_role_is_self_described():
    received = []
    status = submit_review(
        CLAIM,
        "I visited the university's official page and read the announcement about examination timetables.",
        "Reader",
        "https://news.mak.ac.ug/example",
        "https://demo.supabase.co",
        "DEMO-SECRET",
        sender=received.append,
    )
    assert "moderator" in status.lower()
    assert len(received) == 1
    assert received[0]["status"] == "pending"
    assert received[0]["claim_hash"] == claim_key(CLAIM)
    assert "name" not in received[0]


def test_only_approved_notes_are_given_to_readers():
    def get_mock(key):
        assert key == claim_key(CLAIM)
        return [{"review_text": "I read the official schedule and found the examination date in the notice.",
                 "reviewer_role": "Reader", "created_at": "2026-10-29T00:00:00Z",
                 "source_url": "https://news.mak.ac.ug/example"}]
    found = approved_reviews(CLAIM, "https://demo.supabase.co", "DEMO-SECRET", getter=get_mock)
    assert len(found) == 1
    assert found[0]["source"].startswith("https://")


@pytest.mark.parametrize("bad", [
    "http://my.supabase.co", "https://evil.supabase.co.attacker.net",
    "https://localhost:8443", "https://a.supabase.co/path",
    "https://user:pass@project.supabase.co",
])
def test_supabase_secret_not_sent_to_unapproved_host(bad):
    with pytest.raises(ReviewError):
        safe_supabase_url(bad)


def test_private_or_http_link_cannot_be_recommended():
    assert not is_safe_public_link("http://example.org")
    assert not is_safe_public_link("https://localhost/private")
    assert not is_safe_public_link("javascript:alert(1)")


def test_requires_review_and_user_contribution_not_short_slander():
    with pytest.raises(ReviewError):
        submit_review(CLAIM, "They lied", "Reader", "", "https://demo.supabase.co", "KEY", sender=lambda x: None)


def test_only_defined_role_is_accepted():
    with pytest.raises(ReviewError):
        submit_review(
            CLAIM, "The original documents should be checked against the dates in the source.",
            "Official fact-checker", "", "https://demo.supabase.co", "KEY", sender=lambda x: None
        )
