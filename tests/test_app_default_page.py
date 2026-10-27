"""Smoke-test the public-facing Evidence Desk as the first app screen."""
from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_evidence_desk_is_initial_app_page():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    app.run()
    assert not app.exception, [str(err.message) for err in app.exception]
    assert app.radio(key="workspace_page").value == "Evidence desk"
