"""Text helpers shared by the checks: sentence splitting and content words."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Abbreviations whose final period does not end a sentence.
_ABBREVIATIONS = frozenset(
    {
        "e.g.",
        "i.e.",
        "etc.",
        "vs.",
        "mr.",
        "mrs.",
        "ms.",
        "dr.",
        "st.",
        "no.",
        "u.s.",
        "a.m.",
        "p.m.",
        "inc.",
        "ltd.",
        "jr.",
        "sr.",
        "approx.",
    }
)
_BOUNDARY = re.compile(r"[.!?]+[\"'”’)\]*_]*(?=\s|$)")
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d{1,3}[.)])\s+")

_STOPWORDS = frozenset(
    """about above after again against also being below between could doing during every
    first from have having here into just know like might more most need never note notes
    other over please really right same should since some source sources still such sure than
    thank thanks that their them then there these they this those through today under until
    very want were what when where which while will with would your yours does done make
    made only well each both because before""".split()
)


@dataclass(frozen=True)
class Span:
    """A sentence and its character offsets inside the line it came from."""

    text: str
    start: int
    end: int


def split_line(line: str) -> tuple[str, list[Span]]:
    """Split one line into a list marker prefix (such as "- " or "2. ") and its sentences.

    A sentence ends at ".", "!" or "?" followed by whitespace or the end of the line, so
    "report.pdf", "3.5" and "https://example.com/a.b" stay whole. Common abbreviations
    ("e.g.", "Dr.") and single-letter initials do not end a sentence, and neither does a
    period followed by a lowercase word.
    """
    bullet = _BULLET.match(line)
    offset = bullet.end() if bullet else 0
    prefix = line[:offset]
    body = line[offset:]
    spans: list[Span] = []
    start = 0
    for match in _BOUNDARY.finditer(body):
        end = match.end()
        if not _is_boundary(body, match.start(), end):
            continue
        _append(spans, body, start, end, offset)
        start = end
    _append(spans, body, start, len(body), offset)
    return prefix, spans


def _is_boundary(body: str, punct_start: int, end: int) -> bool:
    word_start = body.rfind(" ", 0, punct_start) + 1
    word = body[word_start:end].lower().strip("\"'“‘(")
    # After a number, a short word is a unit ("42 ms.", "60 F."), not an abbreviation or initial.
    after_number = bool(re.search(r"\d\s+$", body[:word_start]))
    if word in _ABBREVIATIONS and not after_number:
        return False
    if re.fullmatch(r"[a-z]\.", word) and punct_start - word_start == 1 and not after_number:
        return False
    following = body[end:].lstrip()
    return not (following and following[0].islower())


def _append(spans: list[Span], body: str, start: int, end: int, offset: int) -> None:
    chunk = body[start:end]
    stripped = chunk.strip()
    if not stripped:
        return
    lead = len(chunk) - len(chunk.lstrip())
    s = start + lead + offset
    spans.append(Span(stripped, s, s + len(stripped)))


def split_sentences(text: str) -> list[str]:
    """Return every sentence in ``text``, line by line, without list markers."""
    out: list[str] = []
    for line in text.split("\n"):
        out.extend(span.text for span in split_line(line)[1])
    return out


def content_words(text: str) -> set[str]:
    """Distinctive lowercase words (four or more letters, stopwords dropped, plural "s" removed)."""
    words = set()
    for word in re.findall(r"[a-z][a-z0-9-]{3,}", text.lower()):
        if word in _STOPWORDS:
            continue
        if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        words.add(word)
    return words
