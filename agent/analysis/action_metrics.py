"""Shared action classification and idle/fallback evidence.

The runner, replay auditor, and HTML renderer intentionally use the same small
classifier.  A raw ``PASS`` is not necessarily wasted: a chain can be waiting
for a crop to mature or for stock/cash to arrive.  Conversely, a validator
fallback must remain visible even when the replacement action is safe.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any, Literal

ActionClass = Literal["productive", "movement", "legitimate_wait", "fallback_pass", "idle_pass"]

MOVEMENT_OPS = {"NORTH", "SOUTH", "EAST", "WEST"}
PRODUCTIVE_UNIT_OPS = {
    "PICKUP",
    "PLACE",
    "PLANT",
    "WATER",
    "HARVEST",
    "FERTILIZE",
    "BUILD_COOP",
    "BUILD_PASTURE",
    "FEED",
    "COLLECT_FERTILIZER",
    "CARE",
    "DIG",
    "DROP",
}
PRODUCTIVE_MARKET_OPS = {
    "BUY_SEED",
    "BUY_ANIMAL",
    "BUY_PRODUCT",
    "SELL",
    "HIRE",
    "BUY_LAND",
}


def action_operations(action: Any) -> list[str]:
    """Return all unit and market operation names in an action-shaped value."""
    if not isinstance(action, dict):
        return []
    operations: list[str] = []
    units = [action.get("farmer"), *(action.get("hands", []) or [])]
    for command in units:
        if isinstance(command, list) and command and isinstance(command[0], str):
            operations.append(command[0])
    for order in action.get("market", []) or []:
        if isinstance(order, list) and order and isinstance(order[0], str):
            operations.append(order[0])
    return operations


def is_whole_turn_pass(action: Any) -> bool:
    operations = action_operations(action)
    return bool(operations) and all(operation == "PASS" for operation in operations)


def command_count(action: Any) -> int:
    """Count command slots, including malformed slots that a fallback replaced."""
    if not isinstance(action, dict):
        return 1
    count = 0
    for key in ("farmer", "hands", "market"):
        value = action.get(key)
        if key == "farmer":
            count += 1 if value is not None else 0
        elif isinstance(value, list):
            count += len(value)
    return max(1, count)


def pending_chain(snapshot: dict[str, Any]) -> bool:
    """Whether a PASS can be explained by a known, unfinished game chain."""
    positive_keys = (
        "hungry_animals",
        "irrigation_pending",
        "mature_crops",
        "fertilizer_pending",
        "inventory_units",
        "feed_deficit",
    )
    if any(_positive(snapshot.get(key)) for key in positive_keys):
        return True
    crop_count = _integer(snapshot.get("crop_count"))
    mature_crops = _integer(snapshot.get("mature_crops"))
    return crop_count > mature_crops or _positive(snapshot.get("animal_count"))


def classify_action(
    action: Any,
    observation_before: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
) -> ActionClass:
    """Classify one turn at the turn level rather than counting unit PASSes."""
    if fallback_reason is not None and is_whole_turn_pass(action):
        return "fallback_pass"
    operations = action_operations(action)
    if any(
        operation in PRODUCTIVE_MARKET_OPS or operation in PRODUCTIVE_UNIT_OPS
        for operation in operations
    ):
        return "productive"
    if any(operation in MOVEMENT_OPS for operation in operations):
        return "movement"
    if operations and all(operation == "PASS" for operation in operations):
        if pending_chain(observation_before or {}):
            return "legitimate_wait"
        return "idle_pass"
    return "idle_pass"


def inferred_fallback(action: Any, record: dict[str, Any] | None = None) -> bool:
    """Infer fallback evidence from local/replay metadata without over-claiming."""
    metadata = record or {}
    explicit = any(
        metadata.get(key)
        for key in ("fallback_reason", "fallback", "validation_error", "sanitized")
    )
    # A replay can omit an action when the environment received the validator's
    # safe PASS after an engine/serialization failure.  A normal all-PASS action
    # is deliberately not inferred as a fallback because it is indistinguishable
    # from a legitimate wait.
    return bool(
        explicit
        or (record is not None and record.get("action") is None and "observation" in record)
    )


def summarize_turns(records: Iterable[Any]) -> dict[str, Any]:
    """Aggregate idle, PASS streak, heatmap, fallback, and lost-action evidence."""
    classes: Counter[str] = Counter()
    heatmap: dict[str, Counter[str]] = {}
    pass_streak = 0
    longest_pass_streak = 0
    lost_actions = 0
    fallback_count = 0
    for item in records:
        action = getattr(item, "action_sent", None)
        before = getattr(item, "observation_before", None)
        fallback_reason = getattr(item, "fallback_reason", None)
        if isinstance(item, dict):
            action = item.get("action_sent", item.get("action"))
            before = item.get("observation_before", item.get("observation", {}))
            fallback_reason = item.get("fallback_reason")
            classification = item.get("action_class")
        else:
            classification = getattr(item, "action_class", None)
        if classification is None:
            classification = classify_action(action, before, fallback_reason)
        classes[str(classification)] += 1
        if str(classification) in {"legitimate_wait", "idle_pass", "fallback_pass"}:
            pass_streak += 1
            longest_pass_streak = max(longest_pass_streak, pass_streak)
        else:
            pass_streak = 0
        day = _integer(before.get("day")) if isinstance(before, dict) else 0
        hour = _integer(before.get("hour")) if isinstance(before, dict) else 0
        cell = heatmap.setdefault(f"{day}:{hour}", Counter())
        cell[str(classification)] += 1
        if fallback_reason is not None:
            fallback_count += 1
            if is_whole_turn_pass(action):
                raw = getattr(item, "action_raw", None)
                if isinstance(item, dict):
                    raw = item.get("action_raw", item.get("action"))
                lost_actions += command_count(raw)
    total = sum(classes.values())
    serialized_heatmap = {key: dict(value) for key, value in sorted(heatmap.items())}
    return {
        "turn_classes": dict(classes),
        "idle_turns": classes["idle_pass"],
        "idle_turn_percentage": classes["idle_pass"] / total * 100 if total else 0.0,
        "pass_turns": classes["legitimate_wait"] + classes["idle_pass"] + classes["fallback_pass"],
        "legitimate_wait_turns": classes["legitimate_wait"],
        "fallback_pass_turns": classes["fallback_pass"],
        "fallbacks_inferred": fallback_count,
        "lost_actions": lost_actions,
        "longest_pass_streak": longest_pass_streak,
        "pass_heatmap": serialized_heatmap,
        "heatmap": serialized_heatmap,
    }


def _positive(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


__all__ = [
    "ActionClass",
    "PRODUCTIVE_MARKET_OPS",
    "PRODUCTIVE_UNIT_OPS",
    "MOVEMENT_OPS",
    "action_operations",
    "classify_action",
    "command_count",
    "inferred_fallback",
    "is_whole_turn_pass",
    "pending_chain",
    "summarize_turns",
]
