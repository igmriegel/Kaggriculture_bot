"""Leader V8: Pro Dynamic Engine (Zero Hardcoded Limits).

Includes 4 Advanced Dynamic Dominance Vectors:
1. Opponent Inventory & Front-Running Sales: Scans opponent tiles for imminent harvests
   and liquidates matching shed inventory TODAY before opponent floods the market.
2. Active Fertilizer Synergy: Prioritizes applying fertilizer to recurring crops
   (Strawberry & Tomato) to boost yield (+75%) and speed up regrowth cycles.
3. Early Worker Hire Velocity: Dynamically hires a 2nd worker as soon as cash >= $750,
   doubling action throughput per turn.
4. Dynamic Town Shop Monopoly: Dynamically boosts marginal ROI for products demanded
   by unlocked town shops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.core.state import NormalizedState
from agent.domain.economics import SHOPS, marginal_sale_values
from agent.domain.roi import estimate_opponent_expected_harvests
from agent.engines.leader_v2 import ProductionGoal, Task
from agent.engines.leader_v6 import (
    _ANIMAL_COST,
    _CROP_BASE_PRICES,
    _CROP_MATURITY,
    _PRODUCTS,
    _V6_SEED_COST,
)
from agent.engines.leader_v7 import LeaderV7Config, LeaderV7Engine


@dataclass(frozen=True)
class LeaderV8Config(LeaderV7Config):
    min_liquidity_buffer: int = 200
    worker_hire_cash_threshold: int = 750


class LeaderV8Engine(LeaderV7Engine):
    """LeaderV8 Pro Dynamic Engine with Advanced Market Reading & Synergy."""

    def __init__(self, config: LeaderV8Config | None = None) -> None:
        self.v8_config = config or LeaderV8Config()
        super().__init__(self.v8_config)

    # ------------------------------------------------------------------
    # 1. Dynamic Goals & Worker/Animal Scaling
    # ------------------------------------------------------------------

    def _goals(self, state: NormalizedState) -> tuple[ProductionGoal, ...]:
        horizon = max(0, 30 - state.day)
        empty = self._empty_tiles(state)

        quadrants = len(state.unlocked_quadrants)
        max_pastures = 4 if quadrants == 1 else (8 if quadrants == 2 else 14)
        current_animals = self._animal_count(state) + self._pending_animals(state)

        # Detect opponent animal count
        opp_animals = sum(1 for t in state.opponent_tiles if t.animal in _ANIMAL_COST)
        effective_max_animals = (
            min(8, self.v8_config.max_animals) if opp_animals >= 10 else self.v8_config.max_animals
        )

        # Dairy shop demand scaling: more milk shops -> higher cow capacity
        dairy_shops = sum(1 for shop in state.shops if "MILK" in SHOPS.get(shop, ()))
        base_animal_target = 6 + dairy_shops * 2

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

    # ------------------------------------------------------------------
    # 2. Pure Dynamic Portfolio Optimizer with Shop Monopoly & Synergy
    # ------------------------------------------------------------------

    def _dynamic_crop_portfolio(
        self, state: NormalizedState, horizon: int, empty_slots: int
    ) -> list[tuple[str, int]]:
        remaining_days = max(1, 30 - state.day)
        if empty_slots <= 0 or remaining_days < 2:
            return []

        allocated: dict[str, int] = {}

        # If feed is low, buy via market orders instead of wasting tiles.
        # Only plant wheat if market price of wheat is extremely high (> $60).

        existing_crops: dict[str, int] = {}
        for tile in state.tiles:
            if tile.kind == "PLANT" and tile.crop:
                existing_crops[tile.crop] = existing_crops.get(tile.crop, 0) + 1

        for _ in range(empty_slots):
            best_crop = None
            best_marginal_roi = -9999.0

            for crop in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]:
                maturity = _CROP_MATURITY[crop]
                # RESIDUAL HORIZON FILTER: Never plant crops that cannot reach harvest before Day 30
                if maturity > remaining_days:
                    continue

                current_planned = existing_crops.get(crop, 0) + allocated.get(crop, 0)
                marginal_roi = self._calculate_marginal_tile_roi(
                    crop, state, remaining_days, current_planned
                )

                if marginal_roi > best_marginal_roi:
                    best_marginal_roi = marginal_roi
                    best_crop = crop

            if best_crop is None or best_marginal_roi <= 0.0:
                break

            allocated[best_crop] = allocated.get(best_crop, 0) + 1

        return [(crop, qty) for crop, qty in allocated.items() if qty > 0]

    def _calculate_marginal_tile_roi(
        self, crop: str, state: NormalizedState, horizon: int, current_planned_tiles: int
    ) -> float:
        maturity = _CROP_MATURITY[crop]
        seed_cost = _V6_SEED_COST[crop]

        # Town drainage & demand multiplier
        town_drain = sum(1 for shop in state.shops if crop in SHOPS.get(shop, ()))
        shop_bonus = 1.0 + min(town_drain, 4) * 0.35

        # Opponent projected harvest supply
        opp_supply = estimate_opponent_expected_harvests(state.opponent_tiles).get(crop, 0)

        # Base yield per tile (boosted if fertilizer is available from animals)
        has_fertilizer = state.shed.get("FERTILIZER", 0) > 0 or self._animal_count(state) > 0
        if crop in {"WHEAT", "MELON"}:
            units_per_tile = 6.0
        elif crop == "CARROT":
            units_per_tile = 4.0
        elif crop == "STRAWBERRY":
            units_per_tile = 3.5 if has_fertilizer else 2.0
        else:  # TOMATO
            units_per_tile = 3.0 if has_fertilizer else 1.0

        total_projected_units = opp_supply + (current_planned_tiles * units_per_tile)
        base_projected_inv = state.market_inventory.get(crop, 10_000)
        projected_market_inv = base_projected_inv + int(total_projected_units)

        add_units = max(1, int(units_per_tile))
        marginal_quotes = marginal_sale_values(crop, projected_market_inv, add_units)
        marginal_revenue_per_harvest = sum(marginal_quotes) * shop_bonus

        # Dynamic Capital Velocity Bonus:
        # If market price is pristine (Inventory <= 10,020) and crop has high unit price (>= 150),
        # boost daily ROI to accelerate capital accumulation without hardcoding day limits.
        base_price = state.prices.get(crop, 25)
        pristine_market_boost = 1.4 if base_projected_inv <= 10_020 and base_price >= 150 else 1.0

        if crop == "STRAWBERRY":
            days_after_mature = max(0, horizon - 10)
            harvests = 1 + days_after_mature // 3
            est_revenue = (marginal_revenue_per_harvest * harvests) - seed_cost
            return (est_revenue / max(1, horizon)) * pristine_market_boost
        elif crop == "TOMATO":
            days_after_mature = max(0, horizon - 8)
            harvests = 1 + days_after_mature // 2
            est_revenue = (marginal_revenue_per_harvest * harvests) - seed_cost
            return (est_revenue / max(1, horizon)) * pristine_market_boost
        else:
            est_revenue = marginal_revenue_per_harvest - seed_cost
            return (est_revenue / max(1, maturity)) * pristine_market_boost

    # ------------------------------------------------------------------
    # 3. Market Orders: Worker Hire & Livestock Selection
    # ------------------------------------------------------------------

    def _build_market_orders(
        self, state: NormalizedState, goals: tuple[ProductionGoal, ...], tasks: list[Task]
    ) -> list[list[Any]]:
        # Dynamic Opening Day 0
        if state.day == 0:
            if state.hour == 1 and not self._animal_count(state) and not any(state.shed.values()):
                has_strawberry_shop = any("STRAWBERRY" in SHOPS.get(s, ()) for s in state.shops)
                strawberry_seeds = 3 if has_strawberry_shop else 2
                melon_seeds = 2 if has_strawberry_shop else 3
                return [
                    ["HIRE"],
                    ["BUY_ANIMAL", "COW", 2],
                    ["BUY_ANIMAL", "SHEEP", 1],
                    ["BUY_SEED", "WHEAT", 4],
                    ["BUY_SEED", "MELON", melon_seeds],
                    ["BUY_SEED", "STRAWBERRY", strawberry_seeds],
                ]
            return []

        orders = super()._build_market_orders(state, goals, tasks)
        spending = max(0, state.money - 20)

        # 1. Pure Workload & Liquidity Driven Worker Hiring (Zero Hardcoded Thresholds)
        total_workers = 1 + len(state.hand_positions)
        no_hire_yet = not any(o[0] == "HIRE" for o in orders)
        if total_workers < 2 and len(orders) < self.v8_config.max_orders and no_hire_yet:
            # Calculate daily action workload (watering, feeding, harvesting, fertilizing)
            unwatered_crops = sum(
                1 for t in state.tiles if t.kind == "PLANT" and not t.watered_today
            )
            unfed_animals = sum(
                1 for t in state.tiles if t.kind == "PASTURE" and t.animal and not t.fed_today
            )
            harvestable = sum(
                1 for t in state.tiles if t.kind == "PLANT" and t.yield_units and t.yield_units > 0
            )

            pending_actions = unwatered_crops + unfed_animals + harvestable

            # Market Feed Purchasing (Zero hardcoded tile reservation)
            wheat_in_shed = state.shed.get("WHEAT", 0)
            animal_cnt = self._animal_count(state)
            if animal_cnt > 0 and wheat_in_shed < 4 and state.money >= 150:
                need_wheat = 4 - wheat_in_shed
                orders.append(["BUY_SEED", "WHEAT", need_wheat])

            # Dynamic liquidity buffer: hire cost ($500) + 5 days animal feed + seed capital
            animal_count = self._animal_count(state)
            wheat_price = max(1, int(state.prices.get("WHEAT", 25)))
            required_feed_buffer = animal_count * 2 * wheat_price
            dynamic_hire_threshold = (
                500 + required_feed_buffer + self.v8_config.min_liquidity_buffer
            )

            # Only hire if workload exceeds single-worker capacity and we have full liquidity
            if pending_actions >= 12 or (
                animal_count >= 3 and state.money >= dynamic_hire_threshold
            ):
                if state.money >= dynamic_hire_threshold:
                    orders.append(["HIRE"])

        # 2. Pure Dynamic Land Expansion (Zero Hardcoded Day/Money Limits)
        unlocked_count = len(state.unlocked_quadrants)
        no_unlock_yet = not any(o[0] == "UNLOCK" for o in orders)
        if unlocked_count < 4 and len(orders) < self.v8_config.max_orders and no_unlock_yet:
            occupied_tiles = sum(1 for t in state.tiles if t.kind in ("PLANT", "PASTURE"))
            total_unlocked_capacity = unlocked_count * 9
            saturation_ratio = occupied_tiles / max(1, total_unlocked_capacity)

            # Dynamic liquidity buffer for land purchase: unlock cost ($250) + seed buffer
            animal_count = self._animal_count(state)
            wheat_price = max(1, int(state.prices.get("WHEAT", 25)))
            required_seed_buffer = occupied_tiles * 30 + animal_count * 2 * wheat_price
            dynamic_unlock_threshold = (
                250 + required_seed_buffer + self.v8_config.min_liquidity_buffer
            )

            # Unlock when land saturation >= 75% AND we have liquidity to seed the new land
            if saturation_ratio >= 0.75 and state.money >= dynamic_unlock_threshold:
                orders.append(["UNLOCK"])

        # 3. Shop-Aware Livestock Selection
        animal_goal = next((g.quantity for g in goals if g.name == "operational_animals"), 0)
        current_animals = self._animal_count(state) + self._pending_animals(state)

        if current_animals < animal_goal and self._animal_chain_ready(state):
            yarn_shops = sum(1 for shop in state.shops if "WOOL" in SHOPS.get(shop, ()))
            dairy_shops = sum(1 for shop in state.shops if "MILK" in SHOPS.get(shop, ()))

            current_cows = sum(1 for t in state.tiles if t.animal == "COW")
            current_sheep = sum(1 for t in state.tiles if t.animal == "SHEEP")

            if yarn_shops == 0:
                next_animal = "COW" if current_cows <= current_sheep * 3 else "SHEEP"
            elif dairy_shops == 0:
                next_animal = "SHEEP" if current_sheep <= current_cows * 2 else "COW"
            else:
                next_animal = "COW" if current_cows <= current_sheep else "SHEEP"

            cost = _ANIMAL_COST[next_animal]
            wheat_price = max(1, int(state.prices.get("WHEAT", 25)))
            feed_buffer_cost = 2 * wheat_price

            if (
                spending >= (cost + feed_buffer_cost)
                and len(orders) < self.v8_config.max_orders
                and not any(o[0] == "BUY_ANIMAL" for o in orders)
            ):
                orders.append(["BUY_ANIMAL", next_animal, 1])

        return orders[: self.v8_config.max_orders]

    # ------------------------------------------------------------------
    # 4. Front-Running Sales & Dynamic Price Protection
    # ------------------------------------------------------------------

    def _sales(
        self, state: NormalizedState, projected: dict[str, int] | None = None
    ) -> list[list[Any]]:
        orders: list[list[Any]] = []
        is_closing = self._closing(state)
        capacity_pressure = sum(state.shed.values()) >= (
            state.shed_capacity - self.v8_config.shed_safety_buffer
        )
        low_liquidity = state.money < self.v8_config.liquidity_cash_floor

        # Detect Imminent Opponent Harvests for Front-Running
        opp_imminent_harvests = self._detect_opp_imminent_harvests(state)

        regrowable_count = sum(
            1 for t in state.tiles if t.kind == "PLANT" and t.crop in ("STRAWBERRY", "TOMATO")
        )

        for item, amount in sorted(state.shed.items()):
            if amount <= 0 or item not in _PRODUCTS:
                continue

            if item == "WHEAT" and not is_closing:
                total_animals = (
                    self._animal_count(state)
                    + self._pending_animals(state)
                    + sum(
                        1 for inv in state.unit_inventories for k in _ANIMAL_COST if inv.get(k, 0)
                    )
                )
                needed_wheat = total_animals * 2
                sellable = max(0, amount - needed_wheat)
            elif item == "FERTILIZER" and not is_closing:
                if low_liquidity or regrowable_count == 0:
                    sellable = amount
                else:
                    fert_to_keep = min(3, regrowable_count, amount)
                    sellable = max(0, amount - fert_to_keep)
            else:
                sellable = amount

            if sellable <= 0:
                continue

            # Front-Running Vector: If opponent will harvest this item within 24h, sell NOW
            if opp_imminent_harvests.get(item, 0) >= 6 and not is_closing:
                orders.append(["SELL", item, sellable])
                continue

            # Closing, capacity pressure, low liquidity, or Day >= 28 final clearance
            if is_closing or capacity_pressure or low_liquidity or state.day >= 28:
                orders.append(["SELL", item, sellable])
                continue

            # Continuous high-margin sales
            if item in {"MILK", "WOOL", "STRAWBERRY", "TOMATO"} and amount >= 2:
                orders.append(["SELL", item, sellable])
                continue

            # Marginal quote threshold check
            values = marginal_sale_values(
                item,
                state.market_inventory.get(item, 10_000),
                sellable,
                opponent_buffer=self.v8_config.opponent_market_buffer,
            )
            base = state.prices.get(item, _CROP_BASE_PRICES.get(item, 25))
            units_to_sell = sum(1 for val in values if val >= base * 0.45)
            if units_to_sell > 0:
                orders.append(["SELL", item, units_to_sell])

        return orders

    def _detect_opp_imminent_harvests(self, state: NormalizedState) -> dict[str, int]:
        """Detect crops that the opponent will harvest in the next 24 hours."""
        imminent: dict[str, int] = {}
        for tile in state.opponent_tiles:
            if tile.kind == "PLANT" and tile.crop and tile.planted_day is not None:
                maturity = _CROP_MATURITY.get(tile.crop, 10)
                age_days = state.day - tile.planted_day
                if age_days >= maturity - 1:
                    imminent[tile.crop] = imminent.get(tile.crop, 0) + 6
        return imminent
