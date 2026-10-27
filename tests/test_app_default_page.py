"""Smoke-test the public-facing Evidence Desk as the first app screen."""
from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_evidence_desk_is_initial_app_page():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    app.run()
    assert not app.exception, [str(err.message) for err in app.exception]
    assert app.radio(key="workspace_page").value == "Evidence desk"


def test_evidence_search_terms_are_generated_from_claim_and_remain_editable():
    """The journalist only needs to paste a claim; manual changes still work."""
    from evidence import suggest_query

    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    app.run()
    assert not app.exception, [str(err.message) for err in app.exception]

    claim = "Makerere University suspended all examinations following a government directive."
    app.text_area(key="verification_claim").set_value(claim).run()
    assert not app.exception, [str(err.message) for err in app.exception]
    assert app.text_input(key="verification_query").value == suggest_query(claim)

    custom_terms = "Makerere examinations official statement"
    app.text_input(key="verification_query").set_value(custom_terms).run()
    assert app.text_input(key="verification_query").value == custom_terms

    app.run()
    assert app.text_input(key="verification_query").value == custom_terms

    new_claim = "Bank of Uganda announces revised central bank rate for 2026."
    app.text_area(key="verification_claim").set_value(new_claim).run()
    assert not app.exception, [str(err.message) for err in app.exception]
    assert app.text_input(key="verification_query").value == suggest_query(new_claim)
