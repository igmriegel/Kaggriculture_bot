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
uv run --group competition python -m agent.harness benchmark --scenario leader-v2-pass-development
uv run --group competition python -m agent.harness benchmark --scenario leader-v2-random-development
uv run --group competition python -m agent.harness benchmark --scenario leader-v2-competitive-development

# Repeat the same matrix on unseen seeds 41..80 before promotion.
uv run --group competition python -m agent.harness benchmark --scenario leader-v2-pass-confirmation
uv run --group competition python -m agent.harness benchmark --scenario leader-v2-random-confirmation
uv run --group competition python -m agent.harness benchmark --scenario leader-v2-competitive-confirmation
```

Capture one explicit-seed local episode with its summary and turn log before
the matrix. The local harness currently emits JSON/JSONL evidence; the remote
simulation episode is the replay artifact.

```bash
uv run --group competition python -m agent.harness run \
  --adapter kaggriculture --agent leader-v2 --opponent pass \
  --seed 42 --max-turns 720 --output reports/local --log-turns
```

The local host used for initial evidence has no Python 3.11 `pygame` build
dependencies. A temporary Python 3.12 environment with the official wheel was
used instead to complete seed 42 against PASS in 719 turns with zero errors and
fallbacks. This validates the adapter path but does not replace the required
three-scenario matrix under Python 3.11.

Reports, development dependencies, local paths, and Graphify artifacts must not
enter the package.

After a local run or remote submission, update the audit dashboard with
`make reports`. The dashboard is generated outside the submission archive and
keeps raw replay/log downloads under `reports/submissions/` so scores and
turn-level actions can be reviewed without changing the runtime package.

## Submission lifecycle

1. Generate the archive and run the isolated package check above. Confirm that
   `main.py` is at the archive root and every runtime file parses under Python
   3.11.
2. Run a local Kaggriculture episode with an explicit seed and save its JSON
   summary and JSONL turn log; then run the full fixed PASS, random, and
   self-play matrix through the 720-turn horizon. The corresponding remote
   simulation episode supplies the Kaggle replay.
3. Upload with the Kaggle competition workflow. Record the submitted archive
   checksum, submission timestamp, returned submission ID, and source commit
   with the report:

   ```bash
   kaggle competitions submit kaggriculture \
     --file dist/kaggriculture-submission.tar.gz \
     --message "<source commit and engine version>"
   ```

4. Check remote status, list episodes for the returned submission ID, and
   download each replay and both agents’ logs:

   ```bash
   kaggle competitions submissions kaggriculture --format json
   kaggle competitions episodes <submission_id> --format json
   kaggle competitions replay <episode_id> --path reports/kaggle/<episode_id>
   kaggle competitions logs <episode_id> 0 --path reports/kaggle/<episode_id>
   kaggle competitions logs <episode_id> 1 --path reports/kaggle/<episode_id>
   ```

   Persist submission/episode IDs and downloaded-file checksums alongside the
   report. The returned API metadata and replay/log contents are authoritative
   when they differ from local assumptions.
5. Review the leaderboard only after submission status is complete:

   ```bash
   kaggle competitions leaderboard kaggriculture --show --format json
   ```

   Correlate the result with its submission ID, replay, logs, scenario evidence,
   and source commit. A leaderboard result alone is not a promotion.
