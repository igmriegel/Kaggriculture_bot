"""Normalize local/Kaggle evidence and render deterministic HTML reports."""

from __future__ import annotations

import json
import re
from collections import Counter
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
    our_agent_name: str | None = None
    opponent_agent_name: str | None = None
    our_action_counts: tuple[tuple[str, int], ...] = ()
    opponent_action_counts: tuple[tuple[str, int], ...] = ()
    our_market_orders: int = 0
    opponent_market_orders: int = 0


@dataclass
class ReportSubmission:
    submission_id: str
    status: str = "unknown"
    submitted_at: str | None = None
    description: str | None = None
    episodes: list[ReportEpisode] = field(default_factory=list)
    source: str | None = None
    excluded_episode_ids: frozenset[str] = frozenset()


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
    submission: dict[str, Any],
    episodes: list[dict[str, Any]],
    raw_root: Path,
    agent_name: str | None = None,
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
    replay_cache: dict[str, dict[str, Any] | None] = {}
    for metadata in episodes:
        episode_id = _identifier(metadata, "episode")
        episode_root = raw_root / _slug(episode_id)
        replay_cache[episode_id] = _first_json(
            episode_root,
            ("replay.json", "replay*.json", "*-replay.json"),
        )
    selected_agent_name = agent_name or _infer_agent_name(replay_cache.values())
    result.excluded_episode_ids = _self_play_episode_ids(replay_cache)
    for metadata in episodes:
        episode_id = _identifier(metadata, "episode")
        episode_root = raw_root / _slug(episode_id)
        replay = replay_cache[episode_id]
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
                agent_name=selected_agent_name,
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
    agent_name: str | None = None,
) -> ReportEpisode:
    raw_steps = replay.get("steps")
    raw_rewards = replay.get("rewards")
    steps: list[Any] = raw_steps if isinstance(raw_steps, list) else []
    rewards: list[Any] = raw_rewards if isinstance(raw_rewards, list) else []
    agent_index = _agent_index(replay, agent_name)
    opponent_index = 1 - agent_index if len(rewards) > 1 else None
    agents = _replay_agents(replay)
    our_agent_name = _agent_display_name(agents[agent_index]) if agent_index < len(agents) else None
    opponent_agent_name = (
        _agent_display_name(agents[opponent_index])
        if opponent_index is not None and opponent_index < len(agents)
        else None
    )
    our_action_counts, our_market_orders = _action_counts(steps, agent_index)
    opponent_action_counts, opponent_market_orders = (
        _action_counts(steps, opponent_index) if opponent_index is not None else ((), 0)
    )
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
        our_agent_name=our_agent_name,
        opponent_agent_name=opponent_agent_name,
        our_action_counts=our_action_counts,
        opponent_action_counts=opponent_action_counts,
        our_market_orders=our_market_orders,
        opponent_market_orders=opponent_market_orders,
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
    episodes = sorted(
        submission.episodes,
        key=lambda item: (not _is_excluded_episode(submission, item), item.episode_id),
    )
    counted_episodes = _counted_episodes(submission)
    counts = _outcome_counts(counted_episodes)
    scored = [episode for episode in counted_episodes if episode.score is not None]
    opponent_scored = [
        episode for episode in counted_episodes if episode.opponent_score is not None
    ]
    decided = counts["submission"] + counts["opponent"] + counts["tie"]
    win_rate = counts["submission"] / decided * 100 if decided else None
    rows = []
    for episode in episodes:
        href = f"episodes/{_slug(episode.episode_id)}.html"
        excluded = _is_excluded_episode(submission, episode)
        result_class = "self-play" if excluded else _result_class(episode.winner)
        result_label = "SELF-PLAY (excluded)" if excluded else _winner_label(episode.winner)
        rows.append(
            f'<tr class="{result_class}">'
            f'<td><a href="{escape(href)}">{escape(episode.episode_id)}</a></td>'
            f"<td>{escape(_display(episode.score))}</td>"
            f"<td>{escape(_display(episode.opponent_score))}</td>"
            f'<td><span class="result-badge {result_class}">{escape(result_label)}</span></td>'
            f"<td>{escape(episode.status)}</td>"
            f"<td>{episode.turns}</td><td>{len(episode.errors)}</td></tr>"
        )
    episode_rows = "".join(rows) or '<tr><td colspan="7">No episodes found</td></tr>'
    summary = (
        '<section class="summary-grid" aria-label="Submission summary">'
        f'<div class="summary-card ours"><span>Our wins</span>'
        f"<strong>{counts['submission']}</strong></div>"
        f'<div class="summary-card tie"><span>Ties</span><strong>{counts["tie"]}</strong></div>'
        f'<div class="summary-card opponent"><span>Opponent wins</span>'
        f"<strong>{counts['opponent']}</strong></div>"
        f'<div class="summary-card neutral"><span>Undecided</span>'
        f"<strong>{counts['unknown']}</strong></div>"
        f'<div class="summary-card neutral"><span>Our win rate</span>'
        f"<strong>{escape(_percent(win_rate))}</strong></div>"
        "</section>"
    )
    return _page(
        f"Submission {submission.submission_id}",
        f'<p><a href="../../index.html">All submissions</a></p>'
        f"<h1>Submission {escape(submission.submission_id)}</h1>"
        f"<p>{escape(submission.description or '')}</p>"
        f"<p>Status: <strong>{escape(submission.status)}</strong>"
        f" · submitted: {escape(submission.submitted_at or '-')}</p>"
        f"{_excluded_note(submission)}"
        f"{summary}"
        f'<p class="record"><strong>Record (our wins–ties–opponent wins):</strong> '
        f"{counts['submission']}–{counts['tie']}–{counts['opponent']} "
        f"· our average: {_display(_average(scored, 'score'))} "
        f"· opponent average: {_display(_average(opponent_scored, 'opponent_score'))}</p>"
        "<table><thead><tr><th>Episode</th><th>Our submission</th><th>Opponent</th>"
        "<th>Result</th><th>Status</th><th>Turns</th><th>Errors</th></tr></thead>"
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
    excluded = _is_excluded_episode(submission, episode)
    result_class = "self-play" if excluded else _result_class(episode.winner)
    result_label = "SELF-PLAY (excluded)" if excluded else _winner_label(episode.winner)
    margin = (
        episode.score - episode.opponent_score
        if episode.score is not None and episode.opponent_score is not None
        else None
    )
    action_summary = _action_summary_html(episode)
    body = (
        f'<p><a href="../index.html">Back to submission</a></p>'
        f"<h1>Episode {escape(episode.episode_id)}</h1>"
        f"<p>Submission: <strong>{escape(submission.submission_id)}</strong>"
        f" · status: <strong>{escape(episode.status)}</strong></p>"
        f'<section class="scoreboard {result_class}" aria-label="Episode score comparison">'
        f'<div class="score-card ours"><span>Our submission</span>'
        f"<strong>{escape(_display(episode.score))}</strong></div>"
        '<div class="versus" aria-hidden="true">vs</div>'
        f'<div class="score-card opponent"><span>Opponent</span>'
        f"<strong>{escape(_display(episode.opponent_score))}</strong></div>"
        f'</section><p class="result-line"><strong>Result:</strong> '
        f'<span class="result-badge {result_class}">{escape(result_label)}</span>'
        f" · turns: {episode.turns}</p>"
        "<h2>Game summary</h2>"
        '<section class="summary-grid replay-summary" aria-label="Game summary">'
        f'<div class="summary-card ours"><span>Our agent</span>'
        f'<strong class="summary-name">{escape(episode.our_agent_name or "-")}</strong></div>'
        f'<div class="summary-card opponent"><span>Opponent</span>'
        f'<strong class="summary-name">{escape(episode.opponent_agent_name or "-")}</strong></div>'
        f'<div class="summary-card neutral"><span>Score margin</span>'
        f"<strong>{escape(_display(margin))}</strong></div>"
        f'<div class="summary-card ours"><span>Our market orders</span>'
        f"<strong>{episode.our_market_orders}</strong></div>"
        f'<div class="summary-card opponent"><span>Opponent market orders</span>'
        f"<strong>{episode.opponent_market_orders}</strong></div>"
        f'<div class="summary-card neutral"><span>Our errors</span>'
        f"<strong>{len(episode.errors)}</strong></div>"
        "</section>"
        f"{action_summary}"
        f"<h2>Errors ({len(episode.errors)})</h2><ul>{error_rows}</ul>"
        f"<details><summary>All moves ({len(episode.moves)} turns)</summary>"
        "<table><thead><tr><th>Turn</th><th>Action</th>"
        f"<th>Error</th></tr></thead><tbody>{move_rows}</tbody></table></details>"
    )
    return _page(f"Episode {episode.episode_id}", body, css_href="../../../assets/style.css")


def _index_html(submissions: list[ReportSubmission]) -> str:
    rows = []
    for submission in submissions:
        episodes = submission.episodes
        counted_episodes = _counted_episodes(submission)
        scores = [episode.score for episode in counted_episodes if episode.score is not None]
        opponent_scores = [
            episode.opponent_score
            for episode in counted_episodes
            if episode.opponent_score is not None
        ]
        counts = _outcome_counts(counted_episodes)
        our_average = sum(scores) / len(scores) if scores else None
        opponent_average = sum(opponent_scores) / len(opponent_scores) if opponent_scores else None
        errors = sum(len(episode.errors) for episode in episodes)
        href = f"submissions/{_slug(submission.submission_id)}/index.html"
        rows.append(
            "<tr>"
            f'<td><a href="{escape(href)}">{escape(submission.submission_id)}</a></td>'
            f"<td>{escape(submission.status)}</td><td>{len(episodes)}</td>"
            f'<td><span class="record-badge">'
            f"{counts['submission']}–{counts['tie']}–{counts['opponent']}"
            "</span></td>"
            f"<td>{escape(_display(our_average))}</td>"
            f"<td>{escape(_display(opponent_average))}</td>"
            f"<td>{errors}</td></tr>"
        )
    submission_rows = "".join(rows) or '<tr><td colspan="7">No submissions found</td></tr>'
    return _page(
        "Submission reports",
        "<h1>Submission reports</h1>"
        "<p>Generated from cached Kaggle and local harness evidence.</p>"
        "<table><thead><tr><th>Submission</th><th>Status</th><th>Episodes</th>"
        "<th>Record W–T–L</th><th>Our avg</th><th>Opponent avg</th><th>Errors</th></tr></thead>"
        f"<tbody>{submission_rows}</tbody></table>",
        css_href="assets/style.css",
    )


def _counted_episodes(submission: ReportSubmission) -> list[ReportEpisode]:
    if not submission.excluded_episode_ids:
        return list(submission.episodes)
    return [
        episode
        for episode in submission.episodes
        if episode.episode_id not in submission.excluded_episode_ids
    ]


def _is_excluded_episode(submission: ReportSubmission, episode: ReportEpisode) -> bool:
    return episode.episode_id in submission.excluded_episode_ids


def _excluded_note(submission: ReportSubmission) -> str:
    if not submission.excluded_episode_ids:
        return ""
    episode_ids = ", ".join(
        escape(episode_id) for episode_id in sorted(submission.excluded_episode_ids)
    )
    return (
        '<p class="notice self-play-note"><strong>Excluded from summary:</strong> '
        f"self-play replay(s) ({episode_ids}) are against our own agent.</p>"
    )


def _outcome_counts(episodes: Iterable[ReportEpisode]) -> dict[str, int]:
    counts = {"submission": 0, "tie": 0, "opponent": 0, "unknown": 0}
    for episode in episodes:
        outcome = episode.winner if episode.winner in counts else "unknown"
        counts[outcome] += 1
    return counts


def _result_class(winner: str | None) -> str:
    return {
        "submission": "ours-win",
        "opponent": "opponent-win",
        "tie": "tie-result",
    }.get(winner, "unknown-result")


def _winner_label(winner: str | None) -> str:
    return {
        "submission": "OUR WIN",
        "opponent": "OPPONENT WIN",
        "tie": "TIE",
    }.get(winner, "UNDECIDED")


def _average(episodes: Iterable[ReportEpisode], field_name: str) -> float | None:
    values = [getattr(episode, field_name) for episode in episodes]
    return sum(values) / len(values) if values else None


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def _action_summary_html(episode: ReportEpisode) -> str:
    return (
        '<section class="action-grid" aria-label="Action summary">'
        f"{_action_table('Our actions', episode.our_action_counts, 'ours')}"
        f"{_action_table('Opponent actions', episode.opponent_action_counts, 'opponent')}"
        "</section>"
    )


def _action_table(title: str, counts: tuple[tuple[str, int], ...], css_class: str) -> str:
    if not counts:
        rows = '<tr><td colspan="2">No actions recorded</td></tr>'
    else:
        rows = "".join(
            f"<tr><td>{escape(label)}</td><td>{count}</td></tr>" for label, count in counts
        )
    return (
        f'<div class="action-panel {css_class}"><h3>{escape(title)}</h3>'
        "<table><thead><tr><th>Command</th><th>Count</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
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


def _infer_agent_name(replays: Iterable[dict[str, Any] | None]) -> str | None:
    """Infer our agent from the name repeated across a submission's replays."""
    counts: Counter[str] = Counter()
    for replay in replays:
        if not isinstance(replay, dict):
            continue
        agents = replay.get("info", {}).get("Agents", [])
        if not isinstance(agents, list):
            continue
        names = {name for agent in agents if (name := _agent_display_name(agent)) is not None}
        counts.update(names)
    return counts.most_common(1)[0][0] if counts else None


def _self_play_episode_ids(
    replays: dict[str, dict[str, Any] | None],
) -> frozenset[str]:
    return frozenset(
        episode_id for episode_id, replay in replays.items() if _is_self_play_replay(replay)
    )


def _is_self_play_replay(replay: dict[str, Any] | None) -> bool:
    if not isinstance(replay, dict):
        return False
    info = replay.get("info")
    agents = info.get("Agents", []) if isinstance(info, dict) else []
    if not isinstance(agents, list):
        return False
    names = [_agent_display_name(agent) for agent in agents]
    names = [name for name in names if name is not None]
    return len(names) >= 2 and len(set(names)) == 1


def _replay_agents(replay: dict[str, Any]) -> list[Any]:
    info = replay.get("info")
    agents = info.get("Agents", []) if isinstance(info, dict) else []
    return agents if isinstance(agents, list) else []


def _action_counts(
    steps: list[Any], agent_index: int | None
) -> tuple[tuple[tuple[str, int], ...], int]:
    if agent_index is None:
        return (), 0
    counts: Counter[str] = Counter()
    market_orders = 0
    for step in steps:
        if not isinstance(step, list) or agent_index >= len(step):
            continue
        record = step[agent_index] if isinstance(step[agent_index], dict) else {}
        action = record.get("action")
        if not isinstance(action, dict):
            continue
        _count_action_values(counts, action.get("farmer"), "farmer")
        _count_action_values(counts, action.get("hands"), "hands")
        market = action.get("market")
        if isinstance(market, list):
            market_orders += len(market)
            _count_action_values(counts, market, "market")
    ordered = tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    return ordered, market_orders


def _count_action_values(counts: Counter[str], values: Any, category: str) -> None:
    if not isinstance(values, list):
        return
    for value in values:
        label = _action_label(value)
        if label:
            counts[f"{category}: {label}"] += 1


def _action_label(value: Any) -> str | None:
    if isinstance(value, list) and value:
        return _text(value[0])
    return _text(value) if isinstance(value, str) else None


def _agent_index(replay: dict[str, Any], agent_name: str | None = None) -> int:
    agents = _replay_agents(replay)
    if agent_name:
        normalized = agent_name.strip().casefold()
        for index, agent in enumerate(agents):
            if (name := _agent_display_name(agent)) is not None and name.casefold() == normalized:
                return index
    for index, agent in enumerate(agents):
        if isinstance(agent, dict) and agent.get("Name") not in {None, "other", "opponent"}:
            return index
    return 0


def _agent_display_name(agent: Any) -> str | None:
    if not isinstance(agent, dict):
        return None
    name = _text(agent.get("Name"))
    return name.strip() if name and name.strip() else None


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
.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(135px,1fr));
gap:.75rem;margin:1.25rem 0}
.summary-card{background:#fff;border:1px solid #d9dee7;border-left:5px solid #8b98a8;
border-radius:.35rem;padding:.8rem 1rem}
.summary-card span,.score-card span{display:block;font-size:.82rem;font-weight:700;
letter-spacing:.04em;text-transform:uppercase;color:#536273}
.summary-card strong{display:block;font-size:1.65rem;margin-top:.2rem}
.summary-card strong.summary-name{font-size:1rem;overflow-wrap:anywhere}
.action-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:1rem}
.action-panel{background:#fff;border:1px solid #d9dee7;border-radius:.35rem;padding:.25rem .75rem}
.action-panel.ours{border-top:4px solid #198754}.action-panel.opponent{border-top:4px solid #dc3545}
.action-panel h3{margin:.65rem 0;color:#16324f}.action-panel table{margin:.5rem 0}
details{margin:1rem 0;background:#fff;border:1px solid #d9dee7;border-radius:.35rem;padding:.75rem}
summary{cursor:pointer;font-weight:700;color:#16324f}
.summary-card.ours,.score-card.ours{border-color:#198754;background:#edf8f1}
.summary-card.opponent,.score-card.opponent{border-color:#dc3545;background:#fff0f1}
.summary-card.tie{border-color:#0d6efd;background:#eef5ff}
.summary-card.neutral{border-color:#8b98a8}
.record,.notice{background:#fff;border:1px solid #d9dee7;border-radius:.35rem;padding:.8rem 1rem}
.notice.self-play-note{border-left:5px solid #6c757d;background:#f1f3f5}
.scoreboard{display:flex;align-items:stretch;gap:.75rem;margin:1.25rem 0}
.score-card{flex:1;border:2px solid #8b98a8;border-radius:.45rem;padding:1rem;
text-align:center;background:#fff}
.score-card strong{display:block;font-size:2rem;margin-top:.25rem}
.versus{align-self:center;font-weight:800;color:#536273}
.result-line{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap}
.result-badge,.record-badge{display:inline-block;border-radius:999px;padding:.2rem .55rem;
font-size:.75rem;font-weight:800;letter-spacing:.03em;white-space:nowrap}
.result-badge.ours-win{background:#198754;color:#fff}.result-badge.opponent-win{background:#dc3545;color:#fff}
.result-badge.tie-result{background:#0d6efd;color:#fff}.result-badge.unknown-result{background:#6c757d;color:#fff}
.result-badge.self-play{background:#6c757d;color:#fff}
tr.ours-win{background:#f2fbf5}tr.opponent-win{background:#fff7f7}tr.tie-result{background:#f5f9ff}
tr.self-play{background:#f1f3f5;color:#536273}
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
