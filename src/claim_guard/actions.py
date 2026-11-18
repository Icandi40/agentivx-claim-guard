"""Claims of completed actions.

An agent that only talks cannot send, save, book, fix or deploy anything. A sentence that says
it did ("I've sent the invoice", "Your appointment has been booked", "You're all set") is a
claim the agent cannot back up. Offers, plans, conditionals, questions, advice and honest
negatives are not claims and are left alone.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from ._text import content_words

_A = "['’]"

# Past tense or participle forms an agent would use about its own work.
_FIRST_PERSON_ACTIONS = (
    "sent|saved|created|built|fixed|repaired|set up|booked|reserved|scheduled|rescheduled"
    "|cancell?ed|deployed|published|posted|updated|installed|configured|uploaded|downloaded"
    "|deleted|removed|moved|renamed|emailed|texted|called|messaged|paid|refunded|charged"
    "|processed|submitted|filed|signed|committed|pushed|merged|restarted|rebooted|reset"
    "|activated|enabled|disabled|turned (?:on|off)|switched (?:on|off)|connected|disconnected"
    "|resolved|completed|finished|launched|started|stopped|ordered|purchased|bought|transferred"
    "|added|applied|approved|escalated|forwarded|shared|changed|adjusted|tweaked|patched|ran"
    "|tested|notified|contacted|reached out|issued|placed|renewed|upgraded|downgraded"
    "|backed up|restored|migrated|synced|unlocked|locked|wired up|took care of|handled|sorted"
    "|made the (?:change|changes|booking|reservation|payment|appointment)"
)
# Participles that describe work done for the user. Words that usually describe facts in a
# source ("updated", "launched", "released", "shipped") are left out on purpose.
_PASSIVE_ACTIONS = (
    "sent|saved|created|fixed|repaired|set up|booked|reserved|scheduled|rescheduled"
    "|cancell?ed|deployed|published|posted|installed|configured|uploaded|deleted|emailed"
    "|forwarded|paid|refunded|processed|submitted|filed|signed|restarted|reset|activated"
    "|enabled|disabled|turned (?:on|off)|connected|resolved|completed|done|escalated|issued"
    "|approved|applied|renewed|upgraded|placed|ordered|restored|unlocked|wired up|taken care of"
    "|merged|pushed|committed"
    "|squared away|sorted(?: out)?|handled"
)

_FIRST_PERSON = re.compile(
    rf"\b(?:i|we)(?:{_A}ve|{_A}d| have| had)?\s+"
    rf"(?:(?:just|already|now|also|successfully|finally|quickly|gone ahead and|went ahead and)\s+)*"
    rf"(?:{_FIRST_PERSON_ACTIONS})\b",
    re.IGNORECASE,
)
_PASSIVE = re.compile(
    rf"\b(?:has been|have been|had been|was|were|{_A}s been|got|gets|is now|are now|is already"
    rf"|are already|is all|are all|{_A}s all|{_A}s now|{_A}s already)\s+"
    rf"(?:(?:now|already|all|fully|successfully|officially|just|been)\s+)*"
    rf"(?:{_PASSIVE_ACTIONS})\b",
    re.IGNORECASE,
)
# Someone else finished something: "Your manager has approved it", "The client has paid".
_THIRD_PARTY = re.compile(
    r"\b(?:has|have)\s+(?:(?:already|now|just|finally)\s+)?"
    r"(?:approved|signed|paid|accepted|agreed|confirmed|replied|responded|booked|sent|received"
    r"|reviewed|completed|finished|fixed|resolved)\b",
    re.IGNORECASE,
)
# A finished state stated in the present: "The issue is fixed", "Your table is booked".
_DONE_STATE = re.compile(
    rf"\b(?:is|are|{_A}s|{_A}re)\s+(?:now\s+|all\s+|fully\s+|officially\s+)?"
    r"(?:fixed|resolved|done|complete|completed|booked|reserved|cancell?ed|sent|saved|paid"
    r"|refunded|set up|configured|installed|deployed|submitted|approved|activated)\b",
    re.IGNORECASE,
)
_FILE_PLACED = re.compile(
    r"\bis\s+(?:now\s+)?(?:saved|stored|filed)\s+(?:as|in|under|to|into)\b", re.IGNORECASE
)
_PHRASE = re.compile(
    rf"\b(?:is|are|{_A}re|{_A}s|{_A}m)\s+(?:now\s+|all\s+|officially\s+)?"
    r"(?:all set|good to go|squared away|taken care of|sorted(?: out)?|on (?:its|their|the) way"
    r"|up and running)\b"
    r"|^\s*all (?:done|set)\b"
    rf"|\b(?:is|are|{_A}s|{_A}re)\s+now\s+(?:live|connected|enabled|active|online|on|running"
    r"|working|fixed)\b"
    r"|\b(?:setup|set-up|set up|configured|installed|connected|wired)\b[^.!?]*\bready\b",
    re.IGNORECASE,
)

_CUT = re.compile(r"[,;:()]|\s[-\u2013\u2014]\s|\b(?:but|so|and)\s", re.IGNORECASE)
_HYPOTHETICAL = re.compile(
    rf"\b(?:if|once|when|whenever|after|as soon as|unless|until|before|whether|can|could"
    rf"|would|will|won{_A}t|shall|should|might|may|must|let me|want me|{_A}ll|{_A}d like"
    r"|going to|plan to|planning to|need to|needs to|want to|ready to|about to|able to"
    r"|try to|hope to|happy to|expect to)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    rf"\b(?:not|never|no|nothing|none|neither|nor|nobody|no one|yet to)\b|n{_A}t\b",
    re.IGNORECASE,
)
_ADVICE = re.compile(
    r"^\s*(?:please\s+)?(?:ensure|make sure|check|confirm|verify|remember|double-check|consider"
    r"|note that|try|be sure)\b",
    re.IGNORECASE,
)
_ATTRIBUTED = re.compile(
    r"\baccording to\b|\b(?:notes?|records?|logs?|ticket|history|source|document|page|system"
    r"|dashboard|email|message|policy|confirmation|receipt|tracking|portal|account)\s+"
    r"(?:says?|shows?|mentions?|records?|states?|lists?|confirms?|indicates?|notes?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ActionClaim:
    """A claim of a completed action found in one sentence."""

    phrase: str
    first_person: bool


def find_action_claim(sentence: str, source_sentences: Sequence[str] = ()) -> ActionClaim | None:
    """Return the first completed-action claim in ``sentence``, or None.

    First person claims ("I've booked it") are always returned, since an agent without tools
    could not have done the work. Other claims ("Your refund has been processed", "Your card is
    on its way") are excused when the sentence cites a record ("according to the ticket") or a
    source sentence reports the same completed event in the past tense.
    """
    text = sentence.strip()
    if not text or text.endswith("?"):
        return None
    for pattern, first_person in (
        (_FIRST_PERSON, True),
        (_PASSIVE, False),
        (_DONE_STATE, False),
        (_THIRD_PARTY, False),
        (_FILE_PLACED, False),
        (_PHRASE, False),
    ):
        for match in pattern.finditer(text):
            before = _clause_before(text, match.start())
            if _HYPOTHETICAL.search(before) or _ADVICE.search(before):
                continue
            if _NEGATION.search(before + match[0]):
                continue
            if not first_person and (
                _ATTRIBUTED.search(text) or _recorded(text, match[0], source_sentences)
            ):
                continue
            return ActionClaim(match[0].strip(), first_person)
    return None


def _clause_before(text: str, pos: int) -> str:
    head = text[:pos]
    cuts = list(_CUT.finditer(head))
    return head[cuts[-1].end() :] if cuts else head


def _recorded(sentence: str, phrase: str, source_sentences: Sequence[str]) -> bool:
    key = phrase.lower().split()[-1]
    key_re = re.compile(rf"\b{re.escape(key)}\b", re.IGNORECASE)
    generic = re.compile(
        r"\b(?:are|can|will|may|must|should|typically|usually|normally|generally"
        rf"|automatically)\s+(?:\w+\s+)?{re.escape(key)}\b",
        re.IGNORECASE,
    )
    words = content_words(sentence) - content_words(phrase)
    for source in source_sentences:
        if not key_re.search(source) or generic.search(source):
            continue
        if words & content_words(source):
            return True
    return False
