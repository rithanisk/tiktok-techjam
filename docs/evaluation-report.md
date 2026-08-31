# Evaluation report

Evaluation date: 30–31 August 2026

Dataset: official 200-session public development set

Catalog: official frozen 50,000-product release, SHA-256 `07fd142631fd6b03e2b4d09988c3eb7d53720e9d57010c79db48eeaada50a8f8`

## Default hybrid

- TechnicalScore: 0.877413
- Hit Rate@10: 0.965000
- MRR: 0.766375
- MTTC: 2.750000
- Efficiency: 0.825000
- Reported prompt/completion tokens: 0/0
- Response count: 543

Scenario results:

- Boundary: Hit 1.000000, MRR 0.950000, MTTC 3.100000
- Browsing: Hit 0.975000, MRR 0.779147, MTTC 2.562500
- Buying: Hit 0.962500, MRR 0.757088, MTTC 2.287500
- Intent Override: Hit 0.933333, MRR 0.695873, MTTC 4.366667

## Facet design comparison

- Original progressive portfolio: 0.813553
- Pure facet graph with live-pool entropy: 0.862611
- Pure facet graph with universal question channel: 0.861318
- Hybrid exact-intersection gate: 0.877413

The pure entropy design achieves the highest exact-product recall (0.995) and fastest MTTC (1.875), but lower MRR (0.608704). The hybrid uses a complete strict facet pool only when it contains at most ten products; otherwise it retains the portfolio. That raises MRR to 0.766375 while preserving 0.965 recall.

The entropy policy is catalog-grounded and records a collapse curve, information gain, a branching-factor lower bound, and the expected depth of its own finite greedy tree. Greedy ID3 is not claimed to be universally near-optimal without separability, truthful-answer, equal-cost, and noise assumptions.

## Component ablation

- Official weak baseline: 0.106710
- Stateful single view, no novelty: 0.750401
- Three-view fusion, no novelty: 0.765429
- Progressive three-view portfolio: 0.813553
- Pure facet graph with entropy questions: 0.862611
- Hybrid exact-intersection gate: 0.877413

## Latency context

The dedicated default-hybrid run measured:

- Index build: 4.271830 seconds
- Mean response: 133.907833 ms
- p50: 116.616333 ms
- p95: 331.218750 ms
- p99: 524.282833 ms
- Maximum: 799.452167 ms

These are local measurements, not service-level guarantees.

## Reproduction

```bash
python3 scripts/download_catalog.py
python3 -m unittest discover -v
python3 scripts/benchmark.py --policy competition
python3 scripts/ablation.py
python3 scripts/evaluate_facet_graph.py
```

Machine-readable source results are committed beside this report.

See `docs/facet-graph-evaluation.md` for the controlled hypothesis, initial failure, canonicalization fix, and interpretation limits.
