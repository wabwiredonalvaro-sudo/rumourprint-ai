"""Exercise the consent/access boundary and rerun behaviour in Streamlit."""
from copy import deepcopy
from hashlib import sha256
import io

from PIL import Image
from streamlit.testing.v1 import AppTest

import image_source_ui as ui
from image_source_search import ImageSearchError


def picture(colour="green"):
    out = io.BytesIO()
    Image.new("RGB", (40, 20), colour).save(out, format="PNG")
    return out.getvalue()


def app_for_image(content):
    app = AppTest.from_string("""
from types import SimpleNamespace
import streamlit as st
from image_source_ui import render_image_source_trace
content = st.session_state.get('test_image')
upload = SimpleNamespace(getvalue=lambda: content) if content else None
render_image_source_trace(upload)
""", default_timeout=20)
    app.session_state["test_image"] = content
    return app.run()


def result_for(content):
    return {
        "sha256": sha256(content).hexdigest(), "search_sha256": "copy-hash", "query": "",
        "provider": "Google Lens results via SerpApi", "checked_at": "2026-10-28T12:00:00+00:00",
        "exact_status": "Completed", "exact_matches": [], "visual_matches": [], "notices": [],
        "overview_status": "Retrieved", "overview": {"blocks": [
            {"text": "Possible composite: check the original evidence.", "reference_indexes": [3]},
        ], "references": [{"index": 3, "title": "Source report", "source": "Example", "url": "https://example.org/report"}]},
    }


def enable_search(app, content):
    app.text_input(key="image_source_access").set_value("newsroom-code").run()
    app.checkbox(key="image_source_consent_" + sha256(content).hexdigest()[:16]).check().run()
    return app


def test_unconfigured_image_search_remains_disabled(monkeypatch):
    monkeypatch.setattr(ui, "_settings", lambda: ("", ""))
    monkeypatch.setattr(ui, "search_image", lambda *args: (_ for _ in ()).throw(AssertionError("Unexpected call")))
    app = app_for_image(picture())
    assert not app.exception
    assert app.button(key="image_source_search").disabled
    assert any("not configured" in item.value for item in app.info)


def test_key_alone_does_not_enable_public_billable_search(monkeypatch):
    monkeypatch.setattr(ui, "_settings", lambda: ("fake-key-12345", ""))
    app = app_for_image(picture())
    assert not app.exception and app.button(key="image_source_search").disabled


def test_access_consent_click_and_reruns_do_not_make_background_searches(monkeypatch):
    content = picture()
    calls = []
    monkeypatch.setattr(ui, "_settings", lambda: ("fake-key-12345", "newsroom-code"))

    def perform(*args):
        calls.append(args)
        return deepcopy(result_for(args[0]))

    monkeypatch.setattr(ui, "search_image", perform)
    app = app_for_image(content)
    assert not calls and app.button(key="image_source_search").disabled
    enable_search(app, content)
    assert not calls and not app.button(key="image_source_search").disabled
    app.button(key="image_source_search").click().run()
    assert not app.exception, [e.message for e in app.exception]
    assert len(calls) == 1 and len(app.info) == 1
    app.run()
    assert len(calls) == 1
    app.text_input(key="image_source_query").set_value("new caption").run()
    assert len(calls) == 1 and not app.info


def test_switching_image_hides_old_results_and_requires_fresh_consent(monkeypatch):
    first, second = picture(), picture("blue")
    monkeypatch.setattr(ui, "_settings", lambda: ("fake-key-12345", "newsroom-code"))
    monkeypatch.setattr(ui, "search_image", lambda *args: result_for(args[0]))
    app = enable_search(app_for_image(first), first)
    app.button(key="image_source_search").click().run()
    assert not app.exception and app.info
    app.session_state["test_image"] = second
    app.run()
    assert not app.exception and not app.info
    assert app.button(key="image_source_search").disabled


def test_failed_new_search_clears_previous_success(monkeypatch):
    content = picture()
    monkeypatch.setattr(ui, "_settings", lambda: ("fake-key-12345", "newsroom-code"))
    monkeypatch.setattr(ui, "COOLDOWN_SECONDS", 0)
    monkeypatch.setattr(ui, "search_image", lambda *args: result_for(args[0]))
    app = enable_search(app_for_image(content), content)
    app.button(key="image_source_search").click().run()
    assert app.info

    def failed(*args):
        raise ImageSearchError("Image search is unavailable.")

    monkeypatch.setattr(ui, "search_image", failed)
    app.button(key="image_source_search").click().run()
    assert not app.exception and app.error
    assert not app.info


def test_session_limit_blocks_more_provider_requests(monkeypatch):
    monkeypatch.setattr(ui, "_settings", lambda: ("fake-key-12345", "newsroom-code"))
    content = picture()
    app = enable_search(app_for_image(content), content)
    app.session_state["image_source_attempts"] = ui.SESSION_LIMIT
    app.run()
    assert not app.exception and app.button(key="image_source_search").disabled
