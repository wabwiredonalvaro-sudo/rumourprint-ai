from engine import shift_signals

def test_contracted_negation():
    assert any("Negation" in s for s in shift_signals("The council didn't approve the request.","The council approved the request."))

def test_never_negation():
    assert any("Negation" in s for s in shift_signals("The exams were never cancelled.", "The exams have been cancelled."))

def test_spelled_number():
    assert any("figures" in s for s in shift_signals("Two hundred students were admitted.","One hundred students were admitted."))

def test_conditional():
    assert any("future claim" in s for s in shift_signals("The council will increase tuition.","The council could increase tuition."))

def test_proposal_law():
    assert any("enacted policy" in s for s in shift_signals("The holiday extension is now law.","A proposal to extend the holiday was discussed."))
