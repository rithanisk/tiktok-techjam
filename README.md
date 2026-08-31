# Intent Ledger

**An offline shopping copilot that treats conversation as a changing specification.**

Intent Ledger is a submission-ready solution for TikTok TechJam 2026 Track 4: Shopping Copilot — AI Conversational Search and Recommendations. It converts multi-turn dialogue into auditable intent state, resolves explicit slots through deterministic facet intersections, and retains a high-recall progressive retrieval portfolio for broad or ambiguous requests.

## Verified result

On the official 200-session public evaluator:

- TechnicalScore: **0.877413** versus the official weak baseline's **0.106710**
- Hit Rate@10: **0.965**
- MRR: **0.766375**
- MTTC: **2.750** turns
- Tokens: **0**
- Network calls during inference: **0**
- Index build: about **4.27 seconds** on the development machine
- Mean response latency: about **134 ms**; p95 about **331 ms**

Scenario Hit Rates are 1.000 Boundary, 0.975 Browsing, 0.963 Buying, and 0.933 Intent Override. See [`docs/benchmark_results.json`](docs/benchmark_results.json) for exact output.

These are public-development results. They do not guarantee the private 800-session score or a judging outcome.

## Why it works

The system combines five ideas:

1. **Intent Ledger** — category, hard and soft constraints, no-preference states, provenance, confidence, and superseded values are stored explicitly. Corrections create tombstones rather than destroying history.
2. **Deterministic Facet Graph** — buying slots become posting lists for taxonomy, material, color, brand, budget, and feature values. Lists are intersected from smallest to largest, with no embedding, learned router, or threshold controlling candidate membership.
3. **Bounded Relaxation** — an empty conjunction removes at most three low-confidence soft clauses before hard clauses. Every step records the clause, reason, and before/after pool sizes.
4. **Safe Hybrid Gate** — the exact facet result is used only when the full, unrelaxed intersection contains one to ten products, so the complete pool fits in Top 10. All broad, unresolved, or relaxed requests retain the original progressive three-view portfolio.
5. **Catalog-grounded ID3 Clarification** — the experimental entropy policy selects a non-repeating live facet, reports information gain and an entropy-collapse curve, and computes both an information-theoretic lower bound and the expected depth of its finite greedy tree. The documentation does not claim ID3 is universally near-optimal without additional assumptions.

Every turn also produces a structured flight-recorder event containing the route, active state, question reason, retrieval page, candidate count, latency, and fallback status.

## Quick start

Requirements:

- Python 3.10 or later with SQLite FTS5 enabled
- Approximately 500 MB free disk space for the decompressed catalog
- No third-party Python packages for the scored agent

Clone and prepare:

```bash
git clone <your-repository-url> intent-ledger
cd intent-ledger
python3 scripts/download_catalog.py
```

Run all fast tests:

```bash
python3 -m unittest discover -v
```

Run the official evaluator:

```bash
python3 -m evaluator.local_evaluator --output results.json
```

Expected aggregate score:

```text
TechnicalScore  0.877413
Hit Rate@10     0.965000
MRR             0.766375
MTTC            2.750000
```

## Reproduce all evidence

```bash
make test       # unit, edge-case, contract, and scenario tests
make evaluate   # official metrics
make benchmark  # metrics plus latency percentiles
make ablate     # baseline through full portfolio
make evaluate-facets # pure facet, question-channel, and hybrid comparison
make demo       # changing-intent demonstration
```

The full ablation is:

- Official weak baseline: 0.106710
- Stateful single view: 0.750401
- Three-view fusion: 0.765429
- Progressive retrieval portfolio: 0.813553
- Pure facet graph with entropy questions: 0.862611
- Pure facet graph with universal question channel: 0.861318
- Hybrid exact-intersection gate: 0.877413

Exact scenario results and wall times are committed in [`docs/ablation_results.json`](docs/ablation_results.json) and [`docs/facet_graph_comparison.json`](docs/facet_graph_comparison.json). The design decision, failed literal prototype, correction, and theorem boundary are explained in [`docs/facet-graph-evaluation.md`](docs/facet-graph-evaluation.md).

## Agent interface

The organizer's evaluator continues to import `starter.agent.Agent`. That file is a compatibility wrapper around the actual implementation:

```python
from starter.agent import Agent

agent = Agent("data/catalog.jsonl")
agent.reset("session-1", user_profile={})
response = agent.respond(
    "session-1",
    "I'm looking for running shoes, but I'm still exploring.",
    turn=1,
    top_k=10,
)
```

The response follows the published contract exactly:

```python
{
    "message": "What other requirement or preference matters most?",
    "ask_attribute": "other",
    "recommendations": [{"parent_asin": "..."}],
    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
}
```

## Default and experimental modes

The organizer-facing `starter.agent.Agent` is the hybrid exact-intersection system and reproduces the strongest result:

```bash
python3 -m evaluator.local_evaluator
```

The original portfolio's `adaptive` demo uses concrete, non-repeating questions:

```bash
TECHJAM_POLICY_MODE=adaptive python3 scripts/demo.py
```

The pure facet-entropy agent is measured separately by `make evaluate-facets`; it scores 0.862611 with 0.995 Hit Rate@10 and 1.875 MTTC. The hybrid remains best because exact small intersections improve rank while the portfolio protects broad-query recall.

## Failure behavior

The scored path is deterministic and local. If the facet path raises an exception, the hybrid immediately uses the independently produced portfolio result and records the error. If portfolio retrieval fails, its existing bounded fallback uses the last valid result list or deterministic popularity list. There are no retries, external calls, or unbounded loops.

Session state is isolated by `session_id`, copied on reset, capped with LRU eviction, and excluded from global ranking state. Optional trace files sanitize session names and are disabled unless `TECHJAM_TRACE_DIR` is set.

## Repository map

```text
submission/     ledger, facet graph, hybrid agent, portfolio, policy, and trace helpers
starter/        organizer-compatible entry point
baselines/      frozen weak baseline for ablations
evaluator/      official local evaluator, unchanged
tests/          contract, unit, edge-case, and scenario coverage
scripts/        catalog setup, benchmark, facet comparison, ablation, and demo
docs/           architecture, evidence, threat model, and submission materials
```

## Test scope

The automated suite covers:

- Official evaluator normalization and score semantics
- Buying, Browsing, Intent Override, and Boundary behavior
- Constraint accumulation, deduplication, hardness, provenance, and tombstones
- No-preference closure and non-repeating adaptive questions
- Stable-query pagination and reset on new information
- Selectivity-ordered posting intersections and non-adjacent taxonomy paths
- Canonical labeled facets, numeric budgets, bounded logged relaxation, and safe hybrid gating
- Live-pool entropy, grounded question values, entropy curves, and finite-tree bounds
- Empty input, Unicode, quote/operator-like text, oversized `top_k`, and out-of-range turns
- Missing catalog, empty lexical query, invalid view configuration, and retrieval timeout injection
- Contract shape, valid attributes, unique catalog IDs, zero token reporting, and ten-item cap
- Cross-session isolation, reset determinism, bounded session retention, and trace filename sanitization

See [`docs/testing.md`](docs/testing.md) for commands, expected outputs, and known test boundaries.

## Privacy and security

- No raw user IDs, reviews, timestamps, credentials, or external APIs are used.
- Aggregate profiles are copied per session and are not included in trace output.
- Inference is local and produces zero model tokens.
- User text is tokenized to bounded alphanumeric terms before constructing FTS expressions.
- The catalog is read-only; no products or ASINs are created or mutated.
- Recommendations are always catalog-backed `parent_asin` values.

See [`docs/threat-model.md`](docs/threat-model.md).

## Hackathon compliance

- Headless Python Agent interface: implemented
- At most ten catalog-valid recommendations: enforced
- Maximum ten-turn protocol: supported
- Frozen catalog remains read-only and git-ignored
- No multimodal system, heavy vector database, or foundational-model training
- Works without network during inference
- Model choice, token use, latency, limitations, and fallback behavior disclosed
- Setup, reproduction, architecture, tests, project description, and demo storyboard included

The remaining external submission actions—adding actual team-member names, recording/uploading the public YouTube video, and pasting the repository/video links into Devpost—are listed in [`docs/submission-checklist.md`](docs/submission-checklist.md).

## Limitations

- Public responses are generated from catalog metadata, so lexical retrieval is advantaged relative to natural paraphrased users.
- Progressive pagination improves exact-target coverage but can trade immediate relevance for exploration.
- Greedy facet entropy optimizes catalog uncertainty, not answerability, abandonment, or conversion; it is not universally near-optimal without additional assumptions.
- Intent parsing is deterministic and intentionally conservative; subtle implicit negation may not be tombstoned correctly.
- The public set is development data, not an unseen test set. Private-set generalization remains unknown.

More detail: [`docs/limitations.md`](docs/limitations.md).

## Data and license

The catalog and sessions are derived from Amazon Reviews 2023. See [`DATA_ATTRIBUTION.md`](DATA_ATTRIBUTION.md) and follow the source dataset's applicable terms. The catalog is downloaded separately and never committed.

Original solution code in this repository is released under the MIT License. Organizer-provided evaluator, contract, public data, and documentation retain their applicable terms and attribution.

The original participant-kit repository and base revision are recorded in [`UPSTREAM.md`](UPSTREAM.md).
