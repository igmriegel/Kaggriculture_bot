"""Leader V9.1 Leader Engine: Crop Dusta's Aggressive Opening."""

from __future__ import annotations

from typing import Any

from agent.core.state import NormalizedState
from agent.domain.economics import SHOPS
from agent.engines.leader_v2 import ProductionGoal, Task
from agent.engines.leader_v9 import LeaderV9Config, LeaderV9Engine

_ANIMAL_COST = {"COW": 400, "SHEEP": 500, "GOOSE": 300}


class LeaderV9_1LeaderConfig(LeaderV9Config):
    wheat_bias: float = 1.2
    carrot_pivot_day: int = 20
    carrot_roi_multiplier: float = 1.8
    max_unlocked_quadrants: int = 3  # NW, NE, SW
    max_active_hands: int = 4


class LeaderV9_1LeaderEngine(LeaderV9Engine):
    def __init__(self, config: LeaderV9_1LeaderConfig | None = None) -> None:
        self.leader_config = config or LeaderV9_1LeaderConfig()
        super().__init__(self.leader_config)

    def _goals(self, state: NormalizedState) -> tuple[ProductionGoal, ...]:
        # Day 29 closing: no new operational goals, just clear out everything
        if state.day >= 29:
            return ()

        # Re-use V9 base animal logic but cap quadrants at max_unlocked_quadrants
        horizon = max(0, 30 - state.day)
        empty = self._empty_tiles(state)

        # Force cap on quadrants to max_unlocked_quadrants
        quadrants = min(len(state.unlocked_quadrants), self.leader_config.max_unlocked_quadrants)
        max_pastures = 4 if quadrants == 1 else (8 if quadrants == 2 else 14)
        current_animals = self._animal_count(state) + self._pending_animals(state)

        dairy_shops = sum(1 for shop in state.shops if "MILK" in SHOPS.get(shop, ()))
        wool_shops = sum(1 for shop in state.shops if "WOOL" in SHOPS.get(shop, ()))

        opp_animals = sum(1 for t in state.opponent_tiles if t.animal in _ANIMAL_COST)
        if opp_animals >= 10:
            effective_max_animals = min(8, self.leader_config.max_animals)
        else:
            effective_max_animals = self.leader_config.max_animals
        base_animal_target = 6 + (dairy_shops + wool_shops) * 2

        if horizon < 8:
            target_animals = current_animals
        else:
            target_animals = min(max_pastures, base_animal_target, effective_max_animals)

        goals: list[ProductionGoal] = [
            ProductionGoal("operational_animals", target_animals, state.day + 3)
        ]

        crop_plan = self._dynamic_crop_portfolio(state, horizon, empty)
        for crop, qty in crop_plan:
            if qty > 0:
                goals.append(ProductionGoal(f"plant_{crop.lower()}", qty, state.day + 1))

        return tuple(goals)

    def _dynamic_crop_portfolio(
        self, state: NormalizedState, horizon: int, empty_slots: int
    ) -> list[tuple[str, int]]:
        # Day 29 closing: no new planting
        if state.day >= 29:
            return []
        return super()._dynamic_crop_portfolio(state, horizon, empty_slots)

    def _calculate_marginal_tile_roi(
        self, crop: str, state: NormalizedState, horizon: int, current_planned_tiles: int
    ) -> float:
        # Recompute base ROI without V9 labor friction penalties, but with V8 base logic.
        # V9 inherited: WHEAT penalty (-12), CARROT penalty (-6), STRAWBERRY boost (*1.5),
        # MELON boost (*1.3). We want to remove the WHEAT/CARROT labor friction penalties,
        # and also remove the MELON boost.

        # Call LeaderV8Engine's method to get a clean baseline ROI:
        base_roi = super(LeaderV9Engine, self)._calculate_marginal_tile_roi(
            crop, state, horizon, current_planned_tiles
        )

        # STRAWBERRY early game boost: keep V8/V9 behavior (1.5x)
        if crop == "STRAWBERRY" and state.day < 12:
            base_roi = base_roi * 1.5

        # Dynamic Wheat Bias & Labor Friction:
        # Combined detection: reduce bias if opponent has >= 5 wheat tiles
        # OR market inventory of WHEAT > 10,150.
        # Apply a dynamic labor penalty: if we have too much wheat relative to
        # workforce size, increase penalty to 8.0 to prevent bottlenecking.
        if crop == "WHEAT":
            total_workers = 1 + len(state.hand_positions)
            limit = 3 * total_workers
            penalty = 8.0 if current_planned_tiles >= limit else 1.0

            opp_wheat_tiles = sum(
                1 for t in state.opponent_tiles if t.kind == "PLANT" and t.crop == "WHEAT"
            )
            market_wheat_inv = state.market_inventory.get("WHEAT", 10000)

            if opp_wheat_tiles >= 5 or market_wheat_inv > 10150:
                bias = 1.0
            else:
                bias = self.leader_config.wheat_bias

            return max(0.0, base_roi - penalty) * bias

        # CARROT base labor friction penalty:
        if crop == "CARROT" and state.day < self.leader_config.carrot_pivot_day:
            return max(0.0, base_roi - 3.0)

        # Shop-Aware Carrot Pivot:
        # Boost CARROT after Day 20 if at least one shop accepting CARROT
        # (PET_CAFE or FARMERS_MARKET) is unlocked.
        if crop == "CARROT" and state.day >= self.leader_config.carrot_pivot_day:
            carrot_shops = any(
                any(c == "CARROT" for c in SHOPS.get(shop, ())) for shop in state.shops
            )
            if carrot_shops:
                return base_roi * self.leader_config.carrot_roi_multiplier

        return base_roi

    def _tasks(self, state: NormalizedState, goals: tuple[ProductionGoal, ...]) -> list[Task]:
        # Day 29: Only allow harvesting and feeding/care tasks, no planting/watering
        if state.day >= 29:
            tasks = super()._tasks(state, goals)
            disallowed = ("PLANT", "WATER", "DIG", "BUILD_PASTURE", "BUILD_COOP")
            tasks = [t for t in tasks if not any(op in t.command for op in disallowed)]
            return tasks

        return super()._tasks(state, goals)

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        # 1. Deterministic Day 0 Opening Book
        if state.day == 0:
            if state.hour == 1:
                return [
                    ["HIRE"],
                    ["HIRE"],
                    ["HIRE"],
                    ["HIRE"],
                    ["BUY_ANIMAL", "COW", 2],
                    ["BUY_ANIMAL", "SHEEP", 2],
                    ["BUY_SEED", "STRAWBERRY", 3],
                    ["BUY_SEED", "WHEAT", 15],
                ]
            elif state.hour == 2:
                return [
                    ["BUY_PRODUCT", "WHEAT", 4],
                    ["BUY_ANIMAL", "COW", 1],
                ]
            elif state.hour == 3:
                return [
                    ["BUY_PRODUCT", "WHEAT", 4],
                ]
            return []

        # 2. Day 29 Final Sell-off: Sell all assets, including animal feed
        # reserves, and stop all buys/planting.
        if state.day >= 29:
            # We clear out everything in the shed
            orders: list[list[Any]] = []
            for item, amount in sorted(state.shed.items()):
                if amount > 0:
                    orders.append(["SELL", item, amount])
            return orders[:10]  # Max 10 orders per turn

        # 3. Mid/Late-game market orders: inherit and apply workforce matching
        # and capped land buys.
        orders = super()._build_market_orders(state, goals, tasks)

        # Land Expansion Cap: If BUY_LAND is present in orders but we already
        # have max quadrants, remove it.
        if len(state.unlocked_quadrants) >= self.leader_config.max_unlocked_quadrants:
            orders = [o for o in orders if o[0] != "BUY_LAND"]

        # Workforce matching:
        total_workers = 1 + len(state.hand_positions)
        opp_workers = 1 + state.opponent_hand_count

        # Calculate pending workload actions:
        unwatered_crops = sum(1 for t in state.tiles if t.kind == "PLANT" and not t.watered_today)
        unfed_animals = sum(
            1 for t in state.tiles if t.kind == "PASTURE" and t.animal and not t.fed_today
        )
        harvestable = sum(
            1 for t in state.tiles if t.kind == "PLANT" and t.yield_units and t.yield_units > 0
        )
        pending_actions = unwatered_crops + unfed_animals + harvestable

        if (
            total_workers < self.leader_config.max_active_hands
            and (total_workers < opp_workers or pending_actions >= 8)
            and state.money >= 300
            and not any(o[0] == "HIRE" for o in orders)
            and len(orders) < 10
        ):
            orders.append(["HIRE"])

        # Shop-Driven Animal Priority:
        for idx, o in enumerate(orders):
            if o[0] == "BUY_ANIMAL":
                # Check shops
                yarn_shops = sum(1 for shop in state.shops if "WOOL" in SHOPS.get(shop, ()))
                dairy_shops = sum(1 for shop in state.shops if "MILK" in SHOPS.get(shop, ()))

                current_cows = sum(1 for t in state.tiles if t.animal == "COW")
                current_sheep = sum(1 for t in state.tiles if t.animal == "SHEEP")

                if yarn_shops == 0 and dairy_shops > 0:
                    preferred_animal = "COW"
                elif dairy_shops == 0 and yarn_shops > 0:
                    preferred_animal = "SHEEP"
                else:
                    preferred_animal = "COW" if current_cows <= current_sheep else "SHEEP"

                orders[idx] = ["BUY_ANIMAL", preferred_animal, o[2]]

        return orders[:10]
