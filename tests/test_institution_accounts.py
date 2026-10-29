"""Account hints must come from sourced institutional records and never assert identity."""
from institution_accounts import suggested_institution_accounts


def test_named_police_source_is_related_to_claim():
    hints = suggested_institution_accounts(
        "The Uganda Police Force announced changes to road traffic enforcement."
    )
    assert [item["handle"] for item in hints] == ["PoliceUg"]
    assert hints[0]["x_search"].startswith("https://x.com/search?")
    assert hints[0]["source"].startswith("https://")
    assert "confirm ownership independently" in hints[0]["warning"]


def test_genuine_institution_reference_for_bou_makerere_parliament():
    hints = suggested_institution_accounts(
        "The Bank of Uganda and Makerere University briefed Parliament of Uganda on the new report."
    )
    assert {"BOU_Official", "Makerere", "Parliament_Ug"} == {x["handle"] for x in hints}
    assert all(x["source"] for x in hints)


def test_no_person_face_or_arbitrary_identity_from_unrelated_claim():
    assert suggested_institution_accounts(
        "A singer reportedly spoke about the football final on stage."
    ) == []


def test_public_figure_mentioned_in_claim_suggests_source_linked_account():
    hints = suggested_institution_accounts(
        "General Muhoozi Kainerugaba announced new defence instructions."
    )
    assert len(hints) == 1
    assert hints[0]["handle"] == "mkainerugaba"
    assert "africacheck.org" in hints[0]["source"]
    assert "confirm ownership independently" in hints[0]["warning"]
