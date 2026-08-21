# Submission

A submission contains `main.py` at the package root and only runtime assets.
Build and isolate-check it with:

```bash
uv run python -m agent.harness package-submission --output dist/kaggriculture-submission.tar.gz
uv run python -m agent.harness validate-submission --path dist/kaggriculture-submission.tar.gz
```

Run the fixed evidence matrix once the optional environment is available:

```bash
uv run --group competition python -m agent.harness benchmark --scenario v1-pass
uv run --group competition python -m agent.harness benchmark --scenario v1-random
uv run --group competition python -m agent.harness benchmark --scenario v1-self-play
```

Reports, development dependencies, local paths, and Graphify artifacts must not
enter the package. Remote Kaggle upload is manual.
