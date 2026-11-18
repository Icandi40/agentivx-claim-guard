import pytest

from claim_guard.live_facts import find_contradiction, status_polarity

FACTS = {"payment gateway": "disconnected", "desk mic": "off", "backup job": "running"}


@pytest.mark.parametrize(
    ("status", "polarity"),
    [
        ("on", "up"),
        ("Connected", "up"),
        ("running", "up"),
        ("off", "down"),
        ("disconnected", "down"),
        ("not connected", "down"),
        ("Setup needed", "down"),
        ("unknown", None),
    ],
)
def test_status_polarity(status: str, polarity: str | None) -> None:
    assert status_polarity(status) == polarity


@pytest.mark.parametrize(
    "sentence",
    [
        "The payment gateway is connected again.",
        "The gateway is working fine now.",
        "Your desk mic is on and listening.",
        "The backup job is stopped.",
        "The backup job isn't running.",
    ],
)
def test_contradictions_are_found(sentence: str) -> None:
    assert find_contradiction(sentence, FACTS) is not None


@pytest.mark.parametrize(
    "sentence",
    [
        "The payment gateway is disconnected right now.",
        "Your desk mic is off.",
        "The backup job is running.",
        "Once the payment gateway is connected, I can retry the charge.",
        "Is the desk mic on?",
        "The office printer is offline.",
        "Based on the logs, the backup job is running.",
    ],
)
def test_true_or_unrelated_statements_are_kept(sentence: str) -> None:
    assert find_contradiction(sentence, FACTS) is None


def test_lock_and_door_axes() -> None:
    facts = {"front door lock": "unlocked", "garage door": "open"}
    assert find_contradiction("The front door is locked.", facts) is not None
    assert find_contradiction("The garage door is closed.", facts) is not None
    assert find_contradiction("The garage door is open.", facts) is None
    assert find_contradiction("The thermostat reads 68.", {"thermostat": "68 degrees"}) is None
