"""Specific details: prices, percentages, dates, links, file names, emails and phone numbers.

A detail in a reply counts as supported when the same value appears in a source, even in a
different format: "$1,200" matches "$1200" and "1.2k USD", "March 3" matches "2026-03-03",
"15 percent" matches "15%", and "example.com" matches "https://www.example.com/pricing".
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

DetailKind = Literal["amount", "percentage", "date", "link", "email", "file", "phone"]

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
# Month names must be capitalised so the verb "may" is not read as a month.
_MONTH = (
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?"
    r"|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
)
_TLDS = r"(?:com|org|net|io|ai|dev|app|co|gov|edu|us|uk|info|biz)"

_LINK = re.compile(
    r"https?://[^\s<>\"'”)\]]+"
    r"|\b(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\." + _TLDS + r"\b(?:/[^\s<>\"'”)\]]*)?",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_FILE = re.compile(
    r"\b[\w-]+(?:\.[\w-]+)*\.(?:md|pdf|docx?|xlsx?|pptx?|txt|csv|json|ya?ml|py|ts|js|html"
    r"|png|jpe?g|zip|log)\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_MONTH_DAY = re.compile(r"\b" + _MONTH + r"\s+(\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s+(\d{4})\b)?")
_DAY_MONTH = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MONTH + r"(?:,?\s+(\d{4})\b)?"
)
_AMOUNT = re.compile(
    r"([$€£])\s?(\d[\d,]*(?:\.\d+)?)(?:\s?(k|m|bn|thousand|million|billion)\b)?"
    r"|\b(\d[\d,]*(?:\.\d+)?)\s?(k|m|thousand|million|billion)?\s?"
    r"(dollars|usd|euros?|eur|pounds|gbp)\b",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"\b(\d+(?:\.\d+)?)\s?(?:%|percent\b|per cent\b)", re.IGNORECASE)
_PHONE = re.compile(r"(?<![\w/])\+?\(?\d[\d\s().-]{5,}\d(?![\w/])")

_MULTIPLIERS = {
    "k": 1000,
    "thousand": 1000,
    "m": 1_000_000,
    "million": 1_000_000,
    "bn": 1_000_000_000,
    "billion": 1_000_000_000,
}
_CURRENCY = {
    "$": "USD",
    "dollars": "USD",
    "usd": "USD",
    "€": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "pounds": "GBP",
    "gbp": "GBP",
}


@dataclass(frozen=True)
class Detail:
    """One specific detail found in a piece of text.

    ``text`` is the wording as written. ``value`` is the normalised form used for matching:
    a string for links, emails, files and phones, a ``Decimal`` for percentages, a
    ``(currency, Decimal)`` pair for amounts and a ``(year or None, month, day)`` triple
    for dates.
    """

    kind: DetailKind
    text: str
    value: object


_Builder = Callable[[re.Match[str]], Detail | None]


def extract_details(text: str) -> list[Detail]:
    """Find every specific detail in ``text``.

    Links and emails are read first and masked, so the domain inside an email is not also
    read as a link and the digits inside a date are not read as a phone number.
    """
    found: list[Detail] = []
    masked = text

    def take(pattern: re.Pattern[str], build: _Builder) -> None:
        nonlocal masked
        for match in list(pattern.finditer(masked)):
            detail = build(match)
            if detail is not None:
                found.append(detail)
                masked = masked[: match.start()] + "\0" * len(match[0]) + masked[match.end() :]

    take(_EMAIL, lambda m: Detail("email", m[0], m[0].rstrip(".").lower()))
    take(_LINK, _build_link)
    take(_FILE, lambda m: Detail("file", m[0], m[0].lower()))
    take(_ISO_DATE, lambda m: _build_date(m[0], m[1], m[2], m[3]))
    take(_SLASH_DATE, lambda m: _build_date(m[0], m[3], m[1], m[2]))
    take(_MONTH_DAY, lambda m: _build_date(m[0], m[3], _month(m[1]), m[2]))
    take(_DAY_MONTH, lambda m: _build_date(m[0], m[3], _month(m[2]), m[1]))
    take(_AMOUNT, _build_amount)
    take(_PERCENT, lambda m: _build_number("percentage", m[0], m[1]))
    take(_PHONE, _build_phone)
    return found


def _month(name: str) -> str:
    return str(_MONTHS.index(name[:3].lower()) + 1)


def _build_link(m: re.Match[str]) -> Detail | None:
    raw = m[0].rstrip(".,;:!?")
    norm = re.sub(r"^https?://", "", raw.lower())
    norm = re.sub(r"^www\.", "", norm).rstrip("/")
    return Detail("link", raw, norm)


def _build_date(text: str, year: str | None, month: str, day: str) -> Detail | None:
    m, d = int(month), int(day)
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    return Detail("date", text.strip(), (int(year) if year else None, m, d))


def _to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None


def _build_number(kind: DetailKind, text: str, raw: str) -> Detail | None:
    value = _to_decimal(raw)
    return None if value is None else Detail(kind, text.strip(), value.normalize())


def _build_amount(m: re.Match[str]) -> Detail | None:
    if m[1]:
        symbol, raw, scale = m[1], m[2], m[3]
    else:
        raw, scale, symbol = m[4], m[5], m[6]
    value = _to_decimal(raw.rstrip(".,"))
    if value is None:
        return None
    if scale:
        value *= _MULTIPLIERS[scale.lower()]
    currency = _CURRENCY.get(symbol.lower(), _CURRENCY.get(symbol, "USD"))
    return Detail("amount", m[0].strip().rstrip(".,"), (currency, value.normalize()))


def _build_phone(m: re.Match[str]) -> Detail | None:
    digits = re.sub(r"\D", "", m[0])
    # Seven digits ("555-0142") up to fifteen (international). Plain long numbers without any
    # separator are more likely order or account numbers than phones, so they are skipped.
    if not 7 <= len(digits) <= 15 or not re.search(r"[\s().-]", m[0]):
        return None
    return Detail("phone", m[0].strip(), digits)


@dataclass(frozen=True)
class Evidence:
    """Everything the sources say, indexed for detail lookups."""

    details: tuple[Detail, ...]
    lowered: str

    @classmethod
    def from_texts(cls, texts: Iterable[str]) -> Evidence:
        """Build the index from the full text of every source and live fact."""
        joined = "\n".join(texts)
        return cls(tuple(extract_details(joined)), joined.lower())

    def supports(self, detail: Detail) -> bool:
        """Return True when the sources contain the same value as ``detail``."""
        same_kind = [d for d in self.details if d.kind == detail.kind]
        if detail.kind == "date":
            year, month, day = _date_parts(detail.value)
            for other in same_kind:
                oy, om, od = _date_parts(other.value)
                if (om, od) == (month, day) and (year is None or oy is None or year == oy):
                    return True
            return False
        if detail.kind == "link":
            link = str(detail.value)
            return (
                any(str(o.value) == link or str(o.value).startswith(link + "/") for o in same_kind)
                or link in self.lowered
            )
        if detail.kind == "file":
            return str(detail.value) in self.lowered
        if detail.kind == "phone":
            digits = str(detail.value)
            return any(
                str(o.value).endswith(digits) or digits.endswith(str(o.value))
                for o in same_kind
                if min(len(digits), len(str(o.value))) >= 7
            )
        return any(o.value == detail.value for o in same_kind)


def _date_parts(value: object) -> tuple[int | None, int, int]:
    assert isinstance(value, tuple) and len(value) == 3
    year, month, day = value
    return (year if isinstance(year, int) else None, int(month), int(day))
