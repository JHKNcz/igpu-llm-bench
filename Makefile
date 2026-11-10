# Reproducible entry points. Run `make check` before committing.
.PHONY: all data figures check scan campaign capacity compare clean

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

## Run the full Vulkan campaign at the current memory setting (about 30 min).
## Requires LLAMA_BENCH and MODELS_DIR. Writes to runs/, which is git-ignored.
campaign:
	MODELS_DIR=$(MODELS_DIR) $(PYTHON) scripts/campaign.py --llama-bench "$(LLAMA_BENCH)"

## Probe how many layers a model can offload at the current setting.
## Usage: make capacity LLAMA_BENCH=... MODEL=... LABEL=...
capacity:
	$(PYTHON) scripts/capacity_probe.py --llama-bench "$(LLAMA_BENCH)" \
		--model "$(MODEL)" --label "$(LABEL)"

## Join a Vulkan and a ROCm campaign into a ratio table.
compare:
	$(PYTHON) scripts/compare_backends.py --vulkan $(VULKAN) --rocm $(ROCM) \
		--out data/processed/backend-comparison-512mb.csv

## Remove caches and local run output. Does not touch data/ or docs/.
clean:
	rm -rf runs scripts/__pycache__ __pycache__
	find . -name '*.pyc' -delete
