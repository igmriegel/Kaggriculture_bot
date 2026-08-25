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


class _ProgressBar:
    def __init__(self, total: int, prefix: str = "Progress", width: int = 30) -> None:
        self.total = max(1, total)
        self.current = 0
        self.prefix = prefix
        self.width = width
        self._is_tty = sys.stderr.isatty()
        self._render()

    def update(self, item_name: str = "") -> None:
        self.current = min(self.total, self.current + 1)
        self._render(item_name)
        if self.current >= self.total:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def _render(self, item_name: str = "") -> None:
        percent = (self.current / self.total) * 100
        filled = int(self.width * self.current // self.total)
        bar = "█" * filled + "░" * (self.width - filled)
        trunc_name = (item_name[:25] + "...") if len(item_name) > 28 else item_name
        text = f"\r{self.prefix} |{bar}| {self.current}/{self.total} ({percent:.1f}%) {trunc_name}"
        if self._is_tty:
            sys.stderr.write(f"{text:<80}")
        else:
            # When piped or in non-tty, print at 10% steps and completion
            if self.current == self.total or self.current % max(1, self.total // 10) == 0:
                sys.stderr.write(f"{self.prefix} [{self.current}/{self.total}] {percent:.0f}%\n")
        sys.stderr.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    parser.add_argument("--local-root", type=Path, action="append", default=[])
    parser.add_argument("--competition", default="kaggriculture")
    parser.add_argument(
        "--agent-name",
        default=None,
        help="Display name of our Kaggle agent; inferred from repeated replay names by default",
    )
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
            sources.extend(_update_remote(args.competition, args.reports_dir, args.agent_name))
        except (OSError, RuntimeError, ValueError) as exc:
            remote_error = exc
            print(f"remote report update failed: {exc}", file=sys.stderr)
            sources.extend(_load_cached_remote(args.reports_dir, args.agent_name))

    if not args.download_only:
        if not sources:
            print("no local or remote submission artifacts found", file=sys.stderr)
            return 1 if remote_error is None else 2
        merged = _merge_submissions(sources)
        total_episodes = sum(len(sub.episodes) for sub in merged)
        print(f"Rendering {len(merged)} submissions ({total_episodes} episode pages)...")
        bar = _ProgressBar(total=total_episodes, prefix="Rendering HTML")
        render_reports(merged, args.reports_dir, on_progress=bar.update)
        print(f"Reports successfully updated under {args.reports_dir}")
    return 2 if remote_error is not None else 0


def _update_remote(
    competition: str, reports_dir: Path, agent_name: str | None = None
) -> list[ReportSubmission]:
    raw_root = reports_dir / "submissions"
    listing = _kaggle_json(
        ["competitions", "submissions", competition, "--format", "json", "--quiet"]
    )
    submissions: list[ReportSubmission] = []
    logs_available = True
    logs_warning_shown = False
    submissions_list = _records(listing)

    # 1. First pass: Collect all pending episodes and check which ones need downloading
    all_submission_episodes: list[tuple[dict[str, Any], Path, list[dict[str, Any]]]] = []
    total_episodes_count = 0
    for submission in submissions_list:
        submission_id = _identifier(submission, "submission")
        destination = raw_root / _slug(submission_id) / "raw"
        destination.mkdir(parents=True, exist_ok=True)
        _write_json(destination / "submission.json", submission)

        # Always fetch latest episodes listing from Kaggle API because completed
        # submissions continue receiving public matches
        episodes_path = destination / "episodes.json"
        episodes_data = _kaggle_json(
            ["competitions", "episodes", submission_id, "--format", "json", "--quiet"]
        )
        _write_json(episodes_path, episodes_data)

        episodes = _records(episodes_data)
        all_submission_episodes.append((submission, destination, episodes))
        total_episodes_count += len(episodes)

    # 2. Download pass with progress bar
    print(
        f"Checking/Downloading {total_episodes_count} episodes "
        f"across {len(submissions_list)} submissions..."
    )
    dl_bar = _ProgressBar(total=max(1, total_episodes_count), prefix="Downloading replays")

    for submission, destination, episodes in all_submission_episodes:
        for episode in episodes:
            episode_id = _identifier(episode, "episode")
            episode_dir = destination / _slug(episode_id)
            episode_dir.mkdir(parents=True, exist_ok=True)

            # Lazy download replay only if not present locally
            if not _has_json(episode_dir, "replay"):
                _download(
                    ["competitions", "replay", episode_id, "--path", str(episode_dir), "--quiet"]
                )

            # Lazy download logs only if not present locally
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
                            logs_available = False
                            if not logs_warning_shown:
                                print(
                                    "warning: Kaggle agent logs are unavailable; "
                                    f"continuing without logs ({exc})",
                                    file=sys.stderr,
                                )
                                logs_warning_shown = True
                            break
            dl_bar.update(f"Ep {episode_id}")

        submissions.append(load_remote_submission(submission, episodes, destination, agent_name))

    return submissions


def _load_cached_remote(reports_dir: Path, agent_name: str | None = None) -> list[ReportSubmission]:
    result: list[ReportSubmission] = []
    for raw_root in sorted((reports_dir / "submissions").glob("*/raw")):
        submission = _read_json(raw_root / "submission.json")
        episodes_data = _read_json(raw_root / "episodes.json")
        if isinstance(submission, dict):
            result.append(
                load_remote_submission(submission, _records(episodes_data), raw_root, agent_name)
            )
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
