# Harness operations

## Commands

```bash
uv run python -m agent.harness smoke --adapter kaggriculture
uv run python -m agent.harness run --agent heuristic --opponent random --seed 42
uv run python -m agent.harness benchmark --scenario baseline
uv run python -m agent.harness report --input reports/
uv run python -m agent.harness validate-submission --path dist/submission.tar.gz
```

## Artifact layout

```text
reports/<scenario-fingerprint>/<episode-id>/
  episode.json
  turns.jsonl                 # only when turn logging is enabled
reports/<scenario-fingerprint>/benchmark.json
```

`episode.json` stores version, configuration, status, timings, error counts,
normalized result, and raw environment result. `turns.jsonl` stores one
versioned turn record per line. Do not place reports in a submission package.

## Diagnosis

Read `EpisodeRecord.status`, `fallback_reason`, and `exception` first. Compare
only benchmark reports with the same scenario fingerprint. Re-run with the same
seed and detailed JSONL logging before changing engine behavior.
