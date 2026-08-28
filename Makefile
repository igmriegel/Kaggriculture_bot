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
	PYTHONPATH=. $(PYTHON) scripts/run_benchmarks.py -n $(or $(N),30)

.PHONY: summarize
summarize:
	PYTHONPATH=. $(PYTHON) scripts/summarize_replay.py $(FILE)

.PHONY: package
package:
	$(PYTHON) -m agent.harness package-submission --output dist/submission.tar.gz
	$(PYTHON) -m agent.harness validate-submission --path dist/submission.tar.gz

.PHONY: submit
submit: package
	kaggle competitions submit -c $(COMPETITION) -f dist/submission.tar.gz -m "$(or $(MSG),feat: automated submit)"

.PHONY: optimize-v10
optimize-v10:
	PYTHONPATH=. $(PYTHON) scripts/optimize_v10.py

.PHONY: kaggle-build
kaggle-build:
	uv build

.PHONY: kaggle-deploy-code
kaggle-deploy-code: kaggle-build
	rm -rf kaggle_dataset/dist kaggle_dataset/scripts kaggle_dataset/agent
	mkdir -p kaggle_dataset/dist kaggle_dataset/scripts
	cp dist/*.whl kaggle_dataset/
	cp scripts/kaggle_runner.py kaggle_dataset/scripts/
	cp scripts/optimize_v10.py kaggle_dataset/scripts/
	cp -r agent kaggle_dataset/
	# Try to create dataset first, if exists, update it as a new version
	kaggle datasets version -p kaggle_dataset/ -m "Update code wheel and runners" || kaggle datasets create -p kaggle_dataset/ -u

.PHONY: kaggle-run
kaggle-run:
	kaggle kernels push -p kaggle_kernel/

.PHONY: kaggle-status
kaggle-status:
	kaggle kernels status igmriegel/kaggriculture-optimization

.PHONY: kaggle-retrieve
kaggle-retrieve:
	mkdir -p reports/kaggle
	kaggle kernels output igmriegel/kaggriculture-optimization -p reports/kaggle/
