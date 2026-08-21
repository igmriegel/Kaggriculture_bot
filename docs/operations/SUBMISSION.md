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

The local host used for initial evidence has no Python 3.14 `pygame` build
dependencies. A temporary Python 3.12 environment with the official wheel was
used instead to complete seed 42 against PASS in 719 turns with zero errors and
fallbacks. This validates the adapter path but does not replace the required
three-scenario matrix under the project runtime.

Reports, development dependencies, local paths, and Graphify artifacts must not
enter the package. Remote Kaggle upload is manual.
