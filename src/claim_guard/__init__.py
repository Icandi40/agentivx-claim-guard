"""claim-guard: remove what an AI agent's reply cannot back up, and keep a record of why.

Example:
    >>> from datetime import date
    >>> from claim_guard import guard
    >>> result = guard(
    ...     "I've emailed the invoice to the client. The total is $1,450.",
    ...     sources=["Invoice INV-204 total: $1,450.00, due 2026-03-15."],
    ...     now=date(2026, 3, 1),
    ... )
    >>> result.text
    'The total is $1,450.'
    >>> result.removed[0].rule
    'unverified_action'
"""

from ._text import split_sentences
from .details import Detail, extract_details
from .guard import guard
from .models import GuardResult, Removal, Rule, Source, StaleLabel
from .staleness import DEFAULT_STALE_AFTER_DAYS

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_STALE_AFTER_DAYS",
    "Detail",
    "GuardResult",
    "Removal",
    "Rule",
    "Source",
    "StaleLabel",
    "__version__",
    "extract_details",
    "guard",
    "split_sentences",
]
