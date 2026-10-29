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
