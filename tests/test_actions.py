import pytest

from claim_guard.actions import find_action_claim

CLAIMS = [
    "I have sent the invoice to the client.",
    "I've booked the appointment for Tuesday.",
    "I just updated your calendar.",
    "We went ahead and cancelled the old plan.",
    "I believe I already emailed them.",
    "No problem, I've sent it.",
    "The landing page has been deployed.",
    "Your ticket was escalated to tier two.",
    "Everything is squared away with the bank.",
    "Your new card is on its way.",
    "You're all set.",
    "All done!",
    "The mic issue is fixed, no more clicking required.",
    "The voice setup is ready to go.",
    'The file is saved as "summary.md" in your reports folder.',
    "The integration is now live.",
    "Your manager has approved it.",
    "The change has been merged into main.",
]

NOT_CLAIMS = [
    "I can send the invoice once you approve it.",
    "Once you confirm, I'll book the appointment.",
    "If the payment was processed, you will get a receipt.",
    "I have not booked anything yet.",
    "Nothing has been sent.",
    "I haven't changed any settings.",
    "Did you already send the form?",
    "Make sure the backup has been saved before you upgrade.",
    "Would you like me to draft the reply?",
    "Refunds are processed within 14 days.",
    "Let me know when the form has been submitted.",
    "Here is a draft you can send.",
]


@pytest.mark.parametrize("sentence", CLAIMS)
def test_finds_completed_action_claims(sentence: str) -> None:
    assert find_action_claim(sentence) is not None


@pytest.mark.parametrize("sentence", NOT_CLAIMS)
def test_leaves_offers_conditionals_negatives_and_questions(sentence: str) -> None:
    assert find_action_claim(sentence) is None


def test_first_person_flag() -> None:
    claim = find_action_claim("I've sent it.")
    assert claim is not None and claim.first_person
    passive = find_action_claim("It has been sent.")
    assert passive is not None and not passive.first_person


def test_passive_claim_is_excused_when_a_source_records_the_event() -> None:
    sources = ["Order 4411 was refunded to the original card on March 2."]
    assert find_action_claim("Your order was refunded on March 2.", sources) is None


def test_policy_text_does_not_excuse_a_passive_claim() -> None:
    policy = ["Refunds are processed within 14 days of a return."]
    assert find_action_claim("Your refund has been processed.", policy) is not None


def test_attributed_passive_statement_is_kept() -> None:
    sentence = "According to the ticket, the router was reset on Monday."
    assert find_action_claim(sentence) is None


def test_first_person_claim_is_never_excused_by_sources() -> None:
    sources = ["Invoice INV-9 was sent on March 2."]
    assert find_action_claim("I sent invoice INV-9 on March 2.", sources) is not None
