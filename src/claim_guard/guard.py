"""The guard: one call that checks a reply sentence by sentence."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime

from ._text import split_line, split_sentences
from .actions import find_action_claim
from .details import Detail, Evidence, extract_details
from .live_facts import find_contradiction
from .models import GuardResult, Removal, Source
from .staleness import DEFAULT_STALE_AFTER_DAYS, label_stale

_KIND_NAMES = {
    "amount": "price or amount",
    "percentage": "percentage",
    "date": "date",
    "link": "link",
    "email": "email address",
    "file": "file name",
    "phone": "phone number",
}
_NOTES = {
    "unverified_action": "Removed a sentence that said something was done; there is no record "
    "of it being done.",
    "contradicts_live_fact": "Removed a sentence that did not match the current live status.",
    "unsupported_detail": "Left out a specific detail that is not in the supplied sources.",
}


def guard(
    reply: str,
    sources: Sequence[Source | str] = (),
    live_facts: Mapping[str, str] | None = None,
    tools_available: bool = False,
    now: date | datetime | None = None,
    *,
    check_details: bool = True,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
) -> GuardResult:
    """Check an agent's reply and remove the sentences it cannot back up.

    A sentence is removed when it:

    * claims a completed action ("I've sent the invoice", "You're all set") and
      ``tools_available`` is False, so the agent could not have done it;
    * describes something named in ``live_facts`` as the opposite of its current status;
    * gives a price, percentage, date, link, file name, email or phone number that appears in
      none of the ``sources`` or ``live_facts`` (skip with ``check_details=False``).

    Kept sentences that state something time-sensitive and draw on a source older than
    ``stale_after_days``, or an archived source, get a :class:`StaleLabel`.

    Args:
        reply: The agent's reply, as plain text or Markdown.
        sources: What the agent was given: retrieved documents, tool output, the user's message.
            Plain strings are wrapped in :class:`Source`.
        live_facts: Current status read by code, such as ``{"desk mic": "off"}``.
        tools_available: Set True when the agent could act this turn. Action claims are then
            kept, since text alone cannot show whether a tool call happened.
        now: The reference time for staleness. Defaults to today (UTC); pass it for repeatable
            results.
        check_details: Set False to skip the specific-detail check.
        stale_after_days: Age in days after which a source counts as old.

    Returns:
        A :class:`GuardResult` holding the original text, the kept text, every removal with its
        reason, and any stale labels.
    """
    items = [
        s if isinstance(s, Source) else Source(text=s, id=f"source-{i + 1}")
        for i, s in enumerate(sources)
    ]
    facts = dict(live_facts or {})
    evidence = Evidence.from_texts(
        [f"{s.title}\n{s.text}" for s in items] + [f"{k}: {v}" for k, v in facts.items()]
    )
    source_sentences = [x for s in items for x in split_sentences(s.text)]

    removed: list[Removal] = []
    kept_sentences: list[str] = []
    out_lines: list[str] = []
    checked = 0
    for line in reply.split("\n"):
        prefix, spans = split_line(line)
        kept_here = []
        for span in spans:
            checked += 1
            removal = _check(
                span.text, evidence, source_sentences, facts, tools_available, check_details
            )
            if removal is None:
                kept_here.append(span.text)
            else:
                removed.append(removal)
        kept_sentences.extend(kept_here)
        if len(kept_here) == len(spans):
            out_lines.append(line)
        elif kept_here:
            out_lines.append(prefix + " ".join(kept_here))

    text = reply
    if removed:
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(out_lines)).strip()

    reference = now if now is not None else datetime.now(UTC).date()
    stale = label_stale(kept_sentences, items, reference, stale_after_days)
    notes = tuple(_NOTES[rule] for rule in _NOTES if any(r.rule == rule for r in removed))
    return GuardResult(
        original=reply,
        text=text,
        removed=tuple(removed),
        stale=stale,
        checked_sentences=checked,
        notes=notes,
    )


def _check(
    sentence: str,
    evidence: Evidence,
    source_sentences: Sequence[str],
    facts: Mapping[str, str],
    tools_available: bool,
    check_details: bool,
) -> Removal | None:
    if not tools_available:
        claim = find_action_claim(sentence, source_sentences)
        if claim is not None:
            who = "the agent" if claim.first_person else "something"
            return Removal(
                sentence,
                "unverified_action",
                f'says {who} completed an action ("{claim.phrase}"), but the agent had no '
                "tools to act with",
                claim.phrase,
            )
    if facts:
        conflict = find_contradiction(sentence, facts)
        if conflict is not None:
            return Removal(
                sentence,
                "contradicts_live_fact",
                f"describes {conflict.name} as {conflict.said}, but its live status is "
                f'"{conflict.status}"',
                conflict.name,
            )
    if check_details:
        missing = _first_unsupported(extract_details(sentence), evidence)
        if missing is not None:
            return Removal(
                sentence,
                "unsupported_detail",
                f"gives a {_KIND_NAMES[missing.kind]} ({missing.text}) that appears in none of "
                "the sources",
                missing.text,
            )
    return None


def _first_unsupported(details: Sequence[Detail], evidence: Evidence) -> Detail | None:
    for detail in details:
        if not evidence.supports(detail):
            return detail
    return None
