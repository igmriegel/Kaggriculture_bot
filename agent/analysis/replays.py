"""Deterministic, read-only extraction of strategic evidence from Kaggle replays."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from agent.analysis.action_metrics import inferred_fallback, summarize_turns

LEADER_NAME = "Ryo Hasegawa"
ECONOMIC_ORDERS = {"BUY_ANIMAL", "BUY_LAND", "BUY_PRODUCT", "BUY_SEED", "HIRE", "SELL"}
WORK_OPS = {"CARE", "COLLECT_FERTILIZER", "FEED", "FERTILIZE", "HARVEST", "PLANT", "WATER"}


def audit_replays(paths: list[Path], *, leader_name: str = LEADER_NAME) -> dict[str, Any]:
    """Return a portable audit report without changing the source replays."""
    episodes = [audit_replay(path, leader_name=leader_name) for path in paths]
    return {
        "schema_version": 1,
        "leader_name": leader_name,
        "episodes": episodes,
        "metrics": _aggregate_metrics(episodes),
        "cross_replay_patterns": _patterns(episodes),
    }


def audit_replay(path: Path, *, leader_name: str = LEADER_NAME) -> dict[str, Any]:
    """Extract daily economy, action categories, and final state for one replay."""
    with path.open(encoding="utf-8") as source:
        replay = json.load(source)
    agents = replay.get("info", {}).get("Agents", [])
    names = [entry.get("Name") if isinstance(entry, dict) else None for entry in agents]
    player = names.index(leader_name) if leader_name in names else 0
    rewards = replay.get("rewards", [])
    daily: dict[int, dict[str, Any]] = {}
    turn_evidence: list[dict[str, Any]] = []
    for step in replay.get("steps", []):
        if not isinstance(step, list) or player >= len(step) or not isinstance(step[player], dict):
            continue
        record = step[player]
        observation = record.get("observation", {})
        if not isinstance(observation, dict):
            continue
        day = _integer(observation.get("day"))
        entry = daily.setdefault(day, _daily_snapshot(observation, player))
        _record_actions(entry, record.get("action"))
        action = record.get("action")
        fallback = inferred_fallback(action, record)
        action_sent = (
            action if isinstance(action, dict) else {"farmer": ["PASS"], "hands": [], "market": []}
        )
        snapshot = _turn_snapshot(observation, player)
        turn_evidence.append(
            {
                "turn": len(turn_evidence),
                "action": action_sent,
                "action_sent": action_sent,
                "action_raw": action,
                "observation_before": snapshot,
                "fallback_reason": "inferred replay fallback" if fallback else None,
            }
        )
        snapshot = _daily_snapshot(observation, player)
        for key in ("money", "hands", "quadrants", "animals", "crops"):
            entry[key] = snapshot[key]
    days = [_serialise_day(daily[day]) for day in sorted(daily)]
    final = days[-1] if days else {}
    opponent_player = 1 - player if len(agents) > 1 else None
    opponent_days = (
        _audit_player_days(replay, opponent_player) if opponent_player is not None else []
    )
    return {
        "source": str(path),
        "episode_id": replay.get("info", {}).get("EpisodeId"),
        "seed": replay.get("info", {}).get("seed"),
        "leader_player": player,
        "leader_score": _number(rewards[player]) if player < len(rewards) else 0,
        "opponent_score": _number(rewards[1 - player]) if len(rewards) > 1 else 0,
        "days": days,
        "opponent_days": opponent_days,
        "players": {
            "leader": {"player": player, "days": days},
            "opponent": {"player": opponent_player, "days": opponent_days},
        },
        "final": final,
        "metrics": summarize_turns(turn_evidence),
    }


def _audit_player_days(replay: dict[str, Any], player: int) -> list[dict[str, Any]]:
    daily: dict[int, dict[str, Any]] = {}
    for step in replay.get("steps", []):
        if not isinstance(step, list) or player >= len(step) or not isinstance(step[player], dict):
            continue
        record = step[player]
        observation = record.get("observation", {})
        if not isinstance(observation, dict):
            continue
        day = _integer(observation.get("day"))
        entry = daily.setdefault(day, _daily_snapshot(observation, player))
        _record_actions(entry, record.get("action"))
        snapshot = _daily_snapshot(observation, player)
        for key in ("money", "hands", "quadrants", "animals", "crops"):
            entry[key] = snapshot[key]
    return [_serialise_day(daily[day]) for day in sorted(daily)]


def _aggregate_metrics(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate replay-level evidence for a submission/report batch."""
    classes: Counter[str] = Counter()
    heatmap: dict[str, Counter[str]] = {}
    fallbacks = lost_actions = 0
    longest = 0
    for episode in episodes:
        metrics = episode.get("metrics", {})
        if not isinstance(metrics, dict):
            continue
        classes.update(metrics.get("turn_classes", {}))
        fallbacks += _integer(metrics.get("fallbacks_inferred"))
        lost_actions += _integer(metrics.get("lost_actions"))
        longest = max(longest, _integer(metrics.get("longest_pass_streak")))
        for cell, counts in metrics.get("heatmap", {}).items():
            if isinstance(counts, dict):
                heatmap.setdefault(cell, Counter()).update(counts)
    total = sum(classes.values())
    serialized = {cell: dict(counts) for cell, counts in sorted(heatmap.items())}
    return {
        "turn_classes": dict(classes),
        "idle_turns": classes["idle_pass"],
        "idle_turn_percentage": classes["idle_pass"] / total * 100 if total else 0.0,
        "pass_turns": sum(
            classes[name] for name in ("legitimate_wait", "idle_pass", "fallback_pass")
        ),
        "legitimate_wait_turns": classes["legitimate_wait"],
        "fallback_pass_turns": classes["fallback_pass"],
        "fallbacks_inferred": fallbacks,
        "lost_actions": lost_actions,
        "longest_pass_streak": longest,
        "pass_heatmap": serialized,
        "heatmap": serialized,
    }


def write_audit(report: dict[str, Any], output: Path) -> tuple[Path, Path]:
    """Write machine-readable and concise human-readable audit artifacts."""
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "leader-replay-audit.json"
    markdown_path = output / "leader-replay-audit.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _daily_snapshot(observation: dict[str, Any], player: int) -> dict[str, Any]:
    farms = observation.get("farms", [])
    farm = farms[player] if isinstance(farms, list) and player < len(farms) else {}
    farm = farm if isinstance(farm, dict) else {}
    tiles = [tile for row in farm.get("tiles", []) if isinstance(row, list) for tile in row]
    animals = Counter(
        tile.get("animal") for tile in tiles if isinstance(tile, dict) and tile.get("animal")
    )
    crops = Counter(
        tile.get("crop") for tile in tiles if isinstance(tile, dict) and tile.get("crop")
    )
    return {
        "day": _integer(observation.get("day")),
        "money": _number(farm.get("money")),
        "hands": len(farm.get("hands", [])) if isinstance(farm.get("hands"), list) else 0,
        "quadrants": len(farm.get("unlocked_quadrants", []))
        if isinstance(farm.get("unlocked_quadrants"), list)
        else 0,
        "animals": animals,
        "crops": crops,
        "orders": Counter(),
        "order_units": Counter(),
        "work": Counter(),
    }


def _turn_snapshot(observation: dict[str, Any], player: int) -> dict[str, Any]:
    """Normalize only the chain signals needed by action classification."""
    snapshot = _daily_snapshot(observation, player)
    farms = observation.get("farms", [])
    farm = farms[player] if isinstance(farms, list) and player < len(farms) else {}
    farm = farm if isinstance(farm, dict) else {}
    tiles = [tile for row in farm.get("tiles", []) if isinstance(row, list) for tile in row]
    snapshot.update(
        {
            "hour": _integer(observation.get("hour")),
            "animal_count": sum(
                1 for tile in tiles if isinstance(tile, dict) and tile.get("animal")
            ),
            "crop_count": sum(
                1 for tile in tiles if isinstance(tile, dict) and tile.get("kind") == "PLANT"
            ),
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
                and _integer(tile.get("yield_units")) > 0
            ),
            "fertilizer_pending": sum(
                1 for tile in tiles if isinstance(tile, dict) and tile.get("fertilizer_available")
            ),
            "inventory_units": 0,
            "feed_deficit": 0,
        }
    )
    private_raw = observation.get("private")
    private = private_raw if isinstance(private_raw, dict) else {}
    inventories = private.get("inventories", [])
    if isinstance(inventories, list):
        snapshot["inventory_units"] = sum(
            sum(_integer(value) for value in inventory.values())
            for inventory in inventories
            if isinstance(inventory, dict)
        )
    shed = private.get("shed", {}) if isinstance(private.get("shed"), dict) else {}
    animal_total = (
        sum(snapshot["animals"].values()) if isinstance(snapshot["animals"], Counter) else 0
    )
    snapshot["feed_deficit"] = max(0, animal_total - _integer(shed.get("WHEAT")))
    return snapshot


def _record_actions(entry: dict[str, Any], action: Any) -> None:
    if not isinstance(action, dict):
        return
    units = [action.get("farmer"), *(action.get("hands", []))]
    for command in units:
        if isinstance(command, list) and command and command[0] in WORK_OPS:
            entry["work"][command[0]] += 1
    for order in action.get("market", []):
        if not isinstance(order, list) or not order or order[0] not in ECONOMIC_ORDERS:
            continue
        entry["orders"][order[0]] += 1
        if len(order) >= 3 and isinstance(order[1], str):
            entry["order_units"][f"{order[0]}:{order[1]}"] += _integer(order[2])


def _serialise_day(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        key: dict(value) if isinstance(value, Counter) else value for key, value in entry.items()
    }


def _patterns(episodes: list[dict[str, Any]]) -> list[str]:
    first_days = [episode.get("days", [])[:3] for episode in episodes]
    all_openings = [day for days in first_days for day in days]
    bought_animals = any(
        day.get("order_units", {}).get("BUY_ANIMAL:COW", 0) for day in all_openings
    )
    bought_wheat = any(
        day.get("order_units", {}).get("BUY_PRODUCT:WHEAT", 0) for day in all_openings
    )
    cared = any(
        day.get("work", {}).get("CARE", 0)
        for episode in episodes
        for day in episode.get("days", [])
    )
    patterns = ["daily fertilizer collection and sales", "three-quadrant expansion"]
    if bought_animals:
        patterns.append("animal investment in the opening")
    if bought_wheat:
        patterns.append("purchased wheat used as an animal-feed input")
    if cared:
        patterns.append("animal care paired with feeding")
    classifications = set()
    for episode in episodes:
        days = episode.get("days", [])
        animal_orders = sum(
            day.get("order_units", {}).get("BUY_ANIMAL:COW", 0)
            + day.get("order_units", {}).get("BUY_ANIMAL:SHEEP", 0)
            for day in days
        )
        crop_work = sum(day.get("work", {}).get("PLANT", 0) for day in days)
        expansion = max((day.get("quadrants", 0) for day in days), default=0)
        if animal_orders and crop_work:
            classifications.add("hybrid")
        elif animal_orders:
            classifications.add("animal-first")
        elif crop_work:
            classifications.add("crop-only")
        if expansion > 1 and days and days[min(2, len(days) - 1)].get("quadrants", 0) > 1:
            classifications.add("early-expansion")
        activity = sum(sum(day.get("orders", {}).values()) for day in days)
        if activity < max(1, len(days) // 3):
            classifications.add("low-activity")
    patterns.extend(f"opponent classification: {name}" for name in sorted(classifications))
    return patterns


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# Leader replay audit", "", f"Reference player: {report['leader_name']}", ""]
    for episode in report["episodes"]:
        lines.extend(
            [
                f"## Episode {episode['episode_id']}",
                "",
                f"Seed {episode['seed']} · score {episode['leader_score']:.0f} "
                f"vs {episode['opponent_score']:.0f}",
                "",
                f"Idle PASS {episode.get('metrics', {}).get('idle_turn_percentage', 0):.1f}% · "
                f"longest PASS streak {episode.get('metrics', {}).get('longest_pass_streak', 0)} · "
                f"fallbacks {episode.get('metrics', {}).get('fallbacks_inferred', 0)} · "
                f"lost actions {episode.get('metrics', {}).get('lost_actions', 0)}",
                "",
            ]
        )
        for day in episode["days"]:
            if day["day"] in {0, 1, 2, 6, 12, 18, 24, 29}:
                lines.append(
                    f"- Day {day['day']}: ${day['money']:.0f}, {day['hands']} hands, "
                    f"{day['quadrants']} quadrants, animals={day['animals']}, "
                    f"orders={day['order_units']}"
                )
        lines.append("")
    lines.extend(
        [
            "## Cross-replay patterns",
            "",
            *[f"- {item}" for item in report["cross_replay_patterns"]],
            "",
        ]
    )
    return "\n".join(lines)


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
