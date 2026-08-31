# Threat model and privacy

## Protected assets

- Session messages and inferred constraints
- Aggregate preference profile supplied by the evaluator
- Catalog integrity and exact ASIN namespace
- Deterministic evaluation output
- Local filesystem when optional traces are enabled

## Trust boundaries

- User text is untrusted.
- Catalog and official evaluator inputs are trusted competition artifacts but treated as read-only.
- No network service or model provider is trusted because none is used during inference.
- Trace output is trusted only when the operator explicitly configures its directory.

## Controls

- Bounded alphanumeric tokenization before FTS expression construction
- Maximum 80 unique query terms, ten recommendations, and ten protocol turns
- Session-scoped ledger and retrieval-page state
- Deep-copy of aggregate profiles on reset
- Profiles excluded from trace events
- Sanitized trace filenames
- Deterministic catalog-only recommendation IDs
- LRU cap on retained sessions
- Single bounded fallback with no retry loop
- Catalog file opened read-only by application logic

## Known risks

- Deterministic parsing can misclassify subtle negation or correction scope.
- Optional trace files contain user messages indirectly through constraint values and must be protected by the operator.
- SQLite FTS availability depends on the Python build.
- The Agent is thread-tolerant at the database boundary but not claimed to be a multi-process service.
- Aggregate profiles are retained for the session lifetime even though the current ranking path does not use them.

## Data minimization recommendation

Use the default in-memory trace and destroy the Agent instance after an evaluation job. Enable disk traces only for a controlled demonstration or debugging run, place them outside the repository, and delete them after use.
