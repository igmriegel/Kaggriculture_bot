"""ROI calculations, opponent crop tracking, and harvest horizon planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agent.core.state import NormalizedState, Tile
from agent.domain.economics import MARKET_I0, market_price

CROPS_SPEC = {
    "WHEAT": {
        "seed": 10,
        "first_yield_day": 2,
        "max_yield_day": 4,
        "interval": 0,
        "max_yield": 6,
        "ongoing": False,
        "product": "WHEAT",
    },
    "CARROT": {
        "seed": 20,
        "first_yield_day": 2,
        "max_yield_day": 3,
        "interval": 0,
        "max_yield": 4,
        "ongoing": False,
        "product": "CARROT",
    },
    "TOMATO": {
        "seed": 50,
        "first_yield_day": 8,
        "max_yield_day": 8,
        "interval": 1,
        "max_yield": 4,
        "ongoing": True,
        "product": "TOMATO",
    },
    "STRAWBERRY": {
        "seed": 100,
        "first_yield_day": 10,
        "max_yield_day": 10,
        "interval": 2,
        "max_yield": 4,
        "ongoing": True,
        "product": "STRAWBERRY",
    },
    "MELON": {
        "seed": 80,
        "first_yield_day": 10,
        "max_yield_day": 12,
        "interval": 0,
        "max_yield": 6,
        "ongoing": False,
        "product": "MELON",
    },
}

TOTAL_SEASON_DAYS = 30


@dataclass(frozen=True)
class CropROI:
    crop: str
    expected_profit_per_day: float
    expected_revenue: float
    seed_cost: int
    days_to_first_yield: int
    closing_day: int
    viable_to_plant: bool


def calculate_closing_day(crop: str, total_days: int = TOTAL_SEASON_DAYS) -> int:
    """Last day where planting this crop still yields before season end."""
    spec = CROPS_SPEC.get(crop)
    if not spec:
        return 0
    return total_days - int(spec["first_yield_day"])


def estimate_opponent_expected_harvests(opponent_tiles: tuple[Tile, ...]) -> dict[str, int]:
    """Track opponent planted crops and project expected units coming to market."""
    projected: dict[str, int] = {}
    for tile in opponent_tiles:
        if tile.kind == "PLANT" and tile.crop:
            crop = tile.crop
            spec = CROPS_SPEC.get(crop, {})
            max_yield = int(spec.get("max_yield", 1))
            projected[crop] = projected.get(crop, 0) + max_yield
        elif tile.animal == "GOOSE":
            projected["EGG"] = projected.get("EGG", 0) + 10
    return projected


def evaluate_crops_roi(
    state: NormalizedState,
    *,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> dict[str, CropROI]:
    """Calculate expected ROI and profitability for each crop given current day and market state."""
    opp_harvests = estimate_opponent_expected_harvests(state.opponent_tiles)
    results: dict[str, CropROI] = {}

    days_remaining = max(0, TOTAL_SEASON_DAYS - state.day)

    for crop, spec in CROPS_SPEC.items():
        closing_day = calculate_closing_day(crop)
        first_yield = int(spec["first_yield_day"])
        max_yield_day = int(spec["max_yield_day"])
        seed_cost = int(spec["seed"])
        product = str(spec["product"])

        if state.day > closing_day:
            results[crop] = CropROI(
                crop=crop,
                expected_profit_per_day=-1.0,
                expected_revenue=0.0,
                seed_cost=seed_cost,
                days_to_first_yield=first_yield,
                closing_day=closing_day,
                viable_to_plant=False,
            )
            continue

        current_market_inv = state.market_inventory.get(product, MARKET_I0)
        opp_supply = opp_harvests.get(product, 0)
        projected_inv = current_market_inv + opp_supply
        est_unit_price = market_price(product, projected_inv, overrides)

        is_ongoing = bool(spec["ongoing"])
        interval = int(spec["interval"])
        max_yield = int(spec["max_yield"])

        if not is_ongoing:
            # Yield units accumulate during window [ (max_yield_day+1)//2, max_yield_day ]
            window_len = max_yield_day - ((max_yield_day + 1) // 2) + 1
            yield_units = min(max_yield, window_len)
            revenue = yield_units * est_unit_price
            cycle_days = max_yield_day
            profit = revenue - seed_cost
            # Capital velocity: profit generated per seed dollar invested per cycle day
            profit_per_day = profit / (seed_cost * max(1, cycle_days))
        else:
            days_productive = max(0, days_remaining - first_yield)
            harvests = 1 + (days_productive // max(1, interval + 1))
            total_units = harvests * max_yield
            revenue = total_units * est_unit_price
            profit = revenue - seed_cost
            profit_per_day = profit / (seed_cost * max(1, days_remaining))

        results[crop] = CropROI(
            crop=crop,
            expected_profit_per_day=profit_per_day,
            expected_revenue=revenue,
            seed_cost=seed_cost,
            days_to_first_yield=first_yield,
            closing_day=closing_day,
            viable_to_plant=profit > 0 and state.day <= closing_day,
        )

    return results


def best_crop_to_plant(
    state: NormalizedState,
    *,
    min_budget: int = 0,
    overrides: Mapping[str, Mapping[str, object]] | None = None,
) -> str | None:
    """Return the crop with highest expected daily profit that the bot can afford."""
    rois = evaluate_crops_roi(state, overrides=overrides)
    viable = [
        roi
        for roi in rois.values()
        if roi.viable_to_plant and state.money >= min_budget + roi.seed_cost
    ]
    if not viable:
        return None
    viable.sort(key=lambda r: r.expected_profit_per_day, reverse=True)
    return viable[0].crop
