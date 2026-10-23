from engine import compare, group_narratives, shift_signals, wording_similarity


class FakeModel:
    def __init__(self, vectors):
        self.vectors = vectors

    def embed(self, texts):
        for text in texts:
            yield self.vectors[text]


def test_quick_matching_finds_duplicate_and_excludes_unrelated():
    library = [
        {"text": "Makerere University suspended its examinations following a directive.", "source": "Demo"},
        {"text": "Kampala marathon opens registration for runners this Friday.", "source": "Demo"},
    ]
    results = compare(library[0]["text"], library)
    assert results[0]["score"] == 100.0
    assert all("marathon" not in result["item"]["text"] for result in results)


def test_scope_and_denial_shifts_prompt_review():
    result = shift_signals(
        "All universities have NOT been ordered to close nationwide.",
        "Makerere University has been ordered to close.",
    )
    assert any("scope" in item for item in result)
    assert any("Negation" in item for item in result)


def test_semantic_mode_uses_vectors_not_wording():
    query = "Administrators have called off student exams."
    related = "Examinations have been suspended at the university."
    unrelated = "Runners registered for Kampala Marathon."
    model = FakeModel({query: [1.0, 0.0], related: [0.93, 0.1], unrelated: [0.0, 1.0]})
    results = compare(query, [{"text": related, "source": "A"}, {"text": unrelated, "source": "B"}], model)
    assert len(results) == 1
    assert results[0]["method"] == "semantic"
    assert results[0]["item"]["text"] == related
    assert results[0]["score"] >= 90


def test_semantic_clustering_groups_related_claims_only():
    texts = ["Makerere exams postponed", "University tests called off", "Kampala marathon registration"]
    model = FakeModel({texts[0]: [1, 0], texts[1]: [0.92, 0.1], texts[2]: [0, 1]})
    groups = group_narratives([{"text": x, "source": "Demo"} for x in texts], model)
    assert [g["size"] for g in groups] == [2, 1]


def test_empty_library_is_safe():
    assert compare("any message", []) == []
    assert group_narratives([]) == []


def test_wording_similarity_is_bounded():
    assert 0 <= wording_similarity("A B", "C D") <= 1
    assert wording_similarity("A identical sentence", "A identical sentence") == 1
