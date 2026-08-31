# Contributing

1. Create a focused branch.
2. Keep the official evaluator and public labels unchanged.
3. Add or update tests for every behavior change.
4. Run `python3 -m unittest discover -v`.
5. If retrieval changes, run `python3 scripts/ablation.py` and explain metric movement.
6. Do not commit the catalog, credentials, private data, or generated traces.

Changes should preserve the organizer's Agent contract and the deterministic offline fallback.
