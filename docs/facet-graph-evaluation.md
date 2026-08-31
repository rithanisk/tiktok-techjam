# Facet-graph idea evaluation

## Question tested

Would explicit slot parsing, selectivity-ordered posting-list intersection, bounded relaxation, and live-pool ID3 clarification outperform the original progressive three-view retrieval portfolio?

## Implemented variants

1. **Original portfolio** — three FTS5 views, reciprocal-rank fusion, and progressive pagination.
2. **Pure facet + entropy** — explicit posting lists, strict conjunction, bounded relaxation, and a typed question chosen from live-pool information gain.
3. **Pure facet + universal channel** — identical retrieval with the public evaluator's `other` question channel, isolating the retrieval effect.
4. **Hybrid exact intersection** — run both retrievers, but accept facets only when the original conjunction required no relaxation and its complete pool contains one to ten products.

All four variants used the same frozen 50,000-product catalog and official 200-session public evaluator. Reproduce with:

```bash
python3 scripts/evaluate_facet_graph.py
```

## Results

| Variant | Score | Hit@10 | MRR | MTTC |
| --- | ---: | ---: | ---: | ---: |
| Original portfolio | 0.813553 | 0.960 | 0.583510 | 3.075 |
| Pure facet + entropy | 0.862611 | 0.995 | 0.608704 | 1.875 |
| Pure facet + `other` | 0.861318 | 0.980 | 0.625726 | 1.820 |
| Hybrid exact intersection | **0.877413** | 0.965 | **0.766375** | 2.750 |

The pure proposal is better than the original. It has excellent recall and reaches targets quickly. The hybrid is better still because it uses facets for high-precision small pools and retains portfolio recall for broad or ambiguous pools.

## Important implementation finding

An initial literal prototype scored only 0.772999 in pure entropy form and 0.793753 with the universal question channel. The failure was false precision, not weak facet retrieval:

- `Women Leggings` was treated as an adjacent phrase even though the taxonomy path contained an intervening node.
- `color: red` was treated as a literal phrase even though the catalog could store only `red`.

Canonicalizing controlled values and interpreting category slots as ANDed taxonomy postings corrected the semantics. Regression tests preserve both cases.

## Clarification evidence

For a live candidate pool, each allowed attribute partitions product IDs by observed catalog value. With a uniform target prior, the ID3 information gain of that question equals the Shannon entropy of its answer distribution. The trace reports:

- candidate entropy before the question;
- selected attribute and observed top values;
- information gain in bits;
- expected remaining candidates after one answer;
- a two-point entropy-collapse curve;
- a branching-factor information lower bound;
- the exact expected depth of the finite greedy tree when all leaves resolve;
- the unresolved candidate fraction otherwise.

The question text uses only values observed in the live pool, so it cannot invent a facet option.

## Why “provably near-optimal” is too strong

Greedy ID3 is not universally near-optimal for conversational shopping. A proof needs assumptions about the question family, equal costs, truthful and noiseless answers, candidate separability, and the objective. Catalog entropy also ignores whether a shopper knows or cares about a facet; raw ID3 often favors high-cardinality brand.

The defensible claim is narrower: the implementation has a computable information lower bound and an exact expected depth for its own finite greedy tree when that tree resolves every leaf to Top 10. This gives judges an inspectable algorithmic story without making a theorem the implementation cannot support.

## Tradeoffs

- The dedicated hybrid benchmark built both indexes in 4.27 seconds and measured 134 ms mean / 331 ms p95 response latency on the development machine.
- Independent indexes roughly double memory, but allow the portfolio to remain a true failure fallback.
- Public metadata-derived replies have unusually high lexical overlap; private and paraphrased performance remain unknown.
- The public set is development evidence, not an unseen generalization guarantee.

Machine-readable results are in `docs/facet_graph_comparison.json` and `docs/benchmark_results.json`.
