"""Strategy-agnostic episode orchestration."""

from collections import Counter
from collections.abc import Callable, Sequence
from hashlib import sha256
from time import perf_counter
from typing import Any, cast

from agent.analysis.action_metrics import (
    classify_action,
    command_count,
    inferred_fallback,
    is_whole_turn_pass,
    summarize_turns,
)
from agent.core.validation import validate_action
from agent.harness.models import EpisodeRecord, EpisodeStatus, RunConfig, TurnRecord
from agent.harness.protocols import Agent, EnvironmentAdapter, Reporter


class EpisodeRunner:
    """Run an adapter episode while preserving all safety and evidence events."""

    def __init__(self, config: RunConfig, reporters: Sequence[Reporter] = ()) -> None:
        self.config = config
        self.reporters = tuple(reporters)

    def run(
        self,
        environment: EnvironmentAdapter,
        agent: Agent | Callable[[dict[str, Any]], Any],
        *,
        episode_id: str = "episode-0",
        agent_name: str = "agent",
        opponent_name: str = "unknown",
    ) -> EpisodeRecord:
        observation = environment.reset(
            seed=self.config.seed, configuration=self.config.configuration
        )
        reset_cycle = getattr(agent, "reset_cycle", None)
        if callable(reset_cycle):
            reset_cycle()
        records: list[TurnRecord] = []
        errors = 0
        fallbacks = 0
        status: EpisodeStatus = "incomplete"
        raw_result: Any = None
        for turn in range(self.config.max_turns):
            if environment.finished():
                raw_result = environment.result()
                if status == "incomplete":
                    status = _infer_status(raw_result)
                break
            started = perf_counter()
            raw: Any = None
            exception: str | None = None
            try:
                raw = _act(agent, observation)
            except Exception as exc:
                errors += 1
                exception = f"{type(exc).__name__}: {exc}"
                status = "agent_error"
            latency_ms = (perf_counter() - started) * 1000
            if (
                self.config.action_timeout_ms is not None
                and latency_ms > self.config.action_timeout_ms
            ):
                errors += 1
                exception = f"timeout: action exceeded {self.config.action_timeout_ms}ms"
                status = "timeout"
                raw = None
            action, fallback_reason = validate_action(raw, observation)
            fallbacks += int(fallback_reason is not None)
            action_sent = action.model_dump()
            observation_before = _observation_summary(observation)
            whole_turn_fallback = fallback_reason is not None and is_whole_turn_pass(action_sent)
            event = TurnRecord(
                turn=turn,
                action_raw=raw,
                action_sent=action_sent,
                observation_hash=_hash_observation(observation),
                observation_before=observation_before,
                fallback_reason=fallback_reason,
                action_class=classify_action(action_sent, observation_before, fallback_reason),
                fallback_inferred=inferred_fallback(
                    action_sent, {"fallback_reason": fallback_reason}
                ),
                lost_action_count=(command_count(raw) if whole_turn_fallback else 0),
                exception=exception,
                latency_ms=latency_ms,
            )
            records.append(event)
            try:
                observation = environment.step(event.action_sent)
                event.observation_after = _observation_summary(observation)
                opp_act = getattr(environment, "last_opponent_action", None)
                if isinstance(opp_act, dict):
                    event.opponent_action_sent = opp_act
            except Exception as exc:
                errors += 1
                status = "environment_error"
                event.exception = f"{type(exc).__name__}: {exc}"
            for reporter in self.reporters:
                reporter.on_turn(event)
            if status == "environment_error":
                break
        else:
            status = "incomplete"
        if environment.finished() and raw_result is None:
            raw_result = environment.result()
            if status == "incomplete":
                status = _infer_status(raw_result)
        finalize_cycle = getattr(agent, "finalize_cycle", None)
        if callable(finalize_cycle):
            finalize_cycle(observation)
        record = EpisodeRecord(
            episode_id=episode_id,
            seed=self.config.seed,
            agent=agent_name,
            opponent=opponent_name,
            status=status,
            turns=len(records),
            configuration=self.config.configuration,
            result=_normalize_result(raw_result),
            raw_result=raw_result,
            errors=errors,
            fallbacks=fallbacks,
            metrics=_metrics(records, observation, agent),
            turns_log=records if self.config.log_turns else [],
        )
        for reporter in self.reporters:
            reporter.on_episode(record, self.config)
        return record


def _act(agent: Agent | Callable[[dict[str, Any]], Any], observation: dict[str, Any]) -> Any:
    if callable(agent) and not hasattr(agent, "act"):
        callable_agent = cast(Callable[[dict[str, Any]], Any], agent)
        return callable_agent(observation)
    return cast(Agent, agent).act(observation)


def _hash_observation(observation: dict[str, Any]) -> str:
    return sha256(repr(sorted(observation.items())).encode()).hexdigest()[:16]


def _normalize_result(result: Any) -> dict[str, Any] | None:
    return result if isinstance(result, dict) else None


def _infer_status(result: Any) -> EpisodeStatus:
    if isinstance(result, dict) and result.get("winner") in {0, "agent", "self"}:
        return "win"
    if isinstance(result, dict) and result.get("winner") in {1, "opponent"}:
        return "loss"
    return "tie"


def _metrics(
    records: list[TurnRecord], observation: dict[str, Any], agent: Any | None = None
) -> dict[str, Any]:
    """Portable evidence summary; official-only fields stay nullable/omitted."""
    actions: dict[str, int] = {}
    for record in records:
        command = record.action_sent.get("farmer", ["PASS"])
        operation = command[0] if command and isinstance(command[0], str) else "PASS"
        actions[operation] = actions.get(operation, 0) + 1
        for hand in record.action_sent.get("hands", []):
            if hand and isinstance(hand[0], str):
                actions[hand[0]] = actions.get(hand[0], 0) + 1
        for order in record.action_sent.get("market", []):
            if order and isinstance(order[0], str):
                actions[order[0]] = actions.get(order[0], 0) + 1
    latencies = [record.latency_ms for record in records if record.latency_ms is not None]
    private_raw = observation.get("private")
    private: dict[str, Any] = private_raw if isinstance(private_raw, dict) else {}
    player_raw = observation.get("player", 0)
    player = player_raw if isinstance(player_raw, int) else 0
    farms_raw = observation.get("farms")
    farms: list[Any] = farms_raw if isinstance(farms_raw, list) else []
    farm = farms[player] if isinstance(player, int) and 0 <= player < len(farms) else {}
    result = {
        "action_counts": actions,
        "behavior": summarize_turns(records),
        "economic": _economic_metrics(records),
        "latency_ms": {
            "mean": sum(latencies) / len(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "final_shed": private.get("shed", {}) if isinstance(private.get("shed"), dict) else {},
        "final_seeds": private.get("seeds", {}) if isinstance(private.get("seeds"), dict) else {},
        "final_money": farm.get("money") if isinstance(farm, dict) else None,
        "portfolio": _portfolio_metrics(records, observation),
    }
    cycle_metrics = getattr(agent, "cycle_metrics", None)
    if callable(cycle_metrics):
        result["cycle"] = cycle_metrics()
    return result


def _portfolio_metrics(records: list[TurnRecord], observation: dict[str, Any]) -> dict[str, Any]:
    """Comparable strategy metrics derived from normalized turn snapshots."""
    sales_value = 0
    used_units = 0
    available_units = 0
    for record in records:
        before = record.observation_before
        prices = before.get("prices", {}) if isinstance(before.get("prices"), dict) else {}
        commands = [
            record.action_sent.get("farmer", ["PASS"]),
            *record.action_sent.get("hands", []),
        ]
        available_units += len(commands)
        used_units += sum(1 for command in commands if command and command[0] != "PASS")
        for order in record.action_sent.get("market", []):
            if len(order) >= 3 and order[0] == "SELL" and isinstance(order[1], str):
                quantity = int(order[2]) if isinstance(order[2], int) else 1
                sales_value += quantity * int(prices.get(order[1], 0))
    final = _observation_summary(observation)
    return {
        "animals": final.get("animal_count", 0),
        "crops": final.get("crop_count", 0),
        "hands": len(final.get("hands") or []),
        "sales_value": sales_value,
        "feeding_lost": final.get("hungry_animals", 0),
        "animals_escaped": final.get("escaped_animals", 0),
        "irrigation_pending": final.get("irrigation_pending", 0),
        "stock_wasted": final.get("stock_wasted", 0),
        "hand_utilization": used_units / available_units if available_units else 0.0,
    }


def _economic_metrics(records: list[TurnRecord]) -> dict[str, Any]:
    """Daily evidence for strategy promotion; values derive only from turn records."""
    daily: dict[int, dict[str, Any]] = {}
    capital: Counter[str] = Counter()
    harvested_actions = 0
    shed_operations = 0
    idle_actions = 0
    all_items = [
        "WHEAT",
        "CARROT",
        "TOMATO",
        "STRAWBERRY",
        "MELON",
        "MILK",
        "WOOL",
        "EGG",
        "FERTILIZER",
    ]
    item_lifecycle: dict[str, dict[str, Any]] = {
        item: {
            "price_history": {},
            "plants": [],
            "harvests": [],
            "sales": [],
            "opp_sales": [],
        }
        for item in all_items
    }

    for record in records:
        before = record.observation_before
        after = record.observation_after
        raw_day = before.get("day")
        day = raw_day if isinstance(raw_day, int) else -1
        hour = before.get("hour", 0)
        prices = before.get("prices", {})
        if isinstance(prices, dict):
            for item in all_items:
                if item in prices and day not in item_lifecycle[item]["price_history"]:
                    item_lifecycle[item]["price_history"][day] = prices[item]

        if day not in daily:
            daily[day] = {
                "money_start": before.get("money"),
                "money_end": before.get("money"),
                "market_orders": Counter(),
                "action_counts": Counter(),
            }
        entry = daily[day]
        entry["money_end"] = after.get("money", entry["money_end"])

        farmer_pos = before.get("farmer")
        hands_pos = before.get("hands", [])
        worker_positions = [farmer_pos] + (hands_pos if isinstance(hands_pos, list) else [])

        commands = [
            record.action_sent.get("farmer", ["PASS"]),
            *record.action_sent.get("hands", []),
        ]
        for w_idx, command in enumerate(commands):
            operation = command[0] if command and isinstance(command[0], str) else "PASS"
            entry["action_counts"][operation] += 1
            harvested_actions += int(operation == "HARVEST")
            shed_operations += int(operation in {"PICKUP", "DROP"})
            idle_actions += int(operation == "PASS")

            raw_pos = worker_positions[w_idx] if w_idx < len(worker_positions) else None
            pos = list(raw_pos) if isinstance(raw_pos, list | tuple) else [0, 0]
            if operation == "PLANT" and len(command) > 1 and isinstance(command[1], str):
                crop_name = command[1].upper()
                if crop_name in item_lifecycle:
                    item_lifecycle[crop_name]["plants"].append(
                        {"day": day, "hour": hour, "pos": pos}
                    )

        for order in record.action_sent.get("market", []):
            if not order or not isinstance(order[0], str):
                continue
            operation = order[0]
            quantity = int(order[2]) if len(order) > 2 and isinstance(order[2], int) else 1
            entry["market_orders"][operation] += quantity
            if operation in {"BUY_ANIMAL", "BUY_PRODUCT", "BUY_SEED", "HIRE", "BUY_LAND"}:
                capital[operation] += quantity
            if operation == "SELL" and len(order) > 1 and isinstance(order[1], str):
                item_name = order[1].upper()
                if item_name in item_lifecycle:
                    unit_price = prices.get(item_name, 0) if isinstance(prices, dict) else 0
                    item_lifecycle[item_name]["sales"].append(
                        {
                            "day": day,
                            "hour": hour,
                            "quantity": quantity,
                            "price": unit_price,
                        }
                    )

        for order in record.opponent_action_sent.get("market", []):
            if not order or not isinstance(order[0], str):
                continue
            operation = order[0]
            if operation == "SELL" and len(order) > 1 and isinstance(order[1], str):
                item_name = order[1].upper()
                if item_name in item_lifecycle:
                    quantity = int(order[2]) if len(order) > 2 and isinstance(order[2], int) else 1
                    unit_price = prices.get(item_name, 0) if isinstance(prices, dict) else 0
                    item_lifecycle[item_name]["opp_sales"].append(
                        {
                            "day": day,
                            "hour": hour,
                            "quantity": quantity,
                            "price": unit_price,
                        }
                    )

    days = []
    for day, entry in sorted(daily.items()):
        start = entry["money_start"]
        end = entry["money_end"]
        days.append(
            {
                "day": day,
                "money_start": start,
                "money_end": end,
                "money_delta": end - start
                if isinstance(start, int | float) and isinstance(end, int | float)
                else None,
                "market_orders": dict(entry["market_orders"]),
                "action_counts": dict(entry["action_counts"]),
            }
        )
    return {
        "daily": days,
        "capital_investment_orders": dict(capital),
        "harvested_actions": harvested_actions,
        "shed_operations": shed_operations,
        "idle_actions": idle_actions,
        "items": item_lifecycle,
    }


def _observation_summary(observation: dict[str, Any]) -> dict[str, Any]:
    """Small, replay-safe state snapshot for diagnosis without storing raw state."""
    player = observation.get("player")
    farms = observation.get("farms")
    farm = (
        farms[player]
        if isinstance(player, int) and isinstance(farms, list) and 0 <= player < len(farms)
        else {}
    )
    private = observation.get("private") if isinstance(observation.get("private"), dict) else {}
    tiles_raw = farm.get("tiles") if isinstance(farm, dict) else None
    tiles: list[Any] = tiles_raw if isinstance(tiles_raw, list) else []
    counts: dict[str, int] = {}
    animal_count = 0
    crop_count = 0
    mature_crops = 0
    hungry_animals = 0
    irrigation_pending = 0
    escaped_animals = 0
    fertilizer_pending = 0
    inventory_units = 0
    for row in tiles:
        if not isinstance(row, list):
            continue
        for tile in row:
            kind = (
                "EMPTY"
                if tile is None
                else tile.get("kind", "UNKNOWN")
                if isinstance(tile, dict)
                else str(tile)
            )
            counts[kind] = counts.get(kind, 0) + 1
            if isinstance(tile, dict):
                animal_count += int(bool(tile.get("animal")))
                crop_count += int(tile.get("kind") == "PLANT")
                mature_crops += int(tile.get("kind") == "PLANT" and tile.get("yield_units", 0) > 0)
                hungry_animals += int(bool(tile.get("animal")) and not tile.get("fed_today", False))
                irrigation_pending += int(
                    tile.get("kind") == "PLANT" and not tile.get("watered_today", False)
                )
                escaped_animals += int(tile.get("kind") == "ESCAPED")
                fertilizer_pending += int(bool(tile.get("fertilizer_available")))
    inventories = private.get("inventories", []) if isinstance(private, dict) else []
    if isinstance(inventories, list):
        inventory_units = sum(
            sum(int(amount) for amount in inventory.values() if isinstance(amount, int | float))
            for inventory in inventories
            if isinstance(inventory, dict)
        )
    shed = private.get("shed", {}) if isinstance(private, dict) else {}
    wheat = int(shed.get("WHEAT", 0)) if isinstance(shed, dict) else 0
    feed_deficit = max(0, animal_count - wheat - inventory_units)
    return {
        "day": observation.get("day"),
        "hour": observation.get("hour"),
        "step": observation.get("step"),
        "money": farm.get("money") if isinstance(farm, dict) else None,
        "farmer": farm.get("farmer") if isinstance(farm, dict) else None,
        "hands": farm.get("hands") if isinstance(farm, dict) else [],
        "tile_counts": counts,
        "shed": private.get("shed", {}) if isinstance(private, dict) else {},
        "seeds": private.get("seeds", {}) if isinstance(private, dict) else {},
        "unit_inventories": private.get("inventories", []) if isinstance(private, dict) else [],
        "prices": observation.get("market", {}).get("prices", {})
        if isinstance(observation.get("market"), dict)
        else {},
        "animal_count": animal_count,
        "crop_count": crop_count,
        "mature_crops": mature_crops,
        "hungry_animals": hungry_animals,
        "irrigation_pending": irrigation_pending,
        "escaped_animals": escaped_animals,
        "fertilizer_pending": fertilizer_pending,
        "inventory_units": inventory_units,
        "feed_deficit": feed_deficit,
        "stock_wasted": 0,
    }
