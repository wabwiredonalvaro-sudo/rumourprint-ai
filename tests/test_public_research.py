"""Offline, provider-independent tests for accessible, bounded public research."""
from urllib.parse import parse_qs, urlsplit

from public_research import (
    automatic_terms, suggest_names, query_variants, investigate_text,
    social_discovery, web_hits, PROVENANCE_OPTIONS,
)
from evidence import search_news


CLAIM = "Uganda Police Force confirms that Makerere University will close tomorrow."


def fake_news(query, *, limit=8, region="UG"):
    return [{
        "type": "news",
        "title": "University spokesperson issues public statement",
        "url": "https://news.example.org/official-statement",
        "publisher": "Example News",
        "date": "2026-10-29",
    }]


def fake_web(query, key, limit=20):
    assert key == "TEST-BRAVE"
    return [
        {"title": "Independent article", "url": "https://example.org/article",
         "publisher": "example.org", "date": "2026-10-29"},
        {"title": "Duplicate article", "url": "https://news.example.org/official-statement",
         "publisher": "Example News", "date": "2026-10-29"},
    ]


def test_automatic_keywords_do_not_need_second_input():
    assert "Uganda" in automatic_terms(CLAIM)
    assert 1 <= len(query_variants(CLAIM)) <= 3
    assert len(set(query_variants(CLAIM))) == len(query_variants(CLAIM))


def test_people_and_organisations_are_only_suggestions():
    names = suggest_names(CLAIM)
    assert "Uganda Police Force" in names
    assert "Makerere University" in names


def test_selected_origins_include_spoken_rumours():
    assert "WhatsApp" in PROVENANCE_OPTIONS
    assert "Spoken rumour" in PROVENANCE_OPTIONS
    assert "X" in PROVENANCE_OPTIONS


def test_multiple_indexed_sources_deduplicate_and_record_coverage():
    out = investigate_text(
        CLAIM,
        brave_key="TEST-BRAVE",
        news_search=fake_news,
        web_search=fake_web,
    )
    urls = [x["url"] for x in out["articles"]]
    assert len(urls) == 2
    assert len(out["queries"]) >= 2
    assert len(out["status"]) >= 3
    assert "cannot be found" in out["scope"]


def test_news_search_still_works_without_paid_provider_key():
    out = investigate_text(CLAIM, news_search=fake_news)
    assert len(out["articles"]) == 1
    assert any("Not enabled" in status["error"] for status in out["status"])


def test_rss_can_use_worldwide_search_parameters():
    feed=b'<rss version="2.0"><channel><item><title>Report</title><link>https://example.org/report</link></item></channel></rss>'
    captured=[]
    def transport(url,params):
        captured.append(params)
        return feed
    assert search_news("Uganda", region="WORLD", transport=transport)
    assert captured[0]["gl"] == "US"


def test_social_discovery_returns_original_post_urls_not_profile_links():
    def social_fake(q, key, limit=20):
        platform = "x.com" if "site:x.com" in q else (
            "facebook.com" if "site:facebook.com" in q else "instagram.com"
        )
        return [
            {"title": "Post", "url": (
                "https://x.com/example/status/1980000000000000000" if platform=="x.com"
                else "https://www.facebook.com/example/posts/123" if platform=="facebook.com"
                else "https://www.instagram.com/p/Abc123/"
            )},
            {"title": "Profile only", "url": "https://x.com/example"}
        ]
    out = social_discovery(CLAIM, brave_key="BRAVE", web_search=social_fake)
    assert len(out["posts"]) == 3
    assert {p["platform"] for p in out["posts"]} == {"X", "Instagram", "Facebook"}
    assert all("original" not in p.get("status", "").lower() for p in out["posts"])
    assert len(out["search_links"]) == 3


def test_no_cross_platform_api_is_not_claimed():
    out = social_discovery(CLAIM, brave_key="")
    assert not out["posts"]
    assert any("not configured" in w for w in out["warnings"])
    assert out["search_links"]["X"].startswith("https://x.com/search?")


def test_brave_search_filters_invalid_links_and_preserves_bounded_results():
    def data(q,key,limit=20):
        return {"web":{"results":[
            {"title": "Publisher page", "url":"https://example.org/report", "description":"Published news report"},
            {"title":"Unsafe", "url":"javascript:alert(1)"},
        ]}}
    out=web_hits("Uganda event","TEST",requester=data)
    assert len(out)==1
    assert out[0]["url"]=="https://example.org/report"
