# Benchmark data

`data/dev.jsonl` and `data/test.jsonl` hold one agent reply per line. All content is
synthetic: fictional companies and people, `example.com` style domains, 555 phone numbers.

```json
{"id": "d001", "domain": "support", "now": "2026-03-01", "tools_available": false,
 "live_facts": {"payment gateway": "disconnected"},
 "sources": [{"id": "s1", "title": "Refund policy", "text": "...", "updated": "2026-02-20",
              "archived": false}],
 "sentences": [{"text": "...", "label": "supported", "category": "detail", "stale": false}]}
```

* The reply is the `sentences` joined with single spaces. The scorer stops if the guard's
  sentence splitter does not give back exactly those sentences.
* `label`: `unsupported` when the sentence claims an action the agent could not take, gives a
  detail missing from the sources, contradicts a live fact, or states something the sources
  contradict or do not contain. Otherwise `supported`.
* `category`: `action`, `detail`, `live_fact`, `general_claim` or `benign`.
* `stale`: true when a supported sentence states time-sensitive information from a source
  older than 30 days at `now`, or from an archived source.

Run `python benchmark/run.py` from the repository root to score both splits and rewrite
`BENCHMARK.md` and the results table in the top-level README.
