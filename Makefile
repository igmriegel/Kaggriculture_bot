PYTHON ?= uv run python
COMPETITION ?= kaggriculture
AGENT_NAME ?=
REPORTS_DIR ?= reports
LOCAL_REPORTS_DIR ?= reports/local

.PHONY: reports reports-local reports-download

reports:
	$(PYTHON) -m scripts.update_submission_reports --reports-dir "$(REPORTS_DIR)" --local-root "$(LOCAL_REPORTS_DIR)" --competition "$(COMPETITION)" --agent-name "$(AGENT_NAME)" --remote

reports-local:
	$(PYTHON) -m scripts.update_submission_reports --reports-dir "$(REPORTS_DIR)" --local-root "$(LOCAL_REPORTS_DIR)"

reports-download:
	$(PYTHON) -m scripts.update_submission_reports --reports-dir "$(REPORTS_DIR)" --competition "$(COMPETITION)" --agent-name "$(AGENT_NAME)" --remote --download-only

.PHONY: benchmarks
benchmarks:
	$(PYTHON) scripts/run_benchmarks.py
