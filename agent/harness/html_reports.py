"""Normalize local/Kaggle evidence and render deterministic HTML reports."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReportMove:
    turn: int
    action: Any
    error: str | None = None


@dataclass(frozen=True)
class ReportEpisode:
    episode_id: str
    score: float | None
    opponent_score: float | None
    status: str
    winner: str | None
    turns: int
    errors: tuple[str, ...] = ()
    moves: tuple[ReportMove, ...] = ()
    source: str | None = None


@dataclass
class ReportSubmission:
    submission_id: str
    status: str = "unknown"
    submitted_at: str | None = None
    description: str | None = None
    episodes: list[ReportEpisode] = field(default_factory=list)
    source: str | None = None


def load_local_sources(root: Path) -> list[ReportSubmission]:
    """Read local harness artifacts without assuming one output layout."""
    if not root.is_dir():
        return []
    benchmark_files = sorted(root.rglob("benchmark.json"))
    episode_files = sorted(root.rglob("episode.json"))
    consumed: set[Path] = set()
    submissions: list[ReportSubmission] = []
    for benchmark_path in benchmark_files:
        data = _read_json(benchmark_path)
        if not isinstance(data, dict):
            continue
        fingerprint = str(data.get("scenario_fingerprint") or benchmark_path.parent.name)
        submission = ReportSubmission(
            submission_id=f"local-{_slug(fingerprint)}",
            status="benchmark",
            description=_scenario_description(data.get("scenario")),
            source=str(benchmark_path),
        )
        embedded = data.get("episodes")
        if isinstance(embedded, list):
            for item in embedded:
                episode = episode_from_local(item, benchmark_path.parent)
                if episode:
                    submission.episodes.append(episode)
                    candidate = benchmark_path.parent / episode.episode_id / "episode.json"
                    consumed.add(candidate)
        for episode_path in sorted(benchmark_path.parent.glob("*/episode.json")):
            if episode_path not in consumed:
                episode = episode_from_local(_read_json(episode_path), episode_path.parent)
                if episode:
                    submission.episodes.append(episode)
                consumed.add(episode_path)
        submissions.append(submission)

    for episode_path in episode_files:
        if episode_path in consumed:
            continue
        episode = episode_from_local(_read_json(episode_path), episode_path.parent)
        if not episode:
            continue
        parent = episode_path.parent.parent
        submission_id = f"local-{_slug(parent.name or episode_path.parent.name)}"
        existing = next((item for item in submissions if item.submission_id == submission_id), None)
        if existing is None:
            existing = ReportSubmission(submission_id=submission_id, source=str(parent))
            submissions.append(existing)
        existing.episodes.append(episode)
    return _deduplicate_submissions(submissions)


def load_remote_submission(
    submission: dict[str, Any], episodes: list[dict[str, Any]], raw_root: Path
) -> ReportSubmission:
    """Build a report model from cached Kaggle metadata and downloaded files."""
    submission_id = _identifier(submission, "submission")
    result = ReportSubmission(
        submission_id=submission_id,
        status=_text(submission.get("status")) or "unknown",
        submitted_at=_text(submission.get("submittedAt") or submission.get("submitted_at")),
        description=_text(submission.get("description") or submission.get("fileName")),
        source=str(raw_root),
    )
    for metadata in episodes:
        episode_id = _identifier(metadata, "episode")
        episode_root = raw_root / _slug(episode_id)
        replay = _first_json(episode_root, ("replay.json", "replay*.json"))
        logs = _log_files(episode_root)
        if replay is None:
            result.episodes.append(
                ReportEpisode(
                    episode_id=episode_id,
                    score=_number(
                        _first_value(metadata, "reward", "score", "publicScore", "privateScore")
                    ),
                    opponent_score=None,
                    status=_text(metadata.get("status")) or "download-missing",
                    winner=_text(metadata.get("winner")),
                    turns=0,
                    errors=("replay.json not found",),
                    source=str(episode_root),
                )
            )
            continue
        result.episodes.append(
            episode_from_replay(
                replay,
                episode_id=episode_id,
                source=str(replay),
                log_text="\n".join(_read_text(path) for path in logs),
                metadata=metadata,
            )
        )
    return result


def episode_from_local(data: Any, episode_root: Path) -> ReportEpisode | None:
    if not isinstance(data, dict):
        return None
    episode_id = _text(data.get("episode_id")) or episode_root.name
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    score = _number(_first_value(result, "money", "score", "reward"))
    moves = _local_moves(data, episode_root)
    errors: list[str] = []
    if data.get("errors"):
        errors.append(f"runner errors: {data['errors']}")
    if data.get("fallbacks"):
        errors.append(f"validation fallbacks: {data['fallbacks']}")
    for move in moves:
        if move.error:
            errors.append(move.error)
    return ReportEpisode(
        episode_id=episode_id,
        score=score,
        opponent_score=None,
        status=_text(data.get("status")) or "unknown",
        winner=_text(result.get("winner")),
        turns=int(data.get("turns") or len(moves)),
        errors=tuple(dict.fromkeys(errors)),
        moves=tuple(moves),
        source=str(episode_root / "episode.json"),
    )


def episode_from_replay(
    replay: dict[str, Any],
    *,
    episode_id: str,
    source: str,
    log_text: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportEpisode:
    raw_steps = replay.get("steps")
    raw_rewards = replay.get("rewards")
    steps: list[Any] = raw_steps if isinstance(raw_steps, list) else []
    rewards: list[Any] = raw_rewards if isinstance(raw_rewards, list) else []
    agent_index = _agent_index(replay)
    opponent_index = 1 - agent_index if len(rewards) > 1 else None
    moves: list[ReportMove] = []
    for turn, step in enumerate(steps):
        if not isinstance(step, list) or agent_index >= len(step):
            continue
        record = step[agent_index] if isinstance(step[agent_index], dict) else {}
        action = record.get("action")
        error = _turn_error(record)
        moves.append(ReportMove(turn=turn, action=action, error=error))
    errors = [line.strip() for line in log_text.splitlines() if _looks_like_error(line)]
    errors.extend(move.error for move in moves if move.error)
    score = _number(rewards[agent_index]) if agent_index < len(rewards) else None
    opponent_score = _number(rewards[opponent_index]) if opponent_index is not None else None
    winner = _winner(score, opponent_score)
    status = _text((metadata or {}).get("status")) or ("complete" if steps else "unknown")
    return ReportEpisode(
        episode_id=episode_id,
        score=score,
        opponent_score=opponent_score,
        status=status,
        winner=winner,
        turns=len(steps),
        errors=tuple(dict.fromkeys(errors)),
        moves=tuple(moves),
        source=source,
    )


def render_reports(submissions: Iterable[ReportSubmission], output_dir: Path) -> None:
    """Write an index, one submission page, and one page per episode."""
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = output_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "style.css").write_text(_CSS, encoding="utf-8")
    ordered = sorted(submissions, key=lambda item: item.submission_id)
    for submission in ordered:
        submission_root = output_dir / "submissions" / _slug(submission.submission_id)
        episodes_root = submission_root / "episodes"
        episodes_root.mkdir(parents=True, exist_ok=True)
        for episode in sorted(submission.episodes, key=lambda item: item.episode_id):
            (episodes_root / f"{_slug(episode.episode_id)}.html").write_text(
                _episode_html(submission, episode), encoding="utf-8"
            )
        (submission_root / "index.html").write_text(_submission_html(submission), encoding="utf-8")
    (output_dir / "index.html").write_text(_index_html(ordered), encoding="utf-8")


def _local_moves(data: dict[str, Any], episode_root: Path) -> list[ReportMove]:
    raw = data.get("turns_log")
    records: list[Any] = raw if isinstance(raw, list) else []
    if not records:
        turns_path = episode_root / "turns.jsonl"
        if turns_path.is_file():
            records = [
                item
                for item in (_read_json_line(line) for line in turns_path.read_text().splitlines())
                if item
            ]
    moves = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        action = record.get("action_sent") or record.get("action_raw")
        error = _text(record.get("exception") or record.get("fallback_reason"))
        moves.append(ReportMove(turn=int(record.get("turn", index)), action=action, error=error))
    return moves


def _submission_html(submission: ReportSubmission) -> str:
    rows = []
    for episode in sorted(submission.episodes, key=lambda item: item.episode_id):
        href = f"episodes/{_slug(episode.episode_id)}.html"
        rows.append(
            "<tr>"
            f'<td><a href="{escape(href)}">{escape(episode.episode_id)}</a></td>'
            f"<td>{escape(_display(episode.score))}</td>"
            f"<td>{escape(_display(episode.opponent_score))}</td>"
            f"<td>{escape(episode.status)}</td><td>{escape(episode.winner or '-')}</td>"
            f"<td>{episode.turns}</td><td>{len(episode.errors)}</td></tr>"
        )
    episode_rows = "".join(rows) or '<tr><td colspan="7">No episodes found</td></tr>'
    return _page(
        f"Submission {submission.submission_id}",
        f'<p><a href="../../index.html">All submissions</a></p>'
        f"<h1>Submission {escape(submission.submission_id)}</h1>"
        f"<p>{escape(submission.description or '')}</p>"
        f"<p>Status: <strong>{escape(submission.status)}</strong>"
        f" · submitted: {escape(submission.submitted_at or '-')}</p>"
        "<table><thead><tr><th>Episode</th><th>Score</th><th>Opponent</th>"
        "<th>Status</th><th>Winner</th><th>Turns</th><th>Errors</th></tr></thead>"
        f"<tbody>{episode_rows}</tbody></table>",
        css_href="../../assets/style.css",
    )


def _episode_html(submission: ReportSubmission, episode: ReportEpisode) -> str:
    errors = "".join(f"<li>{escape(item)}</li>" for item in episode.errors)
    moves = []
    for move in episode.moves:
        moves.append(
            "<tr>"
            f"<td>{move.turn}</td><td><pre>{escape(_json_text(move.action))}</pre></td>"
            f"<td>{escape(move.error or '-')}</td></tr>"
        )
    move_rows = "".join(moves) or '<tr><td colspan="3">No moves recorded</td></tr>'
    error_rows = errors or "<li>None recorded</li>"
    body = (
        f'<p><a href="../index.html">Back to submission</a></p>'
        f"<h1>Episode {escape(episode.episode_id)}</h1>"
        f"<p>Submission: <strong>{escape(submission.submission_id)}</strong>"
        f" · status: <strong>{escape(episode.status)}</strong>"
        f" · winner: {escape(episode.winner or '-')}</p>"
        f"<p>Score: <strong>{escape(_display(episode.score))}</strong>"
        f" · opponent: {escape(_display(episode.opponent_score))}"
        f" · turns: {episode.turns}</p>"
        f"<h2>Errors ({len(episode.errors)})</h2><ul>{error_rows}</ul>"
        "<h2>Moves</h2><table><thead><tr><th>Turn</th><th>Action</th>"
        f"<th>Error</th></tr></thead><tbody>{move_rows}</tbody></table>"
    )
    return _page(f"Episode {episode.episode_id}", body, css_href="../../../assets/style.css")


def _index_html(submissions: list[ReportSubmission]) -> str:
    rows = []
    for submission in submissions:
        episodes = submission.episodes
        scores = [episode.score for episode in episodes if episode.score is not None]
        errors = sum(len(episode.errors) for episode in episodes)
        href = f"submissions/{_slug(submission.submission_id)}/index.html"
        rows.append(
            "<tr>"
            f'<td><a href="{escape(href)}">{escape(submission.submission_id)}</a></td>'
            f"<td>{escape(submission.status)}</td><td>{len(episodes)}</td>"
            f"<td>{escape(_display(sum(scores) / len(scores) if scores else None))}</td>"
            f"<td>{escape(_display(max(scores) if scores else None))}</td><td>{errors}</td></tr>"
        )
    submission_rows = "".join(rows) or '<tr><td colspan="6">No submissions found</td></tr>'
    return _page(
        "Submission reports",
        "<h1>Submission reports</h1>"
        "<p>Generated from cached Kaggle and local harness evidence.</p>"
        "<table><thead><tr><th>Submission</th><th>Status</th><th>Episodes</th>"
        "<th>Average score</th><th>Best score</th><th>Errors</th></tr></thead>"
        f"<tbody>{submission_rows}</tbody></table>",
        css_href="assets/style.css",
    )


def _page(title: str, body: str, *, css_href: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(title)}</title>"
        f'<link rel="stylesheet" href="{escape(css_href)}"></head><body><main>'
        f"{body}</main></body></html>"
    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _first_json(root: Path, patterns: tuple[str, ...]) -> dict[str, Any] | None:
    for pattern in patterns:
        for path in root.glob(pattern):
            data = _read_json(path)
            if isinstance(data, dict):
                return data
    return None


def _log_files(root: Path) -> list[Path]:
    return sorted(path for path in root.glob("*") if path.is_file() and "log" in path.name.lower())


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_json_line(line: str) -> Any:
    try:
        return json.loads(line)
    except ValueError:
        return None


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("data", "results", "submissions", "episodes"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
    return []


def _identifier(data: dict[str, Any], prefix: str) -> str:
    for key in ("id", "submissionId", "submission_id", "episodeId", "episode_id", "ref"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"{prefix}-unknown"


def _agent_index(replay: dict[str, Any]) -> int:
    agents = (
        replay.get("info", {}).get("Agents", []) if isinstance(replay.get("info"), dict) else []
    )
    for index, agent in enumerate(agents):
        if isinstance(agent, dict) and agent.get("Name") not in {None, "other", "opponent"}:
            return index
    return 0


def _turn_error(record: dict[str, Any]) -> str | None:
    for key in ("exception", "error", "fallback_reason"):
        value = _text(record.get(key))
        if value:
            return value
    return None


def _looks_like_error(line: str) -> bool:
    normalized = line.strip().lower()
    if re.search(r"\b(no|0)\s+(error|errors|exception|exceptions)\b", normalized):
        return False
    return bool(re.search(r"\b(error|exception|traceback|fallback|illegal)\b", normalized))


def _winner(score: float | None, opponent_score: float | None) -> str | None:
    if score is None or opponent_score is None:
        return None
    if score > opponent_score:
        return "submission"
    if score < opponent_score:
        return "opponent"
    return "tie"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _text(value: Any) -> str | None:
    return str(value) if value is not None else None


def _display(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}".rstrip("0").rstrip(".")


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    except TypeError:
        return str(value)


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-") or "unknown"


def _scenario_description(value: Any) -> str | None:
    return _json_text(value) if isinstance(value, dict) else _text(value)


def _deduplicate_submissions(items: list[ReportSubmission]) -> list[ReportSubmission]:
    merged: dict[str, ReportSubmission] = {}
    for item in items:
        existing = merged.setdefault(item.submission_id, item)
        if existing is not item:
            known = {episode.episode_id for episode in existing.episodes}
            existing.episodes.extend(
                episode for episode in item.episodes if episode.episode_id not in known
            )
    return list(merged.values())


_CSS = """
body{font-family:system-ui,sans-serif;background:#f6f7f9;color:#20242a;margin:0}
main{max-width:1200px;margin:2rem auto;padding:0 1rem}
table{border-collapse:collapse;width:100%;background:#fff;margin:1rem 0}
th,td{border:1px solid #d9dee7;padding:.55rem;text-align:left;vertical-align:top}
th{background:#eaf0f7}pre{white-space:pre-wrap;margin:0;max-width:58rem}
a{color:#145da0}li{margin:.35rem 0}h1{color:#16324f}p{line-height:1.5}
"""


__all__ = [
    "ReportEpisode",
    "ReportMove",
    "ReportSubmission",
    "episode_from_local",
    "episode_from_replay",
    "load_local_sources",
    "load_remote_submission",
    "render_reports",
]
