# Testing and verification

## Fast suite

```bash
python3 -m compileall -q submission starter baselines scripts tests
python3 -m unittest discover -v
```

Verified result on 31 August 2026: 65 tests passed. The suite uses temporary synthetic catalogs, so it runs without downloading the 50,000-product release.

## Official public evaluation

```bash
python3 scripts/download_catalog.py
python3 -m evaluator.local_evaluator --output results.json
```

Expected competition-mode aggregate:

```text
sample_count                 200
hit_rate_at_10              0.965000
mrr                         0.766375
mttc                        2.750000
efficiency                  0.825000
recommended_technical_score 0.877413
```

## Ablation

```bash
python3 scripts/ablation.py
```

Expected scores:

- Official weak baseline: 0.106710
- Stateful single view: 0.750401
- Three-view fusion without novelty: 0.765429
- Full progressive portfolio: 0.813553

Facet comparison:

```bash
python3 scripts/evaluate_facet_graph.py
```

- Pure facet graph with entropy questions: 0.862611
- Pure facet graph with universal question channel: 0.861318
- Hybrid exact-intersection gate: 0.877413

## Latency benchmark

```bash
python3 scripts/benchmark.py --policy competition
python3 scripts/benchmark.py --policy adaptive --output docs/adaptive_benchmark_results.json
```

The dedicated hybrid benchmark measured a 4.271830-second build, 133.907833 ms mean response, and 331.218750 ms p95 on the development machine.

## Edge cases covered

- Empty and non-string messages
- Unicode and punctuation/operator-like input
- Duplicate constraints and repeated replies
- Abrupt replacement of an earlier preference
- No preference for a requested attribute
- Query unchanged versus query changed
- Empty lexical query and missing catalog
- Invalid view configuration
- Retrieval timeout injection
- Oversized Top K and out-of-range turn
- Reset-before-respond contract
- Cross-session state leakage
- Session-cap eviction
- Trace filename sanitization and NDJSON validity
- Selectivity-ordered intersections and exact-pool gating
- Empty-conjunction relaxation count and trace contents
- Canonical color labels and non-adjacent category hierarchy tokens
- Numeric budget filtering, grounded entropy prompts, entropy collapse, and computable bounds
- Facet failure fallback to the independent portfolio

## Boundaries not claimed

No finite suite can prove all natural-language edge cases. The repository does not claim private-set performance, adversarial-language completeness, multi-process load capacity, or user-conversion uplift beyond the official simulated metrics. These are stated limitations and proposed future tests rather than hidden assumptions.
