# Harness operations

## Commands

```bash
uv run python -m agent.harness smoke --adapter kaggriculture
uv run python -m agent.harness run --agent heuristic --opponent pass --seed 42
uv run python -m agent.harness benchmark --scenario baseline
uv run python -m agent.harness report --input reports/
uv run python -m agent.harness validate-submission --path dist/submission.tar.gz
make reports
make reports-local
```

## Artifact layout

```text
reports/<scenario-fingerprint>/<episode-id>/
  episode.json
  turns.jsonl                 # only when turn logging is enabled
reports/<scenario-fingerprint>/benchmark.json

HTML dashboard output:

```text
reports/index.html
reports/assets/style.css
reports/submissions/<submission-id>/index.html
reports/submissions/<submission-id>/episodes/<episode-id>.html
reports/submissions/<submission-id>/raw/...
```
```

`episode.json` stores version, configuration, status, timings, error counts,
normalized result, and raw environment result. `turns.jsonl` stores one
versioned turn record per line. Do not place reports in a submission package.

## HTML submission reports

`make reports` processes `reports/local/` when present, discovers submissions
from the authenticated Kaggle CLI, downloads each submission's episodes,
replays, and agent logs, and writes a static dashboard to `reports/index.html`.
Each submission has its own `submissions/<id>/index.html`, with linked episode
pages listing scores, actions, and errors or fallbacks. Raw downloads are
cached beside the HTML so later runs are incremental. Use `make reports-local`
without network access and `make reports-download` to refresh only the remote
cache.

The target returns a non-zero status when remote authentication or download
fails, but keeps previous files and renders available local/cache data. Override
`COMPETITION`, `REPORTS_DIR`, or `LOCAL_REPORTS_DIR` for another layout.

The current official adapter uses a `PASS` opponent; `random` and self-play are
integration-test targets once the optional native competition dependency is
available.

## Diagnosis

Read `EpisodeRecord.status`, `fallback_reason`, and `exception` first. Compare
only benchmark reports with the same scenario fingerprint. Re-run with the same
seed and detailed JSONL logging before changing engine behavior.
