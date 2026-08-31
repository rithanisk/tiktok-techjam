# Judging criteria evidence map

This document maps the submission to the published criteria. It provides evidence; it does not claim or guarantee a judging result.

## Technical Execution — 35%

- Official public-set TechnicalScore: 0.877413
- Exact-product Hit Rate@10: 0.965
- Scenario-specific results for Buying, Browsing, Intent Override, and Boundary
- Component ablation from official baseline through the full portfolio
- 65 automated contract, unit, facet, edge-case, failure, isolation, and scenario tests
- Deterministic offline inference with zero model tokens
- Bounded fallback and per-turn flight-recorder trace
- Organizer-compatible `starter.agent.Agent` entry point

Evidence:

- `docs/benchmark_results.json`
- `docs/ablation_results.json`
- `tests/`
- `submission/`

## Innovation and Problem Insight — 20%

- Frames shopping dialogue as a changing specification rather than transcript concatenation
- Uses tombstoned constraints to preserve provenance while removing stale intent
- Connects progressive candidate exploration to canonical intent changes
- Separates evaluator-reproducible and natural adaptive-question modes, openly documenting simulator sensitivity
- Includes negative evidence: fusion without novelty and adaptive typed questions do not automatically improve the composite score
- Deterministic selectivity-ordered facet intersections with bounded, inspectable relaxation
- Live-pool entropy-collapse evidence plus rigorous limits on the ID3 optimality claim
- Safe hybrid gate improves the original portfolio from 0.813553 to 0.877413

Evidence:

- `docs/architecture.md`
- `docs/limitations.md`
- `docs/ablation_results.json`

## Impact and Relevance — 20%

- Addresses concrete user failures: vague beginnings, accumulating requirements, changed minds, no-preference answers, and repeated results
- Directly optimizes exact product discovery and turns to conversion
- Recommendation IDs always come from the frozen catalog
- Adaptive mode avoids repeating closed or previously asked attributes

Evidence:

- `scripts/demo.py`
- `tests/test_scenarios.py`
- `docs/demo-script.md`

## Feasibility and Practicality — 15%

- Python standard-library scored path
- No hosted service, API key, vector database, or model download
- Approximately 4.27-second local dual-index construction
- Measured latency percentiles and zero token cost
- Clean-clone catalog download with SHA-256 and row-count verification
- CI configuration runs all catalog-independent tests
- Read-only catalog and explicit privacy/threat model

Evidence:

- `requirements.txt`
- `scripts/download_catalog.py`
- `.github/workflows/test.yml`
- `docs/threat-model.md`

## Presentation and Communication — 10%

- Concise product line: “Shopping is not one query. It is a changing specification.”
- Three-minute demo storyboard with problem, live session, evidence, robustness, and close
- Devpost project-description draft
- Architecture diagram, repository map, exact reproduction commands, limitations, and submission checklist

Evidence:

- `README.md`
- `docs/demo-script.md`
- `docs/project-description.md`
- `docs/submission-checklist.md`

## Honest boundaries

- The 200 public sessions are development data, not an unseen evaluation set.
- The private 800-session result is unknown.
- `ask_attribute="other"` is unusually powerful under the deterministic simulator.
- The public result and repository quality cannot guarantee finalist selection or a prize.
