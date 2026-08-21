# Submission

A submission contains `main.py` at the package root and only runtime assets.
The Kaggle simulation runtime currently uses Python 3.11, so every packaged
runtime module must remain parseable by Python 3.11. Local development targets
the same minimum version.
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

The local host used for initial evidence has no Python 3.11 `pygame` build
dependencies. A temporary Python 3.12 environment with the official wheel was
used instead to complete seed 42 against PASS in 719 turns with zero errors and
fallbacks. This validates the adapter path but does not replace the required
three-scenario matrix under Python 3.11.

Reports, development dependencies, local paths, and Graphify artifacts must not
enter the package. Remote Kaggle upload is manual.
