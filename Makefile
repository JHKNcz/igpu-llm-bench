# Reproducible entry points. Run `make check` before committing.
.PHONY: all data figures check scan clean

PYTHON ?= python3

all: data figures check

## Rebuild every derived file from the raw logs.
data:
	$(PYTHON) scripts/parse_logs.py
	$(PYTHON) scripts/roofline.py
	$(PYTHON) scripts/stats.py

## Regenerate the SVG figures.
figures:
	$(PYTHON) scripts/chart.py

## Verify the documents agree with the data, and scan for secrets.
check:
	$(PYTHON) scripts/verify_results.py
	$(PYTHON) scripts/secret_scan.py

scan:
	$(PYTHON) scripts/secret_scan.py

## Remove caches and local run output. Does not touch data/ or docs/.
clean:
	rm -rf runs scripts/__pycache__ __pycache__
	find . -name '*.pyc' -delete
