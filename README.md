# claim-guard

A small Python library that checks an AI agent's reply before anyone sees it and removes the
sentences the agent cannot back up. Every removal keeps the original wording and a reason, so
the decision can be audited later.

Standard library only. No model calls, no network. Python 3.11 or later.

## The problem

A personal assistant running a local 8B model (Qwen3) told its user that a microphone problem
was fixed and the mic was on and listening. The mic was off. It also said a file had been saved
to a folder, though its chat had no tool that could save files. The model had been given the
live mic status and a rule never to claim actions it had not taken, and it ignored both.

Three things made it worse:

* Nothing checked a reply after it was generated.
* Each false reply went back into the conversation history, so the next reply repeated it.
* A confident wrong answer reads exactly like a confident right one.

Prompting alone did not fix it. A check that runs after generation did. The first version of
this guard was built inside that private assistant; across its 84 earlier replies it removed
10 sentences, all of them claims the assistant could not back up and none of them a plain
fact. This package is that guard rebuilt as a general, typed, tested
library with a public benchmark.

## Design

The guard runs after the model and before the reply is saved, shown or spoken. It splits the
reply into sentences and removes a sentence when it:

1. **Claims a completed action the agent could not take.** "I've sent the invoice", "Your
   refund has been processed", "You're all set". If the agent had no tools this turn
   (`tools_available=False`), it could not have done it. Offers, plans, conditionals,
   questions, advice and honest negatives ("I have not sent anything yet") are kept. A
   third-person claim is kept when a source records the same event in the past tense, or when
   the sentence cites a record ("according to the ticket").
2. **Contradicts live status.** `live_facts` holds status read by code at check time, such as
   `{"payment gateway": "disconnected"}`. "The gateway is connected again" is removed. It reads
   power and connection states, locks, and doors.
3. **Gives a specific detail found in no source.** A price, percentage, date, link, file name,
   email or phone number must appear in the supplied sources or live facts. Formats are
   normalised, so "$1,200" matches "1200 USD" and "March 3" matches "2026-03-03".

Kept sentences that state something time-sensitive (a price, date, status, version, deadline)
and draw on a source last updated more than 30 days ago, or an archived one, get a **stale
label** naming the source and its age. The sentence stays; the reader is told to check it.

Choices behind the design:

* **Remove, do not rewrite.** Every kept sentence is the model's own wording, unchanged. The
  audit record is the original text plus a list of removals, each with a rule and a reason.
* **Precision first.** A guard that deletes true sentences gets switched off. The rules are
  narrow on purpose and accept missing some false claims.
* **Deterministic.** Same input, same output, no model in the loop, so a removal can be
  explained by pointing at the pattern that fired.

## Results

The headline numbers come from the **held-out test split**: 100 synthetic agent replies with
each sentence marked supported or unsupported, written by an author who had the labelling
guide but not the code, and run after the rules were frozen (see the commit history). A
smaller dev split, written alongside the rules and used to tune them, is shown second; its
numbers are optimistic. Full tables, confidence intervals, and every miss and wrong removal
are in [BENCHMARK.md](BENCHMARK.md). This table is written by `benchmark/run.py`:

<!-- benchmark:start -->
| Split | Replies | Sentences | Precision | Recall | False-removal rate |
| --- | --- | --- | --- | --- | --- |
| held-out test (headline) | 100 | 515 | 98.3% (57/58) | 35.6% (57/160) | 0.3% (1/355) |
| dev (tuned on, optimistic) | 62 | 171 | 100.0% (45/45) | 67.2% (45/67) | 0.0% (0/104) |
<!-- benchmark:end -->

What that means: when the guard removes a sentence it is almost always right, and it rarely
touches a true sentence. Recall is the weak side. On the held-out split it misses most
unsupported sentences, and the per-category table in BENCHMARK.md shows where: false action
claims are caught best, and wrong general statements almost never, because they have no
pattern to match. The dev split scores higher on recall because the rules were tuned on it;
the test split is the number to trust.

## Limits

* **Wrong general statements pass.** "The warranty covers water damage" has no number and no
  action verb; if the source says the opposite, the guard cannot tell.
* **Right value, wrong role passes.** If the source says Plan A is $20 and Plan B is $35,
  "Plan A costs $35" passes because $35 is in the sources.
* **The action verb list is closed.** "I reconnected it" and "Seat 12A is yours" pass.
* **Counts, durations and clock times are not checked** ("within 3 days", "10 MB", "7:40").
* **With tools, action claims are kept.** Checking them needs the tool log, not the text.
* **A wrong source makes a wrong detail look supported.**

Use it as the cheap first pass, and put a model-based check (an LLM judge or an entailment
model) behind it for the general statements it cannot read.

## Usage

```python
from datetime import date
from claim_guard import Source, guard

order = Source(title="Order 4411", text="Order 4411 shipped on 2026-02-24. Arrives 2026-03-03.")
reply = "Your order shipped on February 24. I've upgraded it to express. It now arrives March 1."
result = guard(reply, [order], live_facts={"payment gateway": "offline"}, now=date(2026, 3, 1))
print(result.text)  # -> Your order shipped on February 24.
for removal in result.removed:
    print(removal.rule, removal.reason)
audit = result.to_dict()  # original text, kept text, removals and stale labels, ready for JSON
```

`guard(reply, sources, live_facts=None, tools_available=False, now=None)` returns a
`GuardResult` with `text` (kept sentences, nothing added), `original`, `removed` (each with
`sentence`, `rule`, `reason`, `evidence`), `stale` labels, and `labelled_text()`, which appends
a short plain-language note for each removal type and stale source. Pass the user's own message
as a source if details they gave should count as supported.

## Development

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\ruff check .
.venv\Scripts\mypy
.venv\Scripts\python -m pytest
.venv\Scripts\python benchmark\run.py
```

A test fails if `BENCHMARK.md` or the table above no longer matches what the script produces.

Layout: `src/claim_guard` (the library), `tests` (unit tests), `benchmark/data` (labelled
replies, JSON Lines), `benchmark/run.py` (scoring and report).

## License

MIT. See [LICENSE](LICENSE).
