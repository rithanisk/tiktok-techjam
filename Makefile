.PHONY: catalog test evaluate benchmark ablate evaluate-facets demo check

catalog:
	python3 scripts/download_catalog.py

test:
	python3 -m unittest discover -v

evaluate:
	python3 -m evaluator.local_evaluator --output results.json

benchmark:
	python3 scripts/benchmark.py

ablate:
	python3 scripts/ablation.py

evaluate-facets:
	python3 scripts/evaluate_facet_graph.py

demo:
	python3 scripts/demo.py --policy adaptive

check: test evaluate
