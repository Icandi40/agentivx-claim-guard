"""Statements that contradict live status.

``live_facts`` maps a system or device name to its current status, read by code at the moment
the reply is checked, for example ``{"payment gateway": "disconnected", "front door": "locked"}``.
A sentence that names one of them and describes the opposite state is removed.

States are read on three axes: power or connection (on / off, connected / disconnected,
running / stopped), locks (locked / unlocked) and doors (open / closed). A status that fits none
of them, such as "68 degrees", is not checked.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

_A = "['’]"
_NEG = rf"\b(?:not|isn{_A}t|aren{_A}t|wasn{_A}t|weren{_A}t|never|no longer)\s+(?:\w+\s+)?"

_POWER_UP = (
    r"connected|enabled|running|online|active|live|listening|working|ready|healthy"
    r"|operational|available|awake|set up|configured|turned on|switched on|up and running"
)
_POWER_DOWN = (
    r"off|disconnected|disabled|stopped|offline|down|muted|failed|failing|broken|unavailable"
    r"|inactive|paused|error|errors|needs? setup|setup needed|expired|unplugged|asleep|sleeping"
    r"|turned off|switched off"
)


@dataclass(frozen=True)
class _Axis:
    name: str
    sides: tuple[str, str]
    cores: tuple[str, str]
    status: tuple[re.Pattern[str], re.Pattern[str]]
    sentence: tuple[re.Pattern[str], re.Pattern[str]]


def _words(alternatives: str) -> re.Pattern[str]:
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


# In a status string a bare "on" or "up" is a status. In a sentence they only count after a
# verb ("is on", "still up"), so "based on" and "follow up" are not read as status words.
_AXES = (
    _Axis(
        "power",
        ("up", "down"),
        (rf"on|up|{_POWER_UP}", _POWER_DOWN),
        (_words(rf"on|up|{_POWER_UP}"), _words(_POWER_DOWN)),
        (
            re.compile(
                rf"\b(?:{_POWER_UP})\b|\b(?:is|are|was|were|still|now|stays?|left|{_A}s|{_A}re)"
                r"\s+(?:on|up)\b",
                re.IGNORECASE,
            ),
            _words(_POWER_DOWN),
        ),
    ),
    _Axis(
        "lock",
        ("locked", "unlocked"),
        ("locked|secured", "unlocked|unsecured"),
        (_words("locked|secured"), _words("unlocked|unsecured")),
        (_words("locked|secured"), _words("unlocked|unsecured")),
    ),
    _Axis(
        "door",
        ("open", "closed"),
        ("open|opened|ajar", "closed|shut"),
        (_words("open|opened|ajar"), _words("closed|shut")),
        (_words("open|opened|ajar|left open"), _words("closed|shut")),
    ),
)

_HYPOTHETICAL = re.compile(
    r"\b(?:if|once|when|whenever|until|unless|after|whether|can|could|would|will|should|might"
    r"|may|need to|needs to|want to|try)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Contradiction:
    """A sentence that describes a live fact as the opposite of its current status."""

    name: str
    status: str
    said: str


def _side(
    text: str, patterns: tuple[re.Pattern[str], re.Pattern[str]], cores: tuple[str, str]
) -> int | None:
    """Return 0 or 1 for the side of an axis the text states, or None if unclear.

    A negated word counts for the other side: "not connected" reads as down.
    """
    hits = [False, False]
    for index in (0, 1):
        negated = re.compile(_NEG + rf"(?:{cores[index]})\b", re.IGNORECASE)
        if negated.search(text):
            hits[1 - index] = True
        if patterns[index].search(negated.sub(" ", text)):
            hits[index] = True
    if hits[0] != hits[1]:
        return 0 if hits[0] else 1
    return None


def status_state(status: str) -> tuple[str, str] | None:
    """Read a status string as an (axis, side) pair, such as ("power", "down")."""
    for axis in _AXES:
        side = _side(status, axis.status, axis.cores)
        if side is not None:
            return axis.name, axis.sides[side]
    return None


def status_polarity(status: str) -> str | None:
    """Read a power or connection status as "up" or "down", or None for anything else."""
    state = status_state(status)
    return state[1] if state and state[0] == "power" else None


def _mentions(sentence: str, name: str) -> bool:
    lowered = sentence.lower()
    words = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if len(w) >= 3]
    if not words:
        return False
    if re.search(rf"\b{re.escape(name.lower())}\b", lowered):
        return True
    # Every word of the name appears, allowing endings: "front door lock" in "front door is locked".
    if len(words) > 1 and all(re.search(rf"\b{re.escape(w)}", lowered) for w in words):
        return True
    # "payment gateway" is also mentioned as "the gateway".
    return len(words) > 1 and bool(
        re.search(rf"\b(?:the|your|my|our)\s+{re.escape(words[-1])}\b", lowered)
    )


def find_contradiction(sentence: str, live_facts: Mapping[str, str]) -> Contradiction | None:
    """Return the first live fact that ``sentence`` contradicts, or None.

    Questions and conditional sentences ("Once the gateway is connected...") are not checked.
    A sentence that states both sides of an axis ("It was off but is on now") is ambiguous and
    is left alone.
    """
    text = sentence.strip()
    if not text or text.endswith("?") or _HYPOTHETICAL.search(text):
        return None
    for name, status in live_facts.items():
        if not _mentions(text, name):
            continue
        for axis in _AXES:
            actual = _side(str(status), axis.status, axis.cores)
            if actual is None:
                continue
            said = _side(text, axis.sentence, axis.cores)
            if said is not None and said != actual:
                return Contradiction(name, str(status), axis.sides[said])
            break
    return None
