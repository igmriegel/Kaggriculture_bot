"""In-process continuity memory for cycle-oriented engines.

The official observation remains authoritative.  This module only stores the
engine's last intent and a small amount of derived bookkeeping so the next
decision can distinguish a completed step from a no-op or a stale plan.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

from agent.core.state import NormalizedState, Tile

CommitmentStatus = Literal["planned", "in_progress", "confirmed", "blocked", "abandoned"]


@dataclass
class Commitment:
    key: str
    kind: str
    status: CommitmentStatus
    target: tuple[int, int] | None = None
    expected: dict[str, Any] = field(default_factory=dict)
    stage: str = "planned"
    created_day: int = 0
    updated_day: int = 0
    attempts: int = 0
    last_operation: str | None = None


@dataclass(frozen=True)
class Intent:
    key: str
    kind: str
    operation: str
    target: tuple[int, int] | None
    item: str | None
    quantity: int
    before: NormalizedState
    unit_index: int | None = None


@dataclass
class MemoryMetrics:
    commitments_created: int = 0
    commitments_confirmed: int = 0
    commitments_replanned: int = 0
    commitments_abandoned: int = 0
    plant_harvest_sale_cycles: int = 0
    animal_complete_cycles: int = 0
    actions_repeated_without_progress: int = 0
    plan_observation_divergences: int = 0
    cash_reserved: int = 0
    cash_spent: int = 0


class CycleMemory:
    """Small, resettable memory attached to one engine instance."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.commitments: dict[str, Commitment] = {}
        self.pending_intents: list[Intent] = []
        self.last_state: NormalizedState | None = None
        self.last_step: int | None = None
        self.last_action_signature: tuple[Any, ...] | None = None
        self.last_action_progress = True
        self.metrics = MemoryMetrics()
        self.reservations: dict[str, int] = {
            "next_feed": 0,
            "next_hire": 0,
            "seeds": 0,
            "operating": 0,
        }
        self.daily_hires = 0
        self.current_day: int | None = None

    def begin(self, state: NormalizedState) -> None:
        """Reconcile the previous turn and establish the current day."""
        if self._looks_like_new_episode(state):
            self.reset()
        self._reconcile(state)
        if self.current_day != state.day:
            self.current_day = state.day
            self.daily_hires = state.hires_today
        else:
            self.daily_hires = max(self.daily_hires, state.hires_today)
        self._observe_cycles(state)
        self.last_state = state
        self.last_step = state.step

    def reset_for_episode(self) -> None:
        """Explicit hook used by the runner when an adapter starts an episode."""
        self.reset()

    def reserve_for(self, state: NormalizedState, *, seed_cost: int) -> int:
        """Compute protected cash without changing the policy's raw action yet."""
        feed_units = max(
            0,
            sum(tile.animal is not None for tile in state.tiles)
            - state.shed.get("WHEAT", 0)
            - sum(inv.get("WHEAT", 0) for inv in state.unit_inventories),
        )
        feed = feed_units * max(1, int(state.prices.get("WHEAT", 25)))
        next_hire = self._hire_cost(state.hires_today)
        seeds = seed_cost
        operating = 150
        self.reservations = {
            "next_feed": feed,
            "next_hire": next_hire,
            "seeds": seeds,
            "operating": operating,
        }
        self.metrics.cash_reserved = sum(self.reservations.values())
        return self.metrics.cash_reserved

    def record_action(
        self,
        state: NormalizedState,
        assignments: list[dict[str, Any]],
        market_orders: list[list[Any]],
    ) -> None:
        """Store only emitted intentions; no state is mutated optimistically."""
        intents: list[Intent] = []
        for assignment in assignments:
            command = assignment.get("command")
            if not isinstance(command, list) or not command or command[0] == "PASS":
                continue
            operation = command[0] if isinstance(command[0], str) else "UNKNOWN"
            target = assignment.get("target")
            target = target if isinstance(target, tuple) else None
            item = command[1] if len(command) > 1 and isinstance(command[1], str) else None
            tile = state.tile_at(target) if target is not None else None
            if operation == "HARVEST" and item is None and tile is not None:
                item = tile.crop or {
                    "GOOSE": "EGG",
                    "COW": "MILK",
                    "SHEEP": "WOOL",
                }.get(tile.animal or "")
            quantity = _quantity(command, default=1)
            key = self._task_key(state, operation, target, item)
            kind = (
                "plant"
                if operation == "PLANT"
                or (operation == "HARVEST" and tile and tile.kind == "PLANT")
                else "animal"
                if tile and tile.animal
                else "task"
            )
            commitment = self._ensure(
                key,
                kind,
                target,
                state.day,
                {"operation": operation, "item": item, "quantity": quantity},
            )
            commitment.status = "in_progress"
            commitment.last_operation = operation
            intents.append(
                Intent(
                    key=key,
                    kind=commitment.kind,
                    operation=operation,
                    target=target,
                    item=item,
                    quantity=quantity,
                    before=state,
                    unit_index=assignment.get("unit_index"),
                )
            )

        for order in market_orders:
            if not isinstance(order, list) or not order or not isinstance(order[0], str):
                continue
            operation = order[0]
            item = order[1] if len(order) > 1 and isinstance(order[1], str) else None
            quantity = _quantity(order, default=1)
            key = f"market:{state.step}:{operation}:{item or '-'}"
            commitment = self._ensure(
                key,
                "market",
                None,
                state.day,
                {"operation": operation, "item": item, "quantity": quantity},
            )
            commitment.status = "in_progress"
            commitment.last_operation = operation
            intents.append(Intent(key, "market", operation, None, item, quantity, state))

        self.pending_intents = intents
        signature = tuple(
            (intent.operation, intent.target, intent.item, intent.quantity) for intent in intents
        )
        if signature and signature == self.last_action_signature and not self.last_action_progress:
            self.metrics.actions_repeated_without_progress += 1
        self.last_action_signature = signature
        self.last_action_progress = False if intents else True

    def cycle_metrics(self) -> dict[str, Any]:
        statuses = Counter(commitment.status for commitment in self.commitments.values())
        return {
            "commitments_created": self.metrics.commitments_created,
            "commitments_confirmed": self.metrics.commitments_confirmed,
            "commitments_replanned": self.metrics.commitments_replanned,
            "commitments_abandoned": self.metrics.commitments_abandoned,
            "plant_harvest_sale_cycles": self.metrics.plant_harvest_sale_cycles,
            "animal_complete_cycles": self.metrics.animal_complete_cycles,
            "actions_repeated_without_progress": self.metrics.actions_repeated_without_progress,
            "plan_observation_divergences": self.metrics.plan_observation_divergences,
            "cash_reserved": self.metrics.cash_reserved,
            "cash_reserved_current": self.metrics.cash_reserved,
            "cash_spent": self.metrics.cash_spent,
            "commitment_status": dict(statuses),
            "active_commitments": sum(statuses[name] for name in ("planned", "in_progress")),
        }

    def is_blocked(
        self,
        state: NormalizedState,
        operation: str,
        target: tuple[int, int],
        item: str | None = None,
    ) -> bool:
        key = self._task_key(state, operation, target, item)
        commitment = self.commitments.get(key)
        return commitment is not None and commitment.status == "blocked"

    def _reconcile(self, state: NormalizedState) -> None:
        if self.last_state is None:
            return
        if state.money < self.last_state.money:
            self.metrics.cash_spent += self.last_state.money - state.money
        for intent in self.pending_intents:
            commitment = self.commitments.get(intent.key)
            if commitment is None:
                continue
            if self._effect_observed(intent, state):
                if commitment.status != "confirmed":
                    self.metrics.commitments_confirmed += 1
                commitment.status = "confirmed"
                commitment.stage = self._stage_for(intent.operation, intent.item)
                commitment.updated_day = state.day
                self.last_action_progress = True
                self._complete_downstream_cycle(intent, state)
            else:
                commitment.status = "blocked"
                commitment.updated_day = state.day
                commitment.attempts += 1
                self.metrics.commitments_replanned += 1
                self.metrics.plan_observation_divergences += 1
                self.last_action_progress = False
        self.pending_intents = []

    def _observe_cycles(self, state: NormalizedState) -> None:
        for tile in state.tiles:
            if tile.kind == "PLANT" and tile.crop and tile.planted_day is not None:
                key = f"plant:{tile.x}:{tile.y}:{tile.planted_day}"
                commitment = self._ensure(
                    key,
                    "plant",
                    (tile.x, tile.y),
                    tile.planted_day,
                    {
                        "crop": tile.crop,
                        "planted_day": tile.planted_day,
                        "maturity_day": tile.planted_day + _maturity(tile.crop),
                    },
                )
                if tile.yield_units > 0:
                    commitment.stage = "matured"
                    commitment.status = "confirmed"
            elif tile.animal:
                placed_day = _tile_day(tile, "placed_day", state.day)
                key = f"animal:{tile.x}:{tile.y}:{placed_day}"
                commitment = self._ensure(
                    key,
                    "animal",
                    (tile.x, tile.y),
                    placed_day,
                    {"animal": tile.animal, "placed_day": placed_day},
                )
                if tile.yield_units > 0:
                    commitment.stage = "produced"
                    commitment.status = "confirmed"
                elif tile.fed_today:
                    commitment.stage = "fed"
                elif tile.cared_today:
                    commitment.stage = "cared"

    def _complete_downstream_cycle(self, intent: Intent, state: NormalizedState) -> None:
        if intent.operation != "SELL" and intent.kind != "market":
            return
        if intent.operation != "SELL" or intent.item is None:
            return
        for commitment in self.commitments.values():
            if commitment.kind == "plant" and commitment.stage in {"harvested", "matured"}:
                if commitment.expected.get("crop") == intent.item:
                    commitment.stage = "sold"
                    commitment.status = "confirmed"
                    self.metrics.plant_harvest_sale_cycles += 1
                    return
            if commitment.kind == "animal" and commitment.stage == "produced":
                commitment.stage = "sold"
                commitment.status = "confirmed"
                self.metrics.animal_complete_cycles += 1
                return

    def _effect_observed(self, intent: Intent, state: NormalizedState) -> bool:
        before = intent.before
        op = intent.operation
        if op in {"NORTH", "SOUTH", "EAST", "WEST"}:
            positions = state.units()
            return (
                intent.unit_index is not None
                and intent.unit_index < len(positions)
                and positions[int(intent.unit_index)] != before.units()[int(intent.unit_index)]
            )
        if op in {
            "PLANT",
            "WATER",
            "HARVEST",
            "FEED",
            "CARE",
            "COLLECT_FERTILIZER",
            "BUILD_PASTURE",
            "BUILD_COOP",
            "DIG",
            "PLACE",
        }:
            tile = state.tile_at(intent.target) if intent.target is not None else None
            old = before.tile_at(intent.target) if intent.target is not None else None
            if op == "PLANT":
                return bool(tile and tile.kind == "PLANT" and tile.crop == intent.item)
            if op == "WATER":
                return bool(tile and tile.watered_today)
            if op == "HARVEST":
                return _inventory_total(state, intent.item) > _inventory_total(
                    before, intent.item
                ) or (old is not None and tile is not None and tile.kind is None)
            if op == "FEED":
                return bool(tile and tile.fed_today)
            if op == "CARE":
                return bool(tile and tile.cared_today)
            if op == "COLLECT_FERTILIZER":
                return bool(
                    old and old.fertilizer_available and (not tile or not tile.fertilizer_available)
                ) or _inventory_total(state, "FERTILIZER") > _inventory_total(before, "FERTILIZER")
            if op == "DIG":
                return bool(tile and tile.kind != "WEED") or (
                    old is not None and tile is not None and tile.kind is None
                )
            if op == "BUILD_PASTURE":
                return bool(tile and tile.kind == "PASTURE")
            if op == "BUILD_COOP":
                return bool(tile and tile.kind == "COOP")
            if op == "PLACE":
                return bool(tile and tile.animal)
        if op == "PICKUP":
            return _inventory_total(state, intent.item) > _inventory_total(
                before, intent.item
            ) or _shed_total(state, intent.item) < _shed_total(before, intent.item)
        if op == "DROP":
            if intent.item is None:
                before_units = sum(sum(inv.values()) for inv in before.unit_inventories)
                after_units = sum(sum(inv.values()) for inv in state.unit_inventories)
                return (
                    sum(state.shed.values()) > sum(before.shed.values())
                    or after_units < before_units
                )
            return _inventory_total(state, intent.item) < _inventory_total(
                before, intent.item
            ) or _shed_total(state, intent.item) > _shed_total(before, intent.item)
        if op == "SELL":
            return (
                _shed_total(state, intent.item) < _shed_total(before, intent.item)
                and state.money > before.money
            )
        if op in {"BUY_PRODUCT", "BUY_ANIMAL"}:
            return (
                _shed_total(state, intent.item) > _shed_total(before, intent.item)
                and state.money < before.money
            )
        if op == "BUY_SEED":
            return state.seeds.get(intent.item or "", 0) > before.seeds.get(intent.item or "", 0)
        if op == "HIRE":
            return (
                len(state.hand_positions) > len(before.hand_positions)
                or state.hires_today > before.hires_today
            )
        if op == "BUY_LAND":
            return len(state.unlocked_quadrants) > len(before.unlocked_quadrants)
        return False

    def _ensure(
        self,
        key: str,
        kind: str,
        target: tuple[int, int] | None,
        day: int,
        expected: dict[str, Any],
    ) -> Commitment:
        commitment = self.commitments.get(key)
        if commitment is None:
            commitment = Commitment(
                key, kind, "planned", target, expected, created_day=day, updated_day=day
            )
            self.commitments[key] = commitment
            self.metrics.commitments_created += 1
        return commitment

    def _task_key(
        self,
        state: NormalizedState,
        operation: str,
        target: tuple[int, int] | None,
        item: str | None,
    ) -> str:
        if target is None:
            return f"task:{state.day}:{operation}:{item or '-'}"
        tile = state.tile_at(target)
        if operation == "PLANT":
            return f"plant:{target[0]}:{target[1]}:{state.day}"
        if (
            operation == "HARVEST"
            and tile
            and tile.kind == "PLANT"
            and tile.planted_day is not None
        ):
            return f"plant:{target[0]}:{target[1]}:{tile.planted_day}"
        if operation == "HARVEST" and tile and tile.animal:
            return f"animal:{target[0]}:{target[1]}:{_tile_day(tile, 'placed_day', state.day)}"
        return f"task:{state.day}:{operation}:{target[0]}:{target[1]}"

    def _stage_for(self, operation: str, item: str | None) -> str:
        return {
            "PLANT": "planted",
            "WATER": "watered",
            "HARVEST": "harvested",
            "FEED": "fed",
            "CARE": "cared",
            "COLLECT_FERTILIZER": "collected",
            "PLACE": "placed",
            "DROP": "stored",
            "SELL": "sold",
        }.get(operation, "confirmed")

    def _looks_like_new_episode(self, state: NormalizedState) -> bool:
        if self.last_step is None:
            return False
        if state.step < self.last_step:
            return True
        return state.step == 0 and self.last_step != 0

    @staticmethod
    def _hire_cost(hired: int) -> int:
        first, second = 1, 1
        for _ in range(hired):
            first, second = second, first + second
        return first


def _maturity(crop: str) -> int:
    return {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}.get(crop, 0)


def _tile_day(tile: Tile, field: str, default: int) -> int:
    value = getattr(tile, field, None)
    return int(value) if isinstance(value, int) else default


def _quantity(command: list[Any], *, default: int) -> int:
    if len(command) >= 3:
        try:
            return max(1, int(command[2]))
        except (TypeError, ValueError):
            return default
    return default


def _inventory_total(state: NormalizedState, item: str | None) -> int:
    if not item:
        return 0
    return _shed_total(state, item) + sum(inv.get(item, 0) for inv in state.unit_inventories)


def _shed_total(state: NormalizedState, item: str | None) -> int:
    return state.shed.get(item or "", 0)


__all__ = ["Commitment", "CommitmentStatus", "CycleMemory"]
