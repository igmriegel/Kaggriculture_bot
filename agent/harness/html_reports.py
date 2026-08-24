"""Normalize local/Kaggle evidence and render deterministic HTML reports with rich KPIs."""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

from agent.analysis.action_metrics import classify_action, inferred_fallback, summarize_turns


@dataclass(frozen=True)
class ReportMove:
    turn: int
    action: Any
    error: str | None = None
    action_class: str = "idle_pass"


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
    metrics: dict[str, Any] = field(default_factory=dict)


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
    raw_result = data.get("raw_result") if isinstance(data.get("raw_result"), dict) else {}
    rewards = result.get("rewards") or raw_result.get("rewards")
    score = _number(_first_value(result, "money", "score", "reward"))
    opponent_score = None
    if isinstance(rewards, list) and len(rewards) > 1:
        if score is None:
            score = _number(rewards[0])
        opponent_score = _number(rewards[1])

    our_agent_name = _text(data.get("agent")) or "Our agent"
    opponent_agent_name = _text(data.get("opponent")) or "Opponent"

    moves = _local_moves(data, episode_root)
    errors: list[str] = []
    if data.get("errors"):
        errors.append(f"runner errors: {data['errors']}")
    if data.get("fallbacks"):
        errors.append(f"validation fallbacks: {data['fallbacks']}")
    for move in moves:
        if move.error:
            errors.append(move.error)

    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    action_counts_raw = metrics.get("action_counts", {})
    our_action_counts = (
        tuple(sorted(action_counts_raw.items(), key=lambda x: -x[1]))
        if isinstance(action_counts_raw, dict)
        else ()
    )
    our_market_orders = sum(
        count
        for name, count in our_action_counts
        if name in {"BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT", "SELL", "HIRE", "BUY_LAND"}
    )

    winner = (
        _winner(score, opponent_score)
        if opponent_score is not None
        else _text(result.get("winner"))
    )
    return ReportEpisode(
        episode_id=episode_id,
        score=score,
        opponent_score=opponent_score,
        status=_text(data.get("status")) or "unknown",
        winner=winner,
        turns=int(data.get("turns") or len(moves)),
        errors=tuple(dict.fromkeys(errors)),
        moves=tuple(moves),
        source=str(episode_root / "episode.json"),
        our_agent_name=our_agent_name,
        opponent_agent_name=opponent_agent_name,
        our_action_counts=our_action_counts,
        opponent_action_counts=(),
        our_market_orders=our_market_orders,
        opponent_market_orders=0,
        metrics=_local_metrics(data, moves),
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
    evidence: list[dict[str, Any]] = []
    for turn, step in enumerate(steps):
        if not isinstance(step, list) or agent_index >= len(step):
            continue
        record = step[agent_index] if isinstance(step[agent_index], dict) else {}
        action = record.get("action")
        error = _turn_error(record)
        action_sent = (
            action if isinstance(action, dict) else {"farmer": ["PASS"], "hands": [], "market": []}
        )
        fallback = inferred_fallback(action, record)
        action_class = classify_action(
            action_sent,
            _replay_snapshot(record.get("observation")),
            "inferred replay fallback" if fallback else None,
        )
        moves.append(ReportMove(turn=turn, action=action, error=error, action_class=action_class))
        evidence.append(
            {
                "action": action_sent,
                "action_sent": action_sent,
                "action_raw": action,
                "observation_before": _replay_snapshot(record.get("observation")),
                "fallback_reason": "inferred replay fallback" if fallback else None,
                "action_class": action_class,
            }
        )
    errors = [line.strip() for line in log_text.splitlines() if _looks_like_error(line)]
    errors.extend(move.error for move in moves if move.error)
    score = _number(rewards[agent_index]) if agent_index < len(rewards) else None
    opponent_score = _number(rewards[opponent_index]) if opponent_index is not None else None
    winner = _winner(score, opponent_score)
    status = _text((metadata or {}).get("status")) or ("complete" if steps else "unknown")
    metrics = summarize_turns(evidence)
    metrics["economic"] = _replay_economic_metrics(steps, agent_index, opponent_index)
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
        metrics=metrics,
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
        moves.append(
            ReportMove(
                turn=int(record.get("turn", index)),
                action=action,
                error=error,
                action_class=str(
                    record.get("action_class")
                    or classify_action(
                        action,
                        record.get("observation_before", {}),
                        record.get("fallback_reason"),
                    )
                ),
            )
        )
    return moves


def _local_metrics(data: dict[str, Any], moves: list[ReportMove]) -> dict[str, Any]:
    raw = data.get("metrics")
    if isinstance(raw, dict):
        behavior = raw.get("behavior")
        if isinstance(behavior, dict):
            result = dict(behavior)
            if isinstance(raw.get("cycle"), dict):
                result["cycle"] = raw["cycle"]
            if isinstance(raw.get("economic"), dict):
                result["economic"] = raw["economic"]
            if isinstance(raw.get("action_counts"), dict):
                result["action_counts"] = raw["action_counts"]
            return result
        return raw
    return summarize_turns(
        {
            "action_sent": move.action,
            "action_class": move.action_class,
            "fallback_reason": move.error if move.action_class == "fallback_pass" else None,
        }
        for move in moves
    )


def _replay_snapshot(observation: Any) -> dict[str, Any]:
    if not isinstance(observation, dict):
        return {}
    farms = observation.get("farms")
    player = observation.get("player", 0)
    farm = (
        farms[player]
        if isinstance(farms, list) and isinstance(player, int) and player < len(farms)
        else {}
    )
    if not isinstance(farm, dict):
        return {}
    tiles = [tile for row in farm.get("tiles", []) if isinstance(row, list) for tile in row]
    animal_count = sum(1 for tile in tiles if isinstance(tile, dict) and tile.get("animal"))
    crop_count = sum(1 for tile in tiles if isinstance(tile, dict) and tile.get("kind") == "PLANT")
    return {
        "day": observation.get("day"),
        "hour": observation.get("hour"),
        "animal_count": animal_count,
        "crop_count": crop_count,
        "hungry_animals": sum(
            1
            for tile in tiles
            if isinstance(tile, dict) and tile.get("animal") and not tile.get("fed_today")
        ),
        "irrigation_pending": sum(
            1
            for tile in tiles
            if isinstance(tile, dict)
            and tile.get("kind") == "PLANT"
            and not tile.get("watered_today")
        ),
        "mature_crops": sum(
            1
            for tile in tiles
            if isinstance(tile, dict)
            and tile.get("kind") == "PLANT"
            and tile.get("yield_units", 0) > 0
        ),
        "fertilizer_pending": sum(
            1 for tile in tiles if isinstance(tile, dict) and tile.get("fertilizer_available")
        ),
    }


def _replay_economic_metrics(
    steps: list[Any], agent_index: int, opponent_index: int | None
) -> dict[str, Any]:
    daily_our: dict[int, float] = {}
    daily_opp: dict[int, float] = {}
    daily_records: dict[int, dict[str, Any]] = {}

    for step in steps:
        if not isinstance(step, list) or len(step) <= agent_index:
            continue
        rec_our = step[agent_index] if isinstance(step[agent_index], dict) else {}
        obs = rec_our.get("observation", {})
        if not isinstance(obs, dict):
            continue
        day = int(obs.get("day", 0))
        farms = obs.get("farms", [])
        if len(farms) > agent_index and isinstance(farms[agent_index], dict):
            money_our = float(farms[agent_index].get("money", 0.0) or 0.0)
            daily_our[day] = money_our
            if day not in daily_records:
                daily_records[day] = {
                    "day": day,
                    "money_start": money_our,
                    "money_end": money_our,
                    "market_orders": Counter(),
                    "action_counts": Counter(),
                }
            daily_records[day]["money_end"] = money_our

        if (
            opponent_index is not None
            and len(farms) > opponent_index
            and isinstance(farms[opponent_index], dict)
        ):
            money_opp = float(farms[opponent_index].get("money", 0.0) or 0.0)
            daily_opp[day] = money_opp

    return {
        "daily": [daily_records[d] for d in sorted(daily_records.keys())],
        "daily_our_money": [daily_our.get(d, 0.0) for d in range(31) if d in daily_our],
        "daily_opp_money": [daily_opp.get(d, 0.0) for d in range(31) if d in daily_opp],
    }


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
    our_avg = _average(scored, "score")
    opp_avg = _average(opponent_scored, "opponent_score")
    margin_avg = (our_avg - opp_avg) if (our_avg is not None and opp_avg is not None) else None

    # Calculate average idle % across episodes
    raw_idle_pcts: list[float] = [
        float(v)
        for ep in counted_episodes
        if (v := _metric_percent(ep.metrics, "idle_turn_percentage")) is not None
    ]
    avg_idle_pct = sum(raw_idle_pcts) / len(raw_idle_pcts) if raw_idle_pcts else 0.0

    rows = []
    for episode in episodes:
        href = f"episodes/{_slug(episode.episode_id)}.html"
        excluded = _is_excluded_episode(submission, episode)
        result_class = "self-play" if excluded else _result_class(episode.winner)
        result_label = "SELF-PLAY (excluded)" if excluded else _winner_label(episode.winner)
        ep_margin = (
            episode.score - episode.opponent_score
            if episode.score is not None and episode.opponent_score is not None
            else None
        )
        margin_style = (
            "color:#198754;font-weight:700"
            if ep_margin and ep_margin > 0
            else ("color:#dc3545;font-weight:700" if ep_margin and ep_margin < 0 else "")
        )
        margin_text = (
            f"+{ep_margin:,.0f}"
            if ep_margin and ep_margin > 0
            else (f"{ep_margin:,.0f}" if ep_margin is not None else "-")
        )

        ep_idle = _metric_percent(episode.metrics, "idle_turn_percentage")

        rows.append(
            f'<tr class="{result_class}">'
            f'<td><a href="{escape(href)}"><strong>{escape(episode.episode_id)}</strong></a></td>'
            f"<td>{escape(episode.opponent_agent_name or '-')}</td>"
            f"<td><strong>{escape(_display(episode.score))}</strong></td>"
            f"<td>{escape(_display(episode.opponent_score))}</td>"
            f'<td style="{margin_style}">{margin_text}</td>'
            f'<td><span class="result-badge {result_class}">{escape(result_label)}</span></td>'
            f"<td>{escape(episode.status)}</td>"
            f"<td>{episode.turns}</td>"
            f"<td>{escape(_percent(ep_idle))}</td>"
            f"<td>{episode.our_market_orders} / {episode.opponent_market_orders}</td>"
            f"<td>{len(episode.errors)}</td></tr>"
        )
    episode_rows = "".join(rows) or '<tr><td colspan="11">No episodes found</td></tr>'

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

    margin_card_class = (
        "ours"
        if margin_avg and margin_avg > 0
        else ("opponent" if margin_avg and margin_avg < 0 else "neutral")
    )
    kpi_banner = (
        '<section class="kpi-grid" aria-label="Strategic KPI Overview">'
        f'<div class="kpi-card ours"><span>Our Avg Score</span>'
        f"<strong>${_display(our_avg)}</strong>"
        f"<small>Opponent avg: ${_display(opp_avg)}</small></div>"
        f'<div class="kpi-card {margin_card_class}">'
        "<span>Avg Score Margin</span>"
        f"<strong>{'+' if margin_avg and margin_avg > 0 else ''}{_display(margin_avg)}</strong>"
        f"<small>Decided games: {decided}</small></div>"
        f'<div class="kpi-card neutral"><span>Avg Idle Turns</span>'
        f"<strong>{avg_idle_pct:.1f}%</strong>"
        f"<small>Field efficiency: {100 - avg_idle_pct:.1f}%</small></div>"
        f'<div class="kpi-card neutral"><span>Total Matches</span>'
        f"<strong>{len(episodes)}</strong>"
        f"<small>{len(submission.excluded_episode_ids)} excluded self-play</small></div>"
        "</section>"
    )

    return _page(
        f"Submission {submission.submission_id}",
        f'<p><a href="../../index.html">← All submissions</a></p>'
        f"<h1>Submission: {escape(submission.submission_id)}</h1>"
        f"<p class='subtitle'>{escape(submission.description or '')}</p>"
        f"<p>Status: <strong class='status-pill'>{escape(submission.status)}</strong>"
        f" · Submitted: {escape(submission.submitted_at or '-')}</p>"
        f"{_excluded_note(submission)}"
        f"{summary}"
        f'<p class="record"><strong>Record (our wins–ties–opponent wins):</strong> '
        f"{counts['submission']}–{counts['tie']}–{counts['opponent']} "
        f"· our average: {_display(our_avg)} "
        f"· opponent average: {_display(opp_avg)}</p>"
        f"{kpi_banner}"
        f"{_submission_behavior_html(counted_episodes)}"
        "<h2>Match History</h2>"
        "<table><thead><tr><th>Episode</th><th>Opponent</th><th>Our submission</th>"
        "<th>Opponent score</th><th>Margin</th><th>Result</th><th>Status</th>"
        "<th>Turns</th><th>Idle %</th><th>Market Orders (Us/Opp)</th><th>Errors</th></tr></thead>"
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
            f"<td><span class='badge-action {escape(move.action_class)}'>"
            f"{escape(move.action_class)}</span></td>"
            f"<td>{escape(move.error or '-')}</td></tr>"
        )
    move_rows = "".join(moves) or '<tr><td colspan="4">No moves recorded</td></tr>'
    error_rows = errors or "<li>None recorded</li>"
    excluded = _is_excluded_episode(submission, episode)
    result_class = "self-play" if excluded else _result_class(episode.winner)
    result_label = "SELF-PLAY (excluded)" if excluded else _winner_label(episode.winner)
    margin = (
        episode.score - episode.opponent_score
        if episode.score is not None and episode.opponent_score is not None
        else None
    )
    margin_text = (
        f"+{margin:,.0f}"
        if margin and margin > 0
        else (f"{margin:,.0f}" if margin is not None else "-")
    )

    action_summary = _action_summary_html(episode)
    daily_table = _daily_economic_table_html(episode)

    # Activity Metrics Breakdown
    counts = dict(episode.our_action_counts)
    water_count = (
        counts.get("farmer: WATER", 0) + counts.get("hands: WATER", 0) + counts.get("WATER", 0)
    )
    plant_count = (
        counts.get("farmer: PLANT", 0) + counts.get("hands: PLANT", 0) + counts.get("PLANT", 0)
    )
    harvest_count = (
        counts.get("farmer: HARVEST", 0)
        + counts.get("hands: HARVEST", 0)
        + counts.get("HARVEST", 0)
    )
    feed_count = (
        counts.get("farmer: FEED", 0) + counts.get("hands: FEED", 0) + counts.get("FEED", 0)
    )
    care_count = (
        counts.get("farmer: CARE", 0) + counts.get("hands: CARE", 0) + counts.get("CARE", 0)
    )
    fertilizer_count = (
        counts.get("farmer: COLLECT_FERTILIZER", 0)
        + counts.get("hands: COLLECT_FERTILIZER", 0)
        + counts.get("COLLECT_FERTILIZER", 0)
    )
    hire_count = counts.get("market: HIRE", 0) + counts.get("HIRE", 0)
    sell_count = counts.get("market: SELL", 0) + counts.get("SELL", 0)

    idle_pct_str = escape(_percent(_metric_percent(episode.metrics, "idle_turn_percentage")))
    streak_val = _metric(episode.metrics, "longest_pass_streak")

    body = (
        f'<p><a href="../index.html">← Back to submission</a></p>'
        f"<h1>Episode {escape(episode.episode_id)}</h1>"
        f"<p>Submission: <strong>{escape(submission.submission_id)}</strong>"
        f" · Status: <strong>{escape(episode.status)}</strong></p>"
        f'<section class="scoreboard {result_class}" aria-label="Episode score comparison">'
        f'<div class="score-card ours">'
        f"<span>Our submission ({escape(episode.our_agent_name or '-')})</span>"
        f"<strong>${escape(_display(episode.score))}</strong></div>"
        '<div class="versus" aria-hidden="true">vs</div>'
        f'<div class="score-card opponent">'
        f"<span>Opponent ({escape(episode.opponent_agent_name or '-')})</span>"
        f"<strong>${escape(_display(episode.opponent_score))}</strong></div>"
        f'</section><p class="result-line"><strong>Result:</strong> '
        f'<span class="result-badge {result_class}">{escape(result_label)}</span>'
        f" · Margin: <strong>{margin_text}</strong>"
        f" · Turns: <strong>{episode.turns}</strong></p>"
        "<h2>Game summary</h2>"
        '<section class="summary-grid replay-summary" aria-label="Game summary">'
        f'<div class="summary-card ours"><span>Our agent</span>'
        f'<strong class="summary-name">{escape(episode.our_agent_name or "-")}</strong></div>'
        f'<div class="summary-card opponent"><span>Opponent</span>'
        f'<strong class="summary-name">{escape(episode.opponent_agent_name or "-")}</strong></div>'
        f'<div class="summary-card neutral"><span>Score margin</span>'
        f"<strong>{margin_text}</strong></div>"
        f'<div class="summary-card ours"><span>Our market orders</span>'
        f"<strong>{episode.our_market_orders}</strong></div>"
        f'<div class="summary-card opponent"><span>Opponent market orders</span>'
        f"<strong>{episode.opponent_market_orders}</strong></div>"
        f'<div class="summary-card neutral"><span>Our errors</span>'
        f"<strong>{len(episode.errors)}</strong></div>"
        "</section>"
        "<h2>Operational & Strategic KPIs</h2>"
        '<section class="kpi-grid" aria-label="Strategic KPIs">'
        f'<div class="kpi-card highlight-ours"><span>Idle Turns %</span>'
        f"<strong>{idle_pct_str}</strong>"
        f"<small>Longest PASS streak: {streak_val}</small></div>"
        f'<div class="kpi-card ours"><span>Field Operations</span>'
        f"<strong>{water_count + harvest_count + plant_count} ops</strong>"
        f"<small>Water: {water_count} · Harv: {harvest_count} · Plant: {plant_count}</small></div>"
        f'<div class="kpi-card ours"><span>Livestock Care</span>'
        f"<strong>{feed_count + care_count + fertilizer_count} ops</strong>"
        f"<small>Feed: {feed_count} · Care: {care_count} · Poop: {fertilizer_count}</small></div>"
        f'<div class="kpi-card neutral"><span>Market Volume</span>'
        f"<strong>{episode.our_market_orders} orders</strong>"
        f"<small>Hires: {hire_count} · Sells: {sell_count}</small></div>"
        f'<div class="kpi-card {"neutral" if len(episode.errors) == 0 else "opponent"}">'
        "<span>Stability & Errors</span>"
        f"<strong>{len(episode.errors)} errors</strong>"
        f"<small>Fallbacks: {_metric(episode.metrics, 'fallbacks_inferred')}</small></div>"
        "</section>"
        f"{_score_evolution_chart_html(episode)}"
        f"{daily_table}"
        f"{action_summary}"
        f"{_behavior_details_html(episode)}"
        f"{_cycle_details_html(episode)}"
        f"<h2>Errors ({len(episode.errors)})</h2><ul>{error_rows}</ul>"
        f"<details><summary>All moves ({len(episode.moves)} turns)</summary>"
        "<table><thead><tr><th>Turn</th><th>Action</th><th>Cause</th>"
        f"<th>Error</th></tr></thead><tbody>{move_rows}</tbody></table></details>"
    )
    return _page(f"Episode {episode.episode_id}", body, css_href="../../../assets/style.css")


def _score_evolution_chart_html(episode: ReportEpisode) -> str:
    """Generate an accessible, pure SVG line chart comparing our score vs opponent."""
    economic = _metric(episode.metrics, "economic", {})
    daily = economic.get("daily", []) if isinstance(economic, dict) else []

    # Extract points (Day 0 to 30)
    our_points: list[tuple[int, float]] = []
    if daily:
        for d in daily:
            day = int(d.get("day", 0))
            end_val = float(d.get("money_end", d.get("money_start", 0)) or 0)
            our_points.append((day, end_val))
    elif episode.score is not None:
        our_points = [(0, 3000.0), (30, float(episode.score))]
    else:
        return ""

    # Opponent points (from replay series if present, or interpolated)
    opp_series = economic.get("daily_opp_money", []) if isinstance(economic, dict) else []
    opp_points: list[tuple[int, float]] = []
    if opp_series:
        for day, val in enumerate(opp_series):
            opp_points.append((day, float(val)))
    elif episode.opponent_score is not None:
        opp_points = [(0, 3000.0), (30, float(episode.opponent_score))]
    else:
        opp_points = [(0, 3000.0), (30, 3000.0)]

    # Compute bounds
    all_vals = [p[1] for p in our_points] + [p[1] for p in opp_points]
    max_val = max(max(all_vals, default=5000), 5000.0) * 1.15
    min_val = 0.0

    width, height = 900, 320
    pad_left, pad_right, pad_top, pad_bottom = 80, 40, 30, 50
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    def scale_x(day: float) -> float:
        return pad_left + (day / 30.0) * plot_w

    def scale_y(val: float) -> float:
        norm = (val - min_val) / (max_val - min_val) if max_val > min_val else 0.5
        return pad_top + (1.0 - norm) * plot_h

    # Build SVG paths
    our_d = " ".join(
        f"{'M' if i == 0 else 'L'} {scale_x(p[0]):.1f} {scale_y(p[1]):.1f}"
        for i, p in enumerate(our_points)
    )
    opp_d = " ".join(
        f"{'M' if i == 0 else 'L'} {scale_x(p[0]):.1f} {scale_y(p[1]):.1f}"
        for i, p in enumerate(opp_points)
    )

    # Gridlines and Y-axis labels
    grid_lines = []
    for step in range(5):
        y_val = min_val + (max_val - min_val) * (step / 4.0)
        y_pos = scale_y(y_val)
        grid_lines.append(
            f'<line x1="{pad_left}" y1="{y_pos:.1f}" x2="{width - pad_right}" y2="{y_pos:.1f}" '
            'stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="4,4"/>'
            f'<text x="{pad_left - 12}" y="{y_pos + 4:.1f}" fill="#475569" '
            f'font-size="12" font-weight="700" text-anchor="end">${y_val:,.0f}</text>'
        )

    # X-axis labels (Days 0, 5, 10, 15, 20, 25, 30)
    x_labels = []
    for day in range(0, 31, 5):
        x_pos = scale_x(day)
        x_labels.append(
            f'<line x1="{x_pos:.1f}" y1="{pad_top}" x2="{x_pos:.1f}" y2="{height - pad_bottom}" '
            'stroke="#f1f5f9" stroke-width="1"/>'
            f'<text x="{x_pos:.1f}" y="{height - pad_bottom + 22}" fill="#475569" '
            f'font-size="12" font-weight="700" text-anchor="middle">Day {day}</text>'
        )

    # Markers for our key milestones
    circles = []
    for p in our_points:
        if p[0] in {0, 10, 20, 30} or p == our_points[-1]:
            cx, cy = scale_x(p[0]), scale_y(p[1])
            circles.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="#16a34a" '
                'stroke="#ffffff" stroke-width="2"/>'
                f'<text x="{cx:.1f}" y="{cy - 10:.1f}" fill="#14532d" '
                f'font-size="11" font-weight="800" text-anchor="middle">${p[1]:,.0f}</text>'
            )

    # Opponent markers
    for p in opp_points:
        if p[0] in {0, 30} or p == opp_points[-1]:
            opp_cx, opp_cy = scale_x(p[0]), scale_y(p[1])
            circles.append(
                f'<circle cx="{opp_cx:.1f}" cy="{opp_cy:.1f}" r="5" fill="#dc2626" '
                'stroke="#ffffff" stroke-width="2"/>'
                f'<text x="{opp_cx:.1f}" y="{opp_cy + 18:.1f}" fill="#991b1b" '
                f'font-size="11" font-weight="800" text-anchor="middle">${p[1]:,.0f}</text>'
            )

    svg_content = (
        f'<svg viewBox="0 0 {width} {height}" style="width:100%; height:auto; display:block;" '
        'xmlns="http://www.w3.org/2000/svg">'
        f"{''.join(grid_lines)}"
        f"{''.join(x_labels)}"
        f'<path d="{opp_d}" fill="none" stroke="#dc2626" stroke-width="3" '
        'stroke-dasharray="6,4" stroke-linecap="round"/>'
        f'<path d="{our_d}" fill="none" stroke="#16a34a" stroke-width="3.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        f"{''.join(circles)}"
        "</svg>"
    )

    our_name_esc = escape(episode.our_agent_name or "Us")
    opp_name_esc = escape(episode.opponent_agent_name or "Opp")
    return (
        '<section class="chart-container" aria-label="Score Evolution Chart">'
        '<div class="chart-header">'
        '<div class="chart-title">Financial Evolution: Our Score vs Opponent (30 Days)</div>'
        '<div class="chart-legend">'
        '<div class="legend-item"><div class="legend-color legend-ours"></div>'
        f"<span>Our Submission ({our_name_esc})</span></div>"
        '<div class="legend-item"><div class="legend-color legend-opp"></div>'
        f"<span>Opponent ({opp_name_esc})</span></div>"
        "</div></div>"
        f"{svg_content}</section>"
    )


def _daily_economic_table_html(episode: ReportEpisode) -> str:
    economic = _metric(episode.metrics, "economic", {})
    daily = economic.get("daily", []) if isinstance(economic, dict) else []
    if not daily:
        return ""
    rows = []
    for d in daily:
        day = d.get("day", 0)
        start = d.get("money_start", 0)
        end = d.get("money_end", 0)
        delta = end - start
        delta_class = "margin-positive" if delta > 0 else ("margin-negative" if delta < 0 else "")
        delta_text = (
            f"+${delta:,.0f}" if delta > 0 else (f"-${abs(delta):,.0f}" if delta < 0 else "$0")
        )
        mkt = d.get("market_orders", {})
        act = d.get("action_counts", {})
        hires = mkt.get("HIRE", 0)
        sells = mkt.get("SELL", 0)
        waters = act.get("WATER", 0)
        harvests = act.get("HARVEST", 0)
        plants = act.get("PLANT", 0)
        rows.append(
            f"<tr><td>Day {day:02d}</td>"
            f"<td>${start:,.0f}</td><td>${end:,.0f}</td>"
            f'<td class="{delta_class}"><strong>{delta_text}</strong></td>'
            f"<td>{hires}</td><td>{waters}</td><td>{harvests}</td><td>{plants}</td>"
            f"<td>{sells}</td></tr>"
        )
    table_rows = "".join(rows)
    return (
        '<section class="behavior-details" aria-label="Daily Economic Evolution">'
        "<h2>Daily Farm & Financial Evolution (30 Days)</h2>"
        "<div style='overflow-x:auto;'><table><thead><tr>"
        "<th>Day</th><th>Start Cash</th><th>End Cash</th><th>Delta ($)</th>"
        "<th>Hires</th><th>Waters</th><th>Harvests</th><th>Plants</th><th>Sells</th>"
        "</tr></thead>"
        f"<tbody>{table_rows}</tbody></table></div></section>"
    )


def _index_html(submissions: list[ReportSubmission]) -> str:
    all_episodes = [ep for s in submissions for ep in _counted_episodes(s)]
    total_episodes = len(all_episodes)
    global_counts = _outcome_counts(all_episodes)
    decided = global_counts["submission"] + global_counts["opponent"] + global_counts["tie"]
    global_win_rate = global_counts["submission"] / decided * 100 if decided else 0.0

    all_scores = [ep.score for ep in all_episodes if ep.score is not None]
    all_opp_scores = [ep.opponent_score for ep in all_episodes if ep.opponent_score is not None]
    global_our_avg = sum(all_scores) / len(all_scores) if all_scores else None
    global_opp_avg = sum(all_opp_scores) / len(all_opp_scores) if all_opp_scores else None

    overview = (
        '<section class="kpi-grid" aria-label="Global Submission Overview">'
        f'<div class="kpi-card highlight-ours"><span>Total Submissions</span>'
        f"<strong>{len(submissions)}</strong>"
        f"<small>{total_episodes} matches evaluated</small></div>"
        f'<div class="kpi-card ours"><span>Global Record (W–T–L)</span>'
        f"<strong>{global_counts['submission']}–{global_counts['tie']}–"
        f"{global_counts['opponent']}</strong>"
        f"<small>Win rate: {global_win_rate:.1f}%</small></div>"
        f'<div class="kpi-card ours"><span>Global Avg Score</span>'
        f"<strong>${_display(global_our_avg)}</strong>"
        f"<small>Opponents: ${_display(global_opp_avg)}</small></div>"
        f'<div class="kpi-card neutral"><span>Total Matches</span>'
        f"<strong>{total_episodes}</strong>"
        f"<small>Continuous improvement pipeline</small></div>"
        "</section>"
    )

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
        sub_decided = counts["submission"] + counts["opponent"] + counts["tie"]
        sub_win_rate = counts["submission"] / sub_decided * 100 if sub_decided else 0.0
        our_average = sum(scores) / len(scores) if scores else None
        opponent_average = sum(opponent_scores) / len(opponent_scores) if opponent_scores else None
        margin_avg = (
            (our_average - opponent_average)
            if (our_average is not None and opponent_average is not None)
            else None
        )
        margin_style = (
            "color:#198754;font-weight:700"
            if margin_avg and margin_avg > 0
            else ("color:#dc3545;font-weight:700" if margin_avg and margin_avg < 0 else "")
        )
        margin_text = (
            f"+${margin_avg:,.0f}"
            if margin_avg and margin_avg > 0
            else (f"-${abs(margin_avg):,.0f}" if margin_avg and margin_avg < 0 else "-")
        )

        raw_sub_idle: list[float] = [
            float(v)
            for ep in counted_episodes
            if (v := _metric_percent(ep.metrics, "idle_turn_percentage")) is not None
        ]
        avg_idle_pct = sum(raw_sub_idle) / len(raw_sub_idle) if raw_sub_idle else 0.0

        errors = sum(len(episode.errors) for episode in episodes)
        href = f"submissions/{_slug(submission.submission_id)}/index.html"

        sub_id_escaped = escape(submission.submission_id)
        rec_str = f"{counts['submission']}–{counts['tie']}–{counts['opponent']}"
        win_pct_str = f"({sub_win_rate:.0f}%)"
        rows.append(
            "<tr>"
            f'<td><a href="{escape(href)}"><strong>{sub_id_escaped}</strong></a></td>'
            f"<td><span class='status-pill'>{escape(submission.status)}</span></td>"
            f"<td>{len(episodes)}</td>"
            f'<td><span class="record-badge">{rec_str}</span>'
            f'<small style="margin-left:0.35rem;font-weight:600;">{win_pct_str}</small></td>'
            f"<td><strong>${escape(_display(our_average))}</strong></td>"
            f"<td>${escape(_display(opponent_average))}</td>"
            f'<td style="{margin_style}">{margin_text}</td>'
            f"<td>{avg_idle_pct:.1f}%</td>"
            f"<td>{errors}</td></tr>"
        )
    submission_rows = "".join(rows) or '<tr><td colspan="9">No submissions found</td></tr>'
    subtitle = "Unified benchmark and Kaggle replay analytics for agent iterations."
    return _page(
        "Kaggriculture Submission Reports & Analytics",
        "<h1>🌾 Kaggriculture Continuous Improvement Dashboard</h1>"
        f"<p class='subtitle'>{subtitle}</p>"
        f"{overview}"
        "<h2>All Submissions & Benchmarks</h2>"
        "<table><thead><tr><th>Submission</th><th>Status</th><th>Episodes</th>"
        "<th>Record (W–T–L)</th><th>Our Avg</th><th>Opponent Avg</th>"
        "<th>Avg Margin</th><th>Idle %</th><th>Errors</th></tr></thead>"
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
    values = [
        getattr(episode, field_name)
        for episode in episodes
        if getattr(episode, field_name) is not None
    ]
    return sum(values) / len(values) if values else None


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def _action_summary_html(episode: ReportEpisode) -> str:
    return (
        '<section class="action-grid" aria-label="Action summary">'
        f"{_action_table('Our Actions Breakdown', episode.our_action_counts, 'ours')}"
        f"{_action_table('Opponent Actions Breakdown', episode.opponent_action_counts, 'opponent')}"
        "</section>"
    )


def _submission_behavior_html(episodes: list[ReportEpisode]) -> str:
    metrics = [episode.metrics for episode in episodes if episode.metrics]
    total = sum(
        sum(_metric(item, "turn_classes", {}).values())
        for item in metrics
        if isinstance(_metric(item, "turn_classes", {}), dict)
    )
    idle = sum(_metric(item, "idle_turns") for item in metrics)
    fallbacks = sum(_metric(item, "fallbacks_inferred") for item in metrics)
    lost = sum(_metric(item, "lost_actions") for item in metrics)
    longest = max((_metric(item, "longest_pass_streak") for item in metrics), default=0)
    idle_percent = idle / total * 100 if total else None
    return (
        '<section class="kpi-grid behavior-summary" aria-label="Idle and fallback summary">'
        f'<div class="kpi-card neutral"><span>Idle Turns %</span>'
        f"<strong>{_percent(idle_percent)}</strong>"
        f"<small>Total wasted turns</small></div>"
        f'<div class="kpi-card neutral"><span>Longest PASS Streak</span>'
        f"<strong>{longest} turns</strong>"
        f"<small>Max consecutive wait</small></div>"
        f'<div class="kpi-card opponent"><span>Fallbacks Inferred</span>'
        f"<strong>{fallbacks}</strong>"
        f"<small>Sanitized commands</small></div>"
        f'<div class="kpi-card opponent"><span>Lost Action Slots</span>'
        f"<strong>{lost}</strong>"
        f"<small>Dropped commands</small></div>"
        "</section>"
    )


def _behavior_details_html(episode: ReportEpisode) -> str:
    classes = _metric(episode.metrics, "turn_classes", {})
    rows = (
        "".join(
            f"<tr><td><span class='badge-action {escape(str(name))}'>"
            f"{escape(str(name))}</span></td><td><strong>{count}</strong></td></tr>"
            for name, count in classes.items()
        )
        if isinstance(classes, dict)
        else ""
    )
    heatmap = _metric(episode.metrics, "heatmap", {})
    table_rows = rows or '<tr><td colspan="2">No turn metrics</td></tr>'
    return (
        '<section class="behavior-details" aria-label="PASS cause audit">'
        "<h2>Turn Classification Breakdown</h2>"
        "<table><thead><tr><th>Turn Class</th><th>Turn Count</th></tr></thead>"
        f"<tbody>{table_rows}</tbody></table>"
        "<details><summary>Day-Hour Heatmap Matrix (JSON)</summary>"
        f"<pre>{escape(_json_text(heatmap))}</pre></details>"
        "</section>"
    )


def _cycle_details_html(episode: ReportEpisode) -> str:
    cycle = _metric(episode.metrics, "cycle", {})
    if not isinstance(cycle, dict) or not cycle:
        return ""
    rows = "".join(
        f"<tr><td>{escape(str(label))}</td><td><strong>"
        f"{escape(str(cycle.get(key, 0)))}</strong></td></tr>"
        for key, label in (
            ("commitments_created", "Commitments created"),
            ("commitments_confirmed", "Commitments confirmed"),
            ("commitments_replanned", "Commitments replanned"),
            ("commitments_abandoned", "Commitments abandoned"),
            ("plant_harvest_sale_cycles", "Plant cycles complete"),
            ("animal_complete_cycles", "Animal cycles complete"),
            ("actions_repeated_without_progress", "Repeated actions without progress"),
            ("plan_observation_divergences", "Plan/observation divergences"),
            ("cash_reserved", "Cash reserved"),
            ("cash_spent", "Cash spent"),
        )
    )
    return (
        '<section class="behavior-details" aria-label="Cycle memory audit">'
        "<h2>Cycle Memory & Plan Commitments</h2>"
        "<table><thead><tr><th>Commitment Metric</th><th>Value</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></section>"
    )


def _metric(metrics: dict[str, Any], key: str, default: Any = 0) -> Any:
    value = metrics.get(key, default) if isinstance(metrics, dict) else default
    return default if value is None else value


def _metric_percent(metrics: dict[str, Any], key: str) -> float | None:
    value = _metric(metrics, key, None)
    return float(value) if isinstance(value, int | float) else None


def _action_table(title: str, counts: tuple[tuple[str, int], ...], css_class: str) -> str:
    if not counts:
        rows = '<tr><td colspan="2">No actions recorded</td></tr>'
    else:
        rows = "".join(
            f"<tr><td><code>{escape(label)}</code></td><td><strong>{count}</strong></td></tr>"
            for label, count in counts
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
    return "-" if value is None else f"{value:,.2f}".rstrip("0").rstrip(".")


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
:root {
  --primary: #0284c7;
  --primary-dark: #0369a1;
  --primary-light: #e0f2fe;
  --success: #15803d;
  --success-dark: #166534;
  --success-light: #dcfce7;
  --danger: #b91c1c;
  --danger-dark: #991b1b;
  --danger-light: #fee2e2;
  --warning: #c2410c;
  --warning-light: #ffedd5;
  --neutral: #334155;
  --neutral-light: #f1f5f9;
  --bg: #f8fafc;
  --card-bg: #ffffff;
  --border: #cbd5e1;
  --border-dark: #94a3b8;
  --text: #0f172a;
  --text-muted: #475569;
}

* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  margin: 0;
  line-height: 1.6;
  font-size: 15px;
}
main { max-width: 1300px; margin: 2rem auto; padding: 0 1.5rem; }

h1 {
  color: #0f172a;
  margin-bottom: 0.35rem;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: -0.025em;
}
h2 {
  color: #0f172a;
  margin-top: 2.25rem;
  margin-bottom: 0.85rem;
  font-size: 1.4rem;
  font-weight: 700;
  border-bottom: 2px solid var(--border);
  padding-bottom: 0.5rem;
}
h3 { color: #1e293b; margin: 0.6rem 0; font-size: 1.15rem; font-weight: 700; }
p.subtitle { color: var(--text-muted); font-size: 1.05rem; margin: 0 0 1.5rem 0; }
a { color: var(--primary-dark); text-decoration: none; font-weight: 600; }
a:hover { text-decoration: underline; color: #0c4a6e; }

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.25rem;
  margin: 1.5rem 0;
}
.kpi-card {
  background: var(--card-bg);
  border: 1.5px solid var(--border);
  border-radius: 10px;
  padding: 1.25rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.04);
}
.kpi-card span {
  display: block;
  font-size: 0.82rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}
.kpi-card strong {
  display: block;
  font-size: 1.85rem;
  font-weight: 800;
  margin: 0.35rem 0 0.15rem 0;
  color: #0f172a;
}
.kpi-card small { display: block; font-size: 0.88rem; color: #475569; font-weight: 500; }

.kpi-card.highlight-ours {
  border-left: 6px solid var(--primary-dark);
  background: linear-gradient(135deg, #ffffff 0%, #f0f9ff 100%);
}
.kpi-card.ours {
  border-left: 6px solid var(--success-dark);
  background: linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%);
}
.kpi-card.opponent {
  border-left: 6px solid var(--danger-dark);
  background: linear-gradient(135deg, #ffffff 0%, #fef2f2 100%);
}
.kpi-card.neutral {
  border-left: 6px solid var(--neutral);
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
}

.scoreboard {
  display: flex;
  align-items: stretch;
  gap: 1.25rem;
  margin: 1.5rem 0;
  max-width: 800px;
}
.score-card {
  flex: 1;
  border-radius: 10px;
  padding: 1.5rem;
  text-align: center;
  background: var(--card-bg);
  border: 2px solid var(--border);
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.score-card span {
  display: block;
  font-size: 0.9rem;
  font-weight: 800;
  text-transform: uppercase;
  color: var(--text-muted);
}
.score-card strong { display: block; font-size: 2.5rem; font-weight: 900; margin-top: 0.35rem; }
.score-card.ours {
  border-color: var(--success-dark);
  background: #f0fdf4;
  color: #14532d;
}
.score-card.opponent {
  border-color: var(--danger-dark);
  background: #fef2f2;
  color: #7f1d1d;
}
.versus { align-self: center; font-weight: 900; font-size: 1.4rem; color: #64748b; }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem;
  margin: 1.25rem 0;
}
.summary-card {
  background: var(--card-bg);
  border: 1.5px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
}
.summary-card span {
  display: block;
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
  color: var(--text-muted);
}
.summary-card strong {
  display: block;
  font-size: 1.5rem;
  font-weight: 800;
  color: #0f172a;
  margin-top: 0.25rem;
}
.summary-card.ours { border-left: 5px solid var(--success-dark); background: #f0fdf4; }
.summary-card.opponent { border-left: 5px solid var(--danger-dark); background: #fef2f2; }
.summary-card.tie { border-left: 5px solid var(--primary-dark); background: #f0f9ff; }
.summary-card.neutral { border-left: 5px solid var(--neutral); background: #f8fafc; }

/* SVG Score Evolution Chart */
.chart-container {
  background: var(--card-bg);
  border: 1.5px solid var(--border);
  border-radius: 10px;
  padding: 1.5rem;
  margin: 1.5rem 0 2rem 0;
  box-shadow: 0 2px 4px rgba(0,0,0,0.04);
}
.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.75rem;
}
.chart-title { font-size: 1.15rem; font-weight: 800; color: #0f172a; }
.chart-legend { display: flex; gap: 1.5rem; font-size: 0.9rem; font-weight: 700; }
.legend-item { display: flex; align-items: center; gap: 0.5rem; }
.legend-color { width: 14px; height: 14px; border-radius: 3px; }
.legend-ours { background: #16a34a; }
.legend-opp { background: #dc2626; }

table {
  border-collapse: collapse;
  width: 100%;
  background: var(--card-bg);
  margin: 1rem 0 2rem 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1.5px solid var(--border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
th, td {
  border: 1px solid var(--border);
  padding: 0.75rem 1rem;
  text-align: left;
  vertical-align: middle;
  font-size: 0.94rem;
  color: #0f172a;
}
th {
  background: #f1f5f9;
  color: #1e293b;
  font-weight: 800;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
tbody tr:hover { background: #f8fafc; }

.status-pill {
  display: inline-block;
  padding: 0.2rem 0.65rem;
  border-radius: 999px;
  background: #e2e8f0;
  color: #1e293b;
  font-size: 0.82rem;
  font-weight: 700;
}
.result-badge, .record-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 0.3rem 0.75rem;
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.04em;
}
.result-badge.ours-win, tr.ours-win { background: #166534; color: #ffffff; }
.result-badge.opponent-win, tr.opponent-win { background: #991b1b; color: #ffffff; }
.result-badge.tie-result, tr.tie-result { background: #0369a1; color: #ffffff; }
.result-badge.self-play, tr.self-play { background: #334155; color: #ffffff; }
.record-badge { background: #0f172a; color: #ffffff; }

tr.ours-win { background: #f0fdf4 !important; }
tr.opponent-win { background: #fef2f2 !important; }
tr.tie-result { background: #f0f9ff !important; }
tr.self-play { background: #f8fafc !important; color: #475569; }

.badge-action {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 800;
  text-transform: uppercase;
}
.badge-action.productive {
  background: var(--success-light);
  color: #14532d;
  border: 1px solid #bbf7d0;
}
.badge-action.movement {
  background: var(--primary-light);
  color: #075985;
  border: 1px solid #bae6fd;
}
.badge-action.legitimate_wait {
  background: var(--warning-light);
  color: #9a3412;
  border: 1px solid #fed7aa;
}
.badge-action.idle_pass {
  background: #f1f5f9;
  color: #334155;
  border: 1px solid #cbd5e1;
}
.badge-action.fallback_pass {
  background: var(--danger-light);
  color: #991b1b;
  border: 1px solid #fecaca;
}

.margin-positive { color: #166534; font-weight: 800; }
.margin-negative { color: #991b1b; font-weight: 800; }

.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 1.5rem;
  margin: 1.5rem 0;
}
.action-panel {
  background: var(--card-bg);
  border: 1.5px solid var(--border);
  border-radius: 10px;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.action-panel.ours { border-top: 5px solid #16a34a; }
.action-panel.opponent { border-top: 5px solid #dc2626; }

details {
  margin: 1.5rem 0;
  background: var(--card-bg);
  border: 1.5px solid var(--border);
  border-radius: 10px;
  padding: 1.25rem;
}
summary { cursor: pointer; font-weight: 800; color: #0f172a; font-size: 1.1rem; }
pre {
  background: #0f172a;
  color: #f8fafc;
  padding: 1.25rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.88rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
code {
  background: #f1f5f9;
  color: #0f172a;
  font-weight: 600;
  padding: 0.2rem 0.45rem;
  border-radius: 4px;
  font-size: 0.88rem;
}
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
