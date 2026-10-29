"""RUMOURPRINT AI v1: a single plain-language mobile-first journey."""
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1] / "app.py"


def test_homepage_shows_single_investigate_form_and_three_result_tabs():
    app = AppTest.from_file(str(ROOT), default_timeout=30)
    app.run()
    assert not app.exception, [str(err.message) for err in app.exception]
    assert app.text_area(key="public_claim").value == ""
    assert app.radio(key="origin").value == "WhatsApp"
    tabs = [t.label for t in app.tabs]
    assert len(tabs) == 3
    assert tabs == ["📰 News", "💬 Social media search", "🖼️ Image search"]


def test_user_can_enter_message_and_choose_source_without_jargon():
    app = AppTest.from_file(str(ROOT), default_timeout=30)
    app.run()
    claim = "Makerere University exams were cancelled following a government directive."
    app.text_area(key="public_claim").set_value(claim).run()
    app.radio(key="origin").set_value("Spoken rumour").run()
    assert not app.exception, [str(err.message) for err in app.exception]
    assert app.text_area(key="public_claim").value == claim
    assert app.radio(key="origin").value == "Spoken rumour"
    assert app.tabs[0].label == "📰 News"


def test_original_rumourprint_svg_logo_is_restored_in_header():
    """Keep the original October 2026 RUMOURPRINT artwork, not a replacement icon."""
    from pathlib import Path
    source = Path(__file__).resolve().parents[1]
    logo = (source / "assets" / "rumourprint-logo.svg").read_text(encoding="utf-8")
    app = (source / "app.py").read_text(encoding="utf-8")
    assert 'viewBox="0 0 64 64"' in logo
    assert '#D9C28B' in logo and '#7FC0AE' in logo
    assert 'M32 32L45 45' in logo
    assert 'ORIGINAL_LOGO_BASE64' in app
    assert 'alt="Original RUMOURPRINT AI logo"' in app
    assert '<div class="rp-logo-icon">✦' not in app
