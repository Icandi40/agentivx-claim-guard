"""Inputs and outputs of the guard."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

Rule = Literal["unverified_action", "contradicts_live_fact", "unsupported_detail"]


@dataclass(frozen=True)
class Source:
    """A piece of text the agent was given to answer from.

    ``updated`` is when the source was last edited. A source older than the staleness window,
    or one marked ``archived``, gets a label on any time-sensitive sentence that draws on it.
    Pass tool results, retrieved documents, and the user's own message as sources.
    """

    text: str
    title: str = ""
    id: str = ""
    updated: date | datetime | None = None
    archived: bool = False


@dataclass(frozen=True)
class Removal:
    """A sentence the guard removed, with the rule that fired and the words that triggered it."""

    sentence: str
    rule: Rule
    reason: str
    evidence: str


@dataclass(frozen=True)
class StaleLabel:
    """A source that a kept, time-sensitive sentence draws on, and why it may be out of date."""

    source_id: str
    source_title: str
    updated: date | None
    age_days: int | None
    archived: bool
    sentences: tuple[str, ...]
    label: str


@dataclass(frozen=True)
class GuardResult:
    """The outcome of :func:`claim_guard.guard`.

    ``text`` is the reply with unsupported sentences removed and nothing added. ``original`` is
    the reply exactly as the agent wrote it. ``removed`` and ``stale`` say what was dropped or
    flagged and why, so the pair forms an audit record.
    """

    original: str
    text: str
    removed: tuple[Removal, ...] = ()
    stale: tuple[StaleLabel, ...] = ()
    checked_sentences: int = 0
    notes: tuple[str, ...] = field(default=())

    @property
    def changed(self) -> bool:
        """True when at least one sentence was removed."""
        return bool(self.removed)

    @property
    def needs_review(self) -> bool:
        """True when a sentence was removed or a stale label was added."""
        return bool(self.removed or self.stale)

    def labelled_text(self) -> str:
        """The kept text followed by a short note for each removal type and each stale source."""
        lines = [self.text.rstrip()] if self.text.strip() else []
        extras = list(self.notes) + [s.label for s in self.stale]
        if extras:
            if lines:
                lines.append("")
            lines.extend(f"({extra})" for extra in extras)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        """A JSON-ready audit record: original text, kept text, removals and stale labels."""
        return {
            "original": self.original,
            "text": self.text,
            "checked_sentences": self.checked_sentences,
            "removed": [
                {
                    "sentence": r.sentence,
                    "rule": r.rule,
                    "reason": r.reason,
                    "evidence": r.evidence,
                }
                for r in self.removed
            ],
            "stale": [
                {
                    "source_id": s.source_id,
                    "source_title": s.source_title,
                    "updated": s.updated.isoformat() if s.updated else None,
                    "age_days": s.age_days,
                    "archived": s.archived,
                    "sentences": list(s.sentences),
                    "label": s.label,
                }
                for s in self.stale
            ],
        }
