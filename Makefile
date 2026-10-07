# llm-release-gate — stable commands. These names are API: CI and the docs use
# them; change behavior, not names. Everything runs offline (fake provider).

PY ?= python

.PHONY: install test demo-green demo-red demo demo-bound ci clean

install:
	$(PY) -m pip install -e ".[dev]"

test:
	$(PY) -m pytest

# Both green scenarios: a prompt improvement (rag) and a safe cheaper model swap
# (extraction). Expected: exit 0.
demo-green:
	$(PY) -m llm_release_gate gate \
	  --dataset examples/rag-support-bot/dataset.json \
	  --baseline examples/rag-support-bot/baseline.json \
	  --candidate examples/rag-support-bot/candidate.json \
	  --scorers examples/rag-support-bot/scorers.json \
	  --thresholds examples/rag-support-bot/thresholds.json \
	  --pricing examples/pricing.json \
	  --out out/rag-support-bot
	$(PY) -m llm_release_gate gate \
	  --dataset examples/extraction-api/dataset.json \
	  --baseline examples/extraction-api/baseline.json \
	  --candidate examples/extraction-api/candidate.json \
	  --scorers examples/extraction-api/scorers.json \
	  --thresholds examples/extraction-api/thresholds.json \
	  --pricing examples/pricing.json \
	  --out out/extraction-api

# The deliberate regression: cheaper model, worse behavior. The gate MUST exit 1;
# this target fails if the regression is NOT blocked.
demo-red:
	@$(PY) -m llm_release_gate gate \
	  --dataset examples/assistant-cheap-regression/dataset.json \
	  --baseline examples/assistant-cheap-regression/baseline.json \
	  --candidate examples/assistant-cheap-regression/candidate.json \
	  --scorers examples/assistant-cheap-regression/scorers.json \
	  --thresholds examples/assistant-cheap-regression/thresholds.json \
	  --pricing examples/pricing.json \
	  --out out/assistant-cheap-regression; \
	code=$$?; \
	if [ $$code -eq 1 ]; then \
	  echo "OK: regression correctly blocked (exit 1)"; \
	elif [ $$code -eq 0 ]; then \
	  echo "ERROR: the regressing candidate PASSED the gate"; exit 1; \
	else \
	  echo "ERROR: gate did not evaluate (exit $$code)"; exit $$code; \
	fi

demo: demo-green demo-red

demo-bound:
	$(PY) scripts/check_request_binding.py

ci: test demo demo-bound

clean:
	rm -rf out .pytest_cache
