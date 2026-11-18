from decimal import Decimal

import pytest

from claim_guard.details import Evidence, extract_details


def kinds(text: str) -> list[str]:
    return sorted(d.kind for d in extract_details(text))


def test_extracts_each_kind() -> None:
    text = (
        "Call (212) 555-0142 by March 3, see https://example.com/pricing and report.pdf, "
        "email help@example.org, 15% off $49."
    )
    assert kinds(text) == sorted(["phone", "date", "link", "file", "email", "percentage", "amount"])


def test_email_domain_is_not_also_a_link() -> None:
    assert kinds("Write to billing@northwind.example.com today.") == ["email"]


def test_iso_date_digits_are_not_a_phone() -> None:
    assert kinds("It shipped on 2026-03-02.") == ["date"]


def test_may_the_verb_is_not_a_month() -> None:
    assert kinds("You may 3 times retry.") == []


def test_long_unformatted_number_is_not_a_phone() -> None:
    assert kinds("Your order number is 4411902837.") == []


def test_amount_normalisation() -> None:
    values = {d.text: d.value for d in extract_details("$1,200 and $1.2k and 1200 USD and €5")}
    assert values["$1,200"] == ("USD", Decimal("1200"))
    assert values["$1.2k"] == ("USD", Decimal("1200"))
    assert values["1200 USD"] == ("USD", Decimal("1200"))
    assert values["€5"] == ("EUR", Decimal("5"))


@pytest.mark.parametrize(
    ("source", "reply"),
    [
        ("Total: $1200.00", "It costs $1,200."),
        ("Due 2026-03-03.", "It is due March 3."),
        ("Due March 3, 2026.", "It is due 2026-03-03."),
        ("Due 3/3/2026.", "It is due 3 March 2026."),
        ("A 15 percent discount.", "You get 15% off."),
        ("See https://www.example.com/pricing/", "See example.com/pricing."),
        ("See https://example.com/pricing", "Visit example.com."),
        ("Call +1 (212) 555-0142.", "Call 212-555-0142."),
        ("Stored at reports/Q1-summary.pdf", "Open Q1-summary.pdf."),
        ("Mail Help@Example.org", "Mail help@example.org."),
    ],
)
def test_equivalent_formats_are_supported(source: str, reply: str) -> None:
    evidence = Evidence.from_texts([source])
    details = extract_details(reply)
    assert details
    assert all(evidence.supports(d) for d in details)


@pytest.mark.parametrize(
    ("source", "reply"),
    [
        ("Plan A costs $20.", "Plan A costs $25."),
        ("Due 2026-03-03.", "It is due March 4."),
        ("Due 2025-03-03.", "It is due 2026-03-03."),
        ("See example.com", "See example.com/pricing."),
        ("Call 212-555-0142.", "Call 212-555-0199."),
        ("Mail help@example.org", "Mail sales@example.org."),
        ("Open notes.md", "Open notes.pdf."),
        ("A 15% discount.", "A 20% discount."),
    ],
)
def test_different_values_are_not_supported(source: str, reply: str) -> None:
    evidence = Evidence.from_texts([source])
    assert not all(evidence.supports(d) for d in extract_details(reply))
