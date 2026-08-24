#!/usr/bin/env python3
"""Download Kaggle evidence and regenerate local HTML submission reports."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Allow both `python scripts/...` and `python -m scripts...`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.harness.html_reports import (
    ReportSubmission,
    _read_json,
    _records,
    load_local_sources,
    load_remote_submission,
    render_reports,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--local-root", type=Path, action="append", default=[])
    parser.add_argument("--competition", default="kaggriculture")
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--download-only", action="store_true")
    args = parser.parse_args(argv)

    args.reports_dir.mkdir(parents=True, exist_ok=True)
    sources: list[ReportSubmission] = []
    for root in args.local_root:
        sources.extend(load_local_sources(root))
    remote_error: Exception | None = None
    if args.remote:
        try:
            sources.extend(_update_remote(args.competition, args.reports_dir))
        except (OSError, RuntimeError, ValueError) as exc:
            remote_error = exc
            print(f"remote report update failed: {exc}", file=sys.stderr)
            sources.extend(_load_cached_remote(args.reports_dir))

    if not args.download_only:
        if not sources:
            print("no local or remote submission artifacts found", file=sys.stderr)
            return 1 if remote_error is None else 2
        render_reports(_merge_submissions(sources), args.reports_dir)
        print(f"reports updated under {args.reports_dir}")
    return 2 if remote_error is not None else 0


def _update_remote(competition: str, reports_dir: Path) -> list[ReportSubmission]:
    raw_root = reports_dir / "submissions"
    listing = _kaggle_json(
        ["competitions", "submissions", competition, "--format", "json", "--quiet"]
    )
    submissions: list[ReportSubmission] = []
    logs_available = True
    logs_warning_shown = False
    for submission in _records(listing):
        submission_id = _identifier(submission, "submission")
        destination = raw_root / _slug(submission_id) / "raw"
        destination.mkdir(parents=True, exist_ok=True)
        _write_json(destination / "submission.json", submission)
        episodes_data = _kaggle_json(
            ["competitions", "episodes", submission_id, "--format", "json", "--quiet"]
        )
        episodes = _records(episodes_data)
        _write_json(destination / "episodes.json", episodes_data)
        for episode in episodes:
            episode_id = _identifier(episode, "episode")
            episode_dir = destination / _slug(episode_id)
            episode_dir.mkdir(parents=True, exist_ok=True)
            if not _has_json(episode_dir, "replay"):
                _download(
                    ["competitions", "replay", episode_id, "--path", str(episode_dir), "--quiet"]
                )
            if logs_available:
                for agent_index in (0, 1):
                    if not _has_log(episode_dir, agent_index):
                        try:
                            _download(
                                [
                                    "competitions",
                                    "logs",
                                    episode_id,
                                    str(agent_index),
                                    "--path",
                                    str(episode_dir),
                                    "--quiet",
                                ]
                            )
                        except RuntimeError as exc:
                            # Agent logs are useful diagnostics, but Kaggle may
                            # deny this endpoint while still allowing metadata
                            # and replays. Keep the report usable and avoid
                            # repeating the same forbidden request for every
                            # episode in the submission list.
                            logs_available = False
                            if not logs_warning_shown:
                                print(
                                    "warning: Kaggle agent logs are unavailable; "
                                    f"continuing without logs ({exc})",
                                    file=sys.stderr,
                                )
                                logs_warning_shown = True
                            break
        submissions.append(load_remote_submission(submission, episodes, destination))
    return submissions


def _load_cached_remote(reports_dir: Path) -> list[ReportSubmission]:
    result: list[ReportSubmission] = []
    for raw_root in sorted((reports_dir / "submissions").glob("*/raw")):
        submission = _read_json(raw_root / "submission.json")
        episodes_data = _read_json(raw_root / "episodes.json")
        if isinstance(submission, dict):
            result.append(load_remote_submission(submission, _records(episodes_data), raw_root))
    return result


def _kaggle_json(arguments: list[str]) -> Any:
    try:
        completed = subprocess.run(
            ["kaggle", *arguments], check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(detail) from exc
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Kaggle returned non-JSON output for {' '.join(arguments)}") from exc


def _download(arguments: list[str]) -> None:
    try:
        subprocess.run(["kaggle", *arguments], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(detail) from exc


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def _has_json(root: Path, stem: str) -> bool:
    return any(
        path.is_file()
        for pattern in (f"{stem}.json", f"{stem}*.json", f"*-{stem}.json")
        for path in root.glob(pattern)
    )


def _has_log(root: Path, agent_index: int) -> bool:
    return (
        any(path.is_file() and f"{agent_index}" in path.stem for path in root.iterdir())
        if root.is_dir()
        else False
    )


def _identifier(data: dict[str, Any], prefix: str) -> str:
    for key in ("id", "submissionId", "submission_id", "episodeId", "episode_id", "ref"):
        if data.get(key) is not None:
            return str(data[key])
    return f"{prefix}-unknown"


def _slug(value: str) -> str:
    slug = "".join(
        character if character.isalnum() or character in "-_" else "-" for character in value
    )
    return slug.strip("-") or "unknown"


def _merge_submissions(items: list[ReportSubmission]) -> list[ReportSubmission]:
    merged: dict[str, ReportSubmission] = {}
    for item in items:
        current = merged.setdefault(item.submission_id, item)
        if current is not item:
            known = {episode.episode_id for episode in current.episodes}
            current.episodes.extend(
                episode for episode in item.episodes if episode.episode_id not in known
            )
    return list(merged.values())


if __name__ == "__main__":
    raise SystemExit(main())
