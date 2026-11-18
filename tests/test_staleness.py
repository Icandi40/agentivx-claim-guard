from datetime import date

from claim_guard import Source
from claim_guard.staleness import draws_on, is_time_sensitive, label_stale

NOW = date(2026, 3, 1)
OLD = Source(
    id="pricing",
    title="Pricing sheet",
    text="The Starter plan costs $49 per month and the Team plan costs $99 per month.",
    updated=date(2026, 1, 2),
)
FRESH = Source(id="faq", title="FAQ", text="Support hours are 9 to 5.", updated=date(2026, 2, 25))


def test_time_sensitive_sentences() -> None:
    assert is_time_sensitive("The Starter plan costs $49.")
    assert is_time_sensitive("The release is scheduled for spring.")
    assert not is_time_sensitive("Thanks for asking.")


def test_draws_on_by_detail_title_or_shared_words() -> None:
    assert draws_on("It costs $49.", OLD)
    assert draws_on("The pricing sheet lists two options.", OLD)
    assert draws_on("The Starter plan and Team plan are billed per month.", OLD)
    assert not draws_on("Hello there.", OLD)


def test_old_source_gets_a_label_with_age() -> None:
    labels = label_stale(["The Starter plan costs $49."], [OLD, FRESH], NOW)
    assert len(labels) == 1
    label = labels[0]
    assert label.source_id == "pricing"
    assert label.age_days == 58
    assert "Jan 2, 2026" in label.label and "58 days" in label.label


def test_fresh_source_and_timeless_sentence_get_no_label() -> None:
    assert label_stale(["Support hours are 9 to 5."], [FRESH], NOW) == ()
    assert label_stale(["Thanks, the Starter plan is popular."], [OLD], NOW) == ()


def test_archived_source_is_labelled_even_when_recent() -> None:
    archived = Source(text="Version 2 is the latest release.", title="Release notes", archived=True)
    labels = label_stale(["Version 2 is the latest release."], [archived], NOW)
    assert labels and labels[0].archived and "archived" in labels[0].label


def test_window_is_configurable() -> None:
    assert label_stale(["The Starter plan costs $49."], [OLD], NOW, stale_after_days=90) == ()
