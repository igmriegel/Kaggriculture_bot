"""Deterministic hybrid portfolio planner.

V3 deliberately lives beside :mod:`leader_v2`: it is useful for benchmark
comparisons, but cannot silently change the submission candidate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from agent.core.contracts import Action
from agent.core.state import NormalizedState
from agent.domain.economics import marginal_sale_values
from agent.engines.leader_v2 import (
    _ANIMAL_COST,
    LeaderV2Config,
    LeaderV2Engine,
    ProductionGoal,
    Task,
)

_V3_SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}


@dataclass(frozen=True)
class LeaderV3Config(LeaderV2Config):
    """Tunable safety margins for the hybrid portfolio policy."""

    opponent_market_buffer: int = 2
    shed_safety_buffer: int = 4
    land_roi_horizon: int = 8
    max_crop_slots: int = 16


class LeaderV3Engine(LeaderV2Engine):
    """Choose a mixed crop/animal portfolio from the current daily state."""

    def __init__(self, config: LeaderV3Config | None = None) -> None:
        super().__init__(config or LeaderV3Config())

    @property
    def v3_config(self) -> LeaderV3Config:
        return cast(LeaderV3Config, self.v2_config)

    def act(self, observation: dict[str, Any]) -> dict[str, Any]:
        state = NormalizedState.from_observation(observation)
        goals = self._goals(state)
        tasks = self._tasks(state, goals)
        commands = self._allocate(state, tasks)
        return Action(
            farmer=commands[0],
            hands=commands[1:],
            market=self._build_market_orders(state, goals, tasks),
        ).model_dump()

    def _goals(self, state: NormalizedState) -> tuple[ProductionGoal, ...]:
        horizon = max(0, self.v3_config.closing_day - state.day)
        empty = min(self.v3_config.max_crop_slots, self._empty_tiles(state))
        choices = self._crop_portfolio(state, horizon)
        goals: list[ProductionGoal] = []
        remaining = empty
        for crop, quantity in choices:
            quantity = min(quantity, remaining)
            if quantity:
                goals.append(ProductionGoal(f"plant_{crop.lower()}", quantity, state.day + 1))
                remaining -= quantity
        animals = self._animal_count(state)
        pending = self._pending_animals(state)
        # Animals scale only when the shed, pasture, and feed chain have room.
        target = min(self.v3_config.max_animals, animals + pending + self._animal_capacity(state))
        return (ProductionGoal("operational_animals", target, state.day + 4), *goals)

    def _crop_portfolio(self, state: NormalizedState, horizon: int) -> tuple[tuple[str, int], ...]:
        if horizon < 3:
            return ()
        slots = self._empty_tiles(state)
        if slots <= 0:
            return ()
        candidates = ("WHEAT", "CARROT", "MELON", "STRAWBERRY")
        maturity = {"WHEAT": 2, "CARROT": 2, "MELON": 10, "STRAWBERRY": 10}
        base = {"WHEAT": 25, "CARROT": 35, "MELON": 250, "STRAWBERRY": 120}
        scored = []
        for crop in candidates:
            if maturity[crop] > horizon:
                continue
            demand = state.demand.get(crop, 0)
            price = state.prices.get(crop, base[crop])
            # Cheap cash crops receive a small early-season priority; demand
            # and actual market price make the policy adapt to configurations.
            score = float(price) * (1.0 + min(2, demand) * 0.08) / maturity[crop]
            scored.append((score, crop))
        scored.sort(reverse=True)
        if not scored:
            return ()
        primary = scored[0][1]
        secondary = next((crop for _, crop in scored[1:] if crop != primary), None)
        primary_qty = max(1, min(slots, 8 if primary in {"MELON", "STRAWBERRY"} else 6))
        secondary_qty = 1 if secondary and slots > primary_qty else 0
        if secondary:
            return ((primary, primary_qty), (secondary, secondary_qty))
        return ((primary, primary_qty),)

    def _tasks(self, state: NormalizedState, goals: tuple[ProductionGoal, ...]) -> list[Task]:
        tasks = super()._tasks(state, goals)
        wanted = {goal.name.removeprefix("plant_").upper(): goal.quantity for goal in goals}
        # V2 already handles obligations first.  V3 trims speculative planting
        # so a portfolio can never consume seeds reserved for feed or harvest.
        planted = {crop: 0 for crop in wanted}
        result: list[Task] = []
        for task in tasks:
            if task.command[:1] == ["PLANT"] and len(task.command) > 1:
                crop = str(task.command[1])
                if crop not in planted or planted[crop] >= wanted[crop]:
                    continue
                planted[crop] += 1
            result.append(task)
        return result

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        budget = self._budget(state, tasks)
        orders = self._sales(state)
        spending = max(0, state.money - budget.reserve - self.v3_config.operating_cash_floor)
        if self._closing(state):
            return orders[: self.v3_config.max_orders]

        animal_goal = next(goal.quantity for goal in goals if goal.name == "operational_animals")
        ready = self._animal_chain_ready(state)
        if self._animal_count(state) + self._pending_animals(state) < animal_goal and ready:
            animal = "COW" if self._animal_count(state) % 2 else "SHEEP"
            feed = state.shed.get("WHEAT", 0) + sum(
                inv.get("WHEAT", 0) for inv in state.unit_inventories
            )
            feed_needed = max(0, self._animal_count(state) + 1 - feed)
            feed_price = int(state.prices.get("WHEAT", 25))
            if spending >= _ANIMAL_COST[animal] + feed_needed * feed_price:
                if feed_needed:
                    orders.append(["BUY_PRODUCT", "WHEAT", feed_needed])
                    spending -= feed_needed * feed_price
                orders.append(["BUY_ANIMAL", animal, 1])
                spending -= _ANIMAL_COST[animal]

        for goal in goals:
            if not goal.name.startswith("plant_"):
                continue
            crop = goal.name.removeprefix("plant_").upper()
            shortfall = min(max(0, goal.quantity - state.seeds.get(crop, 0)), 6)
            quantity = min(shortfall, spending // _V3_SEED_COST[crop])
            if quantity:
                orders.append(["BUY_SEED", crop, int(quantity)])
                spending -= int(quantity) * _V3_SEED_COST[crop]

        productive = sum(task.priority < 10 for task in tasks)
        target = min(self.v3_config.max_hands, max(1, min(productive, 1 + productive // 8)))
        prospective = len(state.hand_positions)
        while (
            state.hour == 1
            and productive > len(state.units()) + 2
            and prospective < target
            and len(orders) < self.v3_config.max_orders
        ):
            cost = self._hire_cost(state.hires_today + prospective - len(state.hand_positions))
            if spending < cost + 250:
                break
            orders.append(["HIRE"])
            spending -= cost
            prospective += 1

        if self._land_has_return(state, productive, spending):
            orders.append(["BUY_LAND"])
        return orders[: self.v3_config.max_orders]

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        del projected
        orders: list[list[Any]] = []
        pressure = sum(state.shed.values()) >= (
            state.shed_capacity - self.v3_config.shed_safety_buffer
        )
        products = {
            "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
            "EGG", "MILK", "WOOL", "FERTILIZER",
        }
        for item, amount in sorted(state.shed.items()):
            if amount <= 0 or item not in products:
                continue
            retain = self._animal_count(state) if item == "WHEAT" else 0
            quantity = max(0, amount - retain)
            values = marginal_sale_values(
                item,
                state.market_inventory.get(item, 10_000),
                quantity,
                opponent_buffer=self.v3_config.opponent_market_buffer,
            )
            base = state.prices.get(item, 0)
            sell = sum(value <= base or pressure for value in values)
            if state.money < self.v3_config.operating_cash_floor or self._closing(state):
                sell = quantity
            if sell:
                orders.append(["SELL", item, sell])
        return orders

    def _animal_capacity(self, state: NormalizedState) -> int:
        return sum(tile.kind == "PASTURE" and tile.animal is None for tile in state.tiles)

    def _animal_chain_ready(self, state: NormalizedState) -> bool:
        if self._animal_capacity(state) <= self._pending_animals(state):
            return False
        return sum(state.shed.values()) < (state.shed_capacity - 2)

    def _land_has_return(self, state: NormalizedState, productive: int, spending: int) -> bool:
        if len(state.unlocked_quadrants) >= 3 or productive < max(2, len(state.units())):
            return False
        costs = (1000, 2000, 4000)
        cost = costs[min(len(state.unlocked_quadrants) - 1, len(costs) - 1)]
        return spending >= cost and self.v3_config.land_roi_horizon * productive >= cost // 100


__all__ = ["LeaderV3Config", "LeaderV3Engine"]
