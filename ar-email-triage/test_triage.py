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


# ---- keyword patterns match whole words, not fragments of other words
import pytest


@pytest.mark.parametrize("subject,body,expected", [
    ("Statement attached", "Please see the attached statement for each account.", "statement_request"),  # 'ach' in attached/each
    ("Quick question", "Can you please confirm our billing address?", "needs_review"),                  # 'lease' in please
    ("Address change", "We are managing a move to a new office.", "needs_review"),                     # 'aging' in managing
    ("Thanks", "We will reach out after the release.", "needs_review"),                                  # 'ach' in reach, 'lease' in release
])
def test_keywords_do_not_match_inside_other_words(subject, body, expected):
    assert classify(e(subject, body))[0] == expected


@pytest.mark.parametrize("subject,body,expected", [
    ("Payment", "Paid by ACH today.", "remittance"),
    ("Lease buyout", "What is the lease payoff?", "financing_question"),
    ("Aging report", "Please send the AR aging.", "statement_request"),
    ("Financing", "Do you offer financing?", "financing_question"),
    ("Overcharged", "We were overcharged on the last order.", "payment_dispute"),
])
def test_whole_word_keywords_still_match(subject, body, expected):
    assert classify(e(subject, body))[0] == expected


# ---- word boundaries must not cut off plural, -ed, -ing and -ment endings
@pytest.mark.parametrize("subject,body,expected", [
    ("Short payment on INV-204511", "", "payment_dispute"),
    ("Invoice INV-204511", "This invoice was short paid.", "payment_dispute"),
    ("Invoice INV-204511", "We short pay invoices that are wrong.", "payment_dispute"),
    ("Invoice INV-204511", "Customer short pays every month.", "payment_dispute"),
    ("Invoice INV-204511", "They keep short paying us.", "payment_dispute"),
    ("Order 5521", "There are short payments on three orders.", "payment_dispute"),
    ("Order 5521", "These are incorrect amounts.", "payment_dispute"),
    ("Order 5521", "We received incorrect invoices again.", "payment_dispute"),
    ("Order 5521", "You billed wrong prices on two lines.", "payment_dispute"),
    ("Order 5521", "The wrong pricing was applied.", "payment_dispute"),
    ("Account 88", "We have received final notices from your team.", "collections_reply"),
    ("Remittances", "Two remittances for last week.", "remittance"),
    ("Payment confirmations", "Payment confirmations for May.", "remittance"),
    ("Wire confirmations", "Wire confirmations for both orders.", "remittance"),
    ("Credit memos", "Please send the credit memos.", "credit_request"),
    ("Credit notes", "Credit notes for the returned order.", "credit_request"),
    ("Credit requests", "Two credit requests below.", "credit_request"),
    ("Order 5521", "Has this been refunded yet?", "credit_request"),
    ("Order 5521", "Are you refunding the shipping charge?", "credit_request"),
    ("Vendor forms", "Attaching our vendor forms.", "w9_vendor_setup"),
    ("Account balances", "Please confirm account balances for both sites.", "statement_request"),
    ("Device", "We leased the device last year.", "financing_question"),
])
def test_keyword_endings_still_match(subject, body, expected):
    assert classify(e(subject, body))[0] == expected
