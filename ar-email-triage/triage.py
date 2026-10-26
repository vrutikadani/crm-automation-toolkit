"""AR email triage — reference logic for a Copilot Studio / Power Automate agent.

Production shape: a Power Automate flow fires on each new email in the Finance
Director's mailbox, a Copilot Studio prompt classifies it, and the flow logs or updates a
row in a SharePoint "AR Case & Issue Tracker" list, assigns an owner and emails them.

This file is the same decision logic in plain Python, so it can be tested and reviewed
before anyone touches the low-code flow. Synthetic examples only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

CATEGORIES = {
    # category: (keywords, default owner role, priority). Checked in order: high-priority first.
    "collections_reply": (r"past due|overdue|final notice|collections", "Collections", "High"),
    "payment_dispute": (r"dispute|incorrect (amount|invoice)|overcharg|short pa(id|y)|wrong price", "AR Specialist", "High"),
    "remittance": (r"remittance|payment (sent|made|confirmation)|ach|wire (sent|confirmation)|check (sent|mailed)", "Cash Application", "Normal"),
    "credit_request": (r"credit (memo|note|request)|refund|return(ed)? (product|item)", "AR Specialist", "Normal"),
    "w9_vendor_setup": (r"\bw-?9\b|vendor (setup|form)|supplier (setup|onboarding)", "AR Coordinator", "Low"),
    "statement_request": (r"statement|aging|open invoices|account balance", "AR Coordinator", "Low"),
    "financing_question": (r"financ|lease|leasing|payment plan", "Finance Manager", "Normal"),
}

INVOICE_RE = re.compile(r"\b(?:INV|Invoice)[\s#:-]*([A-Z]?\d{5,8})\b", re.I)
AMOUNT_RE = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")


@dataclass
class Email:
    msg_id: str
    sender: str
    subject: str
    body: str
    conversation_id: str = ""


@dataclass
class Case:
    case_id: str
    category: str
    priority: str
    owner_role: str
    customer_email: str
    invoice_numbers: list[str] = field(default_factory=list)
    amounts: list[float] = field(default_factory=list)
    status: str = "Open"
    history: list[str] = field(default_factory=list)


def classify(email: Email) -> tuple[str, str, str]:
    text = f"{email.subject}\n{email.body}".lower()
    for cat, (pattern, owner, prio) in CATEGORIES.items():
        if re.search(pattern, text):
            return cat, owner, prio
    return "needs_review", "Finance Director", "Normal"


def extract(email: Email) -> tuple[list[str], list[float]]:
    text = f"{email.subject}\n{email.body}"
    invoices = sorted({m.upper() for m in INVOICE_RE.findall(text)})
    amounts = [float(a.replace(",", "")) for a in AMOUNT_RE.findall(text)]
    return invoices, amounts


class Tracker:
    """Stand-in for the SharePoint list. Upserts by thread so replies update one case."""

    def __init__(self):
        self.cases: dict[str, Case] = {}
        self.by_thread: dict[str, str] = {}
        self.by_invoice: dict[str, str] = {}
        self.notifications: list[str] = []
        self._n = 0

    def _find_existing(self, email: Email, invoices: list[str]) -> Optional[Case]:
        if email.conversation_id and email.conversation_id in self.by_thread:
            return self.cases[self.by_thread[email.conversation_id]]
        for inv in invoices:
            if inv in self.by_invoice:
                return self.cases[self.by_invoice[inv]]
        return None

    def ingest(self, email: Email) -> Case:
        cat, owner, prio = classify(email)
        invoices, amounts = extract(email)
        case = self._find_existing(email, invoices)
        if case:
            case.history.append(f"update from {email.sender}: {email.subject}")
            if prio == "High":
                case.priority = "High"  # escalate, never downgrade
            case.invoice_numbers = sorted(set(case.invoice_numbers) | set(invoices))
            self.notifications.append(f"[{case.owner_role}] updated {case.case_id}")
        else:
            self._n += 1
            case = Case(f"AR-{self._n:04d}", cat, prio, owner, email.sender, invoices, amounts,
                        history=[f"opened from {email.sender}: {email.subject}"])
            self.cases[case.case_id] = case
            self.notifications.append(f"[{owner}] new {prio} case {case.case_id}: {cat}")
        if email.conversation_id:
            self.by_thread[email.conversation_id] = case.case_id
        for inv in invoices:
            self.by_invoice[inv] = case.case_id
        return case
