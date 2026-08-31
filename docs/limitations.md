# Limitations and future improvements

## Benchmark coupling

The public simulator maps `ask_attribute="other"` to up to two undisclosed constraints of any type. The repository measures both that channel and pure typed facet entropy rather than presenting simulator behavior as natural user behavior.

## Lexical advantage

Public simulator replies are derived from product metadata, so fielded lexical search has unusually strong term overlap. Meaning-preserving paraphrase testing and a character n-gram fallback are the highest-priority generalization improvements.

## Progressive exploration

Pagination raises the probability that an exact hidden target enters Top 10 after earlier misses. In a real store, unexplained deep-page exploration could reduce perceived relevance. A production system should trigger it from calibrated confidence and show diverse explanations.

## Intent parsing

The ledger handles explicit corrections, no-preference answers, and known simulator templates. It can still mishandle implicit replacement, sarcasm, or corrections involving multiple attributes in one sentence. A constrained local parser could improve this without making a hosted LLM mandatory.

## Question value and the ID3 claim

Facet Question ROI uses catalog entropy. It does not estimate whether a person can answer, abandonment probability, or downstream conversion value from real interaction logs. High-cardinality brand can maximize mathematical information gain while being a poor human question.

Greedy ID3 is not universally near-optimal for this problem. Such a theorem would require additional assumptions about truthful/noiseless answers, equal question cost, candidate separability, and the allowed question family. The implementation therefore reports a valid branching-factor lower bound, the exact expected depth of its own constructed finite greedy tree when all leaves resolve, and an unresolved fraction otherwise.

## Hybrid cost

The default agent maintains two in-memory FTS indexes so the facet and portfolio paths fail independently. This improves the public score and fallback isolation but roughly doubles startup memory, raises index construction from about 2.1 to 4.3 seconds, and raises response latency. A production version should share immutable postings while preserving independent decision logic.

## Scale

The in-memory SQLite index is intentionally proportionate to 50,000 products. Millions of frequently changing products would require persistent indexing, incremental updates, and distributed serving, all outside this track's scope.

## With more time

1. Add paraphrased and typo-perturbed development sessions.
2. Add character n-gram retrieval behind a measured confidence gate.
3. Calibrate Question ROI on real interaction outcomes.
4. Add attribute-specific contradiction detection and constraint-violation reranking.
5. Evaluate user effort and recommendation trust with human participants.
6. Package a service adapter while keeping the organizer's Agent interface unchanged.
