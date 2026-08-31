# Devpost project description draft

## Inspiration

Shopping rarely stays inside one query. People begin vaguely, reveal constraints gradually, change their minds, and sometimes have no preference at all. Conventional conversational search often concatenates the entire transcript, allowing obsolete preferences to contaminate ranking and returning the same candidates after every miss.

## What it does

Intent Ledger converts conversation into an explicit changing specification. It records active requirements, provenance, confidence, no-preference states, and tombstones for replaced preferences. A deterministic facet graph intersects explicit slot posting lists from most selective to least selective, with bounded logged relaxation. A safe gate uses the complete facet pool only when the unrelaxed conjunction contains at most ten products; broader requests retain a progressive three-view retrieval portfolio. A catalog-grounded entropy controller can ask the live facet expected to reduce uncertainty most.

## How we built it

- Python 3.10+ standard library
- SQLite FTS5 in memory
- Deterministic intent parsing and session state
- Reciprocal-rank fusion across field-weighted retrieval views
- Selectivity-ordered facet posting intersections and numeric budget filters
- ID3-style live-pool entropy, entropy-collapse traces, and finite-tree depth analysis
- Official local evaluator for Hit Rate@10, MRR, MTTC, and TechnicalScore
- `unittest` for contract, edge-case, scenario, failure, and isolation coverage

No external model API, vector database, hosted service, or credential is required. The scored path reports zero model tokens and works offline.

## Results

On the official 200-session public set, Intent Ledger achieved TechnicalScore 0.877413, Hit Rate@10 0.965, MRR 0.766375, and MTTC 2.750, compared with the official weak baseline's 0.106710 score. The original progressive portfolio scored 0.813553, the pure facet-entropy design scored 0.862611, and the conservative hybrid scored 0.877413.

## Challenges

Literal facet phrases initially created false precision: `Women Leggings` did not match an intervening taxonomy node, and `color: red` did not match a plain `red` value. Canonical slot semantics fixed both. We also found that raw entropy selects high-cardinality brand values even when answerability is uncertain, so we report the constructed tree's evidence without claiming universal ID3 optimality.

## Accomplishments

- 8.22 times the official baseline TechnicalScore
- 96.5% exact-product Hit Rate@10
- Offline deterministic inference with zero model tokens
- Explicit correction and boundary semantics
- Scenario-level metrics, ablations, latency measurements, failure injection, and reproducible traces

## What we learned

In this task, disciplined state and retrieval engineering mattered more than adding a large model. Exact intersections are excellent precision tools but unsafe as a universal retriever; using them only when the entire strict pool fits in Top 10 preserves the portfolio's recall. Entropy is compelling evidence, but answerability and separability assumptions must be stated.

## What's next

We would add paraphrase-robust character n-gram retrieval, calibrate question value on real user behavior, strengthen clause-level contradiction parsing, and run human studies on effort and trust.

## Links to complete before submission

- Public repository: `<PUBLIC_REPOSITORY_URL>`
- Public YouTube demo: `<YOUTUBE_URL>`
