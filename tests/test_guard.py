import json
from datetime import date, datetime

from claim_guard import GuardResult, Source, guard, split_sentences

NOW = date(2026, 3, 1)


def test_removes_false_action_claims_and_keeps_the_rest() -> None:
    reply = (
        "The build failed because the agents page shows forms. "
        'The file is saved as "Build Attempt - Failed.md" in your tasks folder. '
        "Let me know if you want to try again.\n\n"
        "Also, the mic issue is fixed. The desk mic is on and running in always-on mode.\n\n"
        "What's next?"
    )
    result = guard(reply, live_facts={"desk mic": "off"}, now=NOW)
    assert [r.rule for r in result.removed] == [
        "unverified_action",
        "unverified_action",
        "contradicts_live_fact",
    ]
    assert "saved as" not in result.text and "always-on" not in result.text
    assert "Let me know if you want to try again." in result.text
    assert result.text.endswith("What's next?")
    assert result.original == reply


def test_tools_available_keeps_action_claims() -> None:
    result = guard("I've booked the table for 7.", tools_available=True, now=NOW)
    assert not result.changed


def test_unsupported_detail_is_removed_and_supported_one_kept() -> None:
    sources = [Source(text="The Pro plan is $99 per month.", title="Pricing")]
    reply = "The Pro plan is $99 per month. The Basic plan is $29 per month."
    result = guard(reply, sources, now=NOW)
    assert result.text == "The Pro plan is $99 per month."
    assert result.removed[0].rule == "unsupported_detail"
    assert result.removed[0].evidence == "$29"


def test_plain_strings_work_as_sources() -> None:
    result = guard("It is due 2026-03-15.", ["Invoice due March 15, 2026."], now=NOW)
    assert not result.changed


def test_live_facts_count_as_evidence_for_details() -> None:
    facts = {"last backup": "completed 2026-02-28"}
    result = guard("The last backup finished on February 28.", live_facts=facts, now=NOW)
    assert not result.changed


def test_details_check_can_be_turned_off() -> None:
    result = guard("Call 212-555-0142.", check_details=False, now=NOW)
    assert not result.changed


def test_list_markers_and_lines_are_preserved() -> None:
    reply = "Next steps:\n- I sent the form. Review it tonight.\n- I booked the room.\n- Ask HR."
    result = guard(reply, now=NOW)
    assert result.text == "Next steps:\n- Review it tonight.\n- Ask HR."
    assert result.checked_sentences == 5


def test_unchanged_reply_is_returned_verbatim() -> None:
    reply = "  Happy to help.\n\nWhat should I draft?  "
    assert guard(reply, now=NOW).text == reply


def test_stale_label_on_kept_sentence() -> None:
    old = Source(
        text="Annual plan price is $480.", title="Old price list", updated=date(2025, 11, 1)
    )
    result = guard("The annual plan price is $480.", [old], now=datetime(2026, 3, 1, 12))
    assert not result.changed
    assert result.needs_review
    assert result.stale[0].age_days == 120
    assert "Old price list" in result.labelled_text()


def test_labelled_text_and_audit_record() -> None:
    result = guard("I've sent it. Anything else?", now=NOW)
    assert result.labelled_text().startswith("Anything else?\n\n(Removed a sentence")
    record = result.to_dict()
    json.dumps(record)
    assert record["original"] == "I've sent it. Anything else?"
    removed = record["removed"]
    assert isinstance(removed, list) and removed[0]["rule"] == "unverified_action"


def test_everything_removed_gives_empty_text() -> None:
    result = guard("I've sent it.", now=NOW)
    assert result.text == ""
    assert isinstance(result, GuardResult)


def test_split_sentences_keeps_decimals_files_links_and_abbreviations() -> None:
    text = "Version 3.5 is in notes.md, e.g. see https://example.com/a.b now. Done!"
    assert split_sentences(text) == [
        "Version 3.5 is in notes.md, e.g. see https://example.com/a.b now.",
        "Done!",
    ]
