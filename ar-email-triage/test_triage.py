from triage import Email, Tracker, classify, extract


def e(subject, body="", sender="ap@clinic.com", conv=""):
    return Email("m", sender, subject, body, conv)


def test_classifies_disputes_as_high_priority():
    assert classify(e("Invoice INV-204511 incorrect amount")) == ("payment_dispute", "AR Specialist", "High")


def test_unknown_goes_to_director_review():
    assert classify(e("hello", "quick note"))[0] == "needs_review"


def test_extracts_invoices_and_amounts():
    inv, amt = extract(e("Remittance for Invoice #204511", "Paid $12,450.00 by ACH, also INV-204512"))
    assert inv == ["204511", "204512"] and amt == [12450.0]


def test_reply_on_same_thread_updates_one_case():
    t = Tracker()
    c1 = t.ingest(e("Statement request", conv="T1"))
    c2 = t.ingest(e("RE: Statement request - this is now past due?", conv="T1"))
    assert c1.case_id == c2.case_id and len(t.cases) == 1
    assert c2.priority == "High"  # escalated by the reply


def test_same_invoice_from_new_thread_links_to_existing_case():
    t = Tracker()
    t.ingest(e("Dispute on INV-300100", conv="A"))
    t.ingest(e("Following up INV-300100", conv="B"))
    assert len(t.cases) == 1
