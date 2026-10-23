import io
import urllib.error

from evidence import EvidenceError, _get, broaden_query, search_news


def test_broaden_query_shortens_specific_claim():
    q = 'Makerere University suspended all examinations emergency government directive'
    assert broaden_query(q) == 'Makerere University suspended examinations'


def test_news_rss_parse_with_mocked_transport():
    rss = b'''<rss version="2.0"><channel><item><title>Campus bulletin</title><link>https://example.org/campus-news</link><pubDate>Mon, 19 Oct 2026 10:00:00 +0000</pubDate><source>Demo News</source></item></channel></rss>'''
    items = search_news('Makerere exams', transport=lambda url, args: rss)
    assert len(items) == 1
    assert items[0]['title'] == 'Campus bulletin'
    assert items[0]['url'] == 'https://example.org/campus-news'


def test_reject_malformed_rss():
    try:
        search_news('Makerere exams', transport=lambda url, args: b'<notrss/>')
    except EvidenceError as e:
        assert 'RSS' in str(e)
    else:
        raise AssertionError('Should reject invalid feed')
