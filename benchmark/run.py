"""Runs claim-guard over the labelled benchmark and writes BENCHMARK.md.

Usage:
    python benchmark/run.py            # print the report and write BENCHMARK.md
    python benchmark/run.py --check    # exit 1 if BENCHMARK.md is out of date

Every number in BENCHMARK.md comes from this script. The data files are JSON Lines, one agent
reply per line, with each sentence labelled "supported" or "unsupported". See
benchmark/README.md for the format.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from claim_guard import Source, guard, split_sentences

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "benchmark" / "data"
REPORT = ROOT / "BENCHMARK.md"
README = ROOT / "README.md"
MARK_START = "<!-- benchmark:start -->"
MARK_END = "<!-- benchmark:end -->"
# The held-out split comes first: its numbers are the headline. The dev split is reported after
# it, labelled as the split the rules were tuned on.
SPLITS = (
    (
        "test",
        "These are the headline numbers. "
        "Held-out split. Written in a separate pass by an author that had the labelling guide "
        "but not the code, and run once after the rules were frozen. One change was made "
        "after freezing: the first run stopped because the sentence splitter read units such "
        'as "42 ms." and "60 F." as abbreviations, so three replies did not split into their '
        "labelled sentences. The splitter was fixed before any guard output on this split was "
        "seen; no rule changed.",
    ),
    (
        "dev",
        "Development split. Written alongside the rules, and the rules were tuned on it, so "
        "these numbers are optimistic. Use the held-out split above to judge the guard.",
    ),
)
TITLES = {
    "test": "Held-out test split (headline)",
    "dev": "Dev split (rules tuned on it, optimistic)",
}
SHORT = {"test": "held-out test (headline)", "dev": "dev (tuned on, optimistic)"}
CATEGORIES = ("action", "detail", "live_fact", "general_claim", "benign")


@dataclass
class Outcome:
    record_id: str
    text: str
    label: str
    category: str
    removed: bool
    rule: str | None
    stale_expected: bool
    stale_flagged: bool


@dataclass
class SplitResult:
    name: str
    description: str
    records: int = 0
    outcomes: list[Outcome] = field(default_factory=list)
    replies_with_errors: int = 0
    replies_with_errors_flagged: int = 0
    clean_replies: int = 0
    clean_replies_untouched: int = 0


def load(path: Path) -> list[dict[str, Any]]:
    """Read one JSON Lines data file."""
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def to_source(raw: dict[str, Any]) -> Source:
    updated = raw.get("updated")
    return Source(
        text=raw["text"],
        title=raw.get("title", ""),
        id=raw.get("id", ""),
        updated=date.fromisoformat(updated) if updated else None,
        archived=bool(raw.get("archived", False)),
    )


def evaluate(name: str, description: str, records: Iterable[dict[str, Any]]) -> SplitResult:
    """Run the guard on every record and compare each sentence with its label."""
    result = SplitResult(name, description)
    for record in records:
        result.records += 1
        sentences = record["sentences"]
        texts = [s["text"] for s in sentences]
        reply = " ".join(texts)
        if split_sentences(reply) != texts:
            raise SystemExit(
                f"{record['id']}: the reply does not split back into its labelled sentences"
            )
        outcome = guard(
            reply,
            [to_source(s) for s in record.get("sources", [])],
            live_facts=record.get("live_facts") or None,
            tools_available=bool(record.get("tools_available", False)),
            now=date.fromisoformat(record["now"]),
        )
        removed = {r.sentence: r.rule for r in outcome.removed}
        flagged = {s for label in outcome.stale for s in label.sentences}
        rows = [
            Outcome(
                record_id=record["id"],
                text=s["text"],
                label=s["label"],
                category=s["category"],
                removed=s["text"] in removed,
                rule=removed.get(s["text"]),
                stale_expected=bool(s.get("stale", False)),
                stale_flagged=s["text"] in flagged,
            )
            for s in sentences
        ]
        result.outcomes.extend(rows)
        if any(r.label == "unsupported" for r in rows):
            result.replies_with_errors += 1
            result.replies_with_errors_flagged += any(r.removed for r in rows)
        else:
            result.clean_replies += 1
            result.clean_replies_untouched += not any(r.removed for r in rows)
    return result


def wilson(hits: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion."""
    if total == 0:
        return (0.0, 0.0)
    p = hits / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def pct(hits: int, total: int) -> str:
    if total == 0:
        return "n/a"
    low, high = wilson(hits, total)
    return f"{100 * hits / total:.1f}% ({hits}/{total}; 95% CI {100 * low:.0f} to {100 * high:.0f})"


def headline(rows: list[Outcome]) -> dict[str, int]:
    tp = sum(r.removed and r.label == "unsupported" for r in rows)
    fp = sum(r.removed and r.label == "supported" for r in rows)
    fn = sum(not r.removed and r.label == "unsupported" for r in rows)
    supported = sum(r.label == "supported" for r in rows)
    return {"tp": tp, "fp": fp, "fn": fn, "supported": supported, "total": len(rows)}


def render(results: list[SplitResult]) -> str:
    """Build the BENCHMARK.md text."""
    out: list[str] = []
    w = out.append
    w("# Benchmark")
    w("")
    w("Generated by `python benchmark/run.py`. Do not edit by hand; a test fails if this file")
    w("and the script disagree.")
    w("")
    w("**Headline: the held-out test split.** The dev split is reported further down and is")
    w("optimistic, because the rules were tuned on it.")
    w("")
    w(summary_table(results))
    w("")
    w("## What is measured")
    w("")
    w("Each record is one agent reply plus what the agent had: its sources, any live status")
    w("facts, and whether it had tools. Every sentence is labelled `supported` or `unsupported`.")
    w("The guard runs once per reply. A removed sentence is a positive prediction.")
    w("")
    w("* **Precision**: of the sentences the guard removed, the share that were unsupported.")
    w("* **Recall**: of the unsupported sentences, the share the guard removed.")
    w("* **False-removal rate**: of the supported sentences, the share the guard removed.")
    w("")
    w("All replies and sources are synthetic: fictional companies, `example.com` domains and")
    w("555 phone numbers. Nothing comes from real users, clients or private notes. The labels")
    w("are one annotator's judgement per split, and the replies were written to resemble model")
    w("output rather than sampled from a live agent, so treat the numbers as a description of")
    w("this set, not a forecast for your traffic.")
    w("")
    for res in results:
        rows = res.outcomes
        h = headline(rows)
        unsupported = h["tp"] + h["fn"]
        w(f"## {TITLES.get(res.name, res.name + ' split')}")
        w("")
        w(res.description)
        w("")
        w(f"{res.records} replies, {h['total']} sentences, {unsupported} labelled unsupported.")
        w("")
        w("| Metric | Value |")
        w("| --- | --- |")
        w(f"| Precision | {pct(h['tp'], h['tp'] + h['fp'])} |")
        w(f"| Recall | {pct(h['tp'], unsupported)} |")
        w(f"| False-removal rate | {pct(h['fp'], h['supported'])} |")
        w(
            "| Replies with an error that were flagged | "
            f"{pct(res.replies_with_errors_flagged, res.replies_with_errors)} |"
        )
        w(
            "| Fully supported replies left untouched | "
            f"{pct(res.clean_replies_untouched, res.clean_replies)} |"
        )
        w("")
        w("Recall and false removals by sentence category:")
        w("")
        w("| Category | Unsupported | Removed | Recall | Supported | Wrongly removed |")
        w("| --- | --- | --- | --- | --- | --- |")
        for cat in CATEGORIES:
            cat_rows = [r for r in rows if r.category == cat]
            un = [r for r in cat_rows if r.label == "unsupported"]
            sup = [r for r in cat_rows if r.label == "supported"]
            caught = sum(r.removed for r in un)
            wrong = sum(r.removed for r in sup)
            recall = f"{100 * caught / len(un):.0f}%" if un else "n/a"
            w(f"| {cat} | {len(un)} | {caught} | {recall} | {len(sup)} | {wrong} |")
        w("")
        rule_counts = Counter(r.rule for r in rows if r.removed)
        rule_right = Counter(r.rule for r in rows if r.removed and r.label == "unsupported")
        w("Removals by rule:")
        w("")
        w("| Rule | Removed | Correct |")
        w("| --- | --- | --- |")
        for rule in ("unverified_action", "contradicts_live_fact", "unsupported_detail"):
            w(f"| {rule} | {rule_counts[rule]} | {rule_right[rule]} |")
        w("")
        expected = [r for r in rows if r.stale_expected and not r.removed]
        flagged = [r for r in rows if r.stale_flagged]
        stale_tp = sum(r.stale_expected for r in flagged)
        w(
            "Stale labels (kept sentences that state time-sensitive facts from a source older "
            "than 30 days or archived):"
        )
        w("")
        w("| Metric | Value |")
        w("| --- | --- |")
        w(f"| Precision | {pct(stale_tp, len(flagged))} |")
        w(f"| Recall | {pct(stale_tp, len(expected))} |")
        w("")
        misses = [r for r in rows if r.label == "unsupported" and not r.removed]
        wrong_removals = [r for r in rows if r.label == "supported" and r.removed]
        w("<details>")
        w(f"<summary>Every miss and wrong removal in the {res.name} split</summary>")
        w("")
        w("Missed (unsupported, kept):")
        w("")
        for r in misses:
            w(f"* `{r.record_id}` [{r.category}] {r.text}")
        if not misses:
            w("* none")
        w("")
        w("Wrongly removed (supported, removed):")
        w("")
        for r in wrong_removals:
            w(f"* `{r.record_id}` [{r.category}, {r.rule}] {r.text}")
        if not wrong_removals:
            w("* none")
        w("")
        w("</details>")
        w("")
    w("## What a pattern-based guard cannot catch")
    w("")
    w("The guard reads surface patterns: action verbs and tense, specific values, status words")
    w("next to a named system, and word overlap with sources. That design needs no model or")
    w("network calls, gives the same answer every time, and is easy to audit. It also sets hard")
    w("limits, and the misses listed above show each of them:")
    w("")
    w('* **Wrong general statements.** "The warranty covers water damage" has no number and')
    w("  no action verb. If a source says the opposite, the guard cannot tell. The")
    w("  `general_claim` row above shows how many of these it missed.")
    w("* **Right value, wrong role.** If the source says Plan A is $20 and Plan B is $35, the")
    w('  sentence "Plan A costs $35" passes, because $35 is in the sources. The guard checks')
    w("  that a value exists, not what it is attached to.")
    w("* **Actions outside the verb list.** First person claims are matched against a fixed")
    w('  list of action verbs, so "I reconnected it" and "I blocked the sender" pass. So do')
    w('  claims with no action verb at all, such as "Seat 12A is yours".')
    w("* **Counts, durations and measurements.** The detail check covers prices, percentages,")
    w('  dates, links, file names, emails and phone numbers. "Within 3 days", "10 MB" and')
    w('  "12 cities" are not checked, and neither are clock times such as "7:40".')
    w("* **Agents with tools.** With `tools_available=True` the guard keeps action claims, since")
    w("  text alone cannot show whether a tool call happened. Checking those claims needs the")
    w("  tool log, compared call by call.")
    w("* **Live facts that are not on/off.** It reads power, lock and door states. A status like")
    w('  "recording" or "68 degrees" is not compared.')
    w("* **Sources that are themselves wrong.** A recent source with a wrong price makes the")
    w("  wrong price look supported.")
    w("")
    w("For those, add a model-based check (an LLM judge or an entailment model) after this")
    w("guard, and keep the guard as the cheap first pass whose removals are easy to explain.")
    w("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if BENCHMARK.md is stale")
    args = parser.parse_args(argv)
    results = [
        evaluate(name, description, load(DATA / f"{name}.jsonl"))
        for name, description in SPLITS
        if (DATA / f"{name}.jsonl").exists()
    ]
    text = render(results)
    readme_now = README.read_text(encoding="utf-8")
    readme_new = with_summary(readme_now, results)
    if args.check:
        current = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
        if current != text or readme_now != readme_new:
            print("BENCHMARK.md or README.md is out of date; run benchmark/run.py", file=sys.stderr)
            return 1
        return 0
    REPORT.write_text(text, encoding="utf-8", newline="\n")
    README.write_text(readme_new, encoding="utf-8", newline="\n")
    print(text)
    return 0


def summary_table(results: list[SplitResult]) -> str:
    """The short results table shown in README.md."""
    lines = [
        "| Split | Replies | Sentences | Precision | Recall | False-removal rate |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for res in results:
        h = headline(res.outcomes)
        removed = h["tp"] + h["fp"]
        unsupported = h["tp"] + h["fn"]
        lines.append(
            f"| {SHORT.get(res.name, res.name)} | {res.records} | {h['total']} "
            f"| {100 * h['tp'] / removed:.1f}% ({h['tp']}/{removed}) "
            f"| {100 * h['tp'] / unsupported:.1f}% ({h['tp']}/{unsupported}) "
            f"| {100 * h['fp'] / h['supported']:.1f}% ({h['fp']}/{h['supported']}) |"
        )
    return "\n".join(lines)


def with_summary(readme: str, results: list[SplitResult]) -> str:
    """Replace the generated block between the README markers with fresh numbers."""
    start = readme.index(MARK_START) + len(MARK_START)
    end = readme.index(MARK_END)
    return readme[:start] + "\n" + summary_table(results) + "\n" + readme[end:]


if __name__ == "__main__":
    raise SystemExit(main())
