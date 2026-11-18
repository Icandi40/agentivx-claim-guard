"""Labels for statements drawn from old or archived sources.

A sentence is time-sensitive when it states a price, percentage, date, status, deadline,
schedule, version or similar. When such a sentence draws on a source that was last updated more
than ``stale_after_days`` ago, or on an archived source, the guard keeps the sentence and adds a
label naming the source and its age. The sentence may still be right; the label tells the reader
to check before relying on it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime

from ._text import content_words
from .details import Evidence, extract_details
from .models import Source, StaleLabel

DEFAULT_STALE_AFTER_DAYS = 30

_TIME_SENSITIVE = re.compile(
    r"\b(?:price|prices|pricing|priced|cost|costs|fee|fees|rate|rates|status|launch|launched"
    r"|launches|deployed|shipped|released|release|deadline|due|scheduled|schedule|version"
    r"|pending|blocked|latest|current|currently|available|availability|expire|expires|expiry"
    r"|valid|open|opens|closed|closes|hours|discount|promotion|in stock|out of stock|until)\b",
    re.IGNORECASE,
)


def is_time_sensitive(sentence: str) -> bool:
    """True when the sentence states something that can go out of date."""
    if _TIME_SENSITIVE.search(sentence):
        return True
    return any(d.kind in ("amount", "percentage", "date") for d in extract_details(sentence))


def draws_on(sentence: str, source: Source) -> bool:
    """True when the sentence uses the source.

    It does when it repeats one of the source's specific details, names the source by its title
    (eight characters or more), or shares three distinctive words with it.
    """
    details = extract_details(sentence)
    if details:
        evidence = Evidence.from_texts([source.title, source.text])
        if any(evidence.supports(d) for d in details):
            return True
    title = source.title.strip().lower()
    if len(title) >= 8 and title in sentence.lower():
        return True
    shared = content_words(sentence) & content_words(source.title + " " + source.text)
    return len(shared) >= 3


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def label_stale(
    sentences: Sequence[str],
    sources: Sequence[Source],
    now: date | datetime,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
) -> tuple[StaleLabel, ...]:
    """Return one label per old or archived source that a time-sensitive sentence draws on."""
    today = _as_date(now)
    timely = [s for s in sentences if is_time_sensitive(s)]
    labels: list[StaleLabel] = []
    for index, source in enumerate(sources):
        updated = _as_date(source.updated) if source.updated is not None else None
        age = (today - updated).days if updated is not None else None
        if not (source.archived or (age is not None and age > stale_after_days)):
            continue
        using = tuple(s for s in timely if draws_on(s, source))
        if not using:
            continue
        name = source.title or source.id or f"source {index + 1}"
        kind = "an archived source" if source.archived else "a source"
        when = (
            f" last updated {updated:%b} {updated.day}, {updated.year} ({age} days earlier)"
            if updated is not None
            else ""
        )
        label = (
            f'This draws on "{name}", {kind}{when}. '
            "It may be out of date; check it before relying on it."
        )
        labels.append(
            StaleLabel(
                source_id=source.id,
                source_title=source.title,
                updated=updated,
                age_days=age,
                archived=source.archived,
                sentences=using,
                label=label,
            )
        )
    return tuple(labels)
